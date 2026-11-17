"""Вхід, реєстрація й привласнення гостьової організації — з лімітом на адресу.

Блокування акаунта після кількох невдач захищає ОДИН акаунт. Перебір
одного пароля по тисячі адрес (password spraying) і масова реєстрація
його не помічають: кожен акаунт бачить одну спробу. Тому поверх нього —
лічильник на IP, той самий, що вже стоїть на відновленні пароля.
"""

from __future__ import annotations

import pytest

from app.core.config import settings
from tests.integration.conftest import PASSWORD


@pytest.mark.asyncio
async def test_login_attempts_are_limited_per_address(client, monkeypatch):
    monkeypatch.setattr(settings, "login_rate_limit", 3)

    codes = [
        (
            await client.post(
                "/v1/auth/login", json={"email": f"u{i}@example.com", "password": "wrong-pass-1"}
            )
        ).status_code
        for i in range(4)
    ]

    assert codes[:3] == [401, 401, 401]
    assert codes[3] == 429


@pytest.mark.asyncio
async def test_registrations_are_limited_per_address(client, monkeypatch):
    monkeypatch.setattr(settings, "register_rate_limit", 2)

    codes = []
    for i in range(3):
        await client.post("/v1/auth/logout")
        response = await client.post(
            "/v1/auth/register", json={"email": f"n{i}@example.com", "password": PASSWORD}
        )
        codes.append(response.status_code)

    assert codes == [201, 201, 429]


@pytest.mark.asyncio
async def test_claim_is_limited_per_address(client, monkeypatch):
    monkeypatch.setattr(settings, "public_rate_limit", 2)

    codes = [
        (
            await client.post(
                "/v1/public/claim",
                json={"email": "c@example.com", "password": PASSWORD},
                headers={"X-Guest-Token": "nope"},
            )
        ).status_code
        for _ in range(3)
    ]

    assert codes[:2] != [429, 429]
    assert codes[2] == 429
