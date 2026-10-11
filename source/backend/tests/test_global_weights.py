"""Глобальні ваги модулів: затверджена політика (сценарій F, 2026-08-31).

Ваги виведені з обсягу й повторюваності доказу на 969 знімках night3:
SEO — найглибша сімʼя на найширшому доказі; performance — одна сторінка
Lighthouse із міжпрогінним шумом; tech — найповторюваніший доказ;
ai_ready/llm_visibility — сигнали готовності, не AI-присутності;
accessibility — свідомо 0.10 (грубість детектора не плутаємо з
нормативною важливістю). Поріг покриття 0.50 перевиведено: він мусить
перевищувати суму неконтентних ваг 0.44 (жодного бала без прочитаного
вмісту) і не перевищувати 0.60 (perf+seo+tech — легітимна підмножина).
"""

from __future__ import annotations

from fractions import Fraction

from app.audit.enums import Module, Severity
from app.audit.scoring import (
    MIN_COVERED_WEIGHT,
    MODULE_WEIGHT,
    active_weights,
    compute_scores,
)
from app.audit.types import Issue

APPROVED = {
    Module.SEO: Fraction(26, 100),
    Module.PERFORMANCE: Fraction(18, 100),
    Module.AI_READY: Fraction(16, 100),
    Module.LLM_VISIBILITY: Fraction(14, 100),
    Module.TECH: Fraction(16, 100),
    Module.ACCESSIBILITY: Fraction(10, 100),
}
CONTENT = {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY}


def _issue(module: Module, sev: Severity = Severity.MEDIUM, key: str = "") -> Issue:
    return Issue(code=f"{module.value}.x", module=module, severity=sev,
                 title="", evidence={}, weight=2, page_url=None,
                 msg=f"{module.value}.x", params={}, key=key)


# ── A: константи ──────────────────────────────────────────────────────


def test_the_approved_weight_table_is_exact() -> None:
    for module, expected in APPROVED.items():
        assert Fraction(MODULE_WEIGHT[module]).limit_denominator(1000) == expected, module


def test_weights_sum_exactly_to_one() -> None:
    assert sum(Fraction(w).limit_denominator(1000)
               for w in MODULE_WEIGHT.values()) == 1


def test_min_covered_weight_is_half() -> None:
    assert MIN_COVERED_WEIGHT == 0.5


def test_no_module_family_gate_exists() -> None:
    """Гейта сімейств немає навмисно: числовий поріг сам гарантує, що
    бала без контентного модуля не буде — сума неконтентних ваг 0.44."""
    non_content = sum(Fraction(MODULE_WEIGHT[m]).limit_denominator(1000)
                      for m in Module if m not in CONTENT)
    assert non_content == Fraction(44, 100)
    assert float(non_content) < MIN_COVERED_WEIGHT


# ── C: інваріанти доступності бала ────────────────────────────────────


def test_all_six_modules_yield_an_overall() -> None:
    overall, scores = compute_scores([], skipped_modules=set())
    assert overall == 100 and len(scores) == 6


def test_losing_accessibility_alone_keeps_the_overall() -> None:
    overall, _ = compute_scores([], skipped_modules={Module.ACCESSIBILITY})
    assert overall is not None  # покрито 0.90


def test_losing_performance_alone_keeps_the_overall() -> None:
    overall, _ = compute_scores([], skipped_modules={Module.PERFORMANCE})
    assert overall is not None  # покрито 0.82


def test_losing_performance_and_accessibility_keeps_the_overall() -> None:
    overall, _ = compute_scores(
        [], skipped_modules={Module.PERFORMANCE, Module.ACCESSIBILITY})
    assert overall is not None  # покрито 0.72 >= 0.50


def test_perf_tech_a11y_alone_cannot_produce_an_overall() -> None:
    """Жорстка умова приймання: сліпий/withheld аудит (контентні модулі
    вимкнено) не сміє отримати загальний бал із трьох неконтентних —
    рівно те, що дозволили б рівні ваги на 91 сайті night3."""
    overall, scores = compute_scores([], skipped_modules=CONTENT)
    assert overall is None
    assert set(scores) == {m.value for m in Module if m not in CONTENT}


def test_a_single_module_cannot_produce_an_overall() -> None:
    for survivor in Module:
        skipped = {m for m in Module if m is not survivor}
        overall, _ = compute_scores([], skipped_modules=skipped)
        assert overall is None, survivor


# ── D: інваріанти підрахунку ──────────────────────────────────────────


def test_active_weights_renormalize_to_one() -> None:
    for skipped in (set(), {Module.ACCESSIBILITY},
                    {Module.PERFORMANCE, Module.ACCESSIBILITY}):
        weights = active_weights(skipped)
        assert abs(sum(weights.values()) - 1.0) < 1e-12
        base = sum(MODULE_WEIGHT[m] for m in weights)
        for m, w in weights.items():
            assert abs(w - MODULE_WEIGHT[m] / base) < 1e-12


def test_removing_a_penalty_never_lowers_module_or_overall() -> None:
    worse = [_issue(Module.SEO), _issue(Module.SEO, Severity.HIGH, key="b")]
    better = worse[:1]
    ov_w, sc_w = compute_scores(worse, skipped_modules=set())
    ov_b, sc_b = compute_scores(better, skipped_modules=set())
    assert sc_b["seo"] >= sc_w["seo"]
    assert ov_b >= ov_w


def test_improving_one_module_never_lowers_the_overall() -> None:
    """Додатні ваги над монотонними модулями: монотонність структурна."""
    fixed = [_issue(Module.TECH), _issue(Module.PERFORMANCE)]
    ov_low, _ = compute_scores([*fixed, _issue(Module.SEO, Severity.CRITICAL)],
                               skipped_modules=set())
    ov_high, _ = compute_scores([*fixed, _issue(Module.SEO, Severity.LOW)],
                                skipped_modules=set())
    assert ov_high >= ov_low


def test_unavailable_evidence_creates_no_bonus() -> None:
    """Вимкнений модуль лише перерозподіляє ваги — чистий контекст дає
    100 і з ним, і без нього; бонусних шляхів не існує."""
    with_all, _ = compute_scores([], skipped_modules=set())
    without, _ = compute_scores([], skipped_modules={Module.ACCESSIBILITY})
    assert with_all == without == 100


def test_rounding_is_deterministic() -> None:
    issues = [_issue(Module.SEO), _issue(Module.TECH, Severity.HIGH)]
    first = compute_scores(issues, skipped_modules=set())
    assert all(compute_scores(issues, skipped_modules=set()) == first
               for _ in range(5))


# ── B: відбитки ───────────────────────────────────────────────────────


def test_the_rules_generation_marks_the_release_that_priced_a_check() -> None:
    """Зміну констант відбиток бачить сам; покоління — для того, чого він
    не бачить.

    4 вересня 2026 жодна константа формули не змінилась, але
    `tech.form_protection:get_method` уперше після заморозки отримав
    ціну. Бали по різні боки цієї межі непорівнянні, і читач історії
    має бачити це в тому ж полі, у якому дивиться на зміни підрахунку.

    13 вересня 2026 (G6: E-07) те саме сталося з протилежного боку:
    `ai.schema.faq` ціну ВТРАТИВ, бо його вилучено зі скорингу. Знову
    жодна константа не змінилась, і знову покоління — єдине місце, де
    читач це побачить.
    """
    from app.audit.versions import SCORING_RULES, scoring_version

    assert scoring_version() != "0cfbc304bc32", "стара заморозка знята явно"
    assert scoring_version() != "7b16db310137", "межа 4 вересня видима у відбитку"
    assert scoring_version() != "c6a1c3fd43d8", "межа 13 вересня видима у відбитку"
    assert SCORING_RULES == "5"
