"""Перелік сайтів разом із тим, що про них питають першим.

Головне тут — «останній аудит» за створенням, а не за завершенням, і
один розклад на сайт. Обидва правила без бази не перевіряються:
`DISTINCT ON` і унікальне обмеження живуть у PostgreSQL.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from app.application import site_overview
from app.audit.enums import AuditStatus, AuditTrigger
from app.core.run_enums import FailureClass
from app.identity import service as identity
from app.models.audit import Audit
from app.scheduling import service as schedules
from app.scheduling.enums import Cadence
from app.sites import service as sites

PASSWORD = "correct-horse-battery"


async def _org(db, email="overview@example.com"):
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    return reg.organization.id


async def _site(db, org, origin="https://example.com"):
    view = await sites.create(
        db, organization_id=org, url=origin, display_name="", created_by_user_id=None
    )
    await db.flush()
    return view


async def _audit(db, org, site_id, *, created_at, status, score, failure=None):
    audit = Audit(
        organization_id=org,
        site_id=site_id,
        url="https://example.com/",
        origin="https://example.com",
        status=status,
        score_overall=score,
        failure_class=failure,
        options={},
        trigger=AuditTrigger.MANUAL,
        created_at=created_at,
    )
    db.add(audit)
    await db.flush()
    return audit


@pytest.mark.asyncio
async def test_latest_audit_is_the_newest_by_creation_not_by_completion(db_session):
    """Запуск, що триває, і є той, про який хочуть знати.

    За часом завершення найсвіжішим виявився б попередній, уже
    завершений аудит — тобто перелік показував би вчорашній стан саме
    тоді, коли клієнт відкриває його подивитися на сьогоднішній.
    """
    org = await _org(db_session)
    site = await _site(db_session, org)
    now = datetime.now(UTC)

    await _audit(
        db_session, org, site.id,
        created_at=now - timedelta(hours=2),
        status=AuditStatus.COMPLETED, score=71,
    )
    running = await _audit(
        db_session, org, site.id,
        created_at=now, status=AuditStatus.RUNNING, score=None,
    )

    rows = await site_overview.overview(db_session, organization_id=org, sites=[site])

    assert rows[0].latest_audit is not None
    assert rows[0].latest_audit.id == running.id
    assert rows[0].latest_audit.score_overall is None


@pytest.mark.asyncio
async def test_a_blocked_audit_keeps_an_empty_score_and_says_why(db_session):
    """Порожній бал і причина йдуть разом. Нуля тут бути не може."""
    org = await _org(db_session, email="blocked-overview@example.com")
    site = await _site(db_session, org)
    await _audit(
        db_session, org, site.id,
        created_at=datetime.now(UTC),
        status=AuditStatus.FAILED, score=None,
        failure=FailureClass.SITE_UNREACHABLE,
    )

    rows = await site_overview.overview(db_session, organization_id=org, sites=[site])
    latest = rows[0].latest_audit

    assert latest is not None
    assert latest.score_overall is None
    assert latest.failure_class is FailureClass.SITE_UNREACHABLE


@pytest.mark.asyncio
async def test_a_site_without_audits_has_no_latest(db_session):
    org = await _org(db_session, email="fresh-overview@example.com")
    site = await _site(db_session, org)

    rows = await site_overview.overview(db_session, organization_id=org, sites=[site])

    assert rows[0].latest_audit is None
    assert rows[0].schedule is None


@pytest.mark.asyncio
async def test_a_site_cannot_have_two_schedules(db_session):
    """Повторне надсилання форми не має створювати другий розклад.

    Два розклади на сайт — не гнучкість, а два джерела правди: людина
    бачить «щотижня», а запуски приходять щодня.
    """
    org = await _org(db_session, email="dup-schedule@example.com")
    site = await _site(db_session, org)

    # Через контекст розкладів, а не через use case: дефолтні права
    # забороняють розклади взагалі (нуль штук), і перевірка прав
    # спрацювала б раніше за те, що ми тут перевіряємо.
    async def make():
        return await schedules.create(
            db_session,
            organization_id=org,
            site_id=site.id,
            created_by_user_id=None,
            cadence=Cadence.MONTHLY,
            timezone_name="Europe/Kyiv",
            hour_local=9,
            minute_local=0,
            day_of_month=1,
        )

    await make()
    # Точка збереження: порушення обмеження ламає транзакцію, і без неї
    # сесія лишається непридатною для решти тесту. Той самий прийом, що
    # в прийманні подій білінгу.
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await make()
            await db_session.flush()


@pytest.mark.asyncio
async def test_updating_a_schedule_keeps_its_history(db_session):
    """Зміна часу не має скидати лічильник невдач і час останнього запуску.

    Видалити й створити заново було б простіше — і втратило б причину,
    чому розклад просить уваги.
    """
    org = await _org(db_session, email="edit-schedule@example.com")
    site = await _site(db_session, org)
    created = await schedules.create(
        db_session,
        organization_id=org,
        site_id=site.id,
        created_by_user_id=None,
        cadence=Cadence.MONTHLY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
        minute_local=0,
        day_of_month=1,
    )
    record = await schedules.get(
        db_session, schedule_id=created.id, organization_id=org
    )
    assert record is not None
    record.consecutive_failures = 3
    record.last_run_at = datetime.now(UTC)
    await db_session.flush()

    updated = await schedules.update(
        db_session,
        record=record,
        cadence=Cadence.MONTHLY,
        timezone_name="America/Chicago",
        hour_local=6,
        minute_local=30,
        day_of_month=15,
    )

    assert updated.id == created.id
    assert updated.cadence is Cadence.MONTHLY
    assert updated.timezone == "America/Chicago"
    assert updated.next_run_at is not None
    # Історія на місці: розклад той самий, лише правило інше.
    again = await schedules.get(db_session, schedule_id=created.id, organization_id=org)
    assert again is not None
    assert again.consecutive_failures == 3
    assert again.last_run_at is not None


@pytest.mark.asyncio
async def test_creating_a_schedule_twice_returns_the_existing_one(db_session):
    """Повторне надсилання форми — нормальна послідовність, не помилка.

    Сирий IntegrityError назовні дав би 500 на дію, яку користувач
    робить регулярно: подвійний клік, повтор після таймауту, ретрай
    клієнта. Замість цього — типізований результат із наявним розкладом,
    щоб інтерфейс міг відновитися, не питаючи вдруге.
    """
    from app.application import schedules as use_case
    from app.models.billing import EntitlementOverride

    org = await _org(db_session, email="retry-schedule@example.com")
    site = await _site(db_session, org)
    # Права за замовчуванням забороняють розклади зовсім; тут перевіряємо
    # не їх, а поведінку при повторі.
    for key, value in (("scheduled_audits", 5), ("schedule_min_interval_hours", 24)):
        db_session.add(
            EntitlementOverride(
                organization_id=org,
                key=key,
                value={"value": value},
                # Причина обовʼязкова: індивідуальний виняток без пояснення
                # через півроку неможливо ані підтвердити, ані скасувати.
                reason="тест повторного створення розкладу",
            )
        )
    await db_session.flush()

    async def make():
        return await use_case.create_schedule(
            db_session,
            organization_id=org,
            site_id=site.id,
            created_by_user_id=None,
            cadence=Cadence.WEEKLY,
            timezone_name="Europe/Kyiv",
            hour_local=9,
            minute_local=0,
            day_of_week=0,
            day_of_month=None,
            options=None,
        )

    first = await make()
    with pytest.raises(use_case.ScheduleExists) as caught:
        await make()

    # Наявний розклад приходить у самому винятку: клієнту не треба
    # робити ще один запит, щоб дізнатися, що в нього вже є.
    assert caught.value.existing.id == first.id
    # Історія не загубилась: другий запис не створювався.
    all_for_site = await schedules.list_for(
        db_session, organization_id=org, site_id=site.id
    )
    assert len(all_for_site) == 1
