"""Фейковий провайдер: повноцінний адаптер, а не купка monkeypatch.

Реалізує той самий контракт, який у P4.7b реалізує Paddle, — тож тести
application-шару, написані проти нього, перевіряють рівно той шлях, яким
підуть справжні події. Плюс сценарний бік: методи `activate`, `renew`,
`fail_payment` тощо **емітують** нормалізовані події — так, як їх
емітував би провайдер, — а тест сам вирішує, у якому порядку й скільки
разів їх доставити.

Саме тому доставка тут не автоматична: подія повертається викликачеві.
Дублікати — доставити двічі. Не по порядку — притримати й доставити
пізніше. Загублена — не доставити взагалі. Це не зручність тестів, а
модель реального світу вебхуків.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.billing.enums import BillingEventKind
from app.billing.providers.base import (
    CheckoutRequest,
    CheckoutSession,
    InvalidWebhook,
    ProviderRef,
    ProviderUnavailable,
    Settlement,
    SettlementReport,
    VerifiedBillingEvent,
)
from app.billing.publishing import PriceSpec, PublishedPrice, PublishFailed

NAME = "fake"

_K = BillingEventKind


@dataclass(slots=True)
class _FakeSubscription:
    """Що фейк памʼятає про підписку, — рівно стільки, щоб емітити події."""

    ref: str
    customer_ref: str
    organization_id: uuid.UUID
    price_ref: str
    period_start: datetime
    period_end: datetime
    with_trial: bool = False


@dataclass
class FakeBillingProvider:
    """Провайдер, яким керує тест.

    `down = True` — провайдер лежить: усі виклики API кидають
    `ProviderUnavailable`. Вебхуки при цьому працюють — так і в житті:
    недоступність API не зупиняє доставки подій, які вже в черзі.
    """

    down: bool = False
    period: timedelta = timedelta(days=30)
    # Запити на касу, які зробив домен. Тест звіряє, що туди пішов
    # ідентифікатор покупки й не пішло нічого зайвого.
    checkouts: list[CheckoutRequest] = field(default_factory=list)
    _customers: dict[str, uuid.UUID] = field(default_factory=dict)
    _subscriptions: dict[str, _FakeSubscription] = field(default_factory=dict)
    # Що фейк знає про оплату кожної каси. Відкрита каса — не оплачена,
    # поки сценарій не скаже інакше; чужий ідентифікатор — UNKNOWN, як у
    # справжнього провайдера на транзакцію, якої він не бачив.
    _settlements: dict[str, Settlement] = field(default_factory=dict)
    _counter: int = 0

    # ── контракт BillingProvider ───────────────────────────────────────────

    @property
    def name(self) -> str:
        return NAME

    async def create_customer(
        self, *, organization_id: uuid.UUID, email: str
    ) -> ProviderRef:
        self._refuse_if_down()
        ref = f"cus_{self._next()}"
        self._customers[ref] = organization_id
        return ProviderRef(provider=NAME, external_id=ref)

    async def create_checkout(self, request: CheckoutRequest) -> CheckoutSession:
        self._refuse_if_down()
        ref = f"chk_{self._next()}"
        # Запит зберігається: тести звіряють, що домен передав саме
        # ідентифікатор покупки й нічого зайвого.
        self.checkouts.append(request)
        self._settlements[ref] = Settlement.UNPAID
        return CheckoutSession(
            ref=ProviderRef(provider=NAME, external_id=ref),
            url=f"https://fake.checkout.invalid/{ref}?purchase={request.purchase_id}",
        )

    async def settlement_of(self, *, transaction_ref: str) -> Settlement:
        self._refuse_if_down()
        return self._settlements.get(transaction_ref, Settlement.UNKNOWN)

    async def settlement_report(self, *, transaction_ref: str) -> SettlementReport:
        """Стан із памʼяті сценарію. Грошей фейк не називає: їх не було."""
        self._refuse_if_down()
        return SettlementReport(
            settlement=self._settlements.get(transaction_ref, Settlement.UNKNOWN)
        )

    def abandon(self, transaction_ref: str) -> None:
        """Сценарій: людина відкрила касу й пішла, не заплативши.

        Симетрично до `settle`. Без цього фейк на незнайому касу відповідає
        «не знаю», і сценарій «прибрати неоплачені» перевірити нічим:
        мовчання провайдера прибирання свідомо не запускає.
        """
        self._settlements[transaction_ref] = Settlement.UNPAID

    def settle(self, transaction_ref: str) -> None:
        """Сценарій: покупець заплатив у касі, подія ще не доставлена.

        Подія навмисно НЕ емітується: це рівно стан «гроші пішли, вебхук
        у дорозі», і тест сам вирішує, чи доставити його потім.
        """
        self._settlements[transaction_ref] = Settlement.PAID

    async def create_portal_session(self, *, customer_ref: str) -> str:
        return f"https://fake.portal/{customer_ref}"

    def verify_webhook(
        self, *, headers: dict[str, str], body: bytes
    ) -> VerifiedBillingEvent:
        """Фейкова «перевірка підпису»: заголовок мусить бути на місці.

        Не безпека, а перевірка контракту: адаптер, який не відхиляє
        непідписане, тестами не відрізнити від адаптера без перевірки.
        """
        if headers.get("x-fake-signature") != "valid":
            raise InvalidWebhook("підпис відсутній або невірний")
        # Сценарні методи емітять події обʼєктами й тіла не мають. Але
        # маршрут вебхука приймає саме тіло, і без розбору його неможливо
        # перевірити тим самим шляхом, яким піде справжній провайдер:
        # тест бив би по application-шару, обходячи HTTP, підпис і
        # перекладання відмов на коди відповіді.
        try:
            raw = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidWebhook("тіло не є JSON") from exc
        if not isinstance(raw, dict):
            raise InvalidWebhook("тіло не є обʼєктом")
        try:
            kind = BillingEventKind(str(raw["kind"]))
            occurred_at = datetime.fromisoformat(str(raw["occurred_at"]))
        except (KeyError, ValueError) as exc:
            raise InvalidWebhook("подія без виду або без часу") from exc
        organization_id = raw.get("organization_id")

        def _time(key: str) -> datetime | None:
            value = raw.get(key)
            if not value:
                return None
            try:
                return datetime.fromisoformat(str(value))
            except ValueError:
                return None

        return VerifiedBillingEvent(
            provider=NAME,
            external_event_id=str(raw.get("external_event_id") or ""),
            kind=kind,
            occurred_at=occurred_at,
            # Поля підписки їдуть тілом так само, як їх кладе сценарний
            # бік: тест, що доставляє подію через HTTP, перевіряє той
            # самий шлях, яким піде справжній провайдер.
            subscription_ref=str(raw.get("subscription_ref") or "") or None,
            customer_ref=str(raw.get("customer_ref") or "") or None,
            price_ref=str(raw.get("price_ref") or "") or None,
            organization_id=uuid.UUID(str(organization_id)) if organization_id else None,
            with_trial=bool(raw.get("with_trial") or False),
            period_start=_time("period_start"),
            period_end=_time("period_end"),
            trial_end=_time("trial_end"),
            cancel_at=_time("cancel_at"),
            quantity=raw.get("quantity"),
            currency=raw.get("currency"),
            amount_minor=raw.get("amount_minor"),
            payload=dict(raw.get("payload") or {}),
        )

    # ── сценарій: що робить клієнт і банк ──────────────────────────────────

    def activate(
        self,
        *,
        organization_id: uuid.UUID,
        price_ref: str,
        with_trial: bool = False,
        customer_ref: str | None = None,
        at: datetime | None = None,
    ) -> VerifiedBillingEvent:
        """Оплата пройшла (або почався trial): підписка існує."""
        moment = at or self._now()
        customer = customer_ref or f"cus_{self._next()}"
        self._customers.setdefault(customer, organization_id)
        sub = _FakeSubscription(
            ref=f"sub_{self._next()}",
            customer_ref=customer,
            organization_id=organization_id,
            price_ref=price_ref,
            period_start=moment,
            period_end=moment + self.period,
            with_trial=with_trial,
        )
        self._subscriptions[sub.ref] = sub
        return self._event(
            _K.SUBSCRIPTION_STARTED,
            sub,
            occurred_at=moment,
            with_trial=with_trial,
            trial_end=moment + self.period if with_trial else None,
        )

    def renew(self, subscription_ref: str, *, at: datetime | None = None) -> VerifiedBillingEvent:
        sub = self._subscriptions[subscription_ref]
        moment = at or self._now()
        sub.period_start = moment
        sub.period_end = moment + self.period
        return self._event(_K.SUBSCRIPTION_RENEWED, sub, occurred_at=moment)

    def fail_payment(
        self, subscription_ref: str, *, at: datetime | None = None
    ) -> VerifiedBillingEvent:
        sub = self._subscriptions[subscription_ref]
        return self._event(_K.PAYMENT_FAILED, sub, occurred_at=at or self._now())

    def recover_payment(
        self, subscription_ref: str, *, at: datetime | None = None
    ) -> VerifiedBillingEvent:
        sub = self._subscriptions[subscription_ref]
        moment = at or self._now()
        sub.period_start = moment
        sub.period_end = moment + self.period
        return self._event(_K.PAYMENT_RECOVERED, sub, occurred_at=moment)

    def schedule_cancellation(
        self, subscription_ref: str, *, at: datetime | None = None
    ) -> VerifiedBillingEvent:
        sub = self._subscriptions[subscription_ref]
        return self._event(
            _K.CANCELLATION_SCHEDULED,
            sub,
            occurred_at=at or self._now(),
            cancel_at=sub.period_end,
        )

    def cancel(
        self, subscription_ref: str, *, at: datetime | None = None
    ) -> VerifiedBillingEvent:
        sub = self._subscriptions[subscription_ref]
        return self._event(_K.SUBSCRIPTION_CANCELLED, sub, occurred_at=at or self._now())

    def change_plan(
        self, subscription_ref: str, *, price_ref: str, at: datetime | None = None
    ) -> VerifiedBillingEvent:
        sub = self._subscriptions[subscription_ref]
        sub.price_ref = price_ref
        return self._event(_K.PLAN_CHANGED, sub, occurred_at=at or self._now())

    # ── допоміжне ──────────────────────────────────────────────────────────

    # ── сценарій: разова покупка ───────────────────────────────────────────

    def purchase_one_off(
        self,
        *,
        organization_id: uuid.UUID,
        quantity: int = 1,
        currency: str = "USD",
        amount_minor: int = 1900,
        external_id: str | None = None,
        at: datetime | None = None,
    ) -> VerifiedBillingEvent:
        """Клієнт купив разові аудити.

        `external_id` можна задати, щоб відтворити повторну доставку тієї
        самої події: ідемпотентність — властивість, яку треба вміти
        перевірити, а не припустити.
        """
        self._refuse_if_down()
        ident = external_id or f"pur_{self._next()}"
        return VerifiedBillingEvent(
            provider=NAME,
            external_event_id=ident,
            kind=BillingEventKind.ONE_OFF_PURCHASED,
            occurred_at=at or self._now(),
            organization_id=organization_id,
            quantity=quantity,
            currency=currency,
            amount_minor=amount_minor,
            payload={"fake": True, "kind": BillingEventKind.ONE_OFF_PURCHASED.value},
        )

    def refund_one_off(
        self, purchased: VerifiedBillingEvent, *, at: datetime | None = None
    ) -> VerifiedBillingEvent:
        """Кошти за ту покупку повернуто.

        Посилається на подію покупки її ж ідентифікатором: домен знайде
        покупку тією самою парою «провайдер + зовнішній ідентифікатор»,
        якою її й записував.
        """
        self._refuse_if_down()
        return VerifiedBillingEvent(
            provider=NAME,
            external_event_id=f"ref_{self._next()}",
            kind=BillingEventKind.ONE_OFF_REFUNDED,
            occurred_at=at or self._now(),
            organization_id=purchased.organization_id,
            payload={
                "fake": True,
                "kind": BillingEventKind.ONE_OFF_REFUNDED.value,
                "purchase_external_id": purchased.external_event_id,
            },
        )

    def _event(
        self,
        kind: BillingEventKind,
        sub: _FakeSubscription,
        *,
        occurred_at: datetime,
        with_trial: bool = False,
        trial_end: datetime | None = None,
        cancel_at: datetime | None = None,
    ) -> VerifiedBillingEvent:
        return VerifiedBillingEvent(
            provider=NAME,
            external_event_id=f"evt_{self._next()}",
            kind=kind,
            occurred_at=occurred_at,
            subscription_ref=sub.ref,
            customer_ref=sub.customer_ref,
            price_ref=sub.price_ref,
            organization_id=sub.organization_id,
            with_trial=with_trial,
            period_start=sub.period_start,
            period_end=sub.period_end,
            trial_end=trial_end,
            cancel_at=cancel_at,
            payload={"fake": True, "kind": kind.value},
        )

    def _refuse_if_down(self) -> None:
        if self.down:
            raise ProviderUnavailable("фейковий провайдер вимкнено сценарієм")

    def _next(self) -> int:
        self._counter += 1
        return self._counter

    @staticmethod
    def _now() -> datetime:
        return datetime.now(UTC)


class FakePricePublisher:
    """Публікація прайсів у фейкового провайдера: без мережі, з памʼяттю.

    Ідентифікатор стабільний, як у Paddle: наявний `fake_…` лишається,
    новий карбується з коду продукту. Сценарій `down` дає збій публікації —
    рівно те, що адмінка мусить показати, а не проковтнути.
    """

    name = NAME

    def __init__(self) -> None:
        self.published: dict[str, PublishedPrice] = {}
        self.down = False

    async def publish(
        self, spec: PriceSpec, *, price_ref: str | None, product_ref: str | None
    ) -> PublishedPrice:
        if self.down:
            raise PublishFailed("network_error", "фейковий провайдер вимкнено сценарієм")
        ref = price_ref if price_ref and price_ref.startswith("fake_") else f"fake_{spec.code}"
        product = (
            product_ref if product_ref and product_ref.startswith("fake_product_")
            else f"fake_product_{spec.code}"
        )
        published = PublishedPrice(
            provider=NAME, product_ref=product, price_ref=ref,
            amount_minor=spec.amount_minor, currency=spec.currency,
            interval=spec.interval, status="active",
        )
        self.published[ref] = published
        return published

    async def read(self, price_ref: str) -> PublishedPrice | None:
        if self.down:
            raise PublishFailed("network_error", "фейковий провайдер вимкнено сценарієм")
        return self.published.get(price_ref)


__all__ = ["NAME", "FakeBillingProvider", "FakePricePublisher"]
