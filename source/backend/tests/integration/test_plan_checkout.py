"""Каса підписки: від публічного тарифу до чинної підписки — і межі.

Той самий принцип, що в разовій воронці: **право дає перевірена подія,
і лише вона**. Каса — двері до оплати, а не наділ; повернення з неї
нічого не доводить. Стан підписки веде конвеєр application/billing,
який тут перевіряється рівно в місцях, де його торкнувся новий вхід.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.enums import BillingEventKind, SubscriptionStatus
from app.models.billing import Plan, PlanPrice, Subscription
from app.models.purchase import AuditCredit
from tests.integration.conftest import register

pytestmark = pytest.mark.asyncio

_MONTHLY_ENTITLEMENTS = {
    "audits_per_period": None,  # безліміт аналізів — законна конфігурація
    "presence_per_period": 5,
    "max_pages_per_audit": 50,
}


async def _seed_monthly(
    db: AsyncSession, *, code: str, public: bool = True, priced: bool = True
) -> Plan:
    plan = Plan(
        code=code,
        name="Monthly (test)",
        is_public=public,
        sort_order=10,
        entitlements=dict(_MONTHLY_ENTITLEMENTS),
    )
    db.add(plan)
    await db.flush()
    if priced:
        db.add(
            PlanPrice(
                plan_id=plan.id,
                provider="fake",
                provider_price_id=f"pri_{code}",
                currency="USD",
                interval="month",
                display_amount_minor=500,
            )
        )
        await db.flush()
    await db.commit()
    return plan


def _activated_event(
    *,
    organization_id: uuid.UUID,
    price_ref: str,
    event_id: str = "evt-sub-1",
    subscription_ref: str = "sub_test_1",
) -> bytes:
    """Подія «підписка почалася» — так, як її нормалізує адаптер."""
    now = datetime.now(UTC)
    return json.dumps(
        {
            "external_event_id": event_id,
            "kind": BillingEventKind.SUBSCRIPTION_STARTED.value,
            "occurred_at": now.isoformat(),
            "organization_id": str(organization_id),
            "payload": {},
            "quantity": None,
            "currency": None,
            "amount_minor": None,
        }
    ).encode("utf-8")


async def _deliver(client: httpx.AsyncClient, body: bytes) -> httpx.Response:
    return await client.post(
        "/v1/webhooks/fake",
        content=body,
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )


async def _own_organization(client: httpx.AsyncClient) -> uuid.UUID:
    body = (await client.get("/v1/auth/me")).json()
    return uuid.UUID(body["organization"]["id"])


# ── вхід у касу ────────────────────────────────────────────────────────────


async def test_checkout_needs_an_account(client, db_session):
    """Підписку тримає організація — анонімної каси підписки немає."""
    await _seed_monthly(db_session, code="m-anon")
    response = await client.post("/v1/plans/m-anon/checkout")
    assert response.status_code == 401


async def test_checkout_opens_for_a_public_priced_plan(client, db_session):
    await _seed_monthly(db_session, code="m-ok")
    await register(client, "sub@example.com")

    response = await client.post("/v1/plans/m-ok/checkout")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["plan_code"] == "m-ok"
    assert body["url"]
    assert body["provider_ref"]


async def test_checkout_grants_nothing_by_itself(client, db_session):
    """Каса відкрита — підписки немає: право видає лише подія."""
    await _seed_monthly(db_session, code="m-noright")
    await register(client, "sub@example.com")
    org = await _own_organization(client)

    response = await client.post("/v1/plans/m-noright/checkout")
    assert response.status_code == 201

    rows = await db_session.scalar(
        select(func.count()).select_from(Subscription).where(
            Subscription.organization_id == org
        )
    )
    assert rows == 0


async def test_a_private_plan_has_no_checkout(client, db_session):
    """Непублічний тариф відповідає так само, як неіснуючий."""
    await _seed_monthly(db_session, code="m-hidden", public=False)
    await register(client, "sub@example.com")

    hidden = await client.post("/v1/plans/m-hidden/checkout")
    missing = await client.post("/v1/plans/no-such-plan/checkout")

    assert hidden.status_code == 404
    assert missing.status_code == 404


async def test_a_priceless_plan_has_no_checkout(client, db_session):
    await _seed_monthly(db_session, code="m-unpriced", priced=False)
    await register(client, "sub@example.com")

    response = await client.post("/v1/plans/m-unpriced/checkout")
    assert response.status_code == 404


# ── подія → підписка ───────────────────────────────────────────────────────


async def test_a_verified_event_activates_the_subscription(client, db_session):
    await _seed_monthly(db_session, code="m-live")
    await register(client, "sub@example.com")
    org = await _own_organization(client)
    assert (await client.post("/v1/plans/m-live/checkout")).status_code == 201

    body = json.loads(_activated_event(organization_id=org, price_ref="pri_m-live"))
    body["price_ref"] = "pri_m-live"
    body["subscription_ref"] = "sub_live_1"
    # Фейковий адаптер читає плаский словник; прайс і підписка їдуть
    # тими самими полями, що їх кладе сценарний бік фейка.
    delivered = await _deliver(
        client,
        json.dumps({**body, "payload": {}}).encode("utf-8"),
    )
    assert delivered.status_code == 200, delivered.text

    subscription = (
        await db_session.execute(
            select(Subscription).where(Subscription.organization_id == org)
        )
    ).scalars().first()
    assert subscription is not None
    assert subscription.status is SubscriptionStatus.ACTIVE

    account = await client.get("/v1/account")
    assert account.json()["billing_state"] == "active"


async def test_duplicate_delivery_makes_one_subscription(client, db_session):
    await _seed_monthly(db_session, code="m-dup")
    await register(client, "sub@example.com")
    org = await _own_organization(client)

    event = json.loads(_activated_event(organization_id=org, price_ref="pri_m-dup"))
    event["price_ref"] = "pri_m-dup"
    event["subscription_ref"] = "sub_dup_1"
    raw = json.dumps(event).encode("utf-8")

    first = await _deliver(client, raw)
    second = await _deliver(client, raw)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["outcome"] in ("duplicate", "busy")

    rows = await db_session.scalar(
        select(func.count()).select_from(Subscription).where(
            Subscription.organization_id == org
        )
    )
    assert rows == 1


async def test_an_active_subscription_blocks_a_second_checkout(client, db_session):
    """Одна незавершена підписка — жодної другої каси. Стабільним кодом."""
    await _seed_monthly(db_session, code="m-once")
    await register(client, "sub@example.com")
    org = await _own_organization(client)

    start = json.loads(_activated_event(organization_id=org, price_ref="pri_m-once"))
    start["price_ref"] = "pri_m-once"
    start["subscription_ref"] = "sub_once_1"
    assert (await _deliver(client, json.dumps(start).encode())).status_code == 200

    second = await client.post("/v1/plans/m-once/checkout")
    assert second.status_code == 409
    assert second.json()["detail"] == {"reason": "subscription.exists"}


async def test_a_paused_subscription_still_blocks_checkout(client, db_session):
    """Пауза не дає прав, але підписка існує — друга каса недоречна."""
    await _seed_monthly(db_session, code="m-paused")
    await register(client, "sub@example.com")
    org = await _own_organization(client)

    start = json.loads(_activated_event(organization_id=org, price_ref="pri_m-paused"))
    start["price_ref"] = "pri_m-paused"
    start["subscription_ref"] = "sub_paused_1"
    assert (await _deliver(client, json.dumps(start).encode())).status_code == 200
    pause = {
        "external_event_id": "evt-sub-pause",
        "kind": BillingEventKind.SUBSCRIPTION_PAUSED.value,
        "occurred_at": datetime.now(UTC).isoformat(),
        "organization_id": str(org),
        "subscription_ref": "sub_paused_1",
        "payload": {},
    }
    assert (await _deliver(client, json.dumps(pause).encode())).status_code == 200

    blocked = await client.post("/v1/plans/m-paused/checkout")
    assert blocked.status_code == 409
    assert blocked.json()["detail"] == {"reason": "subscription.exists"}


async def test_a_terminal_subscription_frees_the_way_for_a_new_one(
    client, db_session
):
    """Скасована — завершена: нова каса і нова підписка знову можливі."""
    await _seed_monthly(db_session, code="m-again")
    await register(client, "sub@example.com")
    org = await _own_organization(client)

    start = json.loads(_activated_event(organization_id=org, price_ref="pri_m-again"))
    start["price_ref"] = "pri_m-again"
    start["subscription_ref"] = "sub_again_1"
    assert (await _deliver(client, json.dumps(start).encode())).status_code == 200
    cancel = {
        "external_event_id": "evt-sub-again-cancel",
        "kind": BillingEventKind.SUBSCRIPTION_CANCELLED.value,
        "occurred_at": datetime.now(UTC).isoformat(),
        "organization_id": str(org),
        "subscription_ref": "sub_again_1",
        "payload": {},
    }
    assert (await _deliver(client, json.dumps(cancel).encode())).status_code == 200

    reopened = await client.post("/v1/plans/m-again/checkout")
    assert reopened.status_code == 201, reopened.text

    fresh = {
        "external_event_id": "evt-sub-again-2",
        "kind": BillingEventKind.SUBSCRIPTION_STARTED.value,
        "occurred_at": datetime.now(UTC).isoformat(),
        "organization_id": str(org),
        "subscription_ref": "sub_again_2",
        "price_ref": "pri_m-again",
        "payload": {},
    }
    assert (await _deliver(client, json.dumps(fresh).encode())).status_code == 200

    rows = (
        await db_session.execute(
            select(Subscription)
            .where(Subscription.organization_id == org)
            .order_by(Subscription.created_at)
        )
    ).scalars().all()
    assert [row.status for row in rows] == [
        SubscriptionStatus.CANCELLED,
        SubscriptionStatus.ACTIVE,
    ], "нове життя — новий рядок, стара лишилась історією"


async def test_a_second_concurrent_subscription_event_fails_visibly(
    client, db_session
):
    """Нова підписка ПОРУЧ із незавершеною — розбіжність, а не наділ.

    Подія стає failed зі стабільним кодом; другого наділу (аналізи,
    перевірки Presence) не зʼявляється.
    """
    await _seed_monthly(db_session, code="m-conc")
    await register(client, "sub@example.com")
    org = await _own_organization(client)

    first = json.loads(_activated_event(organization_id=org, price_ref="pri_m-conc"))
    first["price_ref"] = "pri_m-conc"
    first["subscription_ref"] = "sub_conc_1"
    assert (await _deliver(client, json.dumps(first).encode())).status_code == 200

    intruder = {
        "external_event_id": "evt-sub-conc-2",
        "kind": BillingEventKind.SUBSCRIPTION_STARTED.value,
        "occurred_at": datetime.now(UTC).isoformat(),
        "organization_id": str(org),
        "subscription_ref": "sub_conc_2",
        "price_ref": "pri_m-conc",
        "payload": {},
    }
    refused = await _deliver(client, json.dumps(intruder).encode())
    # 500: маршрут просить провайдера повторити, а подія лежить у
    # журналі failed зі стабільним кодом для людини.
    assert refused.status_code == 500

    from app.models.billing import BillingEvent

    record = await db_session.scalar(
        select(BillingEvent).where(
            BillingEvent.external_event_id == "evt-sub-conc-2"
        )
    )
    assert record is not None
    assert "subscription.duplicate" in record.error

    rows = (
        await db_session.execute(
            select(Subscription).where(Subscription.organization_id == org)
        )
    ).scalars().all()
    assert len(rows) == 1, "другого наділу не існує"
    assert rows[0].provider_subscription_id == "sub_conc_1"
    allocation = rows[0].period_allocation or {}
    assert allocation.get("presence_per_period") == 5, (
        "наділ лишився один і незмінний"
    )


async def test_cancellation_leaves_purchased_credits_alone(client, db_session):
    """Скасування підписки не забирає куплених окремо одиниць."""
    from app.application import purchases

    await _seed_monthly(db_session, code="m-cancel")
    await register(client, "sub@example.com")
    org = await _own_organization(client)
    await purchases.record(
        db_session,
        organization_id=org,
        provider="fake",
        external_id="pur-pack-1",
        quantity=10,
        currency="USD",
        amount_minor=900,
        purchased_at=datetime.now(UTC),
    )
    await db_session.commit()

    start = json.loads(_activated_event(organization_id=org, price_ref="pri_m-cancel"))
    start["price_ref"] = "pri_m-cancel"
    start["subscription_ref"] = "sub_cancel_1"
    assert (await _deliver(client, json.dumps(start).encode())).status_code == 200

    cancel = {
        "external_event_id": "evt-sub-cancel",
        "kind": BillingEventKind.SUBSCRIPTION_CANCELLED.value,
        "occurred_at": datetime.now(UTC).isoformat(),
        "organization_id": str(org),
        "subscription_ref": "sub_cancel_1",
        "payload": {},
    }
    assert (await _deliver(client, json.dumps(cancel).encode())).status_code == 200

    credits = await db_session.scalar(
        select(func.count()).select_from(AuditCredit).where(
            AuditCredit.organization_id == org
        )
    )
    assert credits == 10, "куплений пакет пережив скасування підписки"

    account = await client.get("/v1/account")
    # Скасована підписка більше нічого не дає, і резолвер стану вільний
    # називати це або «скасовано», або «без тарифу» — суть тесту не в
    # написі, а в тому, що куплене вціліло.
    assert account.json()["billing_state"] in ("cancelled", "free")
    assert account.json()["usage"]["one_off_available"] == 10
