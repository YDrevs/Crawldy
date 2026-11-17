"""HTTP-шар аудиту: безпечний fetch із SSRF-захистом і лімітами."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse

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
        "224.0.0.0/4",
        "240.0.0.0/4",
        "::/96",
        "::1/128",
        "64:ff9b:1::/48",
        "fc00::/7",
        "fe80::/10",
        "ff00::/8",
    )
]

# NAT64 (RFC 6052): останні 32 біти — це IPv4, куди насправді піде запит.
_NAT64 = ipaddress.ip_network("64:ff9b::/96")

IpAddress = ipaddress.IPv4Address | ipaddress.IPv6Address


def _is_forbidden(ip: IpAddress) -> bool:
    """Чи заборонено ходити на цю адресу.

    IPv6-обгортки IPv4 (mapped, 6to4, NAT64) розгортаються: інакше
    `::ffff:127.0.0.1` чи `64:ff9b::a9fe:a9fe` ведуть у loopback і
    метадані хмари, хоча як IPv6 не схожі ні на те, ні на інше. Teredo
    забороняється цілком — тунель на чужий сервер нам не потрібен.
    Головна умова — `is_global`; `BLOCKED_NETWORKS` лишається явним
    списком поверх неї, бо `is_global` не відсікає ані multicast, ані
    зарезервоване.
    """
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return _is_forbidden(ip.ipv4_mapped)
        if ip.sixtofour is not None:
            return _is_forbidden(ip.sixtofour)
        if ip in _NAT64:
            return _is_forbidden(ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF))
        if ip.teredo is not None:
            return True
    if not ip.is_global or ip.is_multicast or ip.is_reserved or ip.is_unspecified:
        return True
    return any(ip in net for net in BLOCKED_NETWORKS)


class SiteUnreachable(RuntimeError):
    """Сайт не віддав вхідну сторінку: DNS, TLS, таймаут, ланцюг редиректів.

    Окремий тип, а не RuntimeError із текстом. Від класу невдачі залежить,
    чи повертається квота, а розбирати повідомлення мовою — рівно та
    пастка, від якої проєкт уже відмовився в деградаціях.
    """


class UnsafeUrlError(ValueError):
    pass


# Скільки переходів ми готові пройти. Шостий — це вже `redirect_limit_exceeded`,
# рівно як `max_redirects=5` у httpx, на якому стояла поведінка до цього.
MAX_REDIRECTS = 5


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


async def assert_public_host(url: str) -> None:
    """Резолвимо DNS і перевіряємо, що IP не приватний. Захист від SSRF."""
    if settings.allow_private_hosts:
        return
    host = urlparse(url).hostname
    if not host:
        raise UnsafeUrlError("URL без хоста")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"DNS не резолвиться: {host}") from exc
    for info in infos:
        # IPv6 link-local приходить зі scope: `fe80::1%eth0`.
        ip = ipaddress.ip_address(str(info[4][0]).split("%", 1)[0])
        if _is_forbidden(ip):
            # Сама адреса — лише в лог: текст помилки доходить до клієнта,
            # а перелік внутрішніх IP за іменами — розвідка мережі воркера.
            log.warning("ssrf_blocked", host=host, ip=str(ip))
            raise UnsafeUrlError(f"хост {host} резолвиться у приватну чи службову адресу")


Resolver = Callable[[str, int], Awaitable[list[str]]]


async def _system_resolve(host: str, port: int) -> list[str]:
    infos = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
    )
    # Порядок відповіді зберігаємо (його вже впорядкував резолвер),
    # дублікати — ні. Scope у `fe80::1%eth0` зрізаємо.
    return list(dict.fromkeys(str(info[4][0]).split("%", 1)[0] for info in infos))


class _GuardedBackend(httpcore.AsyncNetworkBackend):
    """Мережевий бекенд, у якому перевірка адреси й зʼєднання — одна дія.

    Без нього httpx резолвить імʼя вдруге сам, і DNS із TTL 0 віддає
    публічну адресу перевірці й `127.0.0.1` — зʼєднанню (rebinding).
    Тут імʼя резолвиться один раз, кожна адреса відповіді проходить
    `_is_forbidden`, і зʼєднання відкривається саме на перевірений IP.
    SNI й `Host` лишаються оригінальними: httpcore бере їх з адреси
    запиту, а не з того, куди ми конектимося. Кожен крок редиректу
    відкриває своє зʼєднання й проходить тут само.
    """

    def __init__(
        self,
        inner: httpcore.AsyncNetworkBackend | None = None,
        resolve: Resolver | None = None,
    ) -> None:
        self._inner = inner or httpcore.AnyIOBackend()
        self._resolve = resolve or _system_resolve

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,  # noqa: ASYNC109 — сигнатура httpcore
        local_address: str | None = None,
        socket_options: Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        try:
            ips = await asyncio.wait_for(self._resolve(host, port), timeout)
        except (OSError, TimeoutError) as exc:
            raise httpcore.ConnectError(f"DNS не резолвиться: {host}") from exc
        if not ips:
            raise httpcore.ConnectError(f"DNS не резолвиться: {host}")
        if not settings.allow_private_hosts:
            for raw in ips:
                if _is_forbidden(ipaddress.ip_address(raw)):
                    log.warning("ssrf_blocked", host=host, ip=raw)
                    raise UnsafeUrlError(f"хост {host} резолвиться у приватну чи службову адресу")

        last: Exception | None = None
        for ip in ips:
            try:
                return await self._inner.connect_tcp(
                    ip,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except httpcore.ConnectError as exc:
                last = exc
        assert last is not None
        raise last

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


def guarded_transport(
    *,
    verify: bool = True,
    limits: httpx.Limits | None = None,
) -> httpx.AsyncHTTPTransport:
    """Транспорт httpx, усі зʼєднання якого проходять `_GuardedBackend`.

    Публічного параметра для бекенду в `AsyncHTTPTransport` немає, тож
    підмінюється поле пулу; `test_fetcher_pinning` ловить, якщо оновлення
    httpx його перейменує. `trust_env=False`: проксі з оточення зʼєднувався
    б сам, повз перевірку.
    """
    transport = httpx.AsyncHTTPTransport(
        verify=verify,
        http2=True,
        trust_env=False,
        limits=limits or httpx.Limits(max_connections=20, max_keepalive_connections=10),
    )
    pool = transport._pool
    assert hasattr(pool, "_network_backend"), "httpcore змінив внутрішнє поле пулу"
    pool._network_backend = _GuardedBackend()
    return transport


class Fetcher:
    """httpx з таймаутами, лімітом тіла й SSRF-перевіркою кожного редіректу ДО переходу."""

    def __init__(
        self,
        concurrency: int | None = None,
        *,
        verify_tls: bool = True,
        user_agent: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        # verify_tls=False вмикається лише після того, як звичайна спроба
        # впала саме на сертифікаті: інакше сайт зі зламаним HTTPS не можна
        # ані перевірити, ані показати клієнту, в чому проблема.
        self._sem = asyncio.Semaphore(concurrency or settings.crawl_concurrency)
        self._client = httpx.AsyncClient(
            verify=verify_tls,
            http2=True,
            # Редиректи ведемо самі: httpx проходить увесь ланцюг ДО того,
            # як ми побачимо хоч один крок, тож перевірка `history` після
            # запиту вже нічого не захищала — внутрішня адреса була
            # прочитана. Кожен наступний крок має пройти SSRF-перевірку
            # до того, як ми туди підемо.
            follow_redirects=False,
            trust_env=False,
            transport=transport or guarded_transport(verify=verify_tls),
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
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
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
                return await self._follow(url, started)
            except UnsafeUrlError as exc:
                log.warning("fetch_redirect_blocked", url=url, error=str(exc))
                return _failed(url, str(exc), started)
            except httpx.HTTPError as exc:
                log.warning("fetch_failed", url=url, error=str(exc))
                return _failed(url, f"{type(exc).__name__}: {exc}", started)

    async def _follow(self, url: str, started: float) -> FetchResult:
        hops: list[RedirectHop] = []
        current = url
        while True:
            request = self._client.build_request("GET", current)
            response = await self._client.send(request, stream=True)
            try:
                location = response.headers.get("location")
                if not (response.is_redirect and location):
                    return await self._read(url, response, hops, started)
                # Куди вів цей крок, а не звідки: ланцюг читається як
                # послідовність адрес, на які нас відправляли. Значення
                # заголовка як є — відносне розвʼязує `redirects.py`.
                hops.append(RedirectHop(status_code=response.status_code, url=location))
            finally:
                await response.aclose()

            if len(hops) > MAX_REDIRECTS:
                log.warning("fetch_redirect_limit", url=url, hops=len(hops))
                return _failed(
                    url,
                    f"TooManyRedirects: більше {MAX_REDIRECTS} перенаправлень",
                    started,
                    redirect_limit=True,
                )
            nxt = urljoin(current, location)
            if urlparse(nxt).scheme not in ("http", "https"):
                raise UnsafeUrlError("перенаправлення на непідтримувану схему")
            await assert_public_host(nxt)
            current = nxt

    async def _read(
        self,
        url: str,
        response: httpx.Response,
        hops: list[RedirectHop],
        started: float,
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
            content_type=response.headers.get("content-type", "").split(";")[0].strip() or None,
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
