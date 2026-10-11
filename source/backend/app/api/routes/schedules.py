"""Розклади організації."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import ActorDep, AdminDep, SessionDep
from app.application import schedules as use_case
from app.application.schedule_views import (
    Cadence,
    InvalidSchedule,
    ScheduleLimitReached,
    ScheduleView,
    TooFrequent,
    UnknownTimezone,
    list_schedules_for,
    remove_schedule,
    set_schedule_enabled,
)

router = APIRouter(prefix="/v1/schedules", tags=["schedules"])


class ScheduleCreateIn(BaseModel):
    site_id: uuid.UUID
    cadence: Cadence
    timezone: str = Field(default="UTC", max_length=64)
    hour_local: int = Field(default=9, ge=0, le=23)
    minute_local: int = Field(default=0, ge=0, le=59)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)
    options: dict = Field(default_factory=dict)


class ScheduleUpdateIn(BaseModel):
    """Зміна розкладу. Сайт не міняється: це вже інший розклад."""

    cadence: Cadence
    timezone: str = Field(default="UTC", max_length=64)
    hour_local: int = Field(default=9, ge=0, le=23)
    minute_local: int = Field(default=0, ge=0, le=59)
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    day_of_month: int | None = Field(default=None, ge=1, le=31)


class ScheduleOut(BaseModel):
    id: uuid.UUID
    site_id: uuid.UUID
    cadence: Cadence
    timezone: str
    hour_local: int
    minute_local: int
    day_of_week: int | None
    day_of_month: int | None
    enabled: bool
    next_run_at: str | None
    last_run_at: str | None
    consecutive_failures: int
    last_failure_reason: str
    # Розклад не мовчить про свої невдачі: тихо зламаний виглядає для
    # клієнта так само, як робочий.
    needs_attention: bool


def _out(view: ScheduleView) -> ScheduleOut:
    return ScheduleOut(
        id=view.id,
        site_id=view.site_id,
        cadence=view.cadence,
        timezone=view.timezone,
        hour_local=view.hour_local,
        minute_local=view.minute_local,
        day_of_week=view.day_of_week,
        day_of_month=view.day_of_month,
        enabled=view.enabled,
        next_run_at=view.next_run_at.isoformat() if view.next_run_at else None,
        last_run_at=view.last_run_at.isoformat() if view.last_run_at else None,
        consecutive_failures=view.consecutive_failures,
        last_failure_reason=view.last_failure_reason,
        needs_attention=view.needs_attention,
    )


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
async def create_schedule(
    payload: ScheduleCreateIn, actor: AdminDep, db: SessionDep
) -> ScheduleOut:
    """Новий розклад. Права перевіряються тут, а не в контексті розкладів."""
    try:
        view = await use_case.create_schedule(
            db,
            organization_id=actor.organization_id,
            site_id=payload.site_id,
            created_by_user_id=actor.user_id,
            cadence=payload.cadence,
            timezone_name=payload.timezone,
            hour_local=payload.hour_local,
            minute_local=payload.minute_local,
            day_of_week=payload.day_of_week,
            day_of_month=payload.day_of_month,
            options=payload.options,
        )
    except use_case.SiteNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="сайт не знайдено"
        ) from exc
    except use_case.ScheduleExists as exc:
        # 409 із **наявним** розкладом у тілі. Найчастіша причина —
        # повторне надсилання форми або повтор після таймауту, і клієнт
        # має чим відновитися, не питаючи вдруге. Сирий IntegrityError
        # тут дав би 500 на нормальну послідовність дій.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "ScheduleExists",
                "schedule": _out(exc.existing).model_dump(mode="json"),
            },
        ) from exc
    except (ScheduleLimitReached, TooFrequent) as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"reason": type(exc).__name__, "detail": str(exc)},
        ) from exc
    except (InvalidSchedule, UnknownTimezone) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    await db.commit()
    return _out(view)


@router.get("", response_model=list[ScheduleOut])
async def list_schedules(
    actor: ActorDep, db: SessionDep, site_id: uuid.UUID | None = None
) -> list[ScheduleOut]:
    views = await list_schedules_for(
        db, organization_id=actor.organization_id, site_id=site_id
    )
    return [_out(v) for v in views]


@router.patch("/{schedule_id}", response_model=ScheduleOut)
async def update_schedule(
    schedule_id: uuid.UUID,
    payload: ScheduleUpdateIn,
    actor: AdminDep,
    db: SessionDep,
) -> ScheduleOut:
    """Змінити час, частоту або пояс наявного розкладу.

    Не «видалити й створити»: у розкладу є історія запусків і лічильник
    невдач, і перестворення втратило б причину, чому він просить уваги.
    """
    try:
        view = await use_case.update_schedule(
            db,
            organization_id=actor.organization_id,
            schedule_id=schedule_id,
            cadence=payload.cadence,
            timezone_name=payload.timezone,
            hour_local=payload.hour_local,
            minute_local=payload.minute_local,
            day_of_week=payload.day_of_week,
            day_of_month=payload.day_of_month,
        )
    except use_case.ScheduleNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="розклад не знайдено"
        ) from exc
    except TooFrequent as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"reason": type(exc).__name__, "detail": str(exc)},
        ) from exc
    except (InvalidSchedule, UnknownTimezone) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    await db.commit()
    return _out(view)


@router.post("/{schedule_id}/enable", response_model=ScheduleOut)
async def enable_schedule(schedule_id: uuid.UUID, actor: AdminDep, db: SessionDep) -> ScheduleOut:
    """Увімкнути. Наступний запуск рахується від зараз, а не надолужується."""
    view = await set_schedule_enabled(
        db, schedule_id=schedule_id, organization_id=actor.organization_id, enabled=True
    )
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    await db.commit()
    return _out(view)


@router.post("/{schedule_id}/disable", response_model=ScheduleOut)
async def disable_schedule(schedule_id: uuid.UUID, actor: AdminDep, db: SessionDep) -> ScheduleOut:
    view = await set_schedule_enabled(
        db, schedule_id=schedule_id, organization_id=actor.organization_id, enabled=False
    )
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    await db.commit()
    return _out(view)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_schedule(schedule_id: uuid.UUID, actor: AdminDep, db: SessionDep) -> Response:
    removed = await remove_schedule(
        db, schedule_id=schedule_id, organization_id=actor.organization_id
    )
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
