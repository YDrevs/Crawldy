"""Контракт акаунта в дії: тариф, підписка, права, використання."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.billing import service as billing_service
from app.models.billing import Plan, Subscription
from tests.integration.conftest import register


@pytest.mark.asyncio
async def test_a_fresh_organization_lives_on_the_free_plan(client):
    await register(client, "acc@example.com")

    account = (await client.get("/v1/account")).json()

    assert account["plan"]["code"] == "free"
    assert account["subscription"] is None, "безкоштовний тариф — без підписки"
    assert account["usage"]["audits_used"] == 0
    assert account["entitlements"]["max_pages_per_audit"] > 0
    assert account["organization"]["default_locale"] == "en"
    assert account["role"] == "owner"


@pytest.mark.asyncio
async def test_a_subscription_shows_up_with_its_period(client, db_session):
    body = (await register(client, "paid-acc@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    plan = (
        (await db_session.execute(select(Plan).where(Plan.code == "pro"))).scalars().one()
    )
    now = datetime.now(UTC)
    db_session.add(
        Subscription(
            organization_id=org, plan_id=plan.id, status="ACTIVE", provider="fake",
            current_period_start=now - timedelta(days=1),
            current_period_end=now + timedelta(days=29),
        )
    )
    await db_session.flush()

    account = (await client.get("/v1/account")).json()

    assert account["plan"]["code"] == "pro"
    assert account["subscription"]["status"] == "active"
    assert account["subscription"]["current_period_end"] is not None
    assert account["usage"]["audits_limit"] == plan.entitlements["audits_per_period"]


@pytest.mark.asyncio
async def test_an_override_is_visible_in_resolved_entitlements(client, db_session):
    """Права в акаунті — розвʼязані, а не сирий JSONB тарифу."""
    body = (await register(client, "override-acc@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    await billing_service.grant_override(
        db_session, organization_id=org, key="max_pages_per_audit",
        value=555, reason="індивідуальні умови",
    )

    account = (await client.get("/v1/account")).json()

    assert account["entitlements"]["max_pages_per_audit"] == 555


@pytest.mark.asyncio
async def test_preferences_live_on_the_user_not_on_the_billing_resource(client):
    """Мова — налаштування людини, тариф — ресурс організації.

    Змішати їх означало б, що зміна мови концептуально належить до оплати.
    """
    await register(client, "prefs@example.com")

    updated = await client.patch("/v1/auth/me", json={"locale": "uk"})
    assert updated.status_code == 200
    assert updated.json()["user"]["locale"] == "uk"

    # Ресурс білінгу від цього не змінився.
    account = (await client.get("/v1/account")).json()
    assert "locale" not in account
    assert account["plan"]["code"] == "free"


@pytest.mark.asyncio
async def test_a_region_is_normalised_and_nonsense_is_refused(client):
    await register(client, "prefs2@example.com")

    accepted = await client.patch("/v1/auth/me", json={"locale": "pt-BR"})
    assert accepted.json()["user"]["locale"] == "pt", "регіон відкинуто, мова лишилась"

    refused = await client.patch("/v1/auth/me", json={"locale": "klingon"})
    assert refused.status_code == 422


@pytest.mark.asyncio
async def test_clearing_the_locale_means_follow_the_organization(client):
    """Порожньо — це «не обирав», а не «обрав англійську»."""
    await register(client, "prefs3@example.com")
    await client.patch("/v1/auth/me", json={"locale": "uk"})

    cleared = await client.patch("/v1/auth/me", json={"locale": ""})
    assert cleared.json()["user"]["locale"] == ""


@pytest.mark.asyncio
async def test_an_api_key_cannot_touch_the_organizations_money(client):
    """Ключ організації діє «не білінгом»: каса, підписка й портал провайдера
    (скасування, картка) — лише для власника-людини."""
    await register(client, "owner@example.com")
    token = (await client.post("/v1/auth/api-keys", json={})).json()["token"]
    await client.post("/v1/auth/logout")
    client.cookies.clear()
    headers = {"X-API-Key": token}

    assert (await client.post("/v1/account/portal-session", headers=headers)).status_code == 403
    assert (
        await client.post("/v1/offers/checkout", json={"offer_code": "x"}, headers=headers)
    ).status_code == 403
    assert (await client.post("/v1/plans/pro/checkout", headers=headers)).status_code == 403
