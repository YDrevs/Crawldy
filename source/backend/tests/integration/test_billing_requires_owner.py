"""Гроші організації рухає лише її власник — людина, а не ключ.

Каса тарифу, каса пропозиції й портал провайдера стояли на `ActorDep`:
будь-який учасник (MEMBER) чи ключ API організації (роль ADMIN) міг
відкрити підписку, купити пакет або зайти в платіжний кабінет.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.identity.enums import Role
from app.models.identity import Membership, User
from tests.integration.conftest import register
from tests.integration.test_plan_checkout import _seed_monthly

BILLING = [
    ("POST", "/v1/plans/m-own/checkout", None),
    ("POST", "/v1/offers/checkout", {"offer_code": "anything"}),
    ("POST", "/v1/account/portal-session", None),
]


async def _demote(db, email: str, role: Role) -> None:
    user = (await db.scalars(select(User).where(User.email == email))).one()
    membership = (await db.scalars(select(Membership).where(Membership.user_id == user.id))).one()
    membership.role = role
    await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "body"), BILLING)
async def test_a_member_cannot_spend_the_organizations_money(
    client, db_session, method, path, body
):
    await _seed_monthly(db_session, code="m-own")
    await register(client, "member@example.com")
    await _demote(db_session, "member@example.com", Role.MEMBER)

    response = await client.request(method, path, json=body)

    assert response.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "body"), BILLING)
async def test_an_api_key_cannot_spend_the_organizations_money(
    client, db_session, method, path, body
):
    await _seed_monthly(db_session, code="m-own")
    await register(client, "owner@example.com")
    token = (await client.post("/v1/auth/api-keys", json={})).json()["token"]
    await client.post("/v1/auth/logout")

    response = await client.request(method, path, json=body, headers={"X-API-Key": token})

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_the_owner_opens_the_plan_checkout(client, db_session):
    await _seed_monthly(db_session, code="m-own")
    await register(client, "owner@example.com")

    assert (await client.post("/v1/plans/m-own/checkout")).status_code == 201
