"""Текст внутрішнього винятку не йде клієнту.

`f"черга недоступна: {exc}"` зберігався в `audit.error` і повертався в
API: виняток Redis несе хост, порт, а з DSN — і пароль. Портал
провайдера віддавав клієнту текст відмови Paddle про права НАШОГО
ключа. Причину пишемо в лог, клієнт отримує загальне пояснення.
"""

from __future__ import annotations

import pytest

from app.application import billing as billing_app
from tests.integration.conftest import grant_audit_credits, register
from tests.integration.test_audit_ownership import _own_organization

SECRET = "redis://:s3cret@10.1.2.3:6379"


@pytest.mark.asyncio
async def test_a_queue_failure_does_not_expose_the_exception(client, db_session, monkeypatch):
    await register(client, "q@example.com")
    await grant_audit_credits(db_session, organization_id=await _own_organization(client))

    async def broken(*_args: object, **_kwargs: object) -> None:
        raise ConnectionError(f"Error connecting to {SECRET}")

    monkeypatch.setattr("app.api.routes.audits.enqueue_audit", broken)
    response = await client.post(
        "/v1/audits", json={"url": "https://example.com", "options": {"max_pages": 5}}
    )
    assert response.status_code == 503

    listed = (await client.get("/v1/audits")).json()
    dump = str(listed)
    assert "s3cret" not in dump
    assert "10.1.2.3" not in dump


@pytest.mark.asyncio
async def test_a_portal_failure_does_not_expose_the_provider_reply(
    client, db_session, monkeypatch
):
    await register(client, "p@example.com")

    async def refused(*_args: object, **_kwargs: object) -> None:
        raise billing_app.PortalUnavailable("forbidden: not authorized customer-portal-session")

    monkeypatch.setattr(billing_app, "portal_url", refused)
    response = await client.post("/v1/account/portal-session")

    assert response.status_code == 502
    assert "customer-portal-session" not in response.text
