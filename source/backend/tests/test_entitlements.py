"""Права: резолюція, валідація, обрізання запиту.

Чистий шар — бази тут немає. Перевіряється правило, а не запит: назва
тарифу не має з'являтися в жодній перевірці, а відсутність підписки не
має означати відсутність відповіді.
"""

from __future__ import annotations

import pytest

from app.billing.entitlements import (
    FALLBACK,
    KEYS,
    EntitlementSet,
    UnknownEntitlement,
    resolve,
    validate,
)
from app.billing.enums import SubscriptionStatus


def test_an_organization_without_a_subscription_still_has_an_answer():
    """«Немає підписки» означає «безкоштовний тариф», а не «не знаю».

    Якби резолвер повертав None, кожна перевірка в коді мусила б окремо
    обробляти відсутність — і половина забула б.
    """
    ent = resolve(plan_code=None, plan_values=None)

    assert isinstance(ent, EntitlementSet)
    assert ent.plan_code == "free"
    assert ent.can("report_download") is False


def test_the_plan_replaces_the_defaults():
    ent = resolve(plan_code="pro", plan_values={"max_pages_per_audit": 50, "api_access": True})

    assert ent.limit("max_pages_per_audit") == 50
    assert ent.can("api_access") is True


def test_an_override_beats_the_plan():
    """Індивідуальні умови мусять бути можливі без правки коду.

    Перша ж нестандартна домовленість — компенсація, дідівські умови,
    доступ для партнера — інакше стає хардкодом.
    """
    ent = resolve(
        plan_code="starter",
        plan_values={"sites_limit": 5},
        overrides={"sites_limit": 50},
    )

    assert ent.limit("sites_limit") == 50
    assert ent.source == "plan+override"


def test_unlimited_is_not_zero():
    """`None` означає «без обмеження». Переплутати їх — це або віддати
    все, або не дати нічого."""
    ent = resolve(plan_code="agency", plan_values={"sites_limit": None})

    assert ent.limit("sites_limit") is None
    assert ent.can("sites_limit") is True
    assert ent.cap("sites_limit", 10_000) == 10_000


def test_zero_means_no():
    ent = resolve(plan_code="free", plan_values={"scheduled_audits": 0})

    assert ent.can("scheduled_audits") is False


def test_a_request_is_trimmed_to_what_is_allowed():
    """Саме так права потрапляють у двигун: він не питає про тариф, він
    отримує вже дозволені опції."""
    ent = resolve(plan_code="starter", plan_values={"max_pages_per_audit": 25})

    assert ent.cap("max_pages_per_audit", 100) == 25
    assert ent.cap("max_pages_per_audit", 5) == 5


def test_an_unknown_entitlement_is_an_error_not_a_silent_false():
    """Помилка в назві права мовчки перетворилася б на «заборонено» —
    і функція просто перестала б працювати без жодного сліду."""
    ent = resolve(plan_code="pro", plan_values={})

    with pytest.raises(UnknownEntitlement):
        ent.can("scheduled_audit")  # однина, друкарська помилка


def test_a_boolean_right_is_not_a_limit():
    ent = resolve(plan_code="pro", plan_values={"api_access": True})

    with pytest.raises(UnknownEntitlement):
        ent.limit("api_access")


def test_unknown_keys_in_a_plan_are_ignored_not_obeyed():
    """Тариф із вигаданим ключем не повинен нічого вмикати."""
    ent = resolve(plan_code="x", plan_values={"unlimited_everything": True})

    assert "unlimited_everything" not in ent.to_json()["values"]


@pytest.mark.parametrize(
    ("values", "expected_problem"),
    [
        ({"max_pages_per_audit": "багато"}, "очікується число"),
        ({"api_access": 1}, "очікується true/false"),
        ({"sites_limit": -5}, "від'ємний"),
        ({"api_access": None}, "не може бути None"),
        ({"вигаданий": 1}, "невідоме право"),
    ],
)
def test_validation_catches_what_the_database_cannot(values, expected_problem):
    """Права живуть у JSONB, і типів база не контролює.

    Тариф із рядком замість числа не зламається одразу — він зламається
    під час першої перевірки ліміту, тобто у клієнта.
    """
    problems = validate(values)

    assert problems
    assert any(expected_problem in p for p in problems)


def test_a_correct_plan_has_no_problems():
    assert validate({key: FALLBACK[key] for key in KEYS}) == []


def test_every_key_has_a_fallback():
    """Право без дефолта дало б KeyError у момент перевірки — тобто в
    найгіршому місці."""
    assert set(KEYS) == set(FALLBACK)


# ── стани підписки ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "grants"),
    [
        (SubscriptionStatus.INACTIVE, False),
        (SubscriptionStatus.TRIALING, True),
        (SubscriptionStatus.ACTIVE, True),
        (SubscriptionStatus.PAST_DUE, True),
        (SubscriptionStatus.PAUSED, False),
        (SubscriptionStatus.CANCELLED, False),
    ],
)
def test_which_states_grant_entitlements(status, grants):
    """`past_due` дає права навмисно.

    Відрізати клієнта, який платить, на першій невдалій спробі списання
    гірше, ніж кілька днів безкоштовного сервісу: карта протермінувалася,
    банк відхилив разову операцію, людина у відпустці.
    """
    assert status.grants_entitlements is grants
