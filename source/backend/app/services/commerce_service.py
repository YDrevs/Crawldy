"""Доступ до даних комерції для маршрутів: моделі не течуть у API-шар."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import commerce as commerce_app
from app.billing import credits as billing_credits
from app.models.billing import Plan, PlanPrice
from app.models.commerce import CommercialOffer, OfferType, PromoCampaign
from app.models.purchase import AuditCredit, OneOffPurchase


async def all_offers(db: AsyncSession) -> list[CommercialOffer]:
    rows = await db.execute(
        select(CommercialOffer).order_by(
            CommercialOffer.sort_order, CommercialOffer.code
        )
    )
    return list(rows.scalars())


async def upsert_offer(db: AsyncSession, *, code: str, values: dict[str, Any]) -> CommercialOffer:
    offer_type = OfferType(values["offer_type"])
    offer = await commerce_app.offer_by_code(db, code)
    if offer is None:
        offer = CommercialOffer(
            code=code, offer_type=offer_type,
            display_name=values["display_name"],
            provider=values["provider"],
            provider_price_ref=values["provider_price_ref"],
        )
        db.add(offer)
    offer.offer_type = offer_type
    offer.active = bool(values["active"])
    offer.display_name = values["display_name"]
    offer.description = values.get("description", "")
    offer.provider = values["provider"]
    offer.provider_price_ref = values["provider_price_ref"]
    offer.provider_product_ref = values.get("provider_product_ref")
    if "provider_refs" in values:
        offer.provider_refs = dict(values["provider_refs"] or {})
    offer.currency = str(values.get("currency", "USD")).upper()
    offer.display_amount_minor = values.get("display_amount_minor")
    offer.audit_credits = int(values.get("audit_credits", 1))
    offer.presence_credits = int(values.get("presence_credits", 0))
    offer.promo_eligible = bool(values.get("promo_eligible", False))
    offer.sort_order = int(values.get("sort_order", 0))
    offer.display_name_i18n = dict(values.get("display_name_i18n") or {})
    offer.description_i18n = dict(values.get("description_i18n") or {})
    await db.flush()
    return offer


async def all_plans(db: AsyncSession) -> list[dict[str, Any]]:
    """Тарифи з правами й цінами — очима адміністратора.

    На відміну від публічного каталогу тут видно все: приховані й
    архівні тарифи, сирі ключі прав, посилання на прайси провайдера.
    Саме цим адмінка й керує.
    """
    plans = (
        (
            await db.execute(
                select(Plan).order_by(Plan.sort_order, Plan.code)
            )
        )
        .scalars()
        .all()
    )
    prices: dict[uuid.UUID, list[PlanPrice]] = {}
    for price in (await db.execute(select(PlanPrice))).scalars().all():
        prices.setdefault(price.plan_id, []).append(price)
    return [
        {
            "code": plan.code,
            "name": plan.name,
            "description": plan.description,
            "name_i18n": dict(plan.name_i18n or {}),
            "description_i18n": dict(plan.description_i18n or {}),
            "is_public": plan.is_public,
            "archived": plan.archived_at is not None,
            "sort_order": plan.sort_order,
            "entitlements": dict(plan.entitlements or {}),
            "prices": [
                {
                    "provider": p.provider,
                    "provider_price_id": p.provider_price_id,
                    "provider_product_ref": p.provider_product_ref,
                    "provider_refs": dict(p.provider_refs or {}),
                    "currency": p.currency,
                    "interval": p.interval,
                    "display_amount_minor": p.display_amount_minor,
                }
                for p in sorted(
                    prices.get(plan.id, []),
                    key=lambda p: (p.provider, p.interval, p.currency),
                )
            ],
        }
        for plan in plans
    ]


async def upsert_plan(
    db: AsyncSession,
    *,
    code: str,
    name: str,
    description: str,
    name_i18n: dict[str, str] | None = None,
    description_i18n: dict[str, str] | None = None,
    is_public: bool,
    sort_order: int,
    entitlement_values: dict[str, Any],
    prices: list[dict[str, Any]],
) -> Plan:
    """Створити або оновити тариф разом із цінами. Валідність прав і
    форм посилань перевіряє маршрут — тут лише персистентність.

    Ціна впізнається за (валюта, період): «$49 → $79» — це оновлення
    того самого рядка новим прайсом провайдера й новою показовою сумою,
    а не другий рядок поруч зі старим. Провайдер — властивість запису,
    а не частина його ідентичності: у каталозі одна ціна на продукт, і
    при зміні провайдера каси той самий запис публікується наново, а не
    дублюється. Інакше після повернення до попереднього провайдера
    касу відкривав би рядок зі старою сумою.
    """
    plan = (
        await db.execute(select(Plan).where(Plan.code == code))
    ).scalar_one_or_none()
    if plan is None:
        plan = Plan(code=code, name=name)
        db.add(plan)
        await db.flush()
    plan.name = name
    plan.description = description
    plan.name_i18n = dict(name_i18n or {})
    plan.description_i18n = dict(description_i18n or {})
    plan.is_public = is_public
    plan.sort_order = sort_order
    plan.entitlements = dict(entitlement_values)

    existing = {
        (p.currency, p.interval): p
        for p in (
            await db.execute(
                select(PlanPrice).where(PlanPrice.plan_id == plan.id)
            )
        ).scalars()
    }
    for row in prices:
        key = (row["currency"], row["interval"])
        price = existing.get(key)
        if price is None:
            price = PlanPrice(
                plan_id=plan.id,
                provider=row["provider"],
                currency=row["currency"],
                interval=row["interval"],
                provider_price_id=row["provider_price_id"],
            )
            db.add(price)
        price.provider = row["provider"]
        price.provider_price_id = row["provider_price_id"]
        price.provider_product_ref = row.get("provider_product_ref")
        if "provider_refs" in row:
            price.provider_refs = dict(row["provider_refs"] or {})
        price.display_amount_minor = row.get("display_amount_minor")
    await db.flush()
    return plan


async def upsert_campaign(
    db: AsyncSession, *, code: str, name: str, active: bool,
    provider_discount_ref: str | None, starts_at: datetime | None,
    ends_at: datetime | None, description: str,
) -> PromoCampaign:
    row = await db.execute(
        select(PromoCampaign).where(PromoCampaign.code == code)
    )
    campaign = row.scalar_one_or_none()
    if campaign is None:
        campaign = PromoCampaign(code=code, name=name)
        db.add(campaign)
    campaign.name = name
    campaign.active = active
    campaign.provider_discount_ref = provider_discount_ref
    campaign.starts_at = starts_at
    campaign.ends_at = ends_at
    campaign.description = description
    await db.flush()
    return campaign


async def org_view(db: AsyncSession, *, organization_id: uuid.UUID) -> dict[str, Any]:
    """Баланси, одиниці й покупки організації — з походженням кожної."""
    credit_rows = await db.execute(
        select(AuditCredit)
        .where(AuditCredit.organization_id == organization_id)
        .order_by(AuditCredit.created_at.desc())
        .limit(200)
    )
    purchases_rows = await db.execute(
        select(OneOffPurchase)
        .where(OneOffPurchase.organization_id == organization_id)
        .order_by(OneOffPurchase.id.desc())
        .limit(50)
    )
    return {
        "balances": {
            "audit": await billing_credits.balance(
                db, organization_id=organization_id
            ),
            "presence": await billing_credits.balance(
                db, organization_id=organization_id, credit_type="presence"
            ),
        },
        "credits": [
            {
                "id": str(c.id), "type": c.credit_type, "state": c.state.value,
                "source": c.source, "reason": c.reason,
                "purchase_id": str(c.purchase_id) if c.purchase_id else None,
                "audit_id": str(c.audit_id) if c.audit_id else None,
                "presence_run_id": (
                    str(c.presence_run_id) if c.presence_run_id else None
                ),
                "created_at": c.created_at.isoformat(),
            }
            for c in credit_rows.scalars()
        ],
        "purchases": [
            {
                "id": str(p.id), "status": p.status.value,
                "offer_code": p.offer_code, "quantity": p.quantity,
                "amount_minor": p.amount_minor, "currency": p.currency,
                "provider_ref": p.provider_ref,
            }
            for p in purchases_rows.scalars()
        ],
    }
