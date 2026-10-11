"""Сімʼя seo.h1: вузькі факти без обіцянок, одна знахідка на сторінку.

Затверджена політика: h1 — рекомендована практика, а не вимога
(Google title-link бере h1 як одне з девʼяти джерел; W3C WAI і MDN
називають один h1 практикою). Тому «немає h1, але є інший заголовок» —
LOW; «HTML-заголовків немає взагалі» — MEDIUM; «кілька h1» — INFO без
штрафу, бо видимість дублів із CSS ми не відновлюємо. Відсутній title
не підвищує серйозність: його наслідком володіє seo.title:missing.
"""

from __future__ import annotations

import uuid

from app.audit.checks.seo import H1Check, TitleCheck
from app.audit.enums import AuditStatus, Confidence, Module, Severity
from app.audit.scoring import module_score
from app.audit.types import Issue, RenderResult
from tests.factories import context, page_from_html

LOCALES = ("uk", "en", "de", "es", "fr", "ru")


def _page(body: str, head: str = "<title>Сторінка</title>", url: str = "https://example.com/"):
    return page_from_html(
        f"<html><head>{head}</head><body><main>{body}</main></body></html>", url=url
    )


def _h1_issues(*pages):
    return list(H1Check().run(context(*pages)))


# ── 1–3: наявність і missing ──────────────────────────────────────────


def test_one_h1_yields_no_family_finding() -> None:
    assert _h1_issues(_page("<h1>Тема</h1><p>текст</p>")) == []


def test_no_h1_with_h2_is_missing_low_weight_three() -> None:
    issues = _h1_issues(_page("<h2>Розділ</h2><p>текст</p>"))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_key == "seo.h1:missing"
    assert issue.severity is Severity.LOW
    assert issue.weight == 3
    assert issue.confidence is Confidence.HIGH


def test_missing_names_the_observed_level_and_text_in_evidence() -> None:
    issues = _h1_issues(_page("<h3>Доставка і оплата</h3><p>текст</p>"))
    assert issues[0].evidence["first_heading"] == "h3: Доставка і оплата"


# ── 4–7: no_headings і межа з title ───────────────────────────────────


def test_no_headings_with_title_is_medium_weight_three() -> None:
    issues = _h1_issues(_page("<p>лише текст без заголовків</p>"))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_key == "seo.h1:no_headings"
    assert issue.severity is Severity.MEDIUM
    assert issue.weight == 3
    assert issue.evidence["html_heading_count"] == 0


def test_no_headings_without_title_is_the_same_medium() -> None:
    issues = _h1_issues(_page("<p>лише текст</p>", head=""))
    assert len(issues) == 1
    assert issues[0].issue_key == "seo.h1:no_headings"
    assert issues[0].severity is Severity.MEDIUM


def test_title_absence_does_not_escalate_the_h1_family() -> None:
    """Наслідком відсутнього title володіє seo.title:missing, не ця сімʼя."""
    with_title = _h1_issues(_page("<p>текст</p>"))[0]
    without = _h1_issues(_page("<p>текст</p>", head=""))[0]
    assert with_title.severity is without.severity
    assert with_title.weight == without.weight
    assert with_title.issue_key == without.issue_key


def test_the_d_state_coexists_with_title_missing_but_family_emits_once() -> None:
    page = _page("<p>текст</p>", head="")
    site = context(page)
    h1 = list(H1Check().run(site))
    titles = [i for i in TitleCheck().run(site) if i.issue_key == "seo.title:missing"]
    assert len(h1) == 1 and h1[0].issue_key == "seo.h1:no_headings"
    assert len(titles) == 1, "title-наслідок лишається за seo.title"


# ── 8–9: що вважається наявним h1 ─────────────────────────────────────


def test_an_empty_h1_is_not_credited_as_present() -> None:
    issues = _h1_issues(_page("<h1> </h1><h2>Розділ</h2><p>текст</p>"))
    assert len(issues) == 1
    assert issues[0].issue_key == "seo.h1:missing"


def test_a_rendered_only_h1_is_credited_through_as_seen() -> None:
    """Google виконує JS — SEO-чек судить відрендерене подання."""
    static = _page("<p>текст без заголовків</p>")
    rendered = _page("<h1>Тема</h1><p>текст без заголовків</p>")
    site = context(static)
    site.renders[static.url] = RenderResult(
        url=static.url, rendered=True, html="", signals=rendered
    )
    assert list(H1Check().run(site)) == []


# ── 10–12: кілька h1 ──────────────────────────────────────────────────


def test_multiple_h1_is_info_with_medium_confidence() -> None:
    issues = _h1_issues(_page("<h1>Тема</h1><h1>Тема</h1><p>текст</p>"))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.issue_key == "seo.h1:multiple"
    assert issue.severity is Severity.INFO
    assert issue.confidence is Confidence.MEDIUM
    assert issue.params["count"] == 2


def test_multiple_h1_carries_no_numerical_penalty() -> None:
    issues = _h1_issues(_page("<h1>А</h1><h1>Б</h1><h1>В</h1><p>текст</p>"))
    assert module_score(issues, Module.SEO) == 100


def test_a_css_hidden_h1_still_counts_and_no_visibility_is_claimed() -> None:
    """CSS ми не читаємо: прихований h1 лишається спостереженим h1,
    а знахідка про дублі чесно каже, що видимість не оцінювалась."""
    hidden = _page('<h1 style="display:none">Тема</h1><h2>Розділ</h2><p>текст</p>')
    assert _h1_issues(hidden) == [], "прихований h1 — усе ще h1 для екстрактора"
    pair = _h1_issues(_page('<h1>Тема</h1><h1 style="display:none">Тема</h1><p>т</p>'))
    assert pair[0].evidence["css_visibility_assessed"] is False


# ── 13–14: межі предиката ─────────────────────────────────────────────


def test_an_aria_only_heading_is_not_an_html_heading() -> None:
    """ARIA-заголовків ми не збираємо — і формулювання обмежене HTML,
    щоб знахідка не стверджувала більшого, ніж бачив екстрактор."""
    aria = _page('<div role="heading" aria-level="1">Тема</div><p>текст</p>')
    issues = _h1_issues(aria)
    assert len(issues) == 1
    assert issues[0].issue_key == "seo.h1:no_headings"
    from app.audit.i18n.en import MESSAGES

    blob = " ".join(MESSAGES["seo.h1.no_headings"].values())
    assert "HTML" in blob, "твердження мусить бути обмежене HTML-заголовками"


def test_at_most_one_family_finding_per_page() -> None:
    for body, head in (
        ("<h1>Тема</h1><p>т</p>", "<title>t</title>"),
        ("<h2>Розділ</h2><p>т</p>", "<title>t</title>"),
        ("<p>т</p>", "<title>t</title>"),
        ("<p>т</p>", ""),
        ("<h1>А</h1><h1>Б</h1><p>т</p>", "<title>t</title>"),
    ):
        assert len(_h1_issues(_page(body, head=head))) <= 1, (body, head)


# ── 15–16: без бонусів, без суджень про непрочитане ───────────────────


def test_no_passed_check_or_bonus_exists_for_h1() -> None:
    from app.report.passed import evaluate_all

    states = evaluate_all({}, set())
    assert not any(key.startswith("seo.h1") for key in states)
    assert module_score(_h1_issues(_page("<h1>Тема</h1><p>т</p>")), Module.SEO) == 100


def test_non_eligible_pages_stay_silent() -> None:
    broken = _page("<p>Not Found</p>", url="https://example.com/gone")
    broken.status_code = 404
    assert _h1_issues(broken) == []
    assert _h1_issues() == []


# ── 17–18: шість мов ──────────────────────────────────────────────────


def test_all_three_messages_render_in_all_six_locales() -> None:
    from app.audit.i18n import Locale, render

    emitted = {
        "seo.h1.missing": {},
        "seo.h1.no_headings": {},
        "seo.h1.multiple": {"count": 2},
    }
    for code in LOCALES:
        for key, params in emitted.items():
            entry = render(key, params, Locale(code))
            assert entry.title and key not in entry.title, f"{code}/{key}"
            assert "{" not in entry.title + entry.description, f"{code}/{key}: плейсхолдер"


def test_no_locale_makes_prohibited_search_or_ai_claims() -> None:
    """Заборонені: втрата позицій, гарантії індексації, «не зможе
    зрозуміти», AI-видимість/цитування, обовʼязковість h1 і твердження,
    що побачений h2 «слугує головним заголовком»."""
    forbidden = (
        "ranking", "ранжув", "ранжир", "classement", "posicionamiento",
        "cannot understand", "не зможе зрозуміти", "не может понять",
        "kann die seite nicht verstehen", "no puede entender", "ne peut pas comprendre",
        "chatgpt", "цитуват", "цитиров", "citation", "zitier",
        "mandatory", "обовʼязков", "обязатель", "verpflichtend", "obligatorio",
        "obligatoire",
        "serves as the main", "слугує головним", "служит главным",
    )
    for code in LOCALES:
        module = __import__(f"app.audit.i18n.{code}", fromlist=["MESSAGES"])
        for key in ("seo.h1.missing", "seo.h1.no_headings", "seo.h1.multiple"):
            blob = " ".join(module.MESSAGES[key].values()).lower()
            for mark in forbidden:
                assert mark not in blob, f"{code}/{key}: «{mark}»"


# ── 19–20: поверхні звіту й історичні рядки ───────────────────────────


def _report_source(issues):
    from app.report.types import ReportSource

    return ReportSource(
        url="https://example.com", entry_url="https://example.com/",
        origin="https://example.com", overall=70,
        scores={m.value: 70 for m in Module}, issues=issues, degraded=[],
        skipped_modules=set(), evidence={}, pages_crawled=3,
        status=AuditStatus.COMPLETED,
    )


def test_the_new_variant_travels_the_surfaces_without_raw_keys() -> None:
    import io
    import re
    import zipfile

    from app.audit.i18n import Locale
    from app.report.builder import build_report
    from app.report.docx import render_docx
    from app.report.web import to_web

    fresh = Issue(
        code="seo.h1", module=Module.SEO, severity=Severity.MEDIUM, title="",
        evidence={"html_heading_count": 0, "title_present": True}, weight=3,
        page_url="https://example.com/", msg="seo.h1.no_headings", params={},
        key="no_headings",
    )
    document = build_report(_report_source([fresh]))
    entry = next(i for i in document.issues if i.code == "seo.h1")
    assert entry.title and "seo.h1.no_headings" not in entry.title

    result = to_web(document, audit_id=uuid.uuid4(), site_id=None,
                    status="completed", finished_at=None, fallback_locale="uk")
    assert any(f.issue_key == "seo.h1:no_headings" for f in result.findings)

    blob = render_docx(build_report(_report_source([fresh])), Locale.EN)
    xml = zipfile.ZipFile(io.BytesIO(blob)).read("word/document.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", " ", xml)
    assert "seo.h1.no_headings" not in text, "сирий ключ у документі"


def test_historical_missing_and_multiple_rows_remain_readable() -> None:
    """Старі рядки БД: missing без params (і серед них — сторінки взагалі
    без заголовків), multiple лише з count. Жоден не сміє показати сирий
    плейсхолдер чи ключ."""
    from app.report.builder import build_report

    old_missing = Issue(
        code="seo.h1", module=Module.SEO, severity=Severity.HIGH, title="",
        evidence={"found": [], "headings": [], "title": None}, weight=3,
        page_url="https://old.example/", msg="seo.h1.missing", params={},
        key="missing",
    )
    old_multiple = Issue(
        code="seo.h1", module=Module.SEO, severity=Severity.LOW, title="",
        evidence={"h1": ["А", "Б"]}, weight=3,
        page_url="https://old.example/", msg="seo.h1.multiple",
        params={"count": 2}, key="multiple",
    )
    document = build_report(_report_source([old_missing, old_multiple]))
    rendered = [i for i in document.issues if i.code == "seo.h1"]
    assert len(rendered) == 2
    for entry in rendered:
        assert entry.title
        assert "seo.h1." not in entry.title
        assert "{" not in entry.title + (entry.description or "")


# ── E-16: «перший заголовок» у доказі означає перший ──────────────────
#
# До E-16 екстрактор віддавав заголовки згрупованими за рівнем, тож
# `next(iter(page.headings))` брав НАЙНИЖЧИЙ рівень сторінки, а не той
# заголовок, який читач бачить першим. На сторінці, де після `h3` іде `h2`,
# доказ називав `h2` — і це було твердження про наш обхід, а не про сайт.


def _missing_evidence(body: str) -> dict:
    issues = _h1_issues(_page(body))
    assert len(issues) == 1
    assert issues[0].issue_key == "seo.h1:missing"
    return dict(issues[0].evidence)


def test_first_heading_evidence_names_the_first_heading_in_document_order():
    evidence = _missing_evidence("<h3>Спершу третій</h3><h2>Потім другий</h2><p>текст</p>")

    assert evidence["first_heading"] == "h3: Спершу третій"
    assert evidence["first_heading_in_document_order"] is True


def test_first_heading_evidence_is_untouched_when_order_is_not_proven():
    """Старий знімок лишається байт у байт таким, яким був.

    Без доведеного порядку «перший» і далі означає найнижчий рівень — і
    саме тому позначки про порядок у доказі НЕМАЄ: її поява на старому
    знімку зробила б перерахунок дельтою там, де сайт не змінився.
    """
    from app.audit.snapshot import _dump, _load_page

    row = _dump(_page("<h3>Спершу третій</h3><h2>Потім другий</h2><p>текст</p>"))
    row.pop("headings_in_document_order")
    row["headings"] = [list(h) for h in sorted(row["headings"], key=lambda h: h[0])]
    legacy = _load_page(row)

    issues = list(H1Check().run(context(legacy)))
    assert len(issues) == 1
    evidence = dict(issues[0].evidence)
    assert evidence["first_heading"] == "h2: Потім другий"
    assert "first_heading_in_document_order" not in evidence
    assert set(evidence) == {"found", "first_heading", "title"}


def test_the_h1_family_verdicts_do_not_move_with_the_new_order():
    # Жоден вердикт сімʼї не залежить від порядку: список h1 той самий,
    # кількість та сама, серйозності ті самі.
    assert _h1_issues(_page("<h3>Третій</h3><h1>Тема</h1><h2>Другий</h2>")) == []

    multiple = _h1_issues(_page("<h3>Третій</h3><h1>Одна</h1><h1>Дві</h1>"))
    assert len(multiple) == 1
    assert multiple[0].issue_key == "seo.h1:multiple"
    assert multiple[0].evidence["h1"] == ["Одна", "Дві"]

    none_at_all = _h1_issues(_page("<p>текст без заголовків</p>"))
    assert len(none_at_all) == 1
    assert none_at_all[0].issue_key == "seo.h1:no_headings"
