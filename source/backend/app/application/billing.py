"""Конвеєр білінгових подій: від перевіреної події до стану підписки.

    подія провайдера
    → перевірка/нормалізація (адаптер, не тут)
    → BillingEvent (журнал, ідемпотентність у базі)
    → доменний перехід (машина станів)
    → стан Subscription
    → права (наявний резолвер, без дублювання тут)

Права цей модуль не чіпає взагалі: він приводить підписку до правильного
стану, а що з цього стану випливає — знає `billing.for_organization`.
Вебхук, який сам вмикає `scheduled_audits = true`, — це два місця правди
про одне право.

## Дві фази, і чому їх дві

Запис події і її обробка розділені комітом. Якби вони були однією
транзакцією, збій обробки відкочував би й сам запис — і подія-невдаха
зникала б без сліду, а «retry» означав би «чекати, чи провайдер
надішле ще раз». Натомість:

    фаза 1: подія лягає в журнал зі статусом received (свій коміт)
    фаза 2: захоплення → перехід → processed (один коміт на обидва)

Падіння другої фази лишає подію зі статусом failed і текстом помилки:
її видно, її можна повторити (`replay_failed`), і повтор не створить
другого переходу — захоплення атомарне, як оренда в планувальника.

## Не по порядку

«Новіше» вирішує час події **в провайдера** (`occurred_at`), а не час
доставки. Подія, старша за вже застосований стан, записується як
`stale`: видима, порахована, не застосована. Це не збій — це
властивість доставки вебхуків, і відкат підписки в старий стан був би
справжньою помилкою, якої тут немає за побудовою.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import guest, purchases
from app.billing import service as billing
from app.billing import state_machine
from app.billing.enums import BillingEventKind, BillingEventStatus, SubscriptionStatus
from app.billing.enums import PurchaseStatus as _PS
from app.billing.providers.base import VerifiedBillingEvent
from app.core.logging import log
from app.models.audit import Audit
from app.models.billing import (
    BillingCustomer,
    BillingEvent,
    Plan,
    PlanPrice,
    Subscription,
    SubscriptionTransition,
)
from app.models.purchase import OneOffPurchase

_K = BillingEventKind
_S = BillingEventStatus


class EventUnprocessable(Exception):
    """Подію неможливо застосувати, і повтор цього не змінить.

    Невідомий прайс, відсутня організація, недозволений перехід — це не
    тимчасові збої, а розбіжності в даних. Подія стає `failed` з цим
    текстом і чекає на людину, а не на retry.
    """


@dataclass(frozen=True, slots=True)
class IngestResult:
    """Що сталося з доставленою подією."""

    event_id: uuid.UUID
    outcome: str  # "processed" | "duplicate" | "stale" | "failed" | "busy"
    error: str = ""


def _now() -> datetime:
    return datetime.now(UTC)


async def ingest(db: AsyncSession, event: VerifiedBillingEvent) -> IngestResult:
    """Прийняти одну перевірену подію. Скільки завгодно разів.

    Перша доставка обробляє, повторні впізнаються базою. Відповідь
    «duplicate» — це успіх, а не помилка: провайдер переслав, бо не
    дочекався нашої відповіді, і чекає 200.
    """
    stored = await _store(db, event)
    if stored is None:
        # Уже в журналі. Якщо оброблена — дублікат; якщо застрягла в
        # failed/received — доставка стає нагодою доробити.
        existing = await _find(db, event)
        if existing is None:  # прибрано паралельним видаленням; неймовірно
            return IngestResult(uuid.uuid4(), "failed", "подія зникла з журналу")
        if existing.status in (_S.PROCESSED, _S.STALE):
            return IngestResult(existing.id, "duplicate")
        return await _process(db, existing.id, event)
    return await _process(db, stored, event)


async def replay_failed(db: AsyncSession, *, limit: int = 50) -> list[IngestResult]:
    """Повторити невдалі події. Безпечно: захоплення те саме, що в ingest.

    Для розслідування й ручного запуску після виправлення даних —
    наприклад, коли невідомий прайс нарешті додали в PlanPrice.
    """
    stmt = (
        select(BillingEvent)
        .where(BillingEvent.status == _S.FAILED)
        .order_by(BillingEvent.occurred_at)
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    results = []
    for row in rows:
        results.append(await _process(db, row.id, _reconstruct(row)))
    return results


# ── фаза 1: журнал ─────────────────────────────────────────────────────────


async def _store(db: AsyncSession, event: VerifiedBillingEvent) -> uuid.UUID | None:
    """Записати подію. `None` — така вже є (унікальність у базі).

    `ON CONFLICT DO NOTHING`, а не «спитати й вставити»: між питанням і
    вставкою влазить другий процес, і рівно так дублікати й народжуються.
    """
    stmt = (
        pg_insert(BillingEvent)
        .values(
            id=uuid.uuid4(),
            provider=event.provider,
            external_event_id=event.external_event_id,
            kind=event.kind.value,
            occurred_at=event.occurred_at,
            received_at=_now(),
            status=_S.RECEIVED,
            subscription_ref=event.subscription_ref,
            customer_ref=event.customer_ref,
            price_ref=event.price_ref,
            organization_id=event.organization_id,
            with_trial=event.with_trial,
            period_start=event.period_start,
            period_end=event.period_end,
            trial_end=event.trial_end,
            cancel_at=event.cancel_at,
            payload=dict(event.payload),
        )
        .on_conflict_do_nothing(index_elements=["provider", "external_event_id"])
        .returning(BillingEvent.id)
    )
    inserted = (await db.execute(stmt)).scalar_one_or_none()
    await db.commit()
    return inserted


async def _find(db: AsyncSession, event: VerifiedBillingEvent) -> BillingEvent | None:
    stmt = select(BillingEvent).where(
        BillingEvent.provider == event.provider,
        BillingEvent.external_event_id == event.external_event_id,
    )
    return (await db.execute(stmt)).scalars().first()


# ── фаза 2: захоплення й перехід ───────────────────────────────────────────

# У колонках enum SQLAlchemy зберігає **імена** членів (`RECEIVED`), а не
# значення (`received`) — сирий SQL мусить порівнювати з тим, що лежить у
# базі насправді. Порівняння зі значеннями тихо не збігалося б ніколи, і
# кожна подія виглядала б «зайнятою кимось іншим».
_CLAIM = text(
    """
    UPDATE billing_events SET status = 'PROCESSING'
     WHERE id = :id AND status IN ('RECEIVED', 'FAILED')
    RETURNING id
    """
)


async def _process(
    db: AsyncSession, event_id: uuid.UUID, event: VerifiedBillingEvent
) -> IngestResult:
    claimed = (await db.execute(_CLAIM, {"id": event_id})).fetchall()
    await db.commit()
    if not claimed:
        # Хтось інший тримає подію просто зараз. Не чіпаємо: його коміт
        # і буде відповіддю, а «busy» для провайдера — той самий 200.
        return IngestResult(event_id, "busy")

    record = await db.get(BillingEvent, event_id)
    if record is None:
        return IngestResult(event_id, "failed", "подія зникла після захоплення")
    try:
        # Перехід — у явному savepoint, а не під голим rollback(). Межа
        # відкоту тоді точна: рівно доменні зміни цієї події, і ні запис
        # у журналі, ні захоплення не зникають разом із ними. Голий
        # rollback відкочує до останнього справжнього коміту — а що ним
        # було, залежить від того, звідки нас викликали.
        async with db.begin_nested():
            outcome = await _apply(db, record, event)
        record.status = _S.PROCESSED if outcome == "processed" else _S.STALE
        record.processed_at = _now()
        record.error = ""
        await db.commit()
        return IngestResult(event_id, outcome)
    except Exception as exc:  # noqa: BLE001 — будь-який збій обробки має стати failed-подією
        # Savepoint уже відкотився; сесія жива, запис журналу на місці.
        record.status = _S.FAILED
        record.error = str(exc)[:2000]
        await db.commit()
        log.warning(
            "billing_event_failed",
            provider=event.provider,
            external_event_id=event.external_event_id,
            kind=event.kind.value,
            error=str(exc),
        )
        return IngestResult(event_id, "failed", str(exc))


_ONE_OFF_KINDS = frozenset({_K.ONE_OFF_PURCHASED, _K.ONE_OFF_REFUNDED})


def _is_one_off(event: VerifiedBillingEvent) -> bool:
    """Чи стосується подія разової покупки, а не підписки.

    `PAYMENT_FAILED` буває в обох світах, і розрізняє їх наш власний
    ідентифікатор у даних події: він є лише там, де ми самі відкривали
    касу разової покупки. Без цієї розвилки невдала оплата гостя пішла б
    машиною станів підписки й шукала б тариф за прайсом, якого в неї
    немає, — тобто чесна відмова платежу виглядала б як наш збій.
    """
    if event.kind in _ONE_OFF_KINDS:
        return True
    return event.kind is _K.PAYMENT_FAILED and bool(event.payload.get("purchase_ref"))


async def _apply_one_off(db: AsyncSession, event: VerifiedBillingEvent) -> str:
    """Покупка або повернення разових аудитів.

    Ідемпотентність тут подвійна й це навмисно: зовнішній шар не пише
    ту саму подію двічі завдяки унікальному ключу події, а сам запис
    покупки ще раз захищений унікальним ключем «провайдер + покупка».
    Перше боронить від повторної доставки, друге — від того, що ту саму
    покупку принесуть під двома різними подіями.

    Організація тут не аргумент, і це суттєво. Разова покупка в
    анонімній воронці не має ані акаунта, ані відображеного покупця:
    провайдер створює свого клієнта сам, у касі, і його ідентифікатор
    ми бачимо вперше саме в цій події. Питати «чия це подія» через
    покупця означало б не мати відповіді жодного разу.

    Тому джерело — наш власний запис покупки, і організацію ми беремо
    з нього. Питання «чия подія» лишається лише там, де запису немає, —
    і тоді на нього справді відповідає відображення покупця.
    """
    if event.kind is _K.PAYMENT_FAILED:
        # Покупка лишається PENDING, і це не пропуск, а рішення. Окремий
        # термінальний стан «не оплачено» зробив би з невдалої спроби
        # блокувач: людина мусила б чекати на нашу дію, щоб спробувати
        # ще раз. Сама подія лежить у журналі — саме з неї екран бере
        # чесне «оплата не пройшла».
        if await _pending_for(db, event) is None:  # pragma: no cover — гейт у _is_one_off
            raise ValueError("невдала оплата без посилання на покупку")
        return "processed"

    if event.kind is _K.ONE_OFF_PURCHASED:
        # Каса, відкрита нами заздалегідь: подія несе НАШ ідентифікатор
        # покупки у власних даних провайдера. Тоді аудит береться з
        # нашого запису, а не з події — інакше підроблені довільні дані
        # називали б, який аудит відкрити.
        correlated = await _pending_for(db, event)
        if correlated is not None:
            return await _confirm_pending(db, event, correlated)

        if not event.quantity or not event.currency or event.amount_minor is None:
            raise ValueError("покупка без кількості або суми не піддається обліку")
        recorded = await purchases.record(
            db,
            organization_id=await _organization_for(db, event),
            provider=event.provider,
            external_id=event.external_event_id,
            quantity=event.quantity,
            currency=event.currency,
            amount_minor=event.amount_minor,
            purchased_at=event.occurred_at,
        )
        # Дві комерційні моделі під одним видом події, і розрізняє їх
        # наявність аудиту в даних події.
        #
        # Без `audit_id` це покупка наперед: кредити чекають на майбутній
        # запуск, і саме так працює кабінет. З `audit_id` — навпаки:
        # робота вже виконана, куплено її повний вигляд. Друге і є
        # анонімна воронка, де платять за те, що вже виміряно.
        audit_ref = event.payload.get("audit_id")
        if audit_ref:
            await _unlock_audit(db, purchase=recorded.purchase, audit_ref=str(audit_ref))
        return "processed"

    # Повернення може посилатися двома способами. Провайдер, у якого
    # подія про повернення вказує на транзакцію, дає `provider_transaction_id`;
    # фейк і старий шлях посилаються на подію покупки її ж ідентифікатором.
    transaction_ref = str(event.payload.get("provider_transaction_id") or "")
    if transaction_ref:
        purchase = await purchases.find_by_provider_ref(
            db, provider=event.provider, provider_ref=transaction_ref
        )
        if purchase is None:
            raise ValueError("повернення посилається на невідому транзакцію")
        await purchases.refund(
            db, provider=event.provider, external_id=purchase.external_id
        )
        return "processed"

    target = str(event.payload.get("purchase_external_id") or "")
    if not target:
        raise ValueError("повернення без посилання на покупку")
    await purchases.refund(db, provider=event.provider, external_id=target)
    return "processed"


async def _pending_for(
    db: AsyncSession, event: VerifiedBillingEvent
) -> OneOffPurchase | None:
    """Покупка, яку ми самі відкрили перед касою, якщо подія її називає.

    `purchase_ref` — те, що ми віддали провайдеру у власних даних і
    отримали назад. Воно ідентифікує наш рядок, але нічого не доводить
    саме по собі: підпис події вже перевірено адаптером, а решту звіряє
    `_confirm_pending`.
    """
    ref = str(event.payload.get("purchase_ref") or "")
    if not ref:
        return None
    try:
        uuid.UUID(ref)
    except ValueError:
        raise ValueError("подія посилається на покупку неіснуючого вигляду") from None
    purchase = await purchases.find(db, provider=event.provider, external_id=ref)
    if purchase is None:
        # Подія називає покупку, якої в нас немає. Це не «нова покупка»:
        # створити її тут означало б дозволити чужим даним призначати
        # нам записи.
        raise ValueError("подія посилається на покупку, якої не існує")
    return purchase


async def _confirm_pending(
    db: AsyncSession, event: VerifiedBillingEvent, purchase: OneOffPurchase
) -> str:
    """PENDING → PAID і відкриття доступу за НАШИМ записом.

    Аудит береться з покупки, а не з події. Довільні дані провайдера —
    кореляція, не повноваження: вони кажуть, ЯКИЙ наш рядок мають на
    увазі, і не кажуть, що саме відкрити.
    """
    if event.amount_minor is None or not event.currency:
        raise ValueError("оплата без суми або валюти не піддається обліку")

    # Покупця провайдера ми бачимо вперше саме тут: у касі його ще не
    # існувало. Без цього запису людина, яка купила пакет, не могла
    # відкрити «Платежі й квитанції» — портал провайдера відкривається за
    # покупцем, а він був відомий лише провайдерові. Прав це не додає:
    # відображення каже, ЧИЯ подія, а не що видати.
    await _remember_customer(db, event, organization_id=purchase.organization_id)

    became_paid = await purchases.mark_paid(
        db,
        purchase=purchase,
        currency=event.currency,
        amount_minor=event.amount_minor,
        purchased_at=event.occurred_at,
        provider_ref=str(event.payload.get("provider_transaction_id") or "") or None,
    )
    if not became_paid and purchase.status is not _PS.PAID:
        # Повернена покупка не оживає: подія про оплату, що прийшла
        # після повернення, не скасовує термінального стану.
        return "stale"

    if not became_paid:
        second = await _second_payment(db, event, purchase)
        if second is not None:
            return second

    if purchase.audit_id is not None:
        await guest.unlock_for_purchase(
            db, purchase=purchase, audit_id=purchase.audit_id
        )
    return "processed"

async def _second_payment(
    db: AsyncSession, event: VerifiedBillingEvent, purchase: OneOffPurchase
) -> str | None:
    """Ще одна транзакція під той самий намір — тобто друге списання.

    Дві вкладки, дві каси, один наш ідентифікатор у довільних даних
    обох. Повторна доставка тієї самої події виглядає звідси однаково,
    і розрізняє їх лише транзакція провайдера.

    Мовчати не можна: людина заплатила двічі, а в нас лежав би один
    рядок — повернути зайве не було б за чим, і повернення єдиної
    покупки забрало б доступ, за який заплачено двічі. Тому друга
    оплата стає власною покупкою на той самий аудит. Правило чинності
    доступу («хоч одна незвернена покупка») робить решту саме.
    """
    transaction = str(event.payload.get("provider_transaction_id") or "")
    if not transaction or not purchase.provider_ref or transaction == purchase.provider_ref:
        return None
    if event.amount_minor is None or not event.currency:  # pragma: no cover
        return None

    recorded = await purchases.record(
        db,
        organization_id=purchase.organization_id,
        provider=event.provider,
        external_id=event.external_event_id,
        quantity=purchase.quantity,
        currency=event.currency,
        amount_minor=event.amount_minor,
        purchased_at=event.occurred_at,
    )
    if recorded.already_known:
        return "duplicate"
    recorded.purchase.provider_ref = transaction
    recorded.purchase.audit_id = purchase.audit_id
    await db.flush()
    log.warning(
        "billing.double_payment",
        purchase_id=str(purchase.id),
        second_purchase_id=str(recorded.purchase.id),
        audit_id=str(purchase.audit_id) if purchase.audit_id else None,
    )
    if purchase.audit_id is not None:
        await guest.unlock_for_purchase(
            db, purchase=recorded.purchase, audit_id=purchase.audit_id
        )
    return "processed"


async def _unlock_audit(
    db: AsyncSession, *, purchase: OneOffPurchase, audit_ref: str
) -> None:
    """Відкрити повний вигляд аудиту за покупкою.

    Аудит мусить належати тій самій організації, що й покупка. Інакше
    оплата в одному орендарі відкривала б чужий аудит в іншому — а
    ідентифікатор аудиту не є секретом, він лише називає ресурс.
    """
    try:
        audit_id = uuid.UUID(audit_ref)
    except ValueError as exc:
        raise ValueError("подія посилається на аудит, якого не існує") from exc

    owner = await db.scalar(select(Audit.organization_id).where(Audit.id == audit_id))
    if owner is None:
        raise ValueError("подія посилається на аудит, якого не існує")
    if owner != purchase.organization_id:
        raise ValueError("аудит належить іншій організації, ніж покупка")

    # Покупка теж памʼятає аудит: без цього «за що заплатили» довелося б
    # відновлювати через рядок розблокування, який може бути почищений
    # разом з аудитом, а покупка — ні.
    purchase.audit_id = audit_id
    await guest.unlock_for_purchase(db, purchase=purchase, audit_id=audit_id)


async def _apply(db: AsyncSession, record: BillingEvent, event: VerifiedBillingEvent) -> str:
    """Доменний перехід. Повертає processed | stale, кидає на розбіжності."""
    # Разова покупка не проходить машиною станів підписки: у неї немає
    # ані стану, ані періоду, ані плану. Розвилка тут, а не всередині —
    # інакше половина функції звірялася б із підпискою, якої не існує.
    if _is_one_off(event):
        return await _apply_one_off(db, event)

    organization_id = await _organization_for(db, event)
    subscription = await _subscription_for(db, event, organization_id)

    if subscription is None:
        if event.kind is _K.SUBSCRIPTION_CANCELLED:
            # Скасування підписки, якої ми не знаємо, — нічого скасовувати.
            # Записати й пройти повз: обидва боки згодні, що її немає.
            return "processed"
        # Друга ОДНОЧАСНА підписка на ту саму організацію — розбіжність,
        # а не подія до застосування: два наділи на один період означали
        # б подвійні права. Та сама підписка провайдера сюди не потрапляє
        # (її знайшов би `_subscription_for` — повторна доставка лишається
        # ідемпотентною); термінальна попередня не блокує нову. Подія
        # стає failed зі стабільним кодом і чекає на людину, а частковий
        # unique-індекс бази лишається другою лінією оборони.
        concurrent = await _non_terminal_of(db, organization_id)
        if concurrent is not None:
            raise EventUnprocessable(
                "subscription.duplicate: організація вже має незавершену "
                f"підписку {concurrent.provider_subscription_id!r}, а подія "
                f"називає іншу ({event.subscription_ref!r})"
            )
        subscription = Subscription(
            organization_id=organization_id,
            plan_id=await _plan_for(db, event),
            status=SubscriptionStatus.INACTIVE,
            provider=event.provider,
            provider_subscription_id=event.subscription_ref,
        )
        db.add(subscription)
        await db.flush()

    # Не по порядку: старіша за застосоване — записуємо, не застосовуємо.
    seen = subscription.provider_updated_at
    if seen is not None and event.occurred_at <= seen:
        return "stale"

    target = state_machine.next_status(
        subscription.status, event.kind, with_trial=event.with_trial
    )

    transition = SubscriptionTransition(
        subscription_id=subscription.id,
        organization_id=subscription.organization_id,
        from_status=subscription.status,
        to_status=target,
        from_plan_id=subscription.plan_id,
        to_plan_id=subscription.plan_id,
        effective_at=event.occurred_at,
        billing_event_id=record.id,
    )

    if event.kind is _K.PLAN_CHANGED:
        transition.to_plan_id = await _plan_for(db, event)
        subscription.plan_id = transition.to_plan_id

    if event.kind is _K.PAYMENT_FAILED:
        billing.enter_past_due(subscription, at=event.occurred_at)
    else:
        subscription.status = target
        if target is not SubscriptionStatus.PAST_DUE:
            subscription.grace_until = None

    if event.kind is _K.CANCELLATION_SCHEDULED:
        subscription.cancel_at_period_end = True
    if event.kind in (_K.SUBSCRIPTION_STARTED, _K.SUBSCRIPTION_RENEWED, _K.PAYMENT_RECOVERED):
        subscription.cancel_at_period_end = False

    period_moved = (
        event.period_start is not None
        and event.period_start != subscription.current_period_start
    )
    if event.period_start is not None:
        subscription.current_period_start = event.period_start
    if event.period_end is not None:
        subscription.current_period_end = event.period_end
    if event.trial_end is not None:
        subscription.trial_end = event.trial_end

    # Наділ періоду знімкується з тарифу рівно тоді, коли міняється те,
    # до чого він прив'язаний: почався новий період, клієнт перейшов на
    # інший тариф, або зліпка ще не було (підписка старша за поле).
    # Редагування рядка тарифу адміністратором сюди НЕ потрапляє — саме
    # тому воно й не переписує вже виданого наділу.
    if period_moved or event.kind is _K.PLAN_CHANGED or subscription.period_allocation is None:
        await _snapshot_period_allocation(db, subscription, at=event.occurred_at)

    subscription.provider_updated_at = event.occurred_at
    if subscription.provider_subscription_id is None and event.subscription_ref:
        subscription.provider_subscription_id = event.subscription_ref

    transition.period_start = subscription.current_period_start
    transition.period_end = subscription.current_period_end
    transition.grace_until = subscription.grace_until
    transition.cancel_at_period_end = subscription.cancel_at_period_end
    db.add(transition)
    await db.flush()
    return "processed"


async def _snapshot_period_allocation(
    db: AsyncSession, subscription: Subscription, *, at: datetime
) -> None:
    """Зафіксувати комерційний наділ періоду з тарифу — зараз.

    Беруться лише ключі `PERIOD_ALLOCATION_KEYS`: це те, що клієнт
    отримує НА період (кількість аудитів, кількість перевірок
    присутності). Решта прав лишається живою — зміна дозволеної
    кількості сторінок діє одразу, бо це поведінка продукту, а не
    виданий наділ.

    `None` у значенні — законний «безліміт» аудитів, тому перенесення
    йде за наявністю ключа, а не за істинністю значення.
    """
    from app.billing import entitlements

    plan = await db.get(Plan, subscription.plan_id)
    values = dict(plan.entitlements or {}) if plan is not None else {}
    subscription.period_allocation = {
        **{
            key: values[key]
            for key in entitlements.PERIOD_ALLOCATION_KEYS
            if key in values
        },
        "plan_code": plan.code if plan is not None else None,
        "captured_at": at.isoformat(),
    }


# ── розвʼязання наших сутностей із зовнішніх посилань ─────────────────────


async def _remember_customer(
    db: AsyncSession, event: VerifiedBillingEvent, *, organization_id: uuid.UUID
) -> None:
    """Запамʼятати покупця провайдера за організацією, якщо ще не знаємо.

    Разова покупка резолвиться через НАШ запис, тож `_organization_for`
    на цьому шляху не викликається — і відображення покупця не зʼявлялось
    ніколи. Наслідок бачив клієнт: пакет оплачено, а квитанції не
    відкриваються, бо портал провайдера адресується покупцем.
    """
    if not event.customer_ref:
        return
    known = (
        await db.execute(
            select(BillingCustomer).where(
                BillingCustomer.provider == event.provider,
                BillingCustomer.provider_customer_id == event.customer_ref,
            )
        )
    ).scalars().first()
    if known is not None:
        return
    db.add(
        BillingCustomer(
            organization_id=organization_id,
            provider=event.provider,
            provider_customer_id=event.customer_ref,
        )
    )
    await db.flush()


async def _organization_for(db: AsyncSession, event: VerifiedBillingEvent) -> uuid.UUID:
    """Чия це подія. Посилання покупця → наша організація.

    Подія з organization_id (checkout несе наші custom-дані) заразом
    створює відображення покупця — так наступні події знайдуть
    організацію вже без підказки.
    """
    if event.customer_ref:
        stmt = select(BillingCustomer).where(
            BillingCustomer.provider == event.provider,
            BillingCustomer.provider_customer_id == event.customer_ref,
        )
        existing = (await db.execute(stmt)).scalars().first()
        if existing is not None:
            return existing.organization_id
    if event.organization_id is not None:
        if event.customer_ref:
            db.add(
                BillingCustomer(
                    organization_id=event.organization_id,
                    provider=event.provider,
                    provider_customer_id=event.customer_ref,
                )
            )
            await db.flush()
        return event.organization_id
    raise EventUnprocessable(
        f"не знаємо, чия це подія: покупець {event.customer_ref!r} не відображений "
        "на організацію, і в події немає organization_id"
    )


async def _non_terminal_of(
    db: AsyncSession, organization_id: uuid.UUID
) -> Subscription | None:
    """Незавершена підписка організації — межа «одна за раз»."""
    from app.billing.service import non_terminal_subscription

    return await non_terminal_subscription(db, organization_id=organization_id)


async def _subscription_for(
    db: AsyncSession, event: VerifiedBillingEvent, organization_id: uuid.UUID
) -> Subscription | None:
    if event.subscription_ref:
        stmt = select(Subscription).where(
            Subscription.provider == event.provider,
            Subscription.provider_subscription_id == event.subscription_ref,
        )
        found = (await db.execute(stmt)).scalars().first()
        if found is not None:
            return found
    return None


async def _plan_for(db: AsyncSession, event: VerifiedBillingEvent) -> uuid.UUID:
    """Прайс провайдера → наш тариф. Через PlanPrice, не через хардкод."""
    if not event.price_ref:
        raise EventUnprocessable("подія без прайсу: нема з чого визначити тариф")
    stmt = select(PlanPrice).where(
        PlanPrice.provider == event.provider,
        PlanPrice.provider_price_id == event.price_ref,
    )
    price = (await db.execute(stmt)).scalars().first()
    if price is None:
        raise EventUnprocessable(
            f"прайс {event.price_ref!r} провайдера {event.provider!r} не відображений "
            "на жоден тариф; додайте PlanPrice і повторіть подію"
        )
    return price.plan_id


def _reconstruct(record: BillingEvent) -> VerifiedBillingEvent:
    """Подія з журналу — для повтору без участі провайдера."""
    return VerifiedBillingEvent(
        provider=record.provider,
        external_event_id=record.external_event_id,
        kind=BillingEventKind(record.kind),
        occurred_at=record.occurred_at,
        subscription_ref=record.subscription_ref,
        customer_ref=record.customer_ref,
        price_ref=record.price_ref,
        organization_id=record.organization_id,
        with_trial=record.with_trial,
        period_start=record.period_start,
        period_end=record.period_end,
        trial_end=record.trial_end,
        cancel_at=record.cancel_at,
        payload=dict(record.payload or {}),
    )


__all__ = ["EventUnprocessable", "IngestResult", "ingest", "replay_failed"]


class PortalUnavailable(Exception):
    """Провайдер не відкрив портал: права ключа, мережа, його збій.

    Окремо від «профілю немає» (`None`): у першому випадку працювати
    треба нам, у другому людина просто ще не платила. Тип — тутешній, бо
    шар API не має знати класів провайдера; переклад робить application.
    """


async def portal_url(
    db: AsyncSession, *, organization_id: uuid.UUID
) -> str | None:
    """Посилання на хостований портал провайдера або None без профілю."""
    from app.billing import catalog as billing_catalog
    from app.billing.registry import provider_for as _provider_for

    row = await db.execute(
        select(BillingCustomer).where(
            BillingCustomer.organization_id == organization_id
        )
    )
    customer = row.scalar_one_or_none()
    if customer is None:
        return None
    adapter = _provider_for(billing_catalog.current_provider())
    if adapter is None:
        return None
    from app.billing.providers import ProviderUnavailable

    try:
        return await adapter.create_portal_session(
            customer_ref=customer.provider_customer_id
        )
    except ProviderUnavailable as exc:
        raise PortalUnavailable(str(exc)) from exc
