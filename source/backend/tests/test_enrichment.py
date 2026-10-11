"""AI-збагачення: межі, маршрути, провенанс і правило правди.

Жоден тест не звертається до мережі й не витрачає грошей: провайдер —
протокол саме для того, щоб перевірка поведінки була безкоштовною.

Головне, що тут доводиться, — не «модель гарно пише», а що вихід моделі
фізично не може стати новою знахідкою, змінити бал чи посилатися на те,
чого у вході не було.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.enrich.contracts import (
    AttemptOutcome,
    EnrichmentStatus,
    ProviderCall,
    ProviderError,
    TaskType,
    TaskValidationError,
)
from app.enrich.identity import input_hash
from app.enrich.providers.scripted import ScriptedProvider
from app.enrich.routing import (
    DEFAULT_ROUTES,
    PRICING_VERSION,
    RouteCandidate,
    cost_estimate,
    route_for,
)
from app.enrich.runner import execute
from app.enrich.tasks import TASKS, build_request
from app.enrich.tasks.remediation import REMEDIATION_PLAN
from app.enrich.tasks.root_cause import ROOT_CAUSE_GROUPING
from app.enrich.tasks.site_understanding import SITE_UNDERSTANDING

ENRICH = Path(__file__).resolve().parents[1] / "app" / "enrich"

FINDINGS = [
    {
        "ref": "seo.canonical:missing",
        "module": "seo",
        "severity": "high",
        "title": "17 сторінок без canonical",
        "pages": 17,
        "examples": ["https://example.com/a", "https://example.com/b"],
        "evidence": "missing=17; checked=20",
    },
    {
        "ref": "seo.title:duplicate",
        "module": "seo",
        "severity": "medium",
        "title": "Однаковий title на 12 сторінках",
        "pages": 12,
        "examples": ["https://example.com/a"],
        "evidence": "duplicates=12",
    },
]


def _payload() -> dict:
    return {"findings": FINDINGS, "site": "Магазин подушок"}


async def _run(spec, payload, script, *, routes=None, provider=None, **kwargs):
    request = build_request(spec, payload)
    used = provider or ScriptedProvider("fake", script)
    return (
        await execute(
            spec,
            request,
            routes=routes or {spec.type: (RouteCandidate("fake", "model-x"),)},
            provider_factory=lambda _name: used,
            timeout_s=kwargs.get("timeout_s", 5.0),
            max_attempts=kwargs.get("max_attempts", 2),
            max_output_tokens=1000,
        ),
        used,
    )


# ── архітектура ────────────────────────────────────────────────────────────


def _module_sources(*relative: str) -> list[tuple[Path, str]]:
    files: list[Path] = []
    for rel in relative:
        target = ENRICH / rel
        files += sorted(target.rglob("*.py")) if target.is_dir() else [target]
    return [(path, path.read_text(encoding="utf-8")) for path in files]


def test_task_code_imports_no_provider_sdk():
    """Логіка задач не знає жодного SDK. Провайдер — деталь за адаптером."""
    forbidden = {"anthropic", "openai", "google", "mistralai", "cohere"}
    for path, source in _module_sources("tasks", "runner.py", "contracts.py", "identity.py"):
        for node in ast.walk(ast.parse(source)):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                root = name.split(".")[0]
                assert root not in forbidden, f"{path.name}: імпорт {name}"


def test_task_logic_never_names_a_provider_or_model():
    """`root_cause → claude-sonnet` — саме те, чого тут не має бути.

    Імена живуть у маршрутах і в адаптерах; задача описує потребу.
    """
    banned = ("claude", "gpt-", "gemini", "anthropic", "openai", "sonnet", "opus", "haiku")
    for path, source in _module_sources("tasks", "runner.py"):
        lowered = source.lower()
        for word in banned:
            assert word not in lowered, f"{path.name} згадує «{word}»"


def test_model_names_live_only_in_routing():
    """Позитивна половина попереднього: у маршрутах вони саме мають бути."""
    models = {c.model for candidates in DEFAULT_ROUTES.values() for c in candidates}
    assert models, "маршрути без жодної моделі — шар не змогли б виконати"
    assert all(DEFAULT_ROUTES[task] for task in TaskType), "кожна задача має кандидата"


# ── діалект провайдера проти канонічного контракту ────────────────────────


def test_canonical_schema_keeps_the_constraint_provider_cannot_take():
    """Anthropic не диктує контракт Crawldy.

    `minimum` лишається в канонічній схемі, хоч провайдер його для цілих
    і відбиває: обмеження — наше твердження про план, а не побажання до
    чужого API.
    """
    order = REMEDIATION_PLAN.schema["properties"]["steps"]["items"]["properties"]["order"]
    assert order == {"type": "integer", "minimum": 1}


def test_provider_schema_drops_only_the_known_incompatibility():
    """У схему для Anthropic `minimum` не їде, решта лишається цілою.

    Живий виклик 2026-08-24 відбивав саме його:
    «For 'integer' type, property 'minimum' is not supported».
    """
    from app.enrich.providers.anthropic import to_provider_schema

    wire = to_provider_schema(REMEDIATION_PLAN.schema)
    order = wire["properties"]["steps"]["items"]["properties"]["order"]
    assert order == {"type": "integer"}, "minimum поїхав до провайдера"

    # Канонічний обʼєкт не мутовано: він спільний для всіх провайдерів.
    canonical = REMEDIATION_PLAN.schema["properties"]["steps"]["items"]["properties"]["order"]
    assert canonical["minimum"] == 1

    # Усе інше доїхало без втрат — зокрема доведено підтримуване.
    assert wire["properties"]["steps"]["items"]["required"] == (
        REMEDIATION_PLAN.schema["properties"]["steps"]["items"]["required"]
    )
    assert wire["additionalProperties"] is False
    groups = ROOT_CAUSE_GROUPING.schema["properties"]["groups"]["items"]["properties"]
    wire_groups = to_provider_schema(ROOT_CAUSE_GROUPING.schema)["properties"]["groups"]["items"][
        "properties"
    ]
    assert wire_groups["finding_refs"]["minItems"] == groups["finding_refs"]["minItems"]
    assert wire_groups["cause_confidence"]["enum"] == groups["cause_confidence"]["enum"]


def test_semantic_concepts_live_above_the_provider_adapter():
    """Покриття й впевненість у причині — поняття Crawldy, не транспорту.

    Адаптер має право лише перекладати діалект схеми. Щойно він почне
    знати про `cause_confidence` чи `coverage`, зміна провайдера стане
    зміною семантики продукту.
    """
    import inspect

    from app.enrich.providers import anthropic as adapter

    source = inspect.getsource(adapter)
    # Імена понять, а не звичайні англійські слова: «supported» законно
    # трапляється в процитованому тексті помилки провайдера, і ловити
    # його означало б плутати документацію зі знанням семантики.
    for concept in (
        "cause_confidence",
        "cause_hypothesis",
        "cluster_summary",
        "causal_basis",
        "coverage",
        "pages_read",
        "pages_known",
    ):
        assert concept not in source, f"адаптер знає про семантику «{concept}»"


def test_canonical_schemas_contain_no_provider_concessions():
    """У канонічних схемах немає поступок чужому API.

    Перевірка позитивна: `minimum` мусить бути на місці. Саме його
    зняття з канону і було поступкою, яку довелося скасувати.
    """
    order = REMEDIATION_PLAN.schema["properties"]["steps"]["items"]["properties"]["order"]
    assert order.get("minimum") == 1
    groups = ROOT_CAUSE_GROUPING.schema["properties"]["groups"]["items"]["properties"]
    assert groups["finding_refs"].get("minItems") == 1


def test_unknown_keywords_are_not_stripped_silently():
    """Невідома несумісність мусить впасти голосно, а не зникнути.

    Узагальнений «прибирач усього підозрілого» вирізав би й ті
    обмеження, які провайдер приймає, — і ми б не дізналися про втрату.
    """
    from app.enrich.providers.anthropic import to_provider_schema

    schema = {
        "type": "object",
        "properties": {
            "n": {"type": "integer", "minimum": 1, "maximum": 9, "multipleOf": 3},
            "s": {"type": "string", "pattern": "^a", "minLength": 2},
        },
    }
    wire = to_provider_schema(schema)
    assert "minimum" not in wire["properties"]["n"], "відоме несумісне мало зникнути"
    # Решта — не наша справа: не спостерігали, отже не чіпаємо.
    assert wire["properties"]["n"]["maximum"] == 9
    assert wire["properties"]["n"]["multipleOf"] == 3
    assert wire["properties"]["s"]["pattern"] == "^a"
    assert wire["properties"]["s"]["minLength"] == 2


def test_canonical_validator_enforces_the_bound_provider_never_saw():
    """`order = 0` відбивається локально — саме тому межа й не втрачена."""
    payload = {
        "findings": [{"ref": "seo.canonical:missing", "severity": "high", "title": "t", "rank": 1}],
        "groups": [],
        "site": "",
    }
    step = {
        "title": "Fix canonical",
        "why_now": "спільна причина",
        "finding_refs": ["seo.canonical:missing"],
        "group_ids": [],
        "depends_on": [],
    }

    accepted = REMEDIATION_PLAN.validate({"steps": [{**step, "order": 1}]}, payload)
    assert accepted["steps"][0]["order"] == 1

    for bad in (0, -3):
        with pytest.raises(TaskValidationError, match="order"):
            REMEDIATION_PLAN.validate({"steps": [{**step, "order": bad}]}, payload)


# ── маршрутизація й fallback ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_routing_picks_the_configured_candidate():
    providers: dict[str, ScriptedProvider] = {
        "alpha": ScriptedProvider("alpha", lambda c: ROOT_CAUSE_GROUPING.dry_output(_payload())),
        "beta": ScriptedProvider("beta", lambda c: ROOT_CAUSE_GROUPING.dry_output(_payload())),
    }
    request = build_request(ROOT_CAUSE_GROUPING, _payload())

    outcome = await execute(
        ROOT_CAUSE_GROUPING,
        request,
        routes={TaskType.ROOT_CAUSE_GROUPING: (RouteCandidate("beta", "model-b"),)},
        provider_factory=lambda name: providers[name],
        timeout_s=5.0,
        max_attempts=2,
        max_output_tokens=1000,
    )

    assert outcome.status is EnrichmentStatus.COMPLETED
    assert not providers["alpha"].calls, "викликали не того, кого просив маршрут"
    assert providers["beta"].calls
    assert outcome.attempts[-1].provider == "beta"
    assert outcome.attempts[-1].model == "model-b"


@pytest.mark.asyncio
async def test_switching_provider_and_model_needs_no_task_change():
    """Порівняння провайдерів — це конфігурація, а не правка коду.

    Той самий обʼєкт задачі виконується двома різними «провайдерами» з
    різними моделями; у задачі не змінено жодного рядка.
    """
    payload = _payload()
    seen: list[tuple[str, str]] = []

    def make(name: str, model: str) -> ScriptedProvider:
        def script(call: ProviderCall) -> dict:
            seen.append((name, call.model))
            return ROOT_CAUSE_GROUPING.dry_output(payload)

        return ScriptedProvider(name, script)

    registry = {"alpha": make("alpha", "model-a"), "beta": make("beta", "model-b")}
    for provider, model in (("alpha", "model-a"), ("beta", "model-b")):
        outcome = await execute(
            ROOT_CAUSE_GROUPING,
            build_request(ROOT_CAUSE_GROUPING, payload),
            routes={TaskType.ROOT_CAUSE_GROUPING: (RouteCandidate(provider, model),)},
            provider_factory=lambda name: registry[name],
            timeout_s=5.0,
            max_attempts=1,
            max_output_tokens=1000,
        )
        assert outcome.status is EnrichmentStatus.COMPLETED

    assert seen == [("alpha", "model-a"), ("beta", "model-b")]


@pytest.mark.asyncio
async def test_fallback_is_journalled_not_hidden():
    """Друга спроба після невдалої першої — і обидві видно в журналі."""
    payload = _payload()
    broken = ScriptedProvider("alpha", fail_with=ProviderError("provider_error", "503"))
    working = ScriptedProvider("beta", lambda c: ROOT_CAUSE_GROUPING.dry_output(payload))
    registry = {"alpha": broken, "beta": working}

    outcome = await execute(
        ROOT_CAUSE_GROUPING,
        build_request(ROOT_CAUSE_GROUPING, payload),
        routes={
            TaskType.ROOT_CAUSE_GROUPING: (
                RouteCandidate("alpha", "model-a"),
                RouteCandidate("beta", "model-b"),
            )
        },
        provider_factory=lambda name: registry[name],
        timeout_s=5.0,
        max_attempts=2,
        max_output_tokens=1000,
    )

    assert outcome.status is EnrichmentStatus.COMPLETED
    assert len(outcome.attempts) == 2, "невдала спроба зникла з журналу"
    first, second = outcome.attempts
    assert (first.provider, first.outcome) == ("alpha", AttemptOutcome.PROVIDER_ERROR)
    assert first.error_category == "provider_error"
    assert (second.provider, second.outcome) == ("beta", AttemptOutcome.OK)


@pytest.mark.asyncio
async def test_attempt_timeout_is_ours_not_the_sdk_default():
    """Один виклик не має права тримати платний процес десять хвилин."""
    import asyncio

    class Hanging:
        name = "slow"

        async def generate_structured(self, call: ProviderCall):
            await asyncio.sleep(10)
            raise AssertionError("не мали дочекатися")

    outcome = await execute(
        ROOT_CAUSE_GROUPING,
        build_request(ROOT_CAUSE_GROUPING, _payload()),
        routes={TaskType.ROOT_CAUSE_GROUPING: (RouteCandidate("slow", "model-s"),)},
        provider_factory=lambda _name: Hanging(),
        timeout_s=0.05,
        max_attempts=1,
        max_output_tokens=1000,
    )

    assert outcome.status is EnrichmentStatus.UNAVAILABLE
    assert outcome.attempts[0].outcome is AttemptOutcome.TIMEOUT


@pytest.mark.asyncio
async def test_no_configured_candidate_is_unavailable_not_a_crash():
    outcome = await execute(
        ROOT_CAUSE_GROUPING,
        build_request(ROOT_CAUSE_GROUPING, _payload()),
        routes={},
        provider_factory=lambda _name: ScriptedProvider(),
        timeout_s=1.0,
        max_attempts=1,
        max_output_tokens=100,
    )
    assert outcome.status is EnrichmentStatus.UNAVAILABLE
    assert outcome.result is None


# ── провенанс ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_attempt_records_what_actually_ran():
    outcome, _ = await _run(
        ROOT_CAUSE_GROUPING, _payload(), lambda c: ROOT_CAUSE_GROUPING.dry_output(_payload())
    )
    attempt = outcome.attempts[0]

    assert attempt.provider == "fake"
    assert attempt.model == "model-x"
    assert attempt.request_id
    assert attempt.input_tokens and attempt.output_tokens
    assert attempt.total_tokens == attempt.input_tokens + attempt.output_tokens
    assert attempt.latency_ms is not None
    assert attempt.started_at and attempt.finished_at


def test_cost_prices_every_token_class_separately():
    """Кеш тарифікується інакше за звичайний вхід — і формула це знає.

    Ставки claude-opus-5: вхід $5, вихід $25, запис у кеш $6.25,
    читання з кешу $0.50 за мільйон. Одна ставка на все занизила б
    вартість рівно на кешовану частину.
    """
    cost, version = cost_estimate("claude-opus-5", 1_000_000, 1_000_000)
    assert cost == pytest.approx(30.0)
    assert version == PRICING_VERSION

    with_cache, _ = cost_estimate("claude-opus-5", 1_000_000, 1_000_000, 1_000_000, 1_000_000)
    assert with_cache == pytest.approx(30.0 + 6.25 + 0.50)
    assert with_cache > cost, "кешовані токени зникли з рахунку"


def test_unknown_cost_stays_null_and_is_never_invented():
    """Токени є, ціни немає — вартість лишається NULL.

    Правдоподібне число в журналі витрат гірше за його відсутність:
    на нього спираються рішення, а перевірити його нічим.
    """
    cost, version = cost_estimate("model-nobody-priced", 1000, 500)
    assert cost is None and version is None


def test_versions_travel_with_the_request():
    request = build_request(ROOT_CAUSE_GROUPING, _payload())
    assert request.task_version == ROOT_CAUSE_GROUPING.version
    assert request.prompt_version == ROOT_CAUSE_GROUPING.prompt_version
    assert request.schema_version == ROOT_CAUSE_GROUPING.schema_version
    assert request.task_type is TaskType.ROOT_CAUSE_GROUPING


def test_input_hash_is_deterministic_and_order_independent():
    """Той самий вхід — той самий хеш, незалежно від порядку ключів."""
    a = input_hash({"findings": FINDINGS, "site": "x"})
    b = input_hash({"site": "x", "findings": FINDINGS})
    assert a == b
    assert a != input_hash({"findings": FINDINGS[:1], "site": "x"})


def test_locale_is_part_of_the_identity():
    """Інша мова — інший артефакт, а не привід перезаписати наявний."""
    en = build_request(ROOT_CAUSE_GROUPING, _payload(), locale="en")
    de = build_request(ROOT_CAUSE_GROUPING, _payload(), locale="de")
    assert en.input_hash != de.input_hash
    assert en.locale == "en" and de.locale == "de"


# ── межа правди ───────────────────────────────────────────────────────────


def test_unknown_finding_reference_is_rejected():
    """Вигадана знахідка — провал валідації, а не «додаткова знахідка»."""
    bad = {
        "groups": [
            {
                "id": "g1",
                "title": "Вигадане",
                "hypothesis": "Ймовірно…",
                "finding_refs": ["seo.canonical:missing", "seo.i_made_this_up"],
                "confidence": "likely",
            }
        ],
        "ungrouped_refs": [],
    }
    with pytest.raises(TaskValidationError, match="неіснуючі"):
        ROOT_CAUSE_GROUPING.validate(bad, _payload())


def test_grouping_cannot_smuggle_a_new_problem_through_ungrouped():
    bad = {"groups": [], "ungrouped_refs": ["seo.canonical:missing", "invented.problem"]}
    with pytest.raises(TaskValidationError, match="поза входом"):
        ROOT_CAUSE_GROUPING.validate(bad, _payload())


def test_remediation_drops_steps_that_reference_nothing_known():
    """«Ще виправте X», якого немає в аудиті, до плану не потрапляє."""
    payload = {
        "findings": [{"ref": f["ref"], "severity": f["severity"], "title": f["title"], "rank": i}
                     for i, f in enumerate(FINDINGS, start=1)],
        "groups": [],
        "site": "",
    }
    output = {
        "steps": [
            {
                "order": 1,
                "title": "Полагодити canonical",
                "why_now": "Спільна причина",
                "finding_refs": ["seo.canonical:missing"],
                "group_ids": [],
                "depends_on": [],
            },
            {
                "order": 2,
                "title": "Ще перепишіть усі тексти",
                "why_now": "Бо гарно",
                "finding_refs": ["nothing.we.found"],
                "group_ids": ["no-such-group"],
                "depends_on": [],
            },
        ]
    }
    clean = REMEDIATION_PLAN.validate(output, payload)

    assert len(clean["steps"]) == 1
    assert clean["dropped_ungrounded_steps"] == 1
    assert clean["steps"][0]["finding_refs"] == ["seo.canonical:missing"]


def test_remediation_with_no_grounded_step_at_all_is_a_failure():
    payload = {"findings": [{"ref": "a", "severity": "high", "title": "t", "rank": 1}],
               "groups": [], "site": ""}
    output = {"steps": [{"order": 1, "title": "x", "why_now": "y",
                         "finding_refs": ["unknown"], "group_ids": [], "depends_on": []}]}
    with pytest.raises(TaskValidationError):
        REMEDIATION_PLAN.validate(output, payload)


def test_site_understanding_cannot_cite_a_page_we_never_read():
    payload = {
        "origin": "https://example.com",
        "pages": [{"url": "https://example.com/", "title": "Home", "text": "текст"}],
    }
    output = {
        "site_kind": "shop",
        "name": "Acme",
        "tagline": "t",
        "description": "d",
        "offerings": [],
        "audience": "a",
        "page_roles": [{"url": "https://example.com/secret", "role": "invented"}],
        "source_urls": ["https://example.com/"],
    }
    with pytest.raises(TaskValidationError, match="невідому адресу"):
        SITE_UNDERSTANDING.validate(output, payload)


@pytest.mark.asyncio
async def test_invalid_output_never_reaches_the_result():
    """Невалідна відповідь — збій задачі, і результату немає взагалі."""
    outcome, _ = await _run(
        ROOT_CAUSE_GROUPING,
        _payload(),
        lambda c: {"groups": [{"id": "g", "title": "t", "hypothesis": "h",
                               "finding_refs": ["ghost"], "confidence": "likely"}],
                   "ungrouped_refs": []},
        max_attempts=1,
    )
    assert outcome.status is EnrichmentStatus.FAILED
    assert outcome.result is None
    assert outcome.attempts[0].outcome is AttemptOutcome.INVALID_OUTPUT
    assert outcome.attempts[0].error_category == "task_validation"


@pytest.mark.asyncio
async def test_enrichment_result_carries_no_score_or_severity_fields():
    """Схема виходу фізично не має чим змінити бал чи серйозність.

    Не «модель не повинна» — у контракті просто немає таких полів, а
    `additionalProperties: false` не дає їх додати.
    """
    for spec in TASKS.values():
        properties = set(spec.schema["properties"])
        assert spec.schema["additionalProperties"] is False
        assert not properties & {"score", "severity", "overall", "weight", "confidence_band"}


def test_grouping_separates_observed_cluster_from_inferred_cause():
    """Контракт v2: кластер і причина — різні поля, і причини може не бути.

    У v1 поле `hypothesis` було обовʼязковим, тож модель мусила вигадати
    причину, щоб заповнити схему. На пілоті так і сталося: 30 із 34 груп
    отримали припущення там, де доказів на причину не було.
    """
    props = ROOT_CAUSE_GROUPING.schema["properties"]["groups"]["items"]["properties"]
    assert "cluster_summary" in props, "спостережений кластер мусить мати власне поле"
    assert props["cause_confidence"]["enum"] == ["supported", "likely", "possible", "unknown"]
    # Доказ кластера й доказ причини — різні переліки.
    assert "cluster_evidence" in props and "cause_evidence" in props

    system = ROOT_CAUSE_GROUPING.system.lower()
    assert "co-occurrence is not causality" in system
    assert "same detector" in system and "lighthouse" in system
    assert "unknown" in system


def test_remediation_prompt_forbids_unmeasured_promises():
    system = REMEDIATION_PLAN.system.lower()
    for promise in ("hours", "money", "traffic", "ranking"):
        assert promise in system, f"промпт не забороняє обіцяти {promise}"


# ── шлюз ──────────────────────────────────────────────────────────────────


def test_enrichment_is_disabled_by_default():
    """Дефолт класу, а не поточне значення з .env розробника."""
    from app.core.config import Settings

    assert Settings.model_fields["enrich_enabled"].default is False


def test_legacy_semantic_layer_stays_disabled():
    """Шар, що впливає на бал, лишається вимкненим і цією задачею не вмикається."""
    from app.core.config import Settings

    assert Settings.model_fields["llm_enabled"].default is False


def test_default_routes_cover_every_task():
    for task in TaskType:
        assert route_for(task), f"{task.value} без маршруту"
