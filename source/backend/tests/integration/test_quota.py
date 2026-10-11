"""Квота: атомарність, період, повернення.

Головний тест тут — гонка. Усе інше можна було б перевірити й без бази;
те, що два паралельні запити на останній аудит дають рівно одне
списання, — не можна.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.billing import quota
from app.billing import service as billing
from app.billing.enums import SubscriptionStatus
from app.identity import service as identity
from app.models.billing import Subscription

PASSWORD = "correct-horse-battery"


def _now() -> datetime:
    return datetime.now(UTC)


async def _org(db, email="a@example.com"):
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    return reg.organization.id


@pytest.mark.asyncio
async def test_consuming_within_the_limit_succeeds(db_session):
    org = await _org(db_session)
    period = quota.period_for(None)

    first = await quota.consume(db_session, organization_id=org, period=period, limit=3)
    second = await quota.consume(db_session, organization_id=org, period=period, limit=3)

    assert first.allowed and first.used == 1
    assert second.allowed and second.used == 2
    assert second.remaining == 1


@pytest.mark.asyncio
async def test_the_limit_is_the_limit(db_session):
    org = await _org(db_session)
    period = quota.period_for(None)
    for _ in range(2):
        await quota.consume(db_session, organization_id=org, period=period, limit=2)

    third = await quota.consume(db_session, organization_id=org, period=period, limit=2)

    assert third.allowed is False
    assert third.reason == "quota.exhausted"
    assert third.used == 2, "лічильник не збільшився на відмові"


@pytest.mark.asyncio
async def test_a_zero_limit_means_the_feature_is_not_in_the_plan(db_session):
    """Нуль і «вичерпано» — різні відповіді.

    Клієнтові з тарифом без аудитів треба сказати «це не входить у ваш
    тариф», а не «ви використали 0 з 0».
    """
    org = await _org(db_session)

    decision = await quota.consume(
        db_session, organization_id=org, period=quota.period_for(None), limit=0
    )

    assert decision.allowed is False
    assert decision.reason == "quota.not_included"


@pytest.mark.asyncio
async def test_no_limit_still_counts(db_session):
    """Тариф без обмеження все одно рахує споживання.

    Інакше «скільки аудитів було в травні» немає з чого відповісти — а
    це перше питання при суперечці про рахунок.
    """
    org = await _org(db_session)
    period = quota.period_for(None)

    for _ in range(3):
        decision = await quota.consume(
            db_session, organization_id=org, period=period, limit=None
        )

    assert decision.allowed is True
    assert decision.used == 3
    assert decision.remaining is None


@pytest.mark.asyncio
async def test_releasing_gives_the_unit_back(db_session):
    org = await _org(db_session)
    period = quota.period_for(None)
    await quota.consume(db_session, organization_id=org, period=period, limit=1)

    await quota.release(db_session, organization_id=org, period=period)

    again = await quota.consume(db_session, organization_id=org, period=period, limit=1)
    assert again.allowed is True


@pytest.mark.asyncio
async def test_releasing_never_goes_below_zero(db_session):
    org = await _org(db_session)
    period = quota.period_for(None)

    await quota.release(db_session, organization_id=org, period=period)
    await quota.release(db_session, organization_id=org, period=period)

    assert await quota.used_in(db_session, organization_id=org, period=period) == 0


@pytest.mark.asyncio
async def test_two_organizations_do_not_share_a_counter(db_session):
    first = await _org(db_session, "first@example.com")
    second = await _org(db_session, "second@example.com")
    period = quota.period_for(None)
    await quota.consume(db_session, organization_id=first, period=period, limit=1)

    decision = await quota.consume(db_session, organization_id=second, period=period, limit=1)

    assert decision.allowed is True


@pytest.mark.asyncio
async def test_a_new_period_starts_from_zero(db_session):
    org = await _org(db_session)
    old = quota.Period(
        start=_now() - timedelta(days=60), end=_now() - timedelta(days=30), source="calendar"
    )
    await quota.consume(db_session, organization_id=org, period=old, limit=1)

    decision = await quota.consume(
        db_session, organization_id=org, period=quota.period_for(None), limit=1
    )

    assert decision.allowed is True


# ── період ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_period_follows_the_subscription_not_the_calendar(db_session):
    """Клієнт, який оплатив 15-го, очікує свій ліміт з 15-го.

    Це найлегша річ переплутати, тому вона перевіряється окремо.
    """
    org = await _org(db_session)
    plan = await billing.plan_by_code(db_session, "pro")
    start = _now() - timedelta(days=10)
    subscription = Subscription(
        organization_id=org,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        provider="paddle",
        current_period_start=start,
        current_period_end=start + timedelta(days=30),
    )
    db_session.add(subscription)
    await db_session.flush()

    period = quota.period_for(subscription)

    assert period.source == "subscription"
    assert period.start == start


def test_without_a_subscription_the_period_is_the_calendar_month():
    period = quota.period_for(None, at=datetime(2026, 8, 22, 13, 0, tzinfo=UTC))

    assert period.source == "calendar"
    assert period.start == datetime(2026, 8, 1, tzinfo=UTC)
    assert period.end == datetime(2026, 9, 1, tzinfo=UTC)


def test_december_rolls_into_january():
    """Найпопулярніша помилка в обчисленні місяця."""
    period = quota.period_for(None, at=datetime(2026, 12, 15, tzinfo=UTC))

    assert period.end == datetime(2027, 1, 1, tzinfo=UTC)


def test_an_expired_subscription_period_falls_back_to_the_calendar(db_session):
    """Підписка з простроченим періодом не має розтягувати квоту вічно."""
    stale = Subscription(
        organization_id=None,
        plan_id=None,
        status=SubscriptionStatus.ACTIVE,
        provider="paddle",
        current_period_start=_now() - timedelta(days=90),
        current_period_end=_now() - timedelta(days=60),
    )

    assert quota.period_for(stale).source == "calendar"


# ── гонка ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_two_parallel_requests_for_the_last_audit_give_exactly_one(postgres_url):
    """Заради цього списання й зроблене одним запитом.

    Тут потрібні справжні паралельні з'єднання, а не транзакція фікстури:
    усередині однієї сесії гонки не буває, а дані фікстури не видно
    ззовні, бо її транзакція не закомічена. Тому тест працює власними
    з'єднаннями й прибирає за собою сам.
    """
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    period = quota.period_for(None)

    async with factory() as setup:
        org = await _org(setup, "race@example.com")
        await setup.commit()

    async def attempt() -> bool:
        async with factory() as session:
            decision = await quota.consume(session, organization_id=org, period=period, limit=1)
            await session.commit()
            return decision.allowed

    try:
        results = await asyncio.gather(attempt(), attempt())

        assert sorted(results) == [False, True], "рівно одне списання з двох спроб"

        async with factory() as check:
            assert await quota.used_in(check, organization_id=org, period=period) == 1
    finally:
        # Фікстура нічого не відкотить: ми писали повз її транзакцію.
        async with factory() as cleanup:
            await cleanup.execute(
                text("DELETE FROM usage_counters WHERE organization_id = :org"), {"org": org}
            )
            await cleanup.execute(
                text("DELETE FROM memberships WHERE organization_id = :org"), {"org": org}
            )
            await cleanup.execute(
                text("DELETE FROM users WHERE email = 'race@example.com'")
            )
            await cleanup.execute(
                text("DELETE FROM organizations WHERE id = :org"), {"org": org}
            )
            await cleanup.commit()
        await engine.dispose()
