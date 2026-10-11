"""Права організації на справжній базі: підписка, грація, винятки."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.billing import service
from app.billing.enums import DEFAULT_PAST_DUE_GRACE_DAYS, SubscriptionStatus
from app.identity import service as identity
from app.models.billing import Plan, Subscription

PASSWORD = "correct-horse-battery"


def _now() -> datetime:
    return datetime.now(UTC)


async def _org(db, email="a@example.com"):
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    return reg.organization.id


async def _subscribe(db, org_id, code="pro", status=SubscriptionStatus.ACTIVE, **extra):
    plan = await service.plan_by_code(db, code)
    record = Subscription(
        organization_id=org_id,
        plan_id=plan.id,
        status=status,
        provider="paddle",
        current_period_start=_now() - timedelta(days=1),
        current_period_end=_now() + timedelta(days=29),
        **extra,
    )
    db.add(record)
    await db.flush()
    return record


@pytest.mark.asyncio
async def test_the_seeded_plans_are_valid(db_session):
    """Тариф із помилкою в правах зламався б не одразу, а у клієнта.

    Перевіряємо саме засіяні дані, а не абстрактний словник: помилка
    друку в міграції інакше жила б до першої перевірки ліміту.
    """
    from app.billing import entitlements

    plans = (await db_session.execute(select(Plan))).scalars().all()

    assert {p.code for p in plans} >= {"free", "starter", "pro", "agency"}
    for plan in plans:
        assert entitlements.validate(plan.entitlements) == [], plan.code


@pytest.mark.asyncio
async def test_an_organization_without_a_subscription_gets_the_free_plan(db_session):
    org = await _org(db_session)

    ent = await service.for_organization(db_session, organization_id=org)

    assert ent.plan_code == "free"
    assert ent.can("api_access") is False


@pytest.mark.asyncio
async def test_an_active_subscription_gives_the_plan_of_that_subscription(db_session):
    org = await _org(db_session)
    await _subscribe(db_session, org, "pro")

    ent = await service.for_organization(db_session, organization_id=org)

    assert ent.plan_code == "pro"
    assert ent.can("api_access") is True
    assert ent.can("semantic_analysis") is True


@pytest.mark.asyncio
async def test_a_cancelled_subscription_falls_back_to_free(db_session):
    org = await _org(db_session)
    await _subscribe(db_session, org, "pro", status=SubscriptionStatus.CANCELLED)

    ent = await service.for_organization(db_session, organization_id=org)

    assert ent.plan_code == "free"


@pytest.mark.asyncio
async def test_a_failed_payment_does_not_cut_the_service_immediately(db_session):
    """Грація навмисна.

    Відрізати клієнта, який платить, на першій невдалій спробі списання
    гірше, ніж кілька днів безкоштовного сервісу.
    """
    org = await _org(db_session)
    await _subscribe(
        db_session,
        org,
        "pro",
        status=SubscriptionStatus.PAST_DUE,
        grace_until=_now() + timedelta(days=DEFAULT_PAST_DUE_GRACE_DAYS),
    )

    ent = await service.for_organization(db_session, organization_id=org)

    assert ent.plan_code == "pro"


@pytest.mark.asyncio
async def test_when_the_grace_runs_out_the_rights_stop(db_session):
    org = await _org(db_session)
    await _subscribe(
        db_session,
        org,
        "pro",
        status=SubscriptionStatus.PAST_DUE,
        grace_until=_now() - timedelta(hours=1),
    )

    ent = await service.for_organization(db_session, organization_id=org)

    assert ent.plan_code == "free"


@pytest.mark.asyncio
async def test_running_out_of_grace_does_not_rewrite_the_status(db_session):
    """Перевести підписку в cancelled має провайдер своєю подією.

    Наше рішення — не давати прав, і воно оборотне: платіж пройде, і
    все повернеться без ручного втручання.
    """
    org = await _org(db_session)
    record = await _subscribe(
        db_session,
        org,
        "pro",
        status=SubscriptionStatus.PAST_DUE,
        grace_until=_now() - timedelta(hours=1),
    )

    await service.for_organization(db_session, organization_id=org)

    assert record.status is SubscriptionStatus.PAST_DUE


@pytest.mark.asyncio
async def test_only_one_live_subscription_per_organization(db_session):
    """Друга означала б два набори прав одночасно й питання «який правда»
    без відповіді. Обмеження в базі, бо перевірка в коді не переживе гонки."""
    org = await _org(db_session)
    await _subscribe(db_session, org, "pro")

    async with db_session.begin_nested():
        with pytest.raises(IntegrityError):
            # Виняток вилітає вже на flush усередині _subscribe: саме
            # цього ми й хочемо — база не дає створити другу живу підписку.
            await _subscribe(db_session, org, "starter")


@pytest.mark.asyncio
async def test_a_cancelled_subscription_does_not_block_a_new_one(db_session):
    """Частковий індекс покриває лише живі стани — інакше клієнт не зміг
    би повернутися після скасування."""
    org = await _org(db_session)
    await _subscribe(db_session, org, "pro", status=SubscriptionStatus.CANCELLED)

    await _subscribe(db_session, org, "starter")

    ent = await service.for_organization(db_session, organization_id=org)
    assert ent.plan_code == "starter"


# ── індивідуальні винятки ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_override_lifts_a_limit_without_changing_the_plan(db_session):
    org = await _org(db_session)
    await _subscribe(db_session, org, "starter")

    await service.grant_override(
        db_session,
        organization_id=org,
        key="sites_limit",
        value=100,
        reason="компенсація за збій 21.08",
    )

    ent = await service.for_organization(db_session, organization_id=org)
    assert ent.plan_code == "starter"
    assert ent.limit("sites_limit") == 100


@pytest.mark.asyncio
async def test_an_expired_override_stops_working(db_session):
    org = await _org(db_session)
    await service.grant_override(
        db_session,
        organization_id=org,
        key="api_access",
        value=True,
        reason="тестовий доступ",
        expires_at=_now() - timedelta(minutes=1),
    )

    ent = await service.for_organization(db_session, organization_id=org)

    assert ent.can("api_access") is False


@pytest.mark.asyncio
async def test_an_override_without_a_reason_is_refused(db_session):
    """Виняток без причини через рік неможливо ні пояснити, ні зняти —
    і він живе вічно саме тому."""
    org = await _org(db_session)

    with pytest.raises(ValueError, match="причини"):
        await service.grant_override(
            db_session, organization_id=org, key="api_access", value=True, reason="  "
        )


@pytest.mark.asyncio
async def test_an_override_of_a_nonexistent_right_is_refused(db_session):
    org = await _org(db_session)

    with pytest.raises(KeyError):
        await service.grant_override(
            db_session, organization_id=org, key="вигадане", value=1, reason="бо"
        )


@pytest.mark.asyncio
async def test_an_override_with_the_wrong_type_is_refused(db_session):
    org = await _org(db_session)

    with pytest.raises(ValueError, match="число"):
        await service.grant_override(
            db_session,
            organization_id=org,
            key="sites_limit",
            value="багато",
            reason="хай буде",
        )


@pytest.mark.asyncio
async def test_granting_the_same_key_twice_updates_it(db_session):
    org = await _org(db_session)
    await service.grant_override(
        db_session, organization_id=org, key="sites_limit", value=10, reason="перша"
    )

    await service.grant_override(
        db_session, organization_id=org, key="sites_limit", value=20, reason="друга"
    )

    ent = await service.for_organization(db_session, organization_id=org)
    assert ent.limit("sites_limit") == 20


@pytest.mark.asyncio
async def test_entitlements_of_one_organization_do_not_leak_to_another(db_session):
    first = await _org(db_session, "first@example.com")
    second = await _org(db_session, "second@example.com")
    await _subscribe(db_session, first, "agency")

    ent = await service.for_organization(db_session, organization_id=second)

    assert ent.plan_code == "free"
