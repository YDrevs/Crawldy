"""Фасад контексту розкладів для шару API.

Прості операції — перелік, вимкнення, видалення — не перетинають
контекстів, і продуктовий шар не додає до них нічого. Але маршрут не має
імпортувати контекст напряму: сьогодні там простий виклик, завтра
з'явиться перевірка права, і додати її треба буде в одному місці, а не в
кожному клієнті.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.scheduling import service
from app.scheduling.enums import Cadence
from app.scheduling.service import (
    InvalidSchedule,
    ScheduleLimitReached,
    ScheduleView,
    TooFrequent,
    UnknownTimezone,
)


async def list_schedules_for(
    db: AsyncSession, *, organization_id: uuid.UUID, site_id: uuid.UUID | None = None
) -> list[ScheduleView]:
    return await service.list_for(db, organization_id=organization_id, site_id=site_id)


async def set_schedule_enabled(
    db: AsyncSession, *, schedule_id: uuid.UUID, organization_id: uuid.UUID, enabled: bool
) -> ScheduleView | None:
    return await service.set_enabled(
        db, schedule_id=schedule_id, organization_id=organization_id, enabled=enabled
    )


async def remove_schedule(
    db: AsyncSession, *, schedule_id: uuid.UUID, organization_id: uuid.UUID
) -> bool:
    return await service.delete(db, schedule_id=schedule_id, organization_id=organization_id)


__all__ = [
    "Cadence",
    "InvalidSchedule",
    "ScheduleLimitReached",
    "ScheduleView",
    "TooFrequent",
    "UnknownTimezone",
    "list_schedules_for",
    "remove_schedule",
    "set_schedule_enabled",
]
