"""Разова покупка й кредити, які вона породжує.

## Кредит — рядок, а не число

Спокуслива модель — лічильник: `balance = 5`. Вона не відповідає на
жодне з питань, які виникають першого ж місяця. Повернути кошти за
конкретну покупку? Відкликати саме її невикористані одиниці?
Повернути кредит за аудит, що не відбувся, — але **той самий**, а не
абстрактний? Пояснити через півроку, звідки взялися ці пʼять?

Тому одиниця обліку — рядок. «Кредит не можна зарезервувати двічі»
стає властивістю рядка, а не арифметикою над лічильником, у якій гонка
непомітна доти, доки хтось не поскаржиться.

Ціна — рядок на одиницю. Для разових покупок по одній–пʼять це дешево;
якщо колись зʼявляться пакети на тисячу, модель доведеться переглянути,
і це буде видно з розміру таблиці, а не з несподіваного дефекту.

## Покупка памʼятає, ким вона була продана

`supplier_snapshot` — незмінний зліпок наших реквізитів на момент
продажу. Ключа мало: реєстр колись відредагують, і стара покупка тихо
змінить постачальника. `commerce_model` теж у рядку: після переходу
Paddle → Stripe та сама покупка мусить і далі означати «продавцем за
законом був провайдер», а не почати означати протилежне.

Продавця за законом не дублюємо: при merchant of record він
авторитетно визначається транзакцією провайдера, а модель торгівлі,
записана тут, дозволяє це відтворити.
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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.billing.enums import CommerceModel, CreditState, PurchaseStatus
from app.core.db import Base


def _now() -> datetime:
    return datetime.now(UTC)


class OneOffPurchase(Base):
    """Одна оплачена покупка разових аудитів.

    Ідемпотентність тримає база: пара «провайдер + його ідентифікатор»
    унікальна, тож повтор вебхука або повторне програвання події не
    створюють другої покупки й другої партії кредитів.
    """

    __tablename__ = "one_off_purchases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )

    # Провайдер-нейтральне посилання тією самою парою, що й скрізь у
    # білінгу: назва провайдера — дані рядка, а не форма таблиці.
    provider: Mapped[str] = mapped_column(String(32))
    external_id: Mapped[str] = mapped_column(String(128))

    # Хто постачав продукт і за якою моделлю торгували — на момент продажу.
    supplier_entity_key: Mapped[str] = mapped_column(String(48))
    supplier_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    commerce_model: Mapped[CommerceModel] = mapped_column(
        Enum(CommerceModel, name="commerce_model", native_enum=False)
    )

    quantity: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    amount_minor: Mapped[int] = mapped_column(Integer)

    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus, name="purchase_status", native_enum=False),
        # Дефолт лишається PAID: він описує запис, створений подією
        # провайдера, і таких у таблиці більшість. Анонімна воронка
        # створює покупку раніше й задає PENDING явно.
        default=PurchaseStatus.PAID,
        # `.name`, а не `.value`: SQLAlchemy кладе в колонку саме імʼя
        # члена, і CHECK побудований на іменах. Значення тут порушувало б
        # власне обмеження таблиці — тихо, бо ORM завжди пише колонку сам
        # і до server_default справа доходить лише в сирому INSERT.
        server_default=PurchaseStatus.PAID.name,
    )

    # Посилання провайдера на саму транзакцію. Порожньо, поки каса не
    # відкрита, і потрібне тому, що подія про повернення коштів
    # посилається на транзакцію, а не на нашу покупку.
    #
    # Окремо від `external_id`: там лежить НАШ ідентифікатор кореляції,
    # який ми самі й віддаємо провайдеру в його довільні дані. Змішати
    # їх означало б не мати можливості звірити одне з одним.
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Порожньо, поки покупка в стані PENDING: каса відкрита, грошей ще
    # немає. Підставити сюди час створення означало б назвати часом
    # оплати момент, коли ніхто не заплатив.
    purchased_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Аудит, доступ до якого куплено. Порожньо для покупок «наперед»:
    # там кредит резервується під **майбутній** запуск, і напрямок
    # звʼязку зворотний — його тримає `AuditCredit.audit_id`.
    #
    # Тут напрямок інший, і це суть анонімної воронки: робота вже
    # виконана, купується не право її замовити, а повний вигляд того,
    # що вже виміряно. Одне поле розводить дві комерційні моделі, не
    # роздвоюючи таблицю.
    audit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Яку пропозицію купували. Порожньо для покупок анонімної воронки
    # (розблокування виконаного аудиту) — вони старші за каталог
    # пропозицій і живуть за власним правилом.
    offer_code: Mapped[str | None] = mapped_column(String(48), nullable=True)

    # Незмінний зліпок комерційних умов пропозиції на момент відкриття
    # каси: тип, прайс провайдера, показова сума, кількість одиниць.
    # Той самий закон, що й `supplier_snapshot`: рядок каталогу колись
    # відредагують, і без зліпка покупка десяти кредитів мовчки стала б
    # покупкою двадцяти — видача й історія читають ЗВІДСИ, а не з
    # живого каталогу.
    offer_snapshot: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )

    # Погашення промокоду, якщо покупка йшла зі знижкою кампанії.
    # Знижка міняє ЛИШЕ гроші: кількість і тип одиниць — з пропозиції.
    promo_redemption_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    credits: Mapped[list[AuditCredit]] = relationship(back_populates="purchase")

    __table_args__ = (
        UniqueConstraint("provider", "external_id", name="uq_purchase_provider_external"),
        Index("ix_purchases_org_created", "organization_id", "created_at"),
    )


class AuditCredit(Base):
    """Одна оплачена одиниця аудиту без періоду.

    Життєвий цикл:

        available ──reserve──> reserved ──consume──> consumed
             ▲                     │
             └──────release────────┘
        available ──revoke──> revoked        (повернення коштів)

    Кожен перехід — умовний UPDATE із перевіркою поточного стану, тож
    подвійне резервування, подвійне списання й подвійне повернення
    неможливі навіть при паралельних запитах: другий не знайде рядка в
    очікуваному стані.

    `audit_id` заповнюється при резерві й **лишається** після списання:
    без нього неможливо відповісти, який саме аудит зʼїв цей кредит.
    Порожнє воно лише в доступного або відкликаного.
    """

    __tablename__ = "audit_credits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Порожньо для промо- та адмінських грантів: не кожна одиниця
    # походить із покупки, але кожна знає своє походження (`source`).
    purchase_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("one_off_purchases.id", ondelete="CASCADE"),
        nullable=True, index=True,
    )
    # Денормалізовано навмисно: баланс питають по організації, і відповідь
    # не має вимагати обходу покупок.
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )

    state: Mapped[CreditState] = mapped_column(
        Enum(CreditState, name="audit_credit_state", native_enum=False),
        default=CreditState.AVAILABLE,
        server_default=CreditState.AVAILABLE.name,
    )

    # Тип одиниці. Кредит аудиту і перевірка AI-присутності — РІЗНІ
    # одиниці з різною економікою (~$0.05 інфраструктури проти ~$3.3
    # провайдерських грошей), і одна колонка тримає їх нарізно, не
    # роздвоюючи ні таблицю, ні дисципліну переходів.
    credit_type: Mapped[str] = mapped_column(
        String(16), default="audit", server_default="audit"
    )

    # Звідки взялася одиниця: purchase | promo | admin. Продуктове
    # правило «куплені кредити не згорають» тримається структурно —
    # колонки строку придатності тут НЕМАЄ і не буде.
    source: Mapped[str] = mapped_column(
        String(24), default="purchase", server_default="purchase"
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    # Який прогін присутності зʼїв цю одиницю — дзеркало audit_id для
    # другого типу. SET NULL: фінансовий запис живе довше за виміряне.
    presence_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("presence_runs.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )

    # SET NULL, а не CASCADE: аудит колись видалять за строком зберігання,
    # і кредит не має зникати разом із ним — він фінансовий запис.
    audit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("audits.id", ondelete="SET NULL"), nullable=True, index=True
    )

    reserved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    purchase: Mapped[OneOffPurchase] = relationship(back_populates="credits")

    __table_args__ = (
        # Пошук вільного кредита організації — найгарячіший запит цієї
        # таблиці, і він завжди «організація + стан».
        Index("ix_credits_org_state", "organization_id", "state"),
    )


__all__ = ["AuditCredit", "OneOffPurchase"]
