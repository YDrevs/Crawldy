"""Один запланований момент — рівно один запуск.

Прострочена оренда, перезапуск планувальника, повторна доставка в чергу —
усе це нові *спроби* того самого запуску, а не нові запуски. Другий
історичний запис про ту саму дев'яту ранку означав би два аудити там, де
був один, і крива показувала б подію, якої не було.

Тут же перевіряється друга половина інваріанта часу: локальними є
**правила** розкладу, а моменти виконання — абсолютні в UTC.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.application import scheduled
from app.audit.enums import AuditStatus
from app.billing import quota
from app.billing import service as billing
from app.identity import service as identity
from app.models.audit import Audit
from app.models.billing import Subscription
from app.models.scheduling import AuditSchedule
from app.scheduling import service as schedules
from app.scheduling.enums import Cadence
from app.sites import service as sites

PASSWORD = "correct-horse-battery"


def _now() -> datetime:
    return datetime.now(UTC)


async def _org_with_site(db, email: str, origin: str = "https://example.com"):
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    site = await sites.create(
        db, organization_id=reg.organization.id, url=origin, created_by_user_id=reg.user.id
    )
    return reg.organization.id, site.id


async def _paid_org_with_due_schedule(db, email: str = "occ@example.com"):
    """Організація з тарифом, сайтом і розкладом, якому вже час."""
    org, site = await _org_with_site(db, email)
    plan = await billing.plan_by_code(db, "pro")
    db.add(
        Subscription(
            organization_id=org,
            plan_id=plan.id,
            status="ACTIVE",
            provider="paddle",
            current_period_start=_now() - timedelta(days=1),
            current_period_end=_now() + timedelta(days=29),
        )
    )
    view = await schedules.create(
        db, organization_id=org, site_id=site, created_by_user_id=None, cadence=Cadence.DAILY
    )
    record = await db.get(AuditSchedule, view.id)
    due_at = _now() - timedelta(minutes=1)
    record.next_run_at = due_at
    await db.flush()
    return org, site, view.id, due_at


@pytest.mark.asyncio
async def test_the_run_remembers_which_occurrence_it_is(db_session):
    _, _, schedule_id, due_at = await _paid_org_with_due_schedule(db_session)

    runs = await scheduled.run_all_due(db_session)

    audit = await db_session.get(Audit, runs[0].audit_id)
    assert audit.schedule_id == schedule_id
    assert audit.scheduled_for == due_at
    assert audit.attempts == 1


@pytest.mark.asyncio
async def test_claiming_the_same_occurrence_again_does_not_create_a_second_run(db_session):
    """Головна перевірка інваріанта."""
    _, _, schedule_id, due_at = await _paid_org_with_due_schedule(db_session)

    first = await scheduled.run_all_due(db_session)

    # Оренда минула, і момент знову виглядає як той, якому час.
    record = await db_session.get(AuditSchedule, schedule_id)
    record.next_run_at = due_at
    record.claimed_until = None
    await db_session.flush()
    second = await scheduled.run_all_due(db_session)

    assert second[0].reused is True
    assert second[0].audit_id == first[0].audit_id

    audits = (
        (await db_session.execute(select(Audit).where(Audit.schedule_id == schedule_id)))
        .scalars()
        .all()
    )
    assert len(audits) == 1, "один запланований момент — один запуск"
    assert audits[0].attempts == 2, "повтор — спроба, а не новий аудит"


@pytest.mark.asyncio
async def test_a_repeat_does_not_consume_quota_twice(db_session):
    """Повтор не має коштувати клієнту вдруге."""
    org, _, schedule_id, due_at = await _paid_org_with_due_schedule(db_session)

    await scheduled.run_all_due(db_session)
    after_first = await quota.used_in(
        db_session, organization_id=org, period=quota.period_for(None)
    )

    record = await db_session.get(AuditSchedule, schedule_id)
    record.next_run_at = due_at
    record.claimed_until = None
    await db_session.flush()
    await scheduled.run_all_due(db_session)

    after_second = await quota.used_in(
        db_session, organization_id=org, period=quota.period_for(None)
    )
    assert after_second == after_first


@pytest.mark.asyncio
async def test_a_different_occurrence_is_a_different_run(db_session):
    """Ідемпотентність не має злипати різні моменти в один запис."""
    _, _, schedule_id, _ = await _paid_org_with_due_schedule(db_session)

    await scheduled.run_all_due(db_session)

    record = await db_session.get(AuditSchedule, schedule_id)
    record.next_run_at = _now() - timedelta(seconds=1)  # інший момент
    record.claimed_until = None
    await db_session.flush()
    await scheduled.run_all_due(db_session)

    audits = (
        (await db_session.execute(select(Audit).where(Audit.schedule_id == schedule_id)))
        .scalars()
        .all()
    )
    assert len(audits) == 2
    assert len({a.scheduled_for for a in audits}) == 2


@pytest.mark.asyncio
async def test_the_database_refuses_a_duplicate_occurrence(db_session):
    """Перевірка в коді не переживе двох планувальників послідовно."""
    org, site, schedule_id, due_at = await _paid_org_with_due_schedule(db_session)
    await scheduled.run_all_due(db_session)

    async with db_session.begin_nested():
        db_session.add(
            Audit(
                organization_id=org,
                site_id=site,
                schedule_id=schedule_id,
                scheduled_for=due_at,
                url="https://example.com/",
                origin="https://example.com",
                status=AuditStatus.QUEUED,
                options={},
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_manual_audits_never_collide(db_session):
    """Обмеження часткове: у ручних аудитів немає моменту входження, і
    два таких записи мусять співіснувати."""
    org, site = await _org_with_site(db_session, "manual@example.com")

    for _ in range(2):
        db_session.add(
            Audit(
                organization_id=org,
                site_id=site,
                url="https://example.com/",
                origin="https://example.com",
                status=AuditStatus.QUEUED,
                options={},
            )
        )
    await db_session.flush()

    audits = (
        (await db_session.execute(select(Audit).where(Audit.organization_id == org)))
        .scalars()
        .all()
    )
    assert len(audits) == 2


@pytest.mark.asyncio
async def test_skipped_is_not_failed(db_session):
    """«Не виконувався, бо тариф» і «зламався» — різні відповіді клієнту."""
    org, site = await _org_with_site(db_session, "skip@example.com")  # без підписки
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.next_run_at = _now() - timedelta(minutes=1)
    await db_session.flush()
    await scheduled.run_all_due(db_session)  # з'їдає єдиний аудит місяця

    record = await db_session.get(AuditSchedule, view.id)
    record.next_run_at = _now() - timedelta(seconds=30)
    record.claimed_until = None
    await db_session.flush()
    runs = await scheduled.run_all_due(db_session)

    skipped = await db_session.get(Audit, runs[0].audit_id)
    assert skipped.status is AuditStatus.SKIPPED
    assert skipped.status.was_executed is False
    assert AuditStatus.FAILED.was_executed is True


# ── час: абсолютні моменти в UTC ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_execution_timestamps_come_back_as_absolute_utc(db_session):
    """Локальними є **правила** розкладу, а не моменти виконання.

    Момент, у який правила розв'язалися, мусить бути абсолютним: інакше
    його неможливо порівняти ні з `now()`, ні з моментом іншого розкладу
    в іншій зоні.
    """
    org, site = await _org_with_site(db_session, "tz@example.com")
    view = await schedules.create(
        db_session,
        organization_id=org,
        site_id=site,
        created_by_user_id=None,
        cadence=Cadence.DAILY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
    )
    record = await db_session.get(AuditSchedule, view.id)
    record.claimed_until = _now() + timedelta(minutes=5)
    record.last_run_at = _now()
    await db_session.flush()
    db_session.expire_all()

    fresh = await db_session.get(AuditSchedule, view.id)
    for field in ("next_run_at", "claimed_until", "last_run_at"):
        value = getattr(fresh, field)
        assert value is not None, field
        assert value.tzinfo is not None, f"{field} без зони"
        assert value.utcoffset() == timedelta(0), f"{field} не в UTC"


@pytest.mark.asyncio
async def test_the_same_local_hour_in_two_zones_is_two_different_instants(db_session):
    """Правила однакові, моменти різні — і саме моменти лежать у базі."""
    org_a, site_a = await _org_with_site(db_session, "kyiv@example.com", "https://a.example")
    org_b, site_b = await _org_with_site(db_session, "ny@example.com", "https://b.example")

    kyiv = await schedules.create(
        db_session, organization_id=org_a, site_id=site_a, created_by_user_id=None,
        cadence=Cadence.DAILY, timezone_name="Europe/Kyiv", hour_local=9,
    )
    new_york = await schedules.create(
        db_session, organization_id=org_b, site_id=site_b, created_by_user_id=None,
        cadence=Cadence.DAILY, timezone_name="America/New_York", hour_local=9,
    )

    assert kyiv.next_run_at != new_york.next_run_at
    assert abs((kyiv.next_run_at - new_york.next_run_at).total_seconds()) >= 6 * 3600


@pytest.mark.asyncio
async def test_a_future_occurrence_is_not_claimed(db_session):
    """Порівняння робиться в базі над timestamptz.

    Якби десь загубилася зона, розклад у далекій зоні спрацював би на
    кілька годин раніше часу.
    """
    org, site = await _org_with_site(db_session, "offset@example.com")
    view = await schedules.create(
        db_session, organization_id=org, site_id=site, created_by_user_id=None,
        cadence=Cadence.DAILY, timezone_name="Pacific/Kiritimati", hour_local=9,
    )

    assert view.next_run_at > _now()
    assert await schedules.claim_due(db_session) == [], "майбутнє не захоплюється"


@pytest.mark.asyncio
async def test_the_audit_records_the_occurrence_as_utc(db_session):
    *_, due_at = await _paid_org_with_due_schedule(db_session, "utcrun@example.com")

    runs = await scheduled.run_all_due(db_session)
    db_session.expire_all()

    audit = await db_session.get(Audit, runs[0].audit_id)
    assert audit.scheduled_for.tzinfo is not None
    assert audit.scheduled_for.utcoffset() == timedelta(0)
    assert audit.scheduled_for == due_at
