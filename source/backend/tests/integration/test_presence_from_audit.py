"""Присутність із самої лише адреси: підстановка фактів і гостьовий прогін.

Ланка, якої не було: разова покупка давала одиницю присутності, але
дороги від покупки до прогону не існувало. Тут перевіряється, що
факти виводяться з прочитаного аудиту, що гість після оплати може
запустити прогін своєю одиницею, і що без оплати чи без одиниці шлях
чесно зачинений.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.audit.enums import AuditStatus
from app.billing.enums import CommerceModel, CreditState, PurchaseStatus
from app.core.run_enums import QuotaSource, QuotaState
from app.models.audit import Audit, AuditPage, AuditTarget
from app.models.guest import AuditUnlock
from app.models.identity import Organization
from app.models.presence import PresenceRun
from app.models.purchase import AuditCredit, OneOffPurchase

from .conftest import register

pytestmark = pytest.mark.asyncio

KA_DENT_TITLE = "Стоматологічна клініка Ка-Дент — Кам'янець-Подільский"


async def _seed_audit(db, *, organization_id: uuid.UUID, source: QuotaSource) -> Audit:
    audit = Audit(
        organization_id=organization_id,
        url="https://ka-dent.com.ua/",
        origin="https://ka-dent.com.ua",
        status=AuditStatus.COMPLETED,
        quota_source=source,
        quota_state=QuotaState.CONSUMED,
        finished_at=datetime.now(UTC),
        evidence={
            "site_facts": {
                "organization": "",
                "cities": ["Кам'янець-Подільський"],
                "schema_types": {"Organization": 10},
            }
        },
    )
    db.add(audit)
    await db.flush()
    target = AuditTarget(
        audit_id=audit.id, position=0, url="https://ka-dent.com.ua/",
        origin="https://ka-dent.com.ua", status=AuditStatus.COMPLETED,
    )
    db.add(target)
    await db.flush()
    db.add(AuditPage(
        id=uuid.uuid4(), audit_id=audit.id, target_id=target.id,
        url="https://ka-dent.com.ua/", status_code=200, response_ms=120, depth=0,
        raw={"title": KA_DENT_TITLE, "lang": "uk"},
    ))
    await db.commit()
    return audit


# ── кабінет: підстановка ────────────────────────────────────────────────


async def test_cabinet_suggestion_comes_from_the_audit(client, db_session):
    await register(client, f"sug-{uuid.uuid4().hex[:8]}@example.com")
    org = (await db_session.execute(
        select(Organization.id).order_by(Organization.created_at.desc()).limit(1)
    )).scalar_one()
    await _seed_audit(db_session, organization_id=org, source=QuotaSource.SUBSCRIPTION)

    response = await client.get("/v1/presence/suggest", params={"url": "https://ka-dent.com.ua"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["brand"] == "Ка-Дент"
    assert body["category"] == "стоматологічна клініка"
    assert body["location"] == "Кам'янець-Подільський"
    assert "Ka-Dent" in body["brand_aliases"]
    assert body["sources"]["location"] == "site"


async def test_cabinet_suggestion_needs_a_read_audit(client):
    await register(client, f"sug-{uuid.uuid4().hex[:8]}@example.com")
    response = await client.get("/v1/presence/suggest", params={"url": "https://nothing.example"})
    assert response.status_code == 404


# ── гість: після оплати ─────────────────────────────────────────────────


async def _guest(client, db_session) -> tuple[dict, uuid.UUID, Audit]:
    opened = await client.post("/v1/public/sessions")
    assert opened.status_code in (200, 201), opened.text
    token = opened.json()["token"]
    headers = {"X-Guest-Token": token}
    org = (await db_session.execute(
        select(Organization.id).order_by(Organization.created_at.desc()).limit(1)
    )).scalar_one()
    audit = await _seed_audit(db_session, organization_id=org, source=QuotaSource.FREE_PREVIEW)
    return headers, org, audit


async def _pay(db, *, organization_id: uuid.UUID, audit: Audit, presence: int) -> None:
    """Оплата гостя так, як її записує вебхук: покупка, розблокування, одиниці."""
    purchase = OneOffPurchase(
        organization_id=organization_id, provider="paddle",
        external_id=f"ext-{uuid.uuid4().hex[:10]}", supplier_entity_key="test",
        commerce_model=CommerceModel.MERCHANT_OF_RECORD, quantity=1, currency="USD",
        amount_minor=1500, status=PurchaseStatus.PAID, purchased_at=datetime.now(UTC),
        audit_id=audit.id, offer_snapshot={"offer_type": "single"},
    )
    db.add(purchase)
    await db.flush()
    db.add(AuditUnlock(audit_id=audit.id, purchase_id=purchase.id))
    for _ in range(presence):
        db.add(AuditCredit(organization_id=organization_id, purchase_id=purchase.id,
                           state=CreditState.AVAILABLE, credit_type="presence",
                           source="purchase"))
    await db.commit()


async def test_guest_cannot_see_presence_before_paying(client, db_session):
    headers, _, audit = await _guest(client, db_session)
    response = await client.get(f"/v1/public/audits/{audit.id}/presence", headers=headers)
    assert response.status_code == 402


async def test_guest_gets_prefilled_facts_and_runs_with_the_paid_unit(
    client, db_session, queue_is_not_the_subject
):
    headers, org, audit = await _guest(client, db_session)
    # Оплата: розблокування аудиту й одиниця присутності на гостьовій організації.
    await _pay(db_session, organization_id=org, audit=audit, presence=1)

    shown = await client.get(f"/v1/public/audits/{audit.id}/presence", headers=headers)
    assert shown.status_code == 200, shown.text
    body = shown.json()
    assert body["suggestion"]["brand"] == "Ка-Дент"
    assert body["suggestion"]["location"] == "Кам'янець-Подільський"
    assert body["credits_available"] == 1
    assert body["runs"] == []

    # Людина виправила місто — саме виправлене йде в прогін.
    started = await client.post(
        f"/v1/public/audits/{audit.id}/presence",
        headers=headers,
        json={
            "brand": "Ка-Дент",
            "brand_aliases": ["Ka-Dent"],
            "category": "стоматологічна клініка",
            "location": "Кам'янець-Подільський",
            "language": "uk",
        },
    )
    assert started.status_code == 202, started.text
    run_id = uuid.UUID(started.json()["id"])
    run = await db_session.get(PresenceRun, run_id)
    assert run is not None
    assert run.organization_id == org
    assert run.entitlement_source == "credit"
    assert all("Кам'янець-Подільський" in p["text"] for p in run.prompts if p["category"] == "local")
    assert not any("Київ" in p["text"] for p in run.prompts)

    # Одиниця зарезервована саме цим прогоном — другої немає.
    credit = (await db_session.execute(
        select(AuditCredit).where(AuditCredit.organization_id == org)
    )).scalar_one()
    assert credit.state is CreditState.RESERVED
    assert credit.presence_run_id == run_id

    again = await client.post(
        f"/v1/public/audits/{audit.id}/presence",
        headers=headers,
        json={"brand": "Ка-Дент", "category": "стоматологічна клініка", "language": "uk"},
    )
    assert again.status_code == 402
    assert again.json()["detail"]["reason"] == "presence.noEntitlement"

    # І прогін видно гостю тим самим контрактом, що в кабінеті.
    seen = await client.get(f"/v1/public/presence/{run_id}", headers=headers)
    assert seen.status_code == 200, seen.text
    assert seen.json()["status"] == "queued"
    listed = await client.get(f"/v1/public/audits/{audit.id}/presence", headers=headers)
    assert [r["id"] for r in listed.json()["runs"]] == [str(run_id)]


async def test_guest_cannot_use_a_foreign_audit(client, db_session):
    headers, _, _ = await _guest(client, db_session)
    stranger = await client.post("/v1/public/sessions")
    other = {"X-Guest-Token": stranger.json()["token"]}
    org = (await db_session.execute(
        select(Organization.id).order_by(Organization.created_at.desc()).limit(1)
    )).scalar_one()
    audit = await _seed_audit(db_session, organization_id=org, source=QuotaSource.FREE_PREVIEW)
    await _pay(db_session, organization_id=org, audit=audit, presence=0)
    assert (await client.get(f"/v1/public/audits/{audit.id}/presence", headers=headers)).status_code == 404
    assert (await client.get(f"/v1/public/audits/{audit.id}/presence", headers=other)).status_code == 200
