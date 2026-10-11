"""Чотири рішення з огляду P4.0–P4.6, зафіксовані перевірками.

1. Обрізання опцій видно назовні, а не лише в результаті.
2. Резерв квоти має завершення, і воно залежить від класу невдачі.
3. Сайт — бізнес-ресурс; origin — адреса, за якою він зараз відповідає.
4. Грація після невдалого платежу обмежена й налаштовується.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.audit.enums import AuditStatus
from app.billing import quota
from app.billing import service as billing
from app.billing.enums import SubscriptionStatus
from app.core.run_enums import FailureClass, QuotaState
from app.identity import service as identity
from app.models.audit import Audit, AuditTarget
from app.models.billing import Subscription
from tests.integration.conftest import grant_audit_credits, register, sign_in_as

PASSWORD = "correct-horse-battery"


def _now() -> datetime:
    return datetime.now(UTC)


async def _org(db, email="a@example.com"):
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    return reg.organization.id


async def _paying_customer(client, db) -> None:
    """Акаунт із купленою одиницею: безкоштовних повних аудитів немає."""
    await register(client, "a@example.com")
    me = (await client.get("/v1/auth/me")).json()
    await grant_audit_credits(
        db, organization_id=uuid.UUID(me["organization"]["id"])
    )


# ── 1. прозоре обрізання ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_api_says_what_the_plan_took_away(client, db_session):
    """Клієнт бачить не лише результат, а й різницю з тим, що просив.

    Мовчазне обрізання — це відповідь не на те питання, яке поставили.
    """
    await _paying_customer(client, db_session)

    response = await client.post(
        "/v1/audits", json={"url": "https://example.com", "options": {"max_pages": 100}}
    )

    adjustments = response.json()["option_adjustments"]
    assert len(adjustments) == 1
    assert adjustments[0] == {
        "option": "max_pages",
        "requested": 100,
        "effective": 10,
        "limited_by": "max_pages_per_audit",
    }


@pytest.mark.asyncio
async def test_a_switched_off_feature_is_reported_too(client, db_session):
    await _paying_customer(client, db_session)

    response = await client.post(
        "/v1/audits", json={"url": "https://example.com", "options": {"llm": True}}
    )

    adjustments = response.json()["option_adjustments"]
    assert {"option": "llm", "requested": True, "effective": False,
            "limited_by": "semantic_analysis"} in adjustments


@pytest.mark.asyncio
async def test_no_adjustments_is_also_an_answer(client, db_session):
    """Порожній перелік означає «тариф ні на що не вплинув»."""
    await _paying_customer(client, db_session)

    response = await client.post(
        "/v1/audits", json={"url": "https://example.com", "options": {"max_pages": 5}}
    )

    assert response.json()["option_adjustments"] == []


@pytest.mark.asyncio
async def test_both_versions_of_the_options_are_kept(client, db_session):
    """Пара «просив / зробили» і є фактом; різниця — похідна від неї."""
    await _paying_customer(client, db_session)
    response = await client.post(
        "/v1/audits", json={"url": "https://example.com", "options": {"max_pages": 100}}
    )

    stored = await db_session.get(Audit, uuid.UUID(response.json()["id"]))

    assert stored.requested_options["max_pages"] == 100
    assert stored.options["max_pages"] == 10


@pytest.mark.asyncio
async def test_the_adjustment_survives_a_later_read(client, db_session):
    """Через місяць правил під рукою вже немає — різниця має читатися з
    самого запису."""
    await _paying_customer(client, db_session)
    created = await client.post(
        "/v1/audits", json={"url": "https://example.com", "options": {"max_pages": 100}}
    )

    listed = (await client.get("/v1/audits")).json()

    assert listed[0]["option_adjustments"] == created.json()["option_adjustments"]


# ── 2. життєвий цикл квоти ─────────────────────────────────────────────────


async def _reserved_audit(db, org_id) -> Audit:
    audit = Audit(
        organization_id=org_id,
        url="https://example.com/",
        origin="https://example.com",
        status=AuditStatus.QUEUED,
        options={},
        quota_state=QuotaState.RESERVED,
    )
    db.add(audit)
    await db.flush()
    await quota.consume(
        db, organization_id=org_id, period=quota.period_for(None), limit=10
    )
    return audit


@pytest.mark.asyncio
async def test_a_finished_audit_consumes_the_reservation(db_session):
    from app.application import audits as application

    org = await _org(db_session)
    audit = await _reserved_audit(db_session, org)

    state = await application.settle_quota(db_session, audit)

    assert state is QuotaState.CONSUMED
    assert await quota.used_in(db_session, organization_id=org, period=quota.period_for(None)) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure", "expected", "left"),
    [
        (FailureClass.SITE_UNREACHABLE, QuotaState.CONSUMED, 1),
        (FailureClass.SITE_BLOCKED, QuotaState.CONSUMED, 1),
        (FailureClass.PROVIDER_FAILED, QuotaState.RELEASED, 0),
        (FailureClass.INTERNAL_ERROR, QuotaState.RELEASED, 0),
        (FailureClass.CANCELLED, QuotaState.RELEASED, 0),
    ],
)
async def test_who_pays_for_which_failure(db_session, failure, expected, left):
    """Клієнт не платить за нашу поломку й за недоступність провайдера.

    Але й не отримує назад за те, що його власний сайт не відповів: краул
    відбувся, відповідь чесна, робота зроблена.
    """
    from app.application import audits as application

    org = await _org(db_session)
    audit = await _reserved_audit(db_session, org)

    state = await application.settle_quota(db_session, audit, failure=failure)

    assert state is expected
    assert audit.failure_class is failure
    used = await quota.used_in(db_session, organization_id=org, period=quota.period_for(None))
    assert used == left


@pytest.mark.asyncio
async def test_settling_twice_does_nothing_the_second_time(db_session):
    """Повтор задачі не має повертати квоту вдруге."""
    from app.application import audits as application

    org = await _org(db_session)
    audit = await _reserved_audit(db_session, org)

    await application.settle_quota(db_session, audit, failure=FailureClass.INTERNAL_ERROR)
    await application.settle_quota(db_session, audit, failure=FailureClass.INTERNAL_ERROR)

    assert await quota.used_in(db_session, organization_id=org, period=quota.period_for(None)) == 0


def test_unknown_failures_are_charged_to_us_not_to_the_client():
    """Дефолт класифікатора — внутрішня помилка.

    Невідомий виняток означає, що ми не розібралися, і платити за це має
    не клієнт.
    """
    from app.application.failures import classify

    assert classify(RuntimeError("щось нове")) is FailureClass.INTERNAL_ERROR


def test_a_site_that_did_not_answer_is_not_our_fault():
    from app.application.failures import classify
    from app.audit.fetcher import SiteUnreachable

    assert classify(SiteUnreachable("DNS")) is FailureClass.SITE_UNREACHABLE


# ── 3. сайт як ресурс, origin як адреса ────────────────────────────────────


@pytest.mark.asyncio
async def test_history_is_keyed_by_the_site_not_by_the_address(client, db_session):
    """Головна перевірка третього рішення.

    Аудити лежать із двома різними origin — так буває після переїзду на
    https або на www. Прив'язані вони до одного сайту, і історія бачить
    обидва: ресурс той самий, адреса змінилася.
    """
    await register(client, "a@example.com")
    site = (await client.post("/v1/sites", json={"url": "http://example.com"})).json()

    for origin in ("http://example.com", "https://example.com"):
        audit = Audit(
            organization_id=uuid.UUID((await client.get("/v1/auth/me")).json()["organization"]["id"]),
            site_id=uuid.UUID(site["id"]),
            url=f"{origin}/",
            origin=origin,
            status=AuditStatus.COMPLETED,
            options={},
        )
        db_session.add(audit)
        await db_session.flush()
        db_session.add(
            AuditTarget(
                audit_id=audit.id,
                position=0,
                url=f"{origin}/",
                origin=origin,
                status=AuditStatus.COMPLETED,
                score_overall=70,
                scores={"seo": 70},
                versions={"detector": "d1", "scoring": "s1"},
                finished_at=_now(),
            )
        )
    await db_session.flush()

    history = (await client.get(f"/v1/sites/{site['id']}/history")).json()

    assert len(history["points"]) == 2, "адреса змінилася, ресурс той самий"


@pytest.mark.asyncio
async def test_merging_two_sites_would_not_rewrite_the_past(client, db_session):
    """Доказ, що рішення «не зливати автоматично» не прив'язує продукт
    до origin назавжди.

    Об'єднання — це переведення `audits.site_id`. Самі аудити, їхні
    origin і бали лишаються недоторканими, а історія йде за ресурсом.
    """
    await register(client, "a@example.com")
    org = uuid.UUID((await client.get("/v1/auth/me")).json()["organization"]["id"])
    old = (await client.post("/v1/sites", json={"url": "http://example.com"})).json()
    new = (await client.post("/v1/sites", json={"url": "https://example.com"})).json()

    audit = Audit(
        organization_id=org,
        site_id=uuid.UUID(old["id"]),
        url="http://example.com/",
        origin="http://example.com",
        status=AuditStatus.COMPLETED,
        options={},
    )
    db_session.add(audit)
    await db_session.flush()
    db_session.add(
        AuditTarget(
            audit_id=audit.id,
            position=0,
            url="http://example.com/",
            origin="http://example.com",
            status=AuditStatus.COMPLETED,
            score_overall=65,
            scores={"seo": 65},
            versions={},
            finished_at=_now(),
        )
    )
    await db_session.flush()

    # Ось і все «об'єднання»: одна колонка, жодного переписування минулого.
    audit.site_id = uuid.UUID(new["id"])
    await db_session.flush()

    moved = (await client.get(f"/v1/sites/{new['id']}/history")).json()
    left = (await client.get(f"/v1/sites/{old['id']}/history")).json()

    assert len(moved["points"]) == 1
    assert left["points"] == []
    assert audit.origin == "http://example.com", "адреса аудиту не переписана"


@pytest.mark.asyncio
async def test_a_foreign_site_history_is_not_visible(client, db_session):
    await register(client, "victim@example.com")
    site = (await client.post("/v1/sites", json={"url": "https://secret.example"})).json()

    await sign_in_as(client, "attacker@example.com")

    assert (await client.get(f"/v1/sites/{site['id']}/history")).status_code == 404


# ── 4. грація ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_grace_is_written_down_explicitly(db_session):
    """Перехід у past_due проставляє строк, а не лишає його на здогадку."""
    org = await _org(db_session)
    plan = await billing.plan_by_code(db_session, "pro")
    record = Subscription(
        organization_id=org,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        provider="paddle",
        current_period_start=_now() - timedelta(days=5),
        current_period_end=_now() + timedelta(days=25),
    )
    db_session.add(record)
    await db_session.flush()

    deadline = billing.enter_past_due(record)

    assert record.status is SubscriptionStatus.PAST_DUE
    assert record.grace_until == deadline
    assert deadline > _now()


@pytest.mark.asyncio
async def test_the_grace_length_is_configuration_not_code(db_session, monkeypatch):
    from app.core.config import settings

    monkeypatch.setattr(settings, "billing_past_due_grace_days", 1)
    org = await _org(db_session)
    plan = await billing.plan_by_code(db_session, "pro")
    record = Subscription(
        organization_id=org,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        provider="paddle",
        current_period_end=_now() + timedelta(days=25),
    )
    db_session.add(record)
    await db_session.flush()

    deadline = billing.enter_past_due(record)

    assert deadline - _now() < timedelta(days=2)


@pytest.mark.asyncio
async def test_zero_grace_means_cut_off_immediately(db_session, monkeypatch):
    """Нуль — теж політика, і вона має працювати.

    Безмежного доступу немає ні за яких налаштувань.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "billing_past_due_grace_days", 0)
    org = await _org(db_session)
    plan = await billing.plan_by_code(db_session, "pro")
    record = Subscription(
        organization_id=org,
        plan_id=plan.id,
        status=SubscriptionStatus.ACTIVE,
        provider="paddle",
        current_period_end=_now() + timedelta(days=25),
    )
    db_session.add(record)
    await db_session.flush()
    billing.enter_past_due(record, at=_now() - timedelta(seconds=1))
    await db_session.flush()

    ent = await billing.for_organization(db_session, organization_id=org)

    assert ent.plan_code == "free"


@pytest.mark.asyncio
async def test_a_subscription_that_bypassed_our_code_still_has_a_deadline(db_session):
    """Запобіжник: у продукті не має бути стану «права діють невідомо доки».

    Підписка, що потрапила в past_due повз `enter_past_due`, все одно
    отримує обчислений строк, а не безмежний доступ.
    """
    org = await _org(db_session)
    plan = await billing.plan_by_code(db_session, "pro")
    record = Subscription(
        organization_id=org,
        plan_id=plan.id,
        status=SubscriptionStatus.PAST_DUE,
        provider="paddle",
        current_period_end=_now() - timedelta(days=365),
        grace_until=None,
    )
    db_session.add(record)
    await db_session.flush()

    assert billing.grace_deadline(record) < _now()
    ent = await billing.for_organization(db_session, organization_id=org)
    assert ent.plan_code == "free"


@pytest.mark.asyncio
async def test_the_refund_policy_is_replaceable_without_touching_the_state_machine(
    db_session, monkeypatch
):
    """Політика — конфігурація, а не структура.

    Змінити, за що повертається квота, можна налаштуванням: ні машина
    станів (`reserved → consumed | released`), ні класифікатор невдач
    про цю зміну не знають і не міняються.
    """
    from app.application import audits as application
    from app.core.config import settings

    monkeypatch.setattr(settings, "billing_refundable_failures", ["site_blocked"])
    org = await _org(db_session, "policy@example.com")
    audit = await _reserved_audit(db_session, org)

    state = await application.settle_quota(
        db_session, audit, failure=FailureClass.SITE_BLOCKED
    )

    assert state is QuotaState.RELEASED, "політику змінено — поведінка пішла за нею"
    assert await quota.used_in(db_session, organization_id=org, period=quota.period_for(None)) == 0


def test_a_typo_in_the_policy_does_not_silently_widen_it():
    """Невідома назва класу ігнорується.

    Помилка друку в змінній оточення не має мовчки розширювати
    повернення — і не має його мовчки звужувати теж.
    """
    from app.billing import refund_policy
    from app.core.config import settings

    original = settings.billing_refundable_failures
    settings.billing_refundable_failures = ["internal_error", "вигаданий_клас"]
    try:
        assert refund_policy.refundable() == {FailureClass.INTERNAL_ERROR}
    finally:
        settings.billing_refundable_failures = original
