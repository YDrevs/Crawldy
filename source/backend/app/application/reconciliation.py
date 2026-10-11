"""Зарахування оплат, про які провайдер не повідомив.

Правило продукту незмінне: доступ відкриває перевірена подія провайдера.
Але подія може не дійти — збій доставки, недоступний сервер, помилка
адреси, — і тоді гроші списані, а прав немає. Досі це виправлялось руками
в базі; тепер є службова дія.

Три речі, які роблять її чесною:

* **Питаємо провайдера, а не людину.** Зарахування можливе рівно тоді,
  коли провайдер САМ каже, що транзакцію оплачено. Кнопка не має
  повноважень видати доступ; вона має повноваження ЗАПИТАТИ.
* **Сума береться з відповіді провайдера**, коли він її називає. Наш
  рядок каже, скільки ми хотіли; квитанція клієнта — скільки взяли.
* **Слід лишається.** Кожне зарахування пише подію в журнал білінгу з
  іменем того, хто його зробив.

Повторна доставка справжньої події після цього нічого не подвоює:
покупка вже PAID, а транзакція та сама.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import guest, purchases
from app.billing import catalog
from app.billing.enums import BillingEventKind, BillingEventStatus, PurchaseStatus
from app.billing.providers import ProviderUnavailable, Settlement
from app.billing.registry import provider_for
from app.identity.enums import OrganizationKind
from app.models.billing import BillingEvent
from app.models.commerce import CommercialOffer
from app.models.identity import Membership, Organization, User
from app.models.purchase import OneOffPurchase


class NotPending(Exception):
    """Покупка вже в термінальному стані: зараховувати нема чого."""


class NotSettled(Exception):
    """Провайдер не підтверджує оплату — зараховувати не можна."""


@dataclass(frozen=True, slots=True)
class Verified:
    """Відповідь провайдера про транзакцію."""

    settlement: Settlement
    amount_minor: int | None
    currency: str | None
    invoice: str | None
    detail: str
    #: Покупець у провайдера й його пошта, якщо провайдер їх віддає. Для
    #: гостьової покупки це єдина ідентичність людини, яка заплатила.
    customer_ref: str | None = None
    email: str | None = None


async def pending(
    db: AsyncSession,
    *,
    limit: int = 100,
    include_closed: bool = False,
    include_unspent: bool = False,
) -> list[dict[str, Any]]:
    """Незараховані покупки: наші дані, без жодного запиту до провайдера.

    Провайдера питає окрема дія: перелік має відкриватися миттєво й не
    коштувати запиту на кожен рядок.

    `include_closed` додає погашені каси. Вони не зникли — вони лише
    прибрані з робочого переліку, і людина мусить мати змогу на них
    подивитися: інакше «куди все зникло» лишається без відповіді.

    `include_unspent` додає оплачені покупки анонімної воронки, на які
    ще не запущено перевірку. Це третій стан, а не різновид перших двох:
    гроші прийшли й зараховані кредитами, але сайт людина ще не назвала.
    Ані «незарахована оплата», ані «виданий доступ» його не описують, і
    без окремого перемикача він не видно ніде — а це саме той стан, у
    якому оператор мусить бачити гроші.
    """
    # Каса провайдера, який більше не обслуговує оплату: нову оплату через
    # нього ми не приймаємо, і його «не знаю» не має читатися як мовчання
    # чинної каси.
    active = catalog.current_provider()
    states = (
        [PurchaseStatus.PENDING, PurchaseStatus.ABANDONED]
        if include_closed
        else [PurchaseStatus.PENDING]
    )
    # Назва продукту з каталогу: у рядку лежить код (`pack`), а читає це
    # людина. Зниклу пропозицію показуємо кодом — інакше рядок став би
    # порожнім там, де саме назва й потрібна.
    names = {
        code: name
        for code, name in (
            await db.execute(select(CommercialOffer.code, CommercialOffer.display_name))
        ).all()
    }
    rows = (
        await db.execute(
            select(OneOffPurchase, Organization.name, User.email)
            .join(Organization, Organization.id == OneOffPurchase.organization_id)
            .join(
                Membership,
                Membership.organization_id == OneOffPurchase.organization_id,
                isouter=True,
            )
            .join(User, User.id == Membership.user_id, isouter=True)
            .where(
                or_(
                    and_(
                        OneOffPurchase.status.in_(states),
                        OneOffPurchase.provider_ref.isnot(None),
                    ),
                    # Оплачено, але сайт ще не названий. Лише гостьова
                    # воронка: у кабінеті така покупка — це поповнення
                    # балансу, тобто нормальний кінцевий стан.
                    and_(
                        true() if include_unspent else false(),
                        OneOffPurchase.status == PurchaseStatus.PAID,
                        OneOffPurchase.audit_id.is_(None),
                        Organization.kind.in_(
                            [OrganizationKind.GUEST, OrganizationKind.CLAIMED]
                        ),
                    ),
                )
            )
            .order_by(OneOffPurchase.created_at.desc())
            .limit(limit)
        )
    ).all()
    return [
        {
            "purchase_id": str(purchase.id),
            "status": purchase.status.value,
            "created_at": purchase.created_at.isoformat(),
            "organization": organization,
            # Гостьова покупка не має ані акаунта, ані пошти: людина
            # платить, не реєструючись. Порожнє поле — це стан, а не
            # прогалина в даних.
            "email": email,
            "offer_code": purchase.offer_code,
            "product": (
                names.get(purchase.offer_code or "") or purchase.offer_code
            ),
            "audit_id": str(purchase.audit_id) if purchase.audit_id else None,
            "quantity": purchase.quantity,
            # Сума САМОЇ покупки заповнюється лише оплатою: до неї в рядку
            # нулі. Тому показуємо ціну зі зліпка умов — те, що людина
            # бачила, коли відкривала касу. Скільки провайдер узяв
            # насправді, каже звірка.
            **_ordered_amount(purchase),
            "provider": purchase.provider,
            "foreign": purchase.provider != active,
            "transaction_ref": purchase.provider_ref,
        }
        for purchase, organization, email in rows
    ]


def _ordered_amount(purchase: OneOffPurchase) -> dict[str, Any]:
    """Ціна замовленого: з покупки, якщо вона вже має суму, інакше зі зліпка."""
    if purchase.amount_minor and purchase.currency:
        return {"currency": purchase.currency, "amount_minor": purchase.amount_minor}
    snapshot = purchase.offer_snapshot or {}
    amount = snapshot.get("display_amount_minor")
    return {
        "currency": str(snapshot.get("currency") or "") or None,
        "amount_minor": int(amount) if isinstance(amount, int) else None,
    }


async def _load(db: AsyncSession, purchase_id: uuid.UUID) -> OneOffPurchase:
    purchase = (
        await db.execute(
            select(OneOffPurchase).where(OneOffPurchase.id == purchase_id)
        )
    ).scalar_one_or_none()
    if purchase is None:
        raise NotPending("покупки не існує")
    # Погашену зарахувати МОЖНА: це і є оживлення каси, за яку заплатили
    # після гасіння. Термінальні стани (оплачено, повернено) — ні.
    if purchase.status not in (PurchaseStatus.PENDING, PurchaseStatus.ABANDONED):
        raise NotPending(f"покупка вже {purchase.status.value}")
    if not purchase.provider_ref:
        raise NotPending("покупка не має транзакції провайдера")
    return purchase


async def _ask_provider(provider: str, transaction_ref: str) -> Verified:
    """Питання до провайдера й нічого більше.

    Без сесії бази навмисно: звірка всього переліку йде паралельно, а
    сесія SQLAlchemy одночасних викликів не переживає.
    """
    adapter = provider_for(provider)
    if adapter is None:  # pragma: no cover — реєстр статичний
        return Verified(
            Settlement.UNKNOWN, None, None, None,
            f"провайдер {provider} не зареєстрований",
        )
    try:
        found = await adapter.settlement_report(transaction_ref=transaction_ref)
    except ProviderUnavailable as exc:
        # Провайдер не відповів — це «не знаємо», а не «не оплачено».
        return Verified(Settlement.UNKNOWN, None, None, None, str(exc))
    return Verified(
        found.settlement, found.amount_minor, found.currency, found.invoice, "",
        customer_ref=found.customer_ref, email=found.email,
    )


async def verify(db: AsyncSession, *, purchase_id: uuid.UUID) -> Verified:
    """Що каже провайдер про цю транзакцію. Нічого не змінює."""
    purchase = await _load(db, purchase_id)
    assert purchase.provider_ref is not None
    return await _ask_provider(purchase.provider, purchase.provider_ref)


# Скільки транзакцій питаємо одночасно. Провайдер не любить залпів, а
# послідовні тридцять запитів — це півхвилини очікування на екрані.
_VERIFY_AT_ONCE = 5


async def verify_all(
    db: AsyncSession, *, limit: int = 100, include_closed: bool = False
) -> dict[str, Verified]:
    """Звірити з провайдером усі незараховані покупки одразу.

    Заради цього дія й існує. Кожне натискання «Купити» лишає рядок,
    навіть коли людина не заплатила, тож у переліку майже все — покинуті
    каси. Шукати серед них оплачену по одній означає тридцять натискань
    заради однієї відповіді.
    """
    # Спершу ЧИТАЄМО базу цілком, потім питаємо провайдера. Сесія тут
    # більше не потрібна, і паралельні запити її не чіпають.
    # Звірка — читання, тож вона доречна й на погашених касах: саме так
    # видно ту, за яку заплатили вже після гасіння.
    rows = await pending(db, limit=limit, include_closed=include_closed)
    gate = asyncio.Semaphore(_VERIFY_AT_ONCE)

    async def ask(row: dict[str, Any]) -> tuple[str, Verified]:
        async with gate:
            answer = await _ask_provider(row["provider"], row["transaction_ref"])
        return str(row["purchase_id"]), answer

    return dict(await asyncio.gather(*(ask(row) for row in rows)))


async def sweep(
    db: AsyncSession, *, apply_to: list[uuid.UUID] | None = None, limit: int = 200
) -> dict[str, Any]:
    """Погасити каси, за які не заплатили, щоб перелік не заростав.

    Гасимо СТАНОМ, а не видаленням: `audit_unlocks.purchase_id` стоїть на
    ON DELETE RESTRICT (рядок із відкритим доступом не видалився б узагалі),
    а головне — оплата, що прийде пізніше, мусить знайти свій запис.
    Погашена каса оживає при оплаті, тож вікна «зачекати тиждень» не
    потрібно: помилка тут коштує рядок у списку, а не гроші клієнта.

    Гасяться дві категорії:

    * провайдер сказав саме «не оплачено» — пряма відповідь;
    * покупка належить провайдеру, який більше не обслуговує касу:
      нову оплату через нього ми не приймаємо, а стара, якщо раптом
      прийде, оживить запис.

    «Не знаємо» не гаситься ніколи: мовчання провайдера — не відповідь.

    `apply_to` — ідентифікатори з попереднього підрахунку. Гасяться лише
    ті з них, що й ЗАРАЗ підпадають під правило: набір може звузитись,
    але не вирости, тож підпис на кнопці не стає обіцянкою, якої дія не
    виконає.
    """
    active = catalog.current_provider()
    rows = (
        await db.execute(
            select(OneOffPurchase)
            .where(
                OneOffPurchase.status == PurchaseStatus.PENDING,
                OneOffPurchase.provider_ref.isnot(None),
            )
            .order_by(OneOffPurchase.created_at)
            .limit(limit)
        )
    ).scalars().all()
    pending_total = int(
        (
            await db.execute(
                select(func.count())
                .select_from(OneOffPurchase)
                .where(OneOffPurchase.status == PurchaseStatus.PENDING)
            )
        ).scalar_one()
    )

    foreign = [p for p in rows if p.provider != active]
    ours = [p for p in rows if p.provider == active]
    gate = asyncio.Semaphore(_VERIFY_AT_ONCE)

    async def ask(purchase: OneOffPurchase) -> tuple[OneOffPurchase, Verified]:
        async with gate:
            assert purchase.provider_ref is not None
            return purchase, await _ask_provider(purchase.provider, purchase.provider_ref)

    checked = await asyncio.gather(*(ask(purchase) for purchase in ours))
    unpaid = [p for p, answer in checked if answer.settlement is Settlement.UNPAID]
    paid = sum(1 for _, a in checked if a.settlement is Settlement.PAID)
    unknown = sum(1 for _, a in checked if a.settlement is Settlement.UNKNOWN)

    doomed = unpaid + foreign
    if apply_to is not None:
        wanted = set(apply_to)
        doomed = [p for p in doomed if p.id in wanted]
        for purchase in doomed:
            await purchases.abandon(db, purchase=purchase)
        await db.flush()

    return {
        "swept": len(doomed) if apply_to is not None else 0,
        "sweepable": len(doomed) if apply_to is None else 0,
        "ids": [str(p.id) for p in doomed] if apply_to is None else [],
        "pending_total": pending_total,
        "checked": len(checked),
        "unpaid": len(unpaid),
        "foreign": len(foreign),
        "paid": paid,
        "unknown": unknown,
        "looked_at": len(rows),
    }


async def _refuse_if_transaction_used(
    db: AsyncSession, purchase: OneOffPurchase
) -> None:
    """Та сама транзакція не оплачує двох покупок.

    Провайдер відповідає про ТРАНЗАКЦІЮ, а не про наш рядок, і сказав би
    «оплачено» стільки разів, скільки разів його спитати. Дві вкладки
    лишають два наші рядки на одну оплату; зарахувати обидва означало б
    видати вдвічі більше, ніж куплено.
    """
    twin = (
        await db.execute(
            select(OneOffPurchase).where(
                OneOffPurchase.provider == purchase.provider,
                OneOffPurchase.provider_ref == purchase.provider_ref,
                OneOffPurchase.id != purchase.id,
                OneOffPurchase.status != PurchaseStatus.PENDING,
            )
        )
    ).scalars().first()
    if twin is not None:
        raise NotSettled(
            f"цю транзакцію вже зараховано покупкою {twin.id} ({twin.status.value})"
        )


async def credit(
    db: AsyncSession, *, purchase_id: uuid.UUID, actor_id: uuid.UUID | None
) -> dict[str, Any]:
    """Зарахувати покупку, якщо провайдер підтверджує оплату.

    Питаємо провайдера ще раз, а не віримо попередній звірці: між
    натисканнями могло минути скільки завгодно, а гроші могли повернути.
    """
    purchase = await _load(db, purchase_id)
    await _refuse_if_transaction_used(db, purchase)
    answer = await verify(db, purchase_id=purchase_id)
    if answer.settlement is not Settlement.PAID:
        raise NotSettled(answer.detail or answer.settlement.value)

    at = datetime.now(UTC)
    became_paid = await purchases.mark_paid(
        db,
        purchase=purchase,
        # Сума провайдера головніша за нашу: у квитанції клієнта стоїть
        # саме вона (податок, знижка, валюта каси).
        currency=answer.currency or purchase.currency,
        amount_minor=(
            answer.amount_minor if answer.amount_minor is not None else purchase.amount_minor
        ),
        purchased_at=at,
    )
    if purchase.audit_id is not None:
        await guest.unlock_for_purchase(
            db, purchase=purchase, audit_id=purchase.audit_id
        )

    db.add(
        BillingEvent(
            provider=purchase.provider,
            # Не подія провайдера, і вигляд ідентифікатора це каже прямо.
            external_event_id=f"reconciled:{purchase.id}",
            kind=BillingEventKind.ONE_OFF_PURCHASED,
            occurred_at=at,
            processed_at=at,
            status=BillingEventStatus.PROCESSED,
            organization_id=purchase.organization_id,
            payload={
                "manual_reconciliation": True,
                "reconciled_by": str(actor_id) if actor_id else None,
                "provider_transaction_id": purchase.provider_ref,
                "invoice": answer.invoice,
                # Пошта з боку провайдера. Для гостьової покупки це
                # єдиний спосіб згодом сказати, кому саме зараховано.
                "customer_ref": answer.customer_ref,
                "email": answer.email,
            },
        )
    )
    await db.flush()
    return {
        "purchase_id": str(purchase.id),
        "credited": became_paid,
        "quantity": purchase.quantity,
        "currency": purchase.currency,
        "amount_minor": purchase.amount_minor,
        "invoice": answer.invoice,
        "email": answer.email,
    }


__all__ = [
    "NotPending",
    "NotSettled",
    "Verified",
    "credit",
    "pending",
    "sweep",
    "verify",
    "verify_all",
]
