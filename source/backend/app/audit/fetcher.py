"""HTTP-шар аудиту: безпечний fetch із SSRF-захистом і лімітами."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

import httpcore
import httpx

from app.core.config import settings
from app.core.logging import log

BLOCKED_NETWORKS = [
    ipaddress.ip_network(n)
    for n in (
        "0.0.0.0/8",
        "10.0.0.0/8",
        "100.64.0.0/10",
        "127.0.0.0/8",
        "169.254.0.0/16",
        "172.16.0.0/12",
        "192.0.0.0/24",
        "192.168.0.0/16",
        "198.18.0.0/15",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
]

# Скільки перенаправлень проходимо, перш ніж здатися. Раніше це був
# `max_redirects` самого httpx; тепер ланцюг ведемо ми, бо кожен крок
# треба перевірити ДО запиту, а не після.
MAX_REDIRECTS = 5

# IPv6-префікси, всередині яких живе IPv4-адреса. `is_global` дивиться на
# обгортку, а не на вміст: `64:ff9b::a9fe:a9fe` для нього публічна, хоча
# через NAT64 веде на 169.254.169.254.
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_IPV4_COMPATIBLE = ipaddress.ip_network("::/96")


class SiteUnreachable(RuntimeError):
    """Сайт не віддав вхідну сторінку: DNS, TLS, таймаут, ланцюг редиректів.

    Окремий тип, а не RuntimeError із текстом. Від класу невдачі залежить,
    чи повертається квота, а розбирати повідомлення мовою — рівно та
    пастка, від якої проєкт уже відмовився в деградаціях.
    """


class UnsafeUrlError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class RedirectHop:
    """Один крок ланцюга перенаправлень.

    Провайдер-нейтрально: код і адреса, більше нічого. Ланцюг уже був у
    `response.history` — його обходили заради перевірки SSRF і викидали.
    Зберігаємо, щоб детектор ланцюгів можна було додати без повторної
    переробки збору й витягування.
    """

    status_code: int
    url: str


@dataclass(slots=True)
class FetchResult:
    url: str
    final_url: str
    status_code: int | None
    content_type: str | None
    text: str
    body_bytes: int
    elapsed_ms: int
    headers: dict[str, str]
    error: str | None = None
    # Порожньо — перенаправлень не було. Один крок — звичайний редирект;
    # три й більше вже варті окремої розмови з клієнтом.
    redirects: tuple[RedirectHop, ...] = ()
    # Ланцюг не дійшов до кінця: httpx спинився на межі перенаправлень.
    # Прапорець, а не розбір рядка `error`: причина приходить від чужої
    # бібліотеки англійським текстом, і будувати на ньому твердження
    # для клієнта означало б залежати від її формулювань.
    #
    # Історії при цьому немає взагалі — httpx її не віддає. Тому все,
    # що ми маємо право сказати, це «до кінця не дійшли»; чи там петля,
    # ми не бачили.
    redirect_limit_exceeded: bool = False
    # Протокол, який погодився з сервером САМЕ ЦЕЙ клієнт. Не
    # властивість сервера: вибір залежить від ALPN, CDN і того, що
    # вміє наша бібліотека. Порожньо — не знаємо.
    http_version: str = ""
    # Що ми попросили в `Accept-Encoding`. Без цього «сервер не
    # стиснув» не має сенсу: могли й не просити.
    accept_encoding: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None and self.status_code is not None and self.status_code < 400

    @property
    def is_html(self) -> bool:
        return bool(self.content_type and "html" in self.content_type)


def normalize_url(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        raise UnsafeUrlError("порожній URL")
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        raise UnsafeUrlError(f"схема {parsed.scheme!r} не підтримується")
    if not parsed.netloc:
        raise UnsafeUrlError("URL без хоста")
    path = parsed.path or "/"
    return urlunparse((parsed.scheme, parsed.netloc.lower(), path, "", parsed.query, ""))


def origin_of(url: str) -> str:
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc.lower()}"


def is_forbidden_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    """Чи веде адреса туди, куди аудиту чужого сайту ходити не можна.

    Вимога позитивна — адреса мусить бути глобальною, — бо перелік
    заборонених мереж, написаний від руки, завжди чогось не знає. IPv4,
    загорнуту в IPv6 (mapped, compatible, 6to4, NAT64), спершу
    розгортаємо: Linux із dual-stack сокетом зʼєднається саме з нею.
    """
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip.sixtofour is not None:
            ip = ip.sixtofour
        elif ip in _NAT64 or (ip in _IPV4_COMPATIBLE and int(ip) > 1):
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if not ip.is_global or ip.is_multicast:
        return True
    return any(ip in net for net in BLOCKED_NETWORKS)


async def resolve_public(host: str) -> list[str]:
    """Адреси хоста, якщо ВСІ вони публічні; інакше `UnsafeUrlError`.

    Одна непублічна серед кількох — відмова: яку з них обере зʼєднання,
    вирішуємо не ми.
    """
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(
            host, None, proto=socket.IPPROTO_TCP
        )
    except (socket.gaierror, UnicodeError) as exc:
        raise UnsafeUrlError(f"DNS не резолвиться: {host}") from exc
    addresses: list[str] = []
    for info in infos:
        raw = str(info[4][0]).split("%", 1)[0]
        ip = ipaddress.ip_address(raw)
        if is_forbidden_ip(ip):
            raise UnsafeUrlError(f"хост {host} резолвиться у приватний IP {ip}")
        if raw not in addresses:
            addresses.append(raw)
    if not addresses:
        raise UnsafeUrlError(f"DNS не резолвиться: {host}")
    return addresses


async def assert_public_host(url: str) -> None:
    """Резолвимо DNS і перевіряємо, що IP не приватний. Захист від SSRF.

    Це рання перевірка з людською причиною відмови. Сама гарантія живе
    в `PublicOnlyBackend`: перевірка тут і зʼєднання там — два різні
    резолви, і між ними DNS може відповісти інакше.
    """
    if settings.allow_private_hosts:
        return
    host = urlparse(url).hostname
    if not host:
        raise UnsafeUrlError("URL без хоста")
    await resolve_public(host)


class PublicOnlyBackend(httpcore.AsyncNetworkBackend):
    """Мережевий шар httpcore, що зʼєднується лише з перевіреною адресою.

    Резолв, перевірка й зʼєднання — одна операція: сокет відкривається на
    той IP, який щойно пройшов `is_forbidden_ip`, а не на імʼя, яке
    система резолвитиме вдруге. Так закривається DNS rebinding, і кожен
    крок перенаправлення проходить ту саму перевірку автоматично. SNI й
    `Host` лишаються оригінальними: httpcore бере їх із адреси запиту.
    """

    def __init__(self, inner: httpcore.AsyncNetworkBackend) -> None:
        self._inner = inner

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 — сигнатура httpcore
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if settings.allow_private_hosts:
            return await self._inner.connect_tcp(
                host, port, timeout, local_address, socket_options
            )
        addresses = await asyncio.wait_for(resolve_public(host), timeout)
        last: Exception | None = None
        for address in addresses:
            try:
                return await self._inner.connect_tcp(
                    address, port, timeout, local_address, socket_options
                )
            except (httpcore.ConnectError, httpcore.ConnectTimeout) as exc:
                last = exc
        assert last is not None
        raise last

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,  # noqa: ASYNC109 — сигнатура httpcore
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise UnsafeUrlError("unix-сокет не є адресою сайту")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def public_only_transport(
    *, verify: bool, http2: bool, limits: httpx.Limits
) -> httpx.AsyncHTTPTransport:
    """Транспорт httpx, що не зʼєднається з непублічною адресою.

    httpx не дає передати мережевий шар публічно, тож підміняємо його в
    пулі. Якщо атрибут колись зникне, падаємо одразу: тихий транспорт без
    захисту гірший за відмову стартувати.
    """
    transport = httpx.AsyncHTTPTransport(verify=verify, http2=http2, limits=limits)
    pool = transport._pool
    if not isinstance(getattr(pool, "_network_backend", None), httpcore.AsyncNetworkBackend):
        raise RuntimeError("httpcore змінив пул: SSRF-захист зʼєднань не встановлено")
    pool._network_backend = PublicOnlyBackend(pool._network_backend)
    return transport


class Fetcher:
    """Обгортка httpx з таймаутами, лімітом розміру тіла й SSRF-перевіркою редіректів."""

    def __init__(
        self,
        concurrency: int | None = None,
        *,
        verify_tls: bool = True,
        user_agent: str | None = None,
    ) -> None:
        # verify_tls=False вмикається лише після того, як звичайна спроба
        # впала саме на сертифікаті: інакше сайт зі зламаним HTTPS не можна
        # ані перевірити, ані показати клієнту, в чому проблема.
        self._sem = asyncio.Semaphore(concurrency or settings.crawl_concurrency)
        # Перенаправлення ведемо самі (`_send`): httpx перевірив би крок
        # уже ПІСЛЯ того, як сходив туди. `trust_env=False` — проксі зі
        # змінних оточення резолвив би імʼя сам, повз `PublicOnlyBackend`.
        self._client = httpx.AsyncClient(
            transport=public_only_transport(
                verify=verify_tls,
                http2=True,
                limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
            ),
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(settings.http_timeout_s),
            headers={
                # Рядок приходить з опцій аудиту, а не лише з глобальних
                # налаштувань. Сьогодні його ніхто не передає й поведінка
                # звичайного краулу не змінилася; шлях існує заради
                # підтвердженого володіння сайтом, де верифікований краул
                # мусить представлятися інакше, ніж сторонній бот.
                #
                # Наслідок, який доведеться памʼятати: «нас не пустили»
                # і «не пустили б стороннього» — різні твердження, і
                # зводити їх до однієї знахідки для клієнта не можна.
                "User-Agent": user_agent or settings.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    async def __aenter__(self) -> Fetcher:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def get(self, url: str) -> FetchResult:
        started = time.perf_counter()
        try:
            await assert_public_host(url)
        except UnsafeUrlError as exc:
            return _failed(url, str(exc), started)

        async with self._sem:
            try:
                return await self._send(url, started)
            except UnsafeUrlError as exc:
                log.warning("fetch_blocked", url=url, error=str(exc))
                return _failed(url, str(exc), started)
            except httpx.TooManyRedirects as exc:
                log.warning("fetch_redirect_limit", url=url, error=str(exc))
                return _failed(
                    url, f"{type(exc).__name__}: {exc}", started, redirect_limit=True
                )
            except httpx.HTTPError as exc:
                log.warning("fetch_failed", url=url, error=str(exc))
                return _failed(url, f"{type(exc).__name__}: {exc}", started)

    async def _send(self, url: str, started: float) -> FetchResult:
        """Запит із перенаправленнями, де кожен крок перевірено ДО запиту.

        `response.history` httpx не містить останньої адреси й заповнюється
        вже після походу, тож перевірка по ньому пропускала
        `302 → http://169.254.169.254/` і читала тіло відповіді.
        """
        request = self._client.build_request("GET", url)
        hops: list[RedirectHop] = []
        while True:
            response = await self._client.send(request, stream=True)
            try:
                following = response.next_request
                if following is None:
                    return await _read(url, response, hops, started)
                # Куди вів цей крок, а не звідки: ланцюг читається
                # як послідовність адрес, на які нас відправляли.
                hops.append(
                    RedirectHop(
                        status_code=response.status_code,
                        url=str(response.headers.get("location") or response.url),
                    )
                )
            finally:
                await response.aclose()
            if len(hops) > MAX_REDIRECTS:
                raise httpx.TooManyRedirects(
                    "Exceeded maximum allowed redirects.", request=following
                )
            await assert_public_host(str(following.url))
            request = following


async def _read(
    url: str, response: httpx.Response, hops: list[RedirectHop], started: float
) -> FetchResult:
    body = bytearray()
    async for chunk in response.aiter_bytes():
        body.extend(chunk)
        if len(body) > settings.max_response_bytes:
            break
    raw = bytes(body[: settings.max_response_bytes])
    encoding = response.encoding or "utf-8"
    return FetchResult(
        url=url,
        final_url=str(response.url),
        status_code=response.status_code,
        content_type=response.headers.get("content-type", "").split(";")[0].strip()
        or None,
        text=raw.decode(encoding, errors="replace"),
        body_bytes=len(raw),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        headers={k.lower(): v for k, v in response.headers.items()},
        redirects=tuple(hops),
        http_version=response.http_version,
        accept_encoding=response.request.headers.get("accept-encoding", ""),
    )


def _failed(
    url: str, error: str, started: float, *, redirect_limit: bool = False
) -> FetchResult:
    return FetchResult(
        url=url,
        final_url=url,
        status_code=None,
        content_type=None,
        text="",
        body_bytes=0,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
        headers={},
        error=error,
        redirect_limit_exceeded=redirect_limit,
    )
