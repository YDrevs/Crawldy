"""Звернення з публічної контактної форми.

Представлення персистентності, не бізнес-логіка. Правила — у
`app/application/contact.py`.

## Чому рядок у базі, а не одразу лист

Лист може не піти: провайдера не налаштовано, ключ протух, поштова
служба лежить. Якщо звернення існує лише як спроба надіслати, кожна
така хвилина — це втрачені повідомлення людей, які вважають, що з нами
звʼязалися. Тому звернення спершу **зберігається**, і лише потім
доставляється; стан доставки живе поруч із ним і видно запитом.

## Ідентичність запиту, а не вміст, тримає повтори

`request_key` — хеш звернення (пошта, текст, вікно часу). Повторне
натискання кнопки або повтор мережею дає той самий ключ і не створює
другого рядка: унікальний індекс вирішує гонку в базі, а не сподівання
на дисципліну обробника.

## Чого тут немає

Адреси одержувача. Вона живе в налаштуваннях сервера й ніколи не
потрапляє ані в базу, ані у відповідь API: те, що не зберігається, не
витікає.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class ContactMessage(Base):
    """Одне звернення: що написали, і що з ним сталося далі."""

    __tablename__ = "contact_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), index=True)
    # Необовʼязкове поле форми, збережене вже нормалізованим.
    site_url: Mapped[str] = mapped_column(String(2048), default="")
    message: Mapped[str] = mapped_column(Text)
    # Мова сторінки, з якої написали: відповідати людині треба її мовою.
    locale: Mapped[str] = mapped_column(String(5), default="en")

    # queued → delivered | failed. Термінального «відкинуто» немає:
    # звернення, яке ми прийняли, лишається нашим боргом.
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    delivery_error: Mapped[str] = mapped_column(Text, default="")
    delivery_attempts: Mapped[int] = mapped_column(default=0)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Хеш адреси з сіллю, як у гостьових сесіях: для розбору зловживань
    # достатньо, а самої адреси ми не зберігаємо.
    ip_hash: Mapped[str] = mapped_column(String(64), default="")
    # Ідентичність звернення: другий такий самий запит не створює рядка.
    request_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("request_key", name="uq_contact_message_request"),
        Index("ix_contact_messages_created", "created_at"),
    )
