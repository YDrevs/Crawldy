"""Службовий кабінет проти живої бази: права, конфігурація, тести, аналітика.

Перевіряється те, що не видно з юніт-рівня:

- **права** — без платформної ролі кожен службовий маршрут відповідає
  403, і це стосується конфігурації, аналітики й запуску прогонів;
- **секрет** — збережений через API не повертається назад у жодному полі
  й справді змінює те, що читає код;
- **службовий прогін** — не резервує квоти, не створює покупки й
  виключений з аналітики;
- **аналітика** — рахує оплачені покупки, а не всі, і не плутає
  унікальні сайти з кількістю виконань.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.audit.enums import AuditStatus
from app.billing.enums import CommerceModel, CreditState, PurchaseStatus
from app.core import runtime_config as runtime
from app.core.config import settings
from app.core.run_enums import QuotaSource, QuotaState
from app.identity.enums import PlatformRole
from app.models.audit import Audit
from app.models.identity import Organization, User
from app.models.presence import PresenceRun
from app.models.purchase import AuditCredit, OneOffPurchase

from .conftest import register

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def staff(client, db_session):
    """Клієнт зі службовою роллю: реєстрація + підняття platform_role."""
    body = (await register(client, f"admin-{uuid.uuid4().hex[:8]}@example.com")).json()
    await db_session.execute(
        sa_update(User)
        .where(User.id == uuid.UUID(body["user"]["id"]))
        .values(platform_role=PlatformRole.STAFF)
    )
    await db_session.commit()
    return client


@pytest_asyncio.fixture
async def customer(client, db_session):
    """Звичайний клієнт без платформної ролі — той, кому має бути 403."""
    await register(client, f"plain-{uuid.uuid4().hex[:8]}@example.com")
    return client


async def _org(db_session) -> uuid.UUID:
    return (await db_session.execute(
        select(Organization.id).order_by(Organization.created_at.desc()).limit(1)
    )).scalar_one()


# ── права ───────────────────────────────────────────────────────────────

ADMIN_GETS = [
    "/v1/admin/config/payment",
    "/v1/admin/config/ai",
    "/v1/admin/analytics",
    "/v1/admin/testing/audits",
    "/v1/admin/testing/presence",
]


@pytest.mark.parametrize("path", ADMIN_GETS)
async def test_customer_is_refused_by_the_server(customer, path):
    assert (await customer.get(path)).status_code == 403


async def test_anonymous_is_refused(client):
    for path in ADMIN_GETS:
        assert (await client.get(path)).status_code in (401, 403)


async def test_customer_cannot_start_a_test_run(customer):
    response = await customer.post(
        "/v1/admin/testing/audits", json={"url": "https://example.com"}
    )
    assert response.status_code == 403


async def test_staff_reads_configuration(staff):
    response = await staff.get("/v1/admin/config/payment")
    assert response.status_code == 200
    body = response.json()
    assert body["webhook_url"].endswith("/v1/webhooks/paddle")
    assert {f["key"] for f in body["fields"]} >= {"paddle_api_key", "paddle_env"}


# ── конфігурація ────────────────────────────────────────────────────────


async def test_saved_secret_never_comes_back(staff, monkeypatch):
    monkeypatch.setattr(settings, "secrets_key", "integration-test-key")
    runtime.reset_cache()
    secret = "pdl_sdbx_apikey_integration_value"
    response = await staff.put(
        "/v1/admin/config/payment", json={"values": {"paddle_api_key": secret}}
    )
    assert response.status_code == 200, response.text
    body = response.text
    assert secret not in body
    field = next(f for f in response.json()["fields"] if f["key"] == "paddle_api_key")
    assert field["value"] is None
    assert field["configured"] is True
    assert field["source"] == "admin"
    # …і код читає саме збережене значення.
    assert runtime.get("paddle_api_key") == secret


async def test_saved_value_is_what_the_code_reads(staff, monkeypatch):
    monkeypatch.setattr(settings, "paddle_env", "sandbox")
    runtime.reset_cache()
    response = await staff.put(
        "/v1/admin/config/payment", json={"values": {"paddle_env": "live"}}
    )
    assert response.status_code == 200
    assert runtime.get("paddle_env") == "live"
    assert runtime.source("paddle_env") == "admin"
    # Прибирання повертає до оточення, а не до порожнечі.
    assert (await staff.put(
        "/v1/admin/config/payment", json={"values": {"paddle_env": None}}
    )).status_code == 200
    assert runtime.get("paddle_env") == "sandbox"
    assert runtime.source("paddle_env") == "env"


async def test_bad_format_is_refused_before_writing(staff):
    response = await staff.put(
        "/v1/admin/config/payment", json={"values": {"paddle_api_key": "nonsense"}}
    )
    assert response.status_code == 422
    assert "paddle_api_key" in response.json()["detail"]["errors"]


async def test_ai_policy_change_is_what_the_runtime_reads(staff, db_session):
    from app.services import presence_service

    current = (await staff.get("/v1/admin/config/ai")).json()
    policy = current["policy"]
    policy["enabled"] = True
    policy["providers"]["openai"]["enabled"] = False
    response = await staff.put("/v1/admin/config/ai", json={"policy": policy})
    assert response.status_code == 200, response.text
    stored = await presence_service.load_policy(db_session)
    assert stored.enabled is True
    assert stored.providers["openai"].enabled is False
    assert "openai" not in stored.active_providers()


async def test_unknown_model_is_refused_with_a_reason(staff):
    current = (await staff.get("/v1/admin/config/ai")).json()
    policy = current["policy"]
    policy["providers"]["anthropic"]["enabled"] = True
    policy["providers"]["anthropic"]["model"] = "claude-does-not-exist"
    response = await staff.put("/v1/admin/config/ai", json={"policy": policy})
    assert response.status_code == 422
    assert any("каталозі" in e for e in response.json()["detail"]["errors"]["policy"])


# ── службові прогони ────────────────────────────────────────────────────


async def test_admin_audit_consumes_no_quota_and_creates_no_sale(
    staff, db_session, queue_is_not_the_subject
):
    response = await staff.post(
        "/v1/admin/testing/audits",
        json={"url": "https://example.com", "options": {"max_pages": 3}},
    )
    assert response.status_code == 202, response.text
    audit_id = uuid.UUID(response.json()["id"])
    audit = await db_session.get(Audit, audit_id)
    assert audit is not None
    assert audit.quota_source is QuotaSource.ADMIN_TEST
    # Резерву не було: доля одиниці вирішена одразу.
    assert audit.quota_state is QuotaState.CONSUMED
    # Жодного кредита не зарезервовано й жодної покупки не створено.
    org = await _org(db_session)
    credits = (await db_session.execute(
        select(AuditCredit).where(AuditCredit.organization_id == org)
    )).scalars().all()
    assert credits == []
    purchases = (await db_session.execute(
        select(OneOffPurchase).where(OneOffPurchase.organization_id == org)
    )).scalars().all()
    assert purchases == []
    # І задача таки поставлена в чергу — прогін справжній.
    assert audit_id in queue_is_not_the_subject


async def test_admin_presence_run_has_no_organization(staff, db_session):
    from dataclasses import replace

    from app.presence import policy as presence_policy
    from app.services import presence_service

    policy = await presence_service.load_policy(db_session)
    await presence_service.save_policy(
        db_session, presence_policy.to_stored(replace(policy, enabled=True))
    )
    await db_session.commit()

    response = await staff.post(
        "/v1/admin/testing/presence",
        json={
            "url": "https://example.com",
            "brand": "Example",
            "category": "software",
            "provider": "anthropic",
        },
    )
    assert response.status_code == 202, response.text
    run = await db_session.get(PresenceRun, uuid.UUID(response.json()["id"]))
    assert run is not None
    assert run.organization_id is None
    assert run.entitlement_source == "internal"
    # Рівно один провайдер увімкнений у знімку політики прогону.
    enabled = [
        name
        for name, p in run.policy_snapshot["providers"].items()
        if p.get("enabled")
    ]
    assert enabled == ["anthropic"]


async def test_admin_runs_are_excluded_from_analytics(staff, db_session):
    now = datetime.now(UTC)
    org = await _org(db_session)
    db_session.add_all([
        Audit(
            organization_id=org,
            url="https://admin-test.example",
            origin="https://admin-test.example",
            status=AuditStatus.COMPLETED,
            quota_source=QuotaSource.ADMIN_TEST,
            quota_state=QuotaState.CONSUMED,
            finished_at=now,
        ),
        Audit(
            organization_id=org,
            url="https://customer.example/page",
            origin="https://customer.example",
            status=AuditStatus.COMPLETED,
            quota_source=QuotaSource.SUBSCRIPTION,
            quota_state=QuotaState.CONSUMED,
            finished_at=now,
        ),
        Audit(
            organization_id=org,
            url="https://customer.example/other",
            origin="https://customer.example",
            status=AuditStatus.COMPLETED,
            quota_source=QuotaSource.ONE_OFF,
            quota_state=QuotaState.CONSUMED,
            finished_at=now,
        ),
    ])
    await db_session.commit()

    body = (await staff.get("/v1/admin/analytics")).json()
    usage = body["usage"]
    assert usage["audits_executed"] == 2
    # Два виконання на ОДНОМУ домені — це один унікальний сайт.
    assert usage["unique_domains"] == 1
    assert usage["admin_tests_excluded"]["audits"] == 1


async def test_analytics_counts_paid_purchases_only(staff, db_session):
    now = datetime.now(UTC)
    org = await _org(db_session)
    common = {
        "organization_id": org,
        "provider": "paddle",
        "supplier_entity_key": "test",
        "commerce_model": CommerceModel.MERCHANT_OF_RECORD,
        "currency": "USD",
    }
    db_session.add_all([
        OneOffPurchase(
            **common, external_id=f"ext-{uuid.uuid4().hex[:8]}", quantity=1,
            amount_minor=1500, status=PurchaseStatus.PAID, purchased_at=now,
            offer_snapshot={"offer_type": "single"},
        ),
        OneOffPurchase(
            **common, external_id=f"ext-{uuid.uuid4().hex[:8]}", quantity=10,
            amount_minor=10000, status=PurchaseStatus.PAID, purchased_at=now,
            offer_snapshot={"offer_type": "pack"},
        ),
        # Не оплачена — не продаж.
        OneOffPurchase(
            **common, external_id=f"ext-{uuid.uuid4().hex[:8]}", quantity=1,
            amount_minor=9900, status=PurchaseStatus.PENDING,
            offer_snapshot={"offer_type": "single"},
        ),
        # Повернена — і продаж, і повернення.
        OneOffPurchase(
            **common, external_id=f"ext-{uuid.uuid4().hex[:8]}", quantity=1,
            amount_minor=1500, status=PurchaseStatus.REFUNDED, purchased_at=now,
            refunded_at=now, offer_snapshot={"offer_type": "single"},
        ),
    ])
    await db_session.commit()

    body = (await staff.get("/v1/admin/analytics")).json()
    usd = next(c for c in body["sales"]["currencies"] if c["currency"] == "USD")
    assert usd["purchases"] == 3
    assert usd["gross_minor"] == 1500 + 10000 + 1500
    assert usd["refunds"] == 1
    assert usd["refunded_minor"] == 1500
    assert usd["net_minor"] == usd["gross_minor"] - 1500
    kinds = {row["offer_type"]: row for row in usd["by_type"]}
    # Пакет на 10 одиниць — ОДНА покупка.
    assert kinds["pack"]["purchases"] == 1
    assert kinds["single"]["purchases"] == 2


async def test_analytics_period_filters_by_event_time(staff, db_session):
    org = await _org(db_session)
    old = datetime.now(UTC) - timedelta(days=400)
    db_session.add(
        OneOffPurchase(
            organization_id=org, provider="paddle",
            external_id=f"ext-{uuid.uuid4().hex[:8]}",
            supplier_entity_key="test", commerce_model=CommerceModel.MERCHANT_OF_RECORD,
            quantity=1, currency="EUR", amount_minor=5000,
            status=PurchaseStatus.PAID, purchased_at=old,
            offer_snapshot={"offer_type": "single"},
        )
    )
    await db_session.commit()

    all_time = (await staff.get("/v1/admin/analytics")).json()
    assert any(c["currency"] == "EUR" for c in all_time["sales"]["currencies"])

    since = (datetime.now(UTC) - timedelta(days=30)).date().isoformat()
    recent = (await staff.get(f"/v1/admin/analytics?date_from={since}")).json()
    assert not any(c["currency"] == "EUR" for c in recent["sales"]["currencies"])


async def test_analytics_counts_credits_used_not_sold_twice(staff, db_session):
    org = await _org(db_session)
    now = datetime.now(UTC)
    db_session.add_all([
        AuditCredit(organization_id=org, state=CreditState.AVAILABLE,
                    credit_type="audit", source="purchase"),
        AuditCredit(organization_id=org, state=CreditState.CONSUMED,
                    credit_type="audit", source="purchase", consumed_at=now),
        AuditCredit(organization_id=org, state=CreditState.AVAILABLE,
                    credit_type="presence", source="admin"),
    ])
    await db_session.commit()

    credits = (await staff.get("/v1/admin/analytics")).json()["credits"]
    assert credits["audit"]["sold"] == 2
    assert credits["audit"]["used"] == 1
    assert credits["presence"]["granted"] == 1


async def test_bad_period_is_refused(staff):
    response = await staff.get(
        "/v1/admin/analytics?date_from=2026-09-05&date_to=2026-09-01"
    )
    assert response.status_code == 422


async def test_test_audit_report_needs_a_finished_audit(staff, queue_is_not_the_subject):
    started = (await staff.post(
        "/v1/admin/testing/audits", json={"url": "https://example.com"}
    )).json()
    response = await staff.get(f"/v1/admin/testing/audits/{started['id']}/report")
    assert response.status_code == 409


async def test_customer_audit_is_not_visible_as_a_test_run(
    staff, db_session, queue_is_not_the_subject
):
    org = await _org(db_session)
    audit = Audit(
        organization_id=org,
        url="https://customer.example",
        origin="https://customer.example",
        status=AuditStatus.COMPLETED,
        quota_source=QuotaSource.SUBSCRIPTION,
        quota_state=QuotaState.CONSUMED,
    )
    db_session.add(audit)
    await db_session.commit()
    assert (await staff.get(f"/v1/admin/testing/audits/{audit.id}")).status_code == 404
