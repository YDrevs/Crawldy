"""Публікація каталогу через кабінет: прайс у провайдера пише сервер.

Закони:

* збереження ціни публікує прайс у ЧИННОГО провайдера й записує його
  ідентифікатор; що б не стояло в тілі запиту — сервер це ігнорує;
* зміна суми оновлює той самий прайс, а не створює новий;
* відмова провайдера зупиняє збереження (502), стара ціна лишається;
* зміна провайдера чи ключа перепубліковує весь каталог; збій при цьому
  не відкочує налаштувань, але й не переписує записів, що не
  опублікувались, — кабінет бачить, що саме не вдалося;
* гість купує «разову перевірку» каталогу — окремої ціни для нього немає.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.application import purchases as purchases_app
from app.billing import registry
from app.billing.publishing import PriceSpec, PublishedPrice, PublishFailed
from app.core import runtime_config as runtime
from app.identity.enums import PlatformRole
from app.models.billing import Plan, PlanPrice
from app.models.commerce import CommercialOffer
from app.models.identity import User
from tests.integration.conftest import register

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def staff(client, db_session):
    body = (await register(client, f"pub-staff-{uuid.uuid4().hex[:8]}@example.com")).json()
    await db_session.execute(
        sa_update(User)
        .where(User.id == uuid.UUID(body["user"]["id"]))
        .values(platform_role=PlatformRole.STAFF)
    )
    await db_session.commit()
    return client


@pytest.fixture(autouse=True)
def _fake_publisher_up():
    fake = registry.fake_prices()
    fake.down = False
    yield
    fake.down = False


def _offer(code: str, amount: int | None = 999, **overrides) -> dict:
    payload = {
        "code": code, "offer_type": "single", "display_name": "Single check",
        "display_amount_minor": amount, "audit_credits": 1, "presence_credits": 1,
    }
    payload.update(overrides)
    return payload


def _plan(amount: int | None = 14999) -> dict:
    return {
        "code": "monthly", "name": "Monthly", "description": "", "is_public": True,
        "sort_order": 1,
        "entitlements": {
            "audits_per_period": None, "presence_per_period": 100,
            "max_pages_per_audit": 50, "report_download": True,
        },
        "prices": [{"currency": "USD", "interval": "month", "display_amount_minor": amount}],
    }


async def _single_row(db_session) -> CommercialOffer:
    return (await db_session.execute(
        select(CommercialOffer).where(CommercialOffer.code == "single")
    )).scalar_one()


# ── збереження ціни ────────────────────────────────────────────────────


async def test_saving_a_price_publishes_it_with_the_active_provider(staff, db_session):
    response = await staff.put("/v1/admin/commerce/offers/single", json=_offer("single"))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["provider"] == "fake"
    assert body["provider_price_ref"] == "fake_single"

    row = await _single_row(db_session)
    assert row.provider == "fake"
    assert row.provider_price_ref == "fake_single"
    assert row.provider_product_ref == "fake_product_single"
    assert registry.fake_prices().published["fake_single"].amount_minor == 999


async def test_the_body_cannot_name_the_provider_or_the_price(staff, db_session):
    """Що б не прийшло в тілі — провайдер каси й опублікований прайс."""
    response = await staff.put("/v1/admin/commerce/offers/single", json=_offer(
        "single", provider="paddle", provider_price_ref="pri_0123456789abcdef",
    ))
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "fake"
    assert response.json()["provider_price_ref"] == "fake_single"


async def test_changing_the_amount_updates_the_same_provider_price(staff, db_session):
    """9.99 → 12.00: той самий ідентифікатор, нова сума у провайдера."""
    await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 999))
    response = await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 1200))
    assert response.status_code == 200, response.text
    assert response.json()["provider_price_ref"] == "fake_single"
    assert registry.fake_prices().published["fake_single"].amount_minor == 1200
    assert (await _single_row(db_session)).display_amount_minor == 1200


async def test_a_price_without_an_amount_is_refused(staff):
    response = await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", None))
    assert response.status_code == 422
    assert "ціну" in response.json()["detail"]


async def test_provider_refusal_blocks_the_save_and_keeps_the_old_price(staff, db_session):
    await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 999))
    registry.fake_prices().down = True

    response = await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 1200))
    assert response.status_code == 502, response.text
    assert "fake" in response.json()["detail"]
    assert "network_error" in response.json()["detail"]

    db_session.expire_all()
    row = await _single_row(db_session)
    assert row.display_amount_minor == 999, "сайт не показує суми, яку каса не візьме"
    assert row.provider_price_ref == "fake_single"


async def test_plan_price_is_published_and_updated_in_place(staff, db_session):
    first = await staff.put("/v1/admin/commerce/plans/monthly", json=_plan(14999))
    assert first.status_code == 200, first.text
    price = first.json()["prices"][0]
    assert price["provider"] == "fake"
    assert price["provider_price_id"] == "fake_monthly_month"
    assert price["display_amount_minor"] == 14999

    second = await staff.put("/v1/admin/commerce/plans/monthly", json=_plan(15999))
    assert second.status_code == 200, second.text
    assert second.json()["prices"][0]["provider_price_id"] == "fake_monthly_month"
    assert registry.fake_prices().published["fake_monthly_month"].amount_minor == 15999

    plan = (await db_session.execute(select(Plan).where(Plan.code == "monthly"))).scalar_one()
    rows = (await db_session.execute(
        select(PlanPrice).where(PlanPrice.plan_id == plan.id)
    )).scalars().all()
    assert len(rows) == 1, "одна ціна на (валюта, період), а не рядок на кожне збереження"
    assert rows[0].provider_product_ref == "fake_product_monthly_month"


# ── зміна провайдера ───────────────────────────────────────────────────


class _StubPaddle:
    """Публікатор «paddle» без мережі: ідентифікатори у формі Paddle."""

    name = "paddle"

    def __init__(self, *, failing: bool = False) -> None:
        self.failing = failing
        self.published: dict[str, PublishedPrice] = {}
        self.specs: list[PriceSpec] = []

    async def publish(self, spec, *, price_ref, product_ref):
        self.specs.append(spec)
        if self.failing:
            raise PublishFailed("unauthorized", "Paddle відповів HTTP 403")
        ref = price_ref if price_ref and price_ref.startswith("pri_stub") else (
            f"pri_stub{uuid.uuid4().hex[:16]}"
        )
        published = PublishedPrice(
            provider="paddle", product_ref="pro_stub", price_ref=ref,
            amount_minor=spec.amount_minor, currency=spec.currency,
            interval=spec.interval, status="active",
        )
        self.published[ref] = published
        return published

    async def read(self, price_ref):
        return self.published.get(price_ref)


@pytest_asyncio.fixture
async def paddle_stub(staff):
    """Підмінити публікатор Paddle і повернути все як було — разом із
    чинним провайдером у робочих налаштуваннях."""
    original = registry.publisher_for("paddle")
    stub = _StubPaddle()
    registry.register_publisher("paddle", stub)
    try:
        yield stub
    finally:
        registry.register_publisher("paddle", original)
        await staff.put("/v1/admin/config/payment", json={"values": {"billing_provider": None}})
        runtime.reset_cache()


async def test_switching_the_provider_republishes_the_catalogue(staff, db_session, paddle_stub):
    await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 999))
    await staff.put("/v1/admin/commerce/plans/monthly", json=_plan(14999))

    response = await staff.put(
        "/v1/admin/config/payment", json={"values": {"billing_provider": "paddle"}}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["active_provider"] == "paddle"
    outcomes = {row["code"]: row["outcome"] for row in body["published"]}
    assert outcomes == {"single": "published", "monthly_month": "published"}
    assert all(row["published"] for row in body["catalogue"])
    assert {spec.amount_minor for spec in paddle_stub.specs} == {999, 14999}, (
        "у нового провайдера — ті самі суми, що на закладці цін"
    )

    db_session.expire_all()
    row = await _single_row(db_session)
    assert row.provider == "paddle"
    assert row.provider_price_ref.startswith("pri_stub")
    assert row.display_amount_minor == 999


async def test_switching_back_reuses_what_that_provider_already_had(
    staff, db_session, paddle_stub
):
    """Каса → Paddle → назад на фейк → знову Paddle. Останній крок бере
    ТОЙ САМИЙ прайс, а не створює третій: інакше кожна локальна перевірка
    засмічувала б акаунт провайдера новими продуктами."""
    await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 999))

    await staff.put("/v1/admin/config/payment", json={"values": {"billing_provider": "paddle"}})
    db_session.expire_all()
    first = (await _single_row(db_session)).provider_price_ref
    assert first.startswith("pri_stub")

    await staff.put("/v1/admin/config/payment", json={"values": {"billing_provider": "fake"}})
    db_session.expire_all()
    assert (await _single_row(db_session)).provider == "fake"

    await staff.put("/v1/admin/config/payment", json={"values": {"billing_provider": "paddle"}})
    db_session.expire_all()
    row = await _single_row(db_session)
    assert row.provider == "paddle"
    assert row.provider_price_ref == first, "той самий прайс, а не новий"
    assert row.provider_refs["fake"]["price"] == "fake_single", "памʼять фейка ціла"


async def test_a_failing_provider_keeps_the_settings_and_the_old_records(
    staff, db_session, paddle_stub
):
    await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 999))
    paddle_stub.failing = True

    response = await staff.put(
        "/v1/admin/config/payment", json={"values": {"billing_provider": "paddle"}}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["active_provider"] == "paddle", "налаштування збережено — ключ можна виправити"
    failed = next(row for row in body["published"] if row["code"] == "single")
    assert failed["outcome"] == "unauthorized"
    assert "403" in failed["detail"]
    status = next(row for row in body["catalogue"] if row["code"] == "single")
    assert status["published"] is False, "для нової каси прайса немає — і кабінет це каже"

    db_session.expire_all()
    row = await _single_row(db_session)
    assert row.provider == "fake" and row.provider_price_ref == "fake_single", (
        "запис, що не опублікувався, не переписується"
    )


async def test_a_setting_that_does_not_move_the_target_does_not_republish(staff):
    response = await staff.put(
        "/v1/admin/config/payment", json={"values": {"paddle_timeout_s": "25"}}
    )
    assert response.status_code == 200, response.text
    assert response.json()["published"] is None
    await staff.put("/v1/admin/config/payment", json={"values": {"paddle_timeout_s": None}})
    runtime.reset_cache()


async def test_payment_view_lists_the_catalogue_without_the_network(staff):
    await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 999))
    view = (await staff.get("/v1/admin/config/payment")).json()
    row = next(r for r in view["catalogue"] if r["code"] == "single")
    assert row == {
        "kind": "offer", "code": "single", "name": "Single check",
        "amount_minor": 999, "currency": "USD", "provider": "fake",
        "price_ref": "fake_single", "published": True,
    }


# ── гість купує «разову перевірку» ─────────────────────────────────────


async def test_the_guest_till_sells_the_single_offer(staff, db_session):
    await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 999))
    assert await purchases_app.one_off_price_ref(db_session, provider="fake") == "fake_single"


async def test_without_a_single_offer_the_guest_till_has_no_price(db_session):
    with pytest.raises(purchases_app.ProviderUnavailable, match="разова перевірка"):
        await purchases_app.one_off_price_ref(db_session, provider="fake")


async def test_an_offer_published_elsewhere_does_not_serve_this_till(staff, db_session):
    await staff.put("/v1/admin/commerce/offers/single", json=_offer("single", 999))
    with pytest.raises(purchases_app.ProviderUnavailable):
        await purchases_app.one_off_price_ref(db_session, provider="paddle")
