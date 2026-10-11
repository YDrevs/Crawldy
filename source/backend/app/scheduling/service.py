"""Операції над розкладами й захоплення тих, яким час.

Захист від подвійного запуску живе в базі, а не в черзі. Черга —
інфраструктура: вона може передоставити повідомлення, її можна
перезапустити, її дедуплікація залежить від того, чи не сплив ключ. База
дає оренду, і другий екземпляр планувальника просто не побачить рядка.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scheduling import AuditSchedule
from app.scheduling.enums import Cadence
from app.scheduling.next_run import UnknownTimezone, compute, interval_hours, zone

# Скільки триває оренда захопленого розкладу.
#
# Довше за найповільніший аудит бути не мусить: якщо процес помер, рядок
# має звільнитися сам, а не чекати ручного втручання. Коротше за час
# створення запуску — теж ні, інакше два планувальники візьмуть один
# розклад.
CLAIM_LEASE = timedelta(minutes=10)

# Після скількох невдач поспіль розклад позначається проблемним.
#
# Не вимикається: тихо вимкнений розклад виглядає для клієнта так само,
# як робочий, і про це дізнаються через місяць порожньої історії.
FAILURES_BEFORE_ALARM = 5


class ScheduleLimitReached(ValueError):
    """Тариф не дозволяє більше активних розкладів."""


class TooFrequent(ValueError):
    """Тариф не дозволяє такої частоти."""


class InvalidSchedule(ValueError):
    """Опис розкладу суперечливий."""


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class ScheduleView:
    id: uuid.UUID
    site_id: uuid.UUID
    cadence: Cadence
    timezone: str
    hour_local: int
    minute_local: int
    day_of_week: int | None
    day_of_month: int | None
    enabled: bool
    next_run_at: datetime | None
    last_run_at: datetime | None
    consecutive_failures: int
    last_failure_reason: str

    @classmethod
    def of(cls, record: AuditSchedule) -> ScheduleView:
        return cls(
            id=record.id,
            site_id=record.site_id,
            cadence=record.cadence,
            timezone=record.timezone,
            hour_local=record.hour_local,
            minute_local=record.minute_local,
            day_of_week=record.day_of_week,
            day_of_month=record.day_of_month,
            enabled=record.enabled,
            next_run_at=record.next_run_at,
            last_run_at=record.last_run_at,
            consecutive_failures=record.consecutive_failures,
            last_failure_reason=record.last_failure_reason,
        )

    @property
    def needs_attention(self) -> bool:
        """Розклад не мовчить про свої невдачі."""
        return self.consecutive_failures >= FAILURES_BEFORE_ALARM


def _validate(
    *,
    cadence: Cadence,
    timezone_name: str,
    hour: int,
    minute: int,
    dow: int | None,
    dom: int | None,
) -> None:
    zone(timezone_name)  # кидає UnknownTimezone
    if not 0 <= hour <= 23:
        raise InvalidSchedule("година поза межами доби")
    if not 0 <= minute <= 59:
        raise InvalidSchedule("хвилина поза межами години")
    if cadence is Cadence.WEEKLY and dow is not None and not 0 <= dow <= 6:
        raise InvalidSchedule("день тижня поза межами")
    if cadence is Cadence.MONTHLY and dom is not None and not 1 <= dom <= 31:
        raise InvalidSchedule("день місяця поза межами")


async def create(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    site_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    cadence: Cadence,
    timezone_name: str = "UTC",
    hour_local: int = 9,
    minute_local: int = 0,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
    options: dict[str, Any] | None = None,
    limit: int | None = None,
    min_interval_hours: int | None = None,
) -> ScheduleView:
    """Новий розклад. Ліміти приходять із прав — контекст про тарифи не знає."""
    _validate(
        cadence=cadence,
        timezone_name=timezone_name,
        hour=hour_local,
        minute=minute_local,
        dow=day_of_week,
        dom=day_of_month,
    )
    if min_interval_hours is not None and interval_hours(cadence) < min_interval_hours:
        raise TooFrequent(f"{cadence.value} частіше за дозволені {min_interval_hours} год")
    if limit is not None:
        used = await count_enabled(db, organization_id=organization_id)
        if used >= limit:
            raise ScheduleLimitReached(f"{used}/{limit}")

    record = AuditSchedule(
        organization_id=organization_id,
        site_id=site_id,
        created_by_user_id=created_by_user_id,
        cadence=cadence,
        timezone=timezone_name,
        hour_local=hour_local,
        minute_local=minute_local,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        options=options or {},
    )
    record.next_run_at = _next_for(record, after=_now())
    db.add(record)
    await db.flush()
    return ScheduleView.of(record)


def _next_for(record: AuditSchedule, *, after: datetime) -> datetime:
    return compute(
        cadence=record.cadence,
        timezone_name=record.timezone,
        hour_local=record.hour_local,
        minute_local=record.minute_local,
        day_of_week=record.day_of_week,
        day_of_month=record.day_of_month,
        after=after,
    )


async def get(
    db: AsyncSession, *, schedule_id: uuid.UUID, organization_id: uuid.UUID
) -> AuditSchedule | None:
    stmt = select(AuditSchedule).where(
        AuditSchedule.id == schedule_id, AuditSchedule.organization_id == organization_id
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_for(
    db: AsyncSession, *, organization_id: uuid.UUID, site_id: uuid.UUID | None = None
) -> list[ScheduleView]:
    stmt = select(AuditSchedule).where(AuditSchedule.organization_id == organization_id)
    if site_id is not None:
        stmt = stmt.where(AuditSchedule.site_id == site_id)
    stmt = stmt.order_by(AuditSchedule.created_at)
    return [ScheduleView.of(r) for r in (await db.execute(stmt)).scalars().all()]


async def count_enabled(db: AsyncSession, *, organization_id: uuid.UUID) -> int:
    stmt = select(func.count(AuditSchedule.id)).where(
        AuditSchedule.organization_id == organization_id, AuditSchedule.enabled.is_(True)
    )
    return int((await db.execute(stmt)).scalar_one())


async def update(
    db: AsyncSession,
    *,
    record: AuditSchedule,
    cadence: Cadence,
    timezone_name: str,
    hour_local: int,
    minute_local: int,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
    min_interval_hours: int | None = None,
) -> ScheduleView:
    """Змінити наявний розклад.

    Окремо від видалення й створення заново навмисно: у розкладу є
    історія запусків і лічильник невдач, і перестворення втратило б їх
    разом із причиною, чому він просить уваги.

    Наступний запуск перераховується тут, а не в інтерфейсі: локальний
    час, часовий пояс і перехід на літній час — усе це вже вміє
    `compute`, і другий такий обчислювач у браузері розійшовся б із ним
    двічі на рік.
    """
    _validate(
        cadence=cadence,
        timezone_name=timezone_name,
        hour=hour_local,
        minute=minute_local,
        dow=day_of_week,
        dom=day_of_month,
    )
    if min_interval_hours is not None and interval_hours(cadence) < min_interval_hours:
        raise TooFrequent(f"{cadence.value} частіше за дозволені {min_interval_hours} год")

    record.cadence = cadence
    record.timezone = timezone_name
    record.hour_local = hour_local
    record.minute_local = minute_local
    record.day_of_week = day_of_week
    record.day_of_month = day_of_month
    record.next_run_at = _next_for(record, after=_now())
    await db.flush()
    return ScheduleView.of(record)


async def set_enabled(
    db: AsyncSession, *, schedule_id: uuid.UUID, organization_id: uuid.UUID, enabled: bool
) -> ScheduleView | None:
    record = await get(db, schedule_id=schedule_id, organization_id=organization_id)
    if record is None:
        return None
    record.enabled = enabled
    if enabled:
        # Увімкнений після паузи розклад не має спрацювати негайно за всі
        # пропущені рази: наступний запуск рахується від зараз.
        record.next_run_at = _next_for(record, after=_now())
        record.consecutive_failures = 0
        record.last_failure_reason = ""
    await db.flush()
    return ScheduleView.of(record)


async def delete(
    db: AsyncSession, *, schedule_id: uuid.UUID, organization_id: uuid.UUID
) -> bool:
    record = await get(db, schedule_id=schedule_id, organization_id=organization_id)
    if record is None:
        return False
    await db.delete(record)
    await db.flush()
    return True


# ── захоплення тих, яким час ───────────────────────────────────────────────

# Один запит, у якому живе весь захист від подвійного запуску.
#
# `FOR UPDATE SKIP LOCKED` — щоб другий планувальник не чекав на першому,
# а просто взяв інші рядки. Оренда (`claimed_until`) — щоб рядок
# звільнився сам, якщо процес помер між захопленням і запуском.
_CLAIM = text(
    """
    UPDATE audit_schedules
       SET claimed_until = :lease_until
     WHERE id IN (
        SELECT id FROM audit_schedules
         WHERE enabled
           AND next_run_at IS NOT NULL
           AND next_run_at <= :now
           AND (claimed_until IS NULL OR claimed_until < :now)
         ORDER BY next_run_at
         FOR UPDATE SKIP LOCKED
         LIMIT :batch)
    RETURNING id, next_run_at
    """
)


@dataclass(frozen=True, slots=True)
class ClaimedOccurrence:
    """Захоплений розклад і **момент**, на який він спрацював.

    Момент — частина відповіді, а не деталь: саме він разом із розкладом
    дає стабільний ключ входження. Без нього повторне захоплення після
    простроченої оренди створило б другий запис про ту саму дев'яту ранку.

    Абсолютний момент у UTC. Локальними є правила розкладу; те, у що вони
    розв'язалися, локальним бути не може — інакше його неможливо
    порівняти з `now()`.
    """

    schedule_id: uuid.UUID
    scheduled_for: datetime


async def claim_due(
    db: AsyncSession, *, now: datetime | None = None, batch: int = 20
) -> list[ClaimedOccurrence]:
    """Захопити розклади, яким час, разом із моментом входження.

    Захоплення й запуск — два кроки навмисно: між ними може впасти
    процес, і тоді оренда мине сама. Якби вони були одним кроком,
    відновлення вимагало б ручного розбору.
    """
    moment = now or _now()
    rows = await db.execute(
        _CLAIM, {"now": moment, "lease_until": moment + CLAIM_LEASE, "batch": batch}
    )
    claimed = [
        ClaimedOccurrence(schedule_id=row[0], scheduled_for=row[1]) for row in rows.fetchall()
    ]

    # Сирий UPDATE обходить ORM: об'єкти, які вже лежать у сесії,
    # лишаються зі старим `claimed_until`, і подальше `record.claimed_until
    # = None` не породжує жодного запиту — воно ж «не змінює» значення.
    # Наслідок був би тихим: оренда лишалася б у базі до кінця строку, і
    # розклад мовчки пропускав би наступні кілька запусків.
    if claimed:
        db.expire_all()
    return claimed


async def mark_started(
    db: AsyncSession, *, schedule_id: uuid.UUID, now: datetime | None = None
) -> None:
    """Запуск створено: посунути наступний час і зняти оренду.

    Лічильник невдач тут **не** обнуляється, і це не пропуск. Створений
    запуск — ще не виконаний: розклад, аудити якого падають щоночі,
    показував би нуль невдач вічно, бо створювалися вони бездоганно.
    Обнуляє його `note_outcome`, коли запуск справді дійшов до результату.

    Ідентифікатора аудиту тут немає навмисно: зв'язок тримає сам аудит
    (`audits.schedule_id`, `audits.scheduled_for`), і другий бік цього
    зв'язку розійшовся б із першим після чистки за строком утримання.

    Наступний час рахується від **моменту запуску**, а не від
    попереднього `next_run_at`. Різниця видно після простою: розклад, що
    не працював тиждень, не намагається надолужити сім запусків.
    """
    record = await db.get(AuditSchedule, schedule_id)
    if record is None:
        return
    moment = now or _now()
    record.last_run_at = moment
    record.next_run_at = _next_for(record, after=moment)
    record.claimed_until = None
    await db.flush()


async def mark_failed(
    db: AsyncSession, *, schedule_id: uuid.UUID, reason: str, now: datetime | None = None
) -> None:
    """Запуск не створено: порахувати невдачу й усе одно посунути час.

    Розклад не зупиняється: причина може бути тимчасовою (вичерпана
    квота цього місяця, недоступна черга), а зупинений розклад ніхто не
    вмикає назад. Замість цього росте лічильник, і при
    `FAILURES_BEFORE_ALARM` розклад просить уваги.
    """
    record = await db.get(AuditSchedule, schedule_id)
    if record is None:
        return
    moment = now or _now()
    record.consecutive_failures += 1
    record.last_failure_reason = reason[:500]
    record.next_run_at = _next_for(record, after=moment)
    record.claimed_until = None
    await db.flush()


async def note_outcome(
    db: AsyncSession, *, schedule_id: uuid.UUID, ok: bool, reason: str = ""
) -> None:
    """Чим скінчився запуск розкладу.

    Це і є те, що клієнт називає «розклад працює». Створення запуску до
    цього питання стосунку не має: аудит міг бути створений і не дійти до
    результату жодного разу.

    Викликається лише на **остаточному** результаті — після повтору, який
    не вийшов, а не після кожної невдалої спроби. Інакше три повтори
    одного входження рахувалися б трьома невдачами розкладу, і сигнал
    «потрібна увага» спрацьовував би від однієї поганої ночі.
    """
    record = await db.get(AuditSchedule, schedule_id)
    if record is None:
        return
    if ok:
        record.consecutive_failures = 0
        record.last_failure_reason = ""
    else:
        record.consecutive_failures += 1
        record.last_failure_reason = reason[:500]
    await db.flush()


async def release(db: AsyncSession, *, schedule_id: uuid.UUID) -> None:
    """Зняти оренду, не міняючи розкладу. Для скасування без запуску."""
    record = await db.get(AuditSchedule, schedule_id)
    if record is not None:
        record.claimed_until = None
        await db.flush()


__all__ = [
    "CLAIM_LEASE",
    "FAILURES_BEFORE_ALARM",
    "ClaimedOccurrence",
    "InvalidSchedule",
    "ScheduleLimitReached",
    "ScheduleView",
    "TooFrequent",
    "UnknownTimezone",
    "claim_due",
    "count_enabled",
    "create",
    "delete",
    "get",
    "list_for",
    "mark_failed",
    "mark_started",
    "note_outcome",
    "release",
    "set_enabled",
]
