"""Фейкова каса існує лише локально.

Фейк приймає будь-який вебхук із `x-fake-signature: valid`, тобто видає
платний звіт безкоштовно. Гейт стояв на `app_env != "prod"`, і staging —
публічний, із справжніми акаунтами — мав його ввімкненим.
"""

from __future__ import annotations

import pytest

from app.billing import registry


@pytest.mark.parametrize("env", ["staging", "prod"])
def test_no_fake_provider_outside_local(env: str) -> None:
    providers, publishers = registry.adapters_for(env)
    assert registry.FAKE_NAME not in providers
    assert registry.FAKE_NAME not in publishers
    assert registry.PADDLE_NAME in providers


def test_local_has_the_fake_for_development() -> None:
    providers, publishers = registry.adapters_for("local")
    assert registry.FAKE_NAME in providers
    assert registry.FAKE_NAME in publishers
