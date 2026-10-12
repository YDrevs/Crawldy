"""Службовий ключ: без значення за замовчуванням і без «пускаємо всіх».

Ключ `dev-key-change-me` стояв і в коді, і в `.env.example`, давав роль
OWNER службової організації, а прод його не перевіряв. Порожній перелік
ключів відкривав `require_api_key` для будь-кого.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from app.api import deps
from app.core.config import Settings, settings

PROD = {
    "app_env": "prod",
    "database_url": "postgresql+asyncpg://u:p@localhost/db",
    "redis_url": "redis://localhost:6379",
    "mail_smtp_host": "smtp.example.com",
    "mail_sender": "crawldy@example.com",
    "public_app_url": "https://crawldy.ai",
}


def test_there_is_no_service_key_by_default() -> None:
    assert Settings.model_fields["api_keys"].default_factory() == []  # type: ignore[misc]


@pytest.mark.parametrize("key", ["dev-key-change-me", "short-key"])
def test_production_refuses_a_public_or_short_service_key(key: str) -> None:
    with pytest.raises(ValidationError, match="API_KEYS"):
        Settings(**PROD, api_keys=[key])  # type: ignore[arg-type]


def test_production_accepts_a_real_service_key_or_none() -> None:
    Settings(**PROD, api_keys=["k" * 40])  # type: ignore[arg-type]
    Settings(**PROD, api_keys=[])  # type: ignore[arg-type]


async def test_an_empty_key_list_lets_nobody_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_keys", [])
    with pytest.raises(HTTPException) as exc:
        await deps.require_api_key("anything")
    assert exc.value.status_code == 401
    assert deps._actor_from_legacy_key("anything") is None


async def test_the_configured_key_still_works(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_keys", ["service-key"])
    assert await deps.require_api_key("service-key") == "service-key"
    assert deps._actor_from_legacy_key("service-key") is not None
    assert deps._actor_from_legacy_key("service-ke") is None
    with pytest.raises(HTTPException):
        await deps.require_api_key(None)


# --- адреса клієнта для лічильників ------------------------------------------


def _request(peer: str, forwarded: str | None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded is not None else []
    return Request({"type": "http", "headers": headers, "client": (peer, 1234)})


@pytest.mark.parametrize(
    ("trust", "hops", "forwarded", "expected"),
    [
        # Без довіри до проксі заголовок не важить нічого.
        (False, 1, "6.6.6.6", "10.0.0.2"),
        # Клієнт дописав свій «перший запис»; наш проксі додав справжню адресу.
        (True, 1, "6.6.6.6, 203.0.113.7", "203.0.113.7"),
        (True, 2, "6.6.6.6, 203.0.113.7, 10.0.0.9", "203.0.113.7"),
        # Ланцюг коротший за наші проксі — заголовок неповний, віримо зʼєднанню.
        (True, 2, "203.0.113.7", "10.0.0.2"),
        (True, 1, None, "10.0.0.2"),
    ],
)
def test_client_ip_reads_the_forwarded_chain_from_the_right(
    monkeypatch: pytest.MonkeyPatch, trust: bool, hops: int, forwarded: str | None, expected: str
) -> None:
    monkeypatch.setattr(settings, "trust_proxy_headers", trust)
    monkeypatch.setattr(settings, "trusted_proxy_hops", hops)
    assert deps.client_ip(_request("10.0.0.2", forwarded)) == expected
