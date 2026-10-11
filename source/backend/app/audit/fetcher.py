"""HTTP-шар аудиту: безпечний fetch із SSRF-захистом і лімітами."""

from __future__ import annotations

import asyncio
import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urlparse, urlunparse

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
        ip = ipaddress.ip_address(info[4][0])
        if any(ip in net for net in BLOCKED_NETWORKS):
            raise UnsafeUrlError(f"хост {host} резолвиться у приватний IP {ip}")


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
        self._client = httpx.AsyncClient(
            verify=verify_tls,
            http2=True,
            follow_redirects=True,
            max_redirects=5,
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
                async with self._client.stream("GET", url) as response:
                    hops: list[RedirectHop] = []
                    for hop in response.history:
                        await assert_public_host(str(hop.url))
                        # Куди вів цей крок, а не звідки: ланцюг читається
                        # як послідовність адрес, на які нас відправляли.
                        hops.append(
                            RedirectHop(
                                status_code=hop.status_code,
                                url=str(hop.headers.get("location") or hop.url),
                            )
                        )
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
                        accept_encoding=response.request.headers.get(
                            "accept-encoding", ""
                        ),
                    )
            except httpx.TooManyRedirects as exc:
                log.warning("fetch_redirect_limit", url=url, error=str(exc))
                return _failed(
                    url, f"{type(exc).__name__}: {exc}", started, redirect_limit=True
                )
            except httpx.HTTPError as exc:
                log.warning("fetch_failed", url=url, error=str(exc))
                return _failed(url, f"{type(exc).__name__}: {exc}", started)


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
