import pytest

from app.audit.fetcher import UnsafeUrlError, assert_public_host, normalize_url, origin_of


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


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1",
        "10.1.2.3",
        "169.254.169.254",
        "100.64.0.1",
        "0.0.0.0",
        "240.0.0.1",  # 240/4 — зарезервовано
        "255.255.255.255",
        "224.0.0.1",  # multicast
        "::",
        "::1",
        "::ffff:127.0.0.1",  # IPv4-mapped
        "::ffff:a9fe:a9fe",  # IPv4-mapped 169.254.169.254
        "::127.0.0.1",  # застарілий IPv4-compatible
        "64:ff9b::a9fe:a9fe",  # NAT64 → 169.254.169.254
        "64:ff9b:1::1",  # NAT64 локального вжитку
        "2002:7f00:1::",  # 6to4 → 127.0.0.1
        "2001:0:4136:e378:8000:63bf:3fff:fdd2",  # Teredo
        "fe80::1",
        "fd00::1",
        "ff02::1",  # multicast
    ],
)
def test_forbidden_addresses(ip: str) -> None:
    import ipaddress

    from app.audit.fetcher import _is_forbidden

    assert _is_forbidden(ipaddress.ip_address(ip))


@pytest.mark.parametrize(
    "ip",
    ["93.184.215.14", "1.1.1.1", "2606:4700:4700::1111", "64:ff9b::808:808", "2002:808:808::"],
)
def test_public_addresses_pass(ip: str) -> None:
    import ipaddress

    from app.audit.fetcher import _is_forbidden

    assert not _is_forbidden(ipaddress.ip_address(ip))


async def test_ssrf_guard_blocks_ipv4_mapped_loopback() -> None:
    with pytest.raises(UnsafeUrlError):
        await assert_public_host("http://[::ffff:127.0.0.1]/")


async def test_the_refusal_does_not_name_the_internal_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Перелік внутрішніх IP за іменами — розвідка мережі воркера."""
    import asyncio
    import socket

    async def fake_getaddrinfo(*_a: object, **_k: object) -> list[tuple[object, ...]]:
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.20.30.40", 0))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", fake_getaddrinfo)
    with pytest.raises(UnsafeUrlError) as exc:
        await assert_public_host("https://internal.example/")
    assert "10.20.30.40" not in str(exc.value)
