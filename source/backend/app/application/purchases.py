"""Разова покупка: запис, видача кредитів, повернення коштів.

## Ідемпотентність тримає база, а не код

Провайдер доставляє подію більше одного разу — це нормальна робота, а не
збій. Тому перевірка «чи вже обробляли» не читанням перед записом (між
ними вікно), а унікальним обмеженням на пару «провайдер + його
ідентифікатор»: другий запис просто не відбудеться, і ми повернемо вже
наявну покупку.

Це те саме правило, яким живе приймання подій білінгу, і воно тут
важливіше: подвійна обробка події підписки дасть зайвий перехід стану,
подвійна обробка покупки — зайві кредити, тобто подаровані гроші.

## Постачальник фіксується в момент продажу

Не посиланням на чинного, а знімком. Реєстр колись відредагують — і без
знімка вся історія продажів мовчки перепишеться на нову юридичну особу.
Модель торгівлі теж у рядку: після переходу Paddle → Stripe стара
покупка мусить і далі означати «продавцем за законом був провайдер».
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import catalog
from app.billing import supplier as suppliers
from app.billing.enums import BillingEventKind, CommerceModel, PurchaseStatus
from app.billing.providers import CheckoutRequest, ProviderUnavailable, Settlement
from app.billing.registry import provider_for
from app.models.purchase import AuditCredit, OneOffPurchase


@dataclass(frozen=True, slots=True)
class RecordedPurchase:
    purchase: OneOffPurchase
    credits_granted: int
    # Чи це повторна доставка тієї самої події. Не помилка — факт,
    # який має бути видимим у логах, а не мовчазним.
    already_known: bool


async def find(
    db: AsyncSession, *, provider: str, external_id: str
) -> OneOffPurchase | None:
    row = await db.execute(
        select(OneOffPurchase).where(
            OneOffPurchase.provider == provider,
            OneOffPurchase.external_id == external_id,
        )
    )
    return row.scalar_one_or_none()


async def record(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    provider: str,
    external_id: str,
    quantity: int,
    currency: str,
    amount_minor: int,
    purchased_at: datetime | None = None,
    supplier_key: str | None = None,
    commerce_model: CommerceModel | None = None,
) -> RecordedPurchase:
    """Записати оплачену покупку й видати кредити.

    Повторний виклик із тим самим `external_id` не створює нічого й
    повертає наявну покупку: кредити видаються рівно один раз.
    """
    if quantity <= 0:
        raise ValueError("покупка без одиниць не має сенсу")

    existing = await find(db, provider=provider, external_id=external_id)
    if existing is not None:
        return RecordedPurchase(purchase=existing, credits_granted=0, already_known=True)

    entity = suppliers.SUPPLIERS[supplier_key or suppliers.CURRENT_SUPPLIER_KEY]
    purchase = OneOffPurchase(
        id=uuid.uuid4(),
        organization_id=organization_id,
        provider=provider,
        external_id=external_id,
        supplier_entity_key=entity.key,
        supplier_snapshot=entity.snapshot(),
        commerce_model=commerce_model or suppliers.CURRENT_COMMERCE_MODEL,
        quantity=quantity,
        currency=currency.upper(),
        amount_minor=amount_minor,
        status=PurchaseStatus.PAID,
        purchased_at=purchased_at or datetime.now(UTC),
    )
    db.add(purchase)
    # Явний flush перед кредитами: у них зовнішній ключ на покупку, і
    # порядок вставок SQLAlchemy будує за звʼязками, а не за FK таблиць.
    # Проєкт уже наступав на це між знахідками й сторінками аудиту.
    await db.flush()

    for _ in range(quantity):
        db.add(
            AuditCredit(
                id=uuid.uuid4(),
                purchase_id=purchase.id,
                organization_id=organization_id,
            )
        )
    await db.flush()

    return RecordedPurchase(
        purchase=purchase, credits_granted=quantity, already_known=False
    )


async def open_pending(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    provider: str,
    audit_id: uuid.UUID | None,
    quantity: int = 1,
    supplier_key: str | None = None,
    commerce_model: CommerceModel | None = None,
    offer_code: str | None = None,
    offer_snapshot: dict[str, object] | None = None,
    promo_redemption_id: uuid.UUID | None = None,
) -> OneOffPurchase:
    """Почати покупку ДО каси. Гроші тут ще не приходили.

    Сенс раннього запису — кореляція. Провайдер поверне подію з нашим
    ідентифікатором у своїх довільних даних, і саме за цим рядком ми
    дізнаємось, ЩО саме оплачено. Без нього єдиною ниткою була б
    інформація, яку принесе чужий бік, — а їй вірити не можна.

    `external_id` тут наш власний: провайдерського ще не існує, а
    вигадувати заглушку в полі, за яким шукають, гірше за чесний
    ідентифікатор покупки. Коли каса відкриється, посилання провайдера
    ляже в `provider_ref` — окремо, щоб було чим звірити.

    Сума й валюта відомі провайдеру, а не нам: ціна живе в його прайсі.
    Тому нулі — не оцінка, а «ще не знаємо»; справжні числа приходять
    із події про оплату.
    """
    entity = suppliers.SUPPLIERS[supplier_key or suppliers.CURRENT_SUPPLIER_KEY]
    purchase = OneOffPurchase(
        id=uuid.uuid4(),
        organization_id=organization_id,
        provider=provider,
        supplier_entity_key=entity.key,
        supplier_snapshot=entity.snapshot(),
        commerce_model=commerce_model or suppliers.CURRENT_COMMERCE_MODEL,
        quantity=quantity,
        currency="",
        amount_minor=0,
        status=PurchaseStatus.PENDING,
        purchased_at=None,
        audit_id=audit_id,
        offer_code=offer_code,
        offer_snapshot=offer_snapshot,
        promo_redemption_id=promo_redemption_id,
    )
    purchase.external_id = str(purchase.id)
    db.add(purchase)
    await db.flush()
    return purchase


async def find_pending_for_audit(
    db: AsyncSession, *, organization_id: uuid.UUID, audit_id: uuid.UUID, provider: str
) -> OneOffPurchase | None:
    """Незакрита каса на цей аудит, якщо вона вже відкрита.

    Захист від подвійного кліку й повтору запиту: друга спроба відкрити
    касу віддає ту саму покупку й те саме посилання. Глобальної
    унікальності тут бути не може — купити той самий аудит удруге,
    після повернення коштів, законно, і схема це підтримує.
    """
    row = await db.execute(
        select(OneOffPurchase)
        .where(
            OneOffPurchase.organization_id == organization_id,
            OneOffPurchase.audit_id == audit_id,
            OneOffPurchase.provider == provider,
            OneOffPurchase.status == PurchaseStatus.PENDING,
        )
        .order_by(OneOffPurchase.created_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def find_pending_for_offer(
    db: AsyncSession, *, organization_id: uuid.UUID, offer_code: str, provider: str
) -> OneOffPurchase | None:
    """Незакрита каса на цю пропозицію, якщо вона вже відкрита.

    Те саме, що `find_pending_for_audit`, але для покупки без аудиту:
    в анонімній воронці аудиту ще немає, а повторне натискання «оплатити»
    так само не має плодити ані транзакцій у провайдера, ані рядків для
    гасіння в адмінці.

    Покупки з промокодом сюди не потрапляють: до них привʼязана
    конкретна редемпція, і віддати таку касу під іншу спробу означало б
    застосувати чужу знижку.
    """
    row = await db.execute(
        select(OneOffPurchase)
        .where(
            OneOffPurchase.organization_id == organization_id,
            OneOffPurchase.offer_code == offer_code,
            OneOffPurchase.provider == provider,
            OneOffPurchase.status == PurchaseStatus.PENDING,
            OneOffPurchase.audit_id.is_(None),
            OneOffPurchase.promo_redemption_id.is_(None),
            OneOffPurchase.provider_ref.isnot(None),
        )
        .order_by(OneOffPurchase.created_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


async def attach_provider_ref(
    db: AsyncSession, *, purchase: OneOffPurchase, provider_ref: str
) -> None:
    """Запамʼятати транзакцію провайдера поруч із покупкою."""
    purchase.provider_ref = provider_ref
    await db.flush()


async def mark_paid(
    db: AsyncSession,
    *,
    purchase: OneOffPurchase,
    currency: str,
    amount_minor: int,
    purchased_at: datetime,
    provider_ref: str | None = None,
) -> bool:
    """PENDING → PAID за перевіреною подією. Ідемпотентно.

    Повертає True, якщо перехід стався саме зараз. Повторна доставка
    тієї самої події застає покупку вже оплаченою й нічого не робить —
    кредити видаються рівно один раз.

    Повернена покупка НЕ оживає: `REFUNDED` — стан термінальний, і
    подія про оплату, що прийшла після повернення, не має його
    скасовувати.
    """
    # Покинута каса ОЖИВАЄ: службовий екран гасить каси, про які провайдер
    # сказав «не оплачено», і людина, яка заплатила після цього, мусить
    # отримати куплене. Саме тому гасіння — стан, а не видалення рядка.
    # Повернена не оживає ніколи: REFUNDED термінальний.
    if purchase.status not in (PurchaseStatus.PENDING, PurchaseStatus.ABANDONED):
        return False

    purchase.status = PurchaseStatus.PAID
    purchase.currency = currency.upper()
    purchase.amount_minor = amount_minor
    purchase.purchased_at = purchased_at
    if provider_ref:
        purchase.provider_ref = provider_ref
    await db.flush()

    await _grant_for(db, purchase)
    await _complete_redemption(db, purchase)
    return True


async def abandon(db: AsyncSession, *, purchase: OneOffPurchase) -> bool:
    """PENDING → ABANDONED. Оборотно: оплата потім оживить покупку.

    Нічого не відкликає й нічого не видає: каса просто перестає висіти
    серед незарахованих. Термінальні стани не чіпаються.
    """
    if purchase.status is not PurchaseStatus.PENDING:
        return False
    purchase.status = PurchaseStatus.ABANDONED
    await db.flush()
    return True


async def _grant_for(db: AsyncSession, purchase: OneOffPurchase) -> None:
    """Що саме видає ця оплата.

    Джерело правди — зліпок умов, знятий при відкритті каси: людина
    платила за те, що бачила тоді, і редагування каталогу між касою й
    оплатою не має міняти видачу. Живий рядок пропозиції — фолбек для
    покупок, старших за зліпок; спадкова покупка воронки — quantity
    аудитних кредитів, як завжди. Ідемпотентність тут не потрібна:
    видача живе всередині переходу PENDING→PAID, який не стається двічі.
    """
    snapshot = purchase.offer_snapshot or {}
    audit_units: int | None = None
    presence_units = 0
    if "audit_credits" in snapshot:
        audit_units = int(snapshot["audit_credits"])
        presence_units = int(snapshot.get("presence_credits", 0))
    elif purchase.offer_code:
        from app.models.commerce import CommercialOffer

        row = await db.execute(
            select(CommercialOffer).where(
                CommercialOffer.code == purchase.offer_code
            )
        )
        offer = row.scalar_one_or_none()
        if offer is not None:
            audit_units = offer.audit_credits
            presence_units = offer.presence_credits

    if audit_units is None:
        audit_units = purchase.quantity
    for credit_type, count in (("audit", audit_units),
                               ("presence", presence_units)):
        for _ in range(count):
            db.add(AuditCredit(
                id=uuid.uuid4(),
                purchase_id=purchase.id,
                organization_id=purchase.organization_id,
                credit_type=credit_type,
            ))
    await db.flush()


async def _complete_redemption(db: AsyncSession, purchase: OneOffPurchase) -> None:
    """Погашення промо стає термінальним разом з оплатою.

    Той самий перехід, та сама транзакція: повтор вебхука не завершить
    погашення вдруге, бо не повторить і переходу покупки.
    """
    if purchase.promo_redemption_id is None:
        return
    from app.models.commerce import PromoRedemption, RedemptionStatus

    redemption = await db.get(PromoRedemption, purchase.promo_redemption_id)
    if redemption is not None and redemption.status is RedemptionStatus.PENDING:
        redemption.status = RedemptionStatus.COMPLETED
        redemption.purchase_id = purchase.id
        redemption.redeemed_at = datetime.now(UTC)
        await db.flush()


async def find_by_provider_ref(
    db: AsyncSession, *, provider: str, provider_ref: str
) -> OneOffPurchase | None:
    """Покупка за транзакцією провайдера — шлях подій про повернення."""
    row = await db.execute(
        select(OneOffPurchase).where(
            OneOffPurchase.provider == provider,
            OneOffPurchase.provider_ref == provider_ref,
        )
    )
    return row.scalar_one_or_none()


@dataclass(frozen=True, slots=True)
class OpenedCheckout:
    """Каса, готова прийняти оплату."""

    purchase: OneOffPurchase
    url: str
    reused: bool


async def single_offer(db: AsyncSession, *, provider: str) -> Any:
    """Пропозиція «разова перевірка» каталогу для цієї каси.

    Це той самий продукт, що на сторінці цін, і ціна в нього одна —
    задана в кабінеті й опублікована у провайдера. Окремого налаштування
    «прайс разової покупки» немає навмисно: два місця для однієї суми
    вже розходились (закладка показувала 9.99, каса брала 10.00).

    Порожньо — недоналаштованість, а не «безкоштовно»: відкривати касу
    без ціни означало б продавати за нуль.
    """
    from app.models.commerce import CommercialOffer, OfferType

    row = await db.execute(
        select(CommercialOffer)
        .where(
            CommercialOffer.offer_type == OfferType.SINGLE,
            CommercialOffer.active.is_(True),
            CommercialOffer.archived_at.is_(None),
            CommercialOffer.provider == provider,
        )
        .order_by(CommercialOffer.sort_order)
    )
    offer = row.scalars().first()
    if offer is None or not offer.provider_price_ref:
        raise ProviderUnavailable(
            f"разова перевірка не має ціни для каси {provider}: "
            "задайте її на закладці «Ціни» кабінету адміністратора"
        )
    return offer


async def one_off_price_ref(db: AsyncSession, *, provider: str) -> str:
    """Тільки посилання на прайс. Решту умов бере `single_offer`."""
    offer = await single_offer(db, provider=provider)
    return str(offer.provider_price_ref)


def offer_terms(offer: Any) -> dict[str, object]:
    """Зліпок умов пропозиції на момент каси.

    Той самий формат, що в каталожної покупки кабінету: людина платить
    за те, що бачить зараз, і редагування каталогу до приходу вебхука не
    має ані міняти видачу, ані переписувати історію покупки.
    """
    return {
        "offer_code": offer.code,
        "offer_type": offer.offer_type.value,
        "provider_price_ref": offer.provider_price_ref,
        "currency": offer.currency,
        "display_amount_minor": offer.display_amount_minor,
        "audit_credits": offer.audit_credits,
        "presence_credits": offer.presence_credits,
        "captured_at": datetime.now(UTC).isoformat(),
    }


async def open_checkout(
    db: AsyncSession, *, organization_id: uuid.UUID, audit_id: uuid.UUID
) -> OpenedCheckout:
    """Створити покупку й відкрити касу провайдера. У такому порядку.

    Покупка створюється ДО каси й переживає її: саме вона — нитка між
    нами й провайдером. Його подія назве цей ідентифікатор, і аудит ми
    візьмемо зі свого запису, а не з того, що принесе чужий бік.

    Друга спроба віддає ту саму покупку: подвійний клік не має плодити
    записів. Глобальної унікальності при цьому немає — купити той самий
    аудит удруге, після повернення коштів, законно, і на цьому тримається
    правило чинності доступу.

    Якщо каса не відкрилась, покупка лишається PENDING. Незакрита каса —
    не помилка даних: людина може спробувати ще раз.
    """
    provider_name = catalog.current_provider()
    offer = await single_offer(db, provider=provider_name)
    existing = await find_pending_for_audit(
        db, organization_id=organization_id, audit_id=audit_id, provider=provider_name
    )
    purchase = existing or await open_pending(
        db,
        organization_id=organization_id,
        provider=provider_name,
        audit_id=audit_id,
        # Зліпок умов тієї самої «разової перевірки», що на сторінці цін.
        # Поки його тут не було, `_grant_for` падав у фолбек «quantity
        # аудитних кредитів» і видавав НУЛЬ перевірок присутності: гість
        # платив за дві речі, а отримував одну, і панель присутності на
        # оплаченому екрані не могла запуститись ніколи.
        offer_code=offer.code,
        offer_snapshot=offer_terms(offer),
    )

    adapter = provider_for(provider_name)
    if adapter is None:  # pragma: no cover — реєстр статичний
        raise ProviderUnavailable(f"провайдер {provider_name} не зареєстрований")

    session = await adapter.create_checkout(
        CheckoutRequest(
            purchase_id=purchase.id,
            price_ref=str(offer.provider_price_ref),
            organization_id=organization_id,
        )
    )
    await attach_provider_ref(db, purchase=purchase, provider_ref=session.ref.external_id)
    return OpenedCheckout(purchase=purchase, url=session.url, reused=existing is not None)


async def refund(
    db: AsyncSession, *, provider: str, external_id: str
) -> tuple[OneOffPurchase, int] | None:
    """Повернути кошти за покупку й відкликати невитрачені кредити.

    Витрачені не відкликаються: послугу було надано. Зарезервовані теж —
    їхню долю вирішить розрахунок аудиту, який зараз виконується.

    Повторний виклик безпечний: покупка вже позначена, вільних кредитів
    у ній не лишилось, і другий прохід відкличе нуль.
    """
    from app.billing import credits

    purchase = await find(db, provider=provider, external_id=external_id)
    if purchase is None:
        return None

    revoked = await credits.revoke_unused(db, purchase_id=purchase.id)
    if purchase.status is not PurchaseStatus.REFUNDED:
        purchase.status = PurchaseStatus.REFUNDED
        purchase.refunded_at = datetime.now(UTC)
        # Платні посилання відкликаються лише тоді, коли по цьому аудиту
        # не лишилось ЖОДНОЇ чинної оплати: покупок може бути кілька, і
        # повернення однієї не гасить доступ, куплений іншою. Саме
        # розблокування і рядок покупки лишаються — вони пояснюють, що
        # було куплено й що повернено, а токен — не право, а предʼявлення.
        if purchase.audit_id is not None:
            from app.application import guest

            if not await guest.is_unlocked(db, purchase.audit_id):
                await guest.revoke_paid_links(db, audit_id=purchase.audit_id)
    return purchase, revoked


# Стани, у яких оплата буває видима людині. Рядки, а не enum у базі:
# це похідне подання, зібране з покупки та журналу подій, а не колонка.
# Окремий стовпець став би другим джерелом правди про те саме.
PAYMENT_NONE = "none"
PAYMENT_PROCESSING = "processing"
PAYMENT_PAID = "paid"
PAYMENT_FAILED = "failed"
PAYMENT_REFUNDED = "refunded"


async def owned_purchase(
    db: AsyncSession, *, organization_id: uuid.UUID, purchase_id: uuid.UUID
) -> OneOffPurchase | None:
    """Покупка цієї організації. Чужа — це `None`, а не помилка.

    Гостьовий екран адресує покупку прямо, тож належність перевіряється
    тут, а не в маршруті: одне правило на всі входи.
    """
    return await db.scalar(
        select(OneOffPurchase).where(
            OneOffPurchase.id == purchase_id,
            OneOffPurchase.organization_id == organization_id,
        )
    )


async def spent_on_live_audit(
    db: AsyncSession, *, purchase: OneOffPurchase
) -> Any | None:
    """Аудит, на який цю покупку вже витрачено, якщо він живий.

    «Живий» — будь-який, крім невдалого: невдача не має спалювати
    оплату, і та сама покупка мусить прийняти другу адресу. Черга,
    виконання, готовий звіт — усе це витрачена покупка, і другого
    запуску за ті самі гроші тут не буде.
    """
    from app.audit.enums import AuditStatus
    from app.models.audit import Audit

    if purchase.audit_id is None:
        return None
    audit = await db.scalar(select(Audit).where(Audit.id == purchase.audit_id))
    if audit is None or AuditStatus(audit.status) is AuditStatus.FAILED:
        return None
    return audit


async def payment_state(
    db: AsyncSession, *, organization_id: uuid.UUID, audit_id: uuid.UUID
) -> str:
    """Що зараз відбувається з оплатою цього аудиту.

    Повернення браузера з каси нічого не доводить, тож сторінці
    повернення потрібна відповідь, яку дає сервер за власними записами.
    Саме тому тут немає ані параметрів адреси, ані ідентифікаторів, які
    приніс браузер: усе береться з покупки й журналу подій.

    `paid` каже лише те, що гроші прийшли. Право читати повний звіт
    перевіряє `guest.is_unlocked` окремо — і поки провіження не
    завершилось, чесна відповідь «ще обробляємо», а не «готово».

    `failed` живе в журналі подій, а не в стані покупки: невдала спроба
    не має ставати термінальним станом, інакше вона блокувала б наступну.
    """

    latest = await _latest_for_audit(
        db, organization_id=organization_id, audit_id=audit_id
    )
    return await state_of(db, purchase=latest)


async def state_of(db: AsyncSession, *, purchase: OneOffPurchase | None) -> str:
    """Той самий стан, але про КОНКРЕТНУ покупку.

    Воронка «спершу оплата» питає саме так: аудиту ще немає, а покупка
    вже є. Правило одне на обидва входи — інакше два екрани відповідали
    б на те саме питання по-різному.
    """
    from app.models.billing import BillingEvent

    if purchase is None:
        return PAYMENT_NONE
    if purchase.status is PurchaseStatus.PAID:
        return PAYMENT_PAID
    if purchase.status is PurchaseStatus.REFUNDED:
        # Оплачених покупок могло бути кілька; чинність доступу вирішує
        # не цей рядок, а `guest.is_unlocked`. Тут — доля останньої.
        return PAYMENT_REFUNDED

    failed = await db.scalar(
        select(BillingEvent.id)
        .where(
            BillingEvent.provider == purchase.provider,
            BillingEvent.kind == BillingEventKind.PAYMENT_FAILED,
            BillingEvent.payload["purchase_ref"].astext == str(purchase.id),
        )
        .limit(1)
    )
    return PAYMENT_FAILED if failed is not None else PAYMENT_PROCESSING


async def _latest_for_audit(
    db: AsyncSession, *, organization_id: uuid.UUID, audit_id: uuid.UUID
) -> OneOffPurchase | None:
    row = await db.execute(
        select(OneOffPurchase)
        .where(
            OneOffPurchase.organization_id == organization_id,
            OneOffPurchase.audit_id == audit_id,
        )
        .order_by(OneOffPurchase.created_at.desc())
        .limit(1)
    )
    return row.scalar_one_or_none()


# Скільки останніх незавершених покупок звіряти з провайдером і за який
# час. Не одна й не всі: пояснення — у `awaiting_event`. Вікно потрібне,
# щоб покинута торік каса не коштувала запиту на кожне відкриття
# сторінки; оплата, яку не доставили довше за тиждень, — це вже розмова з
# людиною, а не рядок на екрані.
AWAITING_LOOKBACK = 5
AWAITING_WINDOW = timedelta(days=7)


async def awaiting_event(
    db: AsyncSession, *, organization_id: uuid.UUID
) -> bool:
    """Чи є покупка, за яку провайдер уже отримав гроші, а права ще не видані.

    Права видає ЛИШЕ перевірена подія — це правило тут не порушується й
    порушене бути не може: функція нічого не змінює. Вона відповідає на
    інше питання, на яке кабінет досі мовчав: «я заплатив, чому порожньо».
    Мовчання в цьому місці читається як «гроші зникли».

    Питаємо провайдера про кілька ОСТАННІХ незавершених покупок, а не про
    одну й не про всі. Не про одну: людина відкриває касу, закриває,
    відкриває знову — і оплаченою може бути не остання (саме так і
    сталося: оплата о 16:48, покинута каса о 16:50). Не про всі: покинута
    каса лишає рядок назавжди, і в того, хто відкривав її двадцять разів,
    двадцять запитів на кожне відкриття сторінки коштували б дорожче за
    саму відповідь.
    """
    rows = await db.execute(
        select(OneOffPurchase)
        .where(
            OneOffPurchase.organization_id == organization_id,
            OneOffPurchase.status == PurchaseStatus.PENDING,
            OneOffPurchase.provider_ref.isnot(None),
            OneOffPurchase.created_at >= datetime.now(UTC) - AWAITING_WINDOW,
        )
        .order_by(OneOffPurchase.created_at.desc())
        .limit(AWAITING_LOOKBACK)
    )
    for purchase in rows.scalars():
        adapter = provider_for(purchase.provider)
        if adapter is None:  # pragma: no cover — реєстр статичний
            continue
        try:
            settlement = await adapter.settlement_of(
                transaction_ref=purchase.provider_ref
            )
        except ProviderUnavailable:
            # Провайдер не відповів — це не «не платив». Мовчимо: вигадана
            # обіцянка гірша за відсутню.
            return False
        if settlement is Settlement.PAID:
            return True
    return False


async def charged(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    audit_id: uuid.UUID,
    ask_provider: bool,
) -> bool | None:
    """Чи списано кошти за останню покупку цього аудиту.

    Три відповіді, і третя — чесна: `True`/`False` — знаємо, `None` — ні.

    З наших записів відомо про оплачену покупку (True), повернену (False)
    і касу, яку так і не відкрили (False: транзакції не існує, списувати
    нема з чого). Про відкриту й не закриту касу записи мовчать — події
    від провайдера в такому разі може не бути ніколи, бо закрите без
    оплати вікно не породжує нічого, — і відповідь тут дає лише сам
    провайдер, якщо його попросили (`ask_provider`).

    Це читання не змінює ані покупки, ані права: доступ і далі дає лише
    перевірена подія. Провайдер, який не відповів, — це `None`, а не
    «не списано»: сказати людині «кошти не списано» на підставі
    тайм-ауту означало б продати їй другу покупку за перші гроші.
    """
    latest = await _latest_for_audit(
        db, organization_id=organization_id, audit_id=audit_id
    )
    return await charged_of(db, purchase=latest, ask_provider=ask_provider)


async def charged_of(
    db: AsyncSession, *, purchase: OneOffPurchase | None, ask_provider: bool
) -> bool | None:
    """Те саме питання про конкретну покупку. Див. `charged`."""
    if purchase is None:
        return False
    if purchase.status is PurchaseStatus.PAID:
        return True
    if purchase.status is PurchaseStatus.REFUNDED:
        return False
    if not purchase.provider_ref:
        return False
    if not ask_provider:
        return None

    adapter = provider_for(purchase.provider)
    if adapter is None:  # pragma: no cover — реєстр статичний
        return None
    try:
        settlement = await adapter.settlement_of(transaction_ref=purchase.provider_ref)
    except ProviderUnavailable:
        return None
    if settlement is Settlement.PAID:
        return True
    if settlement is Settlement.UNPAID:
        return False
    return None


__all__ = ["RecordedPurchase", "find", "record", "refund"]


__all__ = [
    "PAYMENT_FAILED",
    "PAYMENT_NONE",
    "PAYMENT_PAID",
    "PAYMENT_PROCESSING",
    "PAYMENT_REFUNDED",
    "OpenedCheckout",
    "ProviderUnavailable",
    "RecordedPurchase",
    "attach_provider_ref",
    "charged",
    "find",
    "find_by_provider_ref",
    "find_pending_for_audit",
    "mark_paid",
    "open_checkout",
    "open_pending",
    "payment_state",
    "record",
    "refund",
]
