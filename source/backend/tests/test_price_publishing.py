"""Публікація прайсів: контракт, адаптер Paddle без мережі, фейк.

Paddle тут — `httpx.MockTransport`: перевіряється, ЩО ми надсилаємо
(адреса, метод, тіло) і як читаємо відповідь. Жодного справжнього
запиту: ключ вигаданий, оточення — пісочниця.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.application import catalogue_publishing as publishing
from app.billing.providers.fake import FakePricePublisher
from app.billing.providers.paddle_prices import TAX_CATEGORY, PaddlePricePublisher
from app.billing.publishing import PriceSpec, PublishFailed
from app.core import runtime_config as runtime
from app.core.config import settings

SANDBOX_KEY = "pdl_sdbx_apikey_0123456789"
SINGLE = PriceSpec(
    code="single", name="Single check", amount_minor=1200, currency="USD",
    interval=None, description="Crawldy single check · single",
)
MONTHLY = PriceSpec(
    code="monthly_month", name="Monthly", amount_minor=14999, currency="USD",
    interval="month", description="Crawldy plan · monthly · month",
)


@pytest.fixture(autouse=True)
def _sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "paddle_env", "sandbox")
    monkeypatch.setattr(settings, "paddle_api_key", SANDBOX_KEY)
    runtime.reset_cache()


def _price(price_id: str, *, product: str, amount: str, currency: str = "USD",
           interval: str | None = None, status: str = "active") -> dict[str, Any]:
    return {
        "id": price_id, "product_id": product, "status": status,
        "unit_price": {"amount": amount, "currency_code": currency},
        "billing_cycle": {"interval": interval, "frequency": 1} if interval else None,
    }


class PaddleStub:
    """Пісочниця в памʼяті: зберігає запити, відповідає за сценарієм."""

    def __init__(self, *, prices: dict[str, dict[str, Any]] | None = None,
                 products: set[str] | None = None, status: int | None = None) -> None:
        self.prices = prices or {}
        self.products = products or set()
        self.status = status
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else None
        path = request.url.path
        self.calls.append((request.method, path, body))
        assert request.headers["authorization"] == f"Bearer {SANDBOX_KEY}"
        assert request.url.host == "sandbox-api.paddle.com"
        if self.status is not None:
            return httpx.Response(self.status, json={"error": {
                "type": "request_error", "code": "forbidden",
                "detail": "not authorized to create|read product",
            }})
        if request.method == "GET" and path.startswith("/prices/"):
            found = self.prices.get(path.removeprefix("/prices/"))
            return httpx.Response(200, json={"data": found}) if found else httpx.Response(404)
        if request.method == "GET" and path.startswith("/products/"):
            pid = path.removeprefix("/products/")
            return (httpx.Response(200, json={"data": {"id": pid}}) if pid in self.products
                    else httpx.Response(404))
        if request.method == "POST" and path == "/products":
            self.products.add("pro_new")
            return httpx.Response(201, json={"data": {"id": "pro_new", **body}})
        if request.method == "POST" and path == "/prices":
            cycle = body.get("billing_cycle")
            created = _price("pri_new", product=body["product_id"],
                             amount=body["unit_price"]["amount"],
                             currency=body["unit_price"]["currency_code"],
                             interval=cycle["interval"] if cycle else None)
            self.prices["pri_new"] = created
            return httpx.Response(201, json={"data": created})
        if request.method == "PATCH" and path.startswith("/prices/"):
            current = dict(self.prices[path.removeprefix("/prices/")])
            current["unit_price"] = body["unit_price"]
            return httpx.Response(200, json={"data": current})
        return httpx.Response(500, json={"error": {"code": "unexpected"}})


def _publisher(stub: PaddleStub) -> PaddlePricePublisher:
    return PaddlePricePublisher(transport=httpx.MockTransport(stub.handler))


# ── перша публікація ───────────────────────────────────────────────────


async def test_first_publication_creates_product_and_price() -> None:
    stub = PaddleStub()
    published = await _publisher(stub).publish(SINGLE, price_ref=None, product_ref=None)

    assert [(m, p) for m, p, _ in stub.calls] == [("POST", "/products"), ("POST", "/prices")]
    product_body = stub.calls[0][2]
    assert product_body == {"name": "Single check", "tax_category": TAX_CATEGORY,
                            "description": SINGLE.description}
    price_body = stub.calls[1][2]
    assert price_body["unit_price"] == {"amount": "1200", "currency_code": "USD"}
    assert price_body["product_id"] == "pro_new"
    assert price_body["quantity"] == {"minimum": 1, "maximum": 1}, "одна позиція на касу"
    assert "billing_cycle" not in price_body, "разова покупка — без періоду"
    assert published.price_ref == "pri_new"
    assert published.product_ref == "pro_new"
    assert published.amount_minor == 1200
    assert published.currency == "USD"
    assert published.interval is None


async def test_subscription_price_carries_the_billing_cycle() -> None:
    stub = PaddleStub()
    published = await _publisher(stub).publish(MONTHLY, price_ref=None, product_ref=None)
    body = stub.calls[-1][2]
    assert body["billing_cycle"] == {"interval": "month", "frequency": 1}
    assert published.interval == "month"


# ── зміна ціни ─────────────────────────────────────────────────────────


async def test_a_known_price_is_updated_in_place() -> None:
    """9.99 → 12: той самий `pri_`, нова сума. Продукт не створюється."""
    stub = PaddleStub(prices={"pri_old": _price("pri_old", product="pro_old", amount="999")},
                      products={"pro_old"})
    changed = PriceSpec(**{**SINGLE.__dict__, "amount_minor": 1200})
    published = await _publisher(stub).publish(changed, price_ref="pri_old", product_ref="pro_old")

    assert [(m, p) for m, p, _ in stub.calls] == [("GET", "/prices/pri_old"),
                                                  ("PATCH", "/prices/pri_old")]
    assert stub.calls[1][2]["unit_price"] == {"amount": "1200", "currency_code": "USD"}
    assert published.price_ref == "pri_old", "ідентифікатор лишається — покупки не старіють"
    assert published.amount_minor == 1200


async def test_a_currency_change_needs_a_new_price() -> None:
    """Валюту чинного прайса не редагуємо: він може обслуговувати підписки,
    відкриті в старій валюті. Новий прайс на тому самому продукті."""
    stub = PaddleStub(prices={"pri_old": _price("pri_old", product="pro_old", amount="999")},
                      products={"pro_old"})
    euro = PriceSpec(**{**SINGLE.__dict__, "currency": "EUR"})
    published = await _publisher(stub).publish(euro, price_ref="pri_old", product_ref="pro_old")
    assert [(m, p) for m, p, _ in stub.calls] == [
        ("GET", "/prices/pri_old"), ("GET", "/products/pro_old"), ("POST", "/prices"),
    ]
    assert stub.calls[-1][2]["unit_price"] == {"amount": "1200", "currency_code": "EUR"}
    assert published.price_ref == "pri_new"
    assert published.currency == "EUR"


# ── інше оточення, інший період ────────────────────────────────────────


async def test_a_price_unknown_here_is_recreated_on_the_known_product() -> None:
    """Прайс пісочниці в бойовому оточенні: 404 → новий прайс. Продукт, який
    оточення знає, не дублюється."""
    stub = PaddleStub(products={"pro_known"})
    published = await _publisher(stub).publish(
        SINGLE, price_ref="pri_from_other_env", product_ref="pro_known"
    )
    assert [(m, p) for m, p, _ in stub.calls] == [
        ("GET", "/prices/pri_from_other_env"), ("GET", "/products/pro_known"),
        ("POST", "/prices"),
    ]
    assert published.price_ref == "pri_new"
    assert published.product_ref == "pro_known"


async def test_a_price_and_product_unknown_here_are_both_recreated() -> None:
    stub = PaddleStub()
    published = await _publisher(stub).publish(
        SINGLE, price_ref="pri_gone", product_ref="pro_gone"
    )
    assert [(m, p) for m, p, _ in stub.calls] == [
        ("GET", "/prices/pri_gone"), ("GET", "/products/pro_gone"),
        ("POST", "/products"), ("POST", "/prices"),
    ]
    assert published.product_ref == "pro_new"


async def test_a_changed_billing_cycle_needs_a_new_price() -> None:
    """Період прайса Paddle не редагується — місячний → річний означає новий
    прайс на тому самому продукті."""
    stub = PaddleStub(
        prices={"pri_m": _price("pri_m", product="pro_plan", amount="14999", interval="month")},
        products={"pro_plan"},
    )
    yearly = PriceSpec(**{**MONTHLY.__dict__, "interval": "year"})
    published = await _publisher(stub).publish(yearly, price_ref="pri_m", product_ref="pro_plan")
    assert [(m, p) for m, p, _ in stub.calls] == [
        ("GET", "/prices/pri_m"), ("GET", "/products/pro_plan"), ("POST", "/prices"),
    ]
    assert published.interval == "year"


async def test_a_foreign_reference_is_ignored_not_queried() -> None:
    """`local_single` від фейка — не прайс Paddle: жодного GET на нього."""
    stub = PaddleStub()
    await _publisher(stub).publish(SINGLE, price_ref="local_single", product_ref="fake_product_x")
    assert [(m, p) for m, p, _ in stub.calls] == [("POST", "/products"), ("POST", "/prices")]


# ── відмови ────────────────────────────────────────────────────────────


async def test_a_key_without_write_permission_says_what_to_turn_on() -> None:
    """Підтверджений випадок: ключ читає (перевірка зʼєднання зелена), але не
    пише, і перша ж публікація падає. «forbidden» саме по собі не каже, що
    робити, тож деталь несе і слова Paddle, і назви потрібних прав."""
    stub = PaddleStub(status=403)
    with pytest.raises(PublishFailed) as caught:
        await _publisher(stub).publish(SINGLE, price_ref=None, product_ref=None)
    assert caught.value.outcome == "forbidden", "не той самий стан, що невірний ключ"
    assert "403" in caught.value.detail
    assert "not authorized" in caught.value.detail, "причина словами Paddle"
    assert "product.write" in caught.value.detail and "price.write" in caught.value.detail, (
        "назви прав такі, як їх пише Paddle — через крапку"
    )
    assert SANDBOX_KEY not in str(caught.value)


async def test_a_rejected_key_is_a_different_failure() -> None:
    stub = PaddleStub(status=401)
    with pytest.raises(PublishFailed) as caught:
        await _publisher(stub).publish(SINGLE, price_ref=None, product_ref=None)
    assert caught.value.outcome == "unauthorized"
    assert "product.write" not in caught.value.detail, "тут проблема не в правах"
    assert SANDBOX_KEY not in str(caught.value)


async def test_network_failure_is_named_without_the_key() -> None:
    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("no route")

    publisher = PaddlePricePublisher(transport=httpx.MockTransport(boom))
    with pytest.raises(PublishFailed) as caught:
        await publisher.publish(SINGLE, price_ref=None, product_ref=None)
    assert caught.value.outcome == "network_error"
    assert SANDBOX_KEY not in str(caught.value)


async def test_missing_key_never_reaches_the_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "paddle_api_key", None)
    runtime.reset_cache()
    stub = PaddleStub()
    with pytest.raises(PublishFailed) as caught:
        await _publisher(stub).publish(SINGLE, price_ref=None, product_ref=None)
    assert caught.value.outcome == "not_configured"
    assert stub.calls == []


async def test_read_reports_what_the_provider_has() -> None:
    stub = PaddleStub(prices={"pri_x": _price("pri_x", product="pro_x", amount="1000")})
    publisher = _publisher(stub)
    found = await publisher.read("pri_x")
    assert found is not None and found.amount_minor == 1000 and found.status == "active"
    assert await publisher.read("pri_absent") is None
    assert await publisher.read("local_single") is None, "чужий ідентифікатор — не запит"


# ── фейк і збирання описів ──────────────────────────────────────────────


async def test_fake_publisher_keeps_a_stable_reference() -> None:
    fake = FakePricePublisher()
    first = await fake.publish(SINGLE, price_ref=None, product_ref=None)
    assert first.price_ref == "fake_single"
    again = await fake.publish(
        PriceSpec(**{**SINGLE.__dict__, "amount_minor": 1500}),
        price_ref=first.price_ref, product_ref=first.product_ref,
    )
    assert again.price_ref == "fake_single" and again.amount_minor == 1500
    assert (await fake.read("fake_single")) == again
    assert await fake.read("pri_paddle") is None
    fake.down = True
    with pytest.raises(PublishFailed):
        await fake.publish(SINGLE, price_ref=None, product_ref=None)


def test_offer_spec_names_the_product_in_english_for_the_receipt() -> None:
    spec = publishing.offer_spec(
        code="pack", offer_type="pack", display_name="Пакет",
        display_name_i18n={"uk": "Пакет перевірок", "en": "Check pack"},
        amount_minor=4999, currency="usd",
    )
    assert spec.name == "Check pack"
    assert spec.currency == "USD"
    assert spec.interval is None
    plain = publishing.offer_spec(
        code="pack", offer_type="pack", display_name="Пакет", display_name_i18n={},
        amount_minor=4999, currency="USD",
    )
    assert plain.name == "Crawldy Audit Pack", (
        "внутрішня українська мітка не їде в чужу квитанцію"
    )
    odd = publishing.offer_spec(
        code="promo", offer_type="bundle", display_name="Набір", display_name_i18n={},
        amount_minor=100, currency="USD",
    )
    assert odd.name == "Набір", "для невідомого виду лишається те, що є"


def test_plan_spec_carries_the_interval_in_code_and_cycle() -> None:
    spec = publishing.plan_spec(
        code="monthly", name="Monthly", name_i18n=None, interval="month",
        amount_minor=14999, currency="USD",
    )
    assert spec.code == "monthly_month" and spec.interval == "month"
    assert spec.name == "Crawldy Monthly Plan"
    named = publishing.plan_spec(
        code="monthly", name="Місячний план", name_i18n={"en": "Crawldy Pro"},
        interval="month", amount_minor=14999, currency="USD",
    )
    assert named.name == "Crawldy Pro", "англійська назва каталогу головніша"


def test_remembered_refs_belong_to_the_active_provider_only() -> None:
    # Чинна привʼязка чужого провайдера для цієї каси нічого не означає.
    assert publishing.remembered(
        "paddle", refs=None, row_provider="fake",
        price_ref="fake_single", product_ref="fake_product_single",
    ) == (None, None)
    # Записи, старші за мапу, мають лише чинну привʼязку.
    assert publishing.remembered(
        "paddle", refs=None, row_provider="paddle", price_ref="pri_x", product_ref="pro_x"
    ) == ("pri_x", "pro_x")
    assert publishing.remembered(
        "paddle", refs={}, row_provider="paddle", price_ref="", product_ref=None
    ) == (None, None)


def test_the_map_remembers_every_provider_the_record_was_published_to() -> None:
    """Перемикання каси туди й назад не має плодити продуктів: те, що запис
    мав у попереднього провайдера, лишається знайомим."""
    refs = {
        "paddle": {"price": "pri_x", "product": "pro_x"},
        "fake": {"price": "fake_pack", "product": "fake_product_pack"},
    }
    # Каса зараз фейкова, тобто чинна привʼязка теж фейкова…
    assert publishing.remembered(
        "fake", refs=refs, row_provider="fake",
        price_ref="fake_pack", product_ref="fake_product_pack",
    ) == ("fake_pack", "fake_product_pack")
    # …і повернення на Paddle бере СТАРИЙ прайс, а не створює новий.
    assert publishing.remembered(
        "paddle", refs=refs, row_provider="fake",
        price_ref="fake_pack", product_ref="fake_product_pack",
    ) == ("pri_x", "pro_x")
    # Провайдер, у якого запис не публікувався, лишається невідомим.
    assert publishing.remembered("stripe", refs=refs) == (None, None)


def test_publishing_writes_into_the_map_without_forgetting_the_others() -> None:
    published = publishing.PublishedPrice(
        provider="paddle", product_ref="pro_new", price_ref="pri_new",
        amount_minor=1200, currency="USD", interval=None, status="active",
    )
    before = {"fake": {"price": "fake_pack", "product": "fake_product_pack"}}
    after = publishing.with_ref(before, published)
    assert after["paddle"] == {"price": "pri_new", "product": "pro_new"}
    assert after["fake"] == before["fake"], "чужий рядок не переписується"
    assert before == {"fake": {"price": "fake_pack", "product": "fake_product_pack"}}, (
        "початкова мапа не змінюється на місці"
    )
