"""Що організація може робити просто зараз.

Єдине місце, де тариф перетворюється на права. Решта коду питає
результат, а не назву тарифу.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import entitlements
from app.billing.entitlements import EntitlementSet
from app.billing.enums import SubscriptionStatus
from app.core.config import settings
from app.models.billing import EntitlementOverride, Plan, PlanPrice, Subscription

# Тариф за замовчуванням. Організація без підписки не лишається без
# набору прав — вона отримує безкоштовний. Різниця принципова: `None`
# змусив би кожну перевірку в коді окремо обробляти відсутність, і
# половина забула б.
FREE_PLAN_CODE = "free"


def _now() -> datetime:
    return datetime.now(UTC)


async def non_terminal_subscription(
    db: AsyncSession, *, organization_id: uuid.UUID
) -> Subscription | None:
    """Підписка, яка ще не завершилась, — хай що вона зараз дає.

    Ширше за `active_subscription` навмисно: пауза, прострочена грація
    чи ще не активований рядок не дають прав, але підписка ІСНУЄ, і
    друга поруч із нею — це два наділи на одну організацію. Термінальний
    стан один — CANCELLED (`state_machine.is_terminal`), і лише після
    нього нова підписка доречна.
    """
    from app.billing.state_machine import is_terminal

    stmt = select(Subscription).where(
        Subscription.organization_id == organization_id,
        Subscription.status.notin_(
            [status for status in SubscriptionStatus if is_terminal(status)]
        ),
    )
    return (await db.execute(stmt)).scalars().first()


async def active_subscription(
    db: AsyncSession, *, organization_id: uuid.UUID
) -> Subscription | None:
    """Підписка, яка зараз щось дає. Прострочена грація вже не дає."""
    stmt = select(Subscription).where(
        Subscription.organization_id == organization_id,
        Subscription.status.in_(
            (
                SubscriptionStatus.TRIALING,
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.PAST_DUE,
            )
        ),
    )
    record = (await db.execute(stmt)).scalars().first()
    if record is None:
        return None
    if record.status is SubscriptionStatus.PAST_DUE and _has_run_out_of_grace(record):
        return None
    return record


def grace_deadline(record: Subscription) -> datetime:
    """Доки діють права після невдалого списання.

    Строк проставляється явно при переході в `past_due`
    (`enter_past_due`). Обчислення тут — запобіжник для підписок, які
    потрапили в цей стан повз наш код: у продукті не має бути стану
    «права діють невідомо доки».
    """
    if record.grace_until is not None:
        return record.grace_until
    days = max(0, settings.billing_past_due_grace_days)
    return (record.current_period_end or _now()) + timedelta(days=days)


def _has_run_out_of_grace(record: Subscription) -> bool:
    """Грація скінчилась.

    Стан у базі при цьому лишається `past_due`: перевести його в
    `cancelled` має провайдер своєю подією, а не ми здогадкою. Наше
    рішення — не давати прав, і воно оборотне.
    """
    return grace_deadline(record) <= _now()


def enter_past_due(record: Subscription, *, at: datetime | None = None) -> datetime:
    """Перевести підписку в `past_due`, проставивши строк грації явно.

    Викликається обробником події провайдера. Строк рахується від
    моменту невдалого списання, а не від кінця періоду: платіж міг не
    пройти й посеред нього.
    """
    moment = at or _now()
    days = max(0, settings.billing_past_due_grace_days)
    record.status = SubscriptionStatus.PAST_DUE
    record.grace_until = moment + timedelta(days=days)
    return record.grace_until


async def _free_plan(db: AsyncSession) -> Plan | None:
    stmt = select(Plan).where(Plan.code == FREE_PLAN_CODE)
    return (await db.execute(stmt)).scalars().first()


async def _overrides(db: AsyncSession, *, organization_id: uuid.UUID) -> dict[str, object]:
    """Індивідуальні винятки, у яких не вийшов строк."""
    stmt = select(EntitlementOverride).where(
        EntitlementOverride.organization_id == organization_id
    )
    out: dict[str, object] = {}
    for record in (await db.execute(stmt)).scalars().all():
        if record.expires_at is not None and record.expires_at <= _now():
            continue
        # Значення лежить у JSONB як {"value": ...}: голе число чи булеве
        # значення в jsonb-колонці читалося б по-різному залежно від
        # драйвера, а обгортка робить формат однозначним.
        out[record.key] = record.value.get("value")
    return out


async def for_organization(db: AsyncSession, *, organization_id: uuid.UUID) -> EntitlementSet:
    """Права організації просто зараз.

    Порядок: дефолт → тариф активної підписки (або безкоштовний) →
    наділ поточного періоду → індивідуальні винятки.

    Наділ періоду — зліпок кількісних ключів тарифу, зроблений у момент
    виставлення періоду. Він перекриває живий тариф, щоб редагування
    тарифу адміністратором посеред періоду не переписувало вже виданого;
    індивідуальні винятки лишаються згори — вони і є механізм «змінити
    саме цій організації просто зараз».
    """
    subscription = await active_subscription(db, organization_id=organization_id)
    plan = subscription.plan if subscription is not None else await _free_plan(db)
    overrides = await _overrides(db, organization_id=organization_id)

    plan_values = dict(plan.entitlements) if plan else None
    if plan_values is not None and subscription is not None:
        allocation = _current_period_allocation(subscription)
        plan_values.update(allocation)

    return entitlements.resolve(
        plan_code=plan.code if plan else None,
        plan_values=plan_values,
        overrides=overrides,
    )


def _current_period_allocation(subscription: Subscription) -> dict[str, object]:
    """Наділ періоду, якщо він виданий і період ще триває.

    `None` у значенні — законний «безліміт», тож перенесення йде за
    наявністю ключа, а не за істинністю. Період, що вже скінчився, надолу
    не дає: тоді діє живий тариф — як і для підписок, старших за поле.
    """
    stored = subscription.period_allocation
    if not stored:
        return {}
    moment = _now()
    if (
        subscription.current_period_start is None
        or subscription.current_period_end is None
        or not (subscription.current_period_start <= moment < subscription.current_period_end)
    ):
        return {}
    return {
        key: stored[key]
        for key in entitlements.PERIOD_ALLOCATION_KEYS
        if key in stored
    }


async def grant_override(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    key: str,
    value: object,
    reason: str,
    expires_at: datetime | None = None,
    created_by_user_id: uuid.UUID | None = None,
) -> EntitlementOverride:
    """Індивідуальний виняток. Причина обов'язкова.

    Виняток без причини через рік неможливо ні пояснити, ні зняти — і
    він живе вічно саме тому.
    """
    if key not in entitlements.KEYS:
        raise entitlements.UnknownEntitlement(key)
    if not reason.strip():
        raise ValueError("виняток без причини не створюється")
    problems = entitlements.validate({key: value})
    if problems:
        raise ValueError("; ".join(problems))

    stmt = select(EntitlementOverride).where(
        EntitlementOverride.organization_id == organization_id,
        EntitlementOverride.key == key,
    )
    record = (await db.execute(stmt)).scalars().first()
    if record is None:
        record = EntitlementOverride(organization_id=organization_id, key=key)
        db.add(record)
    record.value = {"value": value}
    record.reason = reason.strip()
    record.expires_at = expires_at
    record.created_by_user_id = created_by_user_id
    await db.flush()
    return record


async def list_public_plans(db: AsyncSession) -> list[Plan]:
    stmt = (
        select(Plan)
        .where(Plan.is_public.is_(True), Plan.archived_at.is_(None))
        .order_by(Plan.sort_order, Plan.code)
    )
    return list((await db.execute(stmt)).scalars().all())


async def plan_by_code(db: AsyncSession, code: str) -> Plan | None:
    return (await db.execute(select(Plan).where(Plan.code == code))).scalars().first()


async def public_catalog(db: AsyncSession) -> list[tuple[Plan, list[PlanPrice]]]:
    """Публічні тарифи разом із цінами, у порядку показу.

    Одним місцем, щоб маршрут не збирав це сам: `api` не має права
    імпортувати моделі, і без цієї функції сторінка цін ходила б у базу
    в обхід межі.
    """
    plans = (
        (
            await db.execute(
                select(Plan)
                .where(Plan.is_public.is_(True), Plan.archived_at.is_(None))
                .order_by(Plan.sort_order, Plan.code)
            )
        )
        .scalars()
        .all()
    )
    prices: dict[uuid.UUID, list[PlanPrice]] = {}
    for price in (await db.execute(select(PlanPrice))).scalars().all():
        prices.setdefault(price.plan_id, []).append(price)
    return [(plan, prices.get(plan.id, [])) for plan in plans]
