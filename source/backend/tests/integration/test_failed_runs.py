"""Невдалий запуск лишається записом — і каже, чому.

Порожнє місце в історії читається як «нічого не сталося», хоча сталося
саме те, про що клієнту треба знати. Звідси три вимоги, які тут і
перевіряються: невдача зберігається, вона має клас, і повтор її не
подвоює.

Воркер тут працює справжній, з підміненим лише двигуном аудиту й чергою:
перевіряється не краул, а те, що навколо нього відбувається з грошима,
історією й розкладом.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.application import audits as audits_use_case
from app.application import retries
from app.audit.enums import AuditStatus
from app.audit.fetcher import SiteUnreachable
from app.billing import quota
from app.billing import service as billing
from app.core.run_enums import FailureClass, QuotaState
from app.identity import service as identity
from app.models.audit import Audit, AuditAttempt
from app.models.billing import Subscription
from app.models.scheduling import AuditSchedule
from app.scheduling import service as schedules
from app.scheduling.enums import Cadence
from app.schemas.audit import AuditCreate
from app.sites import service as sites
from app.worker import tasks
from tests.integration.conftest import register

PASSWORD = "correct-horse-battery"


def _now() -> datetime:
    return datetime.now(UTC)


async def _paid_org(db, email: str):
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    plan = await billing.plan_by_code(db, "pro")
    db.add(
        Subscription(
            organization_id=reg.organization.id,
            plan_id=plan.id,
            status="ACTIVE",
            provider="paddle",
            current_period_start=_now() - timedelta(days=1),
            current_period_end=_now() + timedelta(days=29),
        )
    )
    await db.flush()
    return reg.organization.id, reg.user.id


async def _an_audit(db, *, email: str = "runs@example.com", url: str = "https://example.com"):
    org, user = await _paid_org(db, email)
    started = await audits_use_case.start_audit(
        db,
        AuditCreate(url=url),
        organization_id=org,
        created_by_user_id=user,
    )
    await db.flush()
    return org, started.audit.id


def _engine_raises(monkeypatch: pytest.MonkeyPatch, error: BaseException) -> None:
    """Двигун аудиту падає на кожній цілі."""

    async def _boom(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(tasks, "run_audit", _boom)


def _queue_collects(monkeypatch: pytest.MonkeyPatch) -> list[tuple[uuid.UUID, int, int]]:
    put: list[tuple[uuid.UUID, int, int]] = []

    async def _enqueue(audit_id: uuid.UUID, *, attempt: int = 1, delay_s: int = 0) -> None:
        put.append((audit_id, attempt, delay_s))

    monkeypatch.setattr(tasks, "enqueue_audit", _enqueue)
    return put


def _queue_is_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _enqueue(*_a: object, **_k: object) -> None:
        raise ConnectionError("redis недоступний")

    monkeypatch.setattr(tasks, "enqueue_audit", _enqueue)


async def _attempts(db, audit_id: uuid.UUID) -> list[AuditAttempt]:
    stmt = (
        select(AuditAttempt)
        .where(AuditAttempt.audit_id == audit_id)
        .order_by(AuditAttempt.number)
    )
    return list((await db.execute(stmt)).scalars().all())


# ── невдача зберігається й має клас ────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_site_that_does_not_answer_ends_the_run_with_a_reason(
    worker_session, monkeypatch
):
    """Найчастіша невдача продукту. Вона не має виглядати як порожнеча."""
    _, audit_id = await _an_audit(worker_session)
    _engine_raises(monkeypatch, SiteUnreachable("не вдалося завантажити"))
    _queue_collects(monkeypatch)

    await tasks.run_audit_task({}, str(audit_id), 1)
    await tasks.run_audit_task({}, str(audit_id), 2)

    audit = await worker_session.get(Audit, audit_id)
    assert audit.status is AuditStatus.FAILED
    assert audit.failure_class is FailureClass.SITE_UNREACHABLE
    assert audit.error


@pytest.mark.asyncio
async def test_a_site_that_did_not_answer_is_asked_once_more(worker_session, monkeypatch):
    """Тридцять секунд збою хостингу не мають ставати результатом аудиту.

    Повтор тут майже безплатний: недосяжний сайт краулу не коштує. А ціна
    відмови від нього — списана квота й фальшивий провал у кривій.
    """
    _, audit_id = await _an_audit(worker_session, email="norep@example.com")
    _engine_raises(monkeypatch, SiteUnreachable("не вдалося завантажити"))
    put = _queue_collects(monkeypatch)

    await tasks.run_audit_task({}, str(audit_id), 1)
    assert [attempt for _, attempt, _ in put] == [2]

    await tasks.run_audit_task({}, str(audit_id), 2)
    audit = await worker_session.get(Audit, audit_id)
    assert audit.status is AuditStatus.FAILED
    assert audit.quota_state is QuotaState.CONSUMED, "двічі спитали — двічі не відповів"


@pytest.mark.asyncio
async def test_a_site_that_refuses_is_not_asked_again(worker_session, monkeypatch):
    """403 на все — рішення сайту. Повторне питання відрізняє нас від
    скрапера лише наміром, а його ззовні не видно."""
    from app.core.run_enums import FailureClass as _FC

    _, audit_id = await _an_audit(worker_session, email="blocked@example.com")
    put = _queue_collects(monkeypatch)

    async def _blocked(*_a: object, **_k: object) -> None:
        raise RuntimeError("403")

    monkeypatch.setattr(tasks, "run_audit", _blocked)
    monkeypatch.setattr(tasks, "classify", lambda _exc: _FC.SITE_BLOCKED)

    await tasks.run_audit_task({}, str(audit_id), 1)

    assert put == []
    audit = await worker_session.get(Audit, audit_id)
    assert audit.status is AuditStatus.FAILED
    assert audit.failure_class is _FC.SITE_BLOCKED


@pytest.mark.asyncio
async def test_our_own_failure_is_not_charged_to_the_client(worker_session, monkeypatch):
    """Головне, заради чого клас невдачі взагалі існує."""
    org, audit_id = await _an_audit(worker_session, email="ours@example.com")
    _engine_raises(monkeypatch, RuntimeError("вада в нашому коді"))
    _queue_collects(monkeypatch)

    await tasks.run_audit_task({}, str(audit_id), 1)  # перша спроба: буде повтор
    await tasks.run_audit_task({}, str(audit_id), 2)  # друга: остаточно

    audit = await worker_session.get(Audit, audit_id)
    assert audit.status is AuditStatus.FAILED
    assert audit.failure_class is FailureClass.INTERNAL_ERROR
    assert audit.quota_state is QuotaState.RELEASED
    assert await quota.used_in(worker_session, organization_id=org, period=quota.period_for(None)) == 0


# ── повтор — це спроба, а не новий запуск ──────────────────────────────────


@pytest.mark.asyncio
async def test_a_retry_does_not_create_a_second_run(worker_session, monkeypatch):
    org, audit_id = await _an_audit(worker_session, email="onerun@example.com")
    _engine_raises(monkeypatch, RuntimeError("тимчасово"))
    _queue_collects(monkeypatch)

    await tasks.run_audit_task({}, str(audit_id), 1)
    await tasks.run_audit_task({}, str(audit_id), 2)

    audits = (
        (await worker_session.execute(select(Audit).where(Audit.organization_id == org)))
        .scalars()
        .all()
    )
    assert len(audits) == 1
    assert audits[0].attempts == 2


@pytest.mark.asyncio
async def test_the_reserve_waits_while_another_attempt_is_coming(worker_session, monkeypatch):
    """Списати за невдачу, яку самі ж вирішили повторити, — взяти двічі."""
    _, audit_id = await _an_audit(worker_session, email="hold@example.com")
    _engine_raises(monkeypatch, RuntimeError("тимчасово"))
    put = _queue_collects(monkeypatch)

    await tasks.run_audit_task({}, str(audit_id), 1)

    audit = await worker_session.get(Audit, audit_id)
    assert audit.status is AuditStatus.QUEUED, "запуск знову чекає на воркера"
    assert audit.finished_at is None, "він не завершився"
    assert audit.quota_state is QuotaState.RESERVED, "доля резерву ще не вирішена"
    assert put[0][1] == 2, "у чергу пішла саме друга спроба"
    assert put[0][2] == int(retries.backoff(1).total_seconds()), "з паузою з політики"


@pytest.mark.asyncio
async def test_a_queue_that_is_down_does_not_leave_the_run_hanging(worker_session, monkeypatch):
    """Пообіцяти повтор, якого не буде, гірше, ніж не пробувати.

    Аудит лишився б `queued` назавжди — а це стан, з якого ніхто не
    виводить: воркер про нього не дізнається, бо в черзі його немає.
    """
    _, audit_id = await _an_audit(worker_session, email="noqueue@example.com")
    _engine_raises(monkeypatch, RuntimeError("тимчасово"))
    _queue_is_down(monkeypatch)

    await tasks.run_audit_task({}, str(audit_id), 1)

    audit = await worker_session.get(Audit, audit_id)
    assert audit.status is AuditStatus.FAILED
    assert audit.quota_state is QuotaState.RELEASED, "черга — наша інфраструктура"


@pytest.mark.asyncio
async def test_a_finished_run_is_not_restarted_by_a_redelivered_job(worker_session, monkeypatch):
    """Передоставка не має переписувати історичний факт."""
    _, audit_id = await _an_audit(worker_session, email="again@example.com")
    _engine_raises(monkeypatch, SiteUnreachable("не відповів"))
    _queue_collects(monkeypatch)
    await tasks.run_audit_task({}, str(audit_id), 1)
    await tasks.run_audit_task({}, str(audit_id), 2)  # повтор теж не вийшов
    audit = await worker_session.get(Audit, audit_id)
    finished_at = audit.finished_at

    result = await tasks.run_audit_task({}, str(audit_id), 2)

    assert result.get("repeat") is True
    worker_session.expire_all()
    audit = await worker_session.get(Audit, audit_id)
    assert audit.finished_at == finished_at
    assert audit.attempts == 2


# ── журнал спроб ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_log_remembers_why_each_attempt_failed(worker_session, monkeypatch):
    """Дві однакові невдачі й дві різні — різні історії.

    Лічильника для цього не вистачає, і саме тому журнал існує.
    """
    _, audit_id = await _an_audit(worker_session, email="log@example.com")
    _queue_collects(monkeypatch)

    _engine_raises(monkeypatch, RuntimeError("наша вада"))
    await tasks.run_audit_task({}, str(audit_id), 1)
    _engine_raises(monkeypatch, SiteUnreachable("а тепер і сайт"))
    await tasks.run_audit_task({}, str(audit_id), 2)

    log = await _attempts(worker_session, audit_id)
    assert [a.number for a in log] == [1, 2]
    assert log[0].failure_class is FailureClass.INTERNAL_ERROR
    assert log[1].failure_class is FailureClass.SITE_UNREACHABLE
    assert all(a.retry_decision for a in log), "рішення про повтор записане"
    assert all(a.finished_at is not None for a in log)


@pytest.mark.asyncio
async def test_a_redelivered_attempt_does_not_become_a_second_row(worker_session, monkeypatch):
    """Номер спроби приходить у завданні саме заради цього."""
    _, audit_id = await _an_audit(worker_session, email="dup@example.com")
    _engine_raises(monkeypatch, RuntimeError("тимчасово"))
    _queue_collects(monkeypatch)

    await tasks.run_audit_task({}, str(audit_id), 1)
    await tasks.run_audit_task({}, str(audit_id), 1)  # та сама спроба вдруге

    log = await _attempts(worker_session, audit_id)
    assert len(log) == 1


@pytest.mark.asyncio
async def test_a_successful_attempt_leaves_no_trace_of_the_failed_one(
    worker_session, monkeypatch
):
    """Ціль, яка з другого разу вийшла, не має лишатися з текстом першої."""
    _, audit_id = await _an_audit(worker_session, email="recover@example.com")
    _queue_collects(monkeypatch)
    _engine_raises(monkeypatch, RuntimeError("тимчасово"))
    await tasks.run_audit_task({}, str(audit_id), 1)

    outcome = _a_clean_outcome()

    async def _ok(*_a: object, **_k: object):
        return outcome

    monkeypatch.setattr(tasks, "run_audit", _ok)
    await tasks.run_audit_task({}, str(audit_id), 2)

    worker_session.expire_all()
    audit = await worker_session.get(Audit, audit_id)
    assert audit.status is AuditStatus.COMPLETED
    assert audit.failure_class is None
    assert not audit.error
    assert audit.quota_state is QuotaState.CONSUMED
    log = await _attempts(worker_session, audit_id)
    assert [a.status for a in log] == [AuditStatus.FAILED, AuditStatus.COMPLETED]


def _a_clean_outcome():
    """Найдешевший успішний результат: сайт без жодної знахідки."""
    from app.audit.orchestrator import AuditOutcome
    from tests.factories import context, page_from_html

    page = page_from_html("<html><head><title>Так</title></head><body>Текст</body></html>")
    return AuditOutcome(
        context=context(page),
        issues=[],
        scores={"seo": 88},
        overall=88,
        degraded=[],
    )


# ── розклад: лічильник невдач міряє запуски ────────────────────────────────


async def _scheduled_audit(db, email: str):
    org, user = await _paid_org(db, email)
    site = await sites.create(
        db, organization_id=org, url="https://example.com", created_by_user_id=user
    )
    view = await schedules.create(
        db, organization_id=org, site_id=site.id, created_by_user_id=None, cadence=Cadence.DAILY
    )
    started = await audits_use_case.start_audit(
        db,
        AuditCreate(url="https://example.com"),
        organization_id=org,
        created_by_user_id=None,
        site_id=site.id,
        schedule_id=view.id,
        scheduled_for=_now() - timedelta(minutes=1),
    )
    await db.flush()
    return view.id, started.audit.id


@pytest.mark.asyncio
async def test_a_schedule_whose_runs_fail_stops_looking_healthy(worker_session, monkeypatch):
    """Створити запуск і виконати його — різні події.

    Поки лічильник обнулявся на створенні, розклад, аудити якого падають
    щоночі, показував нуль невдач вічно: створювалися вони бездоганно.
    """
    schedule_id, audit_id = await _scheduled_audit(worker_session, "sched@example.com")
    _engine_raises(monkeypatch, SiteUnreachable("не відповів"))
    _queue_collects(monkeypatch)

    await tasks.run_audit_task({}, str(audit_id), 1)
    await tasks.run_audit_task({}, str(audit_id), 2)

    record = await worker_session.get(AuditSchedule, schedule_id)
    assert record.consecutive_failures == 1
    assert record.last_failure_reason


@pytest.mark.asyncio
async def test_retries_of_one_night_count_as_one_failure(worker_session, monkeypatch):
    """Інакше сигнал «потрібна увага» спрацьовував би від однієї ночі."""
    schedule_id, audit_id = await _scheduled_audit(worker_session, "once@example.com")
    _engine_raises(monkeypatch, RuntimeError("наша вада"))
    _queue_collects(monkeypatch)

    await tasks.run_audit_task({}, str(audit_id), 1)
    await tasks.run_audit_task({}, str(audit_id), 2)

    record = await worker_session.get(AuditSchedule, schedule_id)
    assert record.consecutive_failures == 1


@pytest.mark.asyncio
async def test_a_run_that_works_clears_the_alarm(worker_session, monkeypatch):
    schedule_id, audit_id = await _scheduled_audit(worker_session, "back@example.com")
    record = await worker_session.get(AuditSchedule, schedule_id)
    record.consecutive_failures = 4
    record.last_failure_reason = "минулого разу не вийшло"
    await worker_session.flush()

    outcome = _a_clean_outcome()

    async def _ok(*_a: object, **_k: object):
        return outcome

    monkeypatch.setattr(tasks, "run_audit", _ok)
    _queue_collects(monkeypatch)
    await tasks.run_audit_task({}, str(audit_id))

    record = await worker_session.get(AuditSchedule, schedule_id)
    assert record.consecutive_failures == 0
    assert record.last_failure_reason == ""


# ── те саме, але очима клієнта ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_client_sees_why_the_run_failed_and_how_many_times_we_tried(
    client, worker_session, monkeypatch
):
    """Записати причину й не показати її — те саме, що не записати.

    Тест іде через HTTP навмисно: між колонкою й клієнтом стоїть схема
    відповіді, і саме на ній причина губиться найтихіше.
    """
    body = (await register(client, "seen@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    plan = await billing.plan_by_code(worker_session, "pro")
    worker_session.add(
        Subscription(
            organization_id=org,
            plan_id=plan.id,
            status="ACTIVE",
            provider="paddle",
            current_period_start=_now() - timedelta(days=1),
            current_period_end=_now() + timedelta(days=29),
        )
    )
    started = await audits_use_case.start_audit(
        worker_session,
        AuditCreate(url="https://example.com"),
        organization_id=org,
        created_by_user_id=None,
    )
    audit_id = started.audit.id
    await worker_session.flush()

    _queue_collects(monkeypatch)
    _engine_raises(monkeypatch, RuntimeError("наша вада"))
    await tasks.run_audit_task({}, str(audit_id), 1)
    _engine_raises(monkeypatch, SiteUnreachable("а тепер і сайт"))
    await tasks.run_audit_task({}, str(audit_id), 2)

    # У продукті запит приходить у власну сесію й читає базу з нуля. Тут
    # сесія одна на воркер і на клієнта, тож її треба спорожнити — інакше
    # тест перевіряв би кеш SQLAlchemy, а не відповідь.
    worker_session.expire_all()

    seen = (await client.get(f"/v1/audits/{audit_id}")).json()
    assert seen["status"] == AuditStatus.FAILED.value
    assert seen["failure_class"] == FailureClass.SITE_UNREACHABLE.value
    assert seen["attempts"] == 2
    log = seen["attempt_log"]
    assert [a["number"] for a in log] == [1, 2]
    assert log[0]["failure_class"] == FailureClass.INTERNAL_ERROR.value
    assert all(a["retry_decision"] for a in log)
