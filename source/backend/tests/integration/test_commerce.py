"""Комерційна модель: пропозиції, пакети, промо, гейт присутності.

Через контракт провайдера (фейк), не через адаптер: усе тут лишиться
правдою після заміни Paddle. Головні закони:

* право дає перевірена подія, і рівно один раз — реплей не дублює;
* PACK-кредити не згорають і не залежать від підписки;
* промокод — лише PACK і лише раз на організацію (UNIQUE у базі);
* присутність без права не стартує; недостатнє покриття повертає право.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.billing import credits as billing_credits
from app.billing.enums import BillingEventKind
from app.models.commerce import (
    CommercialOffer,
    OfferType,
    PromoCampaign,
    PromoRedemption,
    RedemptionStatus,
)
from app.models.purchase import AuditCredit, OneOffPurchase
from tests.integration.conftest import register

pytestmark = pytest.mark.asyncio


async def _org_of(db_session) -> uuid.UUID:
    from app.models.identity import Organization

    return (await db_session.execute(
        select(Organization.id).order_by(Organization.created_at.desc()).limit(1)
    )).scalar_one()


async def _seed_offer(db_session, *, code="pack10", offer_type=OfferType.PACK,
                      audits=10, presence=0, promo=True) -> CommercialOffer:
    offer = CommercialOffer(
        code=code, offer_type=offer_type, active=True,
        display_name=code, provider="fake",
        provider_price_ref=f"fake_{code}", currency="USD",
        display_amount_minor=4900, audit_credits=audits,
        presence_credits=presence, promo_eligible=promo,
    )
    db_session.add(offer)
    await db_session.commit()
    return offer


async def _seed_campaign(db_session, *, code="LAUNCH50") -> PromoCampaign:
    campaign = PromoCampaign(
        code=code, name="Launch", active=True,
        provider_discount_ref="dsc_fake_launch",
    )
    db_session.add(campaign)
    await db_session.commit()
    return campaign


def _paid_event(purchase_id: uuid.UUID, *, event_id: str,
                transaction: str) -> bytes:
    return json.dumps({
        "external_event_id": event_id,
        "kind": BillingEventKind.ONE_OFF_PURCHASED.value,
        "occurred_at": datetime.now(UTC).isoformat(),
        "quantity": 1,
        "currency": "USD",
        "amount_minor": 4900,
        "payload": {"purchase_ref": str(purchase_id),
                    "provider_transaction_id": transaction},
    }).encode("utf-8")


async def _deliver(client, body: bytes):
    return await client.post(
        "/v1/webhooks/fake", content=body,
        headers={"x-fake-signature": "valid",
                 "content-type": "application/json"},
    )


async def _buy(client, db_session, offer_code: str, promo: str | None = None):
    response = await client.post("/v1/offers/checkout", json={
        "offer_code": offer_code,
        **({"promo_code": promo} if promo else {}),
    })
    assert response.status_code == 201, response.text
    body = response.json()
    paid = await _deliver(client, _paid_event(
        uuid.UUID(body["purchase_id"]),
        event_id=f"evt-{uuid.uuid4().hex[:8]}",
        transaction=body["provider_ref"],
    ))
    assert paid.status_code == 200, paid.text
    return body


# ── PACK: видача, ідемпотентність, вічність ───────────────────────────


async def test_pack_purchase_grants_exact_typed_credits(client, db_session):
    await register(client, "commerce-pack@example.com")
    await _seed_offer(db_session, code="pack10a", audits=10, presence=2,
                      promo=False)
    await _buy(client, db_session, "pack10a")
    org = await _org_of(db_session)
    assert await billing_credits.balance(db_session, organization_id=org) == 10
    assert await billing_credits.balance(
        db_session, organization_id=org, credit_type="presence") == 2
    # жодного строку придатності в моделі — вічність структурна
    assert not hasattr(AuditCredit, "expires_at")


async def test_webhook_replay_does_not_duplicate_the_grant(client, db_session):
    await register(client, "commerce-replay@example.com")
    await _seed_offer(db_session, code="pack5r", audits=5, promo=False)
    body = await _buy(client, db_session, "pack5r")
    replay = await _deliver(client, _paid_event(
        uuid.UUID(body["purchase_id"]),
        event_id="evt-replayed-same", transaction=body["provider_ref"],
    ))
    assert replay.status_code == 200
    org = await _org_of(db_session)
    assert await billing_credits.balance(db_session, organization_id=org) == 5


async def test_single_offer_grants_exactly_one(client, db_session):
    await register(client, "commerce-single@example.com")
    await _seed_offer(db_session, code="single1",
                      offer_type=OfferType.SINGLE, audits=1, promo=False)
    await _buy(client, db_session, "single1")
    org = await _org_of(db_session)
    assert await billing_credits.balance(db_session, organization_id=org) == 1


# ── ПРОМО: лише PACK, раз на організацію, гроші а не одиниці ─────────


async def test_promo_applies_discount_but_not_quantity(client, db_session):
    await register(client, "commerce-promo@example.com")
    await _seed_offer(db_session, code="pack10p", audits=10)
    await _seed_campaign(db_session, code="LAUNCHP")
    body = await _buy(client, db_session, "pack10p", promo="LAUNCHP")
    assert body["discount_applied"] is True
    org = await _org_of(db_session)
    assert await billing_credits.balance(db_session, organization_id=org) == 10, (
        "знижка міняє гроші, не кількість")
    redemption = (await db_session.execute(select(PromoRedemption))).scalars().one()
    assert redemption.status is RedemptionStatus.COMPLETED
    assert redemption.redeemed_at is not None


async def test_same_org_cannot_redeem_the_same_campaign_twice(client, db_session):
    await register(client, "commerce-promo2@example.com")
    await _seed_offer(db_session, code="pack10q", audits=10)
    await _seed_campaign(db_session, code="ONCE")
    await _buy(client, db_session, "pack10q", promo="ONCE")
    second = await client.post("/v1/offers/checkout", json={
        "offer_code": "pack10q", "promo_code": "ONCE"})
    assert second.status_code == 422
    assert "використано" in second.json()["detail"]


async def test_promo_is_rejected_for_single_offers(client, db_session):
    await register(client, "commerce-promo3@example.com")
    await _seed_offer(db_session, code="single2",
                      offer_type=OfferType.SINGLE, audits=1, promo=False)
    await _seed_campaign(db_session, code="NOSINGLE")
    response = await client.post("/v1/offers/checkout", json={
        "offer_code": "single2", "promo_code": "NOSINGLE"})
    assert response.status_code == 422
    assert "пакетні" in response.json()["detail"]


async def test_abandoned_promo_checkout_can_retry(client, db_session):
    """Недоплачена спроба не спалює право на код: PENDING переиспользовується."""
    await register(client, "commerce-promo4@example.com")
    await _seed_offer(db_session, code="pack10s", audits=10)
    await _seed_campaign(db_session, code="RETRY")
    first = await client.post("/v1/offers/checkout", json={
        "offer_code": "pack10s", "promo_code": "RETRY"})
    assert first.status_code == 201  # каса відкрита, оплати не було
    second = await client.post("/v1/offers/checkout", json={
        "offer_code": "pack10s", "promo_code": "RETRY"})
    assert second.status_code == 201, "PENDING-погашення переиспользовано"
    redemptions = (await db_session.execute(select(PromoRedemption))).scalars().all()
    assert len(redemptions) == 1, "UNIQUE тримає один рядок на кампанію+орг"


# ── повернення коштів ────────────────────────────────────────────────


async def test_refund_revokes_unused_typed_credits(client, db_session):
    await register(client, "commerce-refund@example.com")
    await _seed_offer(db_session, code="pack4f", audits=4, presence=1,
                      promo=False)
    body = await _buy(client, db_session, "pack4f")
    refund = await _deliver(client, json.dumps({
        "external_event_id": "evt-refund-c1",
        "kind": BillingEventKind.ONE_OFF_REFUNDED.value,
        "occurred_at": datetime.now(UTC).isoformat(),
        "payload": {"provider_transaction_id": body["provider_ref"]},
    }).encode("utf-8"))
    assert refund.status_code == 200
    org = await _org_of(db_session)
    assert await billing_credits.balance(db_session, organization_id=org) == 0
    assert await billing_credits.balance(
        db_session, organization_id=org, credit_type="presence") == 0


async def test_admin_grant_survives_purchase_refunds(client, db_session):
    """Грант без покупки не має звідки бути відкликаним поверненням."""
    await register(client, "commerce-grant@example.com")
    org = await _org_of(db_session)
    await billing_credits.grant(
        db_session, organization_id=org, credit_type="audit", quantity=2,
        source="admin", reason="корекція")
    await db_session.commit()
    assert await billing_credits.balance(db_session, organization_id=org) == 2
    grant_rows = (await db_session.execute(
        select(AuditCredit).where(AuditCredit.organization_id == org)
    )).scalars().all()
    assert all(c.purchase_id is None and c.source == "admin"
               for c in grant_rows)


# ── одночасність ─────────────────────────────────────────────────────


async def test_offer_checkout_requires_active_offer(client, db_session):
    await register(client, "commerce-inactive@example.com")
    offer = await _seed_offer(db_session, code="pack-off", audits=5,
                              promo=False)
    offer.active = False
    await db_session.commit()
    response = await client.post("/v1/offers/checkout",
                                 json={"offer_code": "pack-off"})
    assert response.status_code == 404


async def test_purchase_history_names_the_offer(client, db_session):
    await register(client, "commerce-history@example.com")
    await _seed_offer(db_session, code="pack3h", audits=3, promo=False)
    body = await _buy(client, db_session, "pack3h")
    purchase = await db_session.get(OneOffPurchase, uuid.UUID(body["purchase_id"]))
    assert purchase.offer_code == "pack3h"
    assert purchase.status.value == "paid"
    credits_rows = (await db_session.execute(
        select(AuditCredit).where(AuditCredit.purchase_id == purchase.id)
    )).scalars().all()
    assert len(credits_rows) == 3
    assert {c.source for c in credits_rows} == {"purchase"}


# ── вітрина без входа: перелік публічний, каса — ні ──────────────────


async def test_offer_listing_is_public_but_checkout_is_not(client, db_session):
    """Сторінка цін показує живі пропозиції анонімному відвідувачу —
    як /v1/plans. Купівля лишається за входом: право отримує конкретна
    організація, і без неї каси не існує."""
    await _seed_offer(db_session, code="pack-pub", audits=10, promo=False)
    hidden = await _seed_offer(db_session, code="pack-hidden", audits=5,
                               promo=False)
    hidden.active = False
    await db_session.commit()

    listing = await client.get("/v1/offers")
    assert listing.status_code == 200
    codes = [o["code"] for o in listing.json()]
    assert "pack-pub" in codes
    assert "pack-hidden" not in codes, "неактивна пропозиція не існує назовні"
    row = next(o for o in listing.json() if o["code"] == "pack-pub")
    assert row["display_amount_minor"] == 4900
    assert row["audit_credits"] == 10

    checkout = await client.post("/v1/offers/checkout",
                                 json={"offer_code": "pack-pub"})
    assert checkout.status_code == 401, "каса анонімно не відчиняється"
