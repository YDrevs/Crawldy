"""Матриця білінгових подій: життя підписки очима вебхуків.

Усі тести йдуть через `FakeBillingProvider` — той самий контракт, який у
P4.7b реалізує Paddle. Фейк емітить події, тест вирішує, як їх доставити:
двічі, не по порядку, не доставити взагалі. Це не зручність тестів, а
модель реального світу вебхуків.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.application import billing as pipeline
from app.billing import service as billing_service
from app.billing.enums import BillingEventKind, BillingEventStatus, SubscriptionStatus
from app.billing.providers.base import (
    CheckoutRequest,
    ProviderUnavailable,
    VerifiedBillingEvent,
)
from app.billing.providers.fake import FakeBillingProvider
from app.identity import service as identity
from app.models.billing import (
    BillingEvent,
    Plan,
    PlanPrice,
    Subscription,
    SubscriptionTransition,
)

PASSWORD = "correct-horse-battery"

PRO_PRICE = "pri_fake_pro"
AGENCY_PRICE = "pri_fake_agency"


def _now() -> datetime:
    return datetime.now(UTC)


async def _org(db, email: str) -> uuid.UUID:
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    return reg.organization.id


async def _prices(db) -> None:
    """Відображення прайсів фейка на наші тарифи. Конфігурація, не код."""
    plans = {
        p.code: p.id
        for p in (await db.execute(select(Plan).where(Plan.code.in_(("pro", "agency")))))
        .scalars()
        .all()
    }
    db.add(
        PlanPrice(
            plan_id=plans["pro"], provider="fake", provider_price_id=PRO_PRICE,
            currency="USD", interval="month",
        )
    )
    db.add(
        PlanPrice(
            plan_id=plans["agency"], provider="fake", provider_price_id=AGENCY_PRICE,
            currency="USD", interval="month",
        )
    )
    await db.flush()


async def _subscription(db, org: uuid.UUID) -> Subscription:
    stmt = select(Subscription).where(Subscription.organization_id == org)
    return (await db.execute(stmt)).scalars().one()


async def _transitions(db, org: uuid.UUID) -> list[SubscriptionTransition]:
    stmt = (
        select(SubscriptionTransition)
        .where(SubscriptionTransition.organization_id == org)
        .order_by(SubscriptionTransition.recorded_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _plan_code(db, org: uuid.UUID) -> str:
    resolved = await billing_service.for_organization(db, organization_id=org)
    return resolved.plan_code


@pytest.fixture
def fake() -> FakeBillingProvider:
    return FakeBillingProvider()


# ── активація і життя ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_activation_turns_a_paying_org_into_a_pro_org(db_session, fake):
    """Весь ланцюг §3: подія → журнал → перехід → стан → права."""
    org = await _org(db_session, "act@example.com")
    await _prices(db_session)
    assert await _plan_code(db_session, org) == "free"

    result = await pipeline.ingest(
        db_session, fake.activate(organization_id=org, price_ref=PRO_PRICE)
    )

    assert result.outcome == "processed", result.error
    sub = await _subscription(db_session, org)
    assert sub.status is SubscriptionStatus.ACTIVE
    assert sub.current_period_end is not None
    assert await _plan_code(db_session, org) == "pro", "права йдуть за станом"


@pytest.mark.asyncio
async def test_a_trial_start_grants_entitlements_too(db_session, fake):
    org = await _org(db_session, "trial@example.com")
    await _prices(db_session)

    await pipeline.ingest(
        db_session, fake.activate(organization_id=org, price_ref=PRO_PRICE, with_trial=True)
    )

    sub = await _subscription(db_session, org)
    assert sub.status is SubscriptionStatus.TRIALING
    assert sub.trial_end is not None
    assert await _plan_code(db_session, org) == "pro"


@pytest.mark.asyncio
async def test_renewal_moves_the_period_forward(db_session, fake):
    org = await _org(db_session, "renew@example.com")
    await _prices(db_session)
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)
    first_end = (await _subscription(db_session, org)).current_period_end

    await pipeline.ingest(
        db_session, fake.renew(started.subscription_ref, at=_now() + timedelta(days=30))
    )

    sub = await _subscription(db_session, org)
    assert sub.status is SubscriptionStatus.ACTIVE
    assert sub.current_period_end > first_end


# ── невдалі списання, грація, відновлення ─────────────────────────────────


@pytest.mark.asyncio
async def test_a_failed_renewal_grants_grace_not_a_cliff(db_session, fake):
    org = await _org(db_session, "pastdue@example.com")
    await _prices(db_session)
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)

    await pipeline.ingest(
        db_session, fake.fail_payment(started.subscription_ref, at=_now() + timedelta(days=30))
    )

    sub = await _subscription(db_session, org)
    assert sub.status is SubscriptionStatus.PAST_DUE
    assert sub.grace_until is not None, "строк грації проставлено явно"
    assert await _plan_code(db_session, org) == "pro", "грація: права ще діють"


@pytest.mark.asyncio
async def test_grace_expiration_drops_entitlements_without_an_event(db_session, fake):
    """Провайдер мовчить, а грація скінчилась — прав більше немає.

    Стан у базі лишається past_due: перевести в cancelled має провайдер
    своєю подією, а не ми здогадкою. Наше рішення — не давати прав, і
    воно оборотне.
    """
    org = await _org(db_session, "graceout@example.com")
    await _prices(db_session)
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)
    await pipeline.ingest(db_session, fake.fail_payment(started.subscription_ref))

    sub = await _subscription(db_session, org)
    sub.grace_until = _now() - timedelta(hours=1)
    await db_session.flush()

    assert await _plan_code(db_session, org) == "free"
    assert sub.status is SubscriptionStatus.PAST_DUE, "стан не вигаданий нами"


@pytest.mark.asyncio
async def test_recovery_during_grace_restores_active(db_session, fake):
    org = await _org(db_session, "recover@example.com")
    await _prices(db_session)
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)
    await pipeline.ingest(db_session, fake.fail_payment(started.subscription_ref))

    await pipeline.ingest(
        db_session,
        fake.recover_payment(started.subscription_ref, at=_now() + timedelta(hours=2)),
    )

    sub = await _subscription(db_session, org)
    assert sub.status is SubscriptionStatus.ACTIVE
    assert sub.grace_until is None, "грація знята"
    assert await _plan_code(db_session, org) == "pro"


# ── скасування ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cancellation_at_period_end_is_a_flag_until_it_happens(db_session, fake):
    org = await _org(db_session, "schedcancel@example.com")
    await _prices(db_session)
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)

    await pipeline.ingest(db_session, fake.schedule_cancellation(started.subscription_ref))

    sub = await _subscription(db_session, org)
    assert sub.status is SubscriptionStatus.ACTIVE, "ще активна"
    assert sub.cancel_at_period_end is True
    assert await _plan_code(db_session, org) == "pro", "оплачене — до кінця періоду"

    await pipeline.ingest(
        db_session,
        fake.cancel(started.subscription_ref, at=sub.current_period_end),
    )
    sub = await _subscription(db_session, org)
    assert sub.status is SubscriptionStatus.CANCELLED
    assert await _plan_code(db_session, org) == "free"


@pytest.mark.asyncio
async def test_immediate_cancellation_ends_it_now(db_session, fake):
    org = await _org(db_session, "hardcancel@example.com")
    await _prices(db_session)
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)

    await pipeline.ingest(db_session, fake.cancel(started.subscription_ref))

    assert (await _subscription(db_session, org)).status is SubscriptionStatus.CANCELLED
    assert await _plan_code(db_session, org) == "free"


# ── зміна тарифу ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_plan_change_is_a_mapping_lookup_not_a_hardcode(db_session, fake):
    org = await _org(db_session, "upgrade@example.com")
    await _prices(db_session)
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)

    await pipeline.ingest(
        db_session,
        fake.change_plan(
            started.subscription_ref, price_ref=AGENCY_PRICE, at=_now() + timedelta(minutes=1)
        ),
    )

    assert await _plan_code(db_session, org) == "agency"
    last = (await _transitions(db_session, org))[-1]
    assert last.from_plan_id != last.to_plan_id, "зміна тарифу видима в історії"


@pytest.mark.asyncio
async def test_a_plan_change_does_not_touch_old_audits(db_session, fake):
    """Історія аудитів — виміряні факти; тариф на них не діє ретроспективно."""
    from app.audit.enums import AuditStatus
    from app.models.audit import Audit

    org = await _org(db_session, "history@example.com")
    await _prices(db_session)
    audit = Audit(
        organization_id=org, url="https://example.com/", origin="https://example.com",
        status=AuditStatus.COMPLETED, score_overall=64, options={"max_pages": 10},
        finished_at=_now(),
    )
    db_session.add(audit)
    await db_session.flush()
    audit_id = audit.id  # до expire_all: доступ до простроченого — sync-load
    before = (audit.score_overall, dict(audit.options), audit.status)

    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)
    await pipeline.ingest(
        db_session,
        fake.change_plan(
            started.subscription_ref, price_ref=AGENCY_PRICE, at=_now() + timedelta(minutes=1)
        ),
    )

    db_session.expire_all()
    fresh = await db_session.get(Audit, audit_id)
    assert (fresh.score_overall, dict(fresh.options), fresh.status) == before


# ── дублікати ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_duplicate_delivery_is_one_transition(db_session, fake):
    org = await _org(db_session, "dup@example.com")
    await _prices(db_session)
    event = fake.activate(organization_id=org, price_ref=PRO_PRICE)

    first = await pipeline.ingest(db_session, event)
    second = await pipeline.ingest(db_session, event)
    third = await pipeline.ingest(db_session, event)

    assert first.outcome == "processed"
    assert second.outcome == "duplicate"
    assert third.outcome == "duplicate"
    assert len(await _transitions(db_session, org)) == 1
    events = (await db_session.execute(select(BillingEvent))).scalars().all()
    assert len(events) == 1, "рядок у журналі один"


@pytest.mark.asyncio
async def test_the_database_refuses_a_second_row_for_the_same_event(db_session, fake):
    """Ідемпотентність тримається базою, а не if-ом у Python."""
    org = await _org(db_session, "race@example.com")
    await _prices(db_session)
    event = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, event)

    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(
                BillingEvent(
                    provider=event.provider,
                    external_event_id=event.external_event_id,
                    kind=event.kind.value,
                    occurred_at=event.occurred_at,
                )
            )
            await db_session.flush()


@pytest.mark.asyncio
async def test_the_same_event_id_in_two_providers_does_not_collide(db_session, fake):
    """`evt_1` у Paddle і `evt_1` у Stripe — різні події."""
    org = await _org(db_session, "twoprov@example.com")
    await _prices(db_session)
    event = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, event)

    db_session.add(
        BillingEvent(
            provider="another-provider",
            external_event_id=event.external_event_id,
            kind=event.kind.value,
            occurred_at=event.occurred_at,
        )
    )
    await db_session.flush()  # не кидає: ключ (provider, external_event_id)


# ── не по порядку ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_older_event_cannot_roll_the_subscription_back(db_session, fake):
    """Головна перевірка §5: B новіший застосовано, A старіший — ні."""
    org = await _org(db_session, "ooo@example.com")
    await _prices(db_session)
    moment = _now()
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE, at=moment)
    renewed = fake.renew(started.subscription_ref, at=moment + timedelta(days=30))

    # Доставка навпаки: спершу новіша подія.
    await pipeline.ingest(db_session, renewed)
    late = await pipeline.ingest(db_session, started)

    assert late.outcome == "stale"
    sub = await _subscription(db_session, org)
    assert sub.status is SubscriptionStatus.ACTIVE
    assert sub.current_period_end == renewed.period_end, "період — від новішої події"
    record = (
        await db_session.execute(
            select(BillingEvent).where(
                BillingEvent.external_event_id == started.external_event_id
            )
        )
    ).scalars().one()
    assert record.status is BillingEventStatus.STALE, "стара подія записана, не застосована"


@pytest.mark.asyncio
async def test_a_late_cancellation_from_the_past_does_not_kill_a_recovered_subscription(
    db_session, fake
):
    """Скасування, що заблукало в дорозі, не вбиває відновлену підписку."""
    org = await _org(db_session, "latecancel@example.com")
    await _prices(db_session)
    moment = _now()
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE, at=moment)
    old_cancel = fake.cancel(started.subscription_ref, at=moment + timedelta(days=1))
    recovered = fake.renew(started.subscription_ref, at=moment + timedelta(days=2))

    await pipeline.ingest(db_session, started)
    await pipeline.ingest(db_session, recovered)
    late = await pipeline.ingest(db_session, old_cancel)

    assert late.outcome == "stale"
    assert (await _subscription(db_session, org)).status is SubscriptionStatus.ACTIVE


# ── збої і повтори ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_unknown_price_fails_visibly_and_replays_after_the_fix(db_session, fake):
    """§9: received ≠ processed. Збій видно, повтор безпечний."""
    org = await _org(db_session, "noprice@example.com")
    event = fake.activate(organization_id=org, price_ref="pri_nobody_mapped_me")

    failed = await pipeline.ingest(db_session, event)

    assert failed.outcome == "failed"
    assert "не відображений" in failed.error
    record = (await db_session.execute(select(BillingEvent))).scalars().one()
    assert record.status is BillingEventStatus.FAILED
    assert record.processed_at is None, "невдале не вважається обробленим"

    # Виправили дані — додали відображення прайсу.
    plan = (await db_session.execute(select(Plan).where(Plan.code == "pro"))).scalars().one()
    db_session.add(
        PlanPrice(
            plan_id=plan.id, provider="fake", provider_price_id="pri_nobody_mapped_me",
            currency="USD", interval="month",
        )
    )
    await db_session.flush()

    replayed = await pipeline.replay_failed(db_session)

    assert [r.outcome for r in replayed] == ["processed"]
    assert (await _subscription(db_session, org)).status is SubscriptionStatus.ACTIVE
    assert len(await _transitions(db_session, org)) == 1, "повтор не подвоїв переходу"


@pytest.mark.asyncio
async def test_a_redelivery_of_a_failed_event_retries_instead_of_saying_duplicate(
    db_session, fake
):
    """Повторна доставка невдалої події — нагода доробити, а не «вже було»."""
    org = await _org(db_session, "redeliver@example.com")
    event = fake.activate(organization_id=org, price_ref="pri_unmapped_yet")
    assert (await pipeline.ingest(db_session, event)).outcome == "failed"

    plan = (await db_session.execute(select(Plan).where(Plan.code == "pro"))).scalars().one()
    db_session.add(
        PlanPrice(
            plan_id=plan.id, provider="fake", provider_price_id="pri_unmapped_yet",
            currency="USD", interval="month",
        )
    )
    await db_session.flush()

    again = await pipeline.ingest(db_session, event)

    assert again.outcome == "processed"
    assert len(await _transitions(db_session, org)) == 1


@pytest.mark.asyncio
async def test_an_invalid_transition_is_a_visible_failure_not_a_silent_shrug(db_session, fake):
    org = await _org(db_session, "invalid@example.com")
    await _prices(db_session)
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)
    await pipeline.ingest(
        db_session, fake.cancel(started.subscription_ref, at=_now() + timedelta(minutes=1))
    )

    # Після скасування приходить ще новіше «відновлення з паузи» —
    # перехід, якого з CANCELLED не існує. Подію будуємо руками: фейк
    # такої не емітить, бо чесний провайдер її теж не мав би слати.
    ghost = VerifiedBillingEvent(
        provider="fake",
        external_event_id="evt_ghost_resume",
        kind=BillingEventKind.SUBSCRIPTION_RESUMED,
        occurred_at=_now() + timedelta(minutes=5),
        subscription_ref=started.subscription_ref,
        customer_ref=started.customer_ref,
        price_ref=PRO_PRICE,
        organization_id=org,
    )
    result = await pipeline.ingest(db_session, ghost)

    assert result.outcome == "failed"
    assert "не застосовна" in result.error
    assert (await _subscription(db_session, org)).status is SubscriptionStatus.CANCELLED


@pytest.mark.asyncio
async def test_a_provider_outage_is_an_exception_not_a_hang(db_session, fake):
    fake.down = True
    with pytest.raises(ProviderUnavailable):
        await fake.create_customer(organization_id=uuid.uuid4(), email="x@example.com")
    with pytest.raises(ProviderUnavailable):
        await fake.create_checkout(
            CheckoutRequest(
                purchase_id=uuid.uuid4(),
                price_ref=PRO_PRICE,
                organization_id=uuid.uuid4(),
            )
        )


# ── історія, яку можна пояснити ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_transition_journal_explains_why_pro_on_a_given_day(db_session, fake):
    """§12: «чому ця організація 14 березня мала Pro» — відповідь є в базі."""
    org = await _org(db_session, "explain@example.com")
    await _prices(db_session)
    moment = _now()
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE, at=moment)
    await pipeline.ingest(db_session, started)
    await pipeline.ingest(
        db_session, fake.fail_payment(started.subscription_ref, at=moment + timedelta(days=30))
    )
    await pipeline.ingest(
        db_session, fake.cancel(started.subscription_ref, at=moment + timedelta(days=40))
    )

    journal = await _transitions(db_session, org)

    assert [(t.from_status, t.to_status) for t in journal] == [
        (SubscriptionStatus.INACTIVE, SubscriptionStatus.ACTIVE),
        (SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE),
        (SubscriptionStatus.PAST_DUE, SubscriptionStatus.CANCELLED),
    ]
    active = journal[0]
    assert active.effective_at == moment, "з якого моменту діяло"
    assert active.period_start is not None and active.period_end is not None
    assert active.billing_event_id is not None, "яка подія це спричинила"
    assert all(t.organization_id == org for t in journal)


@pytest.mark.asyncio
async def test_ingesting_more_events_never_rewrites_old_transitions(db_session, fake):
    org = await _org(db_session, "immutable@example.com")
    await _prices(db_session)
    started = fake.activate(organization_id=org, price_ref=PRO_PRICE)
    await pipeline.ingest(db_session, started)
    first = (await _transitions(db_session, org))[0]
    remembered = (first.id, first.from_status, first.to_status, first.effective_at)

    await pipeline.ingest(
        db_session, fake.renew(started.subscription_ref, at=_now() + timedelta(days=30))
    )
    await pipeline.ingest(
        db_session, fake.cancel(started.subscription_ref, at=_now() + timedelta(days=31))
    )

    db_session.expire_all()
    fresh = await db_session.get(SubscriptionTransition, remembered[0])
    assert (fresh.id, fresh.from_status, fresh.to_status, fresh.effective_at) == remembered
