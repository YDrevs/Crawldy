"""Кабінет каже, що оплата в дорозі, і не видає за неї прав.

Стан, заради якого це існує: провайдер гроші отримав, а перевірена подія
до нас ще не дійшла. Раніше кабінет у цьому місці мовчав, і мовчання
читалось як «гроші зникли».

Закон лишається той самий: права дає ЛИШЕ подія. Ця відповідь нічого не
змінює — ані покупки, ані наділу.
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import purchases as purchases_app
from app.billing.providers import ProviderUnavailable
from app.billing.registry import fake as fake_provider
from app.models.identity import Organization
from app.models.purchase import AuditCredit, OneOffPurchase
from tests.integration.conftest import register

pytestmark = pytest.mark.asyncio


async def _org(db: AsyncSession) -> uuid.UUID:
    return (
        await db.execute(
            select(Organization.id).order_by(Organization.created_at.desc()).limit(1)
        )
    ).scalar_one()


async def _pending(db: AsyncSession, org: uuid.UUID, *, ref: str) -> None:
    """Відкрита каса: покупка є, події немає."""
    purchase = await purchases_app.open_pending(
        db, organization_id=org, provider="fake", audit_id=None,
        quantity=25, offer_code="pack",
    )
    await purchases_app.attach_provider_ref(db, purchase=purchase, provider_ref=ref)
    await db.commit()


async def _credits(db: AsyncSession, org: uuid.UUID) -> int:
    rows = await db.execute(
        select(AuditCredit).where(AuditCredit.organization_id == org)
    )
    return len(rows.scalars().all())


async def test_without_purchases_nothing_is_awaited(client: httpx.AsyncClient, db_session):
    await register(client, f"pay-none-{uuid.uuid4().hex[:8]}@example.com")
    body = (await client.get("/v1/account/payment-state")).json()
    assert body == {"awaiting_event": False}


async def test_an_open_till_alone_is_not_a_payment(client: httpx.AsyncClient, db_session):
    """Каса відкрита, грошей немає: провайдер каже «не оплачено»."""
    await register(client, f"pay-open-{uuid.uuid4().hex[:8]}@example.com")
    await _pending(db_session, await _org(db_session), ref="chk_not_paid")
    body = (await client.get("/v1/account/payment-state")).json()
    assert body == {"awaiting_event": False}


async def test_money_taken_without_an_event_is_said_out_loud(
    client: httpx.AsyncClient, db_session
):
    await register(client, f"pay-paid-{uuid.uuid4().hex[:8]}@example.com")
    org = await _org(db_session)
    await _pending(db_session, org, ref="chk_paid_no_event")
    fake_provider().settle("chk_paid_no_event")

    body = (await client.get("/v1/account/payment-state")).json()
    assert body == {"awaiting_event": True}
    # І це не наділ: жодного кредиту з цієї відповіді не зʼявилось.
    assert await _credits(db_session, org) == 0


async def test_a_silent_provider_promises_nothing(
    client: httpx.AsyncClient, db_session, monkeypatch: pytest.MonkeyPatch
):
    """Провайдер не відповів — кажемо нічого, а не «оплату отримано»."""
    await register(client, f"pay-silent-{uuid.uuid4().hex[:8]}@example.com")
    await _pending(db_session, await _org(db_session), ref="chk_silent")

    async def refuse(*_: object, **__: object) -> None:
        raise ProviderUnavailable("провайдер мовчить")

    monkeypatch.setattr(fake_provider(), "settlement_of", refuse)
    body = (await client.get("/v1/account/payment-state")).json()
    assert body == {"awaiting_event": False}


async def test_a_paid_till_older_than_the_last_one_still_counts(
    client: httpx.AsyncClient, db_session
):
    """Справжній випадок: оплата о 16:48, потім ще одна каса о 16:50, яку
    покинули. Оплаченою була НЕ остання."""
    await register(client, f"pay-many-{uuid.uuid4().hex[:8]}@example.com")
    org = await _org(db_session)
    await _pending(db_session, org, ref="chk_old_paid")
    fake_provider().settle("chk_old_paid")
    await _pending(db_session, org, ref="chk_new_unpaid")

    body = (await client.get("/v1/account/payment-state")).json()
    assert body == {"awaiting_event": True}


async def test_the_provider_is_not_asked_about_every_abandoned_till(
    client: httpx.AsyncClient, db_session, monkeypatch: pytest.MonkeyPatch
):
    """Покинута каса лишає рядок назавжди; питати про кожну — платити
    провайдеру за кожне відкриття сторінки."""
    from app.application import purchases as module

    await register(client, f"pay-lots-{uuid.uuid4().hex[:8]}@example.com")
    org = await _org(db_session)
    for i in range(module.AWAITING_LOOKBACK + 3):
        await _pending(db_session, org, ref=f"chk_abandoned_{i}")

    asked: list[str] = []
    original = fake_provider().settlement_of

    async def counted(*, transaction_ref: str):
        asked.append(transaction_ref)
        return await original(transaction_ref=transaction_ref)

    monkeypatch.setattr(fake_provider(), "settlement_of", counted)
    body = (await client.get("/v1/account/payment-state")).json()
    assert body == {"awaiting_event": False}
    assert len(asked) == module.AWAITING_LOOKBACK


async def test_anonymous_gets_no_answer(client: httpx.AsyncClient):
    assert (await client.get("/v1/account/payment-state")).status_code == 401


# ── стан однієї покупки: відповідь для закритої каси ───────────────────
#
# Сторінка оплати без цього маршруту не мала як дізнатися, що сталося з
# касою, яку закрили: вона лишалась зі спінером «Відкриваємо захищену
# оплату» назавжди. Три відповіді розводяться так само, як у гостя.


async def test_a_foreign_purchase_is_not_found(client: httpx.AsyncClient, db_session):
    """Чужа покупка — 404, а не 403: «заборонено» підтвердило б, що вона є."""
    await register(client, f"one-alien-{uuid.uuid4().hex[:8]}@example.com")
    answer = await client.get(f"/v1/account/purchases/{uuid.uuid4()}")
    assert answer.status_code == 404


async def test_an_open_till_is_unknown_until_the_provider_is_asked(
    client: httpx.AsyncClient, db_session
):
    """Без звірки — `null`, а не «не списано».

    Поки провайдера не питали, ми справді не знаємо: подія могла ще не
    дійти. `False` тут запросив би до другої оплати того, хто заплатив.
    """
    await register(client, f"one-open-{uuid.uuid4().hex[:8]}@example.com")
    org = await _org(db_session)
    await _pending(db_session, org, ref="chk_one_open")
    purchase_id = (await db_session.execute(
        select(OneOffPurchase.id).where(OneOffPurchase.organization_id == org)
    )).scalar_one()

    quiet = (await client.get(f"/v1/account/purchases/{purchase_id}")).json()
    assert quiet["state"] == "processing"
    assert quiet["charged"] is None

    # Провайдер, який про касу нічого не знає, — це теж «не знаємо».
    unsure = (await client.get(
        f"/v1/account/purchases/{purchase_id}?reconcile=true")).json()
    assert unsure["charged"] is None

    # А ось пряме «не брали» — це вже знання, і лише воно дає сторінці
    # право сказати «кошти не списано».
    fake_provider().abandon("chk_one_open")
    asked = (await client.get(
        f"/v1/account/purchases/{purchase_id}?reconcile=true")).json()
    assert asked["charged"] is False


async def test_a_paid_purchase_says_so_and_grants_nothing(
    client: httpx.AsyncClient, db_session
):
    await register(client, f"one-paid-{uuid.uuid4().hex[:8]}@example.com")
    org = await _org(db_session)
    await _pending(db_session, org, ref="chk_one_paid")
    fake_provider().settle("chk_one_paid")
    purchase_id = (await db_session.execute(
        select(OneOffPurchase.id).where(OneOffPurchase.organization_id == org)
    )).scalar_one()

    body = (await client.get(
        f"/v1/account/purchases/{purchase_id}?reconcile=true")).json()
    assert body["charged"] is True
    # Читання нічого не видає: наділ і далі відкриває лише подія.
    assert await _credits(db_session, org) == 0


async def test_a_silent_provider_leaves_the_purchase_unknown(
    client: httpx.AsyncClient, db_session, monkeypatch: pytest.MonkeyPatch
):
    """Мовчання провайдера — `null`, і сторінка каже «підтвердження ще немає»."""
    await register(client, f"one-silent-{uuid.uuid4().hex[:8]}@example.com")
    org = await _org(db_session)
    await _pending(db_session, org, ref="chk_one_silent")
    purchase_id = (await db_session.execute(
        select(OneOffPurchase.id).where(OneOffPurchase.organization_id == org)
    )).scalar_one()

    async def refuse(*_: object, **__: object) -> None:
        raise ProviderUnavailable("провайдер мовчить")

    monkeypatch.setattr(fake_provider(), "settlement_of", refuse)
    body = (await client.get(
        f"/v1/account/purchases/{purchase_id}?reconcile=true")).json()
    assert body["charged"] is None
