"""Другий провайдер — і перевірка, що архітектура справді його витримує.

Поки адаптер був один, твердження «провайдер — деталь» ніщо не
доводило. Тут доводиться: та сама канонічна задача проходить крізь два
різні адаптери в той самий валідатор, і код задачі не змінюється.

Мережі немає: обидва адаптери викликаються через підмінені клієнти.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from app.enrich.contracts import ProviderCall, ProviderError
from app.enrich.providers.anthropic import to_provider_schema as anthropic_dialect
from app.enrich.providers.openai import OpenAIProvider
from app.enrich.providers.openai import to_provider_schema as openai_dialect
from app.enrich.routing import BENCHMARK_MODELS, PRICING, benchmark_routes, estimate_upper_bound
from app.enrich.tasks import TASKS
from app.enrich.tasks.remediation import REMEDIATION_PLAN
from app.enrich.tasks.root_cause import ROOT_CAUSE_GROUPING

ENRICH = Path(__file__).resolve().parents[1] / "app" / "enrich"


# ── діалекти схем ─────────────────────────────────────────────────────────


def test_openai_needs_no_schema_translation_and_that_is_proven_not_assumed():
    """OpenAI приймає наші канонічні схеми як є — і це контрактний тест.

    Документація (structured outputs, звірено 2026-08-24) називає
    підтримуваними `minimum`, `minItems`, `enum`, `additionalProperties`
    і вимагає, щоб усі властивості були в `required`. Саме це наші схеми
    й містять, тож порожній перетворювач «про всяк випадок» був би
    зайвим місцем, де щось колись тихо зникне.
    """
    for spec in TASKS.values():
        assert openai_dialect(spec.schema) == spec.schema, f"{spec.type.value}: діалект змінив схему"


def test_the_two_dialects_differ_exactly_where_the_providers_differ():
    """Одна канонічна схема, два діалекти — і різниця саме там, де треба.

    Anthropic відбиває `minimum` для цілих (400 на живому виклику
    2026-08-24), OpenAI його приймає. Канон при цьому один.
    """
    canonical = REMEDIATION_PLAN.schema["properties"]["steps"]["items"]["properties"]["order"]
    assert canonical == {"type": "integer", "minimum": 1}

    a = anthropic_dialect(REMEDIATION_PLAN.schema)["properties"]["steps"]["items"]["properties"]
    o = openai_dialect(REMEDIATION_PLAN.schema)["properties"]["steps"]["items"]["properties"]

    assert a["order"] == {"type": "integer"}, "Anthropic мав отримати схему без minimum"
    assert o["order"] == {"type": "integer", "minimum": 1}, "OpenAI мав отримати minimum"


def test_canonical_schemas_satisfy_the_openai_strict_requirement():
    """`strict: true` вимагає, щоб КОЖНА властивість була обовʼязковою.

    Необовʼязкових полів OpenAI не приймає взагалі, тож порушення тут
    означало б 400 на кожному виклику.
    """

    def check(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                props = set(node["properties"])
                required = set(node.get("required", []))
                assert props == required, f"{path}: не всі поля обовʼязкові: {props - required}"
                assert node.get("additionalProperties") is False, f"{path}: не заборонено зайве"
            for key, value in node.items():
                check(value, f"{path}.{key}" if path else key)
        elif isinstance(node, list):
            for i, item in enumerate(node):
                check(item, f"{path}[{i}]")

    for spec in TASKS.values():
        check(spec.schema, spec.type.value)


# ── межа помилок ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("exc_name", "expected"),
    [
        # Ключ заданий і відхилений — не «немає конфігурації».
        ("AuthenticationError", "authentication_error"),
        ("RateLimitError", "rate_limit"),
        ("BadRequestError", "invalid_request"),
        ("APITimeoutError", "timeout"),
        ("InternalServerError", "provider_error"),
        ("APIConnectionError", "provider_error"),
    ],
)
def test_openai_exceptions_map_to_shared_categories(exc_name, expected):
    """Типи SDK за межу адаптера не виходять — виходять категорії."""
    import httpx
    import openai

    from app.enrich.providers.openai import _category_of

    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    exc_type = getattr(openai, exc_name)
    if exc_name == "APITimeoutError":
        exc = exc_type(request=request)
    elif exc_name == "APIConnectionError":
        exc = exc_type(request=request)
    else:
        status = {"AuthenticationError": 401, "RateLimitError": 429,
                  "BadRequestError": 400, "InternalServerError": 500}[exc_name]
        exc = exc_type(
            "boom", response=httpx.Response(status, request=request), body=None
        )

    assert _category_of(exc) == expected


@pytest.mark.asyncio
async def test_missing_key_is_a_clean_category_not_a_crash(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.openai_api_key", None)
    provider = OpenAIProvider()
    call = ProviderCall(
        system="s", prompt="p", schema={"type": "object"}, model="gpt-5.4-mini",
        max_output_tokens=100, timeout_s=5.0,
    )
    with pytest.raises(ProviderError) as exc:
        await provider.generate_structured(call)
    assert exc.value.category == "not_configured"


# ── те саме канонічне через два адаптери ─────────────────────────────────


class _FakeOpenAIResponse:
    """Форма відповіді Responses API, потрібна адаптеру."""

    def __init__(self, text: str, cached: int = 40) -> None:
        self.id = "resp_test"
        self.model = "gpt-5.4-mini"
        self.status = "completed"
        self.output_text = text
        self.output = []
        details = type("D", (), {"cached_tokens": cached})()
        self.usage = type("U", (), {
            "input_tokens": 100, "output_tokens": 50, "input_tokens_details": details
        })()


@pytest.mark.asyncio
async def test_identical_canonical_result_passes_through_openai_into_the_validator(monkeypatch):
    """Вихід моделі → адаптер OpenAI → канонічний валідатор Crawldy."""
    import json

    payload = {
        "findings": [
            {"ref": "seo.h1:missing", "module": "seo", "severity": "high",
             "title": "no h1", "pages": 3, "scope": "page", "examples": [], "evidence": ""}
        ],
        "site": "",
        "coverage": {"level": "full", "pages_read": 3, "pages_known": 3, "pages_unread": 0},
    }
    canonical_output = {
        "groups": [
            {
                "id": "tpl",
                "cluster_summary": "Same field missing on every page read.",
                "finding_refs": ["seo.h1:missing"],
                "cluster_evidence": ["seo.h1:missing"],
                "cause_confidence": "unknown",
                "cause_hypothesis": "",
                "cause_evidence": [],
            }
        ],
        "ungrouped_refs": [],
    }

    class _Responses:
        async def create(self, **kwargs: Any) -> _FakeOpenAIResponse:
            # Схема доїхала в тому місці, де її чекає Responses API.
            fmt = kwargs["text"]["format"]
            assert fmt["type"] == "json_schema"
            assert fmt["strict"] is True
            assert fmt["schema"] == ROOT_CAUSE_GROUPING.schema
            return _FakeOpenAIResponse(json.dumps(canonical_output))

    provider = OpenAIProvider()
    provider._client = type("C", (), {"responses": _Responses()})()

    reply = await provider.generate_structured(
        ProviderCall(
            system=ROOT_CAUSE_GROUPING.system,
            prompt="whatever",
            schema=ROOT_CAUSE_GROUPING.schema,
            model="gpt-5.4-mini",
            max_output_tokens=1000,
            timeout_s=10.0,
        )
    )

    clean = ROOT_CAUSE_GROUPING.validate(reply.output, payload)
    assert clean["groups"][0]["cause_hypothesis"] is None
    # Кешовані токени враховані окремо й не пораховані двічі.
    assert reply.cache_read_tokens == 40
    assert reply.input_tokens == 60, "кешована частина мала бути віднята від входу"


@pytest.mark.asyncio
async def test_truncated_output_is_reported_as_an_output_limit():
    """Обрив по стелі виходу має називатися своїм імʼям у журналі.

    Категорія спільна з Anthropic (`stop_reason == max_tokens`): це межа
    нашого бюджету виконання, а не зіпсована відповідь, і лікується вона
    бюджетом, а не задачею."""
    provider = OpenAIProvider()

    class _Responses:
        async def create(self, **kwargs: Any) -> Any:
            r = _FakeOpenAIResponse('{"groups": [')
            r.status = "incomplete"
            r.incomplete_details = type("I", (), {"reason": "max_output_tokens"})()
            return r

    provider._client = type("C", (), {"responses": _Responses()})()
    with pytest.raises(ProviderError) as exc:
        await provider.generate_structured(
            ProviderCall(system="s", prompt="p", schema={}, model="gpt-5.4-mini",
                         max_output_tokens=10, timeout_s=5.0)
        )
    assert exc.value.category == "output_limit"
    assert "обірвана" in exc.value.detail


# ── провайдеро-незалежність ──────────────────────────────────────────────


def test_no_provider_sdk_or_model_name_in_task_logic():
    """Ані Anthropic, ані OpenAI не проникають у логіку задач."""
    forbidden_modules = {"anthropic", "openai", "google", "mistralai", "cohere"}
    banned_words = ("claude", "gpt-", "gpt_", "gemini", "anthropic", "openai",
                    "sonnet", "opus", "haiku")

    # Імпорти перевіряються на ширшому наборі — це справжній захист.
    imports_scope: list[Path] = sorted((ENRICH / "tasks").rglob("*.py"))
    imports_scope += [ENRICH / "runner.py", ENRICH / "contracts.py", ENRICH / "identity.py"]
    for path in imports_scope:
        source = path.read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                assert name.split(".")[0] not in forbidden_modules, f"{path.name}: {name}"

    # Словесна перевірка — лише по ЛОГІЦІ задач. `contracts.py` свідомо
    # поза нею: там документується саме це правило, і назвати провайдерів
    # у поясненні межі — не те саме, що знати про них у логіці.
    for path in [*sorted((ENRICH / "tasks").rglob("*.py")), ENRICH / "runner.py"]:
        low = path.read_text(encoding="utf-8").lower()
        for word in banned_words:
            assert word not in low, f"{path.name} згадує «{word}»"


def test_model_names_live_only_in_routing():
    """Позитивна половина: у маршрутах вони саме мають бути."""
    models = {c.model for c in BENCHMARK_MODELS.values()}
    assert models == {"claude-opus-5", "claude-sonnet-5", "gpt-5.4-mini"}
    for key in BENCHMARK_MODELS:
        routes = benchmark_routes(key, tuple(TASKS))
        assert len(routes) == len(TASKS)
        # Один кандидат: fallback перекрив би те, що ми міряємо.
        assert all(len(v) == 1 for v in routes.values())


def test_the_same_task_object_serves_both_providers():
    """Той самий обʼєкт задачі, два маршрути, жодної правки коду.

    Схеми без `minimum` (групування, розуміння сайту) обидва діалекти
    віддають однаково — різниця зʼявляється рівно там, де є доведена
    несумісність, тобто в плані виправлень.
    """
    for key, expected_provider in (("opus-5", "anthropic"), ("gpt-5.4-mini", "openai")):
        for spec in TASKS.values():
            route = benchmark_routes(key, (spec.type,))[spec.type][0]
            assert route.provider == expected_provider
            # Обидва діалекти лишають схему придатною: корінь обʼєкт,
            # зайве заборонене, перелік обовʼязкових цілий.
            for dialect in (anthropic_dialect, openai_dialect):
                wire = dialect(spec.schema)
                assert wire["type"] == "object"
                assert wire["additionalProperties"] is False
                assert wire["required"] == spec.schema["required"]

    assert anthropic_dialect(ROOT_CAUSE_GROUPING.schema) == openai_dialect(
        ROOT_CAUSE_GROUPING.schema
    ), "без minimum діалекти не мають розходитись"
    assert anthropic_dialect(REMEDIATION_PLAN.schema) != openai_dialect(
        REMEDIATION_PLAN.schema
    ), "саме тут несумісність доведена — діалекти мусять розійтись"


# ── ціни ─────────────────────────────────────────────────────────────────


def test_every_benchmark_model_has_verified_pricing():
    """Без цінової бази живий прогін не покаже кошторису — отже не піде."""
    for key, candidate in BENCHMARK_MODELS.items():
        assert candidate.model in PRICING, f"{key}: цінової бази немає"


def test_openai_pricing_matches_the_verified_source():
    """developers.openai.com/api/docs/pricing, звірено 2026-08-24."""
    price = PRICING["gpt-5.4-mini"]
    assert (price.input_, price.output, price.cache_read) == (0.75, 4.50, 0.075)
    # Окремої платної операції запису в кеш у OpenAI немає.
    assert price.cache_write == price.input_


def test_anthropic_sonnet_pricing_matches_the_verified_source():
    """platform.claude.com/docs/en/about-claude/pricing, звірено 2026-08-24."""
    price = PRICING["claude-sonnet-5"]
    assert (price.input_, price.output) == (2.00, 10.00)
    assert (price.cache_write, price.cache_read) == (2.50, 0.20)


def test_upper_bound_estimate_is_pessimistic_and_ordered():
    """Дешевша модель мусить давати меншу стелю — інакше кошторис бреше."""
    calls, in_tok, out_tok = 6, 12_000, 3_000
    opus = estimate_upper_bound("opus-5", calls, in_tok, out_tok)
    sonnet = estimate_upper_bound("sonnet-5", calls, in_tok, out_tok)
    mini = estimate_upper_bound("gpt-5.4-mini", calls, in_tok, out_tok)

    assert opus and sonnet and mini
    assert opus > sonnet > mini
    # Песимістично: вхід за повною ставкою, без знижки за кеш.
    assert opus == pytest.approx((12_000 * 5.0 + 3_000 * 25.0) / 1_000_000 * 6)


def test_unknown_model_has_no_estimate_rather_than_a_guess():
    assert estimate_upper_bound("nonexistent", 6, 1000, 1000) is None


# ── сумісність Sonnet 5 ──────────────────────────────────────────────────


def test_anthropic_request_carries_no_undocumented_parameters():
    """`effort` більше не їде в `output_config`.

    Офіційна документація `output_config` його не описує, а проєкт уже
    знає, що воно модельозалежне: Haiku 4.5 відповідає 400. Слати його
    на Sonnet 5, де його ніхто не перевіряв, означало б покласти
    порівняння на випадковість — і зробити його нечесним, бо Opus
    отримував би інший режим.
    """
    source = (ENRICH / "providers" / "anthropic.py").read_text(encoding="utf-8")
    assert 'output_config["effort"]' not in source
    assert '"effort"' not in source.split('"""', 2)[-1], "effort лишився в коді запиту"
