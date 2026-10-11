"""Службова аналітика: продажі, клієнти, використання — зі справжніх таблиць.

## Правила обліку

Джерело кожного числа — наявна модель, а не окремий лічильник:

- **продажі** — `one_off_purchases` у станах `paid` і `refunded`. Покупка
  стає продажем у момент `purchased_at` (підтверджена подія провайдера),
  повернення рахується за `refunded_at`. Дублювання вебхука неможливе
  за побудовою (UNIQUE на подію), тож рядок покупки — рівно один продаж;
  `pending` — не продаж і не рахується ніде;
- **чиста виручка** = продажі − повернення в тій самій валюті; обидва
  числа з тієї самої таблиці, тож різниця чесна. Валюти не змішуються:
  сума двох валют — не число;
- **платежі за підписку** в книзі покупок НЕ записані (Paddle тримає їх
  у себе), тому їх тут немає, і сторінка про це каже, а не вигадує;
- **використання** — виконані аудити й прогони присутності, окремо від
  покупок: пакет на 10 одиниць — одна покупка, десять використань;
- **унікальні сайти** — різні `origin` (нормалізована схема+хост, як у
  моделі сайтів), а не адреси сторінок;
- **службові тести** команди виключені: аудити з `quota_source =
  admin_test` і прогони присутності без організації. Скільки їх
  відкинуто — теж показується, щоб виключення було видимим.

Період застосовується до всіх метрик однаково: подія входить, якщо її
власна часова мітка лежить у [from, to].
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, case, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.enums import AuditStatus
from app.billing.enums import CreditState, PurchaseStatus, SubscriptionStatus
from app.core.run_enums import QuotaSource
from app.models.audit import Audit
from app.models.billing import Subscription, SubscriptionTransition
from app.models.presence import PresenceRun
from app.models.purchase import AuditCredit, OneOffPurchase

EXECUTED_AUDIT = (AuditStatus.COMPLETED, AuditStatus.PARTIAL)
FAILED_AUDIT = (AuditStatus.FAILED,)
# Прогін присутності «виконано» — дійшов до кінця. Часткові
# спостереження лишаються всередині completed: окремого статусу
# «partial» у прогонів немає (на відміну від аудиту).
EXECUTED_PRESENCE = ("completed",)
FAILED_PRESENCE = ("failed",)
ACTIVE_SUBSCRIPTION = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.TRIALING,
    SubscriptionStatus.PAST_DUE,
)


def _between(column: Any, start: datetime | None, end: datetime | None) -> Any:
    conditions = [column.is_not(None)]
    if start is not None:
        conditions.append(column >= start)
    if end is not None:
        conditions.append(column <= end)
    return and_(*conditions)


def _bucket_for(start: datetime | None, end: datetime | None) -> str:
    if start is None or end is None:
        return "month"
    days = (end - start).days
    if days <= 45:
        return "day"
    if days <= 400:
        return "week"
    return "month"


def _offer_type_expr() -> Any:
    """Тип пропозиції зі зліпка на момент каси; без зліпка — за кількістю."""
    return func.coalesce(
        OneOffPurchase.offer_snapshot["offer_type"].astext,
        case((OneOffPurchase.quantity > 1, literal("pack")), else_=literal("single")),
    )


async def _sales(
    session: AsyncSession, start: datetime | None, end: datetime | None
) -> dict[str, Any]:
    paid = OneOffPurchase.status.in_((PurchaseStatus.PAID, PurchaseStatus.REFUNDED))
    sold_in_period = and_(paid, _between(OneOffPurchase.purchased_at, start, end))
    refunded_in_period = and_(
        OneOffPurchase.status == PurchaseStatus.REFUNDED,
        _between(OneOffPurchase.refunded_at, start, end),
    )
    offer_type = _offer_type_expr().label("offer_type")

    sold_rows = (await session.execute(
        select(
            OneOffPurchase.currency,
            offer_type,
            func.count().label("purchases"),
            func.coalesce(func.sum(OneOffPurchase.amount_minor), 0).label("gross_minor"),
        )
        .where(sold_in_period)
        .group_by(OneOffPurchase.currency, offer_type)
    )).all()
    refund_rows = (await session.execute(
        select(
            OneOffPurchase.currency,
            offer_type,
            func.count().label("refunds"),
            func.coalesce(func.sum(OneOffPurchase.amount_minor), 0).label("refunded_minor"),
        )
        .where(refunded_in_period)
        .group_by(OneOffPurchase.currency, offer_type)
    )).all()

    by_currency: dict[str, dict[str, Any]] = {}

    def bucket(currency: str) -> dict[str, Any]:
        return by_currency.setdefault(currency, {
            "currency": currency,
            "purchases": 0, "gross_minor": 0,
            "refunds": 0, "refunded_minor": 0,
            "by_type": {},
        })

    for currency, kind, purchases, gross in sold_rows:
        row = bucket(currency)
        row["purchases"] += int(purchases)
        row["gross_minor"] += int(gross)
        t = row["by_type"].setdefault(kind, {"offer_type": kind, "purchases": 0,
                                            "gross_minor": 0, "refunds": 0,
                                            "refunded_minor": 0})
        t["purchases"] += int(purchases)
        t["gross_minor"] += int(gross)
    for currency, kind, refunds, refunded in refund_rows:
        row = bucket(currency)
        row["refunds"] += int(refunds)
        row["refunded_minor"] += int(refunded)
        t = row["by_type"].setdefault(kind, {"offer_type": kind, "purchases": 0,
                                            "gross_minor": 0, "refunds": 0,
                                            "refunded_minor": 0})
        t["refunds"] += int(refunds)
        t["refunded_minor"] += int(refunded)

    currencies = []
    for row in sorted(by_currency.values(), key=lambda r: str(r["currency"])):
        row["net_minor"] = row["gross_minor"] - row["refunded_minor"]
        row["average_minor"] = (
            round(row["gross_minor"] / row["purchases"]) if row["purchases"] else None
        )
        row["by_type"] = sorted(row["by_type"].values(), key=lambda t: str(t["offer_type"]))
        currencies.append(row)
    return {
        "currencies": currencies,
        # Платежі за підписку живуть у провайдера, не в книзі покупок.
        "subscription_payments_recorded": False,
    }


async def _customers(
    session: AsyncSession, start: datetime | None, end: datetime | None
) -> dict[str, Any]:
    paid = OneOffPurchase.status.in_((PurchaseStatus.PAID, PurchaseStatus.REFUNDED))
    first_purchase = (
        select(
            OneOffPurchase.organization_id.label("org"),
            func.min(OneOffPurchase.purchased_at).label("first_at"),
        )
        .where(paid, OneOffPurchase.purchased_at.is_not(None))
        .group_by(OneOffPurchase.organization_id)
        .subquery()
    )
    purchasing_total = (await session.execute(
        select(func.count()).select_from(first_purchase)
    )).scalar_one()
    new_in_period = (await session.execute(
        select(func.count()).select_from(first_purchase).where(
            _between(first_purchase.c.first_at, start, end)
        )
    )).scalar_one()
    # Повторний покупець періоду: купив у періоді й мав ХОЧ ОДНУ
    # оплачену покупку раніше за цю (будь-коли до неї).
    buyers_in_period = (
        select(OneOffPurchase.organization_id.label("org"))
        .where(paid, _between(OneOffPurchase.purchased_at, start, end))
        .group_by(OneOffPurchase.organization_id)
        .subquery()
    )
    repeat_in_period = (await session.execute(
        select(func.count())
        .select_from(buyers_in_period)
        .join(first_purchase, first_purchase.c.org == buyers_in_period.c.org)
        .where(
            first_purchase.c.first_at < (start if start is not None else datetime.now(UTC))
            if start is not None
            else literal(False),
        )
    )).scalar_one() if start is not None else 0
    if start is None:
        # «За весь час» повторний покупець — той, у кого покупок більше однієї.
        multi = (
            select(OneOffPurchase.organization_id)
            .where(paid, OneOffPurchase.purchased_at.is_not(None))
            .group_by(OneOffPurchase.organization_id)
            .having(func.count() > 1)
            .subquery()
        )
        repeat_in_period = (await session.execute(
            select(func.count()).select_from(multi)
        )).scalar_one()
    return {
        "purchasing_total": int(purchasing_total),
        "new_in_period": int(new_in_period),
        "repeat_in_period": int(repeat_in_period),
    }


async def _usage(
    session: AsyncSession, start: datetime | None, end: datetime | None
) -> dict[str, Any]:
    customer_audit = or_(
        Audit.quota_source.is_(None), Audit.quota_source != QuotaSource.ADMIN_TEST
    )
    audit_rows = (await session.execute(
        select(Audit.status, Audit.quota_source, func.count())
        .where(customer_audit, _between(Audit.finished_at, start, end))
        .group_by(Audit.status, Audit.quota_source)
    )).all()
    audits_executed = 0
    audits_failed = 0
    by_source: dict[str, int] = {}
    for status, source, count in audit_rows:
        status_value = AuditStatus(status)
        if status_value in EXECUTED_AUDIT:
            audits_executed += int(count)
            key = source.value if source is not None else "unknown"
            by_source[key] = by_source.get(key, 0) + int(count)
        elif status_value in FAILED_AUDIT:
            audits_failed += int(count)

    presence_rows = (await session.execute(
        select(PresenceRun.status, PresenceRun.entitlement_source, func.count())
        .where(PresenceRun.organization_id.is_not(None),
               _between(PresenceRun.finished_at, start, end))
        .group_by(PresenceRun.status, PresenceRun.entitlement_source)
    )).all()
    presence_executed = 0
    presence_failed = 0
    by_entitlement: dict[str, int] = {}
    for status, source, count in presence_rows:
        if status in EXECUTED_PRESENCE:
            presence_executed += int(count)
            key = source or "unknown"
            by_entitlement[key] = by_entitlement.get(key, 0) + int(count)
        elif status in FAILED_PRESENCE:
            presence_failed += int(count)

    origins = union_all(
        select(Audit.origin.label("origin")).where(
            customer_audit, Audit.status.in_(EXECUTED_AUDIT),
            _between(Audit.finished_at, start, end),
        ),
        select(PresenceRun.origin.label("origin")).where(
            PresenceRun.organization_id.is_not(None),
            PresenceRun.status.in_(EXECUTED_PRESENCE),
            _between(PresenceRun.finished_at, start, end),
        ),
    ).subquery()
    unique_domains = (await session.execute(
        select(func.count(func.distinct(origins.c.origin)))
    )).scalar_one()

    excluded_audits = (await session.execute(
        select(func.count()).where(
            Audit.quota_source == QuotaSource.ADMIN_TEST,
            _between(Audit.finished_at, start, end),
        )
    )).scalar_one()
    excluded_presence = (await session.execute(
        select(func.count()).where(
            PresenceRun.organization_id.is_(None),
            _between(PresenceRun.finished_at, start, end),
        )
    )).scalar_one()
    return {
        "audits_executed": audits_executed,
        "audits_failed": audits_failed,
        "audits_by_source": by_source,
        "presence_executed": presence_executed,
        "presence_failed": presence_failed,
        "presence_by_entitlement": by_entitlement,
        "analyses_total": audits_executed + presence_executed,
        "unique_domains": int(unique_domains),
        "admin_tests_excluded": {
            "audits": int(excluded_audits), "presence": int(excluded_presence),
        },
    }


async def _credits(
    session: AsyncSession, start: datetime | None, end: datetime | None
) -> dict[str, Any]:
    sold = (await session.execute(
        select(AuditCredit.credit_type, AuditCredit.source, func.count())
        .where(_between(AuditCredit.created_at, start, end))
        .group_by(AuditCredit.credit_type, AuditCredit.source)
    )).all()
    used = (await session.execute(
        select(AuditCredit.credit_type, func.count())
        .where(AuditCredit.state == CreditState.CONSUMED,
               _between(AuditCredit.consumed_at, start, end))
        .group_by(AuditCredit.credit_type)
    )).all()
    revoked = (await session.execute(
        select(AuditCredit.credit_type, func.count())
        .where(AuditCredit.state == CreditState.REVOKED,
               _between(AuditCredit.revoked_at, start, end))
        .group_by(AuditCredit.credit_type)
    )).all()
    out: dict[str, dict[str, int]] = {}

    def row(kind: str) -> dict[str, int]:
        return out.setdefault(kind, {"sold": 0, "granted": 0, "used": 0, "revoked": 0})

    for kind, source, count in sold:
        row(kind)["sold" if source == "purchase" else "granted"] += int(count)
    for kind, count in used:
        row(kind)["used"] += int(count)
    for kind, count in revoked:
        row(kind)["revoked"] += int(count)
    return out


async def _subscriptions(
    session: AsyncSession, start: datetime | None, end: datetime | None
) -> dict[str, Any]:
    active_now = (await session.execute(
        select(func.count()).where(Subscription.status.in_(ACTIVE_SUBSCRIPTION))
    )).scalar_one()
    new_in_period = (await session.execute(
        select(func.count()).where(
            SubscriptionTransition.to_status.in_(
                (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING)
            ),
            SubscriptionTransition.from_status.in_(
                (SubscriptionStatus.INACTIVE, SubscriptionStatus.CANCELLED)
            ),
            _between(SubscriptionTransition.effective_at, start, end),
        )
    )).scalar_one()
    cancelled_in_period = (await session.execute(
        select(func.count()).where(
            SubscriptionTransition.to_status == SubscriptionStatus.CANCELLED,
            SubscriptionTransition.from_status != SubscriptionStatus.CANCELLED,
            _between(SubscriptionTransition.effective_at, start, end),
        )
    )).scalar_one()
    return {
        "active_now": int(active_now),
        "new_in_period": int(new_in_period),
        "cancelled_in_period": int(cancelled_in_period),
    }


async def _timeline(
    session: AsyncSession, start: datetime | None, end: datetime | None, bucket: str
) -> list[dict[str, Any]]:
    paid = OneOffPurchase.status.in_((PurchaseStatus.PAID, PurchaseStatus.REFUNDED))
    trunc_sales = func.date_trunc(bucket, OneOffPurchase.purchased_at)
    sales = (await session.execute(
        select(trunc_sales.label("b"), OneOffPurchase.currency,
               func.count(), func.coalesce(func.sum(OneOffPurchase.amount_minor), 0))
        .where(paid, _between(OneOffPurchase.purchased_at, start, end))
        .group_by(trunc_sales, OneOffPurchase.currency)
    )).all()
    trunc_audits = func.date_trunc(bucket, Audit.finished_at)
    audits = (await session.execute(
        select(trunc_audits.label("b"), func.count())
        .where(
            or_(Audit.quota_source.is_(None), Audit.quota_source != QuotaSource.ADMIN_TEST),
            Audit.status.in_(EXECUTED_AUDIT),
            _between(Audit.finished_at, start, end),
        )
        .group_by(trunc_audits)
    )).all()
    trunc_presence = func.date_trunc(bucket, PresenceRun.finished_at)
    presence = (await session.execute(
        select(trunc_presence.label("b"), func.count())
        .where(
            PresenceRun.organization_id.is_not(None),
            PresenceRun.status.in_(EXECUTED_PRESENCE),
            _between(PresenceRun.finished_at, start, end),
        )
        .group_by(trunc_presence)
    )).all()

    points: dict[str, dict[str, Any]] = {}

    def point(when: datetime) -> dict[str, Any]:
        key = when.date().isoformat()
        return points.setdefault(key, {"bucket": key, "purchases": 0,
                                       "gross_minor": {}, "audits": 0, "presence": 0})

    for when, currency, count, gross in sales:
        p = point(when)
        p["purchases"] += int(count)
        p["gross_minor"][currency] = p["gross_minor"].get(currency, 0) + int(gross)
    for when, count in audits:
        point(when)["audits"] += int(count)
    for when, count in presence:
        point(when)["presence"] += int(count)
    return [points[k] for k in sorted(points)]


async def overview(
    session: AsyncSession, *, start: datetime | None, end: datetime | None
) -> dict[str, Any]:
    if start is not None and start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if end is not None and end.tzinfo is None:
        end = end.replace(tzinfo=UTC)
    if end is not None and end.hour == 0 and end.minute == 0 and end.second == 0:
        # Дата «до» включно: 2026-09-05 означає весь день 5 вересня.
        end = end + timedelta(days=1) - timedelta(microseconds=1)
    bucket = _bucket_for(start, end)
    return {
        "period": {
            "from": start.isoformat() if start else None,
            "to": end.isoformat() if end else None,
            "bucket": bucket,
            "generated_at": datetime.now(UTC).isoformat(),
        },
        "sales": await _sales(session, start, end),
        "customers": await _customers(session, start, end),
        "usage": await _usage(session, start, end),
        "credits": await _credits(session, start, end),
        "subscriptions": await _subscriptions(session, start, end),
        "timeline": await _timeline(session, start, end, bucket),
    }
