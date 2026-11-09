"""Вихід і зміна пароля справді прибирають cookie з браузера.

Обидва маршрути ставили `delete_cookie` на інʼєктований `response`, а
повертали НОВИЙ `Response` — заголовок губився. До того ж видалення без
`Secure` браузер відкидає для `__Host-`-cookie, тож у проді воно не
спрацювало б навіть у правильному обʼєкті.
"""

from __future__ import annotations

import pytest
from fastapi import Response

from app.api import deps
from tests.integration.conftest import PASSWORD, register


def _cleared(response) -> bool:
    header = "; ".join(response.headers.get_list("set-cookie")).lower()
    return deps.SESSION_COOKIE.lower() in header and "max-age=0" in header


@pytest.mark.asyncio
async def test_logout_clears_the_cookie(client, db_session):
    await register(client, "out@example.com")

    response = await client.post("/v1/auth/logout")

    assert response.status_code == 204
    assert _cleared(response)


@pytest.mark.asyncio
async def test_password_change_clears_the_cookie(client, db_session):
    await register(client, "pw@example.com")

    response = await client.post(
        "/v1/auth/password/change",
        json={"current_password": PASSWORD, "new_password": PASSWORD + "-new-Long1"},
    )

    assert response.status_code == 204, response.text
    assert _cleared(response)


def test_deletion_carries_the_same_attributes_as_the_cookie(monkeypatch):
    """`__Host-` вимагає Secure і Path=/ і на видаленні теж."""
    monkeypatch.setattr(deps.settings, "app_env", "prod")
    response = Response()

    deps.clear_session_cookie(response)

    header = response.headers["set-cookie"].lower()
    assert "secure" in header
    assert "httponly" in header
    assert "path=/" in header
    assert "samesite=lax" in header
