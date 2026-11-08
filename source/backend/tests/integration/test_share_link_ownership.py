"""Публічні посилання належать аудиту, а аудит — організації.

Перелік і відкликання стояли на глобальному ключі (`ApiKeyDep`) без
перевірки власника: будь-хто з ключем бачив посилання чужого аудиту, а
`revoke` комітив відкликання будь-якого `link_id` ДО того, як звіряв
`audit_id`, — тобто 404 приходив уже після того, як чуже (навіть
оплачене) посилання було вимкнено.
"""

from __future__ import annotations

import uuid

import pytest

from app.models.audit import ReportLink
from app.services import link_service
from tests.integration.conftest import register, sign_in_as
from tests.integration.test_audit_ownership import _make_audit, _own_organization


async def _owner_with_link(client, db) -> tuple[uuid.UUID, uuid.UUID]:
    await register(client, "owner@example.com")
    audit = await _make_audit(db, organization_id=await _own_organization(client))
    await db.commit()
    link, _ = await link_service.create_link(db, audit.id, target_id=None, lang="uk", ttl_days=7)
    return audit.id, link.id


async def _is_revoked(db, link_id: uuid.UUID) -> bool:
    db.expire_all()
    link = await db.get(ReportLink, link_id)
    return link.revoked_at is not None


@pytest.mark.asyncio
async def test_a_stranger_cannot_list_links_of_someone_elses_audit(client, db_session):
    audit_id, _ = await _owner_with_link(client, db_session)

    await sign_in_as(client, "stranger@example.com")
    response = await client.get(f"/v1/audits/{audit_id}/links")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_a_stranger_cannot_revoke_a_link(client, db_session):
    audit_id, link_id = await _owner_with_link(client, db_session)

    await sign_in_as(client, "stranger@example.com")
    response = await client.delete(f"/v1/audits/{audit_id}/links/{link_id}")

    assert response.status_code == 404
    assert not await _is_revoked(db_session, link_id)


@pytest.mark.asyncio
async def test_a_link_is_not_revoked_through_another_audit(client, db_session):
    """Невідповідний `audit_id` — 404 і БЕЗ побічного ефекту."""
    _, link_id = await _owner_with_link(client, db_session)
    other = await _make_audit(
        db_session, organization_id=await _own_organization(client), origin="https://b.example"
    )
    await db_session.commit()

    response = await client.delete(f"/v1/audits/{other.id}/links/{link_id}")

    assert response.status_code == 404
    assert not await _is_revoked(db_session, link_id)


@pytest.mark.asyncio
async def test_the_owner_lists_and_revokes_own_link(client, db_session):
    audit_id, link_id = await _owner_with_link(client, db_session)

    listed = await client.get(f"/v1/audits/{audit_id}/links")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [str(link_id)]

    revoked = await client.delete(f"/v1/audits/{audit_id}/links/{link_id}")
    assert revoked.status_code == 200
    assert await _is_revoked(db_session, link_id)


@pytest.mark.asyncio
async def test_anonymous_request_is_refused(client, db_session):
    audit_id, link_id = await _owner_with_link(client, db_session)
    await client.post("/v1/auth/logout")

    assert (await client.get(f"/v1/audits/{audit_id}/links")).status_code == 401
    assert (await client.delete(f"/v1/audits/{audit_id}/links/{link_id}")).status_code == 401
    assert not await _is_revoked(db_session, link_id)
