"""Регресії з живого пілота на пʼяти сайтах (Opus 5, 2026-08-24).

Кожен тест тут описує те, що справді сталося, а не гіпотетичну загрозу.
Пілот коштував $0.93 і дав пʼять конкретних дефектів; ці тести — плата
за те, щоб не купувати ті самі уроки вдруге.

Жодного мережевого виклику: усе на збережених артефактах і фікстурах.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.enrich.benchmark import unsupported_claims
from app.enrich.contracts import TaskValidationError
from app.enrich.tasks.remediation import REMEDIATION_PLAN
from app.enrich.tasks.root_cause import ROOT_CAUSE_GROUPING

PILOT = Path(__file__).resolve().parents[1] / "benchmark" / "pilot"


def _findings(*refs: str, module: str = "a11y") -> dict:
    return {
        "findings": [
            {
                "ref": r,
                "module": module,
                "severity": "medium",
                "title": r,
                "pages": 1,
                "scope": "page",
                "examples": [],
                "evidence": "",
            }
            for r in refs
        ],
        "site": "",
        "coverage": {"level": "full", "pages_read": 10, "pages_known": 10, "pages_unread": 0},
    }


# ── A. Кластер доступності без доведеної причини ──────────────────────────


def test_accessibility_cluster_may_honestly_have_no_cause():
    """Пілот: три групи a11y на трьох сайтах трималися лише на тому, що
    знахідки прийшли з одного запуску Lighthouse. Кластер справжній,
    причина була вигадана під обовʼязкове поле.

    Тепер `unknown` без гіпотези — валідний вихід."""
    payload = _findings("a11y.blocking", "a11y.failures")
    output = {
        "groups": [
            {
                "id": "a11y",
                "cluster_summary": "Both accessibility findings were reported by the same audit.",
                "finding_refs": ["a11y.blocking", "a11y.failures"],
                "cluster_evidence": ["a11y.blocking"],
                "cause_confidence": "unknown",
                "cause_hypothesis": "",
                "cause_evidence": [],
            }
        ],
        "ungrouped_refs": [],
    }

    clean = ROOT_CAUSE_GROUPING.validate(output, payload)

    assert clean["groups"][0]["cause_confidence"] == "unknown"
    # Відсутня причина зберігається як null, а не порожній рядок.
    assert clean["groups"][0]["cause_hypothesis"] is None


def test_cause_hypothesis_smuggled_into_unknown_is_rejected():
    """«unknown» плюс пояснення — саме та вигадка, від якої v2 захищає."""
    payload = _findings("a11y.blocking", "a11y.failures")
    output = {
        "groups": [
            {
                "id": "a11y",
                "cluster_summary": "Same audit run.",
                "finding_refs": ["a11y.blocking", "a11y.failures"],
                "cluster_evidence": [],
                "cause_confidence": "unknown",
                "cause_hypothesis": "These are caused by shared design-system components.",
                "cause_evidence": [],
            }
        ],
        "ungrouped_refs": [],
    }
    with pytest.raises(TaskValidationError, match="гіпотезу"):
        ROOT_CAUSE_GROUPING.validate(output, payload)


def test_supported_cause_requires_evidence_of_the_cause_itself():
    """`supported` без доказу самої причини — заявка без підстави."""
    payload = _findings("tech.nap:schema_mismatch", "tech.nap:phone_not_e164", module="tech")
    base = {
        "id": "nap",
        "cluster_summary": "Both findings describe the same phone value.",
        "finding_refs": ["tech.nap:schema_mismatch", "tech.nap:phone_not_e164"],
        "cluster_evidence": ["tech.nap:schema_mismatch"],
        "cause_confidence": "supported",
        "cause_hypothesis": "One badly formatted source phone value feeds both.",
    }

    with pytest.raises(TaskValidationError, match="supported"):
        ROOT_CAUSE_GROUPING.validate(
            {"groups": [{**base, "cause_evidence": []}], "ungrouped_refs": []}, payload
        )

    ok = ROOT_CAUSE_GROUPING.validate(
        {
            "groups": [{**base, "cause_evidence": ["tech.nap:schema_mismatch"]}],
            "ungrouped_refs": [],
        },
        payload,
    )
    assert ok["groups"][0]["cause_confidence"] == "supported"


# ── B. Кластер продуктивності: third-party не стає причиною сам собою ─────


def test_performance_cluster_may_group_without_promoting_third_party_to_cause():
    """Пілот, web.dev `perf-mobile`: TTFB/LCP/INP/third-party згруповано
    слушно, але «чужі скрипти — причина» ніхто не міряв.

    Кластер валідний; causal_confidence нижче за `supported` — теж."""
    payload = _findings(
        "perf.core_web_vitals:ttfb",
        "perf.core_web_vitals:lcp",
        "perf.core_web_vitals:inp",
        "perf.third_party",
        module="performance",
    )
    for level in ("likely", "possible"):
        clean = ROOT_CAUSE_GROUPING.validate(
            {
                "groups": [
                    {
                        "id": "perf-mobile",
                        "cluster_summary": "All four were measured on the same mobile render.",
                        "finding_refs": [f["ref"] for f in payload["findings"]],
                        "cluster_evidence": ["perf.core_web_vitals:lcp"],
                        "cause_confidence": level,
                        "cause_hypothesis": "Third-party weight may contribute to the vitals.",
                        "cause_evidence": ["perf.third_party"],
                    }
                ],
                "ungrouped_refs": [],
            },
            payload,
        )
        assert clean["groups"][0]["cause_confidence"] == level


def test_evidence_must_come_from_inside_the_group():
    """Доказ причини не можна позичити в знахідки, якої в групі немає."""
    payload = _findings("perf.core_web_vitals:lcp", "perf.third_party", module="performance")
    output = {
        "groups": [
            {
                "id": "perf",
                "cluster_summary": "Same render.",
                "finding_refs": ["perf.core_web_vitals:lcp"],
                "cluster_evidence": [],
                "cause_confidence": "likely",
                "cause_hypothesis": "Third-party weight likely contributes.",
                "cause_evidence": ["perf.third_party"],
            }
        ],
        "ungrouped_refs": ["perf.third_party"],
    }
    with_pytest = pytest.raises(TaskValidationError, match="поза власні знахідки")
    with with_pytest:
        ROOT_CAUSE_GROUPING.validate(output, payload)


# ── C. Частковий краул доходить до задач ──────────────────────────────────


def test_partial_coverage_reaches_every_task_input():
    """Пілот, gocplumbing.com: 3 сторінки з 10, і модель не знала цього.

    Тепер факти покриття входять у канонічний вхід усіх трьох задач і
    видно в промпті, який справді надсилається."""
    from app.enrich.contracts import TaskType
    from app.enrich.tasks import TASKS

    coverage = {
        "level": "partial",
        "pages_read": 3,
        "pages_known": 10,
        "pages_unread": 7,
        "pages_failed": 7,
        "share": 0.3,
    }
    payloads = {
        TaskType.SITE_UNDERSTANDING: {
            "origin": "https://example.com",
            "coverage": coverage,
            "pages": [{"url": "https://example.com/", "title": "T", "text": "текст"}],
        },
        TaskType.ROOT_CAUSE_GROUPING: {**_findings("seo.h1:missing"), "coverage": coverage},
        TaskType.REMEDIATION_PLAN: {
            "findings": [
                {"ref": "seo.h1:missing", "severity": "high", "title": "t", "rank": 1}
            ],
            "groups": [],
            "site": "",
            "coverage": coverage,
        },
    }
    for task, payload in payloads.items():
        prompt = TASKS[task].render_prompt(payload)
        assert "partial" in prompt, f"{task.value}: рівень покриття не дійшов до промпта"
        assert "3 pages read of 10" in prompt, f"{task.value}: числа покриття не дійшли"


def test_coverage_comes_from_the_audit_engine_not_from_the_ai_layer():
    """Другої системи покриття не заводиться — береться канонічна.

    Провайдерські адаптери фактів покриття не бачать і не вигадують.
    """
    import inspect

    from app.enrich.providers import anthropic as adapter
    from app.report import coverage as canonical

    assert hasattr(canonical, "coverage_facts")
    source = inspect.getsource(adapter)
    for word in ("coverage", "pages_read", "pages_known"):
        assert word not in source, f"адаптер провайдера знає про покриття: {word}"


# ── D. План не може бути впевненішим за своє джерело ──────────────────────


def test_remediation_cannot_promote_a_possible_cause_to_certainty():
    """Пілот, web.dev крок 4: група казала «likely», план — «ARE THE
    UPSTREAM CAUSES». Тепер стеля структурна, а не риторична."""
    payload = {
        "findings": [
            {"ref": "perf.core_web_vitals:lcp", "severity": "high", "title": "LCP", "rank": 1}
        ],
        "groups": [
            {
                "id": "perf-mobile",
                "cluster_summary": "Measured on the same render.",
                "cause_confidence": "possible",
                "finding_refs": ["perf.core_web_vitals:lcp"],
            }
        ],
        "site": "",
        "coverage": {"level": "full"},
    }
    output = {
        "steps": [
            {
                "order": 1,
                "title": "Reduce third-party weight",
                "why_now": "…",
                "finding_refs": ["perf.core_web_vitals:lcp"],
                "group_ids": ["perf-mobile"],
                "causal_basis": "supported",
                "depends_on": [],
            }
        ]
    }

    clean = REMEDIATION_PLAN.validate(output, payload)

    assert clean["steps"][0]["causal_basis"] == "possible", "заявку не знижено до джерела"
    assert clean["lowered_causal_basis"] == 1, "зниження не зафіксовано в результаті"


def test_unknown_cause_forbids_any_causal_basis_in_the_plan():
    """`unknown` у групі означає, що крок не стверджує причину взагалі."""
    payload = {
        "findings": [{"ref": "a11y.blocking", "severity": "high", "title": "a", "rank": 1}],
        "groups": [
            {
                "id": "a11y",
                "cluster_summary": "Same audit run.",
                "cause_confidence": "unknown",
                "finding_refs": ["a11y.blocking"],
            }
        ],
        "site": "",
        "coverage": {"level": "full"},
    }
    output = {
        "steps": [
            {
                "order": 1,
                "title": "Fix barriers",
                "why_now": "…",
                "finding_refs": ["a11y.blocking"],
                "group_ids": ["a11y"],
                "causal_basis": "likely",
                "depends_on": [],
            }
        ]
    }

    clean = REMEDIATION_PLAN.validate(output, payload)
    assert clean["steps"][0]["causal_basis"] == "none"


def test_step_without_any_group_cannot_claim_a_cause():
    """Крок, що спирається лише на знахідки, причини не має звідки взяти."""
    payload = {
        "findings": [{"ref": "seo.noindex", "severity": "high", "title": "n", "rank": 1}],
        "groups": [],
        "site": "",
        "coverage": {"level": "full"},
    }
    output = {
        "steps": [
            {
                "order": 1,
                "title": "Restore indexability",
                "why_now": "…",
                "finding_refs": ["seo.noindex"],
                "group_ids": [],
                "causal_basis": "likely",
                "depends_on": [],
            }
        ]
    }
    clean = REMEDIATION_PLAN.validate(output, payload)
    assert clean["steps"][0]["causal_basis"] == "none"


def test_a_supported_cause_may_be_stated_directly():
    """Стеля не карає обґрунтоване: `supported` доходить до плану цілим."""
    payload = {
        "findings": [
            {"ref": "tech.nap:phone_not_e164", "severity": "medium", "title": "p", "rank": 1}
        ],
        "groups": [
            {
                "id": "nap",
                "cluster_summary": "Same phone value.",
                "cause_confidence": "supported",
                "finding_refs": ["tech.nap:phone_not_e164"],
            }
        ],
        "site": "",
        "coverage": {"level": "full"},
    }
    output = {
        "steps": [
            {
                "order": 1,
                "title": "Unify the phone value",
                "why_now": "…",
                "finding_refs": ["tech.nap:phone_not_e164"],
                "group_ids": ["nap"],
                "causal_basis": "supported",
                "depends_on": [],
            }
        ]
    }
    clean = REMEDIATION_PLAN.validate(output, payload)
    assert clean["steps"][0]["causal_basis"] == "supported"
    assert clean["lowered_causal_basis"] == 0


# ── E. Ціни клієнта — не вигаданий кошторис ───────────────────────────────


def test_quoted_customer_pricing_is_not_an_unsupported_claim():
    """Пілот, linear.app: `$0` і `$1` із власної сторінки тарифів були
    позначені як безпідставні твердження. Це була помилка детектора."""
    source = 'Plans: Free $0, Basic $10/user/mo, Business $16/user/mo'
    output = 'Plans: Free $0, Basic $10/user/mo, Business $16/user/mo'

    assert unsupported_claims(output, source) == []


def test_invented_savings_are_still_flagged():
    """Правило проти вигаданих сум не послаблене."""
    source = "Plans: Free $0, Basic $10/user/mo"
    invented = "Fixing this will save about $5,000 per year and take 12 hours."

    flagged = unsupported_claims(invented, source)

    assert any("5,000" in f or "5" in f for f in flagged), "вигадана економія не спіймана"
    assert any("hours" in f for f in flagged), "вигадані години не спіймані"


def test_money_without_any_source_is_flagged():
    """Без поданого джерела будь-яка сума лишається підозрілою."""
    assert unsupported_claims("costs about $250", "") != []


# ── незмінність історичних артефактів пілота ─────────────────────────────


def test_pilot_artifacts_keep_their_historical_labels():
    """Історію не переписуємо: артефакти лишаються доказом того, що було.

    Мітка `schema_version: 2` на `remediation_plan` — слід тимчасового
    стану, і вона мусить пережити перехід на справжню v2, інакше запис
    експерименту перестане відповідати тому, що справді виконувалось.
    """
    if not PILOT.exists():
        pytest.skip("артефактів пілота немає в цій копії репозиторію")
    files = sorted(PILOT.glob("*.json"))
    assert len(files) == 5, "пілот мав пʼять сайтів"
    for path in files:
        record = json.loads(path.read_text(encoding="utf-8"))
        assert record["deterministic_unchanged"] is True
        tasks = {t["task"]: t for t in record["tasks"]}
        assert tasks["remediation_plan"]["schema_version"] == "2"
        assert tasks["root_cause_grouping"]["schema_version"] == "1"
        # Стара форма групи — доказ того, що контракт справді був інший.
        result = tasks["root_cause_grouping"]["result"]
        assert "hypothesis" in result["groups"][0]
        assert "cluster_summary" not in result["groups"][0]
