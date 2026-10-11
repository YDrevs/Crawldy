"""Разова покупка від каси до права — матриця A–S.

Тут перевіряється не адаптер, а **домен**: усе нижче проходить через
контракт провайдера й лишиться правдою після заміни Paddle на будь-кого
іншого. Провайдерські подробиці — форма підпису, назви подій, адреси —
живуть у `tests/test_paddle_adapter.py` і сюди не потрапляють жодного
разу.

Головне твердження всього файлу одне: **право дає перевірена подія, і
лише вона**. Ні повернення браузера, ні ідентифікатор покупки, ні
довільні дані, які принесе чужий бік, правом не є.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import guest as guest_app
from app.application import purchases as purchases_app
from app.audit.enums import AuditStatus
from app.billing.enums import BillingEventKind, PurchaseStatus
from app.billing.providers import CheckoutRequest
from app.billing.registry import fake as fake_provider
from app.models.audit import Audit
from app.models.guest import AuditUnlock
from app.models.purchase import AuditCredit, OneOffPurchase

pytestmark = pytest.mark.asyncio

_FAKE_TRANSACTION = "fake-txn-1"


@pytest_asyncio.fixture(autouse=True)
async def _sellable(single_offer: None) -> None:
    """Каса продає «разову перевірку» каталогу — вона має існувати."""


# ── риштування ─────────────────────────────────────────────────────────────


async def _open(client: httpx.AsyncClient) -> str:
    response = await client.post("/v1/public/sessions")
    assert response.status_code == 201, response.text
    return str(response.json()["token"])


def _auth(token: str) -> dict[str, str]:
    return {"X-Guest-Token": token}


async def _start(client: httpx.AsyncClient, token: str) -> str:
    response = await client.post(
        "/v1/public/audits", json={"url": "https://example.com/"}, headers=_auth(token)
    )
    assert response.status_code == 202, response.text
    return str(response.json()["audit_id"])


async def _finish(db: AsyncSession, audit_id: str) -> Audit:
    audit = await db.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.status = AuditStatus.COMPLETED
    audit.finished_at = datetime.now(UTC)
    await db.flush()
    return audit


async def _ready(client: httpx.AsyncClient, db: AsyncSession) -> tuple[str, str]:
    """Гість із завершеним аудитом — вихідна точка кожного тесту нижче."""
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db, audit_id)
    return token, audit_id


async def _checkout(
    client: httpx.AsyncClient, token: str, audit_id: str
) -> dict[str, object]:
    response = await client.post(
        f"/v1/public/audits/{audit_id}/checkout", headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


def _paid_event(
    *,
    purchase_ref: str,
    event_id: str = "evt-paid-1",
    occurred_at: datetime | None = None,
    transaction: str = _FAKE_TRANSACTION,
    amount_minor: int = 900,
    extra_payload: dict[str, object] | None = None,
) -> bytes:
    """Оплата, що посилається на НАШУ покупку — так, як це робить Paddle.

    Аудиту в тілі немає навмисно: його називає наш власний запис, а не
    те, що принесе чужий бік.
    """
    payload: dict[str, object] = {
        "purchase_ref": purchase_ref,
        "provider_transaction_id": transaction,
    }
    payload.update(extra_payload or {})
    return json.dumps(
        {
            "external_event_id": event_id,
            "kind": BillingEventKind.ONE_OFF_PURCHASED.value,
            "occurred_at": (occurred_at or datetime.now(UTC)).isoformat(),
            "quantity": 1,
            "currency": "USD",
            "amount_minor": amount_minor,
            "payload": payload,
        }
    ).encode("utf-8")


def _failed_event(*, purchase_ref: str, event_id: str = "evt-failed-1") -> bytes:
    return json.dumps(
        {
            "external_event_id": event_id,
            "kind": BillingEventKind.PAYMENT_FAILED.value,
            "occurred_at": datetime.now(UTC).isoformat(),
            "payload": {"purchase_ref": purchase_ref},
        }
    ).encode("utf-8")


def _refund_event(*, transaction: str, event_id: str = "evt-refund-1") -> bytes:
    return json.dumps(
        {
            "external_event_id": event_id,
            "kind": BillingEventKind.ONE_OFF_REFUNDED.value,
            "occurred_at": datetime.now(UTC).isoformat(),
            "payload": {"provider_transaction_id": transaction},
        }
    ).encode("utf-8")


async def _deliver(client: httpx.AsyncClient, body: bytes) -> httpx.Response:
    return await client.post(
        "/v1/webhooks/fake",
        content=body,
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )


async def _purchases(db: AsyncSession, audit_id: str) -> list[OneOffPurchase]:
    rows = await db.scalars(
        select(OneOffPurchase)
        .where(OneOffPurchase.audit_id == uuid.UUID(audit_id))
        .order_by(OneOffPurchase.created_at)
    )
    return list(rows)


# ── A. покупка існує ДО каси ───────────────────────────────────────────────


async def test_pending_purchase_exists_before_the_till_opens(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """A: каса відкривається після запису, а не замість нього.

    Порядок і є кореляцією: те, що ми віддали провайдеру, мусить уже
    існувати в нас, інакше подія назве рядок, якого немає.
    """
    token, audit_id = await _ready(client, db_session)
    body = await _checkout(client, token, audit_id)

    stored = await _purchases(db_session, audit_id)
    assert len(stored) == 1
    purchase = stored[0]
    assert purchase.status is PurchaseStatus.PENDING
    assert purchase.purchased_at is None, "PENDING не має часу оплати"
    assert purchase.external_id == str(purchase.id), "наш ідентифікатор, не чужий"
    assert body["purchase_intent"] == str(purchase.id)

    credits = await db_session.scalars(
        select(AuditCredit).where(AuditCredit.purchase_id == purchase.id)
    )
    assert list(credits) == [], "кредитів немає: за них ще не заплачено"


# ── B. касу відкриває протокол провайдера ──────────────────────────────────


async def test_checkout_goes_through_the_provider_protocol(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """B: адресу дає провайдер, а не ми конкатенацією рядків."""
    fake = fake_provider()
    before = len(fake.checkouts)

    token, audit_id = await _ready(client, db_session)
    body = await _checkout(client, token, audit_id)

    assert len(fake.checkouts) == before + 1
    request = fake.checkouts[-1]
    assert isinstance(request, CheckoutRequest)

    purchase = (await _purchases(db_session, audit_id))[0]
    assert request.purchase_id == purchase.id
    assert request.price_ref == "fake_single", "ціна — з «разової перевірки» каталогу"
    assert str(purchase.id) in str(body["checkout_url"])
    assert purchase.provider_ref, "посилання провайдера лягає поруч із покупкою"


async def test_customer_is_not_created_for_a_guest_purchase(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Гість не має пошти, і вигадувати її заради форми виклику не можна."""
    fake = fake_provider()
    before = len(fake._customers)

    token, audit_id = await _ready(client, db_session)
    await _checkout(client, token, audit_id)

    assert len(fake._customers) == before, "create_customer не викликається"
    assert fake.checkouts[-1].email is None
    assert fake.checkouts[-1].customer is None


async def test_repeated_checkout_reuses_the_same_purchase(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Подвійний клік не плодить ані записів, ані намірів."""
    token, audit_id = await _ready(client, db_session)
    first = await _checkout(client, token, audit_id)
    second = await _checkout(client, token, audit_id)

    assert first["purchase_intent"] == second["purchase_intent"]
    assert len(await _purchases(db_session, audit_id)) == 1


# ── C. повернення браузера нічого не відкриває ─────────────────────────────


async def test_the_return_page_reads_processing_until_the_event_arrives(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """C: сторінка повернення каже правду, а не вгадує за адресою."""
    token, audit_id = await _ready(client, db_session)

    before = await client.get(
        f"/v1/public/audits/{audit_id}/payment", headers=_auth(token)
    )
    assert before.status_code == 200
    assert before.json()["state"] == purchases_app.PAYMENT_NONE
    assert before.json()["unlocked"] is False

    await _checkout(client, token, audit_id)

    waiting = await client.get(
        f"/v1/public/audits/{audit_id}/payment", headers=_auth(token)
    )
    assert waiting.json()["state"] == purchases_app.PAYMENT_PROCESSING
    assert waiting.json()["unlocked"] is False
    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 402


# ── D, E, F. перевірена подія → PAID → доступ до ТОГО САМОГО аудиту ────────


async def test_verified_event_pays_the_pending_purchase(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """D+E+F: гроші відкривають уже виконану роботу, а не замовляють нову."""
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])
    total_before = len(list(await db_session.scalars(select(Audit.id))))

    assert (await _deliver(client, _paid_event(purchase_ref=intent))).status_code == 200

    db_session.expire_all()
    purchase = (await _purchases(db_session, audit_id))[0]
    assert purchase.status is PurchaseStatus.PAID
    assert purchase.purchased_at is not None
    assert purchase.amount_minor == 900
    assert purchase.currency == "USD"
    assert purchase.provider_ref == _FAKE_TRANSACTION

    full = await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    assert full.status_code == 200

    # F: другого краулу немає — той самий рядок, та сама кількість аудитів.
    assert len(list(await db_session.scalars(select(Audit.id)))) == total_before

    state = await client.get(
        f"/v1/public/audits/{audit_id}/payment", headers=_auth(token)
    )
    assert state.json() == {
        "audit_id": audit_id,
        "state": purchases_app.PAYMENT_PAID,
        "unlocked": True,
        # Оплачена покупка — списання відоме з наших записів, без провайдера.
        "charged": True,
    }


# ── G. повторна й затримана доставка ───────────────────────────────────────


async def test_paying_records_the_provider_customer(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Покупця провайдера видно вперше в події оплати — і саме там його
    треба запамʼятати.

    Разова покупка резолвиться через НАШ запис, тож відображення покупця
    не зʼявлялося ніколи, і людина з оплаченим пакетом не могла відкрити
    «Платежі й квитанції»: портал провайдера адресується покупцем.
    """
    from app.models.billing import BillingCustomer

    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])
    body = json.loads(_paid_event(purchase_ref=intent))
    body["customer_ref"] = "ctm_from_checkout"
    await _deliver(client, json.dumps(body).encode("utf-8"))

    db_session.expire_all()
    purchase = (await _purchases(db_session, audit_id))[0]
    known = (await db_session.execute(
        select(BillingCustomer).where(
            BillingCustomer.organization_id == purchase.organization_id
        )
    )).scalars().all()
    assert [c.provider_customer_id for c in known] == ["ctm_from_checkout"]


async def test_the_same_event_delivered_twice_changes_nothing_twice(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """G: один ефект на одну подію, скільки б разів її не привезли."""
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])
    body = _paid_event(purchase_ref=intent)

    first = await _deliver(client, body)
    second = await _deliver(client, body)
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["outcome"] == "duplicate"

    db_session.expire_all()
    assert len(await _purchases(db_session, audit_id)) == 1
    unlocks = await db_session.scalars(
        select(AuditUnlock).where(AuditUnlock.audit_id == uuid.UUID(audit_id))
    )
    assert len(list(unlocks)) == 1
    purchase = (await _purchases(db_session, audit_id))[0]
    credits = list(await db_session.scalars(
        select(AuditCredit).where(AuditCredit.purchase_id == purchase.id)
    ))
    # Разова покупка — це ДВІ одиниці: перевірка сайту й перевірка
    # присутності. Поки каса воронки не несла умов пропозиції, друга не
    # видавалась узагалі, і панель присутності на оплаченому екрані не
    # могла запуститись ніколи. Тут перевіряється й склад видачі, й те,
    # що повторна доставка події його не подвоює.
    by_type = sorted(c.credit_type for c in credits)
    assert by_type == ["audit", "presence"], "видача видається рівно один раз"


async def test_an_older_event_does_not_overwrite_a_newer_state(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Не по порядку: PAID не гасне від старішої доставки."""
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])
    now = datetime.now(UTC)

    await _deliver(client, _paid_event(purchase_ref=intent, occurred_at=now))
    late = await _deliver(
        client,
        _paid_event(
            purchase_ref=intent,
            event_id="evt-paid-late",
            occurred_at=now - timedelta(hours=1),
        ),
    )
    assert late.status_code == 200

    db_session.expire_all()
    purchases = await _purchases(db_session, audit_id)
    assert len(purchases) == 1, "стара доставка не створює другої покупки"
    assert purchases[0].status is PurchaseStatus.PAID


# ── H. підпис ──────────────────────────────────────────────────────────────


async def test_an_unsigned_event_is_not_an_event(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """H: без підпису подія не існує для домену."""
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])

    unsigned = await client.post(
        "/v1/webhooks/fake",
        content=_paid_event(purchase_ref=intent),
        headers={"content-type": "application/json"},
    )
    assert unsigned.status_code == 400

    db_session.expire_all()
    assert (await _purchases(db_session, audit_id))[0].status is PurchaseStatus.PENDING
    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 402


# ── I. подія про покупку, якої немає ───────────────────────────────────────


async def test_an_event_naming_an_unknown_purchase_grants_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """I: чужі дані не призначають нам записів.

    Створити покупку «за подією» тут означало б дозволити будь-кому з
    дійсним підписом вигадати нам продаж.
    """
    token, audit_id = await _ready(client, db_session)
    await _checkout(client, token, audit_id)

    ghost = await _deliver(client, _paid_event(purchase_ref=str(uuid.uuid4())))
    assert ghost.status_code == 500, "подія лишається в журналі як невдала"

    db_session.expire_all()
    assert (await _purchases(db_session, audit_id))[0].status is PurchaseStatus.PENDING
    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 402


# ── J. підроблені довільні дані ────────────────────────────────────────────


async def test_manipulated_custom_data_cannot_choose_the_audit(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """J: аудит береться з нашого запису, а не з даних події.

    Найдорожча помилка, якої тут можна припуститися: повірити полю
    `audit_id`, що прийшло ззовні. Тоді одна оплата відкривала б
    будь-який інший аудит, чий номер підставили в подію.
    """
    victim_token, victim_audit = await _ready(client, db_session)
    buyer_token, buyer_audit = await _ready(client, db_session)
    intent = str((await _checkout(client, buyer_token, buyer_audit))["purchase_intent"])

    paid = await _deliver(
        client,
        _paid_event(purchase_ref=intent, extra_payload={"audit_id": victim_audit}),
    )
    assert paid.status_code == 200

    assert (
        await client.get(
            f"/v1/public/audits/{buyer_audit}/full", headers=_auth(buyer_token)
        )
    ).status_code == 200
    assert (
        await client.get(
            f"/v1/public/audits/{victim_audit}/full", headers=_auth(victim_token)
        )
    ).status_code == 402

    db_session.expire_all()
    assert await _purchases(db_session, victim_audit) == []


async def test_checkout_refuses_an_audit_the_guest_does_not_own(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Номер аудиту не є повноваженням навіть на те, щоб за нього платити."""
    _, victim_audit = await _ready(client, db_session)
    stranger = await _open(client)

    refused = await client.post(
        f"/v1/public/audits/{victim_audit}/checkout", headers=_auth(stranger)
    )
    assert refused.status_code == 404
    assert await _purchases(db_session, victim_audit) == []


# ── K. оплачено, але не провіжено ──────────────────────────────────────────


async def test_paid_without_unlock_stays_discoverable_and_completable(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """K: гроші не «розоплачуються» через те, що право не видалось.

    Стан видимий запитом, а доробити його можна ідемпотентно — саме це
    відрізняє відновлюваний збій від тиші.
    """
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])
    await _deliver(client, _paid_event(purchase_ref=intent))

    db_session.expire_all()
    purchase = (await _purchases(db_session, audit_id))[0]

    unlock = await db_session.scalar(
        select(AuditUnlock).where(AuditUnlock.audit_id == uuid.UUID(audit_id))
    )
    assert unlock is not None
    await db_session.delete(unlock)
    await db_session.flush()

    stuck = await guest_app.unprovisioned_purchases(db_session)
    assert purchase.id in {row.id for row in stuck}

    await guest_app.unlock_for_purchase(
        db_session, purchase=purchase, audit_id=uuid.UUID(audit_id)
    )
    await guest_app.unlock_for_purchase(
        db_session, purchase=purchase, audit_id=uuid.UUID(audit_id)
    )
    await db_session.flush()
    rows = await db_session.scalars(
        select(AuditUnlock).where(AuditUnlock.audit_id == uuid.UUID(audit_id))
    )
    assert len(list(rows)) == 1
    assert await guest_app.unprovisioned_purchases(db_session) == []


# ── L, M. повернення коштів ────────────────────────────────────────────────


async def test_refunding_the_only_payment_closes_access(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """L: повернули єдину оплату — платного доступу немає."""
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])
    await _deliver(client, _paid_event(purchase_ref=intent))
    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 200

    refunded = await _deliver(client, _refund_event(transaction=_FAKE_TRANSACTION))
    assert refunded.status_code == 200

    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 402

    db_session.expire_all()
    purchase = (await _purchases(db_session, audit_id))[0]
    assert purchase.status is PurchaseStatus.REFUNDED
    assert purchase.purchased_at is not None, "історію не стираємо"

    state = await client.get(
        f"/v1/public/audits/{audit_id}/payment", headers=_auth(token)
    )
    assert state.json()["state"] == purchases_app.PAYMENT_REFUNDED
    assert state.json()["unlocked"] is False


async def test_a_second_transaction_on_one_intent_is_its_own_purchase(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """M: дві вкладки — дві оплати, і повернути можна саме одну з них.

    Мовчазне поглинання другого платежу було б втратою грошей клієнта:
    рядок один, повертати нема за чим, а повернення єдиної покупки
    забрало б доступ, оплачений двічі.
    """
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])

    await _deliver(client, _paid_event(purchase_ref=intent))
    second = await _deliver(
        client,
        _paid_event(
            purchase_ref=intent, event_id="evt-paid-2", transaction="fake-txn-2"
        ),
    )
    assert second.status_code == 200

    db_session.expire_all()
    purchases = await _purchases(db_session, audit_id)
    assert len(purchases) == 2
    assert {p.status for p in purchases} == {PurchaseStatus.PAID}

    await _deliver(client, _refund_event(transaction=_FAKE_TRANSACTION))
    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 200, "друга оплата тримає доступ"

    await _deliver(
        client, _refund_event(transaction="fake-txn-2", event_id="evt-refund-2")
    )
    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 402


# ── N, O. невдала й закинута каса ──────────────────────────────────────────


async def test_a_failed_payment_unlocks_nothing_and_blocks_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """N: відмова банку — це стан екрана, а не термінальний стан покупки.

    Якби невдала спроба закривала покупку, людина мусила б чекати на
    нашу дію, щоб спробувати ще раз.
    """
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])

    failed = await _deliver(client, _failed_event(purchase_ref=intent))
    assert failed.status_code == 200

    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 402
    state = await client.get(
        f"/v1/public/audits/{audit_id}/payment", headers=_auth(token)
    )
    assert state.json()["state"] == purchases_app.PAYMENT_FAILED

    db_session.expire_all()
    assert (await _purchases(db_session, audit_id))[0].status is PurchaseStatus.PENDING

    retry = await _deliver(
        client, _paid_event(purchase_ref=intent, event_id="evt-paid-retry")
    )
    assert retry.status_code == 200
    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 200


async def test_an_abandoned_till_leaves_a_pending_row_and_nothing_else(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """O: закинута каса не відкриває нічого й не заважає наступній спробі."""
    token, audit_id = await _ready(client, db_session)
    first = await _checkout(client, token, audit_id)

    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 402

    again = await _checkout(client, token, audit_id)
    assert again["purchase_intent"] == first["purchase_intent"]
    assert len(await _purchases(db_session, audit_id)) == 1


async def test_buying_again_after_a_refund_is_allowed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Повторна покупка того самого аудиту законна — і створює НОВУ покупку."""
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])
    await _deliver(client, _paid_event(purchase_ref=intent))
    await _deliver(client, _refund_event(transaction=_FAKE_TRANSACTION))

    second = await _checkout(client, token, audit_id)
    assert second["purchase_intent"] != intent

    db_session.expire_all()
    purchases = await _purchases(db_session, audit_id)
    assert len(purchases) == 2
    assert {p.status for p in purchases} == {
        PurchaseStatus.REFUNDED,
        PurchaseStatus.PENDING,
    }


# ── P, Q. без акаунта й без пошти ──────────────────────────────────────────


async def test_the_whole_purchase_needs_no_account_and_no_email(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """P+Q: право тримається на покупці, а не на особі.

    Ані пошти, ані користувача в цьому шляху немає жодного разу — і
    саме тому пошта не може стати ключем до чужого звіту.
    """
    token, audit_id = await _ready(client, db_session)
    intent = str((await _checkout(client, token, audit_id))["purchase_intent"])
    await _deliver(client, _paid_event(purchase_ref=intent))

    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 200

    db_session.expire_all()
    purchase = (await _purchases(db_session, audit_id))[0]

    # `supplier_snapshot` виключений свідомо: там наші власні реквізити
    # продавця, і пошта в ньому — теж наша. Твердження стосується
    # покупця: жодне поле покупки його не називає.
    written = " ".join(
        str(getattr(purchase, column.name))
        for column in purchase.__table__.columns
        if column.name != "supplier_snapshot"
    )
    assert "@" not in written, "у покупці немає жодної адреси покупця"


# ── публічні налаштування каси ─────────────────────────────────────────────


async def test_checkout_config_is_public_and_carries_no_secret(
    client: httpx.AsyncClient,
) -> None:
    """Сторінку оплати Paddle відкриває без нашої спроможності.

    Посилання `?_ptxn=` приходить листом, з іншого браузера, наступного
    дня — гостьового токена там немає й бути не мусить. Тому вхід
    відкритий, і саме тому в ньому не може бути нічого, крім публічних
    значень провайдера.
    """
    response = await client.get("/v1/public/checkout-config")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"provider", "environment", "client_token"}
    assert body["environment"] in {"sandbox", "live"}
    # Секрети сервера сюди не потрапляють навіть частково.
    assert "pdl_sdbx" not in response.text
    assert "pdl_live" not in response.text
    assert "pdl_ntfset" not in response.text


# ── T. закрите вікно каси: звірка з провайдером, а не здогад ───────────────


async def _payment(
    client: httpx.AsyncClient, token: str, audit_id: str, *, reconcile: bool
) -> dict[str, object]:
    query = "?reconcile=true" if reconcile else ""
    response = await client.get(
        f"/v1/public/audits/{audit_id}/payment{query}", headers=_auth(token)
    )
    assert response.status_code == 200, response.text
    return dict(response.json())


async def test_before_any_till_nothing_could_have_been_charged(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Покупки немає — списувати нема за що, і це відомо без провайдера."""
    token, audit_id = await _ready(client, db_session)
    answer = await _payment(client, token, audit_id, reconcile=True)
    assert answer["state"] == purchases_app.PAYMENT_NONE
    assert answer["charged"] is False


async def test_an_open_till_is_unknown_until_someone_asks_the_provider(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Без `reconcile` наші записи про відкриту касу мовчать — і відповідь
    теж: `None`, а не вигадане «ні»."""
    token, audit_id = await _ready(client, db_session)
    await _checkout(client, token, audit_id)

    plain = await _payment(client, token, audit_id, reconcile=False)
    assert plain["state"] == purchases_app.PAYMENT_PROCESSING
    assert plain["charged"] is None


async def test_a_till_closed_without_paying_reconciles_to_uncharged(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Провайдер каже «не оплачено» — і лише тоді екран має право на
    «кошти не списано» й кнопку повторної спроби."""
    token, audit_id = await _ready(client, db_session)
    await _checkout(client, token, audit_id)

    answer = await _payment(client, token, audit_id, reconcile=True)
    assert answer["state"] == purchases_app.PAYMENT_PROCESSING
    assert answer["charged"] is False
    assert answer["unlocked"] is False


async def test_money_taken_before_the_event_arrives_is_charged_not_unlocked(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Гроші пішли, вебхук у дорозі: `charged` — так, доступу — ні.

    Звірка не сміє видати право: воно й далі приходить лише з подією.
    Але вона зобовʼязана не дати екрану сказати «не списано» людині,
    яка щойно заплатила.
    """
    token, audit_id = await _ready(client, db_session)
    opened = await _checkout(client, token, audit_id)
    fake_provider().settle(str(opened["transaction_ref"]))

    answer = await _payment(client, token, audit_id, reconcile=True)
    assert answer["charged"] is True
    assert answer["state"] == purchases_app.PAYMENT_PROCESSING
    assert answer["unlocked"] is False
    assert (
        await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    ).status_code == 402


async def test_a_silent_provider_leaves_the_charge_unknown(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Провайдер не відповів — `None`. Не «ні»: тайм-аут — не доказ."""
    token, audit_id = await _ready(client, db_session)
    await _checkout(client, token, audit_id)

    provider = fake_provider()
    provider.down = True
    try:
        answer = await _payment(client, token, audit_id, reconcile=True)
    finally:
        provider.down = False
    assert answer["charged"] is None
    assert answer["state"] == purchases_app.PAYMENT_PROCESSING


async def test_reopening_after_a_closed_till_keeps_one_purchase_and_no_right(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Повторна спроба після закритого вікна: та сама покупка, жодного права.

    Кнопка «спробувати ще раз» відкриває касу на той самий аудит; другого
    рядка покупки, другого аудиту й будь-якого доступу від цього не буде.
    """
    token, audit_id = await _ready(client, db_session)
    first = await _checkout(client, token, audit_id)
    assert (await _payment(client, token, audit_id, reconcile=True))["charged"] is False

    second = await _checkout(client, token, audit_id)
    assert second["purchase_intent"] == first["purchase_intent"]
    assert second["audit_id"] == audit_id

    rows = await _purchases(db_session, audit_id)
    assert len(rows) == 1
    assert rows[0].status is PurchaseStatus.PENDING
    assert await guest_app.is_unlocked(db_session, uuid.UUID(audit_id)) is False


async def test_a_refunded_purchase_is_not_charged_anymore(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    token, audit_id = await _ready(client, db_session)
    opened = await _checkout(client, token, audit_id)
    await _deliver(client, _paid_event(purchase_ref=str(opened["purchase_intent"])))
    assert (await _payment(client, token, audit_id, reconcile=False))["charged"] is True

    await _deliver(client, _refund_event(transaction=_FAKE_TRANSACTION))
    after = await _payment(client, token, audit_id, reconcile=False)
    assert after["state"] == purchases_app.PAYMENT_REFUNDED
    assert after["charged"] is False
