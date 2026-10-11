"""Paddle — перший справжній платіжний адаптер.

Усе, що нижче, — деталі Paddle, і жодна з них не має перетинати цю
межу: адреси API, назви подій, форма підпису, ідентифікатори транзакцій
і прайсів, статуси. Домен знає лише `BillingEventKind` і власні
сутності, тому заміна провайдера лишається заміною цього файла.

## Контракт, звірений з офіційною документацією (2026-08-25)

- **Автентифікація**: `Authorization: Bearer <api_key>`.
- **Адреси**: пісочниця `https://sandbox-api.paddle.com`, бойова
  `https://api.paddle.com`. Розділені явно й перевіряються за
  префіксом ключа — див. `_base_url`.
- **Каса**: `POST /transactions` з `items: [{price_id, quantity}]`,
  `collection_mode: "automatic"` і нашими `custom_data`. У відповіді —
  `id` (`txn_…`) і `checkout.url`.
- **Підпис вебхука**: заголовок `Paddle-Signature` виду
  `ts=<unix>;h1=<hex>`; підписується рядок `ts:<сире тіло>` алгоритмом
  HMAC-SHA256 на секреті призначення; порівняння — стале за часом.
- **Конверт події**: `event_id` (`evt_…`), `event_type`, `occurred_at`
  (RFC 3339), `data`.
- **Події разової покупки**: `transaction.completed` — оплачено;
  `transaction.payment_failed` — оплата не пройшла; `transaction.canceled`
  — касу закрито; `adjustment.created` з `action == "refund"` —
  повернення коштів.

## Підписки

- **Каса підписки** — та сама `POST /transactions` з recurring-прайсом:
  Paddle сам створює підписку після оплати. Кореляція — наш
  `crawldy_organization_id` у `custom_data` транзакції: Paddle копіює
  його в підписку, і кожна подія `subscription.*` несе його назад.
- **Події підписки**: `subscription.activated` — почалася;
  `subscription.updated` — просунувся період або заплановано
  скасування (розрізняє `scheduled_change`); `subscription.past_due` —
  списання не пройшло; `subscription.canceled` / `paused` / `resumed`.
- **`transaction.completed` З `subscription_id`** — оплата підписки, а
  не разова покупка: вона НЕ мапиться (стан ведуть `subscription.*`).
  Без цього захисту кожне списання підписки народжувало б фальшиву
  разову покупку з кредитами.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.billing.enums import BillingEventKind
from app.billing.providers.base import (
    CheckoutRequest,
    CheckoutSession,
    InvalidWebhook,
    ProviderRef,
    ProviderUnavailable,
    Settlement,
    SettlementReport,
    UnhandledEvent,
    VerifiedBillingEvent,
)
from app.core import runtime_config as runtime

NAME = "paddle"

SANDBOX_BASE_URL = "https://sandbox-api.paddle.com"
LIVE_BASE_URL = "https://api.paddle.com"

# Ключі пісочниці й бойові розрізняються префіксом. Перевірка тут — щоб
# «переплутати оточення» стало неможливим, а не малоймовірним: інакше
# бойовий ключ у пісочниці мовчки списав би справжні гроші.
SANDBOX_KEY_MARKER = "sdbx"

SIGNATURE_HEADER = "paddle-signature"

# Довільні дані, які ми віддаємо Paddle і чекаємо назад. Для разової
# покупки — ідентифікатор НАШОЇ покупки: аудит, організація й решта вже
# лежать у ній. Для підписки покупки-рядка немає, тож кореляцією служить
# організація: Paddle копіює custom_data транзакції в підписку й повертає
# їх у кожній події `subscription.*`. Надіслане туди повертається кимось
# іншим і перевіряється як чуже.
CUSTOM_PURCHASE_KEY = "crawldy_purchase_id"
CUSTOM_ORGANIZATION_KEY = "crawldy_organization_id"

# Читання стану транзакції коротке: його робить сторінка, що чекає на
# відповідь щосекунди, і двадцять секунд тайм-ауту каси перетворились
# би на двадцять секунд порожнього екрана. Провайдер, який не встиг,
# дає UNKNOWN — не «не оплачено».
SETTLEMENT_TIMEOUT_S = 5.0

# Статус транзакції Paddle → відповідь на питання «гроші взято?».
# Довідник: draft/ready — каса ще відкрита; billed — рахунок без оплати;
# paid/completed — оплачено; canceled — скасовано; past_due — прострочено.
_SETTLEMENT_BY_STATUS: dict[str, Settlement] = {
    "draft": Settlement.UNPAID,
    "ready": Settlement.UNPAID,
    "billed": Settlement.UNPAID,
    "canceled": Settlement.UNPAID,
    "past_due": Settlement.UNPAID,
    "paid": Settlement.PAID,
    "completed": Settlement.PAID,
}


class PaddleNotConfigured(ProviderUnavailable):
    """Ключа, прайса чи секрета немає — це наша конфігурація, не збій Paddle."""


def _base_url() -> str:
    """Адреса, що відповідає оточенню, і перевірка, що ключ їй пасує."""
    key = runtime.get("paddle_api_key") or ""
    sandbox = (runtime.get("paddle_env") or "sandbox") == "sandbox"
    if sandbox and key and SANDBOX_KEY_MARKER not in key:
        raise PaddleNotConfigured(
            "у пісочниці стоїть ключ, схожий на бойовий — оточення переплутано"
        )
    if not sandbox and key and SANDBOX_KEY_MARKER in key:
        raise PaddleNotConfigured(
            "у бойовому оточенні стоїть ключ пісочниці — оточення переплутано"
        )
    return SANDBOX_BASE_URL if sandbox else LIVE_BASE_URL


class PaddleProvider:
    """Адаптер Paddle.

    Мережа — у трьох місцях: каса (`create_checkout`), портал
    (`create_portal_session`) і читання стану транзакції
    (`settlement_of`). Перші два створюють; третє лише читає й нічого не
    змінює.
    """

    @property
    def name(self) -> str:
        return NAME

    async def create_customer(
        self, *, organization_id: uuid.UUID, email: str
    ) -> ProviderRef:
        """Не використовується разовою покупкою — і це рішення, не пропуск.

        Анонімна воронка не має ані акаунта, ані пошти. Paddle збирає
        покупця на власній сторінці оплати, тож синтетична адреса заради
        цього виклику створювала б фальшиву особу заради форми.

        Метод лишається в контракті: кабінет і майбутня підписка знають
        покупця заздалегідь.
        """
        raise PaddleNotConfigured(
            "разова покупка не створює покупця заздалегідь: Paddle збирає його в касі"
        )

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        """Транзакція Paddle і посилання на касу.

        Єдиний мережевий виклик адаптера. Ідемпотентності на боці Paddle
        тут немає, тож від подвійного кліку боронить домен: він шукає
        відкриту покупку раніше, ніж дійде сюди.
        """
        api_key = runtime.get("paddle_api_key")
        if not api_key:
            raise PaddleNotConfigured("не заданий PADDLE_API_KEY")
        if not request.price_ref:
            raise PaddleNotConfigured("для цього виду покупки не налаштований прайс")

        # Мінімум довільних даних. Разова покупка називає себе НАШИМ
        # ідентифікатором покупки — аудит і організація вже лежать у
        # ній. Підписка покупки-рядка не має, тож їй — і лише їй —
        # кореляцією служить організація: Paddle скопіює custom_data
        # транзакції в підписку й поверне в кожній події subscription.*.
        custom_data: dict[str, str] = (
            {CUSTOM_PURCHASE_KEY: str(request.purchase_id)}
            if request.purchase_id is not None
            else {CUSTOM_ORGANIZATION_KEY: str(request.organization_id)}
        )
        payload: dict[str, Any] = {
            "items": [{"price_id": request.price_ref, "quantity": 1}],
            "collection_mode": "automatic",
            "custom_data": custom_data,
        }
        if request.discount_ref:
            payload["discount_id"] = request.discount_ref
        # `checkout.url` НЕ надсилається навмисно. У Paddle це адреса
        # сторінки, на якій відбувається оплата, а не адреса повернення
        # після неї — і поки ми клали туди своє «повернення», кожна
        # транзакція перекривала обліковий default payment link
        # сторінкою, якої не існує. Мовчки: помилки немає, посилання
        # просто веде в нікуди.
        #
        # Без цього поля Paddle підставляє налаштований в акаунті
        # default payment link, а куди відправити людину ПІСЛЯ оплати —
        # вирішує Paddle.js на самій сторінці (`successUrl`), тобто
        # браузер. Серверного поля для цього в Paddle немає взагалі.
        if request.customer is not None:
            payload["customer_id"] = request.customer.external_id

        try:
            async with httpx.AsyncClient(timeout=runtime.get_float("paddle_timeout_s")) as client:
                response = await client.post(
                    f"{_base_url()}/transactions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable(f"Paddle не відповів вчасно: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Paddle недоступний: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderUnavailable(_safe_error(response))

        data = response.json().get("data") or {}
        transaction_id = str(data.get("id") or "")
        url = str(((data.get("checkout") or {}).get("url")) or "")
        if not transaction_id or not url:
            raise ProviderUnavailable("Paddle не повернув ані транзакції, ані посилання")

        return CheckoutSession(
            ref=ProviderRef(provider=NAME, external_id=transaction_id), url=url
        )

    async def settlement_of(self, *, transaction_ref: str) -> Settlement:
        """GET /transactions/{id} → чи взяв Paddle гроші.

        Єдине читання адаптера, і воно існує заради одного випадку:
        людина закрила касу, не заплативши. Paddle тоді не надсилає
        нічого — `transaction.canceled` стосується скасування через API,
        а не закритого вікна, — і без прямого питання наш сервер до
        кінця часів казав би «обробляємо».

        Статуси транзакції (звірено з довідником Paddle 2026-09-05):
        `draft` і `ready` — каса відкрита, грошей немає; `billed` —
        виставлено рахунок, не оплачено; `paid` і `completed` — оплачено;
        `canceled` — скасовано; `past_due` — прострочено. Усе, чого тут
        немає, — UNKNOWN: краще чесне «не знаємо», ніж переклад навмання.

        Це читання нічого не змінює й права не дає: доступ і далі
        відкриває лише перевірена подія `transaction.completed`.
        """
        api_key = runtime.get("paddle_api_key")
        if not api_key:
            raise PaddleNotConfigured("не заданий PADDLE_API_KEY")
        if not transaction_ref:
            raise ProviderUnavailable("транзакцію не названо — питати нема про що")

        try:
            async with httpx.AsyncClient(timeout=SETTLEMENT_TIMEOUT_S) as client:
                response = await client.get(
                    f"{_base_url()}/transactions/{transaction_ref}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
        except httpx.TimeoutException as exc:
            raise ProviderUnavailable(f"Paddle не відповів вчасно: {exc}") from exc
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Paddle недоступний: {exc}") from exc

        if response.status_code >= 400:
            raise ProviderUnavailable(_safe_error(response))
        try:
            data = response.json().get("data") or {}
        except ValueError as exc:
            raise ProviderUnavailable("Paddle відповів не JSON") from exc
        return _SETTLEMENT_BY_STATUS.get(str(data.get("status") or ""), Settlement.UNKNOWN)

    async def settlement_report(self, *, transaction_ref: str) -> SettlementReport:
        """Стан транзакції плюс гроші, які Paddle справді взяв.

        Сума — з підсумків транзакції (`details.totals.grand_total`): це
        те, що стоїть у квитанції клієнта, з податком і знижкою, і саме
        його має бачити той, хто зараховує оплату руками. Наш власний
        рядок каже лише, скільки ми хотіли.
        """
        api_key = runtime.get("paddle_api_key")
        if not api_key:
            raise PaddleNotConfigured("не заданий PADDLE_API_KEY")
        if not transaction_ref:
            raise ProviderUnavailable("транзакцію не названо — питати нема про що")
        try:
            async with httpx.AsyncClient(timeout=SETTLEMENT_TIMEOUT_S) as client:
                response = await client.get(
                    f"{_base_url()}/transactions/{transaction_ref}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
        except httpx.HTTPError as exc:
            raise ProviderUnavailable(f"Paddle недоступний: {exc}") from exc
        if response.status_code >= 400:
            raise ProviderUnavailable(_safe_reason(response))
        try:
            data = response.json().get("data") or {}
        except ValueError as exc:
            raise ProviderUnavailable("Paddle відповів не JSON") from exc
        totals = (data.get("details") or {}).get("totals") or {}
        raw = str(totals.get("grand_total") or "")
        customer_ref = str(data.get("customer_id") or "") or None
        return SettlementReport(
            settlement=_SETTLEMENT_BY_STATUS.get(
                str(data.get("status") or ""), Settlement.UNKNOWN
            ),
            amount_minor=int(raw) if raw.isdigit() else None,
            currency=str(totals.get("currency_code") or data.get("currency_code") or "")
            or None,
            invoice=str(data.get("invoice_number") or "") or None,
            customer_ref=customer_ref,
            email=await self._customer_email(customer_ref, api_key),
        )

    async def _customer_email(self, customer_ref: str | None, api_key: str) -> str | None:
        """Пошта покупця, якщо ключ має право її читати.

        Окремим запитом, а не `include=customer` до транзакції: без права
        `customer.read` Paddle відхиляє ЗАПИТ ЦІЛКОМ, тобто звірка втратила б
        і стан, і суму заради поля, яке лише приємно мати. Відмова тут
        коштує порожнє поле й нічого більше.
        """
        if not customer_ref:
            return None
        try:
            async with httpx.AsyncClient(timeout=SETTLEMENT_TIMEOUT_S) as client:
                response = await client.get(
                    f"{_base_url()}/customers/{customer_ref}",
                    headers={"Authorization": f"Bearer {api_key}"},
                )
        except httpx.HTTPError:
            return None
        if response.status_code >= 400:
            return None
        try:
            return str((response.json().get("data") or {}).get("email") or "") or None
        except ValueError:  # pragma: no cover — тіло не JSON
            return None

    async def create_portal_session(self, *, customer_ref: str) -> str:
        """POST /customers/{id}/portal-sessions — автентифіковане
        посилання на хостований кабінет: платіжні методи, квитанції,
        скасування підписки. Ми свого кабінету платежів не будуємо."""
        api_key = runtime.get("paddle_api_key")
        if not api_key:
            raise PaddleNotConfigured("не заданий PADDLE_API_KEY")
        async with httpx.AsyncClient(timeout=runtime.get_float("paddle_timeout_s")) as client:
            response = await client.post(
                f"{_base_url()}/customers/{customer_ref}/portal-sessions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={},
            )
        if response.status_code >= 400:
            # Код Paddle і його ж пояснення: «forbidden» саме по собі не
            # каже, що робити, а «not authorized to create
            # customer-portal-session» каже — бракує права ключа.
            raise ProviderUnavailable(f"портал недоступний: {_safe_reason(response)}")
        data = response.json().get("data") or {}
        url = ((data.get("urls") or {}).get("general") or {}).get("overview")
        if not url:
            raise ProviderUnavailable("портал не повернув посилання")
        return str(url)

    def verify_webhook(
        self, *, headers: dict[str, str], body: bytes
    ) -> VerifiedBillingEvent:
        """Підпис, потім розбір. Ніколи навпаки.

        Тіло береться сирим: підпис рахується від байтів, і будь-яке
        перекодування — розбір у JSON і зворотна збірка — його ламає.
        """
        secret = runtime.get("paddle_webhook_secret")
        if not secret:
            # Без секрета перевірити нічого. Прийняти «поки що» означало
            # б відкрити ендпойнт усім охочим.
            raise InvalidWebhook("PADDLE_WEBHOOK_SECRET не налаштований")

        lowered = {k.lower(): v for k, v in headers.items()}
        raw_signature = lowered.get(SIGNATURE_HEADER, "")
        timestamp, provided = _parse_signature(raw_signature)

        expected = hmac.new(
            secret.encode("utf-8"),
            f"{timestamp}:".encode() + body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, provided):
            raise InvalidWebhook("підпис не збігається")

        _reject_if_stale(timestamp)

        try:
            envelope = json.loads(body)
        except json.JSONDecodeError as exc:
            raise InvalidWebhook(f"тіло не розбирається як JSON: {exc}") from exc
        if not isinstance(envelope, dict):
            raise InvalidWebhook("очікували обʼєкт події")

        return _to_domain_event(envelope)


def _parse_signature(raw: str) -> tuple[str, str]:
    """`ts=…;h1=…` → (timestamp, signature)."""
    parts = dict(
        piece.split("=", 1) for piece in raw.split(";") if "=" in piece
    )
    timestamp = parts.get("ts", "").strip()
    signature = parts.get("h1", "").strip()
    if not timestamp or not signature:
        raise InvalidWebhook("заголовок підпису відсутній або неповний")
    return timestamp, signature


def _reject_if_stale(timestamp: str) -> None:
    """Захист від повтору перехопленого запиту.

    Paddle рекомендує вузьке вікно, і його SDK за замовчуванням беруть
    пʼять секунд. Ми беремо ширше й робимо це налаштуванням: розбіжність
    годинника сервера — реальний режим відмови, і виглядає він як
    «підпис не збігається», тобто як атака. Ширше вікно розрізняє ці
    два випадки, лишаючись захистом від повтору.
    """
    tolerance = runtime.get_int("paddle_signature_tolerance_s")
    if tolerance <= 0:
        return
    try:
        sent_at = int(timestamp)
    except ValueError as exc:
        raise InvalidWebhook("позначка часу підпису не є числом") from exc
    drift = abs(int(datetime.now(UTC).timestamp()) - sent_at)
    if drift > tolerance:
        raise InvalidWebhook(f"позначка часу застара або з майбутнього ({drift} с)")


# Події Paddle → словник домену. Усе, чого тут немає, домену не
# показується взагалі: краще проігнорувати відоме нам «ні», ніж
# перекласти навмання.
_PURCHASE_EVENTS = {"transaction.completed"}
_FAILED_EVENTS = {"transaction.payment_failed"}
_CANCELED_EVENTS = {"transaction.canceled"}
_REFUND_EVENTS = {"adjustment.created"}

# Події підписки з однозначним перекладом. `subscription.updated` —
# окремо: у нього кілька значень, і розрізняє їх вміст.
_SUBSCRIPTION_EVENTS: dict[str, BillingEventKind] = {
    "subscription.activated": BillingEventKind.SUBSCRIPTION_STARTED,
    "subscription.past_due": BillingEventKind.PAYMENT_FAILED,
    "subscription.canceled": BillingEventKind.SUBSCRIPTION_CANCELLED,
    "subscription.paused": BillingEventKind.SUBSCRIPTION_PAUSED,
    "subscription.resumed": BillingEventKind.SUBSCRIPTION_RESUMED,
}


class UnsupportedEvent(UnhandledEvent):
    """Подія Paddle, яку цей потік не обробляє.

    Маршрут відповідає на неї 200: повторювати доставку немає сенсу,
    бо ми свідомо не слухаємо цю подію, а не не змогли її прочитати.
    """


def _to_domain_event(envelope: dict[str, Any]) -> VerifiedBillingEvent:
    event_type = str(envelope.get("event_type") or "")
    event_id = str(envelope.get("event_id") or "")
    data = envelope.get("data") or {}
    if not event_id or not isinstance(data, dict):
        raise InvalidWebhook("подія без ідентифікатора або без даних")

    occurred_at = _parse_time(envelope.get("occurred_at"))

    if event_type in _REFUND_EVENTS:
        if str(data.get("action") or "") != "refund":
            raise UnsupportedEvent(f"коригування без повернення коштів: {event_type}")
        transaction_ref = str(data.get("transaction_id") or "")
        if not transaction_ref:
            raise InvalidWebhook("повернення без посилання на транзакцію")
        return VerifiedBillingEvent(
            provider=NAME,
            external_event_id=event_id,
            kind=BillingEventKind.ONE_OFF_REFUNDED,
            occurred_at=occurred_at,
            customer_ref=_opt(data.get("customer_id")),
            # Домен знайде покупку за транзакцією: подія про повернення
            # посилається саме на неї.
            payload={"provider_transaction_id": transaction_ref},
        )

    if event_type in _SUBSCRIPTION_EVENTS or event_type == "subscription.updated":
        return _subscription_event(event_type, event_id, data, occurred_at)

    if event_type in _PURCHASE_EVENTS:
        # Оплата ПІДПИСКИ приходить тим самим видом події, що й разова
        # покупка, і відрізняє їх посилання на підписку. Мапити її як
        # разову означало б народжувати фальшиву покупку з кредитами на
        # кожне списання; стан підписки ведуть події `subscription.*`.
        if str(data.get("subscription_id") or ""):
            raise UnsupportedEvent(
                "оплата підписки: стан ведуть події subscription.*"
            )
        totals = ((data.get("details") or {}).get("totals")) or {}
        currency = str(data.get("currency_code") or totals.get("currency_code") or "")
        return VerifiedBillingEvent(
            provider=NAME,
            external_event_id=event_id,
            kind=BillingEventKind.ONE_OFF_PURCHASED,
            occurred_at=occurred_at,
            customer_ref=_opt(data.get("customer_id")),
            quantity=1,
            currency=currency or None,
            amount_minor=_minor(totals.get("total")),
            payload={
                # Наш ідентифікатор кореляції — саме він, а не аудит.
                # Аудит домен візьме зі свого запису покупки.
                "purchase_ref": _purchase_ref(data),
                "provider_transaction_id": str(data.get("id") or ""),
            },
        )

    if event_type in _FAILED_EVENTS:
        return VerifiedBillingEvent(
            provider=NAME,
            external_event_id=event_id,
            kind=BillingEventKind.PAYMENT_FAILED,
            occurred_at=occurred_at,
            customer_ref=_opt(data.get("customer_id")),
            payload={
                # Кореляція потрібна й тут: невдала оплата разової
                # покупки не має шукати підписку, якої не існує, а
                # відрізняє ці два світи саме наш ідентифікатор.
                "purchase_ref": _purchase_ref(data),
                "provider_transaction_id": str(data.get("id") or ""),
            },
        )

    if event_type in _CANCELED_EVENTS:
        # Закрита каса не є подією домену: покупка просто лишається
        # PENDING, і людина може спробувати ще раз.
        raise UnsupportedEvent(f"каса закрита без оплати: {event_type}")

    raise UnsupportedEvent(f"подія не обробляється цим потоком: {event_type}")


def _subscription_event(
    event_type: str,
    event_id: str,
    data: dict[str, Any],
    occurred_at: datetime,
) -> VerifiedBillingEvent:
    """Подія підписки Paddle → словник домену.

    Ідентичність — `data.id` (`sub_…`); тариф — прайс першої позиції,
    домен розвʼяже його через PlanPrice; організація — наш власний ключ
    у `custom_data`, який Paddle скопіював із транзакції каси. Період —
    `current_billing_period`: саме його рух і є поновленням.
    """
    subscription_ref = str(data.get("id") or "")
    if not subscription_ref:
        raise InvalidWebhook("подія підписки без ідентифікатора підписки")

    if event_type == "subscription.updated":
        # У «оновилася» кілька значень. Заплановане скасування впізнається
        # за scheduled_change і має тривати, поки зміна не сталася; решта
        # оновлень активної підписки — поновлення (рух періоду застосує
        # домен, нерухомий період нічого не змінить). Стани поза цими
        # двома несуть власні події, і их ми і слухаємо.
        scheduled = data.get("scheduled_change") or {}
        if str(scheduled.get("action") or "") == "cancel":
            kind = BillingEventKind.CANCELLATION_SCHEDULED
        elif str(data.get("status") or "") in {"active", "trialing"}:
            kind = BillingEventKind.SUBSCRIPTION_RENEWED
        else:
            raise UnsupportedEvent(
                f"оновлення підписки в стані {data.get('status')!r} "
                "не несе окремого переходу"
            )
    else:
        kind = _SUBSCRIPTION_EVENTS[event_type]

    period = data.get("current_billing_period") or {}
    items = data.get("items") or []
    first_price = (items[0].get("price") or {}) if items else {}

    return VerifiedBillingEvent(
        provider=NAME,
        external_event_id=event_id,
        kind=kind,
        occurred_at=occurred_at,
        subscription_ref=subscription_ref,
        customer_ref=_opt(data.get("customer_id")),
        price_ref=_opt(str(first_price.get("id") or "")),
        organization_id=_organization_ref(data),
        with_trial=str(data.get("status") or "") == "trialing",
        period_start=_opt_time(period.get("starts_at")),
        period_end=_opt_time(period.get("ends_at")),
        cancel_at=_opt_time(
            (data.get("scheduled_change") or {}).get("effective_at")
        ),
    )


def _organization_ref(data: dict[str, Any]) -> uuid.UUID | None:
    """Наша організація з довільних даних, якщо каса її туди поклала."""
    custom = data.get("custom_data")
    if not isinstance(custom, dict):
        return None
    raw = str(custom.get(CUSTOM_ORGANIZATION_KEY) or "")
    if not raw:
        return None
    try:
        return uuid.UUID(raw)
    except ValueError:
        return None


def _opt_time(value: Any) -> datetime | None:
    """Час, якого може не бути. Кривий формат — не подія, а сміття."""
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _purchase_ref(data: dict[str, Any]) -> str:
    """Наш ідентифікатор покупки з довільних даних транзакції.

    Порожньо — теж відповідь: транзакція, створена не нашою касою (у
    кабінеті Paddle, наприклад), нашого рядка не називає, і вигадувати
    його тут нема з чого.
    """
    custom = data.get("custom_data")
    if not isinstance(custom, dict):
        return ""
    return str(custom.get(CUSTOM_PURCHASE_KEY) or "")


def _parse_time(value: Any) -> datetime:
    """Час ПРОВАЙДЕРА. Саме він вирішує, що новіше."""
    if not isinstance(value, str) or not value:
        raise InvalidWebhook("подія без часу настання")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidWebhook(f"час події не розбирається: {value}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _minor(value: Any) -> int | None:
    """Суми Paddle приходять рядком у мінорних одиницях."""
    if value is None:
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _opt(value: Any) -> str | None:
    text = str(value or "")
    return text or None


def _safe_reason(response: Any) -> str:
    """Код і пояснення від Paddle, без тіла відповіді.

    Ширше за `_safe_error`, і місце для нього одне — службові шляхи, де
    докладність економить години. Тіло не йде назовні ніде: у ньому наші
    ж дані й ідентифікатор запиту.
    """
    code, detail = "", ""
    try:
        error = response.json().get("error") or {}
        code = str(error.get("code") or "")
        detail = str(error.get("detail") or "")
    except Exception:  # noqa: BLE001 — тіло помилки може бути не JSON
        pass
    if code and detail:
        return f"HTTP {response.status_code}, {code}: {detail}"
    return f"HTTP {response.status_code}{f', {code}' if code else ''}"


def _safe_error(response: Any) -> str:
    """Помилка Paddle без тіла: у ньому може бути що завгодно.

    Назовні йдуть код і код помилки Paddle, якщо він є, — цього досить,
    щоб зрозуміти причину, і замало, щоб винести назовні зайве.
    """
    code = ""
    try:
        body = response.json()
        code = str(((body.get("error") or {}).get("code")) or "")
    except Exception:  # noqa: BLE001 — тіло помилки може бути не JSON
        code = ""
    suffix = f", код {code}" if code else ""
    return f"Paddle відповів HTTP {response.status_code}{suffix}"


__all__ = [
    "CUSTOM_ORGANIZATION_KEY",
    "CUSTOM_PURCHASE_KEY",
    "NAME",
    "PaddleNotConfigured",
    "PaddleProvider",
    "UnsupportedEvent",
]
