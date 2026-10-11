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
