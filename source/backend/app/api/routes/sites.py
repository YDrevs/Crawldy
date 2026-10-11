"""Сайти організації.

Кожен маршрут отримує організацію з контексту автентифікації, а не з
запиту. Чужий сайт віддає 404, а не 403: відповідь «доступ заборонено»
підтверджує, що ресурс існує.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import ActorDep, AdminDep, SessionDep
from app.application import site_overview
from app.application.visibility import history_window
from app.audit.enums import AuditStatus
from app.core.run_enums import FailureClass
from app.report.history import needs_recompute, timeline
from app.schemas.history import SiteHistoryOut
from app.services import audit_service
from app.sites import service
from app.sites.identity import InvalidSiteUrl

router = APIRouter(prefix="/v1/sites", tags=["sites"])


class SiteCreateIn(BaseModel):
    url: str = Field(min_length=3, max_length=2048)
    display_name: str = Field(default="", max_length=200)


class SiteRenameIn(BaseModel):
    display_name: str = Field(default="", max_length=200)


class LatestAuditOut(BaseModel):
    """Останній запуск сайту — стільки, скільки треба переліку.

    Бал буває порожнім не лише в невдалого аудиту: сайт, що не пустив
    краулер, теж не має числа. Тому поруч завжди статус і клас невдачі —
    щоб інтерфейс сказав, **чому** бала немає, а не намалював нуль.
    """

    id: uuid.UUID
    status: AuditStatus
    score_overall: int | None
    failure_class: FailureClass | None
    created_at: str
    finished_at: str | None


class ScheduleSummaryOut(BaseModel):
    """Розклад сайту у двох словах. Повний — у переліку розкладів."""

    id: uuid.UUID
    enabled: bool
    next_run_at: str | None
    needs_attention: bool


class SiteOut(BaseModel):
    id: uuid.UUID
    origin: str
    display_name: str
    resolved_origin: str | None
    # Сайт привів не туди, куди його оголосили. Підстава запитати людину
    # про об'єднання — і тільки: `example.com` може редиректити на
    # `shop.example.com`, і це два різні сайти з одним власником.
    redirects_elsewhere: bool
    created_at: str
    archived_at: str | None

    # Порожні там, де сайт віддається сам по собі — після створення чи
    # перейменування. У переліку й на сторінці сайту заповнені: саме про
    # них питають, відкриваючи екран.
    latest_audit: LatestAuditOut | None = None
    schedule: ScheduleSummaryOut | None = None


def _out(
    view: service.SiteView,
    *,
    latest: site_overview.LatestAudit | None = None,
    schedule: site_overview.ScheduleSummary | None = None,
) -> SiteOut:
    return SiteOut(
        id=view.id,
        origin=view.origin,
        display_name=view.display_name,
        resolved_origin=view.resolved_origin,
        redirects_elsewhere=view.redirects_elsewhere,
        latest_audit=(
            LatestAuditOut(
                id=latest.id,
                status=latest.status,
                score_overall=latest.score_overall,
                failure_class=latest.failure_class,
                created_at=latest.created_at.isoformat(),
                finished_at=latest.finished_at.isoformat() if latest.finished_at else None,
            )
            if latest is not None
            else None
        ),
        schedule=(
            ScheduleSummaryOut(
                id=schedule.id,
                enabled=schedule.enabled,
                next_run_at=schedule.next_run_at.isoformat() if schedule.next_run_at else None,
                needs_attention=schedule.needs_attention,
            )
            if schedule is not None
            else None
        ),
        created_at=view.created_at.isoformat(),
        archived_at=view.archived_at.isoformat() if view.archived_at else None,
    )


@router.post("", response_model=SiteOut, status_code=status.HTTP_201_CREATED)
async def create_site(payload: SiteCreateIn, actor: AdminDep, db: SessionDep) -> SiteOut:
    """Новий сайт. Адреса зводиться до origin, решта відкидається."""
    try:
        view = await service.create(
            db,
            organization_id=actor.organization_id,
            url=payload.url,
            created_by_user_id=actor.user_id,
            display_name=payload.display_name,
        )
    except InvalidSiteUrl as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except service.SiteExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="такий сайт уже додано"
        ) from exc
    await db.commit()
    return _out(view)


@router.get("", response_model=list[SiteOut])
async def list_sites(
    actor: ActorDep, db: SessionDep, include_archived: bool = False
) -> list[SiteOut]:
    views = await service.list_for(
        db, organization_id=actor.organization_id, include_archived=include_archived
    )
    rows = await site_overview.overview(
        db, organization_id=actor.organization_id, sites=views
    )
    return [_out(r.site, latest=r.latest_audit, schedule=r.schedule) for r in rows]


@router.get("/{site_id}", response_model=SiteOut)
async def get_site(site_id: uuid.UUID, actor: ActorDep, db: SessionDep) -> SiteOut:
    record = await service.get(db, site_id=site_id, organization_id=actor.organization_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    view = service.SiteView.of(record)
    rows = await site_overview.overview(
        db, organization_id=actor.organization_id, sites=[view]
    )
    row = rows[0]
    return _out(row.site, latest=row.latest_audit, schedule=row.schedule)


@router.patch("/{site_id}", response_model=SiteOut)
async def rename_site(
    site_id: uuid.UUID, payload: SiteRenameIn, actor: AdminDep, db: SessionDep
) -> SiteOut:
    """Змінити можна підпис, але не `origin`.

    Origin — ідентичність, на якій тримається історія. Змінити його
    означало б криву, зібрану для одного сайту, видати за криву іншого.
    """
    view = await service.rename(
        db,
        site_id=site_id,
        organization_id=actor.organization_id,
        display_name=payload.display_name,
    )
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    await db.commit()
    return _out(view)


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_site(site_id: uuid.UUID, actor: AdminDep, db: SessionDep) -> Response:
    """Архівація, не видалення: аудити лишаються історією організації."""
    archived = await service.archive(
        db, site_id=site_id, organization_id=actor.organization_id
    )
    if not archived:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{site_id}/history", response_model=SiteHistoryOut)
async def site_history(
    site_id: uuid.UUID, actor: ActorDep, db: SessionDep, limit: int = 50
) -> dict[str, object]:
    """Історія балів сайту з позначками, де порівняння недійсне.

    Ключем є сайт, а не рядок адреси. Це різні речі: `Site` — бізнес-
    ресурс організації, який вона завела й за який платить; origin —
    адреса, за якою він зараз відповідає. Прив'язка історії до адреси
    означала б, що переїзд на інший хост розриває криву, а об'єднання
    двох записів вимагає переписування минулого.

    Тепер об'єднання — це переведення `audits.site_id`: аудити, їхні
    origin і бали лишаються недоторканими.
    """
    record = await service.get(db, site_id=site_id, organization_id=actor.organization_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")

    window = await history_window(db, organization_id=actor.organization_id)
    points = await audit_service.score_history_for_site(
        db,
        site_id=site_id,
        organization_id=actor.organization_id,
        limit=limit,
        since=window.since,
    )
    steps = timeline(points)
    return {
        "site": {"id": str(record.id), "origin": record.origin, "name": record.display_name},
        "visible_days": window.days,
        "points": [p.to_json() for p in points],
        "steps": [s.to_json() for s in steps],
        "incomparable_steps": sum(1 for s in steps if not s.comparable),
        "fixable_by_recompute": len(needs_recompute(steps)),
    }
