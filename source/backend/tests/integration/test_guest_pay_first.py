"""Разова покупка, що починається з оплати. Без акаунта.

Друга дорога до того самого продукту: на сторінці цін людина натискає
«Отримати звіт», платить, і лише потім називає сайт. Реєстрації тут
немає ніде — це рішення власника, і саме воно відрізняє цю воронку від
кабінету.

Перевіряється те, чого не видно з коду поодинці: що касу можна відкрити
без жодного аудиту, що оплата видає ДВІ одиниці (перевірку сайту й
перевірку присутності), що покупка звʼязується з аудитом лише тоді, коли
людина назвала адресу, і що за ті самі гроші другого аудиту не буде.
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
from app.audit.enums import AuditStatus
from app.billing.enums import BillingEventKind, PurchaseStatus
from app.models.audit import Audit
from app.models.guest import AuditUnlock
from app.models.purchase import AuditCredit, OneOffPurchase

pytestmark = pytest.mark.asyncio

_TRANSACTION = "txn_pay_first"


@pytest_asyncio.fixture(autouse=True)
async def _sellable(single_offer: None) -> None:
    """Анонімно продається «разова перевірка» каталогу — заводимо її."""


async def _open(client: httpx.AsyncClient) -> str:
    response = await client.post("/v1/public/sessions")
    assert response.status_code == 201, response.text
    return str(response.json()["token"])


def _auth(token: str) -> dict[str, str]:
    return {"X-Guest-Token": token}


async def _order(client: httpx.AsyncClient, token: str) -> str:
    response = await client.post("/v1/public/orders", headers=_auth(token))
    assert response.status_code == 200, response.text
    return str(response.json()["purchase_id"])


def _paid_event(*, purchase_ref: str, event_id: str = "evt-pay-first") -> bytes:
    return json.dumps(
        {
            "external_event_id": event_id,
            "kind": BillingEventKind.ONE_OFF_PURCHASED.value,
            "occurred_at": datetime.now(UTC).isoformat(),
            "quantity": 1,
            "currency": "USD",
            "amount_minor": 999,
            "payload": {
                "purchase_ref": purchase_ref,
                "provider_transaction_id": _TRANSACTION,
            },
        }
    ).encode("utf-8")


async def _pay(client: httpx.AsyncClient, purchase_id: str, event_id: str = "evt-1") -> None:
    response = await client.post(
        "/v1/webhooks/fake",
        content=_paid_event(purchase_ref=purchase_id, event_id=event_id),
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )
    assert response.status_code == 200, response.text


async def _credits(db_session: AsyncSession, purchase_id: str) -> list[str]:
    rows = await db_session.scalars(
        select(AuditCredit).where(AuditCredit.purchase_id == uuid.UUID(purchase_id))
    )
    return sorted(row.credit_type for row in rows)


# ── каса до аудиту ─────────────────────────────────────────────────────


async def test_checkout_opens_without_any_audit(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Головне цієї воронки: платити можна, ще нічого не перевіривши."""
    token = await _open(client)

    purchase_id = await _order(client, token)

    purchase = await db_session.get(OneOffPurchase, uuid.UUID(purchase_id))
    assert purchase is not None
    assert purchase.status is PurchaseStatus.PENDING
    assert purchase.audit_id is None, "аудиту ще немає — і поля бути не має"
    # Умови зняті зліпком: людина платить за те, що бачила на сторінці цін.
    assert purchase.offer_code
    assert (purchase.offer_snapshot or {}).get("presence_credits") == 1


async def test_no_account_is_created_anywhere_on_this_path(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Разова покупка анонімна: ані користувача, ані членства."""
    from app.models.identity import Membership, User

    before = len(list(await db_session.scalars(select(User))))
    token = await _open(client)
    purchase_id = await _order(client, token)
    await _pay(client, purchase_id)

    assert len(list(await db_session.scalars(select(User)))) == before
    session = await guest_app.resolve(db_session, token)
    members = await db_session.scalars(
        select(Membership).where(Membership.organization_id == session.organization_id)
    )
    assert list(members) == []


async def test_payment_grants_both_halves_of_the_product(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Куплено дві речі — видано дві.

    Поки каса воронки не несла умов пропозиції, оплата видавала НУЛЬ
    перевірок присутності, і друга половина продукту не працювала.
    """
    token = await _open(client)
    purchase_id = await _order(client, token)

    await _pay(client, purchase_id)

    db_session.expire_all()
    assert await _credits(db_session, purchase_id) == ["audit", "presence"]
    purchase = await db_session.get(OneOffPurchase, uuid.UUID(purchase_id))
    assert purchase is not None and purchase.status is PurchaseStatus.PAID
    # Аудиту ще немає, тож і розблоковувати нема чого.
    assert purchase.audit_id is None


# ── сайт після оплати ──────────────────────────────────────────────────


async def test_audit_refused_until_the_event_arrives(
    client: httpx.AsyncClient,
) -> None:
    """Повернення браузера з каси нічого не доводить."""
    token = await _open(client)
    purchase_id = await _order(client, token)

    response = await client.post(
        f"/v1/public/orders/{purchase_id}/audit",
        json={"url": "https://example.com/"},
        headers=_auth(token),
    )

    assert response.status_code == 402
    assert response.json()["detail"]["reason"] == "not.paid"


async def test_paid_order_starts_the_audit_and_opens_the_report(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Оплата + названий сайт = аудит, звʼязана покупка й відкритий звіт."""
    token = await _open(client)
    purchase_id = await _order(client, token)
    await _pay(client, purchase_id)

    started = await client.post(
        f"/v1/public/orders/{purchase_id}/audit",
        json={"url": "https://example.com/"},
        headers=_auth(token),
    )
    assert started.status_code == 202, started.text
    audit_id = str(started.json()["audit_id"])
    assert started.json()["unlocked"] is True

    db_session.expire_all()
    purchase = await db_session.get(OneOffPurchase, uuid.UUID(purchase_id))
    assert purchase is not None and str(purchase.audit_id) == audit_id
    unlocks = await db_session.scalars(
        select(AuditUnlock).where(AuditUnlock.audit_id == uuid.UUID(audit_id))
    )
    assert len(list(unlocks)) == 1
    # Аудит платний, а не превʼю: куплена одиниця списана саме на нього.
    spent = await db_session.scalars(
        select(AuditCredit).where(AuditCredit.audit_id == uuid.UUID(audit_id))
    )
    assert len(list(spent)) == 1

    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.status = AuditStatus.COMPLETED
    audit.finished_at = datetime.now(UTC)
    await db_session.flush()

    full = await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    assert full.status_code == 200
    assert "modules" in full.json()


async def test_the_same_purchase_never_buys_two_audits(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Другий виклик віддає той самий аудит, а не запускає новий."""
    token = await _open(client)
    purchase_id = await _order(client, token)
    await _pay(client, purchase_id)

    first = await client.post(
        f"/v1/public/orders/{purchase_id}/audit",
        json={"url": "https://example.com/"},
        headers=_auth(token),
    )
    second = await client.post(
        f"/v1/public/orders/{purchase_id}/audit",
        json={"url": "https://other.example/"},
        headers=_auth(token),
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["audit_id"] == first.json()["audit_id"]
    audits = await db_session.scalars(select(Audit))
    assert len(list(audits)) == 1


async def test_a_failed_audit_does_not_burn_the_purchase(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Невдача — наша, і платити за неї вдруге людина не мусить."""
    token = await _open(client)
    purchase_id = await _order(client, token)
    await _pay(client, purchase_id)
    first = await client.post(
        f"/v1/public/orders/{purchase_id}/audit",
        json={"url": "https://example.com/"},
        headers=_auth(token),
    )
    audit = await db_session.get(Audit, uuid.UUID(str(first.json()["audit_id"])))
    assert audit is not None
    audit.status = AuditStatus.FAILED
    await db_session.flush()
    # Квота повертає кредит на невдалому аудиті — тут імітуємо це прямо,
    # бо повернення робить воркер, а не маршрут.
    from app.billing import credits as billing_credits

    session = await guest_app.resolve(db_session, token)
    await billing_credits.release(db_session, audit_id=audit.id)
    await db_session.flush()
    assert await billing_credits.balance(
        db_session, organization_id=session.organization_id
    ) == 1

    again = await client.post(
        f"/v1/public/orders/{purchase_id}/audit",
        json={"url": "https://second.example/"},
        headers=_auth(token),
    )

    assert again.status_code == 202
    assert again.json()["audit_id"] != first.json()["audit_id"]


async def test_a_foreign_purchase_is_not_found(
    client: httpx.AsyncClient,
) -> None:
    """Чужий ідентифікатор — 404, як і все інше в цьому роутері."""
    mine = await _open(client)
    theirs = await _open(client)
    purchase_id = await _order(client, theirs)

    response = await client.get(f"/v1/public/orders/{purchase_id}", headers=_auth(mine))

    assert response.status_code == 404


async def test_order_state_separates_paid_from_started(
    client: httpx.AsyncClient,
) -> None:
    """Два стани, які інакше злилися б в одне «оплачено»."""
    token = await _open(client)
    purchase_id = await _order(client, token)

    waiting = await client.get(f"/v1/public/orders/{purchase_id}", headers=_auth(token))
    assert waiting.json()["state"] == "processing"
    assert waiting.json()["started_audit_id"] is None

    await _pay(client, purchase_id)
    paid = await client.get(f"/v1/public/orders/{purchase_id}", headers=_auth(token))
    assert paid.json()["state"] == "paid"
    assert paid.json()["started_audit_id"] is None
    assert paid.json()["presence_available"] == 1

    started = await client.post(
        f"/v1/public/orders/{purchase_id}/audit",
        json={"url": "https://example.com/"},
        headers=_auth(token),
    )
    after = await client.get(f"/v1/public/orders/{purchase_id}", headers=_auth(token))
    assert after.json()["started_audit_id"] == started.json()["audit_id"]


async def test_a_second_attempt_reuses_the_same_till(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Закрив вікно, натиснув ще раз — та сама каса, а не друга.

    Інакше кожне натискання лишало б у провайдера ще одну незавершену
    транзакцію, а операторові — ще один рядок для гасіння.
    """
    token = await _open(client)

    first = await _order(client, token)
    second = await _order(client, token)

    assert first == second
    rows = await db_session.scalars(
        select(OneOffPurchase).where(OneOffPurchase.status == PurchaseStatus.PENDING)
    )
    assert len(list(rows)) == 1


async def test_paying_after_a_retry_still_grants_once(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Повтор не подвоює видачу: покупка одна, і кредитів двоє, не четверо."""
    token = await _open(client)
    purchase_id = await _order(client, token)
    await _order(client, token)

    await _pay(client, purchase_id)

    db_session.expire_all()
    assert await _credits(db_session, purchase_id) == ["audit", "presence"]
