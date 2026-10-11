"""Адмін-політики AI-доменів: один рядок на домен, JSON без секретів.

Два домени — «analysis» (збагачення/аналіз) і «presence» (Actual AI
Presence) — це РІЗНІ політики над спільним каталогом можливостей.
Окремі рядки гарантують твердий інваріант: зміна одного домену фізично
не може зачепити інший. Секрети сюди не потрапляють ніколи — ключі
живуть в оточенні, політика знає лише «налаштовано / ні».
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.audit import JSONType


class AiDomainSettings(Base):
    __tablename__ = "ai_domain_settings"

    domain: Mapped[str] = mapped_column(String(32), primary_key=True)
    policy: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
