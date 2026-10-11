"""Таблиці білінгу: тарифи, підписки, індивідуальні винятки.

Провайдер платежів тут присутній рівно двома колонками — `provider` і
`provider_*_id`. Усе інше домен: стан підписки, період, тариф. Це і є
межа, завдяки якій заміна Paddle на Stripe не чіпає ні аудити, ні сайти,
ні інтерфейс.

Цін у `Plan` немає навмисно. Вони живуть у провайдера, а тут лежить лише
відповідність «наш тариф ↔ його прайс». Домен не знає сум і не має знати:
інакше зміна ціни ставала б міграцією.
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
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.billing.enums import BillingEventStatus, SubscriptionStatus
from app.core.db import Base
from app.models.identity import Organization


def _now() -> datetime:
    return datetime.now(UTC)


class Plan(Base):
    """Тариф як набір прав.

    `code` — стабільний ідентифікатор, на який посилається код і
    провайдер. `name` можна міняти скільки завгодно: це напис.
    """

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(48), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    # Клієнтський текст мовами публічного сайту: {"de": "…", "fr": "…"}.
    # ПОРОЖНЯ мапа — явний вибір «назва універсальна»: `name` — бренд,
    # однаковий усіма мовами (і єдина поведінка для старих записів).
    # НЕПОРОЖНЯ мапа публічного запису мусить покривати всі шість мов —
    # це перевіряє адмін-маршрут, щоб німецька сторінка ніколи не
    # показала українську назву мовчазним фолбеком. Числа сюди не
    # потрапляють ніколи: тут лише напис, джерело правди для сум і
    # лімітів лишається одне.
    name_i18n: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    description_i18n: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    # Чи показувати в переліку тарифів. Прихований тариф лишається
    # робочим — так живуть індивідуальні умови й старі тарифи, з яких
    # нікого не переводять примусово.
    is_public: Mapped[bool] = mapped_column(default=True)
    sort_order: Mapped[int] = mapped_column(default=0)

    # Права. JSONB, бо набір ключів змінюється частіше за схему, а
    # колонка на кожне право перетворила б додавання ліміту на міграцію.
    # Типи перевіряє `billing.entitlements.validate`, не база.
    entitlements: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlanPrice(Base):
    """Відповідність «наш тариф ↔ прайс провайдера».

    Окремою таблицею, а не колонкою в `Plan`: тариф має ціну в кожній
    валюті, за кожен період і в кожного провайдера. Колонка `paddle_price_id`
    у тарифі означала б, що другий провайдер вимагає міграції.
    """

    __tablename__ = "plan_prices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    provider_price_id: Mapped[str] = mapped_column(String(128))
    # Продукт провайдера при прайсі — див. `CommercialOffer.provider_product_ref`.
    provider_product_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Памʼять по всіх провайдерах — див. `CommercialOffer.provider_refs`.
    provider_refs: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    currency: Mapped[str] = mapped_column(String(3))
    interval: Mapped[str] = mapped_column(String(16))  # month | year

    # Ціна **для показу**, у мінімальних одиницях цієї валюти.
    #
    # `minor`, а не `cents`: у єни мінімальної одиниці немає взагалі, у
    # динара Бахрейну їх тисяча. Назва з центами зашивала б у модель
    # припущення про два знаки, хибне для міжнародного продукту.
    #
    # Не джерело правди для списання: рахує провайдер за своїм прайсом,
    # і розбіжність тут не змінює жодної суми на рахунку клієнта. Поле
    # існує, бо сторінка тарифів потребує числа, а тягнути його з
    # провайдера на кожен показ означало б класти публічну сторінку разом
    # із його недоступністю. Значення прив'язане до цього рядка, тобто до
    # пари «валюта + період» конкретного прайсу провайдера; у P4.7b його
    # можна буде звіряти з каталогом провайдера.
    #
    # Порожньо — ціни ще не завели: сторінка каже «зв'яжіться з нами», а
    # не малює нуль.
    display_amount_minor: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    plan: Mapped[Plan] = relationship()

    __table_args__ = (
        UniqueConstraint("provider", "provider_price_id", name="uq_plan_price_provider"),
    )


class BillingCustomer(Base):
    """Організація очима провайдера."""

    __tablename__ = "billing_customers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True
    )
    provider: Mapped[str] = mapped_column(String(32))
    provider_customer_id: Mapped[str] = mapped_column(String(128))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    organization: Mapped[Organization] = relationship()

    __table_args__ = (
        UniqueConstraint("provider", "provider_customer_id", name="uq_billing_customer_provider"),
    )


class Subscription(Base):
    """Підписка організації на тариф.

    `cancel_at_period_end` — прапорець, а не стан. «Скасується наприкінці
    періоду» ортогональне до «зараз активна», і зливати їх в один enum
    означало б множити стани: active+cancelling, trialing+cancelling і так
    далі.

    `provider_updated_at` існує через те, що провайдери не гарантують
    порядку доставки подій. Подія, старша за поточний стан, не
    застосовується — інакше запізнілий «trialing» скасував би вже
    отриманий «active».
    """

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="RESTRICT")
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", native_enum=False),
        default=SubscriptionStatus.INACTIVE,
    )
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)

    current_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Коли права закінчаться, якщо платіж так і не пройде. Порожньо, поки
    # підписка не в past_due.
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Комерційний наділ ПОТОЧНОГО періоду — зліпок ключів
    # `PERIOD_ALLOCATION_KEYS` тарифу на момент, коли період було
    # виставлено. Зміна тарифу адміністратором посеред періоду не
    # переписує вже виданого наділу; наступний період знімкується наново.
    # Порожньо для підписок, створених до появи поля, — тоді діє живий
    # тариф, як і раніше.
    period_allocation: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    provider: Mapped[str] = mapped_column(String(32))
    provider_subscription_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), onupdate=_now
    )

    organization: Mapped[Organization] = relationship()
    plan: Mapped[Plan] = relationship(lazy="joined")

    __table_args__ = (
        UniqueConstraint(
            "provider", "provider_subscription_id", name="uq_subscription_provider_id"
        ),
        # Одна діюча підписка на організацію. Друга означала б два набори
        # прав одночасно й питання «який із них правда» без відповіді.
        Index(
            "uq_subscription_active_per_org",
            "organization_id",
            unique=True,
            postgresql_where=status.in_(
                (
                    SubscriptionStatus.TRIALING,
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.PAST_DUE,
                )
            ),
        ),
    )


class BillingEvent(Base):
    """Нормалізована подія провайдера. Вхідний факт, а не стан.

    Ланцюг: сирий вебхук → перевірка підпису й нормалізація в адаптері →
    цей рядок → доменний перехід → стан підписки. Після нормалізації
    сирий payload — лише архів для розслідувань; логіка читає нормалізовані
    колонки, і зміна схеми провайдера її не чіпає.

    Ідемпотентність тримається унікальністю `(provider, external_event_id)`
    в базі, а не if-ом у Python: та сама подія приходить двічі, п'ять
    разів, після таймауту нашої відповіді й паралельно на два процеси — а
    рядок один, і перехід один.
    """

    __tablename__ = "billing_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(32))
    external_event_id: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(48))

    # Три часи, і всі три потрібні: коли сталося в провайдера (порядок
    # подій), коли дійшло до нас (діагностика доставки), коли ми
    # застосували (діагностика обробки). Сплутати перший із другим —
    # значить вирішувати «що новіше» за порядком доставки, якого
    # провайдери не гарантують.
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[BillingEventStatus] = mapped_column(
        Enum(BillingEventStatus, name="billing_event_status", native_enum=False),
        default=BillingEventStatus.RECEIVED,
    )
    error: Mapped[str] = mapped_column(Text, default="")

    # Зовнішні посилання — довідково, не ідентичність наших обʼєктів.
    subscription_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    customer_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    price_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Нормалізовані факти події — колонками, а не всередині payload.
    # З них подія відновлюється для повтору без участі провайдера;
    # повтор, який губить періоди чи trial, був би повтором іншої події.
    organization_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    with_trial: Mapped[bool] = mapped_column(default=False)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    trial_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint("provider", "external_event_id", name="uq_billing_event_provider_id"),
        Index("ix_billing_events_status", "status"),
    )


class SubscriptionTransition(Base):
    """Один перехід підписки. Історія, якої не переписують.

    Відповідь на питання «чому ця організація 14 березня мала права Pro»
    складається саме звідси: стан, тариф, межі періоду, момент дії і
    посилання на подію, яка це спричинила. Поточний рядок підписки цієї
    відповіді не дає — він про «зараз», а питання про «тоді».
    """

    __tablename__ = "subscription_transitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    subscription_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("subscriptions.id", ondelete="CASCADE"), index=True
    )
    # Денормалізовано навмисно: питання ставлять про організацію, і
    # відповідь не має залежати від того, чи жива ще підписка.
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)

    from_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", native_enum=False)
    )
    to_status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status", native_enum=False)
    )
    from_plan_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    to_plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    # Момент, з якого стан діє, — час події в провайдера, не час обробки.
    effective_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    grace_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)

    billing_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("billing_events.id", ondelete="SET NULL"), nullable=True
    )

    subscription: Mapped[Subscription] = relationship()


class EntitlementOverride(Base):
    """Індивідуальний виняток для організації.

    Потрібен із першого дня, а не «коли знадобиться». Перша ж
    нестандартна домовленість — компенсація за збій, дідівські умови,
    доступ для партнера — інакше стає хардкодом у бізнес-логіці.

    `reason` обов'язковий за домовленістю: виняток без причини через рік
    неможливо ні пояснити, ні зняти.
    """

    __tablename__ = "entitlement_overrides"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    key: Mapped[str] = mapped_column(String(64))
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    reason: Mapped[str] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "key", name="uq_entitlement_override_org_key"),
    )


__all__ = [
    "BillingCustomer",
    "BillingEvent",
    "EntitlementOverride",
    "Plan",
    "PlanPrice",
    "Subscription",
    "SubscriptionTransition",
]
