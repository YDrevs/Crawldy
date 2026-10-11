"""Паритет звіту в шести мовах запуску — на справжніх даних.

Документ будується продуктовим шляхом (знімок → перерахунок →
build_report) для кожної мови. Тести не читають словники — вони
читають те, що побачить клієнт: заголовки знахідок, рядки прогалин
даних, Word-документ.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import pytest

from app.audit.i18n import CATALOGS, Locale
from app.audit.orchestrator import rescore
from app.audit.snapshot import load as load_snapshot
from app.report import build_report, source_from_outcome
from app.report.docx import render_docx

FIXTURES = Path(__file__).parent / "fixtures" / "snapshots"
LAUNCH = [Locale.EN, Locale.DE, Locale.ES, Locale.FR, Locale.RU, Locale.UK]


def _outcome(name: str):
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    ctx = load_snapshot(data)
    return rescore(ctx), ctx


@pytest.fixture(scope="module")
def small_site():
    return _outcome("schema1_small_site")


@pytest.fixture(scope="module")
def blocked_crawl():
    return _outcome("schema1_blocked_crawl")


@pytest.mark.parametrize("locale", LAUNCH, ids=lambda loc: loc.value)
def test_full_report_renders_in_the_requested_language(small_site, locale):
    """Кожна мова запуску віддає СВОЇ рядки, а не англійський фолбек.

    Заголовок першої знахідки мусить існувати в каталозі цієї мови — і,
    для неанглійських мов, не збігатися з англійським відповідником."""
    outcome, ctx = small_site
    document = build_report(source_from_outcome(outcome, url=ctx.entry_url), locale)
    assert document.issues, "фікстура мусить мати знахідки"

    catalogue_titles = {
        entry["title"].split("{")[0][:25]
        for entry in CATALOGS[locale].values()
    }
    first = document.issues[0].title
    assert any(first.startswith(prefix) for prefix in catalogue_titles if prefix), (
        f"{locale.value}: заголовок «{first}» не з каталогу цієї мови"
    )

    if locale is not Locale.EN:
        english = build_report(source_from_outcome(outcome, url=ctx.entry_url), Locale.EN)
        localized_pairs = sum(
            1
            for ours, en in zip(document.issues, english.issues, strict=True)
            if ours.title != en.title
        )
        assert localized_pairs > len(document.issues) * 0.8, (
            f"{locale.value}: більшість заголовків збігається з англійськими — "
            "схоже на фолбек"
        )


@pytest.mark.parametrize("locale", LAUNCH, ids=lambda loc: loc.value)
def test_no_raw_message_keys_or_fallback_in_rendered_output(small_site, locale):
    """У відданому клієнту JSON немає сирих ключів і слідів фолбеку."""
    outcome, ctx = small_site
    document = build_report(source_from_outcome(outcome, url=ctx.entry_url), locale)
    payload = json.dumps(document.to_json(), ensure_ascii=False)

    # Сирий ключ повідомлення в тексті — «notice.crawl.blind» тощо.
    assert not re.search(r"\bnotice\.[a-z_.]+\b", payload)
    # Плейсхолдер, який ніхто не підставив.
    for issue in document.issues:
        for text in (issue.title, issue.description, issue.recommendation):
            assert not re.search(r"\{[a-z_]+\}", text), (locale.value, text)


@pytest.mark.parametrize("locale", LAUNCH, ids=lambda loc: loc.value)
def test_unmeasured_states_localize(blocked_crawl, locale):
    """Стани «не виміряли» теж локалізовані: бал порожній, причина — мовою."""
    outcome, ctx = blocked_crawl
    document = build_report(source_from_outcome(outcome, url=ctx.entry_url), locale)
    assert document.overall_score is None, "фікстура без бала"
    assert document.missing_data, "має бути прогалина даних"

    reasons = " ".join(m.reason for m in document.missing_data)
    assert "notice." not in reasons
    if locale is not Locale.EN:
        english = build_report(source_from_outcome(outcome, url=ctx.entry_url), Locale.EN)
        english_reasons = " ".join(m.reason for m in english.missing_data)
        assert reasons != english_reasons, f"{locale.value}: причини лишились англійськими"


@pytest.mark.parametrize("locale", LAUNCH, ids=lambda loc: loc.value)
def test_docx_builds_and_carries_the_language(small_site, locale):
    """Word-документ збирається кожною мовою й несе її рядки.

    Перевіряється не рендеринг шрифтів, а вміст: заголовок розділу
    «Що робити першим» цієї мови присутній у document.xml."""
    from app.report.i18n import STRINGS

    outcome, ctx = small_site
    document = build_report(source_from_outcome(outcome, url=ctx.entry_url), locale)
    blob = render_docx(document, locale)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")

    marker = STRINGS[locale]["section_priorities"]
    assert marker in xml, f"{locale.value}: у документі немає «{marker}»"
    _assert_no_raw_skeleton_keys(xml, locale)
    if locale is not Locale.EN:
        english_marker = STRINGS[Locale.EN]["section_priorities"]
        assert english_marker not in xml, (
            f"{locale.value}: документ несе англійський каркас поруч із перекладом"
        )


def _assert_no_raw_skeleton_keys(xml: str, locale) -> None:
    """Пропущений ключ каркаса віддається клієнту як сам ключ.

    Саме так «area_accessibility» стояв у таблиці напрямів, а
    «verdict_unknown» — у вердикті заблокованого краулу, всіма шістьма
    мовами одразу: тест на паритет мов цього не бачив, бо ключа
    бракувало в усіх мовах однаково."""
    raw = re.search(r">(?:area|owner|col|band|verdict|module|ev)_[a-z_.]+<", xml)
    assert raw is None, f"{locale.value}: сирий ключ каркаса в документі: {raw.group()}"


@pytest.mark.parametrize("locale", LAUNCH, ids=lambda loc: loc.value)
def test_docx_of_a_blocked_crawl_has_no_raw_keys(blocked_crawl, locale):
    """Стани без бала теж мають рядок для кожного ключа каркаса.

    Вердикт «unknown» живе лише в документах без загального бала, тож
    звичайна фікстура його не зачіпає."""
    outcome, ctx = blocked_crawl
    document = build_report(source_from_outcome(outcome, url=ctx.entry_url), locale)
    blob = render_docx(document, locale)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        xml = archive.read("word/document.xml").decode("utf-8")
    _assert_no_raw_skeleton_keys(xml, locale)


def test_unsupported_locale_still_falls_back_safely(small_site):
    """Мова поза шістьма — наявна безпечна поведінка: дефолт, не 500."""
    outcome, ctx = small_site
    document = build_report(source_from_outcome(outcome, url=ctx.entry_url), Locale.PT)
    english = build_report(source_from_outcome(outcome, url=ctx.entry_url), Locale.EN)
    assert document.issues[0].title == english.issues[0].title
