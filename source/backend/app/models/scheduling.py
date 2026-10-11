"""Таблиця розкладів.

Розклад — це конфігурація майбутнього запуску, а не аудит. Він створює
`Audit` із `trigger = scheduled`; сам по собі він нічого не міряє.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.sites import Site
from app.scheduling.enums import Cadence


def _now() -> datetime:
    return datetime.now(UTC)


class AuditSchedule(Base):
    """Регулярний аудит одного сайту.

    Час зберігається як **локальний настінний** плюс зона IANA, а не як
    UTC. «Щодня о 9:00» означає 9:00 у клієнта — і в березні, і в
    жовтні. Зберігати одразу UTC означало б, що двічі на рік звіт
    починає приходити на годину раніше або пізніше, і ніхто не зрозуміє
    чому. `next_run_at` — похідне поле в UTC, перераховується після
    кожного запуску.
    """

    __tablename__ = "audit_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    site_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    cadence: Mapped[Cadence] = mapped_column(
        Enum(Cadence, name="schedule_cadence", native_enum=False)
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    hour_local: Mapped[int] = mapped_column(SmallInteger, default=9)
    minute_local: Mapped[int] = mapped_column(SmallInteger, default=0)
    # 0 = понеділок, як у `date.weekday()`.
    day_of_week: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    day_of_month: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)

    # Опції аудиту, з якими запускати. Обрізаються правами в момент
    # запуску, а не в момент створення розкладу: тариф може змінитися.
    options: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    enabled: Mapped[bool] = mapped_column(default=True)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Останнього аудиту тут немає навмисно. Він виводиться запитом
    # (`audits.schedule_id = ? ORDER BY scheduled_for DESC LIMIT 1`), і
    # зберігати його окремо означало б друге джерело правди, яке
    # розійдеться з першим після чистки за строком утримання чи після
    # об'єднання сайтів. Заразом це прибирає циклічний зовнішній ключ
    # між audits і audit_schedules — SQLAlchemy на нього скаржиться, і
    # має рацію: порядок створення таблиць стає неоднозначним.

    # Оренда на час обробки. Планувальник claim'ить рядок, ставлячи цей
    # строк; поки він не минув, інший екземпляр рядка не візьме. Захист
    # від подвійного запуску живе в базі, бо черга — інфраструктура, а не
    # джерело правди.
    claimed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Скільки разів поспіль не вийшло. Розклад не вимикається мовчки:
    # тихо вимкнений розклад виглядає для клієнта так само, як робочий.
    consecutive_failures: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    last_failure_reason: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), onupdate=_now
    )

    site: Mapped[Site] = relationship()

    __table_args__ = (
        # Головний запит планувальника: що вже час запускати. Частковий
        # індекс — бо вимкнені розклади в ньому не потрібні ніколи.
        Index(
            "ix_schedules_due",
            "next_run_at",
            postgresql_where=enabled.is_(True),
        ),
        Index("ix_schedules_org_site", "organization_id", "site_id"),
        # Один розклад на сайт. Не обмеження інтерфейсу, а правило
        # домену: продуктове питання звучить «коли перевіряти цей сайт»,
        # і два різні розклади на нього — це не гнучкість, а два джерела
        # правди. Заразом це робить повторне надсилання форми безпечним:
        # дубль не створиться навіть тоді, коли запит прийде двічі.
        UniqueConstraint("site_id", name="uq_schedule_site"),
    )


__all__ = ["AuditSchedule"]
