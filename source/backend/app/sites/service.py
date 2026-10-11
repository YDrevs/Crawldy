"""Операції над сайтами організації.

Кожен запит фільтрується за організацією **в SQL**, а не після вибірки.
Різниця не стилістична: фільтр після вибірки легко забути, і тоді чужий
ідентифікатор дає чужі дані. Фільтр у запиті забути неможливо — його
відсутність видно в самому рядку.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sites import Site, SiteMerge
from app.sites.identity import display_name_for, normalize_origin


class SiteExists(ValueError):
    """Такий origin в організації вже є."""


class SiteLimitReached(ValueError):
    """Тариф не дозволяє більше сайтів."""


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class SiteView:
    """Що контекст віддає назовні. Не ORM-об'єкт."""

    id: uuid.UUID
    organization_id: uuid.UUID
    origin: str
    display_name: str
    resolved_origin: str | None
    created_at: datetime
    archived_at: datetime | None

    @classmethod
    def of(cls, record: Site) -> SiteView:
        return cls(
            id=record.id,
            organization_id=record.organization_id,
            origin=record.origin,
            display_name=record.display_name,
            resolved_origin=record.resolved_origin,
            created_at=record.created_at,
            archived_at=record.archived_at,
        )

    @property
    def redirects_elsewhere(self) -> bool:
        """Сайт привів не туди, куди його оголосили.

        Підстава запитати людину про об'єднання — і тільки. Ми не знаємо,
        чи це той самий сайт: `example.com` може редиректити на
        `shop.example.com`, і це два різні сайти з одним власником.
        """
        return self.resolved_origin is not None and self.resolved_origin != self.origin


async def create(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    url: str,
    created_by_user_id: uuid.UUID | None,
    display_name: str = "",
    limit: int | None = None,
) -> SiteView:
    """Новий сайт. `url` нормалізується до origin, решта адреси відкидається.

    `limit` приходить із прав тарифу — контекст сайтів сам про тарифи не
    знає й знати не повинен.
    """
    origin = normalize_origin(url)

    if limit is not None:
        used = await count_active(db, organization_id=organization_id)
        if used >= limit:
            raise SiteLimitReached(f"{used}/{limit}")

    existing = await find_by_origin(db, organization_id=organization_id, origin=origin)
    if existing is not None:
        raise SiteExists(origin)

    record = Site(
        organization_id=organization_id,
        origin=origin,
        display_name=(display_name.strip() or display_name_for(origin))[:200],
        created_by_user_id=created_by_user_id,
    )
    db.add(record)
    await db.flush()
    return SiteView.of(record)


async def find_by_origin(
    db: AsyncSession, *, organization_id: uuid.UUID, origin: str
) -> Site | None:
    stmt = select(Site).where(Site.organization_id == organization_id, Site.origin == origin)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get(db: AsyncSession, *, site_id: uuid.UUID, organization_id: uuid.UUID) -> Site | None:
    """Сайт організації або None.

    Організація — частина умови, а не перевірка після. Чужий сайт для
    того, хто питає, просто не існує.
    """
    stmt = select(Site).where(Site.id == site_id, Site.organization_id == organization_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def list_for(
    db: AsyncSession, *, organization_id: uuid.UUID, include_archived: bool = False
) -> list[SiteView]:
    stmt = select(Site).where(Site.organization_id == organization_id)
    if not include_archived:
        stmt = stmt.where(Site.archived_at.is_(None))
    stmt = stmt.order_by(Site.created_at)
    return [SiteView.of(r) for r in (await db.execute(stmt)).scalars().all()]


async def count_active(db: AsyncSession, *, organization_id: uuid.UUID) -> int:
    stmt = select(func.count(Site.id)).where(
        Site.organization_id == organization_id, Site.archived_at.is_(None)
    )
    return int((await db.execute(stmt)).scalar_one())


async def archive(db: AsyncSession, *, site_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
    """Архівація, не видалення: аудити лишаються історією організації."""
    record = await get(db, site_id=site_id, organization_id=organization_id)
    if record is None or record.archived_at is not None:
        return False
    record.archived_at = _now()
    return True


async def rename(
    db: AsyncSession, *, site_id: uuid.UUID, organization_id: uuid.UUID, display_name: str
) -> SiteView | None:
    """Змінити можна підпис, але не `origin`.

    Origin — це ідентичність, на якій тримається історія. Змінити його
    означало б переписати минуле: криву, зібрану для одного сайту,
    видати за криву іншого.
    """
    record = await get(db, site_id=site_id, organization_id=organization_id)
    if record is None:
        return None
    record.display_name = display_name.strip()[:200] or display_name_for(record.origin)
    return SiteView.of(record)


async def note_resolved_origin(
    db: AsyncSession, *, site_id: uuid.UUID, resolved: str
) -> None:
    """Куди сайт привів після редиректів. Викликає воркер після аудиту.

    Тільки запис факту. Жодного об'єднання, жодної зміни `origin`.
    """
    record = await db.get(Site, site_id)
    if record is None:
        return
    try:
        record.resolved_origin = normalize_origin(resolved)
    except ValueError:
        record.resolved_origin = None


class CannotMerge(ValueError):
    """Об'єднання неможливе: не той власник, той самий сайт, немає запису."""


@dataclass(frozen=True, slots=True)
class MergeResult:
    source_origin: str
    target_origin: str
    audits_moved: int


async def merge(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    source_site_id: uuid.UUID,
    target_site_id: uuid.UUID,
    reason: str,
    performed_by_user_id: uuid.UUID | None = None,
) -> MergeResult:
    """Перевести аудити одного сайту під інший.

    Змінюється рівно одне поле кожного аудиту — `site_id`, тобто
    організаційне групування. Виміряний факт не чіпається взагалі: ні
    адреса, яку читав аудит, ні опції, ні бали, ні знімок, ні версії, ні
    часові мітки. Саме тому об'єднання можливе без переписування минулого.

    Ніколи не викликається автоматично. Схожість адрес — підстава
    **запитати людину**, а не злити: `example.com` може редиректити на
    `shop.example.com`, і це два різні сайти з одним власником.

    Причина обов'язкова: через рік питання «чому ці аудити належать
    іншому сайту» має мати відповідь у базі, а не в чиїйсь пам'яті.
    """
    if source_site_id == target_site_id:
        raise CannotMerge("сайт не об'єднується сам із собою")
    if not reason.strip():
        raise CannotMerge("об'єднання без причини не виконується")

    source = await get(db, site_id=source_site_id, organization_id=organization_id)
    target = await get(db, site_id=target_site_id, organization_id=organization_id)
    if source is None or target is None:
        raise CannotMerge("сайт не знайдено")

    # Оновлення одним запитом і рівно однієї колонки: усе, що можна
    # зачепити випадково, до нього просто не входить.
    moved = await db.execute(
        text(
            "UPDATE audits SET site_id = :target "
            " WHERE site_id = :source AND organization_id = :org "
            "RETURNING id"
        ),
        {"target": target_site_id, "source": source_site_id, "org": organization_id},
    )
    # RETURNING, а не rowcount: перше типізується, друге існує лише на
    # курсорі конкретного драйвера.
    audits_moved = len(moved.fetchall())

    db.add(
        SiteMerge(
            organization_id=organization_id,
            source_site_id=source_site_id,
            target_site_id=target_site_id,
            source_origin=source.origin,
            target_origin=target.origin,
            audits_moved=audits_moved,
            reason=reason.strip(),
            performed_by_user_id=performed_by_user_id,
        )
    )
    # Джерело архівується, а не видаляється: його адреса лишається
    # зайнятою, і повторне додавання не створить дубля мовчки.
    source.archived_at = _now()
    await db.flush()

    return MergeResult(
        source_origin=source.origin, target_origin=target.origin, audits_moved=audits_moved
    )


async def merges_of(db: AsyncSession, *, organization_id: uuid.UUID) -> list[SiteMerge]:
    stmt = (
        select(SiteMerge)
        .where(SiteMerge.organization_id == organization_id)
        .order_by(SiteMerge.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())
