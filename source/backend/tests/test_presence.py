"""Actual AI Presence, юніт-шар: промпти, тлумачення, раннер, метрики.

Мережі тут не існує: всі провайдери — скриптовані, а тест-шпигун на
сокеті доводить це явно. Правила ті самі, що в усьому продукті: збійна
клітинка — «не спостережено», а не нуль; знаменники брендового й
небрендового сегментів не змішуються; жодного зведеного AI-бала.
"""

from __future__ import annotations

import asyncio
from decimal import Decimal

import pytest

from app.ai.catalog import call_cost_usd, capability, max_attempt_cost_usd
from app.presence.budget import REQUEST_CEILINGS
from app.presence.contracts import (
    ObservationStatus,
    PresencePrompt,
    PromptCategory,
    PromptSet,
    Segment,
)
from app.presence.metrics import build_metrics
from app.presence.normalize import interpret, observed_domain
from app.presence.policy import (
    DEFAULT_POLICY,
    PresencePolicy,
    ProviderPolicy,
    from_stored,
    validate,
)
from app.presence.prompts import PromptBiasError, PromptFacts, build_prompt_set
from app.presence.providers.scripted import ScriptedPresenceProvider, ScriptedReply
from app.presence.runner import execute_run

ORIGIN = "https://example.com"
ALIASES = ("Acme Dental", "acme-dental.example")

# Захисний максимум однієї спроби скриптованого провайдера, рахований
# так само, як у раннері: 1M×$1/M + 1500×$1/M + 3×$8/1k = $1.0255.
# Тести бюджету будують арифметику стель від нього, а не від круглих
# чисел: захисна межа тепер ВИВОДИТЬСЯ, а не конфігурується.
_CAP = capability("scripted", "scripted-model")
assert _CAP is not None
BOUND = max_attempt_cost_usd(
    _CAP,
    max_output_tokens=REQUEST_CEILINGS["scripted"].max_output_tokens,
    max_searches=REQUEST_CEILINGS["scripted"].max_searches,
)
assert BOUND is not None


def _prompt(category: PromptCategory = PromptCategory.CATEGORY,
            segment: Segment = Segment.UNBRANDED,
            pid: str = "category-1") -> PresencePrompt:
    return PresencePrompt(prompt_id=pid, text="best dental clinic?",
                          category=category, segment=segment, language="en")


def _interpret(answer_text: str, cited: list[str],
               category: PromptCategory = PromptCategory.CATEGORY,
               searched: bool = True):
    from app.presence.contracts import ProviderAnswer, ProviderUsage

    return interpret(
        ProviderAnswer(text=answer_text, cited_urls=cited, searched=searched,
                       model="m", usage=ProviderUsage(100, 200, 1)),
        prompt=_prompt(category), prompt_set_version="p0-1:en",
        provider="scripted", tool_version="t1", run_index=1, country=None,
        origin=ORIGIN, brand_aliases=ALIASES, cost_usd=0.01,
    )


# ── нормалізація і тлумачення ─────────────────────────────────────────


def test_provider_answer_normalises_into_a_full_observation() -> None:
    rec = _interpret("Try Acme Dental.", ["https://www.example.com/about"])
    assert rec.status is ObservationStatus.OK
    assert rec.brand_mentioned and rec.matched_alias == "Acme Dental"
    assert rec.domain_cited and rec.pages_cited == ["https://www.example.com/about"]
    assert rec.cited_domains == ["example.com"]


def test_brand_alias_needs_word_boundaries() -> None:
    """Клас «cheaper містить heap»: підрядок усередині слова — не згадка."""
    rec = _interpret("Macmedental is unrelated.", [])
    assert rec.brand_mentioned is False
    rec2 = _interpret("Компанія ACME DENTAL відома.", [])
    assert rec2.brand_mentioned is True, "регістр не важить, межі слова важать"


def test_domain_matching_is_site_scope_not_prefix() -> None:
    rec = _interpret("...", ["https://example.com.evil.org/x",
                             "https://shop.example.com/y"])
    assert rec.domain_cited is False, "схожа назва і піддомен — чужі сайти"
    assert set(rec.cited_domains) == {"example.com.evil.org", "shop.example.com"}


def test_observed_domain_strips_www_and_case() -> None:
    assert observed_domain("https://WWW.Example.COM/p") == "example.com"
    assert observed_domain("not a url") is None


def test_not_searched_answer_is_still_an_observation() -> None:
    rec = _interpret("Acme Dental is a known clinic.", [], searched=False)
    assert rec.status is ObservationStatus.OK
    assert rec.searched is False and rec.brand_mentioned is True
    assert rec.domain_cited is False, "без пошуку цитат не буває"


def test_missing_citation_metadata_means_no_citation_claim() -> None:
    rec = _interpret("A generic answer.", [], searched=True)
    assert rec.domain_cited is False and rec.cited_domains == []


def test_recommendation_applies_only_to_list_prompts() -> None:
    listy = _interpret("Acme Dental tops the list.", [],
                       category=PromptCategory.COMPARISON)
    assert listy.recommended is True
    info = _interpret("Acme Dental appears here.", [],
                      category=PromptCategory.INFORMATIONAL)
    assert info.recommended is None, "не-переліковий промпт не судить включення"
    cite_only = _interpret("A list without names.", ["https://example.com/"],
                           category=PromptCategory.CATEGORY)
    assert cite_only.recommended is True, "включення через цитату без назви"
    assert cite_only.brand_mentioned is False


# ── промпти ───────────────────────────────────────────────────────────


def test_unbranded_prompts_pass_the_bias_lint() -> None:
    facts = PromptFacts(brand="Acme Dental", brand_aliases=("acme",),
                        domain="acme-dental.example", category="dental clinic",
                        services=("implants",), location="Kyiv", language="en")
    ps = build_prompt_set(facts)
    assert len(ps.prompts) == 15 and len(ps.unbranded) == 12
    for p in ps.unbranded:
        assert "acme" not in p.text.lower()


def test_bias_lint_rejects_a_brand_leak() -> None:
    facts = PromptFacts(brand="Dental", brand_aliases=(), domain="d.example",
                        category="Dental clinic", services=(), location=None,
                        language="en")
    with pytest.raises(PromptBiasError):
        build_prompt_set(facts)


# ── політика ──────────────────────────────────────────────────────────


def test_default_policy_is_the_approved_p0_and_disabled() -> None:
    assert DEFAULT_POLICY.enabled is False, "бета вимкнена за замовчуванням"
    assert set(DEFAULT_POLICY.active_providers()) == {
        "anthropic", "openai", "perplexity", "google"}
    assert DEFAULT_POLICY.providers["perplexity"].model == "perplexity/sonar"
    # Продуктовий google — Vertex AI з gemini-2.5-flash: заземлення
    # білиться за промпт, максимум спроби рахований. Ряд 2.5 у
    # Developer API закритий для нових користувачів — тому бекенд
    # vertex_ai, і він явний, а не мовчазний фолбек.
    assert DEFAULT_POLICY.providers["google"].model == "gemini-2.5-flash"
    from app.presence.policy import effective_backend

    assert effective_backend(
        "google", DEFAULT_POLICY.providers["google"]) == "vertex_ai"
    ready = capability("google", "gemini-2.5-flash")
    assert ready is not None and ready.max_searches_boundable
    assert DEFAULT_POLICY.runs_per_prompt == 2
    assert DEFAULT_POLICY.max_prompts == 15
    assert DEFAULT_POLICY.modes == ("natural", "explicit")


def test_policy_validation_rejects_invalid_combinations() -> None:
    bad = PresencePolicy(
        enabled=True,
        providers={"gemini": ProviderPolicy(enabled=True, model="gemini-x")},
        runs_per_prompt=0, max_prompts=500, retry_limit=9,
        raw_retention_days=0, concurrency=99,
    )
    errors = validate(bad)
    assert any("без продуктового адаптера" in e for e in errors)
    assert any("runs_per_prompt" in e for e in errors)


def test_stored_overlay_keeps_unknown_keys_harmless() -> None:
    policy = from_stored({"runs_per_prompt": 3, "mystery": True})
    assert policy.runs_per_prompt == 3
    assert policy.max_prompts == DEFAULT_POLICY.max_prompts


def test_scripted_provider_cannot_register_in_prod(monkeypatch) -> None:
    from app.core.config import settings
    from app.presence.providers import registry

    monkeypatch.setattr(settings, "app_env", "prod")
    with pytest.raises(RuntimeError):
        registry.register_provider(
            "scripted", lambda m: ScriptedPresenceProvider([], model=m))
    assert "scripted" not in registry._FACTORIES


# ── раннер ────────────────────────────────────────────────────────────


def _policy(**overrides) -> PresencePolicy:
    base = {
        "enabled": True,
        "providers": {"scripted": ProviderPolicy(enabled=True,
                                                 model="scripted-model")},
        "runs_per_prompt": 2, "max_prompts": 15, "retry_limit": 1,
        "raw_retention_days": 30, "concurrency": 2,
        # Одно-режимна політика: ці тести міряють клітинки без виміру
        # режимів; режими мають власні тести нижче.
        "modes": ("natural",),
    }
    base.update(overrides)
    return PresencePolicy(**base)


def _prompt_set(n: int = 2) -> PromptSet:
    return PromptSet(version="p0-1:en", prompts=tuple(
        _prompt(pid=f"category-{i + 1}") for i in range(n)
    ))


def _run(policy, prompt_set, provider):
    return asyncio.run(execute_run(
        policy=policy, prompt_set=prompt_set, origin=ORIGIN,
        brand_aliases=ALIASES,
        providers_override={"scripted": provider},
    ))


def test_runner_covers_every_cell_and_accounts_cost() -> None:
    provider = ScriptedPresenceProvider(
        [ScriptedReply("Acme Dental", cited_urls=["https://example.com/a"])])
    records, totals = _run(_policy(), _prompt_set(2), provider)
    assert totals.observations == 4  # 2 промпти × 2 повтори
    assert totals.ok == 4
    assert totals.cost_usd > 0
    assert abs(sum(r.cost_usd for r in records) - totals.cost_usd) < 1e-9


def test_cost_accounting_matches_the_catalog_prices() -> None:
    cap = capability("perplexity", "perplexity/sonar")
    assert cap is not None
    cost = call_cost_usd(cap, input_tokens=1_000_000, output_tokens=1_000_000,
                         searches=1000)
    assert abs(cost - (0.25 + 2.50 + 2.50)) < 1e-9


def test_provider_failure_is_recorded_not_zeroed() -> None:
    provider = ScriptedPresenceProvider(
        [ScriptedReply("", fail_with=ObservationStatus.REFUSED)])
    records, totals = _run(_policy(retry_limit=3), _prompt_set(1), provider)
    assert totals.ok == 0 and totals.observations == 2
    assert all(r.status is ObservationStatus.REFUSED for r in records)
    assert len(provider.calls) == 2, "REFUSED не повторюється"


def test_rate_limit_is_retried_within_the_limit() -> None:
    provider = ScriptedPresenceProvider([
        ScriptedReply("", fail_with=ObservationStatus.RATE_LIMITED),
        ScriptedReply("ok"),
        ScriptedReply("ok"),
    ])
    policy = _policy(runs_per_prompt=1, retry_limit=1)
    _records, totals = _run(policy, _prompt_set(1), provider)
    assert totals.ok == 1
    assert len(provider.calls) == 2, "одна невдача + один успішний повтор"


def test_done_cells_are_skipped_on_rerun() -> None:
    provider = ScriptedPresenceProvider([ScriptedReply("ok")])
    policy = _policy(runs_per_prompt=2)
    done = {("scripted", "category-1", "natural", 1)}
    records, totals = asyncio.run(execute_run(
        policy=policy, prompt_set=_prompt_set(1), origin=ORIGIN,
        brand_aliases=ALIASES, done_cells=done,
        providers_override={"scripted": provider},
    ))
    assert totals.observations == 1, "готова клітинка не платить удруге"
    assert records[0].run_index == 2


def test_missing_key_yields_not_configured_without_calls() -> None:
    policy = PresencePolicy(
        enabled=True,
        providers={"perplexity": ProviderPolicy(enabled=True, model="sonar")},
        runs_per_prompt=1, max_prompts=15, retry_limit=0,
        raw_retention_days=30, concurrency=1,
    )
    records, totals = asyncio.run(execute_run(
        policy=policy, prompt_set=_prompt_set(1), origin=ORIGIN,
        brand_aliases=ALIASES,
    ))
    assert totals.ok == 0
    assert records[0].status is ObservationStatus.NOT_CONFIGURED


def test_the_runner_makes_no_network_calls_with_scripted_providers() -> None:
    import socket

    real = socket.socket.connect
    calls: list = []

    def spy(self, *args):
        address = args[0] if args else None
        host = address[0] if isinstance(address, tuple) else address
        # Селекторний луп Windows тримає внутрішній socketpair на
        # loopback — це не мережа, а сантехніка asyncio.
        if host not in ("127.0.0.1", "::1", "localhost"):
            calls.append(args)
        return real(self, *args)

    socket.socket.connect = spy  # type: ignore[method-assign]
    try:
        provider = ScriptedPresenceProvider([ScriptedReply("ok")])
        _run(_policy(), _prompt_set(1), provider)
    finally:
        socket.socket.connect = real  # type: ignore[method-assign]
    assert calls == []


# ── метрики ───────────────────────────────────────────────────────────


def _row(**kw):
    base = {
        "provider": "scripted", "prompt_id": "category-1",
        "category": "category", "segment": "unbranded", "status": "ok",
        "searched": True, "brand_mentioned": False, "domain_cited": False,
        "recommended": None, "observed_domains": [],
    }
    base.update(kw)
    return base


def test_metrics_separate_segments_and_exclude_failures() -> None:
    rows = [
        _row(brand_mentioned=True),
        _row(prompt_id="category-2", status="provider_error"),
        _row(prompt_id="branded-1", segment="branded", category="branded",
             domain_cited=True),
    ]
    metrics = build_metrics(rows)
    combined = metrics["combined"]
    assert combined["mention_presence"]["numerator"] == 1
    assert combined["mention_presence"]["denominator"] == 1, (
        "збійна клітинка і брендовий сегмент поза знаменником")
    assert combined["branded_citation"]["numerator"] == 1
    assert combined["mention_presence"]["rate"] is None, (
        "замало спостережень для відсотка")
    assert "score" not in metrics, "зведеного AI-бала не існує"
    assert metrics["evidence_family"] == "synthetic"


def test_every_metric_names_what_it_does_not_mean() -> None:
    rows = [_row()]
    for name, metric in build_metrics(rows)["combined"].items():
        assert metric["not_meaning"], name
        assert metric["evidence_family"] == "synthetic"


# ── межі доменів і скорингу ───────────────────────────────────────────


def test_audit_never_imports_presence() -> None:
    """Присутність не має шляху в скоринг: жоден модуль ядра аудиту не
    імпортує app.presence."""
    import pathlib

    audit_dir = pathlib.Path("app/audit")
    offenders = [
        p for p in audit_dir.rglob("*.py")
        if "app.presence" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_presence_never_imports_scoring() -> None:
    import pathlib

    offenders = [
        p for p in pathlib.Path("app/presence").rglob("*.py")
        if "app.audit.scoring" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_module_scores_are_untouched_by_presence_activity() -> None:
    """Обчислення балів не залежить від жодного стану присутності."""
    from app.audit.enums import Module
    from app.audit.scoring import compute_scores

    before = compute_scores([], skipped_modules=set())
    provider = ScriptedPresenceProvider([ScriptedReply("Acme Dental")])
    _run(_policy(), _prompt_set(1), provider)
    after = compute_scores([], skipped_modules=set())
    assert before == after
    assert set(after[1]) == {m.value for m in Module}


# ── Perplexity Agent API ──────────────────────────────────────────────


AGENT_FIXTURE = {
    "model": "perplexity/sonar",
    "output": [
        {
            "type": "search_results",
            "queries": ["best dental clinics kyiv"],
            "results": [
                {"id": 1, "url": "https://example.com/about",
                 "title": "About", "snippet": "..."},
                {"id": 2, "url": "https://competitor.example/list",
                 "title": "List", "snippet": "..."},
            ],
        },
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "output_text", "text": "Consider Acme Dental."},
            ],
        },
    ],
    "usage": {
        "input_tokens": 900, "output_tokens": 120, "total_tokens": 1020,
        "tool_calls_details": {"search_web": {"invocation": 2}},
        "cost": {"total_cost": 0.0079},
    },
}


def test_agent_api_response_normalises_with_official_shape() -> None:
    from app.presence.providers.perplexity import parse_agent_response

    answer = parse_agent_response(dict(AGENT_FIXTURE), fallback_model="x")
    assert answer.text == "Consider Acme Dental."
    assert answer.cited_urls == [
        "https://example.com/about", "https://competitor.example/list"]
    assert answer.searched is True and answer.usage.searches == 2
    assert answer.usage.input_tokens == 900
    assert answer.provider_cost_usd == 0.0079
    assert answer.model == "perplexity/sonar"


def test_agent_api_without_search_is_not_searched() -> None:
    from app.presence.providers.perplexity import parse_agent_response

    body = {
        "model": "perplexity/sonar",
        "output": [{"type": "message", "role": "assistant",
                    "content": [{"type": "output_text", "text": "From memory."}]}],
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }
    answer = parse_agent_response(body, fallback_model="perplexity/sonar")
    assert answer.searched is False and answer.cited_urls == []
    assert answer.provider_cost_usd is None, "без поля cost — рахує каталог"


def test_provider_cost_feeds_accounting_but_not_admission() -> None:
    """Фактична вартість провайдера облікується, але стелю не обходить:
    допуск наступної клітинки дивиться на вже витрачене."""
    from app.presence.contracts import ProviderAnswer, ProviderUsage

    class CostedProvider:
        name = "scripted"
        model = "scripted-model"
        tool_version = "t"
        calls = 0

        async def observe(self, prompt_text, *, country, require_search=False):
            CostedProvider.calls += 1
            return ProviderAnswer(text="ok", searched=True,
                                  model=self.model,
                                  usage=ProviderUsage(10, 10, 1),
                                  provider_cost_usd=0.9)

    policy = _policy(runs_per_prompt=2)
    records, totals = asyncio.run(execute_run(
        policy=policy, prompt_set=_prompt_set(2), origin=ORIGIN,
        brand_aliases=ALIASES,
        providers_override={"scripted": CostedProvider()},
    ))
    assert abs(totals.cost_usd - 0.9 * totals.ok) < 1e-9, (
        "облік — за фактичною вартістю провайдера")
    exhausted = [r for r in records
                 if r.status is ObservationStatus.BUDGET_EXHAUSTED]
    assert not exhausted, "вартість більше не перекриває клітинок: стель немає"


def test_perplexity_provenance_rejects_third_party_models() -> None:
    """Agent API вміє чужі моделі — політика присутності їх не пускає:
    provider=perplexity мусить означати модель Perplexity."""
    from app.ai.catalog import is_native_model

    assert is_native_model("perplexity", "perplexity/sonar")
    assert not is_native_model("perplexity", "openai/gpt-5.6-sol")
    assert not is_native_model("perplexity", "claude-sonnet-4-6")

    bad = PresencePolicy(
        enabled=True,
        providers={"perplexity": ProviderPolicy(enabled=True,
                                                model="claude-sonnet-4-6")},
        runs_per_prompt=1, max_prompts=15, retry_limit=0,
        raw_retention_days=30, concurrency=1,
    )
    errors = validate(bad)
    assert any("провенанс" in e or "чужа модель" in e for e in errors)


def test_agent_api_pricing_has_no_legacy_request_fee() -> None:
    cap = capability("perplexity", "perplexity/sonar")
    assert cap is not None
    assert cap.input_usd_per_mtok == 0.25 and cap.output_usd_per_mtok == 2.50
    assert cap.search_usd_per_1k == 2.50, "web_search $2.50/1k, не $5-12 запитний збір"
    assert cap.supports_location is True, "Agent API приймає user_location.country"
    assert capability("perplexity", "sonar") is None, "legacy-запис вилучено"


# ── чотири провайдери, режими, нове тлумачення ───────────────────────


def test_gemini_interaction_parses_text_citations_and_queries() -> None:
    """Офіційна форма Interactions API → канонічна відповідь."""
    from app.presence.providers.google import parse_interaction

    body = {
        "id": "int_1",
        "model": "gemini-3.7-flash",
        "status": "completed",
        "steps": [
            {"type": "google_search_call",
             "queries": ["best dental clinic kyiv"]},
            {"type": "google_search_result", "results": []},
            {"type": "model_output", "content": [{
                "type": "text",
                "text": "Acme Dental is a well-reviewed clinic.",
                "annotations": [
                    {"type": "url_citation",
                     "url": "https://example.com/about",
                     "title": "About", "start_index": 0, "end_index": 10},
                    {"type": "url_citation",
                     "url": "https://maps.example.org/place",
                     "title": "Map", "start_index": 11, "end_index": 20},
                ],
            }]},
        ],
        "usage": {"total_input_tokens": 12, "total_output_tokens": 40,
                  "total_tokens": 52},
    }
    answer = parse_interaction(body, fallback_model="gemini-3.7-flash")
    assert answer.searched is True
    assert answer.search_queries == ["best dental clinic kyiv"]
    assert answer.cited_urls == [
        "https://example.com/about", "https://maps.example.org/place"]
    assert answer.usage.input_tokens == 12
    assert answer.usage.output_tokens == 40
    assert answer.usage.searches == 1
    assert "well-reviewed" in answer.text


def test_gemini_answer_without_search_is_a_valid_natural_observation() -> None:
    from app.presence.providers.google import parse_interaction

    body = {"model": "gemini-3.7-flash", "steps": [
        {"type": "model_output",
         "content": [{"type": "text", "text": "From training knowledge."}]},
    ], "usage": {"total_input_tokens": 5, "total_output_tokens": 9}}
    answer = parse_interaction(body, fallback_model="gemini-3.7-flash")
    assert answer.searched is False
    assert answer.cited_urls == []
    assert answer.usage.searches == 0


def test_google_capability_is_native_and_priced() -> None:
    from app.ai.catalog import is_native_model

    cap = capability("google", "gemini-3.7-flash")
    assert cap is not None and cap.supports_web_search
    assert is_native_model("google", "gemini-3.7-flash")
    assert not is_native_model("google", "gpt-5.1"), "чужа модель під вивіскою"
    cost = call_cost_usd(cap, input_tokens=1_000_000,
                         output_tokens=1_000_000, searches=1000)
    assert abs(cost - (0.75 + 3.75 + 14.0)) < 1e-9


# ── google gemini-2.5-flash: рахований твердий бюджет ─────────────────


def test_gemini_25_bound_is_exact_and_assumes_the_paid_tier() -> None:
    """Максимум спроби — з офіційних меж і платного тарифу (звірено
    2026-09-01): вхідний ліміт 1 048 576 × $0.30/M + наша стеля виходу
    1500 × $2.50/M (thinking вимкнено, тож інших вихідних токенів
    немає) + РІВНО ОДНА одиниця білення заземлення $35/1000.
    Безкоштовні 1500 запитів/добу в межу не закладаються: вони можуть
    здешевити факт, але допуск на них не спирається."""
    cap = capability("google", "gemini-2.5-flash")
    assert cap is not None
    assert cap.input_usd_per_mtok == 0.30
    assert cap.output_usd_per_mtok == 2.50
    assert cap.search_usd_per_1k == 35.0
    assert cap.context_window_tokens == 1_048_576
    ceilings = REQUEST_CEILINGS["google"]
    assert ceilings.max_output_tokens == 1500
    assert ceilings.max_searches == 1, "одна одиниця білення на запит"
    bound = max_attempt_cost_usd(
        cap, max_output_tokens=ceilings.max_output_tokens,
        max_searches=ceilings.max_searches)
    expected = (Decimal("1048576") / Decimal("1000000") * Decimal("0.30")
                + Decimal("1500") / Decimal("1000000") * Decimal("2.50")
                + Decimal("1") / Decimal("1000") * Decimal("35.0"))
    assert bound == expected == Decimal("0.3533228")


def test_gemini_25_generate_content_parses_grounded_answer() -> None:
    """Офіційна форма generateContent → канонічна відповідь: текст,
    виконані запити, джерела (редірект розгортається в домен із title),
    спожите, і РІВНО ОДНА одиниця білення заземлення."""
    from app.presence.providers.google import parse_generate_content

    body = {
        "modelVersion": "gemini-2.5-flash",
        "candidates": [{
            "content": {"role": "model", "parts": [
                {"text": "Acme Dental is a well-reviewed clinic."},
            ]},
            "groundingMetadata": {
                "webSearchQueries": ["best dental clinic kyiv",
                                     "acme dental reviews"],
                "groundingChunks": [
                    {"web": {
                        "uri": ("https://vertexaisearch.cloud.google.com/"
                                "grounding-api-redirect/AbCd"),
                        "title": "example.com"}},
                    {"web": {"uri": "https://maps.example.org/place",
                             "title": "Map"}},
                ],
            },
        }],
        "usageMetadata": {"promptTokenCount": 12,
                          "candidatesTokenCount": 40,
                          "thoughtsTokenCount": 0,
                          "totalTokenCount": 52},
    }
    answer = parse_generate_content(body, fallback_model="gemini-2.5-flash")
    assert answer.searched is True
    assert answer.search_queries == ["best dental clinic kyiv",
                                     "acme dental reviews"]
    assert answer.cited_urls == [
        "https://example.com/", "https://maps.example.org/place"]
    assert answer.usage.input_tokens == 12
    assert answer.usage.output_tokens == 40
    assert answer.usage.searches == 1, (
        "два внутрішні запити — одна одиниця білення: промпт")
    assert answer.model == "gemini-2.5-flash"


def test_gemini_25_answer_without_grounding_bills_no_grounding_unit() -> None:
    from app.presence.providers.google import parse_generate_content

    body = {
        "candidates": [{"content": {"parts": [
            {"text": "From training knowledge."}]}}],
        "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 9},
    }
    answer = parse_generate_content(body, fallback_model="gemini-2.5-flash")
    assert answer.searched is False
    assert answer.cited_urls == []
    assert answer.usage.searches == 0, "незаземлений промпт не білиться"


def test_gemini_25_request_sends_the_limits_the_bound_assumes(
    monkeypatch,
) -> None:
    """Формула і запит — одне ціле: адаптер надсилає РІВНО ті межі, з
    яких рахувався максимум (модель, стеля виходу, вимкнений thinking,
    заземлення), на ендпойнт generateContent."""
    from app.core.config import settings
    from app.presence.providers import google as google_module

    captured: dict = {}
    body = {
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
    }

    class _FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return body

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            return _FakeResponse()

    monkeypatch.setattr(settings, "google_api_key", "test-key")
    monkeypatch.setattr(google_module.httpx, "AsyncClient", _FakeClient)

    provider = google_module.GooglePresenceProvider(
        "gemini-2.5-flash", backend="developer_api")
    assert provider.tool_version == "generate_content-google_search@v1beta"
    answer = asyncio.run(provider.observe("best dental clinic?",
                                          country=None))
    assert answer.text == "ok"
    assert captured["url"].endswith("models/gemini-2.5-flash:generateContent")
    assert "generativelanguage.googleapis.com" in captured["url"]
    payload = captured["json"]
    assert payload["tools"] == [{"google_search": {}}]
    config = payload["generationConfig"]
    assert config["maxOutputTokens"] == REQUEST_CEILINGS[
        "google"].max_output_tokens
    assert config["candidateCount"] == 1
    assert config["thinkingConfig"]["thinkingBudget"] == 0, (
        "thinking вимкнено так само, як припускає формула межі")


# ── google: бекенд vertex_ai ──────────────────────────────────────────


def _fake_vertex_client(captured: dict, *, status_code: int = 200,
                        body: dict | None = None,
                        raise_exc: Exception | None = None):
    import httpx as _httpx

    reply = body if body is not None else {
        "responseId": "resp-1",
        "candidates": [{"content": {"parts": [{"text": "ok"}]}}],
        "usageMetadata": {"promptTokenCount": 1, "candidatesTokenCount": 1},
    }

    class _FakeResponse:
        def __init__(self):
            self.status_code = status_code
            self.text = '{"error": {"status": "INTERNAL"}}'

        def json(self):
            return reply

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, json=None, headers=None):
            captured.setdefault("calls", 0)
            captured["calls"] += 1
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers or {}
            if raise_exc is not None:
                raise raise_exc
            return _FakeResponse()

    del _httpx
    return _FakeClient


def _vertex_provider(monkeypatch, captured: dict, **client_kwargs):
    from app.core.config import settings
    from app.presence.providers import google as google_module

    monkeypatch.setattr(settings, "google_vertex_project", "proj-x")
    monkeypatch.setattr(settings, "google_vertex_location", "global")
    monkeypatch.setattr(google_module, "_refresh_vertex_token",
                        lambda: "fake-token")
    monkeypatch.setattr(google_module.httpx, "AsyncClient",
                        _fake_vertex_client(captured, **client_kwargs))
    return google_module.GooglePresenceProvider(
        "gemini-2.5-flash", backend="vertex_ai")


def test_vertex_request_sends_the_limits_the_bound_assumes(
    monkeypatch,
) -> None:
    """Формула і запит — одне ціле й на Vertex: глобальний ендпойнт,
    точна модель, заземлення, стеля виходу, вимкнений thinking, один
    кандидат, ОДИН запит на спостереження. Автентифікація — Bearer від
    google-auth; жодного API-ключа (і тим паче PSI) у заголовках."""
    captured: dict = {}
    provider = _vertex_provider(monkeypatch, captured)
    assert provider.tool_version == "vertex-generate_content-google_search@v1"

    answer = asyncio.run(provider.observe("best dental clinic?",
                                          country=None))
    assert answer.text == "ok"
    assert answer.provider_request_id == "resp-1"
    assert captured["calls"] == 1, "одне спостереження = один запит"
    assert captured["url"] == (
        "https://aiplatform.googleapis.com/v1/projects/proj-x"
        "/locations/global/publishers/google/models/"
        "gemini-2.5-flash:generateContent"
    )
    assert captured["headers"]["Authorization"] == "Bearer fake-token"
    assert "x-goog-api-key" not in captured["headers"], (
        "API-ключ не буває автентифікацією Vertex")
    payload = captured["json"]
    assert payload["tools"] == [{"google_search": {}}]
    config = payload["generationConfig"]
    assert config["maxOutputTokens"] == 1500
    assert config["candidateCount"] == 1
    assert config["thinkingConfig"]["thinkingBudget"] == 0


def test_vertex_backend_is_explicit_not_a_silent_fallback(
    monkeypatch,
) -> None:
    """Без проєкту Vertex клітинка чесно NOT_CONFIGURED із авторитетним
    нулем — навіть коли API-ключ Developer API налаштований: бекенди
    не підмінюють один одного мовчки."""
    from app.core.config import settings
    from app.presence.contracts import PresenceProviderError
    from app.presence.providers import google as google_module

    captured: dict = {}
    monkeypatch.setattr(settings, "google_vertex_project", None)
    monkeypatch.setattr(settings, "google_api_key", "dev-key-configured")
    monkeypatch.setattr(google_module.httpx, "AsyncClient",
                        _fake_vertex_client(captured))
    provider = google_module.GooglePresenceProvider(
        "gemini-2.5-flash", backend="vertex_ai")
    with pytest.raises(PresenceProviderError) as err:
        asyncio.run(provider.observe("q", country=None))
    assert err.value.status is ObservationStatus.NOT_CONFIGURED
    assert err.value.incurred_usd == 0.0
    assert captured.get("calls", 0) == 0, "жодного мережевого виклику"


def test_vertex_non_200_is_authoritatively_unbilled(monkeypatch) -> None:
    """Офіційне правило Vertex: «charged only for requests that return
    a 200 response code» — не-200 відомо коштує нуль, і резерв
    повертається (KNOWN_ZERO), а не висить невідомим."""
    from app.presence.contracts import PresenceProviderError

    for status_code, expected in ((500, ObservationStatus.PROVIDER_ERROR),
                                  (429, ObservationStatus.RATE_LIMITED),
                                  (404, ObservationStatus.NOT_CONFIGURED)):
        captured: dict = {}
        provider = _vertex_provider(monkeypatch, captured,
                                    status_code=status_code)
        with pytest.raises(PresenceProviderError) as err:
            asyncio.run(provider.observe("q", country=None))
        assert err.value.status is expected, status_code
        assert err.value.incurred_usd == 0.0, status_code


def test_vertex_permission_and_disabled_api_read_distinctly(
    monkeypatch,
) -> None:
    from app.presence.providers.google import _classified_http_error

    disabled = _classified_http_error(
        403, "Vertex AI API has not been used in project… SERVICE_DISABLED",
        incurred_usd=0.0)
    assert "вимкнено" in disabled.detail
    denied = _classified_http_error(
        403, "PERMISSION_DENIED: caller lacks role", incurred_usd=0.0)
    assert "aiplatform.user" in denied.detail
    assert disabled.status is ObservationStatus.NOT_CONFIGURED
    assert denied.status is ObservationStatus.NOT_CONFIGURED


def test_vertex_adc_token_refresh_transport_is_installed() -> None:
    """Живий смок 2026-09-02: автентифікація Vertex падала ImportError —
    google-auth оновлює токен через свій requests-транспорт, а пакета
    requests у продуктових залежностях не було. Тест стереже сам
    транспорт (конструювання Request тягне requests, без мережі), щоб
    залежність не зникла мовчки при наступному прибиранні."""
    import google.auth.transport.requests as ga_transport

    request = ga_transport.Request()
    assert callable(request)


def test_vertex_network_interruption_stays_unknown(monkeypatch) -> None:
    """Обриву відповіді жоден документ не пояснює — доля грошей
    невідома, і книга тримає зарезервований максимум."""
    import httpx as _httpx

    from app.presence.contracts import PresenceProviderError

    captured: dict = {}
    provider = _vertex_provider(
        monkeypatch, captured,
        raise_exc=_httpx.ConnectError("connection dropped"))
    with pytest.raises(PresenceProviderError) as err:
        asyncio.run(provider.observe("q", country=None))
    assert err.value.incurred_usd is None


def test_vertex_grounding_billed_only_when_sources_returned() -> None:
    """Vertex: «billed only when a Grounding Prompt successfully returns
    sources». Запити без джерел — пошук БУВ (метрика чесна), а одиниці
    білення немає. Developer API без такого твердження консервативно
    зараховує одиницю й за самі запити."""
    from app.presence.providers.google import parse_generate_content

    queries_only = {
        "candidates": [{
            "content": {"parts": [{"text": "answer"}]},
            "groundingMetadata": {"webSearchQueries": ["q1", "q2"]},
        }],
        "usageMetadata": {"promptTokenCount": 10,
                          "candidatesTokenCount": 20},
    }
    vertex = parse_generate_content(
        queries_only, fallback_model="gemini-2.5-flash",
        bill_grounding_on_sources_only=True)
    assert vertex.searched is True
    assert vertex.usage.searches == 0, "без джерел Vertex не білить"
    developer = parse_generate_content(
        queries_only, fallback_model="gemini-2.5-flash")
    assert developer.usage.searches == 1, "Developer API — консервативно"

    with_sources = {
        "candidates": [{
            "content": {"parts": [{"text": "answer"}]},
            "groundingMetadata": {
                "webSearchQueries": ["q1"],
                "groundingChunks": [
                    {"web": {"uri": "https://example.com/a",
                             "title": "A"}}],
            },
        }],
        "usageMetadata": {"promptTokenCount": 10,
                          "candidatesTokenCount": 20},
    }
    grounded = parse_generate_content(
        with_sources, fallback_model="gemini-2.5-flash",
        bill_grounding_on_sources_only=True)
    assert grounded.usage.searches == 1, "рівно одна одиниця білення"


def test_vertex_usage_metadata_produces_the_exact_actual_cost() -> None:
    """Факт рахується з авторитетного usageMetadata за цінами каталогу:
    токени + рівно одна одиниця заземлення."""
    from app.presence.providers.google import parse_generate_content

    body = {
        "candidates": [{
            "content": {"parts": [{"text": "answer"}]},
            "groundingMetadata": {
                "webSearchQueries": ["q"],
                "groundingChunks": [
                    {"web": {"uri": "https://example.com/a",
                             "title": "A"}}],
            },
        }],
        "usageMetadata": {"promptTokenCount": 1000,
                          "candidatesTokenCount": 100,
                          "thoughtsTokenCount": 0},
    }
    answer = parse_generate_content(
        body, fallback_model="gemini-2.5-flash",
        bill_grounding_on_sources_only=True)
    cap = capability("google", "gemini-2.5-flash")
    assert cap is not None
    cost = call_cost_usd(cap, input_tokens=answer.usage.input_tokens,
                         output_tokens=answer.usage.output_tokens,
                         searches=answer.usage.searches)
    # 1000×$0.30/M + 100×$2.50/M + 1×$35/1k
    assert abs(cost - (0.0003 + 0.00025 + 0.035)) < 1e-12


def test_policy_snapshot_carries_the_google_backend_without_secrets() -> None:
    import json as _json

    from app.presence.policy import from_stored, to_stored

    stored = to_stored(DEFAULT_POLICY)
    assert stored["providers"]["google"]["backend"] == "vertex_ai"
    assert stored["providers"]["anthropic"]["backend"] is None
    dumped = _json.dumps(stored)
    for needle in ("Bearer", "token", "credentials", "api_key"):
        assert needle not in dumped, needle

    roundtrip = from_stored(stored)
    assert roundtrip.providers["google"].backend == "vertex_ai"


def test_backend_validation_rejects_inconsistent_configuration() -> None:
    base = DEFAULT_POLICY.providers

    unknown = _policy(providers={
        **base, "google": ProviderPolicy(
            enabled=True, model="gemini-2.5-flash", backend="banana"),
    })
    assert any("невідомий бекенд" in e for e in validate(unknown))

    # vertex_ai з моделлю без рахованого максимуму — конфігурація,
    # несумісна з ціновим конвертом: платний шлях не відкриється.
    unboundable = _policy(providers={
        **base, "google": ProviderPolicy(
            enabled=True, model="gemini-3.7-flash", backend="vertex_ai"),
    })
    assert any("vertex_ai вимагає" in e for e in validate(unboundable))

    # developer_api із 3.7 — легальна сумісність (закриється бюджетом).
    legacy = _policy(providers={
        **base, "google": ProviderPolicy(
            enabled=True, model="gemini-3.7-flash",
            backend="developer_api"),
    })
    assert not any("бекенд" in e for e in validate(legacy))

    # Бекенд у провайдера, який бекендів не має, — помилка.
    misplaced = _policy(providers={
        **base, "anthropic": ProviderPolicy(
            enabled=True, model="claude-sonnet-4-6", backend="vertex_ai"),
    })
    assert any("не має сенсу" in e for e in validate(misplaced))


def test_provider_status_reports_vertex_state_without_secrets() -> None:
    from app.presence.policy import provider_status

    rows = {r["provider"]: r for r in provider_status(DEFAULT_POLICY)}
    google = rows["google"]
    assert google["backend"] == "vertex_ai"
    vertex = google["vertex"]
    assert set(vertex) == {"project_configured", "location", "credentials"}
    assert isinstance(vertex["project_configured"], bool)
    assert vertex["credentials"] in (
        "service_account_env", "adc_file", "not_detected_locally")
    assert "backend" not in rows["anthropic"]


def test_unconfigured_vertex_fails_before_any_reservation(
    monkeypatch,
) -> None:
    """Раннер: google з бекендом vertex_ai без проєкту — NOT_CONFIGURED
    ДО резервації, навіть із налаштованим ключем Developer API (фолбека
    немає). Нуль викликів, нуль резервів, нуль витрат."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "google_vertex_project", None)
    monkeypatch.setattr(settings, "google_api_key", "dev-key-configured")
    policy = _google_policy(runs_per_prompt=1)
    records, totals = asyncio.run(execute_run(
        policy=policy, prompt_set=_prompt_set(1), origin=ORIGIN,
        brand_aliases=ALIASES,
    ))
    assert [r.status for r in records] == [ObservationStatus.NOT_CONFIGURED]
    assert totals.cost_usd == 0.0


def _google_policy(**overrides) -> PresencePolicy:
    base = {
        "enabled": True,
        "providers": {"google": ProviderPolicy(enabled=True,
                                               model="gemini-2.5-flash")},
        "runs_per_prompt": 2, "max_prompts": 15, "retry_limit": 0,
        "raw_retention_days": 30, "concurrency": 1,
        "modes": ("natural",),
    }
    base.update(overrides)
    return PresencePolicy(**base)


def _google_bound() -> Decimal:
    cap = capability("google", "gemini-2.5-flash")
    assert cap is not None
    ceilings = REQUEST_CEILINGS["google"]
    bound = max_attempt_cost_usd(
        cap, max_output_tokens=ceilings.max_output_tokens,
        max_searches=ceilings.max_searches)
    assert bound is not None
    return bound


def test_google_cell_executes_under_the_computed_bound() -> None:
    """Google виконується тим самим шляхом книги: резервація рахованого
    максимуму до виклику, факт сідає на її місце, наступна клітинка
    допускається лише коли факт + новий максимум вміщаються."""
    import asyncio as aio

    from app.presence.contracts import ProviderAnswer, ProviderUsage

    class GoogleLike:
        name = "google"
        model = "gemini-2.5-flash"
        tool_version = "generate_content-google_search@v1beta"

        def __init__(self) -> None:
            self.calls = 0

        async def observe(self, prompt_text, *, country,
                          require_search=False):
            self.calls += 1
            await aio.sleep(0.01)
            return ProviderAnswer(
                text="ok", searched=True,
                usage=ProviderUsage(input_tokens=1000, output_tokens=100,
                                    searches=1),
            )

    provider = GoogleLike()
    # Одна клітинка: тест міряє САМУ вартість виклику за каталогом, а не
    # допуск — стель витрат більше немає, і резерв нікого не блокує.
    policy = _google_policy(runs_per_prompt=1)
    records, totals = asyncio.run(execute_run(
        policy=policy, prompt_set=_prompt_set(1), origin=ORIGIN,
        brand_aliases=ALIASES,
        providers_override={"google": provider},
    ))
    assert provider.calls == 1
    statuses = sorted(r.status.value for r in records)
    assert statuses == ["ok"]
    # Факт = 1000×$0.30/M + 100×$2.50/M + 1×$35/1k — за каталогом.
    assert abs(totals.cost_usd - (0.0003 + 0.00025 + 0.035)) < 1e-9


def test_google_unknown_cost_commits_the_reserved_maximum() -> None:
    import asyncio as aio

    from app.presence.contracts import PresenceProviderError

    class TimingOut:
        name = "google"
        model = "gemini-2.5-flash"
        tool_version = "generate_content-google_search@v1beta"
        calls = 0

        async def observe(self, prompt_text, *, country,
                          require_search=False):
            TimingOut.calls += 1
            await aio.sleep(0.01)
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, "таймаут",
                incurred_usd=None)

    from app.presence.budget import MemoryAttemptLedger

    TimingOut.calls = 0
    # Стель немає, тож «невідома доля тримає гроші» доводиться прямо:
    # книга тримає зарезервований максимум, а не списує його в нуль.
    ledger = MemoryAttemptLedger()
    policy = _google_policy(runs_per_prompt=1)
    records, _ = asyncio.run(execute_run(
        policy=policy, prompt_set=_prompt_set(1), origin=ORIGIN,
        brand_aliases=ALIASES,
        providers_override={"google": TimingOut()},
        ledger=ledger,
    ))
    assert TimingOut.calls == 1
    statuses = sorted(r.status.value for r in records)
    assert statuses == ["provider_error"]
    assert ledger.spent_by_provider().get("google", 0) > 0, (
        "невідома вартість тримається як витрата, а не нуль")


def test_restored_four_provider_deliverability_combinations() -> None:
    """Чотири увімкнені провайдери → сувора більшість три, і придатною
    може бути БУДЬ-ЯКА трійка: google рахується нарівні з рештою, а
    його відсутність більше не вимагає всіх трьох інших поіменно."""
    from app.services.presence_service import _deliverable

    policy = _policy(providers={
        name: ProviderPolicy(enabled=True, model="scripted-model")
        for name in ("anthropic", "openai", "perplexity", "google")
    })
    run = object()

    def ok(**counts: int) -> dict[str, int]:
        base = {"anthropic": 0, "openai": 0, "perplexity": 0, "google": 0}
        base.update(counts)
        return base

    # google + будь-які два інші — придатний.
    assert _deliverable(run, policy,
                        ok(google=30, anthropic=30, perplexity=30),
                        planned_per_provider=30) is True
    # google недоступний, решта три — придатний.
    assert _deliverable(run, policy,
                        ok(anthropic=30, openai=30, perplexity=30),
                        planned_per_provider=30) is True
    # один не-google провайдер випав, google + два інші — придатний.
    assert _deliverable(run, policy,
                        ok(google=30, openai=30, perplexity=30),
                        planned_per_provider=30) is True
    # лише два з чотирьох — непридатний.
    assert _deliverable(run, policy,
                        ok(google=30, openai=30),
                        planned_per_provider=30) is False


def test_modes_double_the_cells_and_mark_records() -> None:
    provider = ScriptedPresenceProvider([ScriptedReply("ok")])
    policy = _policy(modes=("natural", "explicit"), runs_per_prompt=1)
    records, totals = _run(policy, _prompt_set(2), provider)
    assert totals.observations == 4  # 2 промпти x 2 режими x 1 повтор
    assert {r.mode.value for r in records} == {"natural", "explicit"}


def test_explicit_mode_appends_instruction_and_requires_search() -> None:
    provider = ScriptedPresenceProvider([ScriptedReply("ok")])
    policy = _policy(modes=("explicit",), runs_per_prompt=1)
    records, _ = _run(policy, _prompt_set(1), provider)
    sent = provider.calls[0]
    assert sent.startswith("best dental clinic?")
    assert "search the web" in sent, "інструкція заземлення додана"
    assert provider.required_search_calls == [True]
    assert records[0].sent_text == sent, "точний надісланий текст збережено"


def test_natural_mode_sends_the_prompt_untouched() -> None:
    provider = ScriptedPresenceProvider([ScriptedReply("ok")])
    policy = _policy(modes=("natural",), runs_per_prompt=1)
    _records, _ = _run(policy, _prompt_set(1), provider)
    assert provider.calls[0] == "best dental clinic?"
    assert provider.required_search_calls == [False]


def test_metrics_keep_mode_denominators_apart() -> None:
    def row(mode: str, mentioned: bool) -> dict:
        return {"provider": "openai", "prompt_id": "category-1",
                "category": "category", "segment": "unbranded",
                "mode": mode, "status": "ok", "searched": True,
                "brand_mentioned": mentioned, "domain_cited": False,
                "domain_linked": False, "recommended": None,
                "observed_domains": []}

    rows = [row("natural", True), row("natural", True),
            row("explicit", False)]
    metrics = build_metrics(rows, min_observations=2)
    natural = metrics["modes"]["natural"]["combined"]["mention_presence"]
    explicit = metrics["modes"]["explicit"]["combined"]["mention_presence"]
    assert natural["numerator"] == 2 and natural["denominator"] == 2
    assert explicit["numerator"] == 0 and explicit["denominator"] == 1
    assert natural["rate"] == 1.0
    assert explicit["rate"] is None, "нижче порога — жодного відсотка"


def test_old_rows_without_mode_read_as_natural() -> None:
    rows = [{"provider": "openai", "prompt_id": "p", "category": "category",
             "segment": "unbranded", "status": "ok", "searched": True,
             "brand_mentioned": True, "domain_cited": False,
             "recommended": None, "observed_domains": []}]
    metrics = build_metrics(rows)
    assert "natural" in metrics["modes"]
    assert metrics["per_provider"], "P0-читачі досі бачать верхній рівень"


def test_unicode_lookalike_brand_still_matches() -> None:
    # Повноширинні латинські форми нормалізуються NFKC перед збігом.
    record = _interpret("Ｔry Ａcme Ｄental today", [])
    assert record.brand_mentioned is True


def test_unsafe_citation_schemes_are_dropped() -> None:
    record = _interpret(
        "answer", ["javascript:alert(1)", "data:text/html,x",
                   "https://example.com/page"])
    assert record.cited_urls == ["https://example.com/page"]
    assert record.domain_cited is True


def test_own_url_in_answer_text_is_a_direct_link_not_a_citation() -> None:
    record = _interpret(
        "See https://example.com/pricing for details.", [])
    assert record.domain_linked is True
    assert record.linked_urls == ["https://example.com/pricing"]
    assert record.domain_cited is False, "текстове посилання — не цитата"


def test_four_provider_run_needs_three_deliverable() -> None:
    from app.services.presence_service import _deliverable

    policy = _policy(providers={
        name: ProviderPolicy(enabled=True, model="scripted-model")
        for name in ("anthropic", "openai", "perplexity", "google")
    })
    run = object()
    ok = {"anthropic": 30, "openai": 30, "perplexity": 30, "google": 0}
    assert _deliverable(run, policy, ok, planned_per_provider=30) is True
    ok_two = {"anthropic": 30, "openai": 30, "perplexity": 0, "google": 0}
    assert _deliverable(run, policy, ok_two, planned_per_provider=30) is False


def test_policy_roundtrip_keeps_new_fields() -> None:
    from app.presence.policy import from_stored, to_stored

    policy = _policy(modes=("explicit",), min_observations_for_rate=5,
                     provider_timeout_s=45.0, languages=("uk",))
    restored = from_stored(to_stored(policy))
    assert restored.modes == ("explicit",)
    assert restored.min_observations_for_rate == 5
    assert restored.provider_timeout_s == 45.0
    assert restored.languages == ("uk",)


def test_stored_p0_policy_without_modes_stays_natural_only() -> None:
    """Старий збережений рядок не дорожчає сам собою."""
    from app.presence.policy import from_stored

    p0 = {"enabled": True, "providers": {
        "openai": {"enabled": True, "model": "gpt-5.1"}}}
    policy = from_stored(p0)
    assert policy.modes == ("natural",)


def test_policy_rejects_unknown_mode() -> None:
    from app.presence.policy import validate

    bad = _policy(modes=("natural", "psychic"))
    assert any("psychic" in e for e in validate(bad))


def test_gemini_redirect_citations_unwrap_to_the_source_domain() -> None:
    """Редірект vertexaisearch → домен із провайдерського title."""
    from app.presence.providers.google import parse_interaction

    body = {"model": "gemini-3.7-flash", "steps": [
        {"type": "google_search_call", "queries": ["q"]},
        {"type": "model_output", "content": [{
            "type": "text", "text": "Clinics list",
            "annotations": [
                {"type": "url_citation", "title": "example.com",
                 "url": ("https://vertexaisearch.cloud.google.com/"
                         "grounding-api-redirect/AUZIabc")},
                {"type": "url_citation", "title": "Not A Domain Title",
                 "url": ("https://vertexaisearch.cloud.google.com/"
                         "grounding-api-redirect/AUZIdef")},
                {"type": "url_citation", "title": "direct",
                 "url": "https://direct.example.org/page"},
            ],
        }]},
    ], "usage": {"total_input_tokens": 1, "total_output_tokens": 2}}
    answer = parse_interaction(body, fallback_model="gemini-3.7-flash")
    assert "https://example.com/" in answer.cited_urls, "домен із title"
    assert any("grounding-api-redirect" in u for u in answer.cited_urls), (
        "нерозгортаний title лишає сирий редірект — без вигадок")
    assert "https://direct.example.org/page" in answer.cited_urls


# ── твердий бюджет: резервація до виклику ────────────────────────────


def _counting_provider(cost_searches: int = 100, delay: float = 0.01):
    """Провайдер, який справді віддає керування й рахує виклики.

    100 пошуків × $8/1k (scripted) = $0.8 фактичних за виклик.
    """
    import asyncio as aio

    from app.presence.contracts import ProviderAnswer, ProviderUsage

    class Counting:
        name = "scripted"
        model = "scripted-model"
        tool_version = "t"

        def __init__(self) -> None:
            self.calls = 0

        async def observe(self, prompt_text, *, country, require_search=False):
            self.calls += 1
            await aio.sleep(delay)
            return ProviderAnswer(
                text="ok", searched=True,
                usage=ProviderUsage(input_tokens=0, output_tokens=0,
                                    searches=cost_searches),
            )

    return Counting()


def test_a_retry_needs_its_own_reservation() -> None:
    import asyncio as aio

    from app.presence.contracts import (
        PresenceProviderError,
        ProviderAnswer,
        ProviderUsage,
    )

    class FlakyThenBlocked:
        name = "scripted"
        model = "scripted-model"
        tool_version = "t"
        calls = 0

        async def observe(self, prompt_text, *, country, require_search=False):
            FlakyThenBlocked.calls += 1
            await aio.sleep(0.01)
            if FlakyThenBlocked.calls == 1:
                # Провайдер АВТОРИТЕТНО оголошує нуль (у продукті так
                # роблять лише збої до мережі): резерв повертається.
                raise PresenceProviderError(
                    ObservationStatus.RATE_LIMITED, "429",
                    incurred_usd=0.0)
            return ProviderAnswer(
                text="ok", searched=True,
                usage=ProviderUsage(0, 0, searches=100))

    FlakyThenBlocked.calls = 0
    policy = _policy(runs_per_prompt=1, retry_limit=1, concurrency=1)
    records, totals = _run(policy, _prompt_set(1), FlakyThenBlocked())
    # 429 повернув резерв (відомий нуль) → повтор зарезервував наново й
    # пройшов; факт 0.8 ≤ стеля.
    assert FlakyThenBlocked.calls == 2
    assert records[0].status is ObservationStatus.OK
    assert totals.cost_usd <= 1.5 + 1e-9


def test_timeout_with_unknown_cost_retains_the_reserved_bound() -> None:
    import asyncio as aio

    from app.presence.contracts import PresenceProviderError

    class TimingOut:
        name = "scripted"
        model = "scripted-model"
        tool_version = "t"
        calls = 0

        async def observe(self, prompt_text, *, country, require_search=False):
            TimingOut.calls += 1
            await aio.sleep(0.01)
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, "таймаут",
                incurred_usd=None)  # доля грошей НЕВІДОМА

    from app.presence.budget import MemoryAttemptLedger

    TimingOut.calls = 0
    ledger = MemoryAttemptLedger()
    policy = _policy(runs_per_prompt=1, retry_limit=0, concurrency=1)
    records, _ = asyncio.run(execute_run(
        policy=policy, prompt_set=_prompt_set(1), origin=ORIGIN,
        brand_aliases=ALIASES,
        providers_override={"scripted": TimingOut()},
        ledger=ledger,
    ))
    # Таймаут утримує резерв як витрату: невідоме ≠ нуль.
    assert TimingOut.calls == 1
    statuses = sorted(r.status.value for r in records)
    assert statuses == ["provider_error"]
    assert ledger.spent_by_provider().get("scripted", 0) > 0, (
        "невідома вартість тримається як витрата, а не нуль")


def test_a_known_unbilled_error_releases_the_full_reservation() -> None:
    import asyncio as aio

    from app.presence.contracts import (
        PresenceProviderError,
        ProviderAnswer,
        ProviderUsage,
    )

    class ErrorThenOk:
        name = "scripted"
        model = "scripted-model"
        tool_version = "t"
        calls = 0

        async def observe(self, prompt_text, *, country, require_search=False):
            ErrorThenOk.calls += 1
            await aio.sleep(0.01)
            if ErrorThenOk.calls == 1:
                raise PresenceProviderError(
                    ObservationStatus.REFUSED, "HTTP 400",
                    incurred_usd=0.0)  # відхилений запит не білиться
            return ProviderAnswer(text="ok", searched=True,
                                  usage=ProviderUsage(0, 0, searches=100))

    ErrorThenOk.calls = 0
    policy = _policy(runs_per_prompt=2, retry_limit=0, concurrency=1)
    _records, totals = _run(policy, _prompt_set(1), ErrorThenOk())
    # Повернутий резерв дозволив другій клітинці стартувати.
    assert ErrorThenOk.calls == 2
    assert abs(totals.cost_usd - 0.8) < 1e-9


def test_missing_cost_bound_fails_closed_without_a_call() -> None:
    """Модель, чий запит не вміє обмежити тарифіковані пошуки (той самий
    клас, що google/Interactions), лишає максимум спроби нерахованим —
    і платний шлях закривається ДО виклику."""
    provider = _counting_provider()
    policy = _policy(providers={
        "scripted": ProviderPolicy(enabled=True, model="scripted-unbounded"),
    }, runs_per_prompt=2)
    records, totals = _run(policy, _prompt_set(1), provider)
    assert provider.calls == 0, "без захисної межі платний виклик не стартує"
    assert all(
        r.status is ObservationStatus.BUDGET_COST_BOUND_UNAVAILABLE
        for r in records
    )
    assert all("budget_cost_bound_unavailable" in (r.error or "")
               for r in records)
    assert totals.cost_usd == 0.0


def test_budget_statuses_are_not_observations() -> None:
    """Блок бюджету — «не спостережено», не нульова присутність, і не
    рахується в придатність: непридатний прогін повертає право."""
    from app.presence.contracts import OBSERVED_STATUSES

    assert ObservationStatus.BUDGET_EXHAUSTED not in OBSERVED_STATUSES
    assert (ObservationStatus.BUDGET_COST_BOUND_UNAVAILABLE
            not in OBSERVED_STATUSES)


def test_attempt_bound_is_derived_from_documented_limits_only() -> None:
    """Формула максимуму: стеля входу (контекстне вікно) × ціна входу +
    стеля виходу × ціна виходу + ліміт пошуків × ціна пошуку. Жодних
    спостережених середніх і множників «про запас»."""
    assert BOUND == Decimal("1.0255")  # 1M×$1/M + 1500×$1/M + 3×$8/1k

    # Кожен продуктовий провайдер, чий запит уміє обмежити білені
    # пошукові одиниці, має рахований максимум — google включно.
    for provider, model in (("anthropic", "claude-sonnet-4-6"),
                            ("openai", "gpt-5.1"),
                            ("perplexity", "perplexity/sonar"),
                            ("google", "gemini-2.5-flash")):
        cap = capability(provider, model)
        assert cap is not None
        ceilings = REQUEST_CEILINGS[provider]
        bound = max_attempt_cost_usd(
            cap, max_output_tokens=ceilings.max_output_tokens,
            max_searches=ceilings.max_searches)
        assert bound is not None and bound > 0, (provider, model)

    # …а gemini-3.x білиться ЗА КОЖЕН пошуковий запит без документованої
    # стелі кількості — максимум нерахований, платний шлях закритий
    # (fail closed), і це рішення каталогу (max_searches_boundable),
    # а не раннера. WATCHLIST до примусової межі від Google.
    google_cap = capability("google", "gemini-3.7-flash")
    assert google_cap is not None
    assert google_cap.max_searches_boundable is False
    google_ceilings = REQUEST_CEILINGS["google"]
    assert max_attempt_cost_usd(
        google_cap,
        max_output_tokens=google_ceilings.max_output_tokens,
        max_searches=google_ceilings.max_searches,
    ) is None


def test_pricing_version_tracks_the_price_list(monkeypatch) -> None:
    """Відбиток прейскуранта детермінований і чутливий до цін: інша
    ціна — інший конверт, і виконання замовленого за старими цінами
    прогону мусить упасти закрито, а не порахуватися мовчки."""
    import dataclasses

    from app.ai import catalog as ai_catalog

    first = ai_catalog.pricing_version()
    assert first == ai_catalog.pricing_version()
    assert len(first) == 12

    key = ("scripted", "scripted-model")
    changed = dataclasses.replace(
        ai_catalog.CATALOG[key], input_usd_per_mtok=2.0)
    monkeypatch.setitem(ai_catalog.CATALOG, key, changed)
    assert ai_catalog.pricing_version() != first


def test_actual_cost_above_the_bound_halts_the_run() -> None:
    """Факт, більший за зарезервований максимум, означає, що конверт цін
    недійсний. Спроба стає COST_BOUND_VIOLATED, решта платних викликів
    прогону НЕ стартує, і межа не підвищується мовчки ніколи."""
    provider = _counting_provider(cost_searches=200)  # факт $1.6 > ~1.0255
    policy = _policy(runs_per_prompt=3, concurrency=1)
    records, totals = _run(policy, _prompt_set(1), provider)
    assert provider.calls == 1, "після зламаного конверта викликів немає"
    assert totals.cost_bound_violation is not None
    assert "1.6" in totals.cost_bound_violation
    halted = [r for r in records
              if r.status is ObservationStatus.BUDGET_EXHAUSTED]
    assert len(halted) == 2
    assert all("конверт" in (r.error or "") for r in halted)
    # Доказ зберігся: перший виклик — повноцінне спостереження з фактом.
    assert records[0].status is ObservationStatus.OK
    assert abs(records[0].cost_usd - 1.6) < 1e-9
