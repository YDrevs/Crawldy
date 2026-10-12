"""Публічні посилання на звіт.

Ендпоінт віддає чужий звіт без API-ключа, тож тут кілька свідомих рішень:

- токен 256 біт із secrets.token_urlsafe — не вгадується перебором;
- у базі лежить лише SHA-256, відкритий токен існує один раз у відповіді;
- пошук іде по хешу, тобто по унікальному індексу, а не порівнянням рядків;
- строк життя обовʼязковий для поділених посилань; платний доступ
  безстроковий і закінчується лише відкликанням;
- прострочене й відкликане не відрізняються ззовні — обидва дають 404.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import ReportLink

TOKEN_BYTES = 32
DEFAULT_TTL_DAYS = 14
MAX_TTL_DAYS = 90


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def create_link(
    session: AsyncSession,
    audit_id: uuid.UUID,
    *,
    target_id: uuid.UUID | None = None,
    # Без дефолту навмисно: мова посилання — рішення викликача, і
    # службовий шар не має власної думки про неї. Два різні дефолти в
    # двох шарах уже одного разу зійшлися лише випадково.
    lang: str,
    ttl_days: int | None = DEFAULT_TTL_DAYS,
    unlock_id: uuid.UUID | None = None,
) -> tuple[ReportLink, str]:
    """Повертає (запис, відкритий токен). Токен більше ніде не зʼявиться.

    `ttl_days=None` — безстрокове посилання. Дозволено лише платному
    доступу (`unlock_id` заповнений): звичайне поділене посилання має
    строк, бо ним діляться з чужими людьми, а платне — це власний доступ
    покупця до купленого, і закінчуватися календарем воно не має.
    """
    if ttl_days is None and unlock_id is None:
        raise ValueError("безстрокове посилання існує лише для оплаченого доступу")
    expires_at = None
    if ttl_days is not None:
        ttl = max(1, min(ttl_days, MAX_TTL_DAYS))
        expires_at = datetime.now(UTC) + timedelta(days=ttl)
    token = secrets.token_urlsafe(TOKEN_BYTES)
    link = ReportLink(
        audit_id=audit_id,
        target_id=target_id,
        token_hash=hash_token(token),
        lang=lang,
        expires_at=expires_at,
        unlock_id=unlock_id,
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link, token


async def resolve(session: AsyncSession, token: str) -> ReportLink | None:
    """Активне посилання за токеном. Прострочене й відкликане — None."""
    stmt = select(ReportLink).where(ReportLink.token_hash == hash_token(token))
    link = (await session.scalars(stmt)).first()
    if link is None or not link.is_active:
        return None

    link.views += 1
    link.last_seen_at = datetime.now(UTC)
    await session.commit()
    return link


async def list_links(session: AsyncSession, audit_id: uuid.UUID) -> list[ReportLink]:
    stmt = (
        select(ReportLink)
        .where(ReportLink.audit_id == audit_id)
        .order_by(ReportLink.created_at.desc())
    )
    return list((await session.scalars(stmt)).all())


async def revoke(
    session: AsyncSession, audit_id: uuid.UUID, link_id: uuid.UUID
) -> ReportLink | None:
    """Відкликає посилання саме цього аудиту; чуже — None, без запису."""
    link = await session.get(ReportLink, link_id)
    if link is None or link.audit_id != audit_id:
        return None
    if link.revoked_at is None:
        link.revoked_at = datetime.now(UTC)
        await session.commit()
    return link


__all__ = ["create_link", "hash_token", "list_links", "resolve", "revoke"]
