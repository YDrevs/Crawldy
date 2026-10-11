"""Стан оплати й залишок квоти — розвʼязані один раз, на бекенді.

Обидві функції тут крихітні, і саме тому їх легко залишити в інтерфейсі.
Причина не робити цього одна: правило, повторене в кожному клієнті,
одного дня розходиться в одному з них — і розходиться мовчки, бо кожен
клієнт окремо виглядає правильним.
"""

from __future__ import annotations

from datetime import datetime

from app.billing.enums import BillingState, SubscriptionStatus
from app.models.billing import Subscription


def state_of(subscription: Subscription | None) -> BillingState:
    """Стан оплати одним словом.

    Відсутність підписки — це `FREE`, а не помилка й не «неактивна»:
    безкоштовний тариф теж тариф, і клієнт на ньому нічого не зламав.

    «Активна, але скасована наприкінці періоду» — окремий стан. У даних
    це статус плюс прапорець, для клієнта — інший текст і інша дія.
    """
    if subscription is None:
        return BillingState.FREE

    status = subscription.status
    if status is SubscriptionStatus.ACTIVE and subscription.cancel_at_period_end:
        return BillingState.CANCELLING
    return {
        SubscriptionStatus.INACTIVE: BillingState.FREE,
        SubscriptionStatus.TRIALING: BillingState.TRIALING,
        SubscriptionStatus.ACTIVE: BillingState.ACTIVE,
        SubscriptionStatus.PAST_DUE: BillingState.PAST_DUE,
        SubscriptionStatus.PAUSED: BillingState.PAUSED,
        SubscriptionStatus.CANCELLED: BillingState.CANCELLED,
    }[status]


def remaining(used: int, limit: int | None) -> int | None:
    """Скільки лишилось. `None` — без обмеження.

    Не просто різниця: перевитрата можлива. Зміна тарифу вниз лишає
    клієнта з десятьма використаними при новій межі пʼять, і від'ємне
    число в інтерфейсі виглядало б поломкою. Нуль — правда: більше не
    можна.
    """
    if limit is None:
        return None
    return max(0, limit - used)


def renews_at(subscription: Subscription | None) -> datetime | None:
    """Коли квота поновиться — або `None`, якщо не поновиться.

    Порожньо для скасованої підписки й для тієї, що доживає період:
    показати дату означало б обіцяти поновлення, якого не буде. Для
    безкоштовного тарифу теж порожньо — там межа календарна, і називати
    її «поновленням підписки» неправда.
    """
    if subscription is None or subscription.cancel_at_period_end:
        return None
    if not subscription.status.grants_entitlements:
        return None
    return subscription.current_period_end


__all__ = ["remaining", "renews_at", "state_of"]
