"""Акаунт: тариф, підписка, права, використання — одним ресурсом."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app.api.deps import ActorDep, OwnerDep, SessionDep
from app.application import guest as guest_app
from app.application.catalog import localized_text
from app.audit.i18n import Locale
from app.billing import credits, quota
from app.billing import service as billing_service
from app.billing import state as billing_state
from app.identity import service as identity
from app.schemas.account import (
    AccountOrganizationOut,
    AccountOut,
    PlanOut,
    SubscriptionOut,
    UsageOut,
)

router = APIRouter(prefix="/v1/account", tags=["account"])


@router.get("", response_model=AccountOut)
async def get_account(
    session: SessionDep, actor: ActorDep, lang: Locale | None = None
) -> AccountOut:
    """Стан акаунта очима продукту.

    `entitlements` — уже розвʼязані значення (дефолт → тариф →
    індивідуальні винятки), тобто те, що справді діє. Інтерфейс не має
    повторювати резолвер, щоб показати, скільки сторінок дозволено.
    """
    organization = await identity.get_organization(
        session, organization_id=actor.organization_id
    )
    if organization is None:
        raise HTTPException(status_code=404, detail="організацію не знайдено")

    resolved = await billing_service.for_organization(
        session, organization_id=actor.organization_id
    )
    plan = await billing_service.plan_by_code(session, resolved.plan_code)
    subscription = await billing_service.active_subscription(
        session, organization_id=actor.organization_id
    )

    period = quota.period_for(subscription)
    used = await quota.used_in(
        session, organization_id=actor.organization_id, period=period
    )
    one_off = await credits.balance(session, organization_id=actor.organization_id)
    presence_credits = await credits.balance(
        session, organization_id=actor.organization_id, credit_type="presence"
    )
    presence_used = await quota.used_in(
        session, organization_id=actor.organization_id, period=period,
        metric="presence",
    )
    presence_limit = resolved.limit("presence_per_period")
    limit = resolved.limit("audits_per_period")

    return AccountOut(
        organization=AccountOrganizationOut.model_validate(organization),
        role=actor.role.value,
        plan=PlanOut(
            code=resolved.plan_code,
            # Назва — мовою кабінету: англійський кабінет не сміє
            # показувати українську назву тарифу дослівно з бази.
            name=(
                localized_text(plan.name, plan.name_i18n, lang or Locale.EN)
                if plan is not None else resolved.plan_code
            ),
        ),
        subscription=(
            SubscriptionOut.model_validate(subscription) if subscription is not None else None
        ),
        billing_state=billing_state.state_of(subscription),
        entitlements=dict(resolved.values),
        usage=UsageOut(
            audits_used=used,
            audits_limit=limit,
            audits_remaining=billing_state.remaining(used, limit),
            period_start=period.start,
            period_end=period.end,
            renews_at=billing_state.renews_at(subscription),
            one_off_available=one_off,
            presence_used=presence_used,
            presence_limit=presence_limit,
            presence_remaining=billing_state.remaining(presence_used, presence_limit),
            presence_credits_available=presence_credits,
        ),
    )


class GuestMergeIn(BaseModel):
    """Злиття гостьової організації в організацію актора.

    Тіло не називає ціль: вона береться з автентифікації, як і всюди.
    Ціль у тілі означала б, що будь-хто підставляє чужу — і перевірка
    власності перетворюється на формальність.
    """

    reason: str = Field(default="", max_length=500)


class GuestMergeOut(BaseModel):
    merge_id: uuid.UUID
    audits_moved: int
    purchases_moved: int
    credits_moved: int


@router.post("/guest-merge", response_model=GuestMergeOut, status_code=status.HTTP_201_CREATED)
async def merge_guest(
    payload: GuestMergeIn,
    session: SessionDep,
    actor: OwnerDep,
    x_guest_token: Annotated[str | None, Header()] = None,
) -> GuestMergeOut:
    """Перенести гостьові ресурси в організацію актора.

    Запит доводить обидва права одразу: токен гостя в заголовку — що
    людина контролює гостьовий контекст, роль OWNER з автентифікації —
    що їй можна приймати чужі покупки в цю організацію. Пошта не бере
    участі ні в першому, ні в другому.
    """
    if not x_guest_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    try:
        guest_session = await guest_app.resolve(session, x_guest_token)
    except guest_app.GuestError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено") from exc

    try:
        merged = await guest_app.merge_into(
            session,
            session=guest_session,
            destination_organization_id=actor.organization_id,
            performed_by_user_id=actor.user_id,
            reason=payload.reason,
        )
    except guest_app.QuotaNotSettled as exc:
        # Минуще: аудит гостя ще не розрахований із квотою. Клієнт
        # повторює запит пізніше; примусовий розрахунок тут означав би
        # вирішувати долю чужого резерву заради зручності злиття.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "quota.pending", "retryable": True},
        ) from exc
    except guest_app.AlreadyClaimed as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "already.claimed", "retryable": False},
        ) from exc
    except guest_app.CannotMergeInto as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "destination.invalid", "retryable": False},
        ) from exc

    await session.commit()
    return GuestMergeOut(
        merge_id=merged.merge.id,
        audits_moved=merged.audits_moved,
        purchases_moved=merged.purchases_moved,
        credits_moved=merged.credits_moved,
    )


class PortalOut(BaseModel):
    url: str


class PaymentStateOut(BaseModel):
    """Чи чекає кабінет на підтвердження оплати від провайдера."""

    awaiting_event: bool


@router.get("/payment-state", response_model=PaymentStateOut)
async def payment_state(session: SessionDep, actor: ActorDep) -> PaymentStateOut:
    """Гроші провайдер отримав, а події ще немає.

    Читання, яке нічого не видає: права й далі дає лише перевірена подія.
    Існує заради одного стану, у якому кабінет раніше мовчав, — «я щойно
    заплатив, а тут порожньо». Мовчання читалось як зникнення грошей.
    """
    from app.application import purchases as purchases_app

    return PaymentStateOut(
        awaiting_event=await purchases_app.awaiting_event(
            session, organization_id=actor.organization_id
        )
    )


class PurchaseStateOut(BaseModel):
    """Що з цією покупкою — той самий контракт, що й у гостя.

    `charged` тримає три відповіді, а не дві: `True` — провайдер узяв
    гроші, `False` — провайдер сказав, що не брав, `None` — він не
    відповів. Останнє не «ні»: сказати «кошти не списано» на підставі
    тайм-ауту означало б запросити до другої оплати того, хто вже
    заплатив.
    """

    purchase_id: uuid.UUID
    state: str
    charged: bool | None


@router.get("/purchases/{purchase_id}", response_model=PurchaseStateOut)
async def purchase_state(
    purchase_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    reconcile: bool = False,
) -> PurchaseStateOut:
    """Стан однієї покупки кабінету. Автентифікований близнюк
    `GET /v1/public/orders/{id}`.

    Потрібен рівно там, де події не буде ніколи: людина відкрила касу
    зі сторінки оплати й закрила вікно. Без прямого питання екран не
    відрізняє «передумав» від «заплатив, а подія в дорозі» — і або
    крутить спінер вічно, або обіцяє «кошти не списано» тому, хто
    заплатив. Обидва стани сторінка вже вміє показувати; бракувало
    саме цієї відповіді.

    `reconcile` питає провайдера й тому вмикається лише після закритої
    каси: поки вікно відкрите, вистачає власних записів.

    Права не видає й нічого не змінює: доступ і далі відкриває тільки
    перевірена подія провайдера.
    """
    from app.application import purchases as purchases_app

    purchase = await purchases_app.owned_purchase(
        session, organization_id=actor.organization_id, purchase_id=purchase_id
    )
    if purchase is None:
        # Чужа покупка — 404, як усюди: «доступ заборонено» підтвердило
        # б, що вона існує.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    return PurchaseStateOut(
        purchase_id=purchase_id,
        state=await purchases_app.state_of(session, purchase=purchase),
        charged=await purchases_app.charged_of(
            session, purchase=purchase, ask_provider=reconcile
        ),
    )


@router.post(
    "/portal-session", response_model=PortalOut, status_code=status.HTTP_201_CREATED
)
async def create_portal_session(session: SessionDep, actor: OwnerDep) -> PortalOut:
    """Створити свіжу сесію хостованого кабінету провайдера.

    POST, бо це дія зі станом: кожен виклик породжує нову тимчасову
    сесію в провайдера. «Платежі і квитанції» — його сторінка, не наша:
    платіжні методи, рахунки, скасування підписки живуть там. Посилання
    одноразове, ніде не зберігається й не кешується — клієнт одразу
    переходить за ним.

    Лише власник: там скасовують підписку й міняють картку, а ключ API
    діє «не білінгом», як і рядовий учасник.
    """
    from app.application import billing as billing_app
    try:
        url = await billing_app.portal_url(
            session, organization_id=actor.organization_id
        )
    except billing_app.PortalUnavailable as exc:
        # Провайдер відмовив — це не «профілю немає». Різниця практична:
        # у першому випадку робота на нашому боці (права ключа, мережа),
        # у другому людина просто ще не платила. 502 відрізняє їх у
        # кабінеті, і причина йде поруч: службовий екран її прочитає.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"портал провайдера не відкрився: {exc}",
        ) from exc
    if url is None:
        raise HTTPException(
            status_code=404,
            detail="платіжного профілю ще немає — він зʼявиться після першої оплати",
        )
    return PortalOut(url=url)
