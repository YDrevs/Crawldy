"""Таблиця сайтів: стабільна ідентичність того, що аудитуємо.

Історія балів досі ключувалася на рядку `origin` в аудиті. Це працює,
поки аудити запускають руками; щойно з'являється розклад, прив'язувати
його нема до чого, а перша ж зміна форми адреси розділяє історію надвоє.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.identity import Organization


def _now() -> datetime:
    return datetime.now(UTC)


class Site(Base):
    """Сайт у межах організації.

    `origin` оголошує людина, і він незмінний: саме на ньому тримається
    історія. `resolved_origin` — те, куди сайт насправді привів після
    редиректів; він заповнюється воркером після першого аудиту й існує
    рівно для того, щоб запитати «схоже, це той самий сайт — об'єднати?».
    Автоматично не об'єднується нічого.
    """

    __tablename__ = "sites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    origin: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(200), default="")
    # Куди сайт привів після редиректів. Порожньо — ще не аудитували або
    # редиректів не було.
    resolved_origin: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), onupdate=_now
    )
    # Архівація, не видалення: аудити сайту лишаються історією організації
    # навіть тоді, коли сам сайт більше не цікавий.
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    notes: Mapped[str] = mapped_column(Text, default="")

    organization: Mapped[Organization] = relationship()

    __table_args__ = (
        UniqueConstraint("organization_id", "origin", name="uq_site_org_origin"),
        Index("ix_sites_org_created", "organization_id", "created_at"),
    )





class SiteMerge(Base):
    """Журнал об'єднань сайтів.

    Через рік питання «чому ці аудити раптом належать іншому сайту» має
    мати відповідь у базі, а не в чиїйсь пам'яті. Без журналу
    організаційне групування виглядало б як довільна зміна історичних
    записів — тобто рівно як те, чим воно не є.

    Запис не видаляється разом із сайтами: він пояснює минуле, а сайти
    можуть бути заархівовані.
    """

    __tablename__ = "site_merges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # SET NULL, а не CASCADE: пояснення переживає сайт, про який воно.
    source_site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    target_site_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="SET NULL"), nullable=True
    )
    # Адреси на момент злиття: сайт може бути видалений, а питання
    # «що з чим об'єднали» лишиться.
    source_origin: Mapped[str] = mapped_column(String(255))
    target_origin: Mapped[str] = mapped_column(String(255))
    audits_moved: Mapped[int] = mapped_column(default=0)
    reason: Mapped[str] = mapped_column(Text, default="")

    performed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )


__all__ = ["Site", "SiteMerge"]
