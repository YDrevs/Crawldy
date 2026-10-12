"""Рендеринг через Playwright: один браузер на аудит, сторінка на URL.

Playwright імпортується ліниво й усередині функції. Це не стилістика:
пакет важкий, у нього окремо завантажуються бінарники браузера, і
відсутність будь-чого з цього не має валити імпорт модуля чеків.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from urllib.parse import urljoin, urlparse

from app.audit.fetcher import MAX_REDIRECTS, UnsafeUrlError, resolve_public
from app.audit.types import RenderResult, ResourceLoad
from app.core.config import settings
from app.core.logging import log

# Скільки чекати на затишшя в мережі. Сторінки з нескінченним
# опитуванням сервера не заспокоюються ніколи, тому networkidle завжди
# із власним таймаутом, після якого беремо те, що встигло відрендеритись.
IDLE_TIMEOUT_MS = 5000

# Ресурси, які на вміст сторінки не впливають, а часу з'їдають більше за
# все інше разом. Відео та шрифти вимикаємо; картинки лишаємо — вони
# потрібні для сигналів про зображення.
BLOCKED_RESOURCES = ("media", "font")


# Ми самі обриваємо завантаження шрифтів і відео — і браузер чесно пише
# про це в консоль. Без цього фільтра кожен сайт отримував би від нас
# звинувачення у зламаному JS за те, що зламали ми.
_OUR_OWN_FAILURES = ("net::err_failed", "failed to load resource")


def _is_our_own_doing(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _OUR_OWN_FAILURES)


_NETWORK_SCHEMES = ("http", "https", "ws", "wss")


class _Guard:
    """SSRF-перевірка для браузера аудиту, один екземпляр на рендер.

    Сторінка чужого сайту керує браузером повністю: навігація, iframe,
    `fetch` зі скрипта — усе це запити з нашої мережі. Перевірка та сама,
    що й у `Fetcher`; вердикт кешується по хосту на один рендер.

    Playwright викликає `page.route` лише для ПЕРШОЇ адреси запиту: за
    перенаправленням, яке браузер отримав (навіть через `route.fulfill`),
    він іде сам, повз обробник. Тому навігацію завантажуємо через
    `route.fetch` без перенаправлень. Відповідь 3xx головному фрейму не
    віддаємо: запамʼятовуємо ціль, перериваємо запит, і `goto` до неї
    робить рендер — новим запитом, який знову проходить перевірку.
    """

    def __init__(self) -> None:
        self._verdicts: dict[str, bool] = {}
        self.redirect_to: str | None = None

    async def is_public(self, url: str) -> bool:
        if settings.allow_private_hosts:
            return True
        parsed = urlparse(url)
        host = parsed.hostname
        if parsed.scheme not in _NETWORK_SCHEMES or not host:
            return False
        if host not in self._verdicts:
            try:
                await resolve_public(host)
                self._verdicts[host] = True
            except UnsafeUrlError:
                self._verdicts[host] = False
            except Exception:  # noqa: BLE001 — не змогли перевірити, значить не пускаємо
                self._verdicts[host] = False
        return self._verdicts[host]

    async def route(self, route: Any) -> None:
        request = route.request
        if request.resource_type in BLOCKED_RESOURCES:
            await route.abort()
            return
        if not await self.is_public(request.url):
            log.warning("render_blocked", url=request.url[:300])
            await route.abort("blockedbyclient")
            return
        if not request.is_navigation_request():
            await route.continue_()
            return
        response = await route.fetch(max_redirects=0, timeout=settings.http_timeout_s * 1000)
        location = response.headers.get("location")
        if not (300 <= response.status < 400 and location):
            await route.fulfill(response=response)
            return
        target = urljoin(request.url, location)
        if not await self.is_public(target):
            log.warning("render_blocked", url=target[:300])
            await route.abort("blockedbyclient")
            return
        if request.frame.parent_frame is None:
            self.redirect_to = target
            await route.abort("aborted")
            return
        # Перенаправлення всередині iframe: наступний крок браузер зробить
        # сам. Вміст чужого iframe у `page.content()` не потрапляє, тож
        # прочитати внутрішню відповідь звідти не можна; лишковий ризик
        # «сліпого» запиту закриває мережевий фільтр воркера, не код.
        await route.fulfill(response=response)

    async def websocket(self, ws: Any) -> None:
        """Вебсокети `page.route` не бачить; перевірка та сама."""
        if await self.is_public(ws.url):
            ws.connect_to_server()
        else:
            log.warning("render_blocked", url=ws.url[:300])
            await ws.close()

    async def goto(self, page: Any, url: str) -> None:
        """`page.goto`, де кожен крок перенаправлення — окремий перевірений запит."""
        target = url
        for _ in range(MAX_REDIRECTS + 1):
            self.redirect_to = None
            try:
                await page.goto(
                    target, wait_until="domcontentloaded", timeout=settings.http_timeout_s * 1000
                )
            except Exception:
                if self.redirect_to is None:
                    raise
            if self.redirect_to is None:
                return
            target = self.redirect_to
        raise RuntimeError(f"більше {MAX_REDIRECTS} перенаправлень")


# Лічильники впізнаються за слідом у самій сторінці, а не за адресою
# скрипта. Адресу можна пропустити через власний домен — Linear роздає
# PostHog з e.linear.app/array/, і за URL його не відрізнити ні від чого.
# Глобальний обʼєкт підмінити не можна: без нього SDK не працює.
#
# Віддається ІМʼЯ глобального обʼєкта з префіксом `global:`, а не назва
# вендора. Дві причини. Перша: `dataLayer` створюють банери згоди без
# GTM, а `analytics.track` має будь-яка бібліотека з методом `track`, —
# вендора вони не називають, і реєстр вирішує це сам (E11-d1). Друга:
# голий рядок у знімку тепер однозначно означає старий аудит, бо новий
# пише лише префіксовані ідентифікатори.
DETECT_GLOBALS_JS = """() => {
  const has = (name) => typeof window[name] !== 'undefined' && window[name] !== null;
  const found = [];
  if (has('gtag')) found.push('global:gtag');
  if (has('ga')) found.push('global:ga');
  if (has('dataLayer')) found.push('global:dataLayer');
  if (has('google_tag_manager')) found.push('global:google_tag_manager');
  const track = has('analytics') && typeof window.analytics.track === 'function';
  if (track) found.push('global:analytics.track');
  if (has('posthog')) found.push('global:posthog');
  if (has('heap')) found.push('global:heap');
  if (has('mixpanel')) found.push('global:mixpanel');
  if (has('amplitude')) found.push('global:amplitude');
  if (has('clarity')) found.push('global:clarity');
  if (has('hj')) found.push('global:hj');
  if (has('plausible')) found.push('global:plausible');
  if (has('fathom')) found.push('global:fathom');
  if (has('_paq')) found.push('global:_paq');
  if (has('Matomo')) found.push('global:Matomo');
  if (has('ym')) found.push('global:ym');
  if (has('va')) found.push('global:va');
  if (has('__VERCEL_INSIGHTS')) found.push('global:__VERCEL_INSIGHTS');
  if (has('FS')) found.push('global:FS');
  if (has('LogRocket')) found.push('global:LogRocket');
  if (has('pendo')) found.push('global:pendo');
  if (has('umami')) found.push('global:umami');
  return found;
}"""


async def _measure(requests: list[Any], *, own_host: str) -> list[ResourceLoad]:
    """Вага й тривалість кожного ресурсу.

    Хост порівнюється за реєстрованим доменом, а не буквально: cdn.site.com
    і site.com — це той самий власник, і рахувати власний CDN як
    сторонній вплив означало б карати за правильно зроблену роздачу.
    """
    own_domain = _registrable(own_host)
    brand = _brand(own_domain)
    loads: list[ResourceLoad] = []
    for request in requests:
        host = urlparse(request.url).netloc.lower()
        try:
            sizes = await request.sizes()
            body = int(sizes.get("responseBodySize", 0) or 0)
            headers = int(sizes.get("responseHeadersSize", 0) or 0)
        except Exception:  # noqa: BLE001 — ресурс міг піти з кешу
            body = headers = 0
        timing = getattr(request, "timing", None) or {}
        start = float(timing.get("startTime", 0) or 0)
        end = float(timing.get("responseEnd", 0) or 0)
        loads.append(
            ResourceLoad(
                url=request.url[:300],
                host=host,
                resource_type=request.resource_type,
                bytes=body + headers,
                duration_ms=int(end - start) if end > start else 0,
                is_third_party=_is_third_party(host, own_domain, brand),
            )
        )
    return loads


def _is_third_party(host: str, own_domain: str, brand: str) -> bool:
    """Чужий домен, а не просто інший.

    Stripe роздає свої ж файли з b.stripecdn.com і images.stripeassets.com.
    За реєстрованим доменом це «чужі» хости, і без цієї перевірки Stripe
    отримував 92% сторонньої ваги — знахідку, яка була б просто неправдою.
    Збіг за назвою бренду не бездоганний, але помиляється в бік
    мовчання, а не наклепу.
    """
    if not host:
        return False
    domain = _registrable(host)
    if domain == own_domain:
        return False
    return not (brand and brand in domain)


# Коротші назви занадто часто трапляються всередині чужих доменів.
_MIN_BRAND = 4


def _brand(domain: str) -> str:
    label = domain.split(".")[0]
    return label if len(label) >= _MIN_BRAND else ""


def _registrable(host: str) -> str:
    """Груба, але передбачувана заміна публічного суфікс-списку.

    Два останні сегменти для звичайних доменів і три для co.uk-подібних.
    Помилки тут коштують дешево: у найгіршому разі власний піддомен
    порахується стороннім, а не навпаки.
    """
    parts = host.split(".")
    if len(parts) <= 2:
        return host
    if parts[-2] in {"co", "com", "org", "net", "gov", "ac"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


class PlaywrightRenderer:
    name = "playwright"

    def __init__(self, viewport: tuple[int, int] = (1280, 800)) -> None:
        self._viewport = viewport
        self._playwright: Any = None
        self._browser: Any = None

    async def _ensure_browser(self) -> Any:
        if self._browser is not None:
            return self._browser
        from playwright.async_api import async_playwright

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            # Без цього Chromium падає в контейнері з /dev/shm за замовчуванням.
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        return self._browser

    async def render(self, url: str) -> RenderResult:
        """Рендер із загальним таймаутом на всю операцію.

        Таймаути на goto й на очікування мережі не покривають решти:
        запуск браузера, створення контексту, page.content() і закриття
        контексту не обмежені нічим. На docs.stripe.com калібрувальний
        прогін через це зависав назавжди — не падав, а саме стояв, і
        відрізнити це від «повільно» ззовні неможливо.

        Таймаут тут, а не в оркестраторі, бо гарантія належить провайдеру:
        будь-хто, хто викличе render(), має отримати відповідь за
        обмежений час, а не покладатися на те, що його обгорнули.
        """
        started = time.perf_counter()
        try:
            return await asyncio.wait_for(
                self._render(url, started), timeout=settings.render_timeout_s
            )
        except TimeoutError:
            log.warning("render_timeout", url=url, seconds=settings.render_timeout_s)
            # Браузер після зависання лишається в невизначеному стані:
            # наступна сторінка на ньому теж має шанс зависнути. Дешевше
            # підняти новий, ніж втратити решту бюджету рендеру.
            await self._discard_browser()
            return RenderResult(
                url=url,
                rendered=False,
                error=f"рендер не вклався у {settings.render_timeout_s:.0f} с",
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )

    async def _discard_browser(self) -> None:
        browser, self._browser = self._browser, None
        if browser is None:
            return
        try:
            await asyncio.wait_for(browser.close(), timeout=5)
        except Exception:  # noqa: BLE001 — закриваємо зависле, збій тут очікуваний
            pass

    async def _render(self, url: str, started: float) -> RenderResult:
        console_errors: list[str] = []
        requests: list[str] = []
        finished: list[Any] = []
        try:
            browser = await self._ensure_browser()
            context = await browser.new_context(
                viewport={"width": self._viewport[0], "height": self._viewport[1]},
                user_agent=settings.user_agent,
                # Запити service worker'а `page.route` не перехоплює взагалі,
                # тобто це був би обхід перевірки адрес.
                service_workers="block",
            )
            guard = _Guard()
            try:
                page = await context.new_page()
                page.on(
                    "console",
                    lambda msg: (
                        console_errors.append(msg.text[:200])
                        if msg.type == "error"
                        and len(console_errors) < 20
                        and not _is_our_own_doing(msg.text)
                        else None
                    ),
                )
                # Запити — найнадійніший слід лічильника. Адресу скрипта
                # можна проксувати, глобального обʼєкта може не бути зовсім
                # (SDK, підключений через import, живе в модулі бандла), але
                # подію лічильник мусить кудись відправити.
                page.on(
                    "request",
                    lambda req: (
                        requests.append(req.url[:300]) if len(requests) < 400 else None
                    ),
                )
                # Розміри лічимо після завантаження, а не в обробнику:
                # request.sizes() — асинхронний виклик, і всередині події
                # він або блокує обробку, або тихо губиться.
                page.on(
                    "requestfinished",
                    lambda req: finished.append(req) if len(finished) < 400 else None,
                )
                await page.route("**/*", guard.route)
                await page.route_web_socket("**/*", guard.websocket)
                await guard.goto(page, url)
                try:
                    await page.wait_for_load_state("networkidle", timeout=IDLE_TIMEOUT_MS)
                except Exception:  # noqa: BLE001
                    # Мережа не заспокоїлась — беремо, що є. Це не помилка:
                    # аналітика й вебсокети шумлять на сторінці вічно.
                    pass
                html = await page.content()
                try:
                    analytics = list(await page.evaluate(DETECT_GLOBALS_JS))
                except Exception:  # noqa: BLE001 — сторінка могла піти в навігацію
                    analytics = []
                resources = await _measure(finished, own_host=urlparse(url).netloc.lower())
            finally:
                await context.close()
        except Exception as exc:  # noqa: BLE001 — падіння браузера не валить аудит
            log.warning("render_failed", url=url, error=str(exc))
            return RenderResult(
                url=url,
                rendered=False,
                error=f"{type(exc).__name__}: {exc}",
                elapsed_ms=int((time.perf_counter() - started) * 1000),
            )

        return RenderResult(
            url=url,
            rendered=True,
            html=html,
            elapsed_ms=int((time.perf_counter() - started) * 1000),
            console_errors=console_errors,
            runtime_analytics=analytics,
            requests=requests,
            resources=resources,
        )

    async def aclose(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None
