"""Автентифікація через HTTP: реєстрація, вхід, cookie, ключі API.

Тут перевіряється не домен (він має власні тести), а межа: що саме
потрапляє в cookie, що віддається назовні, і чи однаково виглядають
відмови, які мусять виглядати однаково.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.api.deps import SESSION_COOKIE
from app.identity import service
from app.models.identity import ApiKey, Session, User
from tests.integration.conftest import PASSWORD, register


async def _register(client, email="sergii@example.com", **extra):
    return await register(client, email, **extra)


@pytest.mark.asyncio
async def test_registration_returns_the_new_account_and_its_organization(client):
    response = await _register(client, display_name="Сергій")

    assert response.status_code == 201
    body = response.json()
    assert body["user"]["email"] == "sergii@example.com"
    assert body["organization"]["role"] == "owner"
    assert body["organization"]["is_personal"] is True
    assert body["auth"] == "session"


@pytest.mark.asyncio
async def test_registration_signs_the_person_in(client):
    """Просити увійти одразу після реєстрації — зайвий крок, на якому
    губляться: людина щойно довела, що знає пароль."""
    response = await _register(client)

    assert SESSION_COOKIE in response.cookies


@pytest.mark.asyncio
async def test_the_session_cookie_is_not_readable_by_scripts(client):
    response = await _register(client)

    header = response.headers["set-cookie"]
    assert "HttpOnly" in header
    assert "SameSite=lax" in header.replace("Lax", "lax")


@pytest.mark.asyncio
async def test_the_cookie_carries_a_token_that_is_not_in_the_database(client, db_session):
    response = await _register(client)
    token = response.cookies[SESSION_COOKIE]

    stored = (await db_session.execute(select(Session.token_hash))).scalars().all()

    assert token not in stored
    assert service.hash_token(token) in stored


@pytest.mark.asyncio
async def test_the_password_never_comes_back(client):
    body = (await _register(client)).json()

    assert "password" not in str(body)
    assert "password_hash" not in str(body)


@pytest.mark.asyncio
async def test_the_same_email_twice_is_a_conflict(client):
    await _register(client)

    second = await _register(client)

    assert second.status_code == 409


@pytest.mark.asyncio
async def test_a_weak_password_is_refused(client):
    response = await client.post(
        "/v1/auth/register", json={"email": "a@example.com", "password": "short"}
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_login_with_the_right_password(client):
    await _register(client)
    await client.post("/v1/auth/logout")

    response = await client.post(
        "/v1/auth/login", json={"email": "sergii@example.com", "password": PASSWORD}
    )

    assert response.status_code == 200
    assert response.json()["organization"]["role"] == "owner"


@pytest.mark.asyncio
async def test_every_failed_login_looks_the_same(client):
    """Неіснуюча пошта й невірний пароль дають однакову відповідь.

    Різні тексти або різні коди — це безкоштовна перевірка, чи
    зареєстрована конкретна адреса.
    """
    await _register(client)

    unknown = await client.post(
        "/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    wrong = await client.post(
        "/v1/auth/login", json={"email": "sergii@example.com", "password": "wrong-password"}
    )

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["detail"] == wrong.json()["detail"]


@pytest.mark.asyncio
async def test_repeated_failures_lock_the_account(client, db_session):
    await _register(client)

    for _ in range(service.MAX_FAILED_LOGINS):
        await client.post(
            "/v1/auth/login", json={"email": "sergii@example.com", "password": "wrong-password"}
        )

    user = (await db_session.execute(select(User))).scalars().first()
    assert user.locked_until is not None

    correct = await client.post(
        "/v1/auth/login", json={"email": "sergii@example.com", "password": PASSWORD}
    )
    assert correct.status_code == 401, "замок діє й для правильного пароля"


@pytest.mark.asyncio
async def test_me_requires_authentication(client):
    response = await client.get("/v1/auth/me")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_answers_who_and_where(client):
    await _register(client, display_name="Сергій")

    body = (await client.get("/v1/auth/me")).json()

    assert body["user"]["display_name"] == "Сергій"
    assert body["organization"]["role"] == "owner"


@pytest.mark.asyncio
async def test_logout_kills_the_session_immediately(client):
    await _register(client)

    await client.post("/v1/auth/logout")

    assert (await client.get("/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_logout_without_a_session_is_not_an_error(client):
    """Вийти, коли ти вже вийшов, — це бажаний стан, а не проблема."""
    assert (await client.post("/v1/auth/logout")).status_code == 204


@pytest.mark.asyncio
async def test_a_forged_cookie_does_not_get_in(client):
    client.cookies.set(SESSION_COOKIE, "made-up-token-value")

    assert (await client.get("/v1/auth/me")).status_code == 401


# ── ключі API ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_api_key_is_shown_once_and_only_once(client, db_session):
    await _register(client)

    created = await client.post("/v1/auth/api-keys", json={"name": "інтеграція"})
    assert created.status_code == 201
    token = created.json()["token"]

    listed = (await client.get("/v1/auth/api-keys")).json()
    assert len(listed) == 1
    assert "token" not in listed[0], "ключ, який можна подивитися пізніше, зберігається відкрито"
    assert listed[0]["prefix"] in token

    stored = (await db_session.execute(select(ApiKey.token_hash))).scalars().all()
    assert token not in stored


@pytest.mark.asyncio
async def test_an_api_key_authenticates_as_its_organization(client):
    await _register(client)
    token = (await client.post("/v1/auth/api-keys", json={})).json()["token"]
    org_id = (await client.get("/v1/auth/me")).json()["organization"]["id"]
    await client.post("/v1/auth/logout")

    body = (await client.get("/v1/auth/me", headers={"X-API-Key": token})).json()

    assert body["organization"]["id"] == org_id
    assert body["auth"] == "api_key"
    assert body["user"] is None, "у ключа немає автора — дія від нього безособова"


@pytest.mark.asyncio
async def test_an_api_key_cannot_create_another_api_key(client):
    """Ключ не розмножується сам.

    Створення ключа потім пояснюють людині, і «зроблено ключем» не є
    відповіддю на питання, хто видав доступ.
    """
    await _register(client)
    token = (await client.post("/v1/auth/api-keys", json={})).json()["token"]
    await client.post("/v1/auth/logout")

    response = await client.post(
        "/v1/auth/api-keys", json={"name": "другий"}, headers={"X-API-Key": token}
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_a_revoked_key_stops_working(client):
    await _register(client)
    created = (await client.post("/v1/auth/api-keys", json={})).json()

    assert (await client.delete(f"/v1/auth/api-keys/{created['id']}")).status_code == 204
    await client.post("/v1/auth/logout")

    assert (
        await client.get("/v1/auth/me", headers={"X-API-Key": created["token"]})
    ).status_code == 401


@pytest.mark.asyncio
async def test_one_organization_cannot_revoke_the_key_of_another(client):
    """Головна перевірка ізоляції: чужий ідентифікатор дає 404, не 403.

    403 підтвердив би, що ключ існує, і дав би спосіб перевіряти чужі
    ідентифікатори перебором.
    """
    await _register(client, email="first@example.com")
    victim_key = (await client.post("/v1/auth/api-keys", json={})).json()
    await client.post("/v1/auth/logout")

    await _register(client, email="second@example.com")
    response = await client.delete(f"/v1/auth/api-keys/{victim_key['id']}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_one_organization_does_not_see_the_keys_of_another(client):
    await _register(client, email="first@example.com")
    await client.post("/v1/auth/api-keys", json={"name": "чужий"})
    await client.post("/v1/auth/logout")

    await _register(client, email="second@example.com")
    listed = (await client.get("/v1/auth/api-keys")).json()

    assert listed == []
