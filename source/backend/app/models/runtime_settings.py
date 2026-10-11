"""Робочі налаштування, збережені адміністратором: один рядок на ключ.

Поруч із `ai_domain_settings` (політики AI-доменів у JSON) — але інша
одиниця: тут окреме значення з відомого переліку ключів, а не документ
політики. Перелік ключів і їхній зміст живуть у `app.core.runtime_config`;
таблиця знає лише ключ, значення й те, чи значення зашифроване.

Секрети зберігаються ЛИШЕ зашифрованими (Fernet, ключ — в оточенні). Рядок
із `is_secret=true` без ключа шифрування прочитати неможливо, і код
чесно каже «не налаштовано», а не вигадує значення.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class RuntimeSetting(Base):
    __tablename__ = "runtime_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    # Для секрету — шифротекст Fernet; для решти — значення як є.
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
