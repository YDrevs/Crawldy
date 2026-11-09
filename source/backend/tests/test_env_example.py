"""`.env.example` — це документація, яка мусить стартувати.

Порожній `BILLING_REFUNDABLE_FAILURES=` валив валідацію `list`: pydantic-
settings пробує `json.loads` для списків ще до валідаторів. Хто копіював
приклад у `.env`, отримував застосунок, що не піднімається.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import Settings

EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def test_the_example_env_file_loads(monkeypatch: pytest.MonkeyPatch) -> None:
    # Оточення розробника не має підміняти перевірку самого файлу.
    for name in ("APP_ENV", "API_KEYS", "BILLING_REFUNDABLE_FAILURES", "CORS_ORIGINS"):
        monkeypatch.delenv(name, raising=False)

    loaded = Settings(_env_file=EXAMPLE)  # type: ignore[call-arg]

    assert loaded.billing_refundable_failures is None, "порожньо — політика за замовчуванням"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", None),
        ("   ", None),
        ("site_blocked", ["site_blocked"]),
        ("site_blocked, internal_error", ["site_blocked", "internal_error"]),
    ],
)
def test_refundable_failures_parse_from_the_environment(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: list[str] | None
) -> None:
    monkeypatch.setenv("BILLING_REFUNDABLE_FAILURES", raw)

    assert Settings(_env_file=None).billing_refundable_failures == expected  # type: ignore[call-arg]
