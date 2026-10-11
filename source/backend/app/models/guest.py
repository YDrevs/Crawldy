"""Таблиці анонімної воронки: гостьова сесія й розблокований аудит.

Представлення персистентності, не бізнес-логіка.

## Чому сесія, а не просто токен на аудиті

Гість приходить із адресою, а не з акаунтом, і між запуском аудиту й
оплатою минає час: він чекає результату, читає короткий вигляд, іде до
каси, повертається. Усе це — одна людина в одній вкладці, і саме її
треба впізнавати, а не кожен аудит окремо.

Тому спроможність (capability) видається сесії. Аудит належить
організації сесії, і доступ до нього виводиться з того, що предʼявник
токена — та сама сесія. Токен на кожен аудит окремо здавався б
простішим, але зробив би неможливим найзвичайніше: показати людині те,
що вона щойно запускала, коли вона повернулася з каси.

## Токен зберігається лише хешем

Так само, як `ReportLink`. Дамп бази чи випадковий `SELECT` не має
роздавати робочі спроможності. Відкритий токен існує один раз — у
відповіді на створення сесії.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

JSONType = JSON().with_variant(JSONB(), "postgresql")


def _now() -> datetime:
    return datetime.now(UTC)


class GuestSession(Base):
    """Анонімний відвідувач: спроможність і організація, якою він володіє."""

    __tablename__ = "guest_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    # SHA-256 від `secrets.token_urlsafe(32)`. Відкритого токена в базі немає.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    # Строк спроможності. Коротший за строк зберігання аудиту навмисно:
    # прострочена сесія не знищує куплений аудит, вона лише перестає
    # бути ключем до нього. Той, хто заплатив, дістає власне посилання.
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Хеш адреси з сіллю, не сама адреса. Потрібен лише для лічильників
    # зловживання; зберігати IP довше за потребу немає підстав.
    ip_hash: Mapped[str] = mapped_column(String(64), default="")

    __table_args__ = (Index("ix_guest_sessions_expires", "expires_at"),)

    def is_live(self, *, now: datetime | None = None) -> bool:
        return self.expires_at > (now or _now())


class AuditUnlock(Base):
    """Повний вигляд аудиту відкрито, і ось за якою покупкою.

    Окремий рядок, а не прапорець на аудиті. Прапорець відповідав би на
    питання «чи відкрито», але не на «чому» — а саме друге питання
    ставлять, коли гроші пройшли, а доступу немає. Тут відповідь є: є
    рядок — є покупка, немає рядка — покупка лишилась без видачі, і це
    видно запитом, а не здогадом.

    Унікальність за `audit_id`: один аудит відкривається один раз.
    Повторна доставка події провайдера не створює другий рядок, а
    повторна покупка того самого аудиту неможлива за побудовою.
    """

    __tablename__ = "audit_unlocks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="CASCADE"), unique=True, index=True
    )
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("one_off_purchases.id", ondelete="RESTRICT"), index=True
    )
    # RESTRICT: покупка пояснює доступ. Видалити її, лишивши відкритий
    # аудит, означало б втратити єдину відповідь на питання «чому».
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("audit_id", name="uq_audit_unlock_audit"),)


class GuestMerge(Base):
    """Журнал злиття гостьової організації в наявну.

    Через рік питання «чому ці аудити й покупки належать цій
    організації» мусить мати відповідь у базі. Без журналу перенесення
    виглядало б як довільна правка історичних записів — тобто рівно як
    те, чим воно не є. Той самий аргумент, що й у `SiteMerge`.

    Це НЕ загальний механізм переносу орендарів. Джерелом може бути лише
    гостьова організація, операція одна, і рядок журналу — її єдиний
    слід. Розширювати його на «перенести будь-що будь-куди» заборонено
    задумом: у звичайного завершеного аудиту власник незмінний.
    """

    __tablename__ = "guest_merges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # RESTRICT з обох боків: журнал пояснює минуле, і організації, про
    # які він говорить, не мають зникати з-під нього мовчки.
    guest_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    destination_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    performed_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    audits_moved: Mapped[int] = mapped_column(default=0)
    purchases_moved: Mapped[int] = mapped_column(default=0)
    credits_moved: Mapped[int] = mapped_column(default=0)
    # Відповідність сайтів на момент злиття: origin, сайт-джерело,
    # цільовий сайт і чи був він створений цією операцією. JSONB, а не
    # колонки, бо сайтів у гостя може бути кілька — по одному на origin.
    site_map: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    reason: Mapped[str] = mapped_column(Text, default="")


class GuestMergeAudit(Base):
    """Один перенесений аудит одного злиття.

    Окрема таблиця, а не список у JSONB, з однієї причини: на ній стоїть
    доступ. Гостьова спроможність після злиття мусить досі відкривати
    рівно ті аудити, які були її, — і «чи був цей аудит перенесений з
    організації цієї сесії» має відповідатися індексом, а не розбором
    JSON у кожному запиті.

    `audit_id` навмисно без FK: журнал — історичний запис, і він
    переживає видалення аудиту, про який говорить.
    """

    __tablename__ = "guest_merge_audits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    merge_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("guest_merges.id", ondelete="CASCADE"), index=True
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    __table_args__ = (
        UniqueConstraint("merge_id", "audit_id", name="uq_guest_merge_audit"),
    )
