"""Сайти разом із тим, що про них питають першим.

## Чому не три запити з інтерфейсу

Перелік сайтів без останнього аудиту марний: людина заходить подивитися,
як почуваються її сайти, а не перелічити їхні адреси. Зібрати це на
клієнті означало б витягти всі аудити й усі розклади, зіставити їх за
`site_id` і вирішити, який із них «останній», — тобто відтворити в
браузері правило, яке вже є на бекенді.

Гірше, що правило «останній» неочевидне: за часом створення, а не за
часом завершення. Аудит, що почався пізніше й досі виконується, — саме
той, про який хочуть знати, хоча `finished_at` у нього порожній.

## Один запит на всі сайти, а не запит на кожен

`DISTINCT ON` бере по одному найсвіжішому рядку на сайт за один прохід.
Обхід сайтів із запитом на кожен дає N+1 і виглядає нормально рівно
доти, доки в клієнта не зʼявиться тридцять сайтів.

## Покриття тут немає навмисно

Скільки сторінок прочитано, зберігається лише звʼязком `audit.pages`, і
порахувати це для переліку означало б витягти всі сторінки всіх аудитів.
Стан вимірювання перелік передає інакше — статусом, порожнім балом і
класом невдачі, — а точні числа живуть на екрані звіту, де вони й
потрібні.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.enums import AuditStatus
from app.core.run_enums import FailureClass
from app.models.audit import Audit
from app.models.scheduling import AuditSchedule
from app.sites.service import SiteView


@dataclass(frozen=True, slots=True)
class LatestAudit:
    """Останній запуск сайту — рівно те, що видно в переліку.

    `score_overall` порожній не лише в невдалого аудиту: сайт, який не
    пустив краулер, теж не має бала. Тому поруч завжди йде `status` і
    `failure_class` — щоб інтерфейс міг сказати, **чому** числа немає,
    замість того щоб намалювати нуль.
    """

    id: uuid.UUID
    status: AuditStatus
    score_overall: int | None
    failure_class: FailureClass | None
    created_at: datetime
    finished_at: datetime | None


@dataclass(frozen=True, slots=True)
class ScheduleSummary:
    """Розклад сайту у двох словах: коли наступного разу й чи все гаразд."""

    id: uuid.UUID
    enabled: bool
    next_run_at: datetime | None
    needs_attention: bool


@dataclass(frozen=True, slots=True)
class SiteOverview:
    site: SiteView
    latest_audit: LatestAudit | None
    schedule: ScheduleSummary | None


async def _latest_audits(
    db: AsyncSession, *, organization_id: uuid.UUID
) -> dict[uuid.UUID, LatestAudit]:
    # Найсвіжіший **за створенням**: запуск, який ще виконується, — саме
    # той, про який хочуть знати, хоча завершення в нього немає.
    stmt = (
        select(Audit)
        .where(
            Audit.organization_id == organization_id,
            Audit.site_id.is_not(None),
        )
        .distinct(Audit.site_id)
        .order_by(Audit.site_id, Audit.created_at.desc())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {
        row.site_id: LatestAudit(
            id=row.id,
            status=row.status,
            score_overall=row.score_overall,
            failure_class=row.failure_class,
            created_at=row.created_at,
            finished_at=row.finished_at,
        )
        for row in rows
        if row.site_id is not None
    }


async def _schedules(
    db: AsyncSession, *, organization_id: uuid.UUID
) -> dict[uuid.UUID, ScheduleSummary]:
    stmt = select(AuditSchedule).where(
        AuditSchedule.organization_id == organization_id
    )
    rows = (await db.execute(stmt)).scalars().all()
    return {
        row.site_id: ScheduleSummary(
            id=row.id,
            enabled=row.enabled,
            next_run_at=row.next_run_at,
            # Те саме правило, що в перегляді розкладів: тихо зламаний
            # розклад виглядає для клієнта так само, як робочий.
            needs_attention=row.enabled and row.consecutive_failures > 0,
        )
        for row in rows
    }


async def overview(
    db: AsyncSession, *, organization_id: uuid.UUID, sites: list[SiteView]
) -> list[SiteOverview]:
    """Сайти з останнім аудитом і станом розкладу. Три запити, не 2N+1."""
    if not sites:
        return []
    latest = await _latest_audits(db, organization_id=organization_id)
    schedules = await _schedules(db, organization_id=organization_id)
    return [
        SiteOverview(
            site=site,
            latest_audit=latest.get(site.id),
            schedule=schedules.get(site.id),
        )
        for site in sites
    ]


__all__ = ["LatestAudit", "ScheduleSummary", "SiteOverview", "overview"]
