"""Лічильник спожитого за період.

Окремою таблицею, а не полем в організації: період змінюється, а
історія споживання має лишатися — інакше «скільки аудитів було в
травні» неможливо відповісти, а це перше питання при суперечці про
рахунок.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class Usage(Base):
    """Скільки організація витратила в конкретному періоді.

    Унікальність (organization_id, period_start, metric) не для порядку:
    на ній тримається атомарне списання через ON CONFLICT. Без неї два
    паралельні запити на останній аудит створили б два рядки й обидва
    пройшли б.
    """

    __tablename__ = "usage_counters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    metric: Mapped[str] = mapped_column(String(32))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "period_start", "metric", name="uq_usage_org_period_metric"
        ),
    )


__all__ = ["Usage"]
