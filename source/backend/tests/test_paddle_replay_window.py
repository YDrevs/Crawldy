"""Вікно повтору вебхука не можна вимкнути налаштуванням.

`if tolerance <= 0: return` перетворював 0 у змінній оточення на
«перехоплений запит приймається вічно».
"""

from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from app.billing.providers import InvalidWebhook, paddle
from app.core.config import Settings


@pytest.mark.parametrize("configured", [0, -5])
def test_a_non_positive_window_still_rejects_an_old_event(
    monkeypatch: pytest.MonkeyPatch, configured: int
) -> None:
    monkeypatch.setattr(paddle.runtime, "get_int", lambda _key: configured)

    with pytest.raises(InvalidWebhook):
        paddle._reject_if_stale(str(int(time.time()) - 86_400))


def test_a_fresh_event_passes_with_the_fallback_window(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(paddle.runtime, "get_int", lambda _key: 0)
    paddle._reject_if_stale(str(int(time.time())))


@pytest.mark.parametrize("value", [0, -1])
def test_settings_refuse_a_non_positive_window(value: int) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, paddle_signature_tolerance_s=value)  # type: ignore[call-arg]
