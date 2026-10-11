"""Стан оплати й залишок квоти — правило живе в одному місці.

Тести без бази: це чиста функція від підписки, і саме такі правила
найчастіше дублюють у кожному клієнті, поки вони не розійдуться.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.billing import state as billing_state
from app.billing.enums import BillingState, SubscriptionStatus
from app.models.billing import Subscription


def _sub(status: SubscriptionStatus, *, cancelling: bool = False) -> Subscription:
    return Subscription(
        status=status,
        cancel_at_period_end=cancelling,
        current_period_end=datetime.now(UTC) + timedelta(days=21),
        provider="fake",
    )


def test_no_subscription_is_free_not_broken():
    """Безкоштовний тариф — теж тариф, і клієнт на ньому нічого не зламав."""
    assert billing_state.state_of(None) is BillingState.FREE


def test_cancelling_is_its_own_state_not_active_with_a_flag():
    """Для клієнта це інший текст і інша дія, ніж просто «активна»."""
    assert (
        billing_state.state_of(_sub(SubscriptionStatus.ACTIVE, cancelling=True))
        is BillingState.CANCELLING
    )
    assert (
        billing_state.state_of(_sub(SubscriptionStatus.ACTIVE))
        is BillingState.ACTIVE
    )


def test_past_due_is_visible_because_the_client_can_still_act():
    assert (
        billing_state.state_of(_sub(SubscriptionStatus.PAST_DUE))
        is BillingState.PAST_DUE
    )


def test_every_subscription_status_maps_somewhere():
    """Новий статус не має тихо провалитися в дефолт."""
    for status in SubscriptionStatus:
        assert billing_state.state_of(_sub(status)) in set(BillingState)


# ── залишок ────────────────────────────────────────────────────────────────


def test_unlimited_has_no_remaining_number():
    assert billing_state.remaining(used=40, limit=None) is None


def test_overspending_shows_zero_not_a_negative_number():
    """Зниження тарифу лишає клієнта з десятьма при новій межі пʼять.

    Мінус пʼять в інтерфейсі виглядає поломкою; нуль — правда.
    """
    assert billing_state.remaining(used=10, limit=5) == 0


def test_remaining_is_the_plain_difference_otherwise():
    assert billing_state.remaining(used=23, limit=50) == 27


# ── дата поновлення ────────────────────────────────────────────────────────


def test_a_cancelling_subscription_has_no_renewal_date():
    """Показати дату означало б обіцяти поновлення, якого не буде."""
    assert billing_state.renews_at(_sub(SubscriptionStatus.ACTIVE, cancelling=True)) is None


def test_a_cancelled_subscription_has_no_renewal_date():
    assert billing_state.renews_at(_sub(SubscriptionStatus.CANCELLED)) is None


def test_free_plan_has_no_renewal_date():
    """Межа там календарна, і називати її поновленням підписки — неправда."""
    assert billing_state.renews_at(None) is None


def test_an_active_subscription_renews_at_the_period_end():
    subscription = _sub(SubscriptionStatus.ACTIVE)
    assert billing_state.renews_at(subscription) == subscription.current_period_end
