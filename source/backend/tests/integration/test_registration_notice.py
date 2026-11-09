"""409 на зайнятій пошті лишається (рішення власника), але власник адреси
дізнається, що її перевіряли: лист, не частіше разу на годину."""

from __future__ import annotations

import pytest

from tests.integration.conftest import PASSWORD, register


@pytest.mark.asyncio
async def test_a_taken_email_notifies_its_owner_once_per_window(client, registration_notices):
    await register(client, "owner@example.com")
    await client.post("/v1/auth/logout")

    for _ in range(3):
        response = await client.post(
            "/v1/auth/register", json={"email": "owner@example.com", "password": PASSWORD}
        )
        assert response.status_code == 409

    assert registration_notices == ["owner@example.com"]


@pytest.mark.asyncio
async def test_a_new_email_sends_no_notice(client, registration_notices):
    await register(client, "fresh@example.com")
    assert registration_notices == []
