"""Комерційні пропозиції: перелік і каса.

Клієнт бачить лише активні пропозиції і рівно ті слова, якими продукт
продається: скільки перевірок дає покупка і скільки це коштує. Механіка
одиниць, промо-правила й провайдерські посилання лишаються за межею.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import ActorDep, SessionDep
from app.application import commerce
from app.application.catalog import localized_text
from app.application.locale import resolve as resolve_locale
from app.audit.i18n import Locale
from app.billing import money

router = APIRouter(prefix="/v1/offers", tags=["offers"])


class OfferOut(BaseModel):
    code: str
    offer_type: str
    display_name: str
    description: str
    currency: str
    display_amount_minor: int | None
    # Знаків після коми в цій валюті: клієнт не має ділити на сто «бо
    # зазвичай так» — у єни нуль, у динара Бахрейну три.
    exponent: int
    audit_credits: int
    presence_credits: int
    promo_eligible: bool


class OfferCheckoutIn(BaseModel):
    offer_code: str = Field(min_length=1, max_length=48)
    promo_code: str | None = Field(default=None, max_length=48)


class OfferCheckoutOut(BaseModel):
    purchase_id: uuid.UUID
    provider_ref: str
    url: str
    discount_applied: bool


@router.get("")
async def list_offers(
    session: SessionDep,
    lang: Locale | None = None,
    accept_language: str | None = Header(default=None),
) -> list[OfferOut]:
    """Активні пропозиції — без входу, як і каталог тарифів (/v1/plans).

    Це вітрина сторінки цін: назви, ціни й кількість перевірок — публічні
    за означенням, бо саме їх бачить покупець до будь-якого акаунта.
    Каса нижче лишається за входом: купує завжди конкретна організація.

    Мова розвʼязується так само, як у /v1/plans: явний `lang` перемагає,
    інакше — мова браузера. Локалізується ЛИШЕ текст: суми, кількості,
    порядок і прайс-посилання однакові для всіх мов за побудовою.
    """
    locale = resolve_locale(requested=lang or accept_language).locale
    rows = await commerce.active_offers(session)
    return [
        OfferOut(
            code=o.code,
            offer_type=o.offer_type.value,
            display_name=localized_text(
                o.display_name, o.display_name_i18n, locale),
            description=localized_text(
                o.description, o.description_i18n, locale),
            currency=o.currency,
            display_amount_minor=o.display_amount_minor,
            exponent=money.exponent(o.currency),
            audit_credits=o.audit_credits,
            presence_credits=o.presence_credits,
            promo_eligible=o.promo_eligible,
        )
        for o in rows
    ]


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
async def open_checkout(
    payload: OfferCheckoutIn, session: SessionDep, actor: ActorDep
) -> OfferCheckoutOut:
    try:
        opened = await commerce.open_offer_checkout(
            session,
            organization_id=actor.organization_id,
            offer_code=payload.offer_code,
            promo_code=payload.promo_code,
        )
    except commerce.OfferUnavailable as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=str(exc)) from exc
    except commerce.PromoNotEligible as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=str(exc)) from exc
    await session.commit()
    return OfferCheckoutOut(
        purchase_id=opened.purchase_id,
        provider_ref=opened.provider_ref,
        url=opened.url,
        discount_applied=opened.discount_applied,
    )
