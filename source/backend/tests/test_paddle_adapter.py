"""Адаптер Paddle: контракт із провайдером, і більше нічого.

Усе провайдерське живе тут — форма підпису, назви подій, адреси API,
вигляд тіла транзакції. Домен цього не бачить жодного разу, і саме тому
файл окремий: коли Paddle зміниться, червоним стане він, а не матриця
прав у `tests/integration/test_one_off_checkout.py`.

Жодного справжнього виклику. HTTP підмінений `respx`, тіла подій зібрані
за офіційними формами Paddle, підпис рахується тим самим алгоритмом, що
й у продукті, — але на тестовому секреті.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
import respx

from app.billing.enums import BillingEventKind
from app.billing.providers import (
    CheckoutRequest,
    InvalidWebhook,
    ProviderUnavailable,
    Settlement,
)
from app.billing.providers import paddle as paddle_module
from app.billing.providers.paddle import (
    LIVE_BASE_URL,
    SANDBOX_BASE_URL,
    PaddleNotConfigured,
    PaddleProvider,
    UnsupportedEvent,
)
from app.core.config import settings

SECRET = "pdl_ntfset_test_secret"
SANDBOX_KEY = "pdl_sdbx_apikey_0123456789"
LIVE_KEY = "pdl_live_apikey_0123456789"
PRICE = "pri_01test0000000000000000000"


@pytest.fixture(autouse=True)
def _sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    """Пісочниця з тестовими значеннями. Справжніх секретів тут немає."""
    monkeypatch.setattr(settings, "paddle_env", "sandbox")
    monkeypatch.setattr(settings, "paddle_api_key", SANDBOX_KEY)
    monkeypatch.setattr(settings, "paddle_webhook_secret", SECRET)
    monkeypatch.setattr(settings, "paddle_signature_tolerance_s", 300)


def _sign(body: bytes, *, secret: str = SECRET, at: int | None = None) -> dict[str, str]:
    """Підпис Paddle: HMAC-SHA256 над `ts:сире тіло`."""
    ts = str(at if at is not None else int(datetime.now(UTC).timestamp()))
    digest = hmac.new(secret.encode(), f"{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return {"paddle-signature": f"ts={ts};h1={digest}"}


def _envelope(event_type: str, data: dict[str, Any], *, event_id: str = "evt_01") -> bytes:
    """Конверт події Paddle: event_id / event_type / occurred_at / data."""
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": "2026-08-25T10:15:30.123456Z",
            "notification_id": "ntf_01",
            "data": data,
        }
    ).encode("utf-8")


def _completed(
    *, purchase_id: str, transaction: str = "txn_01", total: str = "1000"
) -> dict[str, Any]:
    return {
        "id": transaction,
        "status": "completed",
        "customer_id": "ctm_01",
        "currency_code": "USD",
        "custom_data": {paddle_module.CUSTOM_PURCHASE_KEY: purchase_id},
        "details": {"totals": {"total": total, "currency_code": "USD"}},
    }


# ── каса ───────────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_checkout_creates_a_transaction_and_returns_its_url() -> None:
    """Каса — це транзакція Paddle, а не адреса, зібрана нами з рядків."""
    purchase_id = uuid.uuid4()
    route = respx.post(f"{SANDBOX_BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            201,
            json={
                "data": {
                    "id": "txn_01",
                    "status": "ready",
                    "checkout": {"url": "https://sandbox-pay.paddle.io/hsc_01"},
                }
            },
        )
    )

    session = await PaddleProvider().create_checkout(
        CheckoutRequest(
            purchase_id=purchase_id,
            price_ref=PRICE,
            organization_id=uuid.uuid4(),
        )
    )

    assert session.ref.provider == "paddle"
    assert session.ref.external_id == "txn_01"
    assert session.url == "https://sandbox-pay.paddle.io/hsc_01"

    request = route.calls.last.request
    assert request.headers["authorization"] == f"Bearer {SANDBOX_KEY}"
    body = json.loads(request.content)
    assert body["items"] == [{"price_id": PRICE, "quantity": 1}]
    assert body["collection_mode"] == "automatic"


@respx.mock
@pytest.mark.asyncio
async def test_only_our_own_identifier_leaves_for_paddle() -> None:
    """Мінімум довільних даних: один непрозорий ідентифікатор.

    Аудит, організація й будь-що інше вже лежать у покупці. Віддане
    туди повертається кимось іншим і повноваженням не є — тож чим менше
    ми туди кладемо, тим менше можна підробити.
    """
    purchase_id = uuid.uuid4()
    organization_id = uuid.uuid4()
    route = respx.post(f"{SANDBOX_BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            201,
            json={"data": {"id": "txn_01", "checkout": {"url": "https://pay/x"}}},
        )
    )

    await PaddleProvider().create_checkout(
        CheckoutRequest(
            purchase_id=purchase_id, price_ref=PRICE, organization_id=organization_id
        )
    )

    body = json.loads(route.calls.last.request.content)
    assert body["custom_data"] == {
        paddle_module.CUSTOM_PURCHASE_KEY: str(purchase_id)
    }
    assert str(organization_id) not in route.calls.last.request.content.decode()
    assert "customer_id" not in body, "гостьова покупка не має покупця заздалегідь"


@respx.mock
@pytest.mark.asyncio
async def test_the_account_default_payment_link_is_never_overridden() -> None:
    """`checkout.url` не надсилається — і це не дрібниця оформлення.

    У Paddle це адреса сторінки оплати, а не адреса повернення після
    неї. Поки ми клали туди своє «повернення», кожна транзакція
    перекривала обліковий default payment link сторінкою, якої не
    існує, — мовчки, бо помилки немає, посилання просто веде в нікуди.
    """
    route = respx.post(f"{SANDBOX_BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            201,
            json={"data": {"id": "txn_01", "checkout": {"url": "https://pay/x"}}},
        )
    )

    await PaddleProvider().create_checkout(
        CheckoutRequest(
            purchase_id=uuid.uuid4(), price_ref=PRICE, organization_id=uuid.uuid4()
        )
    )

    body = json.loads(route.calls.last.request.content)
    assert "checkout" not in body, "адресу каси задає акаунт, а не транзакція"


@respx.mock
@pytest.mark.asyncio
async def test_a_promo_discount_travels_as_the_paddle_discount_id() -> None:
    """Промо — це гроші, і живе воно в транзакції провайдера.

    Ключ пісочниці не вповноважений створювати знижки (403 на
    POST /discounts), тож наскрізний прогін цю гілку не бачить — форма
    поля закріплена тут. Кількість кредитів знижка не чіпає ніде.
    """
    route = respx.post(f"{SANDBOX_BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            201,
            json={"data": {"id": "txn_01", "checkout": {"url": "https://pay/x"}}},
        )
    )

    await PaddleProvider().create_checkout(
        CheckoutRequest(
            purchase_id=uuid.uuid4(),
            price_ref=PRICE,
            organization_id=uuid.uuid4(),
            discount_ref="dsc_01launch50",
        )
    )

    body = json.loads(route.calls.last.request.content)
    assert body["discount_id"] == "dsc_01launch50"
    assert body["items"] == [{"price_id": PRICE, "quantity": 1}], (
        "знижка міняє суму, а не кількість"
    )


@respx.mock
@pytest.mark.asyncio
async def test_without_a_promo_no_discount_field_is_sent() -> None:
    route = respx.post(f"{SANDBOX_BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            201,
            json={"data": {"id": "txn_01", "checkout": {"url": "https://pay/x"}}},
        )
    )
    await PaddleProvider().create_checkout(
        CheckoutRequest(
            purchase_id=uuid.uuid4(), price_ref=PRICE, organization_id=uuid.uuid4()
        )
    )
    assert "discount_id" not in json.loads(route.calls.last.request.content)


def test_the_contract_has_no_return_url_to_misplace() -> None:
    """Поля з такою назвою немає — саме тому його нікуди не покласти.

    Повернення після оплати в Paddle взагалі не серверне поняття: його
    задає `successUrl` у налаштуваннях Paddle.js, тобто браузер.
    """
    assert not hasattr(
        CheckoutRequest(
            purchase_id=uuid.uuid4(), price_ref=PRICE, organization_id=uuid.uuid4()
        ),
        "return_url",
    )


@respx.mock
@pytest.mark.asyncio
async def test_a_refusal_from_paddle_does_not_carry_its_body_outward() -> None:
    """Помилка провайдера — код і його код помилки, без тіла відповіді."""
    respx.post(f"{SANDBOX_BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            403,
            json={
                "error": {
                    "code": "forbidden",
                    "detail": "token pdl_sdbx_secret_leaked_here",
                }
            },
        )
    )

    with pytest.raises(ProviderUnavailable) as raised:
        await PaddleProvider().create_checkout(
            CheckoutRequest(
                purchase_id=uuid.uuid4(), price_ref=PRICE, organization_id=uuid.uuid4()
            )
        )

    message = str(raised.value)
    assert "403" in message
    assert "forbidden" in message
    assert "pdl_sdbx_secret_leaked_here" not in message


@respx.mock
@pytest.mark.asyncio
async def test_a_timeout_is_an_exception_not_a_hang() -> None:
    respx.post(f"{SANDBOX_BASE_URL}/transactions").mock(
        side_effect=httpx.ConnectTimeout("too slow")
    )
    with pytest.raises(ProviderUnavailable):
        await PaddleProvider().create_checkout(
            CheckoutRequest(
                purchase_id=uuid.uuid4(), price_ref=PRICE, organization_id=uuid.uuid4()
            )
        )


@pytest.mark.asyncio
async def test_a_missing_key_is_our_configuration_not_their_outage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "paddle_api_key", None)
    with pytest.raises(PaddleNotConfigured):
        await PaddleProvider().create_checkout(
            CheckoutRequest(
                purchase_id=uuid.uuid4(), price_ref=PRICE, organization_id=uuid.uuid4()
            )
        )


@pytest.mark.asyncio
async def test_a_guest_purchase_never_creates_a_customer() -> None:
    """`create_customer` лишається в контракті й не використовується тут."""
    with pytest.raises(PaddleNotConfigured):
        await PaddleProvider().create_customer(
            organization_id=uuid.uuid4(), email="someone@example.com"
        )


# ── портал ─────────────────────────────────────────────────────────────────


@respx.mock
@pytest.mark.asyncio
async def test_the_portal_is_a_paddle_session_not_our_own_page() -> None:
    """Кабінет платежів хостить Paddle: ми лише просимо посилання.

    Ключ пісочниці не читає і не створює покупців (403), тож жива
    перевірка тут неможлива — форма виклику й розбір відповіді
    закріплені за офіційною документацією portal-sessions.
    """
    route = respx.post(
        f"{SANDBOX_BASE_URL}/customers/ctm_01/portal-sessions"
    ).mock(
        return_value=httpx.Response(
            201,
            json={
                "data": {
                    "id": "cpls_01",
                    "urls": {
                        "general": {
                            "overview": "https://sandbox-customer-portal.paddle.com/cpl_01"
                        }
                    },
                }
            },
        )
    )

    url = await PaddleProvider().create_portal_session(customer_ref="ctm_01")

    assert url == "https://sandbox-customer-portal.paddle.com/cpl_01"
    assert route.calls.last.request.headers["authorization"] == (
        f"Bearer {SANDBOX_KEY}"
    )


@respx.mock
@pytest.mark.asyncio
async def test_a_portal_refusal_does_not_leak_the_provider_body() -> None:
    respx.post(f"{SANDBOX_BASE_URL}/customers/ctm_02/portal-sessions").mock(
        return_value=httpx.Response(
            404, json={"error": {"detail": "customer ctm_02 secret detail"}}
        )
    )
    with pytest.raises(ProviderUnavailable) as raised:
        await PaddleProvider().create_portal_session(customer_ref="ctm_02")
    assert "404" in str(raised.value)
    assert "secret detail" not in str(raised.value)


# ── оточення ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_live_key_in_the_sandbox_refuses_to_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Переплутати оточення має бути неможливо, а не малоймовірно.

    Бойовий ключ у пісочниці — це списання справжніх грошей за тестову
    покупку, і виявилось би це вже після списання.
    """
    monkeypatch.setattr(settings, "paddle_api_key", LIVE_KEY)
    with pytest.raises(PaddleNotConfigured):
        await PaddleProvider().create_checkout(
            CheckoutRequest(
                purchase_id=uuid.uuid4(), price_ref=PRICE, organization_id=uuid.uuid4()
            )
        )


@pytest.mark.asyncio
async def test_a_sandbox_key_in_production_refuses_to_work(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "paddle_env", "live")
    monkeypatch.setattr(settings, "paddle_api_key", SANDBOX_KEY)
    with pytest.raises(PaddleNotConfigured):
        await PaddleProvider().create_checkout(
            CheckoutRequest(
                purchase_id=uuid.uuid4(), price_ref=PRICE, organization_id=uuid.uuid4()
            )
        )


def test_the_two_environments_are_different_hosts() -> None:
    """Одна адреса на два оточення означала б відсутність поділу."""
    assert SANDBOX_BASE_URL != LIVE_BASE_URL
    assert "sandbox" in SANDBOX_BASE_URL


@respx.mock
@pytest.mark.asyncio
async def test_the_sandbox_host_is_the_one_actually_called() -> None:
    """Поділ, який ніхто не перевірив на виклику, — це коментар."""
    route = respx.post(f"{SANDBOX_BASE_URL}/transactions").mock(
        return_value=httpx.Response(
            201, json={"data": {"id": "txn_01", "checkout": {"url": "https://pay/x"}}}
        )
    )
    await PaddleProvider().create_checkout(
        CheckoutRequest(
            purchase_id=uuid.uuid4(), price_ref=PRICE, organization_id=uuid.uuid4()
        )
    )
    assert route.calls.last.request.url.host.startswith("sandbox-")


# ── підпис ─────────────────────────────────────────────────────────────────


def test_a_valid_signature_opens_the_envelope() -> None:
    body = _envelope("transaction.completed", _completed(purchase_id=str(uuid.uuid4())))
    event = PaddleProvider().verify_webhook(headers=_sign(body), body=body)
    assert event.kind is BillingEventKind.ONE_OFF_PURCHASED


def test_a_wrong_signature_is_refused() -> None:
    body = _envelope("transaction.completed", _completed(purchase_id=str(uuid.uuid4())))
    headers = _sign(body, secret="pdl_ntfset_someone_elses_secret")
    with pytest.raises(InvalidWebhook):
        PaddleProvider().verify_webhook(headers=headers, body=body)


def test_a_body_changed_after_signing_is_refused() -> None:
    """Підпис рахується від байтів, і будь-яка зміна їх ламає його."""
    original = _envelope(
        "transaction.completed", _completed(purchase_id=str(uuid.uuid4()))
    )
    headers = _sign(original)
    tampered = original.replace(b'"total": "1000"', b'"total": "1"')
    with pytest.raises(InvalidWebhook):
        PaddleProvider().verify_webhook(headers=headers, body=tampered)


def test_a_missing_signature_header_is_refused() -> None:
    body = _envelope("transaction.completed", _completed(purchase_id=str(uuid.uuid4())))
    with pytest.raises(InvalidWebhook):
        PaddleProvider().verify_webhook(headers={}, body=body)


def test_a_stale_timestamp_is_refused() -> None:
    """Захист від повтору перехопленого запиту."""
    body = _envelope("transaction.completed", _completed(purchase_id=str(uuid.uuid4())))
    old = int(datetime.now(UTC).timestamp()) - 86_400
    with pytest.raises(InvalidWebhook):
        PaddleProvider().verify_webhook(headers=_sign(body, at=old), body=body)


def test_without_a_configured_secret_nothing_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Поки секрета немає, ендпойнт закритий — а не «поки що відкритий»."""
    body = _envelope("transaction.completed", _completed(purchase_id=str(uuid.uuid4())))
    headers = _sign(body)
    monkeypatch.setattr(settings, "paddle_webhook_secret", None)
    with pytest.raises(InvalidWebhook):
        PaddleProvider().verify_webhook(headers=headers, body=body)


def test_the_signature_is_checked_before_the_body_is_parsed() -> None:
    """Порядок важливий: розбирати непідписане — це вже довіряти йому."""
    body = b"{ this is not json at all"
    with pytest.raises(InvalidWebhook) as raised:
        PaddleProvider().verify_webhook(
            headers={"paddle-signature": "ts=1;h1=deadbeef"}, body=body
        )
    assert "підпис" in str(raised.value)


def test_a_signed_but_malformed_body_is_refused() -> None:
    body = b"{ signed, but still not json"
    with pytest.raises(InvalidWebhook):
        PaddleProvider().verify_webhook(headers=_sign(body), body=body)


def test_a_signed_envelope_without_an_event_id_is_refused() -> None:
    body = json.dumps(
        {"event_type": "transaction.completed", "occurred_at": "2026-08-25T10:00:00Z", "data": {}}
    ).encode()
    with pytest.raises(InvalidWebhook):
        PaddleProvider().verify_webhook(headers=_sign(body), body=body)


# ── переклад подій ─────────────────────────────────────────────────────────


def test_a_completed_transaction_becomes_a_one_off_purchase() -> None:
    """Оплата Paddle → доменна разова покупка з нашою кореляцією."""
    purchase_id = str(uuid.uuid4())
    body = _envelope(
        "transaction.completed",
        _completed(purchase_id=purchase_id, transaction="txn_77", total="1000"),
        event_id="evt_paid",
    )

    event = PaddleProvider().verify_webhook(headers=_sign(body), body=body)

    assert event.provider == "paddle"
    assert event.external_event_id == "evt_paid"
    assert event.kind is BillingEventKind.ONE_OFF_PURCHASED
    assert event.quantity == 1
    assert event.currency == "USD"
    assert event.amount_minor == 1000
    assert event.customer_ref == "ctm_01"
    assert event.payload["purchase_ref"] == purchase_id
    assert event.payload["provider_transaction_id"] == "txn_77"
    assert "audit_id" not in event.payload, "аудит береться з нашого запису"


def test_the_provider_clock_is_the_one_recorded() -> None:
    """«Що новіше» вирішує час Paddle, а не час нашої доставки."""
    body = _envelope("transaction.completed", _completed(purchase_id=str(uuid.uuid4())))
    event = PaddleProvider().verify_webhook(headers=_sign(body), body=body)

    assert event.occurred_at == datetime(2026, 8, 25, 10, 15, 30, 123456, tzinfo=UTC)


def test_two_deliveries_of_one_event_carry_one_identity() -> None:
    """Дублікат розпізнається за `event_id`, і адаптер його зберігає.

    Сама ідемпотентність — у базі; адаптер зобовʼязаний лише не
    вигадувати новий ідентифікатор на кожну доставку.
    """
    body = _envelope(
        "transaction.completed",
        _completed(purchase_id=str(uuid.uuid4())),
        event_id="evt_same",
    )
    first = PaddleProvider().verify_webhook(headers=_sign(body), body=body)
    second = PaddleProvider().verify_webhook(headers=_sign(body), body=body)

    assert first.external_event_id == second.external_event_id == "evt_same"
    assert first.occurred_at == second.occurred_at


def test_out_of_order_deliveries_keep_their_own_times() -> None:
    """Порядок доставки не переписує часів: їх ставить провайдер."""
    older = json.dumps(
        {
            "event_id": "evt_old",
            "event_type": "transaction.completed",
            "occurred_at": "2026-08-25T09:00:00Z",
            "data": _completed(purchase_id=str(uuid.uuid4())),
        }
    ).encode()
    newer = json.dumps(
        {
            "event_id": "evt_new",
            "event_type": "transaction.completed",
            "occurred_at": "2026-08-25T11:00:00Z",
            "data": _completed(purchase_id=str(uuid.uuid4())),
        }
    ).encode()

    adapter = PaddleProvider()
    late = adapter.verify_webhook(headers=_sign(newer), body=newer)
    early = adapter.verify_webhook(headers=_sign(older), body=older)

    assert early.occurred_at < late.occurred_at


def test_a_failed_payment_becomes_a_failed_payment() -> None:
    purchase_id = str(uuid.uuid4())
    body = _envelope(
        "transaction.payment_failed",
        {
            "id": "txn_88",
            "customer_id": "ctm_01",
            "custom_data": {paddle_module.CUSTOM_PURCHASE_KEY: purchase_id},
        },
        event_id="evt_failed",
    )

    event = PaddleProvider().verify_webhook(headers=_sign(body), body=body)

    assert event.kind is BillingEventKind.PAYMENT_FAILED
    assert event.payload["provider_transaction_id"] == "txn_88"
    assert event.payload["purchase_ref"] == purchase_id


def test_a_refund_adjustment_becomes_a_refund() -> None:
    """Повернення посилається на транзакцію — за нею домен і шукає покупку."""
    body = _envelope(
        "adjustment.created",
        {
            "id": "adj_01",
            "action": "refund",
            "status": "approved",
            "transaction_id": "txn_77",
            "customer_id": "ctm_01",
        },
        event_id="evt_refund",
    )

    event = PaddleProvider().verify_webhook(headers=_sign(body), body=body)

    assert event.kind is BillingEventKind.ONE_OFF_REFUNDED
    assert event.payload["provider_transaction_id"] == "txn_77"


def test_an_adjustment_that_is_not_a_refund_is_not_a_refund() -> None:
    """`adjustment.created` буває й кредитом, і поверненням частини.

    Вважати будь-яке коригування поверненням означало б закривати
    доступ за подією, яка грошей не повертала.
    """
    body = _envelope(
        "adjustment.created",
        {"id": "adj_02", "action": "credit", "transaction_id": "txn_77"},
    )
    with pytest.raises(UnsupportedEvent):
        PaddleProvider().verify_webhook(headers=_sign(body), body=body)


def test_a_canceled_transaction_is_deliberately_not_a_domain_event() -> None:
    """Закрита каса лишає покупку PENDING — це не подія домену."""
    body = _envelope("transaction.canceled", {"id": "txn_99"})
    with pytest.raises(UnsupportedEvent):
        PaddleProvider().verify_webhook(headers=_sign(body), body=body)


# ── підписки ───────────────────────────────────────────────────────────────


def _subscription(
    *,
    subscription: str = "sub_01",
    status: str = "active",
    organization: str | None = None,
    scheduled_cancel: bool = False,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": subscription,
        "status": status,
        "customer_id": "ctm_01",
        "custom_data": {
            paddle_module.CUSTOM_ORGANIZATION_KEY: organization
            or "0b1e6a54-1111-4222-8333-444455556666"
        },
        "items": [{"price": {"id": "pri_monthly_01"}}],
        "current_billing_period": {
            "starts_at": "2026-09-03T00:00:00Z",
            "ends_at": "2026-10-03T00:00:00Z",
        },
    }
    if scheduled_cancel:
        data["scheduled_change"] = {
            "action": "cancel",
            "effective_at": "2026-10-03T00:00:00Z",
        }
    return data


def test_an_activated_subscription_becomes_started() -> None:
    """`subscription.activated` — початок життя, з періодом і тарифом."""
    body = _envelope("subscription.activated", _subscription())
    event = PaddleProvider().verify_webhook(headers=_sign(body), body=body)

    assert event.kind is BillingEventKind.SUBSCRIPTION_STARTED
    assert event.subscription_ref == "sub_01"
    assert event.price_ref == "pri_monthly_01"
    assert event.organization_id is not None
    assert event.period_start is not None and event.period_end is not None
    assert event.period_start < event.period_end


def test_an_update_with_a_moving_period_is_a_renewal() -> None:
    body = _envelope("subscription.updated", _subscription())
    event = PaddleProvider().verify_webhook(headers=_sign(body), body=body)
    assert event.kind is BillingEventKind.SUBSCRIPTION_RENEWED


def test_a_scheduled_cancel_wins_over_a_renewal_reading() -> None:
    """Оновлення зі scheduled_change — заплановане скасування, не поновлення.

    Порядок розвилки суттєвий: інакше кожне оновлення активної підписки
    скидало б прапорець «скасується наприкінці періоду».
    """
    body = _envelope(
        "subscription.updated", _subscription(scheduled_cancel=True)
    )
    event = PaddleProvider().verify_webhook(headers=_sign(body), body=body)
    assert event.kind is BillingEventKind.CANCELLATION_SCHEDULED
    assert event.cancel_at is not None


def test_the_subscription_lifecycle_events_map_to_their_kinds() -> None:
    expected = {
        "subscription.past_due": BillingEventKind.PAYMENT_FAILED,
        "subscription.canceled": BillingEventKind.SUBSCRIPTION_CANCELLED,
        "subscription.paused": BillingEventKind.SUBSCRIPTION_PAUSED,
        "subscription.resumed": BillingEventKind.SUBSCRIPTION_RESUMED,
    }
    for event_type, kind in expected.items():
        body = _envelope(event_type, _subscription(status="past_due"))
        event = PaddleProvider().verify_webhook(headers=_sign(body), body=body)
        assert event.kind is kind, event_type


def test_a_subscription_payment_is_not_a_one_off_purchase() -> None:
    """`transaction.completed` З підпискою НЕ народжує разової покупки.

    Без цього захисту кожне місячне списання видавало б кредити, як
    покупка пакета. Стан підписки ведуть події `subscription.*`.
    """
    data = _completed(purchase_id="")
    data.pop("custom_data")
    data["subscription_id"] = "sub_01"
    body = _envelope("transaction.completed", data)
    with pytest.raises(UnsupportedEvent):
        PaddleProvider().verify_webhook(headers=_sign(body), body=body)


def test_subscription_created_is_still_ignored() -> None:
    """`created` передує оплаті — домен чекає на activated."""
    body = _envelope("subscription.created", _subscription(status="trialing"))
    with pytest.raises(UnsupportedEvent):
        PaddleProvider().verify_webhook(headers=_sign(body), body=body)


def test_an_unknown_event_type_is_ignored_not_rejected() -> None:
    """«Не слухаємо» і «відхилено» — різні відповіді провайдеру.

    Відмова змусила б Paddle повторювати доставку вічно; тип
    `UnsupportedEvent` дозволяє маршруту відповісти 200.
    """
    body = _envelope("something.brand_new", {"id": "x_01"})
    with pytest.raises(UnsupportedEvent) as raised:
        PaddleProvider().verify_webhook(headers=_sign(body), body=body)
    assert not isinstance(raised.value, ValueError)
    assert isinstance(raised.value, UnsupportedEvent)


def test_an_ignored_event_is_not_an_invalid_one() -> None:
    """Тип відмови несе рішення маршруту, тож він частина контракту."""
    assert not issubclass(UnsupportedEvent, ValueError)
    assert not issubclass(UnsupportedEvent, InvalidWebhook)


# ── читання стану транзакції: закрита каса не породжує події ────────────────


@respx.mock
@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("paddle_status", "expected"),
    [
        ("draft", Settlement.UNPAID),
        ("ready", Settlement.UNPAID),
        ("billed", Settlement.UNPAID),
        ("canceled", Settlement.UNPAID),
        ("past_due", Settlement.UNPAID),
        ("paid", Settlement.PAID),
        ("completed", Settlement.PAID),
        ("something_new", Settlement.UNKNOWN),
        ("", Settlement.UNKNOWN),
    ],
)
async def test_settlement_translates_every_documented_status(
    paddle_status: str, expected: Settlement
) -> None:
    """Довідник Paddle перекладається цілком, а невідоме — чесним UNKNOWN.

    Закрите без оплати вікно лишає транзакцію в `ready` — і саме цю
    відповідь екран читає як «кошти не списано». Статус, якого ми не
    знаємо, не перекладається навмання ні в один бік.
    """
    respx.get(f"{SANDBOX_BASE_URL}/transactions/txn_01").mock(
        return_value=httpx.Response(
            200, json={"data": {"id": "txn_01", "status": paddle_status}}
        )
    )
    assert await PaddleProvider().settlement_of(transaction_ref="txn_01") is expected


@respx.mock
@pytest.mark.asyncio
async def test_settlement_read_carries_the_key_and_nothing_else() -> None:
    route = respx.get(f"{SANDBOX_BASE_URL}/transactions/txn_01").mock(
        return_value=httpx.Response(200, json={"data": {"status": "ready"}})
    )
    await PaddleProvider().settlement_of(transaction_ref="txn_01")
    request = route.calls[0].request
    assert request.headers["Authorization"] == f"Bearer {SANDBOX_KEY}"
    assert request.method == "GET"
    assert not request.content


@respx.mock
@pytest.mark.asyncio
async def test_a_provider_that_cannot_answer_is_unavailable_not_unpaid() -> None:
    """Тайм-аут і 5xx — ProviderUnavailable, і жоден із них не «не оплачено».

    Сказати «кошти не списано» на підставі того, що Paddle не відповів,
    означало б запропонувати другу оплату тому, хто зробив першу.
    """
    respx.get(f"{SANDBOX_BASE_URL}/transactions/txn_slow").mock(
        side_effect=httpx.ReadTimeout("повільно")
    )
    with pytest.raises(ProviderUnavailable):
        await PaddleProvider().settlement_of(transaction_ref="txn_slow")

    respx.get(f"{SANDBOX_BASE_URL}/transactions/txn_500").mock(
        return_value=httpx.Response(500, json={"error": {"code": "internal"}})
    )
    with pytest.raises(ProviderUnavailable):
        await PaddleProvider().settlement_of(transaction_ref="txn_500")


@pytest.mark.asyncio
async def test_settlement_without_a_transaction_asks_nothing() -> None:
    with pytest.raises(ProviderUnavailable):
        await PaddleProvider().settlement_of(transaction_ref="")


def test_settlement_reads_are_short_lived() -> None:
    """Сторінка чекає на відповідь щосекунди; тайм-аут каси тут задовгий."""
    assert paddle_module.SETTLEMENT_TIMEOUT_S <= 5.0
