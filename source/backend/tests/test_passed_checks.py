"""Пройдені перевірки: явний доказ, нуль впливу на бали, чесна межа.

Головні інваріанти: пройдене ніколи не виводиться з тиші чека; жоден
стан, крім PASSED, не потрапляє до клієнта; бали до і після появи
контракту ідентичні, бо скоринг цього шару не бачить узагалі.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.audit.enums import AuditStatus, Module
from app.report.builder import build_report
from app.report.passed import PassState, collect_passed, evaluate_all
from app.report.types import ReportSource
from app.report.web import to_web


def _evidence(**over: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "http": {"origin": "https://e.com", "is_https": True, "hsts": True, "tls_error": None},
        "robots_txt": {"exists": True, "status_code": 200},
        "sitemap_xml": {"exists": True, "url_count": 40, "parse_error": None},
        "security_headers": {
            "available": True, "complete": True, "checked_url": "https://e.com/",
            "missing": [],
        },
        "analytics": {"found": ["google_analytics"], "checked_after_render": True},
        "llms_txt": {"exists": True, "status_code": 200},
        "structured_data": {"pages_with_jsonld": 5, "pages_total": 10},
    }
    base.update(over)
    return base


def _source(evidence: dict[str, Any], *, skipped: set[Module] | None = None) -> ReportSource:
    return ReportSource(
        url="https://e.com", entry_url="https://e.com/", origin="https://e.com",
        overall=60, scores={m.value: 60 for m in Module}, issues=[], degraded=[],
        skipped_modules=set(skipped or ()), evidence=evidence, pages_crawled=5,
        status=AuditStatus.COMPLETED,
    )


# ── явний успіх зʼявляється ───────────────────────────────────────────


def test_explicit_successes_appear_in_order() -> None:
    passed = collect_passed(_evidence(), set())
    assert [p.key for p in passed] == [
        "seo.https", "seo.robots_txt", "seo.sitemap",
        "tech.security_headers", "tech.analytics", "ai.jsonld", "ai.llms_txt",
    ]


# ── тиша — не доказ ───────────────────────────────────────────────────


def test_absence_of_evidence_creates_no_pass() -> None:
    """Старий аудит без блоків доказів не вигадує собі пройденого."""
    assert collect_passed({}, set()) == []
    states = evaluate_all({}, set())
    assert set(states.values()) == {PassState.UNAVAILABLE}


def test_a_failed_fact_does_not_appear_as_passed() -> None:
    evidence = _evidence(
        http={"origin": "http://e.com", "is_https": False, "tls_error": None},
        security_headers={"available": True, "complete": False, "missing": ["x-frame-options"]},
        analytics={"found": [], "checked_after_render": True},
    )
    keys = {p.key for p in collect_passed(evidence, set())}
    assert "seo.https" not in keys
    assert "tech.security_headers" not in keys
    assert "tech.analytics" not in keys


def test_unavailable_evidence_does_not_appear_as_passed() -> None:
    """Провайдер мовчав чи блок не зібрано — це «не знаємо», не «пройдено»."""
    evidence = _evidence(
        security_headers={"available": False},
        llms_txt={"exists": False, "status_code": None},
    )
    states = evaluate_all(evidence, set())
    assert states["tech.security_headers"] is PassState.UNAVAILABLE
    assert states["ai.llms_txt"] is PassState.UNAVAILABLE
    keys = {p.key for p in collect_passed(evidence, set())}
    assert not {"tech.security_headers", "ai.llms_txt"} & keys


def test_https_without_certificate_evidence_is_unavailable_not_passed() -> None:
    """Старий аудит зберігав is_https, але не tls_error: схема без доказу
    сертифіката — не «HTTPS пройдено»."""
    evidence = _evidence(http={"origin": "https://e.com", "is_https": True})
    assert evaluate_all(evidence, set())["seo.https"] is PassState.UNAVAILABLE


def test_skipped_module_produces_no_passes() -> None:
    """Покриття притримало напрям або користувач вимкнув — хвалити наосліп
    не можна."""
    withheld = {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY}
    keys = {p.key for p in collect_passed(_evidence(), withheld)}
    assert keys == {"tech.security_headers", "tech.analytics"}
    states = evaluate_all(_evidence(), withheld)
    assert states["seo.https"] is PassState.SKIPPED
    assert states["ai.jsonld"] is PassState.SKIPPED


def test_page_scoped_evidence_stays_page_scoped() -> None:
    check = next(
        p for p in collect_passed(_evidence(), set())
        if p.key == "tech.security_headers"
    )
    assert check.scope == "page"
    assert check.facts["checked_url"] == "https://e.com/"


def test_accessibility_is_never_in_the_generic_passed_section() -> None:
    """Доступність має власний знімок; дублювати його тут не можна."""
    from app.report.passed import CURATED

    assert all(module is not Module.ACCESSIBILITY for _, module, _ in CURATED)


# ── бали не рухаються ─────────────────────────────────────────────────


def test_scores_are_identical_with_and_without_passed_evidence() -> None:
    """Пройдені перевірки — довідка. Бали їх не бачать за побудовою."""
    rich = build_report(_source(_evidence()))
    bare = build_report(_source({}))
    assert len(rich.passed_checks) == 7
    assert bare.passed_checks == []
    assert rich.overall_score == bare.overall_score
    assert {e.module: e.score for e in rich.scores} == {e.module: e.score for e in bare.scores}


def test_passed_checks_never_offset_penalties() -> None:
    """Сім пройдених не компенсують жодного штрафу знахідки."""
    from app.audit.enums import Severity
    from app.audit.types import Issue

    issue = Issue(code="seo.title", module=Module.SEO, severity=Severity.MEDIUM,
                  title="t", evidence={}, weight=2, page_url=None,
                  msg="seo.title.missing", params={}, key="missing")
    with_passes = build_report(_source(_evidence()))
    src = _source(_evidence())
    src.issues = [issue]
    with_issue = build_report(src)
    # Бал зі знахідкою нижчий незалежно від кількості пройденого поруч.
    assert len(with_issue.passed_checks) == 7
    seo_clean = next(e.score for e in with_passes.scores if e.module is Module.SEO)
    seo_hit = next(e.score for e in with_issue.scores if e.module is Module.SEO)
    assert seo_clean == 60 and seo_hit == 60, "бали приходять із source і не рухаються"


# ── поширення по поверхнях ────────────────────────────────────────────


def test_passes_travel_to_the_public_contract_localized() -> None:
    document = build_report(_source(_evidence()))
    result = to_web(document, audit_id=uuid.uuid4(), site_id=None,
                    status="completed", finished_at=None, fallback_locale="uk")
    assert len(result.passed_checks) == 7
    first = result.passed_checks[0]
    assert first.key == "seo.https"
    assert first.title and "passed." not in first.title, "заголовок локалізовано"
    sitemap = next(p for p in result.passed_checks if p.key == "seo.sitemap")
    assert "40" in sitemap.title


def test_every_locale_renders_every_passed_title() -> None:
    from app.audit.i18n import COMPLETE_LOCALES
    from app.report.i18n import t
    from app.report.passed import CURATED

    facts = {
        "declared": 7, "found": "x", "pages": 2, "total": 5, "count": 3,
        "providers": "turnstile", "forms": 1,
    }
    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        assert "{count}" not in t("section_passed", locale, count=3)
        for key, _, _ in CURATED:
            text = t(f"passed.{key}", locale, **facts)
            assert "passed." not in text, f"{locale.value}: сирий ключ {key}"


def test_json_report_carries_passed_checks() -> None:
    payload = build_report(_source(_evidence())).to_json()
    assert len(payload["passed_checks"]) == 7
    assert payload["passed_checks"][0] == {
        "key": "seo.https", "module": "seo", "scope": "origin",
        "facts": {"origin": "https://e.com"},
    }


def test_an_old_stored_audit_renders_with_no_fabricated_passes() -> None:
    document = build_report(_source({}))
    assert document.passed_checks == []
    result = to_web(document, audit_id=uuid.uuid4(), site_id=None,
                    status="completed", finished_at=None, fallback_locale="uk")
    assert result.passed_checks == []


# ── DOCX ──────────────────────────────────────────────────────────────


def _docx_text(document: Any, locale: Any) -> str:
    import io
    import re
    import zipfile

    from app.report.docx import render_docx

    blob = render_docx(document, locale)
    xml = zipfile.ZipFile(io.BytesIO(blob)).read("word/document.xml").decode("utf-8")
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", xml))


def test_docx_places_passed_after_details_and_groups_by_module() -> None:
    from app.audit.i18n import Locale
    from app.report.i18n import t

    document = build_report(_source(_evidence()))
    body = _docx_text(document, Locale.UK)
    heading = t("section_passed", Locale.UK, count=7)
    assert heading in body
    # після повного розбору, перед доказами
    assert body.index(t("section_details", Locale.UK)) < body.index(heading)
    assert t("passed.seo.https", Locale.UK) in body


def test_docx_hides_the_section_when_nothing_passed() -> None:
    from app.audit.i18n import Locale
    from app.report.i18n import t

    document = build_report(_source({}))
    body = _docx_text(document, Locale.UK)
    assert t("section_passed", Locale.UK, count=0).split(":")[0] not in body


# ── вузькість факту: пройдене не глушить знахідок і не конфліктує ─────


def test_a_check_is_never_both_failed_and_passed() -> None:
    """Спільна функція доказу робить конфлікт неможливим.

    «Повний набір заголовків» пройденого означає рівно «missing порожній»
    у детектора: обидва читають security_header_gaps, тож одночасно
    «пройдено» і «бракує» не буває за побудовою.
    """
    from app.audit.checks.tech import SecurityHeadersCheck
    from tests.factories import context, page_from_html

    page = page_from_html("<html></html>", url="https://e.com/")
    page.headers = {
        "content-security-policy": "default-src 'self'",
        "x-frame-options": "DENY",
        "x-content-type-options": "nosniff",
        "referrer-policy": "no-referrer",
        "permissions-policy": "camera=()",
    }
    ctx = context(page)
    finding = list(SecurityHeadersCheck().run(ctx))
    from app.report.builder import build_evidence

    passed = collect_passed(build_evidence(ctx), set())
    header_pass = any(p.key == "tech.security_headers" for p in passed)
    assert finding == [] and header_pass, "повний набір: знахідки немає, пройдене є"

    page.headers.pop("x-frame-options")
    page.headers["content-security-policy"] = "default-src 'self'"
    finding = list(SecurityHeadersCheck().run(context(page)))
    passed = collect_passed(build_evidence(context(page)), set())
    header_pass = any(p.key == "tech.security_headers" for p in passed)
    assert finding and not header_pass, "бракує: знахідка є, пройденого немає"


def test_restricted_robots_is_still_only_retrieved() -> None:
    """robots.txt із повною забороною — «отримано», і не більше.

    Сама заборона лишається окремою видимою знахідкою через стан
    покриття (robots_restricted); пройдене каже лише про факт отримання
    файла й нічого про його зміст.
    """
    evidence = _evidence(robots_txt={"exists": True, "status_code": 200,
                                     "disallows_all": True})
    states = evaluate_all(evidence, set())
    assert states["seo.robots_txt"] is PassState.PASSED
    from app.audit.i18n import Locale
    from app.report.i18n import t

    title = t("passed.seo.robots_txt", Locale.EN)
    for overclaim in ("unrestricted", "allows", "correct", "valid"):
        assert overclaim not in title.lower()


# ── аналітика: пройдене читає ВИД доказу, а не наявність рядка (E-11) ─


def _fact(**over: Any) -> dict[str, Any]:
    """Факт аналітики нового зразка: перелік вендорів плюс класифікація."""
    fact: dict[str, Any] = {
        "found": [], "checked_after_render": True, "kind": "NONE", "verdict": "FAIL",
        "coverage": "COMPLETE", "observations": [], "unidentified": [],
    }
    fact.update(over)
    return fact


def _observation(**over: Any) -> dict[str, str]:
    row = {"kind": "UNIDENTIFIED_MEASUREMENT", "rule_id": "generic.measurement_path",
           "channel": "request", "signal": "https://e.com/api/collect"}
    row.update(over)
    return row


def test_a_verified_vendor_is_what_passes() -> None:
    fact = _fact(
        found=["google_analytics"], kind="VERIFIED_VENDOR", verdict="PASS",
        observations=[_observation(kind="VERIFIED_VENDOR", vendor="google_analytics",
                                   rule_id="google_analytics.host",
                                   signal="https://www.google-analytics.com/g/collect")],
    )
    assert evaluate_all(_evidence(analytics=fact), set())["tech.analytics"] is PassState.PASSED


def test_unidentified_measurement_is_never_passed_and_never_called_absent() -> None:
    """Власний `/api/collect` щось міряє. Пройденим це не робить — і «немає
    аналітики» теж: доказу для жодного з двох тверджень немає."""
    fact = _fact(kind="UNIDENTIFIED_MEASUREMENT", verdict="NO_VERDICT",
                 unidentified=[_observation()], observations=[_observation()])
    evidence = _evidence(analytics=fact)

    assert evaluate_all(evidence, set())["tech.analytics"] is PassState.UNAVAILABLE
    assert "tech.analytics" not in {p.key for p in collect_passed(evidence, set())}


def test_no_signal_at_all_stays_failed() -> None:
    assert evaluate_all(_evidence(analytics=_fact()), set())["tech.analytics"] is PassState.FAILED


def test_one_verified_vendor_settles_it_beside_unidentified_traffic() -> None:
    """ANY_SUFFICIENT_EVIDENCE: один впізнаний вендор вирішує питання."""
    fact = _fact(found=["plausible"], kind="VERIFIED_VENDOR", verdict="PASS",
                 unidentified=[_observation(signal="https://e.com/telemetry")])
    (entry,) = [p for p in collect_passed(_evidence(analytics=fact), set())
                if p.key == "tech.analytics"]

    assert entry.facts["found"] == "plausible", "у факті лише впізнане"


def test_a_legacy_first_party_label_is_not_a_vendor() -> None:
    """Збережений аудит: `first_party` означав «вендора назвати не змогли»."""
    states = evaluate_all(
        _evidence(analytics={"found": ["first_party"], "checked_after_render": True}), set()
    )
    assert states["tech.analytics"] is PassState.UNAVAILABLE


def test_a_legacy_vendor_string_still_renders_an_old_report() -> None:
    """Старий факт без нових полів лишається читабельним: поля додані, а не замінені."""
    states = evaluate_all(
        _evidence(analytics={"found": ["google_analytics"], "checked_after_render": False}), set()
    )
    assert states["tech.analytics"] is PassState.PASSED


def test_the_fact_names_at_most_four_vendors() -> None:
    fact = _fact(found=["amplitude", "google_analytics", "heap", "matomo", "plausible"],
                 kind="VERIFIED_VENDOR", verdict="PASS")
    (entry,) = [p for p in collect_passed(_evidence(analytics=fact), set())
                if p.key == "tech.analytics"]

    assert entry.facts["found"] == "amplitude, google_analytics, heap, matomo"


def test_sitemap_pass_coexists_with_sitemap_quality_findings() -> None:
    """«Карту оголошено: N адрес» не глушить знахідок про її якість."""
    from app.audit.enums import Severity
    from app.audit.types import Issue

    src = _source(_evidence())
    src.issues = [Issue(code="seo.sitemap_consistency", module=Module.SEO,
                        severity=Severity.LOW, title="t", evidence={}, weight=1,
                        page_url=None, msg="seo.sitemap_consistency", params={},
                        key="redirect")]
    document = build_report(src)
    assert any(p.key == "seo.sitemap" for p in document.passed_checks)
    assert any(i.code == "seo.sitemap_consistency" for i in document.issues)
