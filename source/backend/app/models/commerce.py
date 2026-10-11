"""Комерційний каталог: пропозиції, кампанії, погашення промокодів.

Продукт один — аналіз сайту. Пропозиції — це способи його купити:
SINGLE (одна перевірка), PACK (кілька дешевше). MONTHLY навмисно НЕ
тут: місячна модель — це наявні тарифи (`plans`) із підпискою,
періодами та правами; дублювати той механізм другою таблицею означало
б два джерела правди про одне право.

Жодної ціни в коді: рядок пропозиції несе посилання на прайс
провайдера і показові метадані. Зміна ціни чи розміру пакета — правка
рядка адміністратором, не реліз.

Промо-правило продукту: код діє ЛИШЕ на PACK-пропозиції й лише один
раз на організацію. Paddle рахує гроші знижки; хто МОЖЕ її отримати —
вирішуємо ми, і UNIQUE(campaign, organization) тримає «один раз»
рівнем бази, а не дисципліни.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class OfferType(StrEnum):
    SINGLE = "single"
    PACK = "pack"


class RedemptionStatus(StrEnum):
    """PENDING — каса відкрита, грошей ще немає; COMPLETED — оплачено.

    PENDING не блокує повторну спробу НАЗАВЖДИ: та сама організація з
    тією самою кампанією знаходить свій рядок і переиспользовує його.
    COMPLETED — термінальний: другого погашення не буде.
    """

    PENDING = "pending"
    COMPLETED = "completed"


class CommercialOffer(Base):
    __tablename__ = "commercial_offers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    offer_type: Mapped[OfferType] = mapped_column(
        Enum(OfferType, name="offer_type", native_enum=False)
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    display_name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    # Клієнтський текст мовами публічного сайту — та сама модель, що в
    # Plan.name_i18n: порожня мапа = універсальна назва (display_name
    # для всіх мов, і єдина поведінка старих записів); непорожня мапа
    # активної пропозиції мусить покривати всі шість мов (стереже
    # адмін-маршрут). Жодних чисел: суми, кількості й прайс-посилання
    # мають одне джерело правди й не локалізуються.
    display_name_i18n: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    description_i18n: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )

    # Прайс провайдера — та сама дисципліна, що в plan_prices: назва
    # провайдера — дані, `pri_…` у коді не існує.
    provider: Mapped[str] = mapped_column(String(32))
    provider_price_ref: Mapped[str] = mapped_column(String(128))
    # Продукт провайдера, при якому живе прайс. Заповнює публікація, а не
    # людина; порожньо — прайс іще не публікувався (або запис старіший за
    # публікацію), і наступна публікація створить продукт сама.
    provider_product_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Те саме, але памʼять по ВСІХ провайдерах, у яких запис колись
    # публікувався: `{"paddle": {"price": "pri_…", "product": "pro_…"}}`.
    # Поля вище описують ЧИННУ привʼязку, ця мапа — історію, і саме вона
    # робить повернення до попереднього провайдера безкоштовним. Без неї
    # кожне перемикання каси створювало б у нього нові продукти.
    provider_refs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    # Для показу, не для списання: рахує провайдер.
    display_amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Що видає оплата. Куплені одиниці не згорають — строку придатності
    # немає ніде в моделі, і це продуктова гарантія, не пропуск.
    audit_credits: Mapped[int] = mapped_column(Integer, default=1)
    presence_credits: Mapped[int] = mapped_column(Integer, default=0)

    promo_eligible: Mapped[bool] = mapped_column(Boolean, default=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class PromoCampaign(Base):
    __tablename__ = "promo_campaigns"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Знижка провайдера: гроші рахує він. Порожньо для кампаній, що
    # діють внутрішніми грантами (наприклад, «перші 10 — безкоштовно»
    # видаються адмінським грантом, а не $0-транзакцією).
    provider_discount_ref: Mapped[str | None] = mapped_column(
        String(128), nullable=True
    )
    starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    redemptions: Mapped[list[PromoRedemption]] = relationship(
        back_populates="campaign"
    )


class PromoRedemption(Base):
    __tablename__ = "promo_redemptions"
    __table_args__ = (
        # Правило бізнесу рівнем бази: одна організація — одне погашення
        # однієї кампанії. Не Paddle-івський usage_limit (він глобальний),
        # а наша власна межа.
        UniqueConstraint(
            "campaign_id", "organization_id", name="uq_promo_once_per_org"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    campaign_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("promo_campaigns.id", ondelete="CASCADE"),
        index=True,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
    )
    offer_code: Mapped[str] = mapped_column(String(48))
    status: Mapped[RedemptionStatus] = mapped_column(
        Enum(RedemptionStatus, name="promo_redemption_status", native_enum=False),
        default=RedemptionStatus.PENDING,
        server_default=RedemptionStatus.PENDING.name,
    )
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("one_off_purchases.id", ondelete="SET NULL"),
        nullable=True,
    )
    redeemed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    campaign: Mapped[PromoCampaign] = relationship(back_populates="redemptions")
