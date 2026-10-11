"""Робоча конфігурація: порядок розвʼязання, секрети, формат.

Без бази: кеш заповнюється рядками напряму (`apply_rows`), як це робив
би `refresh`. Перевіряється саме те, заради чого модуль існує:
збережене адміністратором сильніше за оточення, оточення лишається
фолбеком, секрет не виходить назовні, а без ключа шифрування секрет
не зберігається.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from app.core import runtime_config as runtime
from app.core.config import settings


@pytest.fixture(autouse=True)
def clean_cache() -> Iterator[None]:
    runtime.reset_cache()
    yield
    runtime.reset_cache()


@pytest.fixture
def secrets_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secrets_key", "test-key-for-unit-tests")


def test_environment_is_the_fallback_when_nothing_is_saved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "paddle_env", "live")
    monkeypatch.setattr(settings, "paddle_api_key", "pdl_live_apikey_abc")
    assert runtime.get("paddle_env") == "live"
    assert runtime.source("paddle_env") == "env"
    assert runtime.configured("paddle_api_key") is True
    assert runtime.source("paddle_api_key") == "env"


def test_saved_value_wins_over_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "paddle_env", "live")
    runtime.apply_rows([("paddle_env", "sandbox", False)])
    assert runtime.get("paddle_env") == "sandbox"
    assert runtime.source("paddle_env") == "admin"


def test_default_reported_when_neither_saved_nor_in_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "google_vertex_location", "")
    assert runtime.source("google_vertex_location") == "default"
    assert runtime.get("google_vertex_location") is None
    assert runtime.source("google_vertex_project") in ("env", "none")


def test_secret_never_leaves_in_description(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-secret-value-1234")
    row = runtime.describe("anthropic_api_key")
    assert row["configured"] is True
    assert row["value"] is None
    assert row["hint"] == "1234"
    assert "secret-value" not in str(row)


def test_masked_value_is_hidden_but_not_a_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "paddle_client_token", "test_0123456789abcdef")
    row = runtime.describe("paddle_client_token")
    assert row["secret"] is False
    assert row["value"] is None
    assert row["hint"] == "cdef"


def test_plain_value_is_returned_as_is(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "paddle_env", "live")
    row = runtime.describe("paddle_env")
    assert row["value"] == "live"


def test_encrypted_secret_round_trips_through_the_cache(secrets_key: None) -> None:
    token = runtime._encrypt("pdl_sdbx_apikey_xyz")
    assert "pdl_sdbx" not in token
    runtime.apply_rows([("paddle_api_key", token, True)])
    assert runtime.get("paddle_api_key") == "pdl_sdbx_apikey_xyz"
    assert runtime.source("paddle_api_key") == "admin"


def test_secret_saved_under_another_key_is_reported_not_guessed(
    secrets_key: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    token = runtime._encrypt("pdl_sdbx_apikey_xyz")
    monkeypatch.setattr(settings, "secrets_key", "a-different-key")
    monkeypatch.setattr(settings, "paddle_api_key", None)
    runtime.apply_rows([("paddle_api_key", token, True)])
    assert runtime.configured("paddle_api_key") is False
    assert runtime.describe("paddle_api_key")["undecryptable"] is True


def test_without_secrets_key_storage_is_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "secrets_key", None)
    assert runtime.secrets_storage_available() is False
    with pytest.raises(runtime.SecretsUnavailable):
        runtime._encrypt("x")


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("paddle_env", "sandbox", None),
        ("paddle_env", "prod", "дозволені значення: sandbox, live"),
        ("paddle_timeout_s", "abc", "має бути числом"),
        ("paddle_timeout_s", "-1", "має бути додатним числом"),
        ("paddle_signature_tolerance_s", "300", None),
        ("paddle_api_key", "sk-oops", "очікується початок pdl_live_apikey_ або pdl_sdbx_apikey_"),
        ("anthropic_api_key", "sk-ant-abc", None),
        ("billing_provider", "stripe", "дозволені значення: paddle, fake"),
    ],
)
def test_format_problems(key: str, value: str, expected: str | None) -> None:
    assert runtime.format_problem(key, value) == expected


def test_numeric_getters_fall_back_to_code_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime.apply_rows([("paddle_timeout_s", "7.5", False)])
    assert runtime.get_float("paddle_timeout_s") == 7.5
    assert runtime.get_int("paddle_signature_tolerance_s") == int(
        settings.paddle_signature_tolerance_s
    )


def test_unknown_key_is_refused() -> None:
    with pytest.raises(runtime.UnknownSetting):
        runtime.get("stripe_secret")


def test_keys_are_grouped_by_domain() -> None:
    assert set(runtime.keys_for("payment")) >= {"billing_provider", "paddle_env", "paddle_api_key"}
    assert set(runtime.keys_for("ai")) >= {"anthropic_api_key", "openai_api_key", "google_api_key"}
    assert not set(runtime.keys_for("payment")) & set(runtime.keys_for("ai"))
