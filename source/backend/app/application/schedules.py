"""Use case: завести розклад.

Створення розкладу перетинає три контексти — сайти (чи він наш), білінг
(чи дозволяє тариф) і розклади (власне запис). Тому воно тут, а не в
маршруті: інакше ту саму послідовність довелося б повторити в кожному
клієнті, який захоче створити розклад, — а клієнтів буде більше одного.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import service as billing
from app.scheduling import service as schedules
from app.scheduling.enums import Cadence
from app.sites import service as sites


class SiteNotFound(LookupError):
    """Сайт не належить цій організації або не існує."""


class ScheduleNotFound(LookupError):
    """Розклад не належить цій організації або не існує."""


class ScheduleExists(Exception):
    """У сайту вже є розклад.

    Не помилка клієнта в звичайному сенсі: найчастіша причина — повторне
    надсилання тієї самої форми або повтор запиту після таймауту. Тому
    виняток несе **наявний** розклад: інтерфейс має чим відновитися, не
    питаючи вдруге.
    """

    def __init__(self, existing: schedules.ScheduleView) -> None:
        super().__init__(str(existing.id))
        self.existing = existing


async def create_schedule(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    site_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    cadence: Cadence,
    timezone_name: str,
    hour_local: int,
    minute_local: int,
    day_of_week: int | None,
    day_of_month: int | None,
    options: dict[str, Any] | None,
) -> schedules.ScheduleView:
    """Перевірити власність сайту й права, потім створити розклад.

    Порядок той самий, що всюди: спершу «чи це його», потім «чи дозволяє
    тариф». Активна підписка не дає права на чужий сайт.
    """
    site = await sites.get(db, site_id=site_id, organization_id=organization_id)
    if site is None:
        raise SiteNotFound(str(site_id))

    # Один розклад на сайт. Перевірка тут — швидкий шлях для звичайного
    # повтору форми; від гонки двох одночасних запитів боронить не вона,
    # а унікальне обмеження в базі, і його порушення теж перекладається
    # у ту саму відповідь нижче.
    already = await schedules.list_for(
        db, organization_id=organization_id, site_id=site_id
    )
    if already:
        raise ScheduleExists(already[0])

    ent = await billing.for_organization(db, organization_id=organization_id)
    try:
        return await schedules.create(
            db,
            organization_id=organization_id,
            site_id=site_id,
            created_by_user_id=created_by_user_id,
            cadence=cadence,
            timezone_name=timezone_name,
            hour_local=hour_local,
            minute_local=minute_local,
            day_of_week=day_of_week,
            day_of_month=day_of_month,
            options=options,
            limit=ent.limit("scheduled_audits"),
            min_interval_hours=ent.limit("schedule_min_interval_hours"),
        )
    except IntegrityError as exc:
        # Гонка: два запити дійшли до вставки одночасно. Транзакція вже
        # зіпсована, тож відкочуємось до точки збереження й читаємо те,
        # що переміг інший запит.
        await db.rollback()
        existing = await schedules.list_for(
            db, organization_id=organization_id, site_id=site_id
        )
        if not existing:
            raise
        raise ScheduleExists(existing[0]) from exc


async def update_schedule(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    schedule_id: uuid.UUID,
    cadence: Cadence,
    timezone_name: str,
    hour_local: int,
    minute_local: int,
    day_of_week: int | None,
    day_of_month: int | None,
) -> schedules.ScheduleView:
    """Змінити розклад, не втрачаючи його історії.

    Ліміт кількості розкладів тут не перевіряється: він про те, скільки
    їх завести, а не як часто вони спрацьовують. Мінімальний інтервал —
    навпаки, перевіряється: зміна «щомісяця» на «щодня» це саме те, що
    він обмежує.
    """
    record = await schedules.get(
        db, schedule_id=schedule_id, organization_id=organization_id
    )
    if record is None:
        raise ScheduleNotFound(str(schedule_id))

    ent = await billing.for_organization(db, organization_id=organization_id)
    return await schedules.update(
        db,
        record=record,
        cadence=cadence,
        timezone_name=timezone_name,
        hour_local=hour_local,
        minute_local=minute_local,
        day_of_week=day_of_week,
        day_of_month=day_of_month,
        min_interval_hours=ent.limit("schedule_min_interval_hours"),
    )
