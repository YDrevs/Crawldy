"""Use case: виконати те, чому настав час.

Планувальник не знає ні про квоти, ні про тарифи, ні про чергу — він
лише каже «цим розкладам час, ось на який момент». Що з цього виходить,
вирішується тут, і порядок той самий, що й для ручного запуску: права,
квота, обрізання, запис, черга.

Дві відмінності принципові.

**Один запланований момент — рівно один запуск.** Ключ входження
(`schedule_id`, `scheduled_for`) робить створення ідемпотентним:
прострочена оренда, перезапуск планувальника, повторна доставка в чергу —
усе це нові *спроби* того самого запуску, а не нові запуски. Інакше крива
історії показувала б два аудити там, де була одна дев'ята ранку.

**Невдача теж стає записом.** Історія має показувати

    успішний → успішний → квоту вичерпано → успішний

а не діру між третім і четвертим. Порожнє місце читається як «нічого не
сталося», хоча сталося саме те, про що клієнту треба знати. При цьому
«пропущено» і «зламалося» — різні статуси: перше не варто повторювати до
нового періоду, друге варто.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import audits as audits_use_case
from app.audit.enums import AuditStatus, AuditTrigger
from app.core.run_enums import FailureClass
from app.models.audit import Audit
from app.models.scheduling import AuditSchedule
from app.scheduling import service as schedules
from app.scheduling.service import ClaimedOccurrence
from app.schemas.audit import AuditCreate
from app.sites import service as sites


@dataclass(frozen=True, slots=True)
class ScheduledRun:
    """Що вийшло з одного входження.

    `audit_id` порожній лише тоді, коли не вдалося створити навіть запис —
    тобто коли розкладу або сайту вже немає.

    `reused` каже, що запис для цього моменту вже існував: повторне
    захоплення нічого не створило й нічого не списало.
    """

    schedule_id: uuid.UUID
    scheduled_for: datetime
    audit_id: uuid.UUID | None
    started: bool
    reused: bool = False
    reason: str = ""


def _now() -> datetime:
    return datetime.now(UTC)


async def _existing_occurrence(
    db: AsyncSession, *, schedule_id: uuid.UUID, scheduled_for: datetime
) -> Audit | None:
    """Запис, уже створений для цього моменту.

    Перевірка перед вставкою не замінює обмеження в базі — вона лише
    робить звичайний шлях без винятків. Гонку ловить унікальний індекс.
    """
    stmt = select(Audit).where(
        Audit.schedule_id == schedule_id, Audit.scheduled_for == scheduled_for
    )
    return (await db.execute(stmt)).scalars().first()


async def run_occurrence(db: AsyncSession, occurrence: ClaimedOccurrence) -> ScheduledRun:
    """Створити (або знайти) запуск для захопленого входження.

    Викликається після `claim_due`, тобто оренда вже наша. Що б тут не
    сталося, оренда знімається: розклад, який лишився захопленим після
    падіння, мовчки пропускає запуски до кінця оренди.
    """
    schedule_id, moment = occurrence.schedule_id, occurrence.scheduled_for

    already = await _existing_occurrence(db, schedule_id=schedule_id, scheduled_for=moment)
    if already is not None:
        # Повторне захоплення того самого моменту. Квота не списується
        # вдруге, історія не подвоюється; лишається порахувати спробу.
        already.attempts += 1
        already.last_attempt_at = _now()
        await schedules.mark_started(db, schedule_id=schedule_id)
        return ScheduledRun(
            schedule_id=schedule_id,
            scheduled_for=moment,
            audit_id=already.id,
            started=already.status is AuditStatus.QUEUED,
            reused=True,
            reason="цей момент уже має запуск",
        )

    record = await db.get(AuditSchedule, schedule_id)
    if record is None:
        return ScheduledRun(
            schedule_id=schedule_id, scheduled_for=moment, audit_id=None, started=False,
            reason="розкладу вже немає",
        )

    site = await sites.get(db, site_id=record.site_id, organization_id=record.organization_id)
    if site is None or site.archived_at is not None:
        # Той рідкісний випадок, коли вимкнення правильне: причина
        # назавжди, і мовчазним воно не є — вона записана.
        record.enabled = False
        record.last_failure_reason = "сайт заархівовано або видалено"
        record.claimed_until = None
        await db.flush()
        return ScheduledRun(
            schedule_id=schedule_id, scheduled_for=moment, audit_id=None, started=False,
            reason="сайт заархівовано",
        )

    payload = AuditCreate(url=site.origin, options=record.options or {})

    try:
        started = await audits_use_case.start_audit(
            db,
            payload,
            organization_id=record.organization_id,
            created_by_user_id=None,
            trigger=AuditTrigger.SCHEDULED,
            site_id=record.site_id,
            schedule_id=schedule_id,
            scheduled_for=moment,
        )
    except audits_use_case.NotAllowed as exc:
        skipped = await _record_skip(db, record, moment=moment, reason=exc.reason)
        await schedules.mark_failed(db, schedule_id=schedule_id, reason=exc.reason)
        return ScheduledRun(
            schedule_id=schedule_id,
            scheduled_for=moment,
            audit_id=skipped.id,
            started=False,
            reason=exc.reason,
        )

    started.audit.attempts = 1
    started.audit.last_attempt_at = _now()
    await schedules.mark_started(db, schedule_id=schedule_id)
    return ScheduledRun(
        schedule_id=schedule_id,
        scheduled_for=moment,
        audit_id=started.audit.id,
        started=True,
    )


async def _record_skip(
    db: AsyncSession, record: AuditSchedule, *, moment: datetime, reason: str
) -> Audit:
    """Записати пропущене входження як факт історії.

    Статус `SKIPPED`, а не `FAILED`: виконання не починалося, і сказати
    клієнту «зламалося» там, де правильна відповідь «вичерпано», означає
    відповісти не на те питання. Від цього ж залежить, чи є сенс
    повторювати: скасоване квотою повторювати нема чого до нового періоду.

    Квота не резервується — її ж і не вистачило.
    """
    from app.services import audit_service

    audit = await audit_service.create_audit(
        db,
        AuditCreate(url=(record.site.origin if record.site else "https://example.invalid")),
        organization_id=record.organization_id,
        site_id=record.site_id,
        created_by_user_id=None,
        trigger=AuditTrigger.SCHEDULED,
        schedule_id=record.id,
        scheduled_for=moment,
    )
    audit.status = AuditStatus.SKIPPED
    audit.error = reason
    audit.failure_class = FailureClass.CANCELLED
    audit.attempts = 1
    audit.last_attempt_at = _now()
    audit.finished_at = _now()
    await db.flush()
    return audit


async def run_all_due(
    db: AsyncSession, *, now: datetime | None = None, batch: int = 20
) -> list[ScheduledRun]:
    """Захопити те, чому час, і створити запуски.

    Захоплення й виконання розділені: між ними може впасти процес, і
    тоді оренда мине сама. Одним кроком це вимагало б ручного розбору.
    """
    claimed = await schedules.claim_due(db, now=now, batch=batch)
    return [await run_occurrence(db, occurrence) for occurrence in claimed]
