"""Довговічна книга платних спроб: резервація переживає процес.

Тут перевіряється те, чого памʼятна книга довести не може: рядок
резервації комітиться ДО мережевого виклику, падіння процесу між
диспетчеризацією і персистенцією відповіді не звільняє грошей, а два
процеси не можуть спільно зарезервувати понад стелю — бо серіалізує їх
база (`SELECT ... FOR UPDATE`), а не памʼять одного процесу.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import catalog as ai_catalog
from app.models.presence import PresenceAttempt, PresenceRun
from app.presence.budget import AttemptCell, AttemptState, as_money
from app.presence.policy import DEFAULT_POLICY, to_stored
from app.services.presence_service import DurableAttemptLedger

PRICING = ai_catalog.pricing_version()


def _cell(no: int = 1, prompt: str = "category-1") -> AttemptCell:
    return AttemptCell(provider="scripted", prompt_id=prompt,
                       mode="natural", run_index=1, attempt_no=no)


async def _make_run(session: AsyncSession) -> PresenceRun:
    run = PresenceRun(
        url="https://example.com", origin="https://example.com",
        brand="Acme", brand_aliases=["Acme"],
        prompt_set_version="p0-1:en", prompts=[],
        policy_snapshot={}, status="queued",
    )
    session.add(run)
    await session.flush()
    return run


def _ledger(session: AsyncSession, run_id: uuid.UUID) -> DurableAttemptLedger:
    return DurableAttemptLedger(
        session, run_id=run_id, pricing_version=PRICING,
    )


@pytest_asyncio.fixture
async def ledger_session(db_session: AsyncSession) -> AsyncIterator[AsyncSession]:
    """Сесія, чий commit — flush: книга комітить на кожному кроці, а
    зовнішня транзакція фікстури мусить дожити до відкоту."""
    original_commit = db_session.commit
    db_session.commit = db_session.flush  # type: ignore[method-assign]
    yield db_session
    db_session.commit = original_commit  # type: ignore[method-assign]


@pytest.mark.asyncio
async def test_crash_between_dispatch_and_settlement_keeps_the_money(
    ledger_session: AsyncSession,
) -> None:
    """Симуляція падіння: спробу 1 диспетчеризовано (виклик міг дійти до
    провайдера), спробу 2 зарезервовано, але виклик не стартував —
    процес загинув. Резюме: сирота-DISPATCHED тримає свій максимум
    назавжди, нестартована резервація звільняється аудиторно."""
    run = await _make_run(ledger_session)
    bound = as_money(1.0)

    dead = _ledger(ledger_session, run.id)
    t1 = await dead.reserve(_cell(prompt="category-1"), bound)
    assert t1 is not None
    await dead.dispatch(t1)
    t2 = await dead.reserve(_cell(prompt="category-2"), bound)
    assert t2 is not None
    # …процес гине: t2 так і не диспетчеризовано, t1 не розвʼязано.

    resumed = _ledger(ledger_session, run.id)
    await resumed.reconcile()

    rows = {(r.prompt_id): r for r in (await ledger_session.execute(
        select(PresenceAttempt).where(PresenceAttempt.run_id == run.id)
    )).scalars()}
    assert rows["category-1"].state == AttemptState.DISPATCHED.value
    assert rows["category-2"].state == AttemptState.RELEASED.value
    assert "резюме" in (rows["category-2"].error or "")

    # Резервація мертвого процесу звільнена, а DISPATCHED лишився: нова
    # спроба отримує свій рядок, історія загиблої не переписана.
    t3 = await resumed.reserve(_cell(prompt="category-3"), bound)
    assert t3 is not None, "після резюме нова спроба резервується"


@pytest.mark.asyncio
async def test_worker_retry_gets_the_next_attempt_number(
    ledger_session: AsyncSession,
) -> None:
    """Повтор задачі воркера резервує ту саму клітинку знову: рядок
    мертвої спроби лишається в історії, нова отримує наступний номер —
    UNIQUE не порушується, дублікатів немає."""
    run = await _make_run(ledger_session)
    ledger = _ledger(ledger_session, run.id)

    t1 = await ledger.reserve(_cell(no=1), as_money(1.0))
    assert t1 is not None
    t2 = await ledger.reserve(_cell(no=1), as_money(1.0))
    assert t2 is not None

    numbers = sorted((await ledger_session.execute(
        select(PresenceAttempt.attempt_no)
        .where(PresenceAttempt.run_id == run.id)
    )).scalars())
    assert numbers == [1, 2]


@pytest.mark.asyncio
async def test_settlement_and_error_states_are_durable(
    ledger_session: AsyncSession,
) -> None:
    """Факт сідає на місце резерву і звільняє різницю; авторитетний нуль
    звільняє все; невідома доля тримає максимум. Усе — рядками бази."""
    run = await _make_run(ledger_session)
    ledger = _ledger(ledger_session, run.id)
    bound = as_money(1.0)

    t1 = await ledger.reserve(_cell(prompt="category-1"), bound)
    assert t1 is not None
    await ledger.dispatch(t1)
    violated = await ledger.settle_actual(t1, as_money(0.4))
    assert violated is False

    t2 = await ledger.reserve(_cell(prompt="category-2"), bound)
    assert t2 is not None
    await ledger.dispatch(t2)
    await ledger.known_zero(t2, "запит не покидав процесу")

    t3 = await ledger.reserve(_cell(prompt="category-3"), bound)
    assert t3 is not None
    await ledger.dispatch(t3)
    await ledger.unknown(t3, "таймаут")

    # Стель немає, тож облік доводиться прямо, а не через відмову
    # допуску: факт 0.4 + авторитетний нуль + невідоме, що тримає свій
    # максимум 1.0, дають 1.4.
    assert ledger.spent_by_provider()["scripted"] == Decimal("1.4")

    states = {r.prompt_id: r for r in (await ledger_session.execute(
        select(PresenceAttempt).where(PresenceAttempt.run_id == run.id)
    )).scalars()}
    assert states["category-1"].state == AttemptState.SETTLED.value
    assert states["category-1"].actual_cost_usd == Decimal("0.400000")
    assert states["category-2"].state == AttemptState.KNOWN_ZERO.value
    assert states["category-3"].state == AttemptState.UNKNOWN_COST.value
    assert states["category-1"].pricing_version == PRICING


@pytest.mark.asyncio
async def test_cost_bound_violation_is_durable_and_halts_resume(
    ledger_session: AsyncSession,
) -> None:
    """Факт понад максимум — COST_BOUND_VIOLATED у базі. Навіть новий
    процес (резюме) бачить зламаний конверт і не стартує платних
    викликів: інцидент не зникає разом із процесом."""
    run = await _make_run(ledger_session)
    ledger = _ledger(ledger_session, run.id)

    t1 = await ledger.reserve(_cell(), as_money(1.0))
    assert t1 is not None
    await ledger.dispatch(t1)
    violated = await ledger.settle_actual(t1, as_money(1.2))
    assert violated is True
    assert ledger.halted()

    row = (await ledger_session.execute(
        select(PresenceAttempt).where(PresenceAttempt.run_id == run.id)
    )).scalar_one()
    assert row.state == AttemptState.COST_BOUND_VIOLATED.value
    assert row.actual_cost_usd == Decimal("1.200000")
    assert "1.2" in (row.error or "")

    resumed = _ledger(ledger_session, run.id)
    await resumed.reconcile()
    assert resumed.halted(), "зламаний конверт видно й після рестарту"
    assert await resumed.reserve(_cell(no=2), as_money(0.1)) is None


@pytest.mark.asyncio
async def test_pricing_version_mismatch_fails_the_run_closed(
    ledger_session: AsyncSession,
) -> None:
    """Прогін, замовлений за іншим прейскурантом, не виконується: бал
    «поїхав би» мовчки. Закрите падіння, право розраховано як
    непридатне."""
    from app.services import presence_service

    policy = to_stored(DEFAULT_POLICY)
    policy["enabled"] = True
    run = PresenceRun(
        url="https://example.com", origin="https://example.com",
        brand="Acme", brand_aliases=["Acme"],
        prompt_set_version="p0-1:en",
        prompts=[{"prompt_id": "category-1", "text": "best dental clinic?",
                  "category": "category", "segment": "unbranded",
                  "language": "en"}],
        policy_snapshot={**policy, "pricing_version": "000000000000"},
        status="queued",
    )
    ledger_session.add(run)
    await ledger_session.flush()

    result = await presence_service.execute(ledger_session, run.id)
    assert result.status == "failed"
    assert "pricing_version_mismatch" in (result.error or "")
    assert result.deliverable is False
    assert result.entitlement_settled is True
    attempts = (await ledger_session.execute(
        select(PresenceAttempt).where(PresenceAttempt.run_id == run.id)
    )).scalars().all()
    assert attempts == [], "жодної платної спроби не резервувалося"


