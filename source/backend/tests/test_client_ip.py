"""Адреса клієнта для лічильників частоти — N-й запис `X-Forwarded-For` справа.

Три копії `_client_ip` брали ПЕРШИЙ запис, тобто той, який пише сам
клієнт: `X-Forwarded-For: 1.2.3.<n>` давав кожному запиту нове відро, і
ліміт на відновлення пароля, контакт і гостьову воронку обходився одним
рядком. Справжню адресу дописує наш проксі — праворуч.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from starlette.requests import Request

from app.api.client_ip import client_ip
from app.core import config
from app.core.config import Settings


def _request(xff: str | None, peer: str = "10.0.0.5") -> Request:
    headers = [] if xff is None else [(b"x-forwarded-for", xff.encode())]
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


@pytest.fixture
def proxies(monkeypatch: pytest.MonkeyPatch):
    def set_count(n: int) -> None:
        monkeypatch.setattr(config.settings, "trusted_proxy_count", n)

    return set_count


def test_without_trusted_proxies_the_header_is_ignored(proxies) -> None:
    proxies(0)
    assert client_ip(_request("6.6.6.6")) == "10.0.0.5"


def test_one_proxy_takes_the_rightmost_entry(proxies) -> None:
    proxies(1)
    assert client_ip(_request("6.6.6.6, 203.0.113.7")) == "203.0.113.7"


def test_a_spoofed_first_entry_does_not_change_the_bucket(proxies) -> None:
    proxies(1)
    a = client_ip(_request("1.1.1.1, 203.0.113.7"))
    b = client_ip(_request("2.2.2.2, 203.0.113.7"))
    assert a == b == "203.0.113.7"


def test_two_proxies_take_the_second_from_the_right(proxies) -> None:
    proxies(2)
    assert client_ip(_request("6.6.6.6, 203.0.113.7, 172.16.0.2")) == "203.0.113.7"


def test_a_short_chain_falls_back_to_the_peer(proxies) -> None:
    """Ланцюг коротший за кількість проксі — запит обійшов зовнішній проксі."""
    proxies(2)
    assert client_ip(_request("203.0.113.7")) == "10.0.0.5"


def test_garbage_in_the_header_falls_back_to_the_peer(proxies) -> None:
    proxies(1)
    assert client_ip(_request("not-an-ip")) == "10.0.0.5"
    assert client_ip(_request(None)) == "10.0.0.5"


def test_legacy_flag_means_one_proxy() -> None:
    loaded = Settings(_env_file=None, trust_proxy_headers=True)  # type: ignore[call-arg]
    assert loaded.trusted_proxy_count == 1


_PROD = {
    "app_env": "prod",
    "api_keys": "",
    "mail_smtp_host": "smtp.example.com",
    "mail_sender": "crawldy@example.com",
    "public_app_url": "https://crawldy.ai",
}


def test_production_requires_an_ip_hash_salt() -> None:
    with pytest.raises(ValidationError) as exc:
        Settings(_env_file=None, **_PROD)  # type: ignore[arg-type]
    assert "IP_HASH_SALT" in str(exc.value)


def test_production_with_a_salt_starts() -> None:
    Settings(_env_file=None, ip_hash_salt="x" * 32, **_PROD)  # type: ignore[arg-type]
