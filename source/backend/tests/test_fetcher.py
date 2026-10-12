import ipaddress

import httpcore
import httpx
import pytest

from app.audit import fetcher as fetcher_mod
from app.audit.fetcher import (
    MAX_REDIRECTS,
    Fetcher,
    PublicOnlyBackend,
    UnsafeUrlError,
    assert_public_host,
    is_forbidden_ip,
    normalize_url,
    origin_of,
    public_only_transport,
)


def test_normalize_adds_scheme_and_path():
    assert normalize_url("example.com") == "https://example.com/"
    assert normalize_url("HTTPS://Example.com/a?b=1#frag") == "https://example.com/a?b=1"


def test_normalize_rejects_bad_scheme():
    with pytest.raises(UnsafeUrlError):
        normalize_url("ftp://example.com")


def test_origin_of():
    assert origin_of("https://example.com/a/b?c=1") == "https://example.com"


async def test_ssrf_guard_blocks_localhost():
    with pytest.raises(UnsafeUrlError):
        await assert_public_host("http://127.0.0.1:8000/")


async def test_ssrf_guard_blocks_private_range():
    with pytest.raises(UnsafeUrlError):
        await assert_public_host("http://192.168.1.1/")


def test_user_agent_makes_no_claim_it_cannot_keep():
    """detailtyler.com віддавав 403 на «+https://example.com/bot», хоча
    його robots.txt дозволяє всім. Заглушка виглядає для WAF рівно тим,
    чим і є, — ознакою скрапера. Порожньо чесніше за фальшиве посилання."""
    from app.core.config import Settings

    default = str(Settings.model_fields["user_agent"].default)

    assert "example.com" not in default
    assert "example.org" not in default


# --- SSRF: адреси, перенаправлення, зʼєднання --------------------------------


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.1.2.3",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "224.0.0.1",
        "240.0.0.1",
        "255.255.255.255",
        "::1",
        "::",
        "fd00:ec2::254",
        "fe80::1",
        # IPv4, загорнута в IPv6: is_global дивиться на обгортку
        "::ffff:127.0.0.1",
        "::ffff:169.254.169.254",
        "::127.0.0.1",
        "64:ff9b::a9fe:a9fe",
        "2002:a9fe:a9fe::1",
        "ff02::1",
    ],
)
def test_non_public_addresses_are_forbidden(address: str) -> None:
    assert is_forbidden_ip(ipaddress.ip_address(address))


@pytest.mark.parametrize(
    "address", ["8.8.8.8", "93.184.216.34", "2606:4700::1111", "::ffff:8.8.8.8", "64:ff9b::808:808"]
)
def test_public_addresses_are_allowed(address: str) -> None:
    assert not is_forbidden_ip(ipaddress.ip_address(address))


DNS = {"site.test": "93.184.216.34", "other.test": "8.8.8.8", "metadata.test": "169.254.169.254"}


@pytest.fixture
def fake_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    async def resolve(host: str) -> list[str]:
        address = DNS[host]
        if is_forbidden_ip(ipaddress.ip_address(address)):
            raise UnsafeUrlError(f"хост {host} резолвиться у приватний IP {address}")
        return [address]

    monkeypatch.setattr(fetcher_mod, "resolve_public", resolve)


def _fetcher(handler: httpx.MockTransport) -> Fetcher:
    fetcher = Fetcher()
    fetcher._client = httpx.AsyncClient(transport=handler, follow_redirects=False)
    return fetcher


async def test_redirect_to_internal_host_is_never_requested(fake_dns: None) -> None:
    """Останній крок ланцюга не потрапляв у `response.history`, і тіло
    метаданих хмари читалося як сторінка сайту."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if request.url.host == "site.test":
            return httpx.Response(302, headers={"location": "http://metadata.test/latest/"})
        return httpx.Response(200, text="SECRET")

    async with _fetcher(httpx.MockTransport(handler)) as fetcher:
        result = await fetcher.get("https://site.test/")

    assert not result.ok
    assert result.text == ""
    assert "приватний IP" in (result.error or "")
    assert seen == ["https://site.test/"]


async def test_relative_redirects_are_followed_and_recorded(fake_dns: None) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/a":
            return httpx.Response(301, headers={"location": "/b"})
        if request.url.path == "/b":
            return httpx.Response(302, headers={"location": "https://other.test/c"})
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    async with _fetcher(httpx.MockTransport(handler)) as fetcher:
        result = await fetcher.get("https://site.test/a")

    assert result.ok
    assert result.final_url == "https://other.test/c"
    assert [(h.status_code, h.url) for h in result.redirects] == [
        (301, "/b"),
        (302, "https://other.test/c"),
    ]
    assert result.text == "<html>ok</html>"


async def test_endless_redirects_stop_at_the_limit(fake_dns: None) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(302, headers={"location": f"/{calls}"})

    async with _fetcher(httpx.MockTransport(handler)) as fetcher:
        result = await fetcher.get("https://site.test/")

    assert result.redirect_limit_exceeded
    assert not result.ok
    assert calls == MAX_REDIRECTS + 1


class _RecordingBackend(httpcore.AsyncNetworkBackend):
    def __init__(self) -> None:
        self.hosts: list[str] = []

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):  # type: ignore[no-untyped-def]  # noqa: ASYNC109
        self.hosts.append(host)
        raise httpcore.ConnectError("recorded")

    async def connect_unix_socket(self, path, timeout=None, socket_options=None):  # type: ignore[no-untyped-def]  # noqa: ASYNC109
        raise AssertionError

    async def sleep(self, seconds: float) -> None:
        return None


async def test_connection_goes_to_the_checked_ip_not_the_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS rebinding: перевірка й зʼєднання мусять бути одним резолвом."""
    answers = iter([["93.184.216.34"], ["127.0.0.1"]])

    async def resolve(host: str) -> list[str]:
        address = next(answers)
        if is_forbidden_ip(ipaddress.ip_address(address[0])):
            raise UnsafeUrlError("приватний IP")
        return address

    monkeypatch.setattr(fetcher_mod, "resolve_public", resolve)
    inner = _RecordingBackend()
    backend = PublicOnlyBackend(inner)

    with pytest.raises(httpcore.ConnectError):
        await backend.connect_tcp("rebind.test", 443)
    with pytest.raises(UnsafeUrlError):
        await backend.connect_tcp("rebind.test", 443)

    assert inner.hosts == ["93.184.216.34"]


def test_transport_carries_the_public_only_backend() -> None:
    transport = public_only_transport(verify=True, http2=False, limits=httpx.Limits())
    assert isinstance(transport._pool._network_backend, PublicOnlyBackend)


async def test_real_client_refuses_loopback_literal() -> None:
    """Без моків: справжній клієнт Fetcher не відкриває зʼєднання на ::ffff:127.0.0.1."""
    async with Fetcher() as fetcher:
        with pytest.raises(UnsafeUrlError):
            await fetcher._client.get("http://[::ffff:7f00:1]:9/")
