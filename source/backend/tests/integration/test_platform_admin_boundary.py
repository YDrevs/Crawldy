"""STAFF дивиться й допомагає, ADMIN міняє — і це межа сервера, а не меню.

`PlatformRole` задумано двома рівнями, але `PlatformAdminDep` не стояв на
жодному маршруті: будь-хто з командною роллю STAFF міняв ключі
провайдерів, ціни, пропозиції й нараховував кредити.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import update as sa_update

from app.identity.enums import PlatformRole
from app.models.identity import User
from tests.integration.conftest import register

ORG = uuid.uuid4()
PURCHASE = uuid.uuid4()

MUTATIONS = [
    ("PUT", "/v1/admin/config/payment", {}),
    ("PUT", "/v1/admin/config/ai", {}),
    ("PUT", "/v1/admin/ai/analysis", {}),
    ("PUT", "/v1/admin/ai/presence", {}),
    ("PUT", "/v1/admin/commerce/offers/x", {}),
    ("PUT", "/v1/admin/commerce/campaigns/x", {}),
    ("PUT", "/v1/admin/commerce/plans/x", {}),
    ("POST", f"/v1/admin/commerce/orgs/{ORG}/grants", {}),
    ("POST", f"/v1/admin/payments/{PURCHASE}/credit", None),
    ("POST", "/v1/admin/payments/sweep", {}),
]


async def _with_platform_role(client, db, role: PlatformRole) -> None:
    body = (await register(client, f"team-{uuid.uuid4().hex[:8]}@example.com")).json()
    await db.execute(
        sa_update(User).where(User.id == uuid.UUID(body["user"]["id"])).values(platform_role=role)
    )
    await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "body"), MUTATIONS)
async def test_staff_cannot_change_money_or_configuration(client, db_session, method, path, body):
    await _with_platform_role(client, db_session, PlatformRole.STAFF)

    response = await client.request(method, path, json=body)

    assert response.status_code == 403, response.text


@pytest.mark.asyncio
@pytest.mark.parametrize(("method", "path", "body"), MUTATIONS)
async def test_admin_passes_the_role_check(client, db_session, method, path, body):
    await _with_platform_role(client, db_session, PlatformRole.ADMIN)

    response = await client.request(method, path, json=body)

    # Порожнє тіло й вигадані ідентифікатори дають 404/409/422 — головне,
    # що відмова вже не про роль.
    assert response.status_code != 403, response.text
    assert response.status_code != 401


@pytest.mark.asyncio
async def test_staff_still_reads_the_payments_list(client, db_session):
    await _with_platform_role(client, db_session, PlatformRole.STAFF)

    assert (await client.get("/v1/admin/payments/pending")).status_code == 200
