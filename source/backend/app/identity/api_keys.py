"""Ключі API організації.

Замінюють глобальний `settings.api_keys` — один спільний секрет процесу,
який неможливо ні видати комусь окремо, ні відкликати, ні порахувати.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity.service import hash_token
from app.models.identity import ApiKey

# Впізнаваний префікс: знайшовши такий рядок у чужому репозиторії чи в
# логах, і людина, і автоматичний сканер секретів розуміють, що це.
PREFIX = "cwd_"
SECRET_BYTES = 32
# Скільки символів показуємо в переліку. Достатньо, щоб власник упізнав
# свій ключ, і замало, щоб його відновити.
VISIBLE = 12


@dataclass(frozen=True, slots=True)
class IssuedApiKey:
    record: ApiKey
    token: str


def _now() -> datetime:
    return datetime.now(UTC)


async def issue(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    name: str = "",
    expires_at: datetime | None = None,
) -> IssuedApiKey:
    token = PREFIX + secrets.token_urlsafe(SECRET_BYTES)
    record = ApiKey(
        organization_id=organization_id,
        created_by_user_id=created_by_user_id,
        name=name.strip()[:100],
        prefix=token[:VISIBLE],
        token_hash=hash_token(token),
        expires_at=expires_at,
    )
    db.add(record)
    await db.flush()
    return IssuedApiKey(record=record, token=token)


async def resolve(db: AsyncSession, token: str) -> ApiKey | None:
    """Чинний ключ або None.

    Пошук по хешу, а не по префіксу: префікс не унікальний і потрібен
    лише для показу. Відкликаний і прострочений дають той самий None —
    відрізняти їх у відповіді означало б підказувати, що ключ існував.
    """
    if not token.startswith(PREFIX):
        return None
    stmt = select(ApiKey).where(ApiKey.token_hash == hash_token(token))
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None or record.revoked_at is not None:
        return None
    if record.expires_at is not None and record.expires_at <= _now():
        return None
    return record


async def revoke(db: AsyncSession, *, key_id: uuid.UUID, organization_id: uuid.UUID) -> bool:
    """Відкликання лише в межах своєї організації.

    Фільтр по організації стоїть у запиті, а не після вибірки: інакше
    достатньо було б знати чужий id ключа.
    """
    stmt = select(ApiKey).where(
        ApiKey.id == key_id,
        ApiKey.organization_id == organization_id,
        ApiKey.revoked_at.is_(None),
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        return False
    record.revoked_at = _now()
    return True


async def list_for(db: AsyncSession, *, organization_id: uuid.UUID) -> list[ApiKey]:
    stmt = (
        select(ApiKey)
        .where(ApiKey.organization_id == organization_id, ApiKey.revoked_at.is_(None))
        .order_by(ApiKey.created_at.desc())
    )
    return list((await db.execute(stmt)).scalars().all())
