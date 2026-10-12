"""Публічний каталог тарифів і каса підписки.

Каталог — без входу: це сторінка цін. Каса — за входом: підписку
тримає конкретна організація, і стан у неї мусить бути кому належати.
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel

from app.api.deps import OwnerDep, SessionDep
from app.application import commerce
from app.application.catalog import public_plan
from app.application.locale import resolve as resolve_locale
from app.audit.i18n import Locale
from app.billing import service as billing
from app.schemas.catalog import PlanCatalogOut

router = APIRouter(prefix="/v1/plans", tags=["plans"])


class PlanCheckoutOut(BaseModel):
    """Каса відкрита. Не право й не підписка — лише двері до оплати."""

    plan_code: str
    provider_ref: str
    url: str


@router.get("", response_model=PlanCatalogOut)
async def list_plans(
    session: SessionDep,
    lang: Locale | None = None,
    accept_language: str | None = Header(default=None),
) -> PlanCatalogOut:
    """Тарифи для сторінки цін.

    Єдиний маршрут, де `Accept-Language` справді враховується: у
    відвідувача без акаунта налаштувань немає, і мова браузера — усе, що
    ми про нього знаємо. Для того, хто мову обрав, її не має перебивати
    браузер, тож на решті маршрутів заголовок не читається.

    Віддає публічний каталог, а не `Plan.entitlements`: внутрішні ключі
    прав не мусять ставати контрактом маркетингової сторінки.
    """
    locale = resolve_locale(requested=lang or accept_language).locale

    return PlanCatalogOut(
        locale=locale.value,
        plans=[
            public_plan(plan, prices, locale)
            for plan, prices in await billing.public_catalog(session)
        ],
    )


@router.post(
    "/{plan_code}/checkout",
    response_model=PlanCheckoutOut,
    status_code=status.HTTP_201_CREATED,
)
async def open_checkout(
    plan_code: str, session: SessionDep, actor: OwnerDep
) -> PlanCheckoutOut:
    """Відкрити касу підписки на публічний тариф.

    Жодного права тут не видається: підписку створить перша перевірена
    подія провайдера, і саме вона — а не повернення з каси — вмикає
    наділ. Непублічний чи безпрайсовий тариф каси не має (404 — та сама
    відповідь, що й на неіснуючий), чинна підписка — 409.

    Лише власник: гроші організації — не дія учасника й не дія ключа API.
    """
    try:
        opened = await commerce.open_plan_checkout(
            session,
            organization_id=actor.organization_id,
            plan_code=plan_code,
        )
    except commerce.PlanUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except commerce.SubscriptionExists as exc:
        # Стабільний код застосунку, не речення: текст для людини обирає
        # інтерфейс своєю мовою.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": commerce.DUPLICATE_SUBSCRIPTION},
        ) from exc
    await session.commit()
    return PlanCheckoutOut(
        plan_code=opened.plan_code,
        provider_ref=opened.provider_ref,
        url=opened.url,
    )
