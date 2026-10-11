"""Комерційні пропозиції і промокоди: правила, не маршрути.

Пропозиція каже, ЩО дає оплата (типізовані одиниці); прайс провайдера
каже, СКІЛЬКИ це коштує; кампанія каже, ХТО може заплатити менше.
Жодне з трьох не живе в коді — все в рядках, які редагує адміністратор.

Промо-межі продукту:
* код діє лише на PACK-пропозиції з promo_eligible;
* одна організація погашає одну кампанію один раз — UNIQUE у базі;
* знижка міняє гроші, НЕ кількість одиниць.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import purchases
from app.billing import catalog
from app.billing.providers.base import CheckoutRequest, ProviderUnavailable
from app.billing.registry import provider_for
from app.models.commerce import (
    CommercialOffer,
    OfferType,
    PromoCampaign,
    PromoRedemption,
    RedemptionStatus,
)


class OfferUnavailable(Exception):
    """Пропозиції немає, вона вимкнена або не для цього провайдера."""


class PromoNotEligible(Exception):
    """Код не може бути застосований — з названої причини."""


class PlanUnavailable(Exception):
    """Тарифу немає, він непублічний або не має прайса в цієї каси."""


# Стабільний код застосунку: його читає інтерфейс і перекладає своїм
# реченням; сирим він не рендериться ніде.
DUPLICATE_SUBSCRIPTION = "subscription.exists"


class SubscriptionExists(Exception):
    """В організації вже є незавершена підписка — друга каса недоречна."""


def _now() -> datetime:
    return datetime.now(UTC)


async def active_offers(db: AsyncSession) -> list[CommercialOffer]:
    rows = await db.execute(
        select(CommercialOffer)
        .where(CommercialOffer.active.is_(True),
               CommercialOffer.archived_at.is_(None))
        .order_by(CommercialOffer.sort_order, CommercialOffer.code)
    )
    return list(rows.scalars())


async def offer_by_code(db: AsyncSession, code: str) -> CommercialOffer | None:
    row = await db.execute(
        select(CommercialOffer).where(CommercialOffer.code == code)
    )
    return row.scalar_one_or_none()


async def check_promo(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    promo_code: str,
    offer: CommercialOffer,
) -> PromoCampaign:
    """Кампанія, якщо органцізація МОЖЕ нею скористатись для цієї пропозиції.

    Правила перевіряються ДО відкриття каси: клієнт дізнається про
    непридатний код одразу, а не після введення картки.
    """
    if offer.offer_type is not OfferType.PACK or not offer.promo_eligible:
        raise PromoNotEligible("промокоди діють лише на пакетні пропозиції")
    row = await db.execute(
        select(PromoCampaign).where(PromoCampaign.code == promo_code)
    )
    campaign = row.scalar_one_or_none()
    if campaign is None or not campaign.active:
        raise PromoNotEligible("такого промокоду немає або він неактивний")
    moment = _now()
    if campaign.starts_at is not None and moment < campaign.starts_at:
        raise PromoNotEligible("кампанія ще не почалась")
    if campaign.ends_at is not None and moment >= campaign.ends_at:
        raise PromoNotEligible("кампанія завершилась")
    redeemed = await db.execute(
        select(PromoRedemption).where(
            PromoRedemption.campaign_id == campaign.id,
            PromoRedemption.organization_id == organization_id,
            PromoRedemption.status == RedemptionStatus.COMPLETED,
        )
    )
    if redeemed.scalar_one_or_none() is not None:
        raise PromoNotEligible("цей код уже було використано цим акаунтом")
    return campaign


async def _open_redemption(
    db: AsyncSession,
    *,
    campaign: PromoCampaign,
    organization_id: uuid.UUID,
    offer_code: str,
) -> PromoRedemption:
    """PENDING-погашення: створити або переиспользувати власне.

    UNIQUE(campaign, organization) робить друге погашення неможливим
    рівнем бази; недоплачена спроба не блокує повторну — та сама
    організація знаходить свій PENDING-рядок і йде далі з ним.
    """
    row = await db.execute(
        select(PromoRedemption).where(
            PromoRedemption.campaign_id == campaign.id,
            PromoRedemption.organization_id == organization_id,
        )
    )
    redemption = row.scalar_one_or_none()
    if redemption is not None:
        if redemption.status is RedemptionStatus.COMPLETED:
            raise PromoNotEligible("цей код уже було використано цим акаунтом")
        redemption.offer_code = offer_code
        await db.flush()
        return redemption
    redemption = PromoRedemption(
        campaign_id=campaign.id,
        organization_id=organization_id,
        offer_code=offer_code,
    )
    db.add(redemption)
    await db.flush()
    return redemption


@dataclass(frozen=True, slots=True)
class OpenedOfferCheckout:
    purchase_id: uuid.UUID
    provider_ref: str
    url: str
    discount_applied: bool


@dataclass(frozen=True, slots=True)
class OpenedPlanCheckout:
    plan_code: str
    provider_ref: str
    url: str


async def open_plan_checkout(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    plan_code: str,
) -> OpenedPlanCheckout:
    """Каса підписки на тариф. Право видає ЛИШЕ подія провайдера.

    Ця функція не створює ані підписки, ані наділу: вона відкриває касу
    й усе. Підписку створить перша перевірена подія `subscription.*` —
    той самий конвеєр, що веде її стан далі. Кореляція — організація у
    власних даних транзакції.

    Непублічний, архівний або безпрайсовий тариф каси не має: вітрина й
    каса мусять погоджуватися, інакше купити можна те, чого не видно.
    """
    from app.billing.service import non_terminal_subscription
    from app.models.billing import Plan, PlanPrice

    plan_row = await db.execute(select(Plan).where(Plan.code == plan_code))
    plan = plan_row.scalar_one_or_none()
    if plan is None or not plan.is_public or plan.archived_at is not None:
        raise PlanUnavailable(f"тариф недоступний: {plan_code}")

    provider_name = catalog.current_provider()
    price_row = await db.execute(
        select(PlanPrice).where(
            PlanPrice.plan_id == plan.id,
            PlanPrice.provider == provider_name,
        )
    )
    price = price_row.scalars().first()
    if price is None:
        raise PlanUnavailable(
            f"тариф {plan_code} не має прайса для каси {provider_name}"
        )

    # Незавершена підписка — БУДЬ-ЯКА, не лише та, що зараз дає права:
    # пауза чи прострочена грація не роблять другу касу доречною, вони
    # роблять доречним портал платежів. Термінальний стан один —
    # скасована, і лише після неї нова підписка можлива.
    if await non_terminal_subscription(db, organization_id=organization_id) is not None:
        raise SubscriptionExists(DUPLICATE_SUBSCRIPTION)

    adapter = provider_for(provider_name)
    if adapter is None:  # pragma: no cover — реєстр статичний
        raise ProviderUnavailable(f"провайдер {provider_name} не зареєстрований")
    session = await adapter.create_checkout(CheckoutRequest(
        # Покупки-рядка в підписки немає: її створить перша подія
        # провайдера, а кореляцією служить організація.
        purchase_id=None,
        price_ref=price.provider_price_id,
        organization_id=organization_id,
    ))
    return OpenedPlanCheckout(
        plan_code=plan.code,
        provider_ref=session.ref.external_id,
        url=session.url,
    )


async def open_offer_checkout(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    offer_code: str,
    promo_code: str | None = None,
    email: str | None = None,
    reuse_pending: bool = False,
) -> OpenedOfferCheckout:
    """Каса для пропозиції каталогу. Промо — лише де дозволено.

    Покупка створюється ДО каси (та сама дисципліна, що в разовій
    воронці) і несе offer_code: подія оплати видасть рівно те, що
    записано в пропозиції на момент покупки.
    """
    offer = await offer_by_code(db, offer_code)
    if offer is None or not offer.active or offer.archived_at is not None:
        raise OfferUnavailable(f"пропозиція недоступна: {offer_code}")
    provider_name = catalog.current_provider()
    if offer.provider != provider_name:
        raise OfferUnavailable(
            f"пропозиція налаштована для {offer.provider}, каса — {provider_name}"
        )

    if reuse_pending and not promo_code:
        # Друга спроба тієї самої людини — та сама каса. Просимо
        # провайдера лише тоді, коли відкривати справді нема чого.
        open_till = await purchases.find_pending_for_offer(
            db,
            organization_id=organization_id,
            offer_code=offer.code,
            provider=provider_name,
        )
        if open_till is not None:
            # Адреси каси тут немає: провайдер віддає її разом із новою
            # транзакцією, а ми повторно відкриваємо стару накладною
            # касою за її ідентифікатором. Порожній рядок чесніший за
            # складене нами посилання, якого провайдер не називав.
            return OpenedOfferCheckout(
                purchase_id=open_till.id,
                provider_ref=str(open_till.provider_ref),
                url="",
                discount_applied=False,
            )

    campaign = None
    redemption = None
    if promo_code:
        campaign = await check_promo(
            db, organization_id=organization_id, promo_code=promo_code,
            offer=offer,
        )
        redemption = await _open_redemption(
            db, campaign=campaign, organization_id=organization_id,
            offer_code=offer.code,
        )

    purchase = await purchases.open_pending(
        db,
        organization_id=organization_id,
        provider=provider_name,
        audit_id=None,
        quantity=max(offer.audit_credits, 1),
        offer_code=offer.code,
        # Зліпок умов НА МОМЕНТ КАСИ: людина платить за те, що бачить
        # зараз, і редагування каталогу до приходу вебхука не має ні
        # міняти видачу, ні переписувати історію покупки.
        offer_snapshot={
            "offer_code": offer.code,
            "offer_type": offer.offer_type.value,
            "provider_price_ref": offer.provider_price_ref,
            "currency": offer.currency,
            "display_amount_minor": offer.display_amount_minor,
            "audit_credits": offer.audit_credits,
            "presence_credits": offer.presence_credits,
            "captured_at": _now().isoformat(),
        },
        promo_redemption_id=redemption.id if redemption else None,
    )

    adapter = provider_for(provider_name)
    if adapter is None:  # pragma: no cover — реєстр статичний
        raise ProviderUnavailable(f"провайдер {provider_name} не зареєстрований")
    session = await adapter.create_checkout(CheckoutRequest(
        purchase_id=purchase.id,
        price_ref=offer.provider_price_ref,
        organization_id=organization_id,
        email=email,
        discount_ref=(campaign.provider_discount_ref if campaign else None),
    ))
    await purchases.attach_provider_ref(
        db, purchase=purchase, provider_ref=session.ref.external_id
    )
    if redemption is not None:
        redemption.purchase_id = purchase.id
        await db.flush()
    return OpenedOfferCheckout(
        purchase_id=purchase.id,
        provider_ref=session.ref.external_id,
        url=session.url,
        discount_applied=bool(campaign and campaign.provider_discount_ref),
    )
