"""Паралельна доставка однієї події двома зʼєднаннями. Живий PostgreSQL.

Решта білінгових тестів живе в одній транзакції фікстури — там «гонку»
можна лише зімітувати послідовно. Цей тест інший: два незалежні
зʼєднання, справжні коміти, одна подія в обох одночасно. Перевіряється
не логіка, а примітиви, на яких вона тримається: `ON CONFLICT DO
NOTHING` по `(provider, external_event_id)` і атомарне захоплення
UPDATE-ом. Regression proof, а не нова архітектура.

Ціна справжніх комітів — прибирання за собою: створене тут пережило б
відкот фікстури й отруїло глобальні підрахунки сусідніх тестів. Тому
`finally` зносить усе створене в зворотному порядку залежностей.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application import billing as pipeline
from app.billing.enums import SubscriptionStatus
from app.billing.providers.fake import FakeBillingProvider
from app.identity import service as identity
from app.models.billing import (
    BillingCustomer,
    BillingEvent,
    Plan,
    PlanPrice,
    Subscription,
    SubscriptionTransition,
)
from app.models.identity import Membership, Organization, User

PASSWORD = "correct-horse-battery"


@pytest.mark.asyncio
async def test_two_connections_delivering_one_event_make_one_transition(postgres_url):
    """Обидва процеси відповідають «добре», перехід — рівно один."""
    engine = create_async_engine(postgres_url)
    make = async_sessionmaker(engine, expire_on_commit=False)
    marker = f"conc-{uuid.uuid4().hex[:8]}"
    price_ref = f"pri_{marker}"

    try:
        # ── підготовка: організація і відображення прайсу, справжній коміт ──
        async with make() as setup:
            reg = await identity.register(
                setup, email=f"{marker}@example.com", password=PASSWORD
            )
            await setup.flush()
            org = reg.organization.id
            plan = (
                (await setup.execute(select(Plan).where(Plan.code == "pro")))
                .scalars()
                .one()
            )
            setup.add(
                PlanPrice(
                    plan_id=plan.id,
                    provider="fake",
                    provider_price_id=price_ref,
                    currency="USD",
                    interval="month",
                )
            )
            await setup.commit()

        fake = FakeBillingProvider()
        event = fake.activate(organization_id=org, price_ref=price_ref)

        # ── сама гонка: одна подія, два зʼєднання, одночасно ──────────────
        async with make() as left, make() as right:
            first, second = await asyncio.gather(
                pipeline.ingest(left, event), pipeline.ingest(right, event)
            )

        outcomes = sorted([first.outcome, second.outcome])
        # Один обробив; другий побачив або готовий результат (duplicate),
        # або чуже захоплення (busy). Обидва — успішні відповіді
        # провайдеру: жодна не вимагає повторної доставки.
        assert "processed" in outcomes, outcomes
        assert outcomes[0] in ("busy", "duplicate"), outcomes

        # ── перевірка в базі, свіжим зʼєднанням ───────────────────────────
        async with make() as check:
            events = (
                (
                    await check.execute(
                        select(BillingEvent).where(
                            BillingEvent.external_event_id == event.external_event_id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(events) == 1, "рядок журналу один — унікальність БД"

            transitions = (
                (
                    await check.execute(
                        select(SubscriptionTransition).where(
                            SubscriptionTransition.organization_id == org
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(transitions) == 1, "перехід один — атомарне захоплення"

            subscription = (
                (
                    await check.execute(
                        select(Subscription).where(Subscription.organization_id == org)
                    )
                )
                .scalars()
                .one()
            )
            assert subscription.status is SubscriptionStatus.ACTIVE

    finally:
        # Створене справжніми комітами — прибрати справжніми комітами,
        # у зворотному порядку залежностей.
        async with make() as cleanup:
            await cleanup.execute(
                delete(SubscriptionTransition).where(
                    SubscriptionTransition.organization_id == org
                )
            )
            await cleanup.execute(
                delete(BillingEvent).where(
                    BillingEvent.external_event_id == event.external_event_id
                )
            )
            await cleanup.execute(
                delete(Subscription).where(Subscription.organization_id == org)
            )
            await cleanup.execute(
                delete(BillingCustomer).where(BillingCustomer.organization_id == org)
            )
            await cleanup.execute(
                delete(PlanPrice).where(PlanPrice.provider_price_id == price_ref)
            )
            await cleanup.execute(
                delete(Membership).where(Membership.organization_id == org)
            )
            await cleanup.execute(delete(Organization).where(Organization.id == org))
            await cleanup.execute(
                delete(User).where(User.email == f"{marker}@example.com")
            )
            await cleanup.commit()
        await engine.dispose()
