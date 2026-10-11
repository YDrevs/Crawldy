"""Виконання одного логічного прогону: маршрути → спроби → валідація.

Правила, які тут неможливо обійти:

- кожна спроба обмежена власним таймаутом (`asyncio.wait_for`), а не
  10-хвилинним дефолтом SDK: один виклик не може зависити платний
  процес;
- кожна спроба — включно з невдалими — повертається в журналі з
  фактичним провайдером і моделлю: fallback не ховається;
- вихід провайдера потрапляє в результат лише крізь валідацію задачі:
  невалідна відповідь — це збій задачі, не збій аудиту й не «результат».

Раннер не знає ані про базу, ані про HTTP: він приймає запит, маршрути
й фабрику провайдерів, повертає дані. Персистентність — справа
застосунку.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from app.enrich.contracts import (
    AttemptOutcome,
    AttemptRecord,
    EnrichmentStatus,
    ProviderCall,
    ProviderError,
    ProviderUsage,
    RunOutcome,
    TaskRequest,
    TaskValidationError,
)
from app.enrich.providers.base import AIProvider
from app.enrich.providers.registry import get_provider
from app.enrich.routing import Routes, cost_estimate, pricing_key_for, route_for
from app.enrich.tasks.base import TaskSpec

_ERROR_TO_OUTCOME = {
    "refused": AttemptOutcome.REFUSED,
    "invalid_output": AttemptOutcome.INVALID_OUTPUT,
    "not_configured": AttemptOutcome.NOT_CONFIGURED,
    "authentication_error": AttemptOutcome.AUTHENTICATION_ERROR,
    "insufficient_quota": AttemptOutcome.INSUFFICIENT_QUOTA,
    "billing_error": AttemptOutcome.BILLING_ERROR,
    "invalid_request": AttemptOutcome.INVALID_REQUEST,
    "rate_limit": AttemptOutcome.RATE_LIMIT,
    "output_limit": AttemptOutcome.OUTPUT_LIMIT,
}

# Класи збою, після яких повтор ТИМ САМИМ запитом безглуздий: конфігурація,
# облікові дані, гроші, наш власний запит. Прогін стає FAILED, а не
# UNAVAILABLE, бо «спробувати пізніше» тут нічого не змінить.
#
# Поза цим набором лишаються rate_limit, timeout і provider_error —
# чужа погода, де чекання має сенс.
NOT_RETRYABLE = frozenset(
    {
        AttemptOutcome.NOT_CONFIGURED,
        AttemptOutcome.AUTHENTICATION_ERROR,
        AttemptOutcome.INSUFFICIENT_QUOTA,
        AttemptOutcome.BILLING_ERROR,
        AttemptOutcome.INVALID_REQUEST,
        AttemptOutcome.INVALID_OUTPUT,
        # Повтор із тим самим бюджетом обірветься так само.
        AttemptOutcome.OUTPUT_LIMIT,
    }
)


async def execute(
    spec: TaskSpec,
    request: TaskRequest,
    *,
    routes: Routes | None = None,
    provider_factory: Callable[[str], AIProvider] = get_provider,
    timeout_s: float,
    max_attempts: int,
    max_output_tokens: int,
) -> RunOutcome:
    candidates = route_for(request.task_type, routes)
    if not candidates:
        return RunOutcome(
            status=EnrichmentStatus.UNAVAILABLE,
            error="для задачі не налаштовано жодного кандидата",
        )

    attempts: list[AttemptRecord] = []
    saw_invalid = False
    last_error = ""

    for number, candidate in enumerate(candidates[:max_attempts], start=1):
        call = ProviderCall(
            system=spec.system,
            prompt=spec.render_prompt(request.input),
            schema=spec.schema,
            model=candidate.model,
            max_output_tokens=max_output_tokens,
            timeout_s=timeout_s,
        )
        started = datetime.now(UTC)
        record = AttemptRecord(
            number=number,
            provider=candidate.provider,
            model=candidate.model,
            outcome=AttemptOutcome.PROVIDER_ERROR,
            started_at=started.isoformat(),
            finished_at=started.isoformat(),
        )
        try:
            provider = provider_factory(candidate.provider)
            reply = await asyncio.wait_for(provider.generate_structured(call), timeout=timeout_s)
        except TimeoutError:
            _finish(record, started)
            record.outcome = AttemptOutcome.TIMEOUT
            record.error = f"спроба перевищила {timeout_s:g} с"
            last_error = record.error
        except ProviderError as exc:
            _finish(record, started)
            record.outcome = _ERROR_TO_OUTCOME.get(exc.category, AttemptOutcome.PROVIDER_ERROR)
            record.error_category = exc.category
            record.error = exc.detail
            last_error = exc.detail
            saw_invalid = saw_invalid or record.outcome in NOT_RETRYABLE
            # Збійна спроба теж коштує грошей — найяскравіше при обриві по
            # стелі виходу, де токени спалені сповна. Втратити оплачене
            # лише тому, що логічна задача не вдалася, не можна: рахунок
            # виставлять усе одно.
            if exc.usage is not None:
                _record_usage(record, candidate.model, exc.usage)
        except KeyError as exc:
            # Маршрут вказує на незареєстрованого провайдера — помилка
            # конфігурації, і журнал мусить її назвати, а не змовчати.
            _finish(record, started)
            record.outcome = AttemptOutcome.NOT_CONFIGURED
            record.error = str(exc)
            last_error = record.error
        else:
            _finish(record, started)
            record.model = reply.model
            record.request_id = reply.request_id
            record.input_tokens = reply.input_tokens
            record.output_tokens = reply.output_tokens
            record.cache_write_tokens = reply.cache_write_tokens
            record.cache_read_tokens = reply.cache_read_tokens
            if reply.input_tokens is not None and reply.output_tokens is not None:
                record.total_tokens = (
                    reply.input_tokens
                    + reply.output_tokens
                    + (reply.cache_write_tokens or 0)
                    + (reply.cache_read_tokens or 0)
                )
            # Ціна шукається за ЗАПИТАНОЮ моделлю, а провенанс зберігає
            # фактичну: провайдер може відпрацювати датованим знімком,
            # якого в ціннику немає.
            record.requested_model = candidate.model
            record.pricing_key = pricing_key_for(candidate.model, reply.model)
            record.cost_usd, record.pricing_version = cost_estimate(
                record.pricing_key or "",
                reply.input_tokens,
                reply.output_tokens,
                reply.cache_write_tokens,
                reply.cache_read_tokens,
            )
            try:
                clean = spec.validate(reply.output, request.input)
            except TaskValidationError as exc:
                record.outcome = AttemptOutcome.INVALID_OUTPUT
                record.error_category = "task_validation"
                record.error = str(exc)
                last_error = record.error
                saw_invalid = True
            else:
                record.outcome = AttemptOutcome.OK
                attempts.append(record)
                return RunOutcome(
                    status=EnrichmentStatus.COMPLETED, result=clean, attempts=attempts
                )
        attempts.append(record)

    # Невалідний вихід — наша межа спрацювала, повтор без зміни задачі
    # навряд чи допоможе; решта причин — зовнішня погода, спробувати
    # пізніше має сенс.
    status = EnrichmentStatus.FAILED if saw_invalid else EnrichmentStatus.UNAVAILABLE
    return RunOutcome(status=status, error=last_error or None, attempts=attempts)


def _record_usage(record: AttemptRecord, requested: str, usage: ProviderUsage) -> None:
    """Токени, ціновий ключ і вартість — однаково для успіху й для збою."""
    record.input_tokens = usage.input_tokens
    record.output_tokens = usage.output_tokens
    record.cache_write_tokens = usage.cache_write_tokens
    record.cache_read_tokens = usage.cache_read_tokens
    if usage.input_tokens is not None and usage.output_tokens is not None:
        record.total_tokens = (
            usage.input_tokens
            + usage.output_tokens
            + (usage.cache_write_tokens or 0)
            + (usage.cache_read_tokens or 0)
        )
    record.requested_model = requested
    record.pricing_key = pricing_key_for(requested, usage.model or record.model)
    record.cost_usd, record.pricing_version = cost_estimate(
        record.pricing_key or "",
        usage.input_tokens,
        usage.output_tokens,
        usage.cache_write_tokens,
        usage.cache_read_tokens,
    )


def _finish(record: AttemptRecord, started: datetime) -> None:
    finished = datetime.now(UTC)
    record.finished_at = finished.isoformat()
    record.latency_ms = int((finished - started).total_seconds() * 1000)
