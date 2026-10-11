"""Операційні категорії збою: що саме сталося і чи варто чекати.

Дві пари тут коштували проєкту реального часу, тож перевіряються окремо:

- «ключа немає» проти «ключ відхилено». Пілот зупинився на мертвому
  ключі, і категорія `not_configured` у журналі казала б неправду: ключ
  був, його відхилив провайдер.
- «квота вичерпана» проти «частота перевищена». В OpenAI обидві приходять
  під HTTP 429, але чекати варто лише на другій.

Мережі немає: винятки SDK будуються локально.
"""

from __future__ import annotations

from typing import ClassVar

import httpx
import pytest

from app.enrich.contracts import AttemptOutcome, ProviderCall, ProviderError
from app.enrich.providers.anthropic import AnthropicProvider
from app.enrich.providers.anthropic import _category_of as anthropic_category
from app.enrich.providers.openai import OpenAIProvider
from app.enrich.providers.openai import _category_of as openai_category
from app.enrich.runner import NOT_RETRYABLE

CALL = ProviderCall(
    system="s", prompt="p", schema={"type": "object"}, model="m",
    max_output_tokens=100, timeout_s=5.0,
)


def _request(url: str) -> httpx.Request:
    return httpx.Request("POST", url)


def _openai_error(kind: str, status: int, body: dict | None = None):
    import openai

    exc_type = getattr(openai, kind)
    request = _request("https://api.openai.com/v1/responses")
    return exc_type("boom", response=httpx.Response(status, request=request), body=body)


def _anthropic_error(kind: str, status: int, body: dict | None = None):
    import anthropic

    exc_type = getattr(anthropic, kind)
    request = _request("https://api.anthropic.com/v1/messages")
    return exc_type("boom", response=httpx.Response(status, request=request), body=body)


# ── конфігурація проти облікових даних ───────────────────────────────────


@pytest.mark.asyncio
async def test_missing_openai_key_is_not_configured(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.openai_api_key", None)
    with pytest.raises(ProviderError) as exc:
        await OpenAIProvider().generate_structured(CALL)
    assert exc.value.category == "not_configured"


@pytest.mark.asyncio
async def test_missing_anthropic_key_is_not_configured(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.anthropic_api_key", None)
    with pytest.raises(ProviderError) as exc:
        await AnthropicProvider().generate_structured(CALL)
    assert exc.value.category == "not_configured"


def test_rejected_openai_key_is_authentication_not_not_configured():
    """Ключ є, провайдер його відхилив — це інша подія й інший винуватець."""
    body = {"error": {"message": "Incorrect API key provided", "code": "invalid_api_key"}}
    assert openai_category(_openai_error("AuthenticationError", 401, body)) == (
        "authentication_error"
    )


def test_rejected_anthropic_key_is_authentication_not_not_configured():
    """Саме цей випадок зупинив пілот, і журнал мусить назвати його точно."""
    body = {"type": "error", "error": {"type": "authentication_error",
                                       "message": "API key is invalid."}}
    assert anthropic_category(_anthropic_error("AuthenticationError", 401, body)) == (
        "authentication_error"
    )


def test_permission_denied_is_also_authentication():
    assert openai_category(_openai_error("PermissionDeniedError", 403)) == "authentication_error"
    assert anthropic_category(
        _anthropic_error("PermissionDeniedError", 403)
    ) == "authentication_error"


# ── 429 означає три різні речі ───────────────────────────────────────────


def test_openai_quota_exhaustion_is_not_rate_limit():
    """Однаковий HTTP 429, різні наслідки: чекати тут марно."""
    body = {"error": {"message": "You exceeded your current quota",
                      "type": "insufficient_quota", "code": "insufficient_quota"}}
    assert openai_category(_openai_error("RateLimitError", 429, body)) == "insufficient_quota"


def test_openai_true_throttling_stays_rate_limit():
    body = {"error": {"message": "Rate limit reached for gpt-5.4-mini",
                      "type": "requests", "code": "rate_limit_exceeded"}}
    assert openai_category(_openai_error("RateLimitError", 429, body)) == "rate_limit"


def test_openai_429_without_any_code_defaults_to_rate_limit():
    """Без структурного коду не вигадуємо платіжну проблему зі статусу."""
    assert openai_category(_openai_error("RateLimitError", 429, None)) == "rate_limit"


def test_openai_billing_state_is_billing_error():
    body = {"error": {"message": "Billing hard limit has been reached",
                      "code": "billing_hard_limit_reached"}}
    assert openai_category(_openai_error("RateLimitError", 429, body)) == "billing_error"


def test_openai_billing_code_wins_over_http_status():
    """Платіжний стан інколи приходить 400-ю: код важить більше за статус."""
    body = {"error": {"message": "Account is not active", "code": "billing_not_active"}}
    assert openai_category(_openai_error("BadRequestError", 400, body)) == "billing_error"


def test_anthropic_low_credit_is_billing_not_invalid_request():
    """Anthropic не дає окремого коду — ознака лишається в тексті."""
    body = {"type": "error", "error": {
        "type": "invalid_request_error",
        "message": "Your credit balance is too low to access the Anthropic API.",
    }}
    assert anthropic_category(_anthropic_error("BadRequestError", 400, body)) == "billing_error"


def test_anthropic_schema_rejection_stays_invalid_request():
    """Той самий 400, але про схему — не про гроші. Саме він спинив пілот."""
    body = {"type": "error", "error": {
        "type": "invalid_request_error",
        "message": "output_config.format.schema: For 'integer' type, property "
                   "'minimum' is not supported",
    }}
    assert anthropic_category(_anthropic_error("BadRequestError", 400, body)) == "invalid_request"


# ── решта категорій ──────────────────────────────────────────────────────


def test_invalid_structured_output_request_is_invalid_request():
    body = {"error": {"message": "Invalid schema for response_format", "code": "invalid_schema"}}
    assert openai_category(_openai_error("BadRequestError", 400, body)) == "invalid_request"


def test_timeout_maps_to_timeout_for_both_providers():
    import anthropic
    import openai

    assert openai_category(
        openai.APITimeoutError(request=_request("https://api.openai.com/v1/responses"))
    ) == "timeout"
    assert anthropic_category(
        anthropic.APITimeoutError(request=_request("https://api.anthropic.com/v1/messages"))
    ) == "timeout"


def test_transient_server_and_connection_failures_are_provider_error():
    import openai

    assert openai_category(_openai_error("InternalServerError", 500)) == "provider_error"
    assert openai_category(
        openai.APIConnectionError(request=_request("https://api.openai.com/v1/responses"))
    ) == "provider_error"
    assert anthropic_category(_anthropic_error("InternalServerError", 500)) == "provider_error"
    assert anthropic_category(_anthropic_error("OverloadedError", 529)) == "provider_error"


# ── семантика повтору ────────────────────────────────────────────────────


def test_retry_semantics_match_the_operational_meaning():
    """Чекати варто лише там, де чекання щось змінює."""
    for outcome in (
        AttemptOutcome.NOT_CONFIGURED,
        AttemptOutcome.AUTHENTICATION_ERROR,
        AttemptOutcome.INSUFFICIENT_QUOTA,
        AttemptOutcome.BILLING_ERROR,
        AttemptOutcome.INVALID_REQUEST,
        AttemptOutcome.INVALID_OUTPUT,
    ):
        assert outcome in NOT_RETRYABLE, f"{outcome} має бути неповторюваним"

    for outcome in (
        AttemptOutcome.RATE_LIMIT,
        AttemptOutcome.TIMEOUT,
        AttemptOutcome.PROVIDER_ERROR,
    ):
        assert outcome not in NOT_RETRYABLE, f"{outcome} мав лишитися повторюваним"


def test_provider_wording_never_reaches_the_neutral_runner():
    """Слова провайдера лишаються в адаптері; раннер знає лише категорії."""
    from pathlib import Path

    runner = (Path(__file__).resolve().parents[1] / "app" / "enrich" / "runner.py").read_text(
        encoding="utf-8"
    )
    for phrase in ("credit balance", "insufficient_quota code", "billing_hard_limit", "429"):
        assert phrase not in runner, f"формулювання провайдера протекло в раннер: {phrase}"


# ── цінова ідентичність: датований знімок моделі ─────────────────────────


def test_dated_provider_snapshot_still_resolves_to_a_price():
    """Перший живий виклик OpenAI повернув `gpt-5.4-mini-2026-03-17`.

    Провенанс мусить зберегти фактичне імʼя, але ціна за ним не
    знаходилась — і вартість записалась NULL при відомій ставці.
    """
    from app.enrich.routing import cost_estimate, pricing_key_for

    key = pricing_key_for("gpt-5.4-mini", "gpt-5.4-mini-2026-03-17")
    assert key == "gpt-5.4-mini"

    cost, version = cost_estimate(key or "", 4052, 607, None, 0)
    assert cost is not None and cost > 0
    assert version


def test_pricing_key_is_explicit_not_a_suffix_stripping_regex():
    """Регулярка так само радо зробила б із `gpt-5.4-mini` модель `gpt-5.4`.

    Тому ключем стає ЗАПИТАНА модель, а фактична лише перевіряється на
    те, що вона є її знімком.
    """
    from app.enrich.routing import pricing_key_for

    # Той самий рядок — очевидно так.
    assert pricing_key_for("claude-opus-5", "claude-opus-5") == "claude-opus-5"
    # Знімок запитаної — так.
    assert pricing_key_for("gpt-5.4-mini", "gpt-5.4-mini-2026-03-17") == "gpt-5.4-mini"
    # Інша модель — ціну не вгадуємо.
    assert pricing_key_for("gpt-5.4-mini", "gpt-5.4") is None
    assert pricing_key_for("gpt-5.4-mini", "gpt-5.6-luna") is None
    # Модель поза цінником — теж None, а не здогад.
    assert pricing_key_for("some-unpriced-model", "some-unpriced-model") is None


def test_provenance_keeps_all_three_model_identities_apart():
    """`model`, `requested_model` і `pricing_key` — різні величини."""
    from app.enrich.contracts import AttemptOutcome, AttemptRecord

    record = AttemptRecord(
        number=1, provider="openai", model="gpt-5.4-mini-2026-03-17",
        outcome=AttemptOutcome.OK, started_at="", finished_at="",
        requested_model="gpt-5.4-mini", pricing_key="gpt-5.4-mini",
    )
    assert record.model != record.requested_model, "знімок не можна підміняти чистим імʼям"
    assert record.pricing_key == record.requested_model


# ── детектор: чужа гарантія проти нашої обіцянки ─────────────────────────


def test_customer_guarantee_described_is_not_an_unsupported_claim():
    """rightpricerooter.com справді дає гарантію; переказати її — робота."""
    from app.enrich.benchmark import unsupported_claims

    source = "Whether the job is big or small, we guarantee to be honest and courteous."
    # Модель написала множину там, де джерело має однину — це переказ.
    assert unsupported_claims("Homepage introduces the company's guarantees", source) == []


def test_our_own_outcome_promise_is_always_flagged():
    """Що б сайт собі не гарантував, позицій наш звіт не міряв."""
    from app.enrich.benchmark import unsupported_claims

    source = "we guarantee to be honest"
    assert unsupported_claims("this will guarantee rankings", source)
    assert unsupported_claims("expect 30% more traffic", source)
    assert unsupported_claims("your site will rank higher", source)


def test_invented_money_and_effort_stay_flagged_even_with_a_source():
    from app.enrich.benchmark import unsupported_claims

    source = "24 hour emergency service, plans from $0"
    assert unsupported_claims("this takes 12 hours", source), "інший строк — інше твердження"
    assert unsupported_claims("saves $5,000 a year", source), "вигадана економія"
    # А те, що справді є у вході, лишається цитатою.
    assert unsupported_claims("offers 24 hour service", source) == []
    assert unsupported_claims("plans start at $0", source) == []


# ── обрив по стелі виходу: спільна категорія й збережений облік ──────────


def test_anthropic_max_tokens_is_an_output_limit_not_malformed_json():
    """Живий прогін записав пʼять обривів як «відповідь не JSON».

    Причина була неправильна, і разом із нею губився облік: адаптер
    перевіряв лише `refusal`, тож обрізаний JSON летів у парсер.
    """
    import asyncio

    from app.enrich.providers.anthropic import AnthropicProvider

    class _Truncated:
        stop_reason = "max_tokens"
        model = "claude-opus-5"
        content: ClassVar[list] = [
            type("B", (), {"type": "text", "text": '{"groups": ['})()
        ]
        usage = type("U", (), {
            "input_tokens": 12, "output_tokens": 3000,
            "cache_creation_input_tokens": 7789, "cache_read_input_tokens": 0,
        })()

    class _Messages:
        async def create(self, **kwargs):
            return _Truncated()

    provider = AnthropicProvider()
    provider._client = type("C", (), {"messages": _Messages()})()

    with pytest.raises(ProviderError) as exc:
        asyncio.run(
            provider.generate_structured(
                ProviderCall(system="s", prompt="p", schema={}, model="claude-opus-5",
                             max_output_tokens=3000, timeout_s=5.0)
            )
        )
    assert exc.value.category == "output_limit"
    # Облік спожитого не губиться: рахунок виставлять усе одно.
    assert exc.value.usage is not None
    assert exc.value.usage.output_tokens == 3000
    assert exc.value.usage.cache_write_tokens == 7789


def test_output_limit_is_not_retryable_with_the_same_budget():
    """Повтор із тією самою стелею обірветься так само."""
    assert AttemptOutcome.OUTPUT_LIMIT in NOT_RETRYABLE


def test_failed_attempt_usage_reaches_the_ledger():
    """Збійна спроба теж коштує грошей — і мусить це показати."""
    from app.enrich.contracts import AttemptOutcome as AO
    from app.enrich.contracts import AttemptRecord, ProviderUsage
    from app.enrich.runner import _record_usage

    record = AttemptRecord(
        number=1, provider="anthropic", model="claude-opus-5",
        outcome=AO.OUTPUT_LIMIT, started_at="", finished_at="",
    )
    _record_usage(
        record,
        "claude-opus-5",
        ProviderUsage(input_tokens=12, output_tokens=3000,
                      cache_write_tokens=7789, cache_read_tokens=0,
                      model="claude-opus-5"),
    )
    assert record.output_tokens == 3000
    assert record.cost_usd is not None and record.cost_usd > 0
    assert record.pricing_key == "claude-opus-5"


def test_timeout_leaves_cost_unknown_rather_than_estimated():
    """Таймаут не дає обліку — і вигадувати рахунок не можна."""
    from app.enrich.contracts import AttemptOutcome as AO
    from app.enrich.contracts import AttemptRecord

    record = AttemptRecord(
        number=1, provider="openai", model="gpt-5.4-mini",
        outcome=AO.TIMEOUT, started_at="", finished_at="",
    )
    assert record.cost_usd is None
    assert record.input_tokens is None


# ── бюджети виконання ───────────────────────────────────────────────────


def test_execution_budgets_are_per_task_not_global():
    """Однакове число для різних за обсягом робіт — не однакові умови."""
    from app.enrich.budgets import budget_for
    from app.enrich.contracts import TaskType

    site = budget_for(TaskType.SITE_UNDERSTANDING)
    root = budget_for(TaskType.ROOT_CAUSE_GROUPING)
    plan = budget_for(TaskType.REMEDIATION_PLAN)

    assert site.max_output_tokens == 3000 and site.timeout_s == 45.0
    assert root.max_output_tokens == 8000 and root.timeout_s == 120.0
    assert plan.max_output_tokens == 8000 and plan.timeout_s == 120.0
    assert root.max_output_tokens > site.max_output_tokens


def test_budgets_carry_no_provider_or_model_dimension():
    """Бюджет належить задачі. Інакше порівняння міряло б налаштування."""
    import inspect

    from app.enrich import budgets

    source = inspect.getsource(budgets)
    for word in ("anthropic", "openai", "claude", "gpt-", "opus", "sonnet"):
        assert word not in source.lower(), f"бюджет знає про «{word}»"


def test_budgets_are_recorded_in_run_provenance():
    """Два прогони під різними стелями непорівнянні — це має бути видно."""
    from app.enrich.budgets import budgets_provenance

    provenance = budgets_provenance()
    assert set(provenance) == {"site_understanding", "root_cause_grouping", "remediation_plan"}
    assert provenance["root_cause_grouping"]["max_output_tokens"] == 8000


def test_refusal_keeps_the_usage_it_consumed():
    """A refusal burns tokens too, and the bill arrives regardless.

    The same class of defect as the output-limit one: the category was
    right, the accounting was lost. Anthropic passed usage on refusal
    from the start; OpenAI did not.
    """
    import asyncio

    from app.enrich.providers.openai import OpenAIProvider

    class _Refused:
        id = "resp_refused"
        model = "gpt-5.4-mini-2026-03-17"
        status = "completed"
        output_text = ""
        output: ClassVar[list] = [
            type("Item", (), {
                "content": [type("B", (), {"type": "refusal", "refusal": "не можу"})()]
            })()
        ]
        details = type("D", (), {"cached_tokens": 0})()
        usage = type("U", (), {
            "input_tokens": 700, "output_tokens": 15, "input_tokens_details": details
        })()

    class _Responses:
        async def create(self, **kwargs):
            return _Refused()

    provider = OpenAIProvider()
    provider._client = type("C", (), {"responses": _Responses()})()

    with pytest.raises(ProviderError) as exc:
        asyncio.run(
            provider.generate_structured(
                ProviderCall(system="s", prompt="p", schema={}, model="gpt-5.4-mini",
                             max_output_tokens=100, timeout_s=5.0)
            )
        )
    assert exc.value.category == "refused"
    assert exc.value.usage is not None, "usage lost — the tokens were still billed"
    assert exc.value.usage.input_tokens == 700
    assert exc.value.usage.output_tokens == 15


def test_every_failure_category_is_mapped_and_classified():
    """No category may exist without a place in the runner's tables.

    An unmapped category silently degrades to `provider_error`, which
    would misreport both the cause and the retry decision.
    """
    from app.enrich.runner import _ERROR_TO_OUTCOME

    # Outcomes the runner sets directly rather than via error category.
    direct = {AttemptOutcome.OK, AttemptOutcome.TIMEOUT, AttemptOutcome.PROVIDER_ERROR}
    mapped = set(_ERROR_TO_OUTCOME.values()) | direct

    for outcome in AttemptOutcome:
        assert outcome in mapped, f"{outcome.value} is unreachable from any adapter"
