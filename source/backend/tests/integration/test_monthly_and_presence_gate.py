"""MONTHLY-модель і гейт присутності: квоти, безліміт, розрахунок права.

MONTHLY — це наявні тарифи з підпискою: ліміти в entitlements,
споживання в usage_counters за періодом підписки. Тут закони:

* безліміт краулів НІКОЛИ не означає безліміт AI — presence_per_period
  завжди число;
* новий період підписки — новий рядок лічильника: подвійного
  скидання/нарахування того самого періоду не існує структурно;
* скасування підписки не чіпає куплених PACK-кредитів;
* присутність без права — 402; придатне покриття списує, непридатне
  повертає.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.billing import credits as billing_credits
from app.billing import quota as billing_quota
from app.models.billing import Plan, Subscription
from app.presence.providers.scripted import ScriptedPresenceProvider, ScriptedReply
from app.services import presence_service
from tests.integration.conftest import register
from tests.integration.test_presence_api import (
    _enable_with_scripted,
    _grant_presence,
)

pytestmark = pytest.mark.asyncio


async def _org_of(db_session) -> uuid.UUID:
    from app.models.identity import Organization

    return (await db_session.execute(
        select(Organization.id).order_by(Organization.created_at.desc()).limit(1)
    )).scalar_one()


async def _subscribe(db_session, org: uuid.UUID, *, audits_limit,
                     presence_limit: int) -> Subscription:
    plan = Plan(
        code=f"monthly-{uuid.uuid4().hex[:6]}", name="Monthly",
        entitlements={
            "audits_per_period": audits_limit,
            "presence_per_period": presence_limit,
        },
    )
    db_session.add(plan)
    await db_session.flush()
    now = datetime.now(UTC)
    subscription = Subscription(
        organization_id=org, plan_id=plan.id, status="ACTIVE",
        provider="fake", provider_subscription_id=f"sub-{uuid.uuid4().hex[:8]}",
        current_period_start=now - timedelta(days=1),
        current_period_end=now + timedelta(days=29),
    )
    db_session.add(subscription)
    await db_session.commit()
    return subscription


# ── місячні квоти ────────────────────────────────────────────────────


async def test_limited_monthly_audits_enforce_the_configured_number(
    client, db_session
):
    await register(client, "monthly-limited@example.com")
    org = await _org_of(db_session)
    sub = await _subscribe(db_session, org, audits_limit=2, presence_limit=0)
    period = billing_quota.period_for(sub)
    first = await billing_quota.consume(
        db_session, organization_id=org, period=period, limit=2)
    second = await billing_quota.consume(
        db_session, organization_id=org, period=period, limit=2)
    third = await billing_quota.consume(
        db_session, organization_id=org, period=period, limit=2)
    assert first.allowed and second.allowed and not third.allowed


async def test_unlimited_crawl_still_counts_usage(client, db_session):
    await register(client, "monthly-unlim@example.com")
    org = await _org_of(db_session)
    sub = await _subscribe(db_session, org, audits_limit=None,
                           presence_limit=5)
    period = billing_quota.period_for(sub)
    for _ in range(4):
        decision = await billing_quota.consume(
            db_session, organization_id=org, period=period, limit=None)
        assert decision.allowed
    used = await billing_quota.used_in(
        db_session, organization_id=org, period=period)
    assert used == 4, "безліміт рахує споживання, не блокуючи його"


async def test_new_billing_period_is_a_new_counter_row(client, db_session):
    """Скидання періоду структурне: інший period_start — інший рядок.
    Повторне «нарахування» того самого періоду неможливе — ON CONFLICT
    інкрементить той самий рядок, а не створює другий."""
    await register(client, "monthly-period@example.com")
    org = await _org_of(db_session)
    sub = await _subscribe(db_session, org, audits_limit=3, presence_limit=0)
    period1 = billing_quota.period_for(sub)
    await billing_quota.consume(db_session, organization_id=org,
                                period=period1, limit=3)
    # «оновлення» підписки: наступний період
    sub.current_period_start = period1.end
    sub.current_period_end = period1.end + timedelta(days=30)
    await db_session.commit()
    period2 = billing_quota.period_for(sub)
    assert period2.start != period1.start
    used2 = await billing_quota.used_in(
        db_session, organization_id=org, period=period2)
    assert used2 == 0, "новий період починається з нуля"
    used1 = await billing_quota.used_in(
        db_session, organization_id=org, period=period1)
    assert used1 == 1, "старий період не переписаний"


async def test_cancellation_leaves_pack_credits_untouched(client, db_session):
    await register(client, "monthly-cancel@example.com")
    org = await _org_of(db_session)
    sub = await _subscribe(db_session, org, audits_limit=10,
                           presence_limit=2)
    await billing_credits.grant(
        db_session, organization_id=org, credit_type="audit", quantity=7,
        source="purchase", reason=None)
    await db_session.commit()
    sub.status = "CANCELLED"
    await db_session.commit()
    assert await billing_credits.balance(db_session, organization_id=org) == 7, (
        "PACK-кредити вічні й не належать підписці")


# ── гейт присутності ─────────────────────────────────────────────────


async def test_presence_without_entitlement_is_402(client, db_session):
    await register(client, "gate-402@example.com")
    await _enable_with_scripted(db_session)
    response = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic"})
    assert response.status_code == 402


async def test_monthly_presence_allowance_admits_and_counts(client, db_session):
    await register(client, "gate-monthly@example.com")
    await _enable_with_scripted(db_session)
    org = await _org_of(db_session)
    sub = await _subscribe(db_session, org, audits_limit=None,
                           presence_limit=2)
    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic"})
    assert created.status_code == 202, created.text
    used = await billing_quota.used_in(
        db_session, organization_id=org,
        period=billing_quota.period_for(sub), metric="presence")
    assert used == 1
    run = await db_session.get(
        presence_service.PresenceRun, uuid.UUID(created.json()["id"]))
    assert run.entitlement_source == "subscription"


async def test_deliverable_run_consumes_the_reserved_credit(client, db_session):
    await register(client, "gate-consume@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)
    org = await _org_of(db_session)
    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic"})
    run_id = uuid.UUID(created.json()["id"])
    provider = ScriptedPresenceProvider([ScriptedReply("ok")])
    await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()
    from app.models.purchase import AuditCredit

    credit = (await db_session.execute(
        select(AuditCredit).where(AuditCredit.presence_run_id == run_id)
    )).scalars().one()
    assert credit.state.value == "consumed", (
        "30/30 успішних (поріг min(20, 30)) — прогін придатний, списано")
    assert await billing_credits.balance(
        db_session, organization_id=org, credit_type="presence") == 0


async def test_undeliverable_run_releases_the_credit(client, db_session):
    """Покриття нижче порога — клієнт не платить; витрачене поглинаємо ми."""
    await register(client, "gate-release@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)
    org = await _org_of(db_session)
    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic"})
    run_id = uuid.UUID(created.json()["id"])
    # 30 клітинок, усі — відмова провайдера: 0 успішних, поріг 20
    from app.presence.contracts import ObservationStatus

    provider = ScriptedPresenceProvider(
        [ScriptedReply("", fail_with=ObservationStatus.REFUSED)])
    await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()
    assert await billing_credits.balance(
        db_session, organization_id=org, credit_type="presence") == 1, (
        "право повернулося")
    run = await db_session.get(presence_service.PresenceRun, run_id)
    assert run.entitlement_settled is True


async def test_resume_does_not_settle_twice(client, db_session):
    await register(client, "gate-resume@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)
    org = await _org_of(db_session)
    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic"})
    run_id = uuid.UUID(created.json()["id"])
    provider = ScriptedPresenceProvider([ScriptedReply("ok")])
    await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()
    await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()
    balances = [
        await billing_credits.balance(
            db_session, organization_id=org, credit_type="presence"),
        await billing_credits.balance(db_session, organization_id=org),
    ]
    assert balances == [0, 0], "повтор не списує вдруге і не повертає списане"


