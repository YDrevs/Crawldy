"""Книга платних спроб присутності: довговічна резервація до виклику.

Стель витрат ця книга більше не має. Вартість прогону обмежена його
сіткою (промпти × режими × повтори × провайдери), а видима — в таблиці
собівартості адмінки. Стелі знято свідомо: сконфігуровані величини
($10 на прогін, $5 на провайдера) були нижчі за виміряну вартість
повного аудиту ($10.81, сама Anthropic $6.21), тож обрізали б перший же
справжній клієнтський прогін — і число описувало б наш ліміт, а не
присутність клієнта.

Що книга робить далі: резервує ЗАХИСНИЙ максимум спроби (з документованих
меж запиту й версіонованого прейскуранта — жодних спостережених середніх)
і комітить рядок у базу ДО мережевого виклику (див. DurableAttemptLedger
у сервісі), тож падіння процесу між диспетчеризацією і персистенцією
відповіді не «звільняє» гроші: нерозвʼязана DISPATCHED-спроба лишається в
історії як є. Памʼятна книга тут — та сама семантика без бази, для
юніт-тестів раннера.

Факт, що перевищив зарезервований максимум, ламає ціновий конверт: спроба
стає COST_BOUND_VIOLATED, прогін зупиняється, і це ЄДИНА причина, з якої
допуск тепер відмовляє. Біллінгові ліміти акаунта провайдера — окремий
контроль деплою.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import Protocol


def as_money(value: float | str | Decimal) -> Decimal:
    """Float конфігурації → точна величина. Через str: Decimal(0.1)
    успадкував би двійкове наближення, Decimal("0.1") — ні."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class AttemptState(StrEnum):
    """Життя однієї платної спроби. Історія не переписується."""

    RESERVED = "reserved"          # допуск пройдено, виклик ще не почато
    DISPATCHED = "dispatched"      # мережевий виклик стартував
    SETTLED = "settled"            # факт відомий і записаний
    KNOWN_ZERO = "known_zero"      # авторитетно відомо: не тарифіковано
    UNKNOWN_COST = "unknown_cost"  # доля грошей невідома: тримаємо резерв
    RELEASED = "released"          # виклик так і не стартував
    COST_BOUND_VIOLATED = "cost_bound_violated"  # факт > максимуму: конверт зламано


# Стани, чия сума рахується як витрачене за фактом. RELEASED і
# KNOWN_ZERO коштують нуль; UNKNOWN_COST тримає зарезервований максимум
# і додається окремо там, де рахується витрачене.
COMMITTED_AT_ACTUAL = frozenset({
    AttemptState.SETTLED, AttemptState.COST_BOUND_VIOLATED,
})


# Стелі, які адаптери СПРАВДІ ставлять у запит, — єдине джерело для
# формули максимуму. Пошуки None — запит не вміє обмежити кількість
# тарифікованих пошуків (Gemini Interactions), і максимум нерахований.
@dataclass(frozen=True, slots=True)
class RequestCeilings:
    max_output_tokens: int
    max_searches: int | None


REQUEST_CEILINGS: dict[str, RequestCeilings] = {
    # Messages API: max_tokens (вихід) + max_uses інструмента пошуку.
    "anthropic": RequestCeilings(max_output_tokens=1500, max_searches=3),
    # Responses API: max_output_tokens (включно з reasoning) +
    # max_tool_calls (документований параметр обмеження викликів).
    "openai": RequestCeilings(max_output_tokens=1500, max_searches=3),
    # Agent API: max_output_tokens + max_tool_calls (документовані).
    "perplexity": RequestCeilings(max_output_tokens=1500, max_searches=3),
    # generateContent + gemini-2.5-flash (бекенд vertex_ai; ті самі
    # стелі й у developer_api-сумісності): вихід обмежує
    # maxOutputTokens, thinking вимкнено (thinkingBudget=0 —
    # документовано для 2.5 Flash), а одиниця білення заземлення —
    # ЗАЗЕМЛЕНИЙ ПРОМПТ: «Even if multiple Grounding Queries are sent,
    # there is only one charge for a Grounding Prompt» (Vertex-прайс,
    # 2026-09-01). Тому max_searches=1 — стеля ОДИНИЦЬ БІЛЕННЯ на
    # запит, а не кількості внутрішніх пошуків. Для gemini-3.x, що
    # білиться за кожен запит без документованої стелі кількості,
    # максимум лишається нерахованим — це вирішує
    # max_searches_boundable=False у каталозі, і 3.x закритий
    # (fail closed) незалежно від цього рядка.
    "google": RequestCeilings(max_output_tokens=1500, max_searches=1),
    "scripted": RequestCeilings(max_output_tokens=1500, max_searches=3),
}


@dataclass(slots=True, frozen=True)
class AttemptCell:
    """Ідентичність спроби: клітинка + номер спроби."""

    provider: str
    prompt_id: str
    mode: str
    run_index: int
    attempt_no: int


@dataclass(slots=True)
class AttemptTicket:
    """Квиток зарезервованої спроби, який супроводжує виклик."""

    attempt_id: uuid.UUID
    cell: AttemptCell
    reserved_max: Decimal


class AttemptLedger(Protocol):
    """Книга платних спроб. Допуск атомарний; історія append-only.

    Після скасування стель `reserve` відмовляє лише зупиненому прогону
    (зламаний ціновий конверт), і така відмова остаточна: чекати нема на
    що, тож окремого питання «чи вміститься коли-небудь» більше немає.
    """

    async def reserve(
        self, cell: AttemptCell, bound: Decimal
    ) -> AttemptTicket | None: ...

    async def dispatch(self, ticket: AttemptTicket) -> None: ...

    async def settle_actual(
        self, ticket: AttemptTicket, actual: Decimal,
        *, provider_request_id: str | None = None,
    ) -> bool:
        """Записати факт. True — конверт зламано (факт > максимуму):
        спроба стає COST_BOUND_VIOLATED, і прогін мусить зупинитися."""
        ...

    async def known_zero(self, ticket: AttemptTicket, detail: str) -> None: ...

    async def unknown(self, ticket: AttemptTicket, detail: str) -> None: ...

    def halted(self) -> bool: ...

    def spent_by_provider(self) -> dict[str, Decimal]: ...


@dataclass(slots=True)
class _MemoryAttempt:
    cell: AttemptCell
    state: AttemptState
    reserved: Decimal
    actual: Decimal | None = None


@dataclass(slots=True)
class MemoryAttemptLedger:
    """Та сама семантика без бази — для юніт-тестів раннера."""

    _attempts: list[_MemoryAttempt] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _halted: bool = False

    async def reserve(
        self, cell: AttemptCell, bound: Decimal
    ) -> AttemptTicket | None:
        async with self._lock:
            if self._halted:
                return None
            self._attempts.append(_MemoryAttempt(
                cell=cell, state=AttemptState.RESERVED, reserved=bound))
            return AttemptTicket(
                attempt_id=uuid.uuid4(), cell=cell, reserved_max=bound)

    def _find(self, ticket: AttemptTicket) -> _MemoryAttempt:
        for a in reversed(self._attempts):
            if a.cell == ticket.cell:
                return a
        raise LookupError(str(ticket.cell))

    async def dispatch(self, ticket: AttemptTicket) -> None:
        async with self._lock:
            self._find(ticket).state = AttemptState.DISPATCHED

    async def settle_actual(
        self, ticket: AttemptTicket, actual: Decimal,
        *, provider_request_id: str | None = None,
    ) -> bool:
        del provider_request_id
        async with self._lock:
            attempt = self._find(ticket)
            attempt.actual = actual
            if actual > ticket.reserved_max:
                attempt.state = AttemptState.COST_BOUND_VIOLATED
                self._halted = True
                return True
            attempt.state = AttemptState.SETTLED
            return False

    async def known_zero(self, ticket: AttemptTicket, detail: str) -> None:
        del detail
        async with self._lock:
            attempt = self._find(ticket)
            attempt.state = AttemptState.KNOWN_ZERO
            attempt.actual = Decimal("0")

    async def unknown(self, ticket: AttemptTicket, detail: str) -> None:
        del detail
        async with self._lock:
            self._find(ticket).state = AttemptState.UNKNOWN_COST

    def halted(self) -> bool:
        return self._halted

    def spent_by_provider(self) -> dict[str, Decimal]:
        out: dict[str, Decimal] = {}
        for a in self._attempts:
            if a.state in COMMITTED_AT_ACTUAL and a.actual is not None:
                out[a.cell.provider] = out.get(
                    a.cell.provider, Decimal("0")) + a.actual
            elif a.state is AttemptState.UNKNOWN_COST:
                out[a.cell.provider] = out.get(
                    a.cell.provider, Decimal("0")) + a.reserved
        return out


__all__ = [
    "COMMITTED_AT_ACTUAL",
    "REQUEST_CEILINGS",
    "AttemptCell",
    "AttemptLedger",
    "AttemptState",
    "AttemptTicket",
    "MemoryAttemptLedger",
    "RequestCeilings",
    "as_money",
]
