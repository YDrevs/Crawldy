"""Зарахування оплат руками: службова дія, яка не має власних повноважень.

Закони:

* зарахувати можна лише те, що ПРОВАЙДЕР називає оплаченим;
* провайдера питаємо на момент дії, а не віримо попередній звірці;
* та сама транзакція не оплачує двох покупок;
* повторна доставка справжньої події після зарахування нічого не подвоює;
* слід лишається: у журналі видно, хто зарахував.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import purchases as purchases_app
from app.billing.enums import PurchaseStatus
from app.billing.registry import fake as fake_provider
from app.identity.enums import PlatformRole
from app.models.billing import BillingEvent
from app.models.identity import Organization, User
from app.models.purchase import AuditCredit, OneOffPurchase
from tests.integration.conftest import register

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def staff(client, db_session):
    body = (await register(client, f"rec-staff-{uuid.uuid4().hex[:8]}@example.com")).json()
    await db_session.execute(
        sa_update(User)
        .where(User.id == uuid.UUID(body["user"]["id"]))
        .values(platform_role=PlatformRole.STAFF)
    )
    await db_session.commit()
    return client


async def _org(db: AsyncSession) -> uuid.UUID:
    return (
        await db.execute(
            select(Organization.id).order_by(Organization.created_at.desc()).limit(1)
        )
    ).scalar_one()


async def _pending(db: AsyncSession, org: uuid.UUID, *, ref: str, quantity: int = 25) -> uuid.UUID:
    """Відкрита каса зі зліпком умов — так, як це робить справжня покупка.

    Зліпок обовʼязковий: саме з нього видача бере, скільки чого належить,
    і без нього тест міряв би фолбек, а не продукт.
    """
    purchase = await purchases_app.open_pending(
        db, organization_id=org, provider="fake", audit_id=None,
        quantity=quantity, offer_code="pack",
        offer_snapshot={
            "offer_code": "pack", "offer_type": "pack",
            "audit_credits": quantity, "presence_credits": quantity,
            "currency": "USD", "display_amount_minor": 4999,
        },
    )
    await purchases_app.attach_provider_ref(db, purchase=purchase, provider_ref=ref)
    await db.commit()
    return purchase.id


async def _credits(db: AsyncSession, org: uuid.UUID) -> int:
    rows = await db.execute(select(AuditCredit).where(AuditCredit.organization_id == org))
    return len(rows.scalars().all())


# ── перелік ────────────────────────────────────────────────────────────


async def test_the_list_shows_what_is_needed_to_recognise_the_payment(staff, db_session):
    org = await _org(db_session)
    await _pending(db_session, org, ref="chk_listed")

    rows = (await staff.get("/v1/admin/payments/pending")).json()
    row = next(r for r in rows if r["transaction_ref"] == "chk_listed")
    assert set(row) == {
        "purchase_id", "status", "created_at", "organization", "email",
        "offer_code", "product", "audit_id", "quantity", "currency",
        "amount_minor", "provider", "foreign", "transaction_ref",
    }
    assert row["status"] == "pending"
    assert row["quantity"] == 25
    assert row["provider"] == "fake"


async def test_a_credited_purchase_leaves_the_list(staff, db_session):
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_leaves")
    fake_provider().settle("chk_leaves")

    await staff.post(f"/v1/admin/payments/{purchase_id}/credit")
    rows = (await staff.get("/v1/admin/payments/pending")).json()
    assert all(r["purchase_id"] != str(purchase_id) for r in rows)


# ── звірка ─────────────────────────────────────────────────────────────


async def test_verify_asks_the_provider_and_changes_nothing(staff, db_session):
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_asked")
    fake_provider().settle("chk_asked")

    answer = (await staff.post(f"/v1/admin/payments/{purchase_id}/verify")).json()
    assert answer["settlement"] == "paid"

    db_session.expire_all()
    purchase = (await db_session.execute(
        select(OneOffPurchase).where(OneOffPurchase.id == purchase_id)
    )).scalar_one()
    assert purchase.status is PurchaseStatus.PENDING, "звірка нічого не зараховує"
    assert await _credits(db_session, org) == 0


# ── зарахування ────────────────────────────────────────────────────────


async def test_credit_grants_exactly_what_was_bought(staff, db_session):
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_paid", quantity=25)
    fake_provider().settle("chk_paid")

    response = await staff.post(f"/v1/admin/payments/{purchase_id}/credit")
    assert response.status_code == 200, response.text
    assert response.json()["credited"] is True

    db_session.expire_all()
    purchase = (await db_session.execute(
        select(OneOffPurchase).where(OneOffPurchase.id == purchase_id)
    )).scalar_one()
    assert purchase.status is PurchaseStatus.PAID
    assert await _credits(db_session, org) == 50, "25 перевірок і 25 Presence"


async def test_an_unpaid_transaction_is_refused(staff, db_session):
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_unpaid")

    response = await staff.post(f"/v1/admin/payments/{purchase_id}/credit")
    assert response.status_code == 409, response.text
    assert "не підтверджує" in response.json()["detail"]
    assert await _credits(db_session, org) == 0


async def test_crediting_twice_grants_once(staff, db_session):
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_twice")
    fake_provider().settle("chk_twice")

    assert (await staff.post(f"/v1/admin/payments/{purchase_id}/credit")).status_code == 200
    second = await staff.post(f"/v1/admin/payments/{purchase_id}/credit")
    assert second.status_code == 409, "покупка вже не в очікуванні"
    db_session.expire_all()
    assert await _credits(db_session, org) == 50


async def test_one_transaction_cannot_pay_two_purchases(staff, db_session):
    """Дві вкладки лишають два наші рядки на одну оплату. Провайдер
    відповідає про транзакцію й сказав би «оплачено» обом."""
    org = await _org(db_session)
    first = await _pending(db_session, org, ref="chk_shared")
    second = await _pending(db_session, org, ref="chk_shared")
    fake_provider().settle("chk_shared")

    assert (await staff.post(f"/v1/admin/payments/{first}/credit")).status_code == 200
    refused = await staff.post(f"/v1/admin/payments/{second}/credit")
    assert refused.status_code == 409, refused.text
    assert "вже зараховано" in refused.json()["detail"]
    db_session.expire_all()
    assert await _credits(db_session, org) == 50


async def test_the_journal_names_who_credited(staff, db_session):
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_trail")
    fake_provider().settle("chk_trail")
    await staff.post(f"/v1/admin/payments/{purchase_id}/credit")

    event = (await db_session.execute(
        select(BillingEvent).where(
            BillingEvent.external_event_id == f"reconciled:{purchase_id}"
        )
    )).scalar_one()
    assert event.payload["manual_reconciliation"] is True
    assert event.payload["reconciled_by"], "у сліду є людина"
    assert event.payload["provider_transaction_id"] == "chk_trail"


# ── гасіння покинутих кас ──────────────────────────────────────────────


async def test_counting_changes_nothing(staff, db_session):
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_counted")
    fake_provider().abandon("chk_counted")

    report = (await staff.post("/v1/admin/payments/sweep", json={})).json()
    assert report["sweepable"] == 1
    assert report["swept"] == 0, "перший виклик лише рахує"
    assert report["ids"] == [str(purchase_id)]
    db_session.expire_all()
    purchase = (await db_session.execute(
        select(OneOffPurchase).where(OneOffPurchase.id == purchase_id)
    )).scalar_one()
    assert purchase.status is PurchaseStatus.PENDING


async def test_an_unpaid_till_is_closed_not_deleted(staff, db_session):
    """Рядок лишається: пізніша оплата мусить знайти свій запис."""
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_closed")
    fake_provider().abandon("chk_closed")

    report = (await staff.post(
        "/v1/admin/payments/sweep", json={"purchase_ids": [str(purchase_id)]}
    )).json()
    assert report["swept"] == 1
    db_session.expire_all()
    purchase = (await db_session.execute(
        select(OneOffPurchase).where(OneOffPurchase.id == purchase_id)
    )).scalar_one()
    assert purchase.status is PurchaseStatus.ABANDONED, "рядок на місці"
    rows = (await staff.get("/v1/admin/payments/pending")).json()
    assert all(r["purchase_id"] != str(purchase_id) for r in rows), "перелік чиститься"


async def test_closed_tills_are_visible_on_request(staff, db_session):
    """Погашена каса не зникла: перемикач повертає її на екран."""
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_visible")
    fake_provider().abandon("chk_visible")
    await staff.post("/v1/admin/payments/sweep", json={"purchase_ids": [str(purchase_id)]})

    default = (await staff.get("/v1/admin/payments/pending")).json()
    assert all(r["purchase_id"] != str(purchase_id) for r in default)

    with_closed = (await staff.get(
        "/v1/admin/payments/pending?include_closed=true"
    )).json()
    row = next(r for r in with_closed if r["purchase_id"] == str(purchase_id))
    assert row["status"] == "abandoned"


async def test_bulk_check_covers_closed_tills_on_request(staff, db_session):
    """Звірка — читання, і на погашених вона потрібна найбільше: саме так
    видно оплату, що прийшла вже після гасіння."""
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_bulk_closed")
    fake_provider().abandon("chk_bulk_closed")
    await staff.post("/v1/admin/payments/sweep", json={"purchase_ids": [str(purchase_id)]})
    fake_provider().settle("chk_bulk_closed")

    default = (await staff.post("/v1/admin/payments/verify")).json()
    assert str(purchase_id) not in default, "у робочому переліку її немає"

    with_closed = (await staff.post(
        "/v1/admin/payments/verify?include_closed=true"
    )).json()
    assert with_closed[str(purchase_id)]["settlement"] == "paid"


async def test_a_closed_till_can_still_be_credited(staff, db_session):
    """Заплатили після гасіння — оператор зараховує без жодних обрядів."""
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_late_pay")
    fake_provider().abandon("chk_late_pay")
    await staff.post("/v1/admin/payments/sweep", json={"purchase_ids": [str(purchase_id)]})

    fake_provider().settle("chk_late_pay")
    response = await staff.post(f"/v1/admin/payments/{purchase_id}/credit")
    assert response.status_code == 200, response.text
    db_session.expire_all()
    purchase = (await db_session.execute(
        select(OneOffPurchase).where(OneOffPurchase.id == purchase_id)
    )).scalar_one()
    assert purchase.status is PurchaseStatus.PAID
    assert await _credits(db_session, org) == 50


async def test_a_payment_after_closing_revives_the_purchase(staff, db_session):
    """Найважливіше: гасіння не коштує клієнту грошей."""
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_revived")
    fake_provider().abandon("chk_revived")
    await staff.post("/v1/admin/payments/sweep", json={"purchase_ids": [str(purchase_id)]})

    # Перевірена подія оживляє покупку сама, без жодної ручної дії.
    db_session.expire_all()
    purchase = (await db_session.execute(
        select(OneOffPurchase).where(OneOffPurchase.id == purchase_id)
    )).scalar_one()
    assert await purchases_app.mark_paid(
        db_session, purchase=purchase, currency="USD", amount_minor=4999,
        purchased_at=datetime.now(UTC),
    ) is True
    await db_session.commit()
    db_session.expire_all()
    revived = (await db_session.execute(
        select(OneOffPurchase).where(OneOffPurchase.id == purchase_id)
    )).scalar_one()
    assert revived.status is PurchaseStatus.PAID
    assert await _credits(db_session, org) == 50, "куплене видано"


async def test_a_paid_till_is_never_closed(staff, db_session):
    org = await _org(db_session)
    await _pending(db_session, org, ref="chk_paid_sweep")
    fake_provider().settle("chk_paid_sweep")

    report = (await staff.post("/v1/admin/payments/sweep", json={})).json()
    assert report["sweepable"] == 0
    assert report["paid"] == 1


async def test_a_silent_provider_closes_nothing(
    staff, db_session, monkeypatch: pytest.MonkeyPatch
):
    """«Не знаємо» — не «не оплачено». Мовчання нічого не гасить."""
    from app.billing.providers import ProviderUnavailable

    org = await _org(db_session)
    await _pending(db_session, org, ref="chk_silent_sweep")

    async def refuse(*_: object, **__: object) -> None:
        raise ProviderUnavailable("провайдер мовчить")

    monkeypatch.setattr(fake_provider(), "settlement_report", refuse)
    report = (await staff.post("/v1/admin/payments/sweep", json={})).json()
    assert report["sweepable"] == 0
    assert report["unknown"] == 1


async def test_the_confirmed_set_can_only_shrink(staff, db_session):
    """Між підрахунком і згодою людина могла заплатити."""
    org = await _org(db_session)
    first = await _pending(db_session, org, ref="chk_shrink_a")
    second = await _pending(db_session, org, ref="chk_shrink_b")
    fake_provider().abandon("chk_shrink_a")
    fake_provider().abandon("chk_shrink_b")

    counted = (await staff.post("/v1/admin/payments/sweep", json={})).json()
    assert counted["sweepable"] == 2
    fake_provider().settle("chk_shrink_b")  # заплатили саме зараз

    applied = (await staff.post(
        "/v1/admin/payments/sweep", json={"purchase_ids": counted["ids"]}
    )).json()
    assert applied["swept"] == 1, "оплачену не гасимо, хоч її й підтвердили"
    db_session.expire_all()
    still = (await db_session.execute(
        select(OneOffPurchase).where(OneOffPurchase.id == second)
    )).scalar_one()
    assert still.status is PurchaseStatus.PENDING
    assert first


async def test_the_summary_names_the_whole_backlog(staff, db_session):
    """Нуль мусить нести знаменник: скільки всього, скільки звірено."""
    org = await _org(db_session)
    await _pending(db_session, org, ref="chk_summary")
    report = (await staff.post("/v1/admin/payments/sweep", json={})).json()
    assert report["pending_total"] >= 1
    assert set(report) == {
        "swept", "sweepable", "ids", "pending_total", "checked",
        "unpaid", "foreign", "paid", "unknown", "looked_at",
    }


async def test_a_customer_cannot_sweep_anything(client: httpx.AsyncClient, db_session):
    await register(client, f"rec-sweeper-{uuid.uuid4().hex[:8]}@example.com")
    assert (
        await client.post("/v1/admin/payments/sweep", json={})
    ).status_code == 403


async def test_a_customer_cannot_credit_anything(client: httpx.AsyncClient, db_session):
    await register(client, f"rec-customer-{uuid.uuid4().hex[:8]}@example.com")
    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_forbidden")
    fake_provider().settle("chk_forbidden")

    assert (await client.get("/v1/admin/payments/pending")).status_code == 403
    assert (
        await client.post(f"/v1/admin/payments/{purchase_id}/credit")
    ).status_code == 403
    assert await _credits(db_session, org) == 0


async def test_paid_but_unstarted_guest_purchase_is_visible_on_request(
    staff, db_session
):
    """Третій стан анонімної воронки: гроші є, сайт ще не названий.

    Такої покупки не показував жоден перелік: вона не «незарахована» (її
    зараховано кредитами) і не «без доступу» (аудиту ще немає). Саме в
    цьому стані оператор мусить бачити гроші.
    """
    from datetime import UTC, datetime

    from app.identity.enums import OrganizationKind

    org = await _org(db_session)
    await db_session.execute(
        sa_update(Organization)
        .where(Organization.id == org)
        .values(kind=OrganizationKind.GUEST)
    )
    purchase_id = await _pending(db_session, org, ref="chk_unspent", quantity=1)
    purchase = await db_session.get(OneOffPurchase, purchase_id)
    assert purchase is not None
    await purchases_app.mark_paid(
        db_session, purchase=purchase, currency="USD", amount_minor=999,
        purchased_at=datetime.now(UTC),
    )
    await db_session.commit()

    default = (await staff.get("/v1/admin/payments/pending")).json()
    assert all(r["purchase_id"] != str(purchase_id) for r in default)

    shown = (await staff.get(
        "/v1/admin/payments/pending?include_unspent=true"
    )).json()
    row = next(r for r in shown if r["purchase_id"] == str(purchase_id))
    assert row["status"] == "paid"
    assert row["audit_id"] is None


async def test_a_cabinet_top_up_is_not_an_unspent_purchase(staff, db_session):
    """Пакет на акаунті теж без аудиту — але це нормальний кінцевий стан.

    Він зарахований на баланс, і показувати його поруч із «гроші без
    товару» означало б назвати роботою те, що вже зроблено.
    """
    from datetime import UTC, datetime

    org = await _org(db_session)
    purchase_id = await _pending(db_session, org, ref="chk_topup", quantity=25)
    purchase = await db_session.get(OneOffPurchase, purchase_id)
    assert purchase is not None
    await purchases_app.mark_paid(
        db_session, purchase=purchase, currency="USD", amount_minor=4999,
        purchased_at=datetime.now(UTC),
    )
    await db_session.commit()

    shown = (await staff.get(
        "/v1/admin/payments/pending?include_unspent=true"
    )).json()

    assert all(r["purchase_id"] != str(purchase_id) for r in shown)
