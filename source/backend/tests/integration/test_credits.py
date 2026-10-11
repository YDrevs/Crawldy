"""Разові кредити: провенанс, гонки, повернення, відкликання.

Головні тести тут — ті, які без бази неможливі: два паралельні аудити на
останній кредит і повернення **того самого** кредиту, а не абстрактної
одиниці в баланс. Решту інваріантів теж перевіряємо тут, бо всі переходи
станів — умовні UPDATE, і на SQLite вони поводяться інакше.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application import purchases
from app.audit.enums import AuditStatus, AuditTrigger
from app.billing import credits
from app.billing.enums import CommerceModel, CreditState, PurchaseStatus
from app.core.run_enums import FailureClass, QuotaSource, QuotaState
from app.identity import service as identity
from app.models.audit import Audit
from app.models.purchase import AuditCredit

PASSWORD = "correct-horse-battery"


async def _org(db, email="credits@example.com"):
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    return reg.organization.id


async def _audit(db, org) -> uuid.UUID:
    """Справжній рядок аудиту: у кредита на нього зовнішній ключ.

    Випадковий UUID тут не годиться, і це добре: звʼязок «який саме аудит
    зʼїв цей кредит» тримає база, а не домовленість.
    """
    audit = Audit(
        organization_id=org,
        url="https://example.com/",
        origin="https://example.com",
        status=AuditStatus.QUEUED,
        options={},
        trigger=AuditTrigger.MANUAL,
    )
    db.add(audit)
    await db.flush()
    return audit.id


async def _buy(db, org, *, quantity=2, external_id="tx-1", provider="fake"):
    return await purchases.record(
        db,
        organization_id=org,
        provider=provider,
        external_id=external_id,
        quantity=quantity,
        currency="usd",
        amount_minor=1900,
        purchased_at=datetime.now(UTC),
    )


# ── покупка ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_purchase_grants_one_credit_per_unit(db_session):
    org = await _org(db_session)
    result = await _buy(db_session, org, quantity=3)

    assert result.credits_granted == 3
    assert result.already_known is False
    assert await credits.balance(db_session, organization_id=org) == 3


@pytest.mark.asyncio
async def test_replaying_the_same_payment_does_not_grant_credits_twice(db_session):
    """Провайдер доставляє подію двічі — це нормальна робота, а не збій.

    Подвійна обробка події підписки дала б зайвий перехід стану; подвійна
    обробка покупки дає подаровані гроші.
    """
    org = await _org(db_session)
    first = await _buy(db_session, org, quantity=2, external_id="tx-repeat")
    second = await _buy(db_session, org, quantity=2, external_id="tx-repeat")

    assert first.credits_granted == 2
    assert second.credits_granted == 0
    assert second.already_known is True
    assert second.purchase.id == first.purchase.id
    assert await credits.balance(db_session, organization_id=org) == 2


@pytest.mark.asyncio
async def test_purchase_keeps_who_sold_it_at_the_time_of_sale(db_session):
    """Ключ постачальника й знімок реквізитів — обидва, і назавжди.

    Ключа мало: реєстр юридичних осіб колись відредагують, і без знімка
    вся історія продажів мовчки перепишеться на нову особу.
    """
    org = await _org(db_session)
    result = await _buy(db_session, org)
    purchase = result.purchase

    assert purchase.supplier_entity_key
    assert purchase.supplier_snapshot["key"] == purchase.supplier_entity_key
    assert "country" in purchase.supplier_snapshot
    # Модель торгівлі — окреме поняття від провайдера: після переходу
    # Paddle → Stripe ця покупка мусить і далі означати те саме.
    assert purchase.commerce_model in set(CommerceModel)


@pytest.mark.asyncio
async def test_two_providers_coexist_in_history(db_session):
    """Старі покупки не «перетворюються» на нового провайдера.

    Провайдер — дані рядка, а не глобальна константа, тож покоління
    записів читаються одночасно.
    """
    org = await _org(db_session)
    await _buy(db_session, org, quantity=1, provider="paddle", external_id="p-1")
    await _buy(db_session, org, quantity=1, provider="stripe", external_id="s-1")

    old = await purchases.find(db_session, provider="paddle", external_id="p-1")
    new = await purchases.find(db_session, provider="stripe", external_id="s-1")

    assert old is not None and old.provider == "paddle"
    assert new is not None and new.provider == "stripe"
    # Однаковий зовнішній ідентифікатор у різних провайдерів — не колізія.
    await _buy(db_session, org, quantity=1, provider="paddle", external_id="s-1")
    assert await credits.balance(db_session, organization_id=org) == 3


# ── життєвий цикл кредита ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reserve_consume_removes_the_credit_from_the_balance(db_session):
    org = await _org(db_session)
    await _buy(db_session, org, quantity=2)
    audit_id = await _audit(db_session, org)

    reserved = await credits.reserve(db_session, organization_id=org, audit_id=audit_id)
    assert reserved is not None
    assert await credits.balance(db_session, organization_id=org) == 1

    assert await credits.consume(db_session, audit_id=audit_id) is True
    assert await credits.balance(db_session, organization_id=org) == 1


@pytest.mark.asyncio
async def test_release_returns_the_same_credit_not_an_abstract_unit(db_session):
    """Повернення повертає **той самий** рядок.

    Це не педантизм: кредит належить конкретній покупці, і при поверненні
    коштів за неї має відкликатися саме він. Баланс, поповнений
    абстрактною одиницею, зробив би це неможливим.
    """
    org = await _org(db_session)
    await _buy(db_session, org, quantity=1)
    audit_id = await _audit(db_session, org)

    reserved = await credits.reserve(db_session, organization_id=org, audit_id=audit_id)
    assert await credits.release(db_session, audit_id=audit_id) is CreditState.AVAILABLE

    row = await db_session.execute(select(AuditCredit).where(AuditCredit.id == reserved))
    credit = row.scalar_one()
    assert credit.state is CreditState.AVAILABLE
    assert credit.audit_id is None
    assert await credits.balance(db_session, organization_id=org) == 1


@pytest.mark.asyncio
async def test_consume_and_release_happen_exactly_once(db_session):
    org = await _org(db_session)
    await _buy(db_session, org, quantity=1)
    audit_id = await _audit(db_session, org)
    await credits.reserve(db_session, organization_id=org, audit_id=audit_id)

    assert await credits.consume(db_session, audit_id=audit_id) is True
    # Повтор задачі не має списувати вдруге.
    assert await credits.consume(db_session, audit_id=audit_id) is False
    # Списаний кредит уже не повертається: послугу надано.
    assert await credits.release(db_session, audit_id=audit_id) is None


@pytest.mark.asyncio
async def test_a_credit_cannot_be_reserved_twice(db_session):
    org = await _org(db_session)
    await _buy(db_session, org, quantity=1)

    first = await credits.reserve(db_session, organization_id=org, audit_id=await _audit(db_session, org))
    second = await credits.reserve(db_session, organization_id=org, audit_id=await _audit(db_session, org))

    assert first is not None
    assert second is None, "єдиний кредит дістався двом аудитам"


@pytest.mark.asyncio
async def test_two_parallel_audits_never_share_one_credit(postgres_url):
    """Гонка. Єдина причина, чому цей файл вимагає бази.

    Два одночасні запити на останній кредит: один отримує його, другий —
    нічого. Ніколи обидва.
    """
    # Власна пошта, а не спільна з іншими тестами гонок: ми пишемо повз
    # транзакцію фікстури, тож рядок переживе тест і зіткнеться з тим,
    # хто візьме таку саму. Це вже сталося одного разу.
    email = "credit-race@example.com"
    engine = create_async_engine(postgres_url, poolclass=None)
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as setup:
        org = await _org(setup, email=email)
        await _buy(setup, org, quantity=1, external_id="tx-race")
        await setup.commit()

    async def take() -> uuid.UUID | None:
        async with factory() as session:
            got = await credits.reserve(
                session, organization_id=org, audit_id=await _audit(session, org)
            )
            await session.commit()
            return got

    try:
        left, right = await asyncio.gather(take(), take())
        assert len([x for x in (left, right) if x is not None]) == 1
    finally:
        # Фікстура нічого не відкотить: ми писали повз її транзакцію.
        async with factory() as cleanup:
            for statement, params in (
                ("DELETE FROM audit_credits WHERE organization_id = :org", {"org": org}),
                ("DELETE FROM one_off_purchases WHERE organization_id = :org", {"org": org}),
                ("DELETE FROM audits WHERE organization_id = :org", {"org": org}),
                ("DELETE FROM memberships WHERE organization_id = :org", {"org": org}),
                ("DELETE FROM users WHERE email = :email", {"email": email}),
                ("DELETE FROM organizations WHERE id = :org", {"org": org}),
            ):
                await cleanup.execute(text(statement), params)
            await cleanup.commit()
        await engine.dispose()


# ── повернення коштів ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refund_revokes_unused_credits_and_leaves_spent_ones(db_session):
    """Витрачене не відкликається: послугу було надано."""
    org = await _org(db_session)
    await _buy(db_session, org, quantity=3, external_id="tx-refund")
    audit_id = await _audit(db_session, org)
    await credits.reserve(db_session, organization_id=org, audit_id=audit_id)
    await credits.consume(db_session, audit_id=audit_id)

    result = await purchases.refund(db_session, provider="fake", external_id="tx-refund")
    assert result is not None
    purchase, revoked = result

    assert revoked == 2, "відкликати треба лише невитрачені"
    assert purchase.status is PurchaseStatus.REFUNDED
    assert await credits.balance(db_session, organization_id=org) == 0

    spent = await db_session.execute(
        select(AuditCredit).where(AuditCredit.audit_id == audit_id)
    )
    assert spent.scalar_one().state is CreditState.CONSUMED


@pytest.mark.asyncio
async def test_refund_is_idempotent(db_session):
    org = await _org(db_session)
    await _buy(db_session, org, quantity=2, external_id="tx-twice")

    first = await purchases.refund(db_session, provider="fake", external_id="tx-twice")
    second = await purchases.refund(db_session, provider="fake", external_id="tx-twice")

    assert first is not None and first[1] == 2
    assert second is not None and second[1] == 0


@pytest.mark.asyncio
async def test_refund_does_not_touch_a_credit_in_flight(db_session):
    """Зарезервований кредит зараз виконується — його долю вирішить аудит."""
    org = await _org(db_session)
    await _buy(db_session, org, quantity=2, external_id="tx-inflight")
    audit_id = await _audit(db_session, org)
    await credits.reserve(db_session, organization_id=org, audit_id=audit_id)

    _, revoked = await purchases.refund(  # type: ignore[misc]
        db_session, provider="fake", external_id="tx-inflight"
    )

    assert revoked == 1
    row = await db_session.execute(
        select(AuditCredit).where(AuditCredit.audit_id == audit_id)
    )
    assert row.scalar_one().state is CreditState.RESERVED


# ── повний шлях через прикладний шар ───────────────────────────────────────


@pytest.mark.asyncio
async def test_subscription_quota_is_spent_before_bought_credits(db_session):
    """Порядок оплати. Зворотний витрачав би куплене при наявному наділі.

    Наділ періоду дає лише підписка: безкоштовних повних аудитів не
    існує (рішення власника 2026-09-03), тож тут вона сіється явно.
    """
    from app.application import audits as use_case
    from app.billing.enums import SubscriptionStatus
    from app.models.billing import Plan, Subscription
    from app.schemas.audit import AuditCreate

    org = await _org(db_session, email="order@example.com")
    plan = Plan(
        code="order-monthly",
        name="Order monthly",
        is_public=False,
        entitlements={"audits_per_period": 5, "max_pages_per_audit": 10},
    )
    db_session.add(plan)
    await db_session.flush()
    db_session.add(
        Subscription(
            organization_id=org,
            plan_id=plan.id,
            status=SubscriptionStatus.ACTIVE,
            provider="fake",
            provider_subscription_id="sub-order-1",
        )
    )
    await db_session.flush()
    await _buy(db_session, org, quantity=1, external_id="tx-order")

    payload = AuditCreate(url="https://example.com")
    started = await use_case.start_audit(
        db_session, payload, organization_id=org, created_by_user_id=None
    )

    assert started.audit.quota_source is QuotaSource.SUBSCRIPTION
    assert await credits.balance(db_session, organization_id=org) == 1, (
        "кредит витрачено, поки в тарифі ще лишалася квота"
    )


@pytest.mark.asyncio
async def test_a_failed_audit_paid_by_credit_returns_that_credit(db_session):
    """Наскрізний шлях: покупка → резерв → невдача з нашої вини → повернення."""
    from app.application import audits as use_case

    org = await _org(db_session, email="settle@example.com")
    await _buy(db_session, org, quantity=1, external_id="tx-settle")
    audit_id = await _audit(db_session, org)
    await credits.reserve(db_session, organization_id=org, audit_id=audit_id)

    row = await db_session.execute(select(Audit).where(Audit.id == audit_id))
    audit = row.scalar_one()
    audit.quota_source = QuotaSource.ONE_OFF

    state = await use_case.settle_quota(
        db_session, audit, failure=FailureClass.INTERNAL_ERROR
    )

    assert state is QuotaState.RELEASED
    assert await credits.balance(db_session, organization_id=org) == 1


@pytest.mark.asyncio
async def test_a_credit_paid_audit_that_worked_is_consumed_not_returned(db_session):
    from app.application import audits as use_case

    org = await _org(db_session, email="spent@example.com")
    await _buy(db_session, org, quantity=1, external_id="tx-spent")
    audit_id = await _audit(db_session, org)
    await credits.reserve(db_session, organization_id=org, audit_id=audit_id)

    row = await db_session.execute(select(Audit).where(Audit.id == audit_id))
    audit = row.scalar_one()
    audit.quota_source = QuotaSource.ONE_OFF

    state = await use_case.settle_quota(db_session, audit, failure=None)

    assert state is QuotaState.CONSUMED
    assert await credits.balance(db_session, organization_id=org) == 0
    assert await credits.credit_for(db_session, audit_id=audit_id) is not None


@pytest.mark.asyncio
async def test_renewing_a_subscription_period_does_not_touch_credits(db_session):
    """Кредит не має періоду — і не має його набути.

    Найдорожча помилка цієї моделі була б тихою: кредити, що згорають
    разом із квотою місяця. Тест перевіряє межу прямо: змінюємо період
    так, як його змінює поновлення, і рахуємо баланс.
    """
    from app.billing import quota

    org = await _org(db_session, email="renew@example.com")
    await _buy(db_session, org, quantity=2, external_id="tx-renew")

    old = quota.period_for(None)
    await quota.consume(db_session, organization_id=org, period=old, limit=5)

    later = datetime(old.end.year, old.end.month, old.end.day, tzinfo=UTC)
    fresh = quota.period_for(None, at=later)
    assert fresh.start != old.start, "період справді змінився"

    assert await credits.balance(db_session, organization_id=org) == 2


# ── наскрізь через провайдера ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_whole_path_runs_through_the_provider_adapter(db_session):
    """Покупка приходить подією провайдера, а не викликом зсередини.

    Це і є перевірка провайдер-нейтральності: домен не знає, що подію
    зробив фейк, і при заміні адаптера на справжній не міняється нічого,
    крім самого адаптера.
    """
    from app.application import billing as pipeline
    from app.billing.providers.fake import FakeBillingProvider

    org = await _org(db_session, email="through@example.com")
    provider = FakeBillingProvider()

    bought = provider.purchase_one_off(organization_id=org, quantity=3)
    result = await pipeline.ingest(db_session, bought)

    assert result.outcome == "processed"
    assert await credits.balance(db_session, organization_id=org) == 3

    purchase = await purchases.find(
        db_session, provider="fake", external_id=bought.external_event_id
    )
    assert purchase is not None
    assert purchase.quantity == 3
    assert purchase.supplier_snapshot, "постачальника не зафіксовано"


@pytest.mark.asyncio
async def test_redelivered_purchase_event_grants_nothing_extra(db_session):
    """Провайдер доставив ту саму подію двічі.

    Захист подвійний навмисно: унікальний ключ події не пускає другий
    запис, а унікальний ключ покупки не пустив би її навіть тоді, коли
    ту саму покупку принесли б під двома різними подіями.
    """
    from app.application import billing as pipeline
    from app.billing.providers.fake import FakeBillingProvider

    org = await _org(db_session, email="twice@example.com")
    provider = FakeBillingProvider()
    bought = provider.purchase_one_off(organization_id=org, quantity=2)

    await pipeline.ingest(db_session, bought)
    again = await pipeline.ingest(db_session, bought)

    assert again.outcome in {"duplicate", "processed"}
    assert await credits.balance(db_session, organization_id=org) == 2


@pytest.mark.asyncio
async def test_refund_event_revokes_the_unused_credits(db_session):
    from app.application import billing as pipeline
    from app.billing.providers.fake import FakeBillingProvider

    org = await _org(db_session, email="back@example.com")
    provider = FakeBillingProvider()
    bought = provider.purchase_one_off(organization_id=org, quantity=2)
    await pipeline.ingest(db_session, bought)

    await pipeline.ingest(db_session, provider.refund_one_off(bought))

    assert await credits.balance(db_session, organization_id=org) == 0


@pytest.mark.asyncio
async def test_a_raw_insert_without_enum_columns_survives_the_default(db_session):
    """Запис повз ORM більше не падає на дефолті колонки.

    Дефолт `audits.trigger` і `audits.quota_state` був заданий значенням
    перерахування, а CHECK побудований на іменах, — тобто дефолт
    порушував обмеження власної колонки. ORM завжди пише ці поля сам,
    тому дефект був невидимий; спрацював би він на ручному INSERT,
    міграції даних або відновленні з дампа.
    """
    org = await _org(db_session, email="rawinsert@example.com")
    audit_id = uuid.uuid4()

    await db_session.execute(
        text(
            """
            INSERT INTO audits
                   (id, organization_id, url, origin, status,
                    options, requested_options, findings_summary)
            VALUES (:id, :org, :url, :origin, 'QUEUED',
                    '{}'::jsonb, '{}'::jsonb, '{}'::jsonb)
            """
        ),
        {
            "id": audit_id,
            "org": org,
            "url": "https://example.com/",
            "origin": "https://example.com",
        },
    )

    row = await db_session.execute(
        text("SELECT trigger, quota_state FROM audits WHERE id = :id"), {"id": audit_id}
    )
    trigger, quota_state = row.one()
    assert trigger == "MANUAL"
    assert quota_state == "RESERVED"


# ── повернення коштів під час виконання аудиту ─────────────────────────────


@pytest.mark.asyncio
async def test_a_refunded_purchase_does_not_resurrect_a_credit_on_release(db_session):
    """Найтонший сценарій усієї моделі.

    Кредит зайнято під аудит, за покупку тим часом повернули кошти,
    аудит потім упав із нашої вини. Якби повернення просто вертало
    кредит у доступні, клієнт отримав би оплачений аудит після того, як
    оплату йому повернули.
    """
    from app.application import audits as use_case

    org = await _org(db_session, email="inflight-refund@example.com")
    await _buy(db_session, org, quantity=1, external_id="tx-inflight-refund")
    audit_id = await _audit(db_session, org)
    await credits.reserve(db_session, organization_id=org, audit_id=audit_id)

    # Кошти повертають, поки аудит ще виконується. Зарезервований кредит
    # не чіпаємо: аудит уже запущено.
    await purchases.refund(
        db_session, provider="fake", external_id="tx-inflight-refund"
    )
    assert await credits.balance(db_session, organization_id=org) == 0

    row = await db_session.execute(select(Audit).where(Audit.id == audit_id))
    audit = row.scalar_one()
    audit.quota_source = QuotaSource.ONE_OFF
    state = await use_case.settle_quota(
        db_session, audit, failure=FailureClass.INTERNAL_ERROR
    )

    assert state is QuotaState.RELEASED
    assert await credits.balance(db_session, organization_id=org) == 0, (
        "кредит воскрес доступним після повернення коштів"
    )

    credit = await db_session.execute(
        select(AuditCredit).where(AuditCredit.audit_id == audit_id)
    )
    revoked = credit.scalar_one()
    assert revoked.state is CreditState.REVOKED
    assert revoked.revoked_at is not None
    # Звʼязок з аудитом лишається: видно, під що кредит займали.
    assert revoked.audit_id == audit_id


@pytest.mark.asyncio
async def test_a_refunded_purchase_still_lets_a_running_audit_finish(db_session):
    """Успішний бік того самого сценарію.

    Аудит виконався — послугу надано, і кредит списується остаточно.
    Повернення коштів заднім числом не стирає роботу, яку вже зробили.
    """
    from app.application import audits as use_case

    org = await _org(db_session, email="inflight-done@example.com")
    await _buy(db_session, org, quantity=1, external_id="tx-inflight-done")
    audit_id = await _audit(db_session, org)
    await credits.reserve(db_session, organization_id=org, audit_id=audit_id)
    await purchases.refund(db_session, provider="fake", external_id="tx-inflight-done")

    row = await db_session.execute(select(Audit).where(Audit.id == audit_id))
    audit = row.scalar_one()
    audit.quota_source = QuotaSource.ONE_OFF
    state = await use_case.settle_quota(db_session, audit, failure=None)

    assert state is QuotaState.CONSUMED
    credit = await db_session.execute(
        select(AuditCredit).where(AuditCredit.audit_id == audit_id)
    )
    assert credit.scalar_one().state is CreditState.CONSUMED
    assert await credits.balance(db_session, organization_id=org) == 0


@pytest.mark.asyncio
async def test_settling_twice_does_not_change_the_credit_again(db_session):
    """Перехід рівно один раз навіть при повторі задачі."""
    from app.application import audits as use_case

    org = await _org(db_session, email="settle-twice@example.com")
    await _buy(db_session, org, quantity=1, external_id="tx-settle-twice")
    audit_id = await _audit(db_session, org)
    await credits.reserve(db_session, organization_id=org, audit_id=audit_id)

    row = await db_session.execute(select(Audit).where(Audit.id == audit_id))
    audit = row.scalar_one()
    audit.quota_source = QuotaSource.ONE_OFF

    first = await use_case.settle_quota(
        db_session, audit, failure=FailureClass.INTERNAL_ERROR
    )
    second = await use_case.settle_quota(
        db_session, audit, failure=FailureClass.INTERNAL_ERROR
    )

    assert first is QuotaState.RELEASED
    assert second is QuotaState.RELEASED
    assert await credits.balance(db_session, organization_id=org) == 1
