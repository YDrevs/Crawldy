"""Службовий API команди Crawldy. Клієнт сюди не ходить.

Окремий префікс і окрема залежність — не для охайності. Клієнтський і
службовий API мусять бути розділені так, щоб додати службовий ендпойнт у
клієнтський роутер було незручно: інакше одного дня хтось додасть, і
дізнаємось ми про це від клієнта, який побачив чужі дані.

Права перевіряються тут, а не в тому, що адмінки не видно в інтерфейсі:
клієнт із вгаданим URL отримує 403 так само, як клієнт без URL — нічого.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, StaffDep
from app.schemas.ai_admin import AnalysisSettingsOut, PresenceSettingsOut
from app.services import verdict_service

router = APIRouter(prefix="/v1/admin", tags=["admin"])


@router.get("/checks/feedback")
async def check_feedback(session: SessionDep, _: StaffDep) -> dict[str, object]:
    """Що люди сказали про кожен чек — по всіх організаціях разом.

    Перше в проєкті число про якість детекції, яке не є нашою власною
    гіпотезою. Частка рахується лише від вердикту «такого немає»: «не
    робитимемо» свідчить про пріоритети клієнта, а не про помилку чека.

    **Було на клієнтському API і не мало там бути.** Зведення йде по всіх
    організаціях (`feedback_by_check` не приймає `organization_id`), тож
    будь-який автентифікований клієнт бачив, скільки чужих людей і як
    відповіли на кожен чек. Це внутрішній інструмент якості, а не
    продуктова функція.
    """
    summary = await verdict_service.feedback_by_check(session)
    return {
        "checks": [item.to_json() for item in summary],
        "min_answers_to_judge": verdict_service.MIN_VERDICTS_TO_JUDGE,
    }


# ── AI-конфігурація: два окремі домени, жодного спільного форму ───────────
#
# «AI Analysis» і «Actual AI Presence» — різні політики над спільним
# каталогом можливостей. Ендпойнти навмисно окремі: зміна моделі аналізу
# фізично не може зачепити спостереження присутності, і навпаки.
# Секрети сюди не потрапляють — лише «ключ налаштовано / ні».


@router.get("/ai/analysis")
async def ai_analysis_settings(session: SessionDep, _: StaffDep) -> AnalysisSettingsOut:
    from app.enrich import policy as analysis_policy
    from app.services.ai_policy_service import load_analysis

    policy = await load_analysis(session)
    return AnalysisSettingsOut.model_validate(analysis_policy.status_view(policy))


@router.put("/ai/analysis")
async def update_ai_analysis(
    payload: dict[str, Any], session: SessionDep, _: StaffDep
) -> AnalysisSettingsOut:
    from app.enrich import policy as analysis_policy
    from app.services.ai_policy_service import save_analysis

    policy, errors = await save_analysis(session, payload)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": errors},
        )
    await session.commit()
    return AnalysisSettingsOut.model_validate(analysis_policy.status_view(policy))


@router.get("/ai/presence")
async def ai_presence_settings(session: SessionDep, _: StaffDep) -> PresenceSettingsOut:
    from app.presence import policy as presence_policy
    from app.services import presence_service

    policy = await presence_service.load_policy(session)
    return PresenceSettingsOut.model_validate({
        "domain": presence_policy.DOMAIN,
        "policy": presence_policy.to_stored(policy),
        "providers": presence_policy.provider_status(policy),
    })


@router.put("/ai/presence")
async def update_ai_presence(
    payload: dict[str, Any], session: SessionDep, _: StaffDep
) -> PresenceSettingsOut:
    from app.presence import policy as presence_policy
    from app.services import presence_service

    policy, errors = await presence_service.save_policy(session, payload)
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"errors": errors},
        )
    await session.commit()
    return PresenceSettingsOut.model_validate({
        "domain": presence_policy.DOMAIN,
        "policy": presence_policy.to_stored(policy),
        "providers": presence_policy.provider_status(policy),
    })


# ── комерція: пропозиції, кампанії, гранти ────────────────────────────────
#
# Ціни, розміри пакетів і ліміти — рядки, не код: адміністратор змінює
# їх без релізу. Секрети провайдера сюди не потрапляють — прайс
# зветься посиланням, ключів тут немає.


def _require_complete_public_text(
    *, active: bool, maps: dict[str, dict[str, str]]
) -> None:
    """Публічний запис із частковою локалізацією не зберігається.

    Порожня мапа — легальний вибір універсальної назви; часткова мапа
    активного/публічного запису означала б, що котрась мова побачить
    чужий текст мовчазним фолбеком. Чернетки (неактивні записи) можна
    заповнювати поступово.
    """
    from app.application.catalog import missing_text_locales

    if not active:
        return
    for field, mapping in maps.items():
        missing = missing_text_locales(mapping)
        if missing:
            raise HTTPException(
                status_code=422,
                detail=f"{field}: бракує мов {', '.join(missing)} — "
                       "публічний запис або універсальний (порожня мапа), "
                       "або повний усіма шістьма мовами",
            )


async def _publish_or_502(
    spec: Any, *, provider: str, price_ref: str | None, product_ref: str | None
) -> Any:
    """Опублікувати прайс у провайдера або відмовити у збереженні.

    502, а не 422: проблема не у введеному, а між нами й провайдером —
    ключ, оточення, мережа. Текст називає провайдера й причину; ціна на
    сайті лишається попередньою.
    """
    from app.application import catalogue_publishing as publishing
    from app.billing.publishing import PublishFailed

    try:
        return await publishing.publish(
            spec, provider=provider, price_ref=price_ref, product_ref=product_ref
        )
    except PublishFailed as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                f"ціну не опубліковано у провайдера {provider}: "
                f"{exc.outcome} — {exc.detail}"
            ),
        ) from exc


class OfferIn(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    offer_type: str
    active: bool = True
    display_name: str = Field(min_length=1, max_length=100)
    description: str = ""
    # Провайдер і прайс пише ПУБЛІКАЦІЯ, а не форма: поля лишаються в
    # контракті, бо сторінка цін повертає запис цілком, але сервер їх
    # ігнорує — інакше сума на сайті й сума в касі мали б два джерела.
    provider: str | None = None
    provider_price_ref: str | None = Field(default=None, max_length=128)
    currency: str = Field(default="USD", max_length=3)
    display_amount_minor: int | None = None
    audit_credits: int = Field(default=1, ge=0, le=1000)
    presence_credits: int = Field(default=0, ge=0, le=1000)
    promo_eligible: bool = False
    sort_order: int = 0
    # Клієнтський текст мовами публічного сайту. Порожня мапа — явний
    # вибір «назва універсальна» (display_name для всіх мов); непорожня
    # мапа АКТИВНОЇ пропозиції мусить покривати всі шість мов — інакше
    # німецька сторінка показала б українську назву мовчазним фолбеком.
    display_name_i18n: dict[str, str] = Field(default_factory=dict)
    description_i18n: dict[str, str] = Field(default_factory=dict)


class OfferAdminOut(OfferIn):
    id: uuid.UUID


@router.get("/commerce/offers")
async def list_commerce_offers(
    session: SessionDep, _: StaffDep
) -> list[OfferAdminOut]:
    from app.services import commerce_service

    rows = await commerce_service.all_offers(session)
    return [
        OfferAdminOut(
            id=o.id, code=o.code, offer_type=o.offer_type.value,
            active=o.active, display_name=o.display_name,
            description=o.description, provider=o.provider,
            provider_price_ref=o.provider_price_ref, currency=o.currency,
            display_amount_minor=o.display_amount_minor,
            audit_credits=o.audit_credits,
            presence_credits=o.presence_credits,
            promo_eligible=o.promo_eligible, sort_order=o.sort_order,
            # Мапи віддаються як є: адміністратор бачить, яких мов
            # бракує, замість здогадуватися.
            display_name_i18n=dict(o.display_name_i18n or {}),
            description_i18n=dict(o.description_i18n or {}),
        )
        for o in rows
    ]


@router.put("/commerce/offers/{code}")
async def upsert_commerce_offer(
    code: str, payload: OfferIn, session: SessionDep, _: StaffDep
) -> OfferAdminOut:
    if payload.offer_type not in ("single", "pack"):
        raise HTTPException(status_code=422, detail="offer_type: single або pack")
    if payload.code != code:
        raise HTTPException(status_code=422, detail="code у тілі й шляху різні")
    if payload.offer_type == "single" and payload.audit_credits != 1:
        raise HTTPException(
            status_code=422,
            detail="SINGLE видає рівно одну перевірку — це його означення",
        )
    if payload.offer_type == "pack" and payload.audit_credits < 2:
        raise HTTPException(status_code=422, detail="PACK має давати 2+ одиниць")
    if payload.promo_eligible and payload.offer_type != "pack":
        raise HTTPException(
            status_code=422, detail="промокоди діють лише на PACK"
        )
    _require_complete_public_text(
        active=payload.active,
        maps={"display_name_i18n": payload.display_name_i18n,
              "description_i18n": payload.description_i18n},
    )
    if payload.display_amount_minor is None:
        raise HTTPException(
            status_code=422,
            detail="вкажіть ціну: без суми прайс у провайдера не опублікувати",
        )

    from app.application import catalogue_publishing as publishing
    from app.application import commerce as commerce_app
    from app.billing import catalog as billing_catalog
    from app.services import commerce_service

    # Спершу провайдер, потім база: сайт не сміє показати суму, за якою
    # каса не візьме гроші. Відмова провайдера — 502, запис не змінюється.
    provider = billing_catalog.current_provider()
    existing = await commerce_app.offer_by_code(session, code)
    price_ref, product_ref = publishing.remembered(
        provider,
        refs=existing.provider_refs if existing else None,
        row_provider=existing.provider if existing else None,
        price_ref=existing.provider_price_ref if existing else None,
        product_ref=existing.provider_product_ref if existing else None,
    )
    published = await _publish_or_502(
        publishing.offer_spec(
            code=code, offer_type=payload.offer_type,
            display_name=payload.display_name,
            display_name_i18n=payload.display_name_i18n,
            amount_minor=payload.display_amount_minor, currency=payload.currency,
        ),
        provider=provider, price_ref=price_ref, product_ref=product_ref,
    )
    values = payload.model_dump() | {
        "provider": published.provider,
        "provider_price_ref": published.price_ref,
        "provider_product_ref": published.product_ref,
        "provider_refs": publishing.with_ref(
            existing.provider_refs if existing else None, published
        ),
    }
    offer = await commerce_service.upsert_offer(session, code=code, values=values)
    await session.commit()
    return OfferAdminOut(
        id=offer.id,
        **(payload.model_dump() | {
            "provider": offer.provider, "provider_price_ref": offer.provider_price_ref,
        }),
    )


class CampaignIn(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=100)
    active: bool = True
    provider_discount_ref: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    description: str = ""


class CampaignSavedOut(BaseModel):
    code: str
    status: str


@router.put("/commerce/campaigns/{code}")
async def upsert_campaign(
    code: str, payload: CampaignIn, session: SessionDep, _: StaffDep
) -> CampaignSavedOut:
    from app.billing import catalog as billing_catalog
    from app.services import commerce_service

    if payload.code != code:
        raise HTTPException(status_code=422, detail="code у тілі й шляху різні")
    if payload.provider_discount_ref:
        # Знижку виконає чинний провайдер каси — його формою й міряємо.
        ref_problem = billing_catalog.ref_format_problem(
            billing_catalog.current_provider(),
            "discount",
            payload.provider_discount_ref,
        )
        if ref_problem:
            raise HTTPException(status_code=422, detail=ref_problem)
    await commerce_service.upsert_campaign(
        session, code=code, name=payload.name, active=payload.active,
        provider_discount_ref=payload.provider_discount_ref,
        starts_at=payload.starts_at, ends_at=payload.ends_at,
        description=payload.description,
    )
    await session.commit()
    return CampaignSavedOut(code=code, status="saved")


# ── MONTHLY: тарифи як конфігурація, не як код ────────────────────────────
#
# Місячна модель живе в `plans` + `plan_prices`, і все комерційне в ній —
# назва, видимість, права (ліміт краулів або безліміт, ліміт присутності),
# прайси провайдера, показові суми, порядок — редагується тут без релізу.
# «$49 → $79», «500 → 1000 краулів», «LIMITED → UNLIMITED» — це PUT, не
# деплой.


class PlanPriceIn(BaseModel):
    # Як і в пропозиції: провайдера й прайс пише публікація, поля з тіла
    # ігноруються.
    provider: str | None = Field(default=None, max_length=32)
    provider_price_id: str | None = Field(default=None, max_length=128)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    interval: str = "month"
    display_amount_minor: int | None = Field(default=None, ge=0)


class PlanIn(BaseModel):
    code: str = Field(min_length=1, max_length=48)
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    is_public: bool = True
    sort_order: int = 0
    entitlements: dict[str, Any]
    prices: list[PlanPriceIn] = Field(default_factory=list)
    # Та сама модель, що в пропозицій: порожньо — універсальна назва,
    # непорожньо в публічному тарифі — всі шість мов обовʼязкові.
    name_i18n: dict[str, str] = Field(default_factory=dict)
    description_i18n: dict[str, str] = Field(default_factory=dict)


class PlanAdminOut(BaseModel):
    code: str
    name: str
    description: str
    is_public: bool
    archived: bool
    sort_order: int
    entitlements: dict[str, Any]
    prices: list[dict[str, Any]]
    name_i18n: dict[str, str] = Field(default_factory=dict)
    description_i18n: dict[str, str] = Field(default_factory=dict)


@router.get("/commerce/plans")
async def list_commerce_plans(
    session: SessionDep, _: StaffDep
) -> list[PlanAdminOut]:
    from app.services import commerce_service

    return [
        PlanAdminOut(**row) for row in await commerce_service.all_plans(session)
    ]


@router.put("/commerce/plans/{code}")
async def upsert_commerce_plan(
    code: str, payload: PlanIn, session: SessionDep, _: StaffDep
) -> PlanAdminOut:
    from app.billing import catalog as billing_catalog
    from app.billing import entitlements
    from app.services import commerce_service

    if payload.code != code:
        raise HTTPException(status_code=422, detail="code у тілі й шляху різні")
    problems = entitlements.validate(payload.entitlements)
    if problems:
        raise HTTPException(status_code=422, detail={"entitlements": problems})
    _require_complete_public_text(
        active=payload.is_public,
        maps={"name_i18n": payload.name_i18n,
              "description_i18n": payload.description_i18n},
    )
    from app.application import catalogue_publishing as publishing

    provider = billing_catalog.current_provider()
    current = next(
        (row for row in await commerce_service.all_plans(session) if row["code"] == code),
        None,
    )
    price_rows: list[dict[str, Any]] = []
    for price in payload.prices:
        if price.interval not in ("month", "year"):
            raise HTTPException(
                status_code=422, detail=f"interval: month або year, не {price.interval!r}"
            )
        if price.display_amount_minor is None:
            raise HTTPException(
                status_code=422,
                detail="вкажіть ціну: без суми прайс у провайдера не опублікувати",
            )
        currency = price.currency.upper()
        known = next(
            (p for p in (current or {}).get("prices", [])
             if p["currency"] == currency and p["interval"] == price.interval),
            None,
        )
        price_ref, product_ref = publishing.remembered(
            provider,
            refs=known.get("provider_refs") if known else None,
            row_provider=known["provider"] if known else None,
            price_ref=known["provider_price_id"] if known else None,
            product_ref=known.get("provider_product_ref") if known else None,
        )
        published = await _publish_or_502(
            publishing.plan_spec(
                code=code, name=payload.name, name_i18n=payload.name_i18n,
                interval=price.interval, amount_minor=price.display_amount_minor,
                currency=currency,
            ),
            provider=provider, price_ref=price_ref, product_ref=product_ref,
        )
        price_rows.append({
            "provider": published.provider,
            "provider_price_id": published.price_ref,
            "provider_product_ref": published.product_ref,
            "provider_refs": publishing.with_ref(
                known.get("provider_refs") if known else None, published
            ),
            "currency": currency,
            "interval": price.interval,
            "display_amount_minor": price.display_amount_minor,
        })

    await commerce_service.upsert_plan(
        session,
        code=code,
        name=payload.name,
        description=payload.description,
        name_i18n=payload.name_i18n,
        description_i18n=payload.description_i18n,
        is_public=payload.is_public,
        sort_order=payload.sort_order,
        entitlement_values=payload.entitlements,
        prices=price_rows,
    )
    await session.commit()
    rows = await commerce_service.all_plans(session)
    saved = next(row for row in rows if row["code"] == code)
    return PlanAdminOut(**saved)


class GrantIn(BaseModel):
    credit_type: str = Field(pattern="^(audit|presence)$")
    quantity: int = Field(ge=1, le=100)
    reason: str = Field(min_length=3, max_length=255)


class GrantOut(BaseModel):
    granted: int
    credit_type: str


class OrgCommerceOut(BaseModel):
    balances: dict[str, int]
    credits: list[dict[str, Any]]
    purchases: list[dict[str, Any]]


@router.get("/commerce/orgs/{organization_id}")
async def org_commerce_view(
    organization_id: uuid.UUID, session: SessionDep, _: StaffDep
) -> OrgCommerceOut:
    """Що організація має і звідки воно взялося. Історію не редагуємо."""
    from app.services import commerce_service

    view = await commerce_service.org_view(
        session, organization_id=organization_id
    )
    return OrgCommerceOut(**view)


@router.post("/commerce/orgs/{organization_id}/grants")
async def grant_credits(
    organization_id: uuid.UUID,
    payload: GrantIn,
    session: SessionDep,
    staff: StaffDep,
) -> GrantOut:
    """Ручний грант — промо чи корекція. Причина обовʼязкова: рядок
    без пояснення не зможе пояснити себе через пів року."""
    from app.billing import credits as billing_credits

    granted = await billing_credits.grant(
        session,
        organization_id=organization_id,
        credit_type=payload.credit_type,
        quantity=payload.quantity,
        source="admin",
        reason=payload.reason,
        granted_by=staff.user_id,
    )
    await session.commit()
    return GrantOut(granted=granted, credit_type=payload.credit_type)
