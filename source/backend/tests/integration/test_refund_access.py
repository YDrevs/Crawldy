"""Повернення коштів закриває платний вміст на всіх шляхах одразу.

Історія лишається повністю — покупка зі статусом REFUNDED, рядок
розблокування, ланцюг походження. Закривається лише доступ: гостьова
сесія, платне посилання, кабінет після привласнення, поділені
посилання. Безкоштовний короткий вигляд живе за своїми правилами.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import guest as guest_app
from app.application import purchases
from app.audit.enums import AuditStatus
from app.billing.enums import BillingEventKind, PurchaseStatus
from app.core.run_enums import QuotaState
from app.models.audit import Audit
from app.models.guest import AuditUnlock
from app.models.purchase import OneOffPurchase

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def _sellable(single_offer: None) -> None:
    """Гостьова каса продає «разову перевірку» каталогу — заводимо її."""



async def _guest_with_paid_audit(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> tuple[str, str, str]:
    """(токен сесії, audit_id, зовнішній id покупки)."""
    opened = await client.post("/v1/public/sessions")
    token = str(opened.json()["token"])
    headers = {"X-Guest-Token": token}
    started = await client.post(
        "/v1/public/audits", json={"url": "https://example.com/"}, headers=headers
    )
    audit_id = str(started.json()["audit_id"])
    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.status = AuditStatus.COMPLETED
    audit.finished_at = datetime.now(UTC)
    audit.quota_state = QuotaState.CONSUMED
    await db_session.flush()

    external_id = await _pay(client, db_session, token, audit_id)
    return token, audit_id, external_id


async def _pay(
    client: httpx.AsyncClient, db_session: AsyncSession, token: str, audit_id: str
) -> str:
    """Оплатити перевіреною подією. Повертає зовнішній id покупки."""
    session = await guest_app.resolve(db_session, token)
    external_id = f"evt-{uuid.uuid4().hex[:10]}"
    body = json.dumps(
        {
            "external_event_id": external_id,
            "kind": BillingEventKind.ONE_OFF_PURCHASED.value,
            "occurred_at": datetime.now(UTC).isoformat(),
            "organization_id": str(session.organization_id),
            "quantity": 1,
            "currency": "USD",
            "amount_minor": 900,
            "payload": {"audit_id": audit_id},
        }
    ).encode()
    response = await client.post(
        "/v1/webhooks/fake",
        content=body,
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )
    assert response.status_code == 200, response.text
    return external_id


async def _refund(db_session: AsyncSession, external_id: str) -> None:
    result = await purchases.refund(db_session, provider="fake", external_id=external_id)
    assert result is not None
    await db_session.flush()


# ── гостьовий шлях ─────────────────────────────────────────────────────────


async def test_guest_full_access_closes_on_refund_while_session_lives(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Сесія ще жива — а платний вміст уже закритий.

    Рівно та прогалина, що лишалась: is_unlocked дивився на історію
    розблокування, а не на чинність оплати.
    """
    token, audit_id, external_id = await _guest_with_paid_audit(client, db_session)
    headers = {"X-Guest-Token": token}

    before = await client.get(f"/v1/public/audits/{audit_id}/full", headers=headers)
    assert before.status_code == 200

    await _refund(db_session, external_id)

    after = await client.get(f"/v1/public/audits/{audit_id}/full", headers=headers)
    assert after.status_code == 402

    # Короткий вигляд живе, і чесно каже, що не відкрито.
    short = await client.get(f"/v1/public/audits/{audit_id}", headers=headers)
    assert short.status_code == 200
    assert short.json()["unlocked"] is False


async def test_refund_blocks_new_link_issuing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Після повернення нове платне посилання не видається."""
    token, audit_id, external_id = await _guest_with_paid_audit(client, db_session)
    await _refund(db_session, external_id)

    issued = await client.post(
        f"/v1/public/audits/{audit_id}/report-link", headers={"X-Guest-Token": token}
    )
    assert issued.status_code == 402


async def test_refund_reopens_checkout(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Повернені гроші — можна купити знову: каса не каже «вже відкрито»."""
    token, audit_id, external_id = await _guest_with_paid_audit(client, db_session)
    await _refund(db_session, external_id)

    checkout = await client.post(
        f"/v1/public/audits/{audit_id}/checkout", headers={"X-Guest-Token": token}
    )
    assert checkout.status_code == 200


# ── кабінет після привласнення ─────────────────────────────────────────────


async def test_claimed_account_cannot_bypass_refund(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Акаунт — ще один шлях до аудиту, але не обхід повернення."""
    token, audit_id, external_id = await _guest_with_paid_audit(client, db_session)
    email = f"claim-{uuid.uuid4().hex[:8]}@example.com"
    claimed = await client.post(
        "/v1/public/claim",
        json={"email": email, "password": "correct horse 9"},
        headers={"X-Guest-Token": token},
    )
    assert claimed.status_code == 201

    login = await client.post(
        "/v1/auth/login", json={"email": email, "password": "correct horse 9"}
    )
    assert login.status_code == 200, login.text

    before = await client.get(f"/v1/audits/{audit_id}/result")
    assert before.status_code == 200

    await _refund(db_session, external_id)

    for path in (
        f"/v1/audits/{audit_id}/result",
        f"/v1/audits/{audit_id}",
        f"/v1/audits/{audit_id}/issues",
        f"/v1/audits/{audit_id}/report",
    ):
        response = await client.get(path)
        assert response.status_code == 402, path

    share = await client.post(f"/v1/audits/{audit_id}/links", json={})
    assert share.status_code == 402


async def test_share_link_created_before_refund_goes_dark(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Поділене з кабінету посилання гасне разом із поверненням."""
    token, audit_id, external_id = await _guest_with_paid_audit(client, db_session)
    email = f"share-{uuid.uuid4().hex[:8]}@example.com"
    await client.post(
        "/v1/public/claim",
        json={"email": email, "password": "correct horse 9"},
        headers={"X-Guest-Token": token},
    )
    await client.post("/v1/auth/login", json={"email": email, "password": "correct horse 9"})

    created = await client.post(f"/v1/audits/{audit_id}/links", json={})
    assert created.status_code == 201, created.text
    share_token = str(created.json()["token"])
    assert (await client.get(f"/r/{share_token}?format=json")).status_code == 200

    await _refund(db_session, external_id)
    assert (await client.get(f"/r/{share_token}?format=json")).status_code == 404


# ── історія ────────────────────────────────────────────────────────────────


async def test_history_survives_refund_completely(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """«Куплено, відкрито, повернено» — усе це читається з бази й після."""
    _, audit_id, external_id = await _guest_with_paid_audit(client, db_session)
    await _refund(db_session, external_id)

    purchase = await db_session.scalar(
        select(OneOffPurchase).where(OneOffPurchase.audit_id == uuid.UUID(audit_id))
    )
    assert purchase is not None
    assert purchase.status is PurchaseStatus.REFUNDED
    assert purchase.refunded_at is not None

    unlock = await db_session.scalar(
        select(AuditUnlock).where(AuditUnlock.audit_id == uuid.UUID(audit_id))
    )
    assert unlock is not None
    assert unlock.purchase_id == purchase.id

    assert await guest_app.has_unlock_history(db_session, uuid.UUID(audit_id))
    assert not await guest_app.is_unlocked(db_session, uuid.UUID(audit_id))

    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None, "аудит не стирається, щоб сховати платне"


async def test_repeated_refund_is_idempotent(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    _, audit_id, external_id = await _guest_with_paid_audit(client, db_session)
    await _refund(db_session, external_id)
    await _refund(db_session, external_id)

    purchase = await db_session.scalar(
        select(OneOffPurchase).where(OneOffPurchase.audit_id == uuid.UUID(audit_id))
    )
    assert purchase is not None
    assert purchase.status is PurchaseStatus.REFUNDED


# ── кілька покупок одного аудиту ───────────────────────────────────────────


async def test_refunding_one_purchase_keeps_access_from_another(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Дві оплати, повернена одна — доступ живе, бо друга чинна.

    Схема цього не забороняє: унікальний лише unlock (один на аудит),
    а покупок із audit_id може бути кілька. Правило чинності дивиться
    на «чи існує оплачена покупка», а не на першу-ліпшу.
    """
    token, audit_id, first_external = await _guest_with_paid_audit(client, db_session)
    second_external = await _pay(client, db_session, token, audit_id)
    headers = {"X-Guest-Token": token}

    await _refund(db_session, first_external)

    still_open = await client.get(f"/v1/public/audits/{audit_id}/full", headers=headers)
    assert still_open.status_code == 200

    issued = await client.post(
        f"/v1/public/audits/{audit_id}/report-link", headers=headers
    )
    assert issued.status_code == 201
    link_token = str(issued.json()["token"])
    assert (await client.get(f"/r/{link_token}?format=json")).status_code == 200

    # Повернули й другу — тепер закрито всюди.
    await _refund(db_session, second_external)
    closed = await client.get(f"/v1/public/audits/{audit_id}/full", headers=headers)
    assert closed.status_code == 402
    assert (await client.get(f"/r/{link_token}?format=json")).status_code == 404
