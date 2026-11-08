"""Глобальний ключ: дефолт не доживає до проду, порожній список — не «пускати всіх».

`dev-key-change-me` стоїть дефолтом і в службовій організації має роль
OWNER. Якщо оточення забуло `API_KEYS`, прод стартував із ключем, який
написаний у публічному репозиторії. А `require_api_key` при порожньому
списку повертав `"anonymous"` — тобто вимкнений ключ означав відкриті
двері, а не зачинені.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.api import deps
from app.core.config import Settings

_PROD = {
    "app_env": "prod",
    "database_url": "postgresql+asyncpg://u:p@localhost/db",
    "redis_url": "redis://localhost:6379",
    "mail_smtp_host": "smtp.example.com",
    "mail_sender": "crawldy@example.com",
    "public_app_url": "https://crawldy.ai",
}


def _settings(**overrides: object) -> Settings:
    return Settings(**{**_PROD, **overrides})  # type: ignore[arg-type]


@pytest.mark.parametrize("env", ["prod", "staging"])
def test_the_default_dev_key_refuses_to_start_outside_local(env: str) -> None:
    with pytest.raises(ValidationError) as exc:
        _settings(app_env=env)
    assert "dev-key-change-me" in str(exc.value)


@pytest.mark.parametrize("env", ["prod", "staging"])
def test_the_dev_key_set_explicitly_is_refused_too(env: str) -> None:
    with pytest.raises(ValidationError):
        _settings(app_env=env, api_keys="real-key-1,dev-key-change-me")


def test_production_with_a_real_key_starts() -> None:
    assert _settings(api_keys="s3cr3t-key-of-sufficient-length").api_keys == [
        "s3cr3t-key-of-sufficient-length"
    ]


def test_production_without_any_global_key_starts() -> None:
    """Без глобального ключа — лише ключі організацій. Це валідний стан."""
    assert _settings(api_keys="").api_keys == []


def test_local_keeps_the_dev_key_for_convenience() -> None:
    assert "dev-key-change-me" in _settings(app_env="local").api_keys


async def test_require_api_key_fails_closed_when_no_key_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(deps.settings, "api_keys", [])

    with pytest.raises(HTTPException) as exc:
        await deps.require_api_key(None)
    assert exc.value.status_code == 401

    with pytest.raises(HTTPException):
        await deps.require_api_key("")


async def test_require_api_key_accepts_only_a_configured_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(deps.settings, "api_keys", ["alpha", "beta"])

    assert await deps.require_api_key("beta") == "beta"
    for wrong in ("gamma", "bet", "betaa", "", None):
        with pytest.raises(HTTPException):
            await deps.require_api_key(wrong)


def test_legacy_actor_needs_a_configured_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps.settings, "api_keys", ["alpha"])
    assert deps._actor_from_legacy_key("alpha") is not None
    assert deps._actor_from_legacy_key("alph") is None

    monkeypatch.setattr(deps.settings, "api_keys", [])
    assert deps._actor_from_legacy_key("alpha") is None
    assert deps._actor_from_legacy_key("") is None


def test_an_empty_entry_in_the_list_never_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps.settings, "api_keys", [""])
    assert deps._actor_from_legacy_key("") is None
