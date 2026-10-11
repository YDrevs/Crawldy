"""Вилучення llm.direct_answer: нові аудити мовчать, старі читаються.

Предикат міряв не сайт, а нашу екстракцію і латинську пунктуацію:
27 із 30 спрацювань вибірки були навігаційними артефактами, CJK-сторінки
не могли пройти структурно, а формулювання обіцяло поведінку ChatGPT,
якої не документує жоден провайдер. Ці тести тримають обидва боки межі:
жодної нової емісії — і жодного зламаного збереженого звіту.
"""

from __future__ import annotations

import uuid

from app.audit.checks.base import REGISTRY, RETIRED_MESSAGE_KEYS, all_message_keys
from app.audit.enums import AuditStatus, Module, Severity
from app.audit.orchestrator import rescore
from app.audit.types import Issue
from tests.factories import context, page_from_html


def _page(text_html: str, url: str = "https://example.com/"):
    return page_from_html(f"<html><body>{text_html}</body></html>", url=url)


# ── вилучено з продукції ──────────────────────────────────────────────


def test_the_check_is_absent_from_the_active_registry() -> None:
    assert all(cls.code != "llm.direct_answer" for cls in REGISTRY)
    assert "llm.direct_answer" not in all_message_keys()
    assert "llm.direct_answer" in RETIRED_MESSAGE_KEYS


def test_a_navigation_prefix_page_emits_nothing_in_its_place() -> None:
    """Меню перед вмістом — головне хибне спрацювання вилученого чека.

    fastapi.tiangolo.com: «Sponsors Keystone Sponsor Gold Sponsors…» —
    сторінка з повноцінним вмістом, чий текст починається навігацією.
    Жодної заміни цьому спрацюванню бути не повинно.
    """
    nav = " ".join(f"Item{i}" for i in range(120))
    ctx = context(_page(f"<main>{nav} довгий справжній текст іде далі тут</main>"))
    outcome = rescore(ctx)
    assert all(i.code != "llm.direct_answer" for i in outcome.issues)
    assert all("direct" not in i.code for i in outcome.issues)


def test_cjk_punctuation_cannot_cause_a_replacement_penalty() -> None:
    """Речення з 。！？ не мають латинської крапки — і не мають штрафу."""
    cjk = "这是一个完整的句子描述了网站的主要目的。它包含了所有必要的信息。" * 12
    ctx = context(_page(f"<main>{cjk}</main>"))
    outcome = rescore(ctx)
    assert all(i.code != "llm.direct_answer" for i in outcome.issues)


def test_list_first_pages_receive_no_replacement_penalty() -> None:
    items = "".join(f"<li>Пункт номер {i}</li>" for i in range(60))
    ctx = context(_page(f"<main><ul>{items}</ul></main>"))
    outcome = rescore(ctx)
    assert all(i.code != "llm.direct_answer" for i in outcome.issues)


def test_adjacent_retained_checks_still_execute() -> None:
    """Сусіди не зачеплені: стіна тексту без підзаголовків досі знахідка."""
    wall = "слово " * 400
    ctx = context(_page(f"<main><h1>Т</h1><p>{wall}</p></main>"))
    outcome = rescore(ctx)
    codes = {i.code for i in outcome.issues}
    assert "llm.structure" in codes, "llm.structure живий"
    assert "llm.about_page" in codes, "llm.about_page живий"


# ── збережені аудити читаються ────────────────────────────────────────


def test_old_stored_findings_render_in_all_six_locales() -> None:
    from app.audit.i18n import COMPLETE_LOCALES, render

    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        entry = render("llm.direct_answer", {}, locale)
        assert entry.title, f"{locale.value}: порожній title"
        assert "llm.direct_answer" not in entry.title, f"{locale.value}: сирий ключ"


def test_an_old_stored_result_travels_through_report_and_api() -> None:
    """Рядок БД зі старою знахідкою → звіт → API, без падінь і без дірок."""
    from app.report.builder import build_report
    from app.report.types import ReportSource
    from app.report.web import to_web

    stored = Issue(
        code="llm.direct_answer", module=Module.LLM_VISIBILITY,
        severity=Severity.MEDIUM, title="", evidence={"intro": "…"},
        weight=3, page_url="https://old.example/", msg="llm.direct_answer",
        params={}, key="",
    )
    src = ReportSource(
        url="https://old.example", entry_url="https://old.example/",
        origin="https://old.example", overall=55,
        scores={m.value: 55 for m in Module}, issues=[stored], degraded=[],
        skipped_modules=set(), evidence={}, pages_crawled=3,
        status=AuditStatus.COMPLETED,
    )
    document = build_report(src)
    entry = next(i for i in document.issues if i.code == "llm.direct_answer")
    assert entry.title and "llm.direct_answer" not in entry.title

    result = to_web(document, audit_id=uuid.uuid4(), site_id=None,
                    status="completed", finished_at=None, fallback_locale="uk")
    assert any(f.issue_key == "llm.direct_answer" for f in result.findings)


def test_docx_renders_an_old_stored_finding() -> None:
    import io
    import re
    import zipfile

    from app.audit.i18n import Locale
    from app.report.builder import build_report
    from app.report.docx import render_docx
    from app.report.types import ReportSource

    stored = Issue(
        code="llm.direct_answer", module=Module.LLM_VISIBILITY,
        severity=Severity.MEDIUM, title="", evidence={"intro": "…"},
        weight=3, page_url=None, msg="llm.direct_answer", params={}, key="",
    )
    src = ReportSource(
        url="https://old.example", entry_url="https://old.example/",
        origin="https://old.example", overall=55,
        scores={m.value: 55 for m in Module}, issues=[stored], degraded=[],
        skipped_modules=set(), evidence={}, pages_crawled=3,
        status=AuditStatus.COMPLETED,
    )
    blob = render_docx(build_report(src), Locale.EN)
    xml = zipfile.ZipFile(io.BytesIO(blob)).read("word/document.xml").decode("utf-8")
    text = re.sub(r"<[^>]+>", " ", xml)
    assert "llm.direct_answer" not in text, "сирий ключ у документі"


def test_removal_does_not_touch_score_availability_or_coverage() -> None:
    """Порожній вплив на все, крім самої знахідки: гейти й стани ті самі."""
    nav = " ".join(f"Item{i}" for i in range(120))
    ctx = context(_page(f"<main>{nav}</main>", url="https://example.com/"))
    outcome = rescore(ctx)
    # знахідки немає — а бал модуля існує (модуль не пропущено)
    assert Module.LLM_VISIBILITY not in outcome.skipped_modules
    assert "llm_visibility" in outcome.scores


# ── legacy-текст: правда про вилучення, жодних старих обіцянок ────────


def test_the_retired_wording_names_itself_legacy_in_all_six_locales() -> None:
    """Старий запис рендериться — і чесно каже, що він застарілий."""
    from app.audit.i18n import COMPLETE_LOCALES, render

    legacy_marks = {
        "uk": "застаріл", "en": "legacy", "de": "veraltet",
        "es": "retirad", "fr": "retiré", "ru": "устаревш",
    }
    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        entry = render("llm.direct_answer", {}, locale)
        blob = " ".join([entry.title, entry.description,
                         entry.recommendation, entry.consequence]).lower()
        assert legacy_marks[locale.value] in blob, f"{locale.value}: не названо застарілим"
        assert "llm.direct_answer" not in blob, f"{locale.value}: сирий ключ"


def test_the_retired_wording_makes_no_citation_or_provider_claims() -> None:
    """Жодного «ChatGPT цитує», жодної поради дописати вступні речення."""
    from app.audit.i18n import COMPLETE_LOCALES, render

    forbidden = ("chatgpt", "perplexity", "цитує", "цитиру", "cites", "citation",
                 "zitiert", "cita ", "cite ", "2-3", "2–3", "трьох речень",
                 "opening sentences", "перших абзац")
    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        entry = render("llm.direct_answer", {}, locale)
        blob = " ".join([entry.title, entry.description,
                         entry.recommendation, entry.consequence]).lower()
        for mark in forbidden:
            assert mark not in blob, f"{locale.value}: заборонене «{mark}»"
