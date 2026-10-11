"""Машина станів підписки: що дозволено, а що — розбіжність.

Чиста функція, тести без бази. Найважливіші тут негативні: недозволений
перехід мусить бути відмовою, бо він означає, що ми й провайдер
розійшлися в уявленні про підписку, — і це треба побачити, а не затерти.
"""

from __future__ import annotations

import pytest

from app.billing import state_machine
from app.billing.enums import BillingEventKind as K
from app.billing.enums import SubscriptionStatus as S
from app.billing.state_machine import InvalidTransition, next_status


def test_a_paid_start_activates_and_a_trial_start_trials():
    assert next_status(S.INACTIVE, K.SUBSCRIPTION_STARTED) is S.ACTIVE
    assert next_status(S.INACTIVE, K.SUBSCRIPTION_STARTED, with_trial=True) is S.TRIALING


def test_the_ordinary_life_of_a_subscription():
    """Trial → оплата → продовження → невдале списання → відновлення."""
    status = next_status(S.INACTIVE, K.SUBSCRIPTION_STARTED, with_trial=True)
    status = next_status(status, K.SUBSCRIPTION_RENEWED)
    assert status is S.ACTIVE
    status = next_status(status, K.PAYMENT_FAILED)
    assert status is S.PAST_DUE
    status = next_status(status, K.PAYMENT_RECOVERED)
    assert status is S.ACTIVE


def test_cancelled_is_absorbing():
    """Повернення клієнта — нова підписка, а не воскресіння старої."""
    for kind in K:
        with pytest.raises(InvalidTransition):
            next_status(S.CANCELLED, kind)


def test_cancellation_scheduled_does_not_change_the_status():
    """«Скасується наприкінці періоду» — прапорець, а не стан."""
    assert next_status(S.ACTIVE, K.CANCELLATION_SCHEDULED) is S.ACTIVE
    assert next_status(S.TRIALING, K.CANCELLATION_SCHEDULED) is S.TRIALING


def test_an_establishing_event_builds_state_from_nothing():
    """Провайдери не гарантують, що started прийде першим.

    Підписка, яка чекає на «правильний порядок», — це клієнт, який
    заплатив і не отримав.
    """
    assert next_status(S.INACTIVE, K.SUBSCRIPTION_RENEWED) is S.ACTIVE
    assert next_status(S.INACTIVE, K.PAYMENT_RECOVERED) is S.ACTIVE


def test_renewal_out_of_past_due_counts_as_recovery():
    """Частина провайдерів після відновлення шле renewed, а не recovered."""
    assert next_status(S.PAST_DUE, K.SUBSCRIPTION_RENEWED) is S.ACTIVE


def test_nonsense_is_refused_not_absorbed():
    with pytest.raises(InvalidTransition):
        next_status(S.ACTIVE, K.SUBSCRIPTION_RESUMED)  # активну нема з чого відновлювати
    with pytest.raises(InvalidTransition):
        next_status(S.PAUSED, K.PAYMENT_FAILED)  # призупинену не списують
    with pytest.raises(InvalidTransition):
        next_status(S.TRIALING, K.SUBSCRIPTION_PAUSED)  # пробну не ставлять на паузу


def test_the_error_names_both_sides_of_the_disagreement():
    """Той, хто читатиме журнал, має побачити стан і подію, а не «помилка»."""
    with pytest.raises(InvalidTransition) as caught:
        next_status(S.CANCELLED, K.SUBSCRIPTION_RENEWED)
    assert "cancelled" in str(caught.value)
    assert "subscription_renewed" in str(caught.value)


def test_every_declared_transition_lands_in_a_real_status():
    """Повнота таблиці перевіряється, а не мається на увазі."""
    for (source, kind), target in state_machine.TRANSITIONS.items():
        assert isinstance(source, S) and isinstance(target, S) and isinstance(kind, K)
        assert source is not S.CANCELLED, "з поглинального стану переходів немає"


def test_entitlement_effect_follows_the_status_not_the_event():
    """Права визначає стан. Подія лише веде до стану — це межа §7."""
    assert S.ACTIVE.grants_entitlements
    assert S.TRIALING.grants_entitlements
    assert S.PAST_DUE.grants_entitlements, "грація: платного клієнта не відрізають одразу"
    assert not S.PAUSED.grants_entitlements
    assert not S.CANCELLED.grants_entitlements
    assert not S.INACTIVE.grants_entitlements
