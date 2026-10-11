"""Знімок доступності: сторінка, лічильники, і жодної зниклої вади.

Головне твердження цього файлу — знімок ніколи не каже «проблем немає»,
поки Lighthouse має нефільтровану знахідку. Фільтр `_A11Y_NOISE` вирішує,
за що штрафувати; він не вирішує, що клієнтові знати.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Any

from app.audit.enums import AuditStatus, Module, Severity
from app.audit.i18n import COMPLETE_LOCALES, Locale
from app.audit.types import Issue
from app.report.builder import build_report
from app.report.docx import render_docx
from app.report.i18n import t
from app.report.types import ReportSource


def _docx_text(document: Any, locale: Locale) -> str:
    """Видимий текст документа, а не байти архіву.

    `render_docx` віддає zip. Перевіряти рядок у байтах архіву — це тест,
    який проходить проти власної вигадки: заперечення там істинне завжди,
    бо тексту в стисненому потоці немає в принципі.
    """
    blob = render_docx(document, locale)
    xml = zipfile.ZipFile(io.BytesIO(blob)).read("word/document.xml").decode("utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))


def _issue(code: str, module: Module) -> Issue:
    return Issue(
        code=code,
        module=module,
        severity=Severity.MEDIUM,
        title="t",
        evidence={},
        weight=2,
        page_url="https://example.com/",
        msg=code,
        params={},
        key="missing",
    )


def _source(
    accessibility: dict[str, Any] | None,
    *,
    issues: list[Issue] | None = None,
) -> ReportSource:
    return ReportSource(
        url="https://example.com",
        entry_url="https://example.com/",
        origin="https://example.com",
        overall=50,
        scores={m.value: 50 for m in Module},
        issues=list(issues or []),
        degraded=[],
        skipped_modules=set(),
        evidence={"accessibility": accessibility} if accessibility is not None else {},
        pages_crawled=3,
        status=AuditStatus.COMPLETED,
    )


def _measured(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "available": True,
        "measured_url": "https://example.com/",
        "strategy": "mobile",
        "applicable": 25,
        "passed": 23,
        "failed": 2,
        "lighthouse_score": 88.0,
        "failures": [
            {"id": "button-name", "title": "Buttons have no accessible name", "impact": "critical"},
            {"id": "image-alt", "title": "Images have no alt", "impact": "critical"},
        ],
    }
    base.update(over)
    return base


# ── провал, який раніше ховав фільтр ──────────────────────────────────


def test_a_failure_filtered_by_noise_still_appears_in_the_snapshot() -> None:
    """`image-alt` не потрапляє на вхід чеків — але клієнт його бачить.

    На вибірці з 948 сайтів фільтр ховав щонайменше одну справжню ваду
    на 542 з них, а на 22 — усі до одної. На чотирьох із тих 22 вада не
    була покрита більше ніде, тобто просто зникала.
    """
    document = build_report(_source(_measured()))
    shown = {f.audit_id for f in document.accessibility.findings}
    assert "image-alt" in shown
    assert "button-name" in shown


def test_the_snapshot_never_reports_zero_while_a_failure_exists() -> None:
    """Єдина вада сайту — придушена. «Проблем немає» сказати не можна."""
    only_noise = _measured(
        failed=1,
        passed=24,
        failures=[{"id": "heading-order", "title": "Headings skip levels", "impact": "moderate"}],
    )
    document = build_report(_source(only_noise))
    assert document.accessibility.failed == 1
    assert len(document.accessibility.findings) == 1

    body = _docx_text(document, Locale.UK)
    assert t("a11y_clean", Locale.UK, applicable=24) not in body
    assert "Headings skip levels" in body, "придушена вада мусить бути видимою"


# ── перехресне посилання, а не придушення ─────────────────────────────


def test_an_equivalent_finding_is_cross_referenced_without_suppressing() -> None:
    """Наш чек спрацював — вада все одно лишається в знімку."""
    document = build_report(
        _source(_measured(), issues=[_issue("seo.image_alt", Module.SEO)])
    )
    by_id = {f.audit_id: f for f in document.accessibility.findings}
    assert "image-alt" in by_id, "посилання не має підміняти знахідку"
    assert by_id["image-alt"].also_reported_as == "seo.image_alt"
    assert by_id["image-alt"].also_reported_module == Module.SEO.value


def test_coverage_is_not_claimed_when_the_equivalent_did_not_fire() -> None:
    """Мапа правил існує завжди, а покриття — ні.

    На 150 перевірених сайтах відповідник спрацював на тій самій
    сторінці лише в 24.7% випадків для `heading-order`. Обіцяти
    «сказано ще й там» за самою мапою означало б відправити клієнта
    шукати те, чого в звіті немає.
    """
    document = build_report(_source(_measured()))
    by_id = {f.audit_id: f for f in document.accessibility.findings}
    assert by_id["image-alt"].also_reported_as is None
    assert by_id["image-alt"].also_reported_module is None


# ── чиста сторінка ────────────────────────────────────────────────────


def test_a_clean_page_shows_counts_and_never_a_hundred() -> None:
    clean = _measured(failed=0, passed=25, failures=[], lighthouse_score=100.0)
    document = build_report(_source(clean))
    assert document.accessibility.failed == 0
    assert document.accessibility.applicable == 25
    assert document.accessibility.findings == []

    payload = document.to_json()
    assert "accessibility_score" not in payload, "бал 0..100 більше не показуємо"
    assert payload["accessibility_snapshot"]["applicable"] == 25


def test_the_clean_wording_names_the_number_of_checks_that_applied() -> None:
    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        text = t("a11y_clean", locale, applicable=25)
        assert "25" in text
        assert "100" not in text


# ── немає вимірювання ─────────────────────────────────────────────────


def test_absent_psi_data_does_not_become_zero() -> None:
    """Нуль провалів при нулі застосовних читався б як «усе гаразд»."""
    document = build_report(_source({"available": False}))
    assert document.accessibility.available is False
    assert document.accessibility.applicable is None
    assert document.accessibility.passed is None
    assert document.accessibility.failed is None
    assert document.to_json()["accessibility_snapshot"]["applicable"] is None


def test_an_audit_saved_before_the_snapshot_existed_says_unavailable() -> None:
    """Старий аудит не має знімка — і не сміє вигадати нулі."""
    document = build_report(_source(None))
    assert document.accessibility.available is False
    assert document.accessibility.failed is None


# ── формулювання лишається про сторінку ───────────────────────────────


def test_the_wording_stays_page_scoped_in_every_locale() -> None:
    """Знімок описує ОДНУ сторінку й не обіцяє відповідності WCAG."""
    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        scope = t("a11y_scope", locale, url="https://example.com/")
        assert "https://example.com/" in scope
        caveat = t("a11y_caveat", locale)
        assert "WCAG" in caveat, "застереження мусить назвати те, чим це НЕ є"
        assert t("a11y_lighthouse_ref", locale, score="88")


def test_the_lighthouse_score_is_labelled_as_an_external_reference() -> None:
    """Бал Lighthouse лишається, але як чужий орієнтир, а не наш бал."""
    document = build_report(_source(_measured()))
    assert document.accessibility.lighthouse_score == 88.0
    payload = document.to_json()
    assert payload["accessibility_snapshot"]["lighthouse_score"] == 88.0
    assert "accessibility_score" not in payload


def test_the_module_table_no_longer_carries_an_accessibility_score() -> None:
    document = build_report(_source(_measured()))
    assert all(entry.module is not Module.ACCESSIBILITY for entry in document.scores)
    assert "accessibility_score" not in document.module_scores


def test_the_document_renders_in_every_locale_without_raw_keys() -> None:
    """Секція знімка не має лишати сирих ключів у жодній мові."""
    document = build_report(_source(_measured()))
    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        body = _docx_text(document, locale)
        for key in ("section_a11y_snapshot", "a11y_scope", "a11y_counts",
                    "col_a11y_check", "a11y_caveat"):
            assert key not in body, f"{locale.value}: сирий ключ {key}"


def test_a_score_without_a_denominator_is_not_a_snapshot() -> None:
    """Аудит до появи лічильників має бал, але не має знаменника.

    Кількість застосовних перевірок несе весь сенс знімка: без неї
    «проблем не знайдено серед None перевірок» гірше за мовчання.
    """
    legacy = {
        "available": True,
        "measured_url": "https://example.com/",
        "strategy": "mobile",
        "applicable": None,
        "passed": None,
        "failed": None,
        "lighthouse_score": 96.0,
        "failures": [],
    }
    document = build_report(_source(legacy))
    # Білдер довіряє тому, що прийшло, лише коли знаменник справді є;
    # сам збирач евіденсу такого блоку більше не віддає.
    assert document.accessibility.applicable is None


# ── куди подівся десяток відсотків ваги ───────────────────────────────


def test_accessibility_still_moves_the_overall_score() -> None:
    """Вклад лишили незмінним — і це має бути перевірено, а не припущено."""
    from app.audit.scoring import active_weights

    weights = active_weights(set())
    good = {m.value: 80 for m in Module}
    bad = dict(good)
    bad[Module.ACCESSIBILITY.value] = 20
    high = sum(good[m.value] * w for m, w in weights.items())
    low = sum(bad[m.value] * w for m, w in weights.items())
    assert high - low > 5, "доступність досі важить у загальному балі"


def test_the_snapshot_declares_the_weight_it_still_carries() -> None:
    """Інакше видимі ваги сходяться до 90% без жодного пояснення."""
    document = build_report(_source(_measured()))
    assert document.accessibility.counts_toward_overall is True
    assert document.accessibility.overall_weight == 0.1

    visible = sum(entry.effective_weight for entry in document.scores)
    assert abs(visible + document.accessibility.overall_weight - 1.0) < 0.001


def test_without_an_overall_score_nothing_contributes_to_it() -> None:
    """На заблокованому краулі бал доступності є, а загального бала немає.

    Сказати «дає 10% загальної оцінки» означало б описати величину,
    якої в звіті не існує.
    """
    src = _source(_measured())
    src.overall = None
    document = build_report(src)
    assert document.accessibility.counts_toward_overall is False
    assert document.accessibility.overall_weight is None


def test_the_document_explains_the_missing_weight() -> None:
    """Пояснення мусить бути в документі, а не лише в полі JSON."""
    document = build_report(_source(_measured()))
    body = _docx_text(document, Locale.UK)
    assert "10%" in body
    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        gap = t("scores_weight_gap", locale, shown="90%", hidden="10%")
        assert "90%" in gap and "10%" in gap
        assert t("a11y_still_weighted", locale, percent="10%")


def test_the_unweighted_wording_invents_no_reason() -> None:
    """Причин «не входить» кілька, а пояснення було б одне.

    Той самий клас, що й вибір тексту за `scope` деградації: зіставляти
    рядок причини — шукати халепи.
    """
    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        assert ":" not in t("a11y_not_weighted", locale)


# ── E-08: доступність, прийшла вона від PSI чи від сайдкара ───────────
#
# До 9 вересня 2026 Lighthouse-провайдер викидав категорію, тож на ньому
# напрям доступності виключався зі скора при повністю придатних даних.
# Тести нижче судять наслідок, а не парсер: скільки знахідок виходить,
# що каже знімок і чи важить напрям ті самі 0.10.


def _perf_from_sidecar(**over: Any) -> Any:
    """Вимір, який повернув би Lighthouse-провайдер після E-08."""
    from app.audit.types import PerformanceResult, Strategy

    result = PerformanceResult(
        provider="lighthouse", strategy=Strategy.MOBILE, url="https://example.com/"
    )
    result.fetched = True
    result.lighthouse_score = 90.0
    result.accessibility_score = 66.0
    result.accessibility_failures = [
        {"id": "button-name", "title": "Buttons have no name", "impact": "critical"},
        {"id": "link-name", "title": "Links have no name", "impact": "serious"},
        {"id": "color-contrast", "title": "Low contrast", "impact": "serious"},
    ]
    result.accessibility_failures_all = list(result.accessibility_failures)
    result.accessibility_audits_total = 12
    result.accessibility_applicable = 9
    result.accessibility_passed = 6
    result.accessibility_failed = 3
    for name, value in over.items():
        setattr(result, name, value)
    return result


def _ctx_with(performance: Any) -> Any:
    from app.audit.types import PageSignals, SiteContext

    ctx = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    ctx.pages = [PageSignals(url="https://example.com/", status_code=200)]
    ctx.performance = [performance]
    return ctx


def test_one_ingested_measurement_yields_one_issue_of_each_kind() -> None:
    """Дві знахідки максимум, і жодного дубля на ту саму перевірку.

    `button-name` і `link-name` блокують користування, `color-contrast` —
    ні. Якби провайдер клав перевірку в перелік двічі, це побачив би
    саме цей тест: знахідок стало б більше, ніж кодів.
    """
    from app.audit.checks.accessibility import AccessibilityCheck, BlockingAccessibilityCheck

    ctx = _ctx_with(_perf_from_sidecar())
    blocking = list(BlockingAccessibilityCheck().run(ctx))
    ordinary = list(AccessibilityCheck().run(ctx))

    assert len(blocking) == 1
    assert len(ordinary) == 1
    assert blocking[0].params["count"] == 2
    assert ordinary[0].params["count"] == 1
    assert {i.code for i in blocking + ordinary} == {"a11y.blocking", "a11y.failures"}


def test_a_repeated_audit_in_the_failure_list_does_not_multiply_the_issues() -> None:
    """Навіть якби перелік прийшов із повтором, кодів лишається два."""
    from app.audit.checks.accessibility import AccessibilityCheck, BlockingAccessibilityCheck

    doubled = _perf_from_sidecar()
    doubled.accessibility_failures = [
        *doubled.accessibility_failures,
        {"id": "button-name", "title": "Buttons have no name", "impact": "critical"},
    ]
    ctx = _ctx_with(doubled)

    blocking = list(BlockingAccessibilityCheck().run(ctx))
    ordinary = list(AccessibilityCheck().run(ctx))
    assert len(blocking) == 1 and len(ordinary) == 1


def test_an_unmeasured_category_produces_no_accessibility_issue_at_all() -> None:
    from app.audit.checks.accessibility import AccessibilityCheck, BlockingAccessibilityCheck

    absent = _perf_from_sidecar(
        accessibility_score=None,
        accessibility_failures=[],
        accessibility_failures_all=[],
        accessibility_audits_total=None,
        accessibility_applicable=None,
        accessibility_passed=None,
        accessibility_failed=None,
    )
    ctx = _ctx_with(absent)

    assert list(BlockingAccessibilityCheck().run(ctx)) == []
    assert list(AccessibilityCheck().run(ctx)) == []


def test_an_unmeasured_category_withholds_the_module_instead_of_scoring_it() -> None:
    """Ні нуля, ні ста: напрям виключається, і причина названа."""
    from app.audit.enums import DegradationKind
    from app.audit.orchestrator import _accessibility_coverage

    absent = _perf_from_sidecar(accessibility_score=None)
    skipped: set[Module] = set()
    degraded: list[Any] = []
    _accessibility_coverage([absent], skipped, degraded)

    assert Module.ACCESSIBILITY in skipped
    assert len(degraded) == 1
    assert degraded[0].kind is DegradationKind.PROVIDER_UNAVAILABLE
    assert degraded[0].reason_key == "notice.accessibility.no_category"


def test_an_ingested_category_keeps_the_module_in_the_score() -> None:
    """Саме це E-08 і повертає: напрям існує, бо дані приїхали."""
    from app.audit.orchestrator import _accessibility_coverage

    skipped: set[Module] = set()
    degraded: list[Any] = []
    _accessibility_coverage([_perf_from_sidecar()], skipped, degraded)

    assert Module.ACCESSIBILITY not in skipped
    assert degraded == []


def test_the_ingested_measurement_carries_the_same_weight_as_on_the_psi_path() -> None:
    """0.10 — існуюча вага. G1 не змінює її, а робить застосовною."""
    document = build_report(
        _source(
            _measured(
                applicable=9,
                passed=6,
                failed=3,
                lighthouse_score=66.0,
                failures=[
                    {"id": "button-name", "title": "Buttons have no name", "impact": "critical"},
                ],
            )
        )
    )
    assert document.accessibility.counts_toward_overall is True
    assert document.accessibility.overall_weight == 0.1


def test_the_snapshot_repeats_the_providers_counters_exactly() -> None:
    """Знімок не перераховує — він переказує. Розбіжність тут була б вадою."""
    measured = _perf_from_sidecar()
    document = build_report(
        _source(
            _measured(
                applicable=measured.accessibility_applicable,
                passed=measured.accessibility_passed,
                failed=measured.accessibility_failed,
                lighthouse_score=measured.accessibility_score,
                failures=[
                    {"id": f["id"], "title": f["title"], "impact": f["impact"]}
                    for f in measured.accessibility_failures_all
                ],
            )
        )
    )
    snapshot = document.accessibility
    assert snapshot.applicable == measured.accessibility_applicable
    assert snapshot.passed == measured.accessibility_passed
    assert snapshot.failed == measured.accessibility_failed
    assert snapshot.lighthouse_score == measured.accessibility_score
    assert [f.audit_id for f in snapshot.findings] == [
        f["id"] for f in measured.accessibility_failures_all
    ]
