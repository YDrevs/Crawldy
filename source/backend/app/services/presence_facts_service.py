"""Пропозиція фактів прогону присутності — зі збереженого аудиту.

Тонкий перехідник між рядками бази й чистим `presence.derive`: сам
висновок не знає ані ORM, ані сесій, і перевіряється без бази. Тут
лише збирається вхід: знання про сайт із доказів аудиту (для аудитів,
старших за це поле, — порожньо) і заголовок та мова головної сторінки.

Пропозиція — не істина. Вона показується людині з можливістю змінити,
і саме змінене йде в прогін.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.enums import AuditStatus
from app.models.audit import Audit, AuditPage
from app.presence.derive import DerivedFacts, derive

# Стани, у яких аудит прочитав сайт і має що запропонувати.
READABLE = (AuditStatus.COMPLETED, AuditStatus.PARTIAL)


async def _home_page(session: AsyncSession, audit: Audit) -> AuditPage | None:
    """Головна сторінка аудиту: глибина 0, а без неї — перша прочитана."""
    rows = list(await session.scalars(
        select(AuditPage)
        .where(AuditPage.audit_id == audit.id)
        .order_by(AuditPage.depth.asc())
        .limit(5)
    ))
    for page in rows:
        if page.url.rstrip("/") == audit.url.rstrip("/"):
            return page
    return rows[0] if rows else None


async def suggest_for_audit(session: AsyncSession, audit: Audit) -> DerivedFacts:
    """Факти для форми прогону з того, що цей аудит прочитав."""
    facts: dict[str, Any] = (audit.evidence or {}).get("site_facts") or {}
    home = await _home_page(session, audit)
    raw: dict[str, Any] = (home.raw or {}) if home is not None else {}
    return derive(
        origin=audit.origin,
        home_title=str(raw.get("title") or ""),
        organization=str(facts.get("organization") or ""),
        cities=tuple(str(c) for c in facts.get("cities") or []),
        schema_types={
            str(k): int(v) for k, v in (facts.get("schema_types") or {}).items()
        },
        lang=str(raw.get("lang") or ""),
    )


async def latest_readable_audit(
    session: AsyncSession, *, organization_id: uuid.UUID, origin: str
) -> Audit | None:
    """Останній прочитаний аудит цього сайту в організації."""
    return await session.scalar(
        select(Audit)
        .where(
            Audit.organization_id == organization_id,
            Audit.origin == origin,
            Audit.status.in_(READABLE),
        )
        .order_by(Audit.created_at.desc())
        .limit(1)
    )


__all__ = ["READABLE", "latest_readable_audit", "suggest_for_audit"]
