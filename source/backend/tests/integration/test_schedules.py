"""Розклади: власність, ліміти тарифу, і головне — жодного подвійного запуску.

Останнє перевіряється справжніми паралельними з'єднаннями. У транзакції
фікстури гонки не буває, і тест виглядав би зеленим, не перевіривши того,
заради чого написаний.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application import scheduled
from app.audit.enums import AuditStatus, AuditTrigger
from app.identity import service as identity
from app.models.audit import Audit
from app.models.scheduling import AuditSchedule
from app.scheduling import service as schedules
from app.scheduling.enums import Cadence
from app.sites import service as sites
from tests.integration.conftest import grant_audit_credits, register, sign_in_as

PASSWORD = "correct-horse-battery"


def _now() -> datetime:
    return datetime.now(UTC)


async def _org_with_site(db, email="a@example.com", origin="https://example.com"):
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    site = await sites.create(
        db,
        organization_id=reg.organization.id,
        url=origin,
        created_by_user_id=reg.user.id,
    )
    return reg.organization.id, site.id


# ── створення й ліміти ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_schedule_needs_a_plan_that_allows_it(client):
    """Безкоштовний тариф не має розкладів — це 402, а не 500."""
    await register(client, "a@example.com")
    site = (await client.post("/v1/sites", json={"url": "example.com"})).json()

    response = await client.post(
        "/v1/schedules", json={"site_id": site["id"], "cadence": "daily"}
    )

    assert response.status_code == 402


@pytest.mark.asyncio
async def test_a_schedule_for_a_foreign_site_is_a_404(client):
    """Права не дають доступу до чужого ресурсу: спершу власність."""
    await register(client, "victim@example.com")
    victim_site = (await client.post("/v1/sites", json={"url": "victim.example"})).json()

    await sign_in_as(client, "attacker@example.com")
    response = await client.post(
        "/v1/schedules", json={"site_id": victim_site["id"], "cadence": "daily"}
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_the_plan_limits_how_often_not_just_how_many(db_session):
    """`schedule_min_interval_hours` обмежує частоту, а не назву періоду."""
    org, site = await _org_with_site(db_session)

    with pytest.raises(schedules.TooFrequent):
        await schedules.create(
            db_session,
            organization_id=org,
            site_id=site,
            created_by_user_id=None,
            cadence=Cadence.DAILY,
            min_interval_hours=168,  # тариф дозволяє не частіше ніж раз на тиждень
        )


@pytest.mark.asyncio
async def test_the_plan_limits_how_many(db_session):
    org, site = await _org_with_site(db_session)
    await schedules.create(
        db_session,
        organization_id=org,
        site_id=site,
        created_by_user_id=None,
        cadence=Cadence.WEEKLY,
        limit=1,
    )

    with pytest.raises(schedules.ScheduleLimitReached):
        await schedules.create(
            db_session,
            organization_id=org,
            site_id=site,
            created_by_user_id=None,
            cadence=Cadence.MONTHLY,
            limit=1,
        )


@pytest.mark.asyncio
async def test_an_unknown_timezone_is_refused_not_silently_replaced(db_session):
    """Тихий фолбек на UTC означав би звіти о четвертій ранку без сліду."""
    org, site = await _org_with_site(db_session)

    with pytest.raises(schedules.UnknownTimezone):
        await schedules.create(
            db_session,
            organization_id=org,
            site_id=site,
            created_by_user_id=None,
            cadence=Cadence.DAILY,
            timezone_name="Europe/Kyyiv",
        )


@pytest.mark.asyncio
async def test_a_new_schedule_knows_when_it_runs_next(db_session):
    org, site = await _org_with_site(db_session)

    view = await schedules.create(
        db_session,
        organization_id=org,
        site_id=site,
        created_by_user_id=None,
        cadence=Cadence.DAILY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
    )

    assert view.next_run_at is not None
    assert view.next_run_at > _now()


# ── захоплення ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_only_the_due_ones_are_claimed(db_session):
    org, site = await _org_with_site(db_session)
    due = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, due.id)
    was_due_at = _now() - timedelta(minutes=1)
    record.next_run_at = was_due_at
    await db_session.flush()

    claimed = await schedules.claim_due(db_session)

    assert [c.schedule_id for c in claimed] == [due.id]
    # Момент входження — саме той, на який розклад був запланований, а не
    # «зараз»: на ньому тримається ключ входження.
    assert claimed[0].scheduled_for == was_due_at


@pytest.mark.asyncio
async def test_a_disabled_schedule_is_never_claimed(db_session):
    org, site = await _org_with_site(db_session)
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.next_run_at = _now() - timedelta(minutes=1)
    record.enabled = False
    await db_session.flush()

    assert await schedules.claim_due(db_session) == []


@pytest.mark.asyncio
async def test_a_claimed_schedule_is_not_claimed_again_until_the_lease_expires(db_session):
    org, site = await _org_with_site(db_session)
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.next_run_at = _now() - timedelta(minutes=1)
    await db_session.flush()

    first = await schedules.claim_due(db_session)
    second = await schedules.claim_due(db_session)

    assert [c.schedule_id for c in first] == [view.id]
    assert second == [], "оренда тримає рядок"


@pytest.mark.asyncio
async def test_an_expired_lease_frees_the_schedule(db_session):
    """Процес міг померти між захопленням і запуском.

    Рядок має звільнитися сам, а не чекати ручного втручання.
    """
    org, site = await _org_with_site(db_session)
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.next_run_at = _now() - timedelta(minutes=1)
    record.claimed_until = _now() - timedelta(seconds=1)
    await db_session.flush()

    claimed = await schedules.claim_due(db_session)
    assert [c.schedule_id for c in claimed] == [view.id]


# ── запуск ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_due_schedule_creates_an_audit_marked_as_scheduled(db_session, monkeypatch):
    """Запис має пам'ятати, звідки взявся: «чому це виконалося о третій
    ночі» має відповідь у самому рядку."""
    from app.billing import service as billing
    from app.models.billing import Subscription

    org, site = await _org_with_site(db_session)
    plan = await billing.plan_by_code(db_session, "pro")
    db_session.add(
        Subscription(
            organization_id=org, plan_id=plan.id, status="ACTIVE", provider="paddle",
            current_period_start=_now() - timedelta(days=1),
            current_period_end=_now() + timedelta(days=29),
        )
    )
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.next_run_at = _now() - timedelta(minutes=1)
    await db_session.flush()

    runs = await scheduled.run_all_due(db_session)

    assert len(runs) == 1 and runs[0].started
    audit = await db_session.get(Audit, runs[0].audit_id)
    assert audit.trigger is AuditTrigger.SCHEDULED
    assert audit.site_id == site
    assert audit.created_by_user_id is None, "у розкладу немає автора"


@pytest.mark.asyncio
async def test_after_a_run_the_next_time_moves_forward(db_session):
    from app.billing import service as billing
    from app.models.billing import Subscription

    org, site = await _org_with_site(db_session)
    plan = await billing.plan_by_code(db_session, "pro")
    db_session.add(
        Subscription(
            organization_id=org, plan_id=plan.id, status="ACTIVE", provider="paddle",
            current_period_start=_now() - timedelta(days=1),
            current_period_end=_now() + timedelta(days=29),
        )
    )
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    was_due = _now() - timedelta(minutes=1)
    record.next_run_at = was_due
    await db_session.flush()

    await scheduled.run_all_due(db_session)
    await db_session.refresh(record)

    assert record.next_run_at > _now()
    assert record.last_run_at is not None
    assert record.claimed_until is None, "оренда знята"


@pytest.mark.asyncio
async def test_an_exhausted_quota_still_leaves_a_record(db_session):
    """Найважливіше рішення блоку.

    Історія має показувати «сайт недоступний» замість діри: порожнє
    місце читається як «нічого не сталося», хоча сталося саме те, про що
    клієнту треба знати.
    """
    # Одна куплена одиниця: безкоштовних повних аудитів не існує, тож
    # «вичерпано» тепер означає «куплене скінчилося».
    org, site = await _org_with_site(db_session)
    await grant_audit_credits(db_session, organization_id=org, quantity=1)
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.next_run_at = _now() - timedelta(minutes=1)
    await db_session.flush()

    first = await scheduled.run_all_due(db_session)
    record.next_run_at = _now() - timedelta(minutes=1)
    record.claimed_until = None
    await db_session.flush()
    second = await scheduled.run_all_due(db_session)

    assert first[0].started is True
    assert second[0].started is False
    assert second[0].audit_id is not None, "пропущений запуск теж є записом"

    missed = await db_session.get(Audit, second[0].audit_id)
    assert missed.status is AuditStatus.SKIPPED, "пропущено, а не зламалося"
    assert missed.trigger is AuditTrigger.SCHEDULED
    assert "quota" in (missed.error or "")


@pytest.mark.asyncio
async def test_a_failed_run_does_not_switch_the_schedule_off(db_session):
    """Причина може бути тимчасовою, а зупинений розклад ніхто не вмикає
    назад. Замість цього росте лічильник."""
    org, site = await _org_with_site(db_session)
    # Одна куплена одиниця: перший запуск нею оплачується, другий уже ні.
    await grant_audit_credits(db_session, organization_id=org, quantity=1)
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.next_run_at = _now() - timedelta(minutes=1)
    await db_session.flush()
    await scheduled.run_all_due(db_session)  # з'їдає єдину куплену одиницю

    record.next_run_at = _now() - timedelta(minutes=1)
    record.claimed_until = None
    await db_session.flush()
    await scheduled.run_all_due(db_session)
    await db_session.refresh(record)

    assert record.enabled is True
    assert record.consecutive_failures == 1
    assert record.last_failure_reason


@pytest.mark.asyncio
async def test_an_archived_site_switches_the_schedule_off_with_a_reason(db_session):
    """Той рідкісний випадок, коли вимкнення правильне: причина назавжди."""
    org, site = await _org_with_site(db_session)
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.next_run_at = _now() - timedelta(minutes=1)
    await sites.archive(db_session, site_id=site, organization_id=org)
    await db_session.flush()

    runs = await scheduled.run_all_due(db_session)
    await db_session.refresh(record)

    assert runs[0].started is False
    assert record.enabled is False
    assert "архів" in record.last_failure_reason


# ── подвійний запуск ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_two_schedulers_never_take_the_same_schedule(postgres_url):
    """Головна перевірка блоку.

    Потрібні справжні паралельні з'єднання: у транзакції фікстури гонки
    не буває, і тест виглядав би зеленим, не перевіривши нічого.
    """
    engine = create_async_engine(postgres_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as setup:
        org, site = await _org_with_site(setup, "race-sched@example.com")
        view = await schedules.create(
            setup, organization_id=org, site_id=site, created_by_user_id=None,
            cadence=Cadence.DAILY,
        )
        record = await setup.get(AuditSchedule, view.id)
        record.next_run_at = _now() - timedelta(minutes=1)
        await setup.commit()

    async def attempt() -> list[schedules.ClaimedOccurrence]:
        async with factory() as session:
            claimed = await schedules.claim_due(session)
            await session.commit()
            return claimed

    try:
        first, second = await asyncio.gather(attempt(), attempt())

        got = [c for c in (first, second) if c]
        assert len(got) == 1, "розклад узяв рівно один планувальник"
        assert [c.schedule_id for c in got[0]] == [view.id]
    finally:
        async with factory() as cleanup:
            for table, column in (
                ("audit_schedules", "organization_id"),
                ("sites", "organization_id"),
                ("memberships", "organization_id"),
            ):
                await cleanup.execute(
                    text(f"DELETE FROM {table} WHERE {column} = :org"), {"org": org}
                )
            await cleanup.execute(text("DELETE FROM users WHERE email = 'race-sched@example.com'"))
            await cleanup.execute(text("DELETE FROM organizations WHERE id = :org"), {"org": org})
            await cleanup.commit()
        await engine.dispose()


@pytest.mark.asyncio
async def test_schedules_of_another_organization_are_invisible(client):
    await register(client, "victim@example.com")
    site = (await client.post("/v1/sites", json={"url": "victim.example"})).json()
    await sign_in_as(client, "attacker@example.com")

    listed = (await client.get("/v1/schedules")).json()
    assert listed == []
    assert (
        await client.post(f"/v1/schedules/{uuid.uuid4()}/disable")
    ).status_code == 404
    assert site  # використано, щоб намір тесту читався


@pytest.mark.asyncio
async def test_re_enabling_does_not_replay_missed_runs(db_session):
    """Розклад, вимкнений на тиждень, не намагається надолужити сім разів."""
    org, site = await _org_with_site(db_session)
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.enabled = False
    record.next_run_at = _now() - timedelta(days=7)
    await db_session.flush()

    updated = await schedules.set_enabled(
        db_session, schedule_id=view.id, organization_id=org, enabled=True
    )

    assert updated.next_run_at > _now()


@pytest.mark.asyncio
async def test_a_schedule_that_keeps_failing_asks_for_attention(db_session):
    org, site = await _org_with_site(db_session)
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )

    for _ in range(schedules.FAILURES_BEFORE_ALARM):
        await schedules.mark_failed(db_session, schedule_id=view.id, reason="квота")

    stored = (
        await db_session.execute(
            select(AuditSchedule).where(AuditSchedule.id == view.id)
        )
    ).scalar_one()
    assert schedules.ScheduleView.of(stored).needs_attention is True
