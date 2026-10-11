"""Раннер присутності: промпти × провайдери × режими × повтори, під бюджетом.

Правила грошей:
* стеля — з політики, не з коду; окремо на провайдера й на весь прогін;
* витрачене рахується з фактичного usage за цінами каталогу;
* коли стелю досягнуто, нові виклики НЕ починаються — решта клітинок
  записується як BUDGET_EXHAUSTED (не спостережено, не нуль);
* fallback на дорожчу модель не існує як шлях: модель фіксована
  політикою на весь прогін.

Правила повторів: лише RETRYABLE-статуси, не більше retry_limit разів,
без зміни моделі. Відмова провайдера відповідати (REFUSED) не
повторюється — це теж спостереження.

Режими: клітинка несе режим. Natural надсилає текст промпту як є;
explicit додає інструкцію заземлення й — де API це вміє (OpenAI) —
примушує інструмент пошуку. Чи стався пошук насправді, каже запис.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

from app.ai.catalog import (
    call_cost_usd,
    capability,
    execution_configured,
    max_attempt_cost_usd,
)
from app.presence.budget import (
    REQUEST_CEILINGS,
    AttemptCell,
    AttemptLedger,
    MemoryAttemptLedger,
    as_money,
)
from app.presence.contracts import (
    RETRYABLE_STATUSES,
    Mode,
    ObservationRecord,
    ObservationStatus,
    PresenceProviderError,
    PromptSet,
)
from app.presence.normalize import failure, interpret
from app.presence.policy import PresencePolicy, effective_backend
from app.presence.prompts import explicit_suffix
from app.presence.providers.base import PresenceProvider
from app.presence.providers.registry import get_provider


@dataclass(slots=True)
class RunTotals:
    observations: int = 0
    ok: int = 0
    cost_usd: float = 0.0
    cost_by_provider: dict[str, float] = field(default_factory=dict)
    # Конверт зламано: факт перевищив зарезервований максимум. Прогін
    # зупинено, і це операційний інцидент, а не доказ, що кап утримався.
    cost_bound_violation: str | None = None


@dataclass(slots=True)
class _Cell:
    provider: str
    prompt_index: int
    mode: Mode
    run_index: int


def planned_cells(policy: PresencePolicy, prompt_count: int) -> int:
    """Скільки спостережень замовляє політика для одного провайдера."""
    prompts = min(prompt_count, policy.max_prompts)
    return prompts * len(policy.modes) * policy.runs_per_prompt


async def execute_run(
    *,
    policy: PresencePolicy,
    prompt_set: PromptSet,
    origin: str,
    brand_aliases: tuple[str, ...],
    done_cells: set[tuple[str, str, str, int]] = frozenset(),  # type: ignore[assignment]
    providers_override: dict[str, PresenceProvider] | None = None,
    ledger: AttemptLedger | None = None,
) -> tuple[list[ObservationRecord], RunTotals]:
    """Виконує прогін і повертає записи в детермінованому порядку.

    `done_cells` — клітинки (провайдер, промпт, режим, повтор), що вже
    мають рядки (перезапуск задачі після падіння): вони пропускаються, і
    повторний запуск не платить двічі й не створює дублікатів.

    `ledger` — книга платних спроб: у продукті довговічна (база),
    у юніт-тестах памʼятна з тією самою семантикою. Без неї
    створюється памʼятна — ШЛЯХ ЛИШЕ ДЛЯ ТЕСТІВ без грошей.

    `providers_override` — інʼєкція для тестів/пілоту; в проді None.
    """
    prompts = prompt_set.prompts[: policy.max_prompts]
    modes = tuple(Mode(m) for m in policy.modes)
    cells: list[_Cell] = [
        _Cell(provider=name, prompt_index=i, mode=mode, run_index=r)
        for name in sorted(policy.active_providers())
        for i in range(len(prompts))
        for mode in modes
        for r in range(1, policy.runs_per_prompt + 1)
    ]

    adapters: dict[str, PresenceProvider | None] = {}
    for name in sorted(policy.active_providers()):
        backend = effective_backend(name, policy.providers[name])
        if providers_override and name in providers_override:
            adapters[name] = providers_override[name]
        elif execution_configured(name, backend):
            adapters[name] = get_provider(
                name, policy.providers[name].model,
                timeout_s=policy.provider_timeout_s,
                backend=backend,
            )
        else:
            # Немає конфігурації виконання (ключ або, для vertex_ai,
            # проєкт) — клітинки стануть NOT_CONFIGURED ДО резервації.
            adapters[name] = None

    totals = RunTotals()
    records: list[ObservationRecord] = []
    lock = asyncio.Lock()
    semaphore = asyncio.Semaphore(policy.concurrency)

    # Книга спроб: резервація стає довговічною ЩЕ ДО мережевого виклику,
    # тож падіння процесу грошей не звільняє. Стель витрат більше немає —
    # вартість прогону обмежена самою сіткою (промпти × режими × повтори
    # × провайдери) і видима в таблиці собівартості адмінки.
    if ledger is None:
        ledger = MemoryAttemptLedger()

    async def _observe(cell: _Cell) -> ObservationRecord:
        prompt = prompts[cell.prompt_index]
        provider_policy = policy.providers[cell.provider]
        adapter = adapters[cell.provider]
        country = provider_policy.default_country
        # Тривалість міряє РОБОТУ клітинки, не чергу: під gather усі
        # клітинки стартують одночасно, і мітка на старті рахувала б
        # очікування семафора (пілот показав «медіану» 389 с на клітинку
        # при реальних ~10-40 с виклику).
        started = time.monotonic()
        work_ms = 0

        sent_text = prompt.text
        if cell.mode is Mode.EXPLICIT:
            sent_text = prompt.text + explicit_suffix(prompt.language)

        def _elapsed_ms() -> int:
            return work_ms if work_ms else int(
                (time.monotonic() - started) * 1000)

        def _fail(status: ObservationStatus, detail: str,
                  retries: int = 0) -> ObservationRecord:
            return failure(
                status, detail,
                prompt=prompt, prompt_set_version=prompt_set.version,
                provider=cell.provider, model=provider_policy.model,
                tool_version=adapter.tool_version if adapter else "",
                run_index=cell.run_index, country=country,
                mode=cell.mode, retries=retries, duration_ms=_elapsed_ms(),
            )

        if adapter is None:
            return _fail(ObservationStatus.NOT_CONFIGURED,
                         "ключ провайдера не налаштовано")

        cap = capability(cell.provider, provider_policy.model)
        if cap is None:
            return _fail(ObservationStatus.NOT_CONFIGURED,
                         "модель відсутня в каталозі — ціна невідома")

        # Захисний максимум спроби — З ДОКУМЕНТОВАНИХ МЕЖ: стеля входу
        # (контекстне вікно/вхідний ліміт API), наша стеля виходу і
        # документований ліміт кількості пошуків. Жодних спостережених
        # середніх. Нерахований максимум (немає стелі входу або запит не
        # вміє обмежити пошуки — Gemini Interactions) закриває платний
        # шлях, і це стан НАШОЇ конфігурації, не збій провайдера.
        ceilings = REQUEST_CEILINGS.get(cell.provider)
        bound = (
            max_attempt_cost_usd(
                cap,
                max_output_tokens=ceilings.max_output_tokens,
                max_searches=ceilings.max_searches,
            )
            if ceilings is not None else None
        )
        if bound is None:
            return _fail(ObservationStatus.BUDGET_COST_BOUND_UNAVAILABLE,
                         "budget_cost_bound_unavailable: захисний максимум "
                         "спроби нерахований з документованих меж")

        attempts = 0
        while True:
            attempts += 1
            if ledger.halted():
                return _fail(
                    ObservationStatus.BUDGET_EXHAUSTED,
                    "прогін зупинено: конверт цін зламано "
                    "(cost_bound_violated)",
                    retries=attempts - 1,
                )
            try:
                async with semaphore:
                    # КОЖНА платна спроба отримує ДОВГОВІЧНУ резервацію
                    # свого максимуму проти обох стель ДО виклику, і
                    # резервація комітиться раніше за мережу: падіння
                    # процесу після диспетчеризації не звільняє грошей.
                    attempt_cell = AttemptCell(
                        provider=cell.provider,
                        prompt_id=prompt.prompt_id,
                        mode=cell.mode.value,
                        run_index=cell.run_index,
                        attempt_no=attempts,
                    )
                    ticket = await ledger.reserve(attempt_cell, bound)
                    # Стель витрат немає, тож допуск відмовляє з однієї
                    # причини: ціновий конверт зламано (факт перевищив
                    # зарезервований максимум) і прогін зупинено. Така
                    # відмова остаточна — чекати тут нема на що.
                    if ticket is None:
                        return _fail(
                            ObservationStatus.BUDGET_EXHAUSTED,
                            "прогін зупинено: конверт цін зламано "
                            "(cost_bound_violated)",
                            retries=attempts - 1,
                        )
                    await ledger.dispatch(ticket)
                    call_started = time.monotonic()
                    try:
                        answer = await adapter.observe(
                            sent_text, country=country,
                            require_search=cell.mode is Mode.EXPLICIT,
                        )
                    except PresenceProviderError as exc:
                        # Провайдеро-специфічна звірка: KNOWN_ZERO лише
                        # там, де це авторитетно відомо (адаптер каже);
                        # решта — UNKNOWN_COST, і книга чесно утримує
                        # зарезервований максимум, а не нуль.
                        if exc.incurred_usd is None:
                            await ledger.unknown(ticket, exc.detail)
                        else:
                            await ledger.known_zero(ticket, exc.detail)
                        raise
                    finally:
                        work_ms += int(
                            (time.monotonic() - call_started) * 1000)
            except PresenceProviderError as exc:
                if exc.status in RETRYABLE_STATUSES and attempts <= policy.retry_limit:
                    await asyncio.sleep(min(2.0 * attempts, 5.0))
                    continue
                return _fail(exc.status, exc.detail, retries=attempts - 1)
            # Фактична вартість провайдера авторитетна для обліку; наш
            # розрахунок із каталогу — консервативний запасний шлях.
            cost = answer.provider_cost_usd
            if cost is None:
                cost = call_cost_usd(
                    cap,
                    input_tokens=answer.usage.input_tokens,
                    output_tokens=answer.usage.output_tokens,
                    searches=answer.usage.searches,
                )
            # Факт замінює резервацію. Факт БІЛЬШИЙ за максимум означає,
            # що конверт цін недійсний: спроба стає COST_BOUND_VIOLATED,
            # прогін зупиняється — це інцидент, а не «кап утримався».
            violated = await ledger.settle_actual(
                ticket, as_money(cost),
                provider_request_id=answer.provider_request_id,
            )
            async with lock:
                totals.cost_usd += cost
                totals.cost_by_provider[cell.provider] = (
                    totals.cost_by_provider.get(cell.provider, 0.0) + cost
                )
                if violated and totals.cost_bound_violation is None:
                    totals.cost_bound_violation = (
                        f"{cell.provider}: факт {cost:.6f} > максимум "
                        f"{bound} (спроба {prompt.prompt_id}/"
                        f"{cell.mode.value}/{cell.run_index})"
                    )
            return interpret(
                answer,
                prompt=prompt, prompt_set_version=prompt_set.version,
                provider=cell.provider, tool_version=adapter.tool_version,
                run_index=cell.run_index, country=country,
                origin=origin, brand_aliases=brand_aliases, cost_usd=cost,
                mode=cell.mode, sent_text=sent_text,
                retries=attempts - 1, duration_ms=_elapsed_ms(),
            )

    pending = [
        cell for cell in cells
        if (cell.provider, prompts[cell.prompt_index].prompt_id,
            cell.mode.value, cell.run_index)
        not in done_cells
    ]
    results = await asyncio.gather(*(_observe(cell) for cell in pending))
    for record in results:
        records.append(record)
        totals.observations += 1
        if record.status is ObservationStatus.OK:
            totals.ok += 1
    return records, totals
