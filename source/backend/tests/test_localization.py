"""Один аудит — багато мов, і жодного повторного запуску двигуна.

Головна вимога багатомовності не про переклад, а про те, **що зберігається**.
Якщо в базі лежить готовий текст, він і є результатом аудиту, і показати
його іншою мовою можна лише перекраулівши сайт. Якщо лежить структура —
ключ, параметри, серйозність, вага, докази, — мова стає питанням рендеру.

Тут перевіряється саме це: беремо зібраний аудит, віддаємо його двома
мовами й переконуємось, що змінився лише текст.
"""

from __future__ import annotations

import pytest

from app.application.locale import resolve
from app.audit import i18n
from app.audit.enums import Module, Severity
from app.audit.i18n import Locale
from app.audit.types import Issue
from app.report.builder import build_report
from app.report.types import ReportSource


def _source() -> ReportSource:
    """Зібраний аудит: структура, а не текст."""
    return ReportSource(
        url="https://example.com/",
        entry_url="https://example.com/",
        origin="https://example.com",
        degraded=[],
        skipped_modules=[],
        evidence={},
        overall=64,
        scores={"seo": 55, "performance": 70},
        issues=[
            Issue(
                code="seo.h1",
                module=Module.SEO,
                severity=Severity.HIGH,
                title="cached",
                description="cached",
                recommendation="cached",
                evidence={"found": 2, "expected": 1},
                weight=3,
                page_url="https://example.com/",
                msg="seo.h1.multiple",
                params={"count": 2},
                key="multiple",
            ),
            Issue(
                code="seo.title",
                module=Module.SEO,
                severity=Severity.CRITICAL,
                title="cached",
                description="cached",
                recommendation="cached",
                evidence={"found": "", "expected": "title"},
                weight=4,
                page_url="https://example.com/",
                msg="seo.title.missing",
                params={"count": 1},
                key="missing",
            ),
        ],
        versions={"detector": "d1", "scoring": "s1", "crawler": "c1"},
    )


# ── той самий аудит різними мовами ─────────────────────────────────────────


def test_a_finished_audit_renders_in_english_and_ukrainian_without_a_rerun():
    """Двигун тут не запускається жодного разу — і це весь сенс."""
    source = _source()

    english = build_report(source, Locale.EN)
    ukrainian = build_report(source, Locale.UK)

    assert english.issues[0].title != ukrainian.issues[0].title
    assert english.locale == "en"
    assert ukrainian.locale == "uk"


def test_changing_the_language_does_not_change_a_single_measured_fact():
    """Мова — властивість відповіді, а не аудиту.

    Якби вона впливала на бал, знахідки чи версії, історія сайту залежала
    б від того, якою мовою його дивилися, — а це вже не вимірювання.
    """
    source = _source()

    english = build_report(source, Locale.EN)
    ukrainian = build_report(source, Locale.UK)

    assert english.summary == ukrainian.summary, "жодного числа не зрушило"
    assert english.versions == ukrainian.versions
    assert [i.code for i in english.issues] == [i.code for i in ukrainian.issues]
    assert [i.severity for i in english.issues] == [i.severity for i in ukrainian.issues]
    assert [i.msg for i in english.issues] == [i.msg for i in ukrainian.issues]
    assert [i.evidence for i in english.issues] == [i.evidence for i in ukrainian.issues]


def test_the_stored_rendered_text_is_not_the_source_of_truth():
    """У знахідках лежить слово «cached» — у звіті його бути не може."""
    report = build_report(_source(), Locale.EN)
    assert all("cached" not in i.title for i in report.issues)


@pytest.mark.parametrize("locale", list(Locale))
def test_every_declared_language_produces_a_report(locale: Locale):
    """Часткова мова — теж робоча мова, просто частина рядків англійські."""
    report = build_report(_source(), locale)
    assert report.issues
    assert all(i.title for i in report.issues)


def test_an_unknown_language_falls_back_to_english_not_to_ukrainian():
    """Найдорожча помилка фолбеку: віддати читачеві третю мову."""
    japanese = build_report(_source(), Locale.JA)
    english = build_report(_source(), Locale.EN)
    ukrainian = build_report(_source(), Locale.UK)

    assert [i.title for i in japanese.issues] == [i.title for i in english.issues]
    assert [i.title for i in japanese.issues] != [i.title for i in ukrainian.issues]


def test_a_missing_translation_key_does_not_break_the_report(monkeypatch):
    """Каталог неповний навіть в англійській — це баг, але не 500."""
    monkeypatch.setitem(i18n.CATALOGS, Locale.EN, {})
    monkeypatch.setitem(i18n.CATALOGS, Locale.UK, {})

    report = build_report(_source(), Locale.EN)

    assert report.issues, "звіт зібрався"
    # Порядок знахідок задає серйозність, а не порядок у джерелі: критична
    # стоїть першою. Важливо тут інше — замість порожнечі видно ключ.
    assert {i.title for i in report.issues} == {"seo.h1.multiple", "seo.title.missing"}


# ── порядок пріоритетів ────────────────────────────────────────────────────


def test_an_explicit_request_wins_over_everything():
    resolved = resolve(requested="de", user_locale="uk", organization_locale="fr")
    assert resolved.locale is Locale.DE
    assert resolved.source == "request"


def test_the_user_wins_over_the_organization():
    resolved = resolve(requested=None, user_locale="pl", organization_locale="fr")
    assert resolved.locale is Locale.PL
    assert resolved.source == "user"


def test_the_organization_answers_when_the_user_never_chose():
    """Порожньо в користувача означає «не обирав», а не «обрав англійську».

    Різниця видима: такий користувач поїде за організацією, коли та
    змінить мову, а той, хто обрав, — ні.
    """
    resolved = resolve(requested=None, user_locale="", organization_locale="es")
    assert resolved.locale is Locale.ES
    assert resolved.source == "organization"


def test_english_answers_when_nobody_said_anything():
    resolved = resolve()
    assert resolved.locale is Locale.EN
    assert resolved.source == "default"


@pytest.mark.parametrize("broken", ["xx", "klingon", "!!", "  ", "en-GB-oed-x-nope-nope"])
def test_a_broken_language_code_means_nothing_instead_of_breaking_things(broken):
    """Зіпсований код у профілі не має робити акаунт непридатним."""
    resolved = resolve(requested=broken, user_locale="uk")
    assert resolved.locale in {Locale.UK, Locale.EN}


def test_a_region_is_dropped_rather_than_rejected():
    """`pt-BR` — це португальська, а не привід віддати англійську."""
    assert resolve(requested="pt-BR").locale is Locale.PT
    assert resolve(requested="ZH_hans").locale is Locale.ZH


def test_arabic_is_declared_right_to_left():
    """Напрямок — властивість мови, і знати його треба до верстки."""
    assert resolve(requested="ar").rtl is True
    assert resolve(requested="ar").direction == "rtl"
    assert resolve(requested="en").direction == "ltr"


# ── дві осі мови, які не можна плутати ─────────────────────────────────────


def test_the_language_of_the_product_is_not_the_language_of_the_site():
    """Іспанський сайт лишається іспанським для читача з Токіо.

    Типи різні саме заради цього: сплутані, вони змусили б продукт
    упізнавати сторінки залежно від налаштувань інтерфейсу.
    """
    from app.audit.vocab import ContentLanguage

    assert ContentLanguage is not Locale
    assert not isinstance(ContentLanguage.ES, Locale)


def test_the_vocabulary_says_out_loud_which_languages_it_covers():
    """Непокрита мова ламається тихо, тож покриття мусить бути видимим."""
    from app.audit import vocab

    covered = vocab.covered()
    assert vocab.ContentLanguage.EN in covered
    assert vocab.ContentLanguage.UK in covered
    # Шість мов запуску покриті з E-12. Підмножина, а не рівність: мова,
    # покрита пізніше, не має ламати цей тест. Він стереже нижню межу — те,
    # що ми обіцяли розуміти, — а не забороняє розуміти більше.
    launch = {
        vocab.ContentLanguage.EN,
        vocab.ContentLanguage.UK,
        vocab.ContentLanguage.DE,
        vocab.ContentLanguage.ES,
        vocab.ContentLanguage.FR,
        vocab.ContentLanguage.RU,
    }
    assert launch <= covered


def test_a_word_is_asked_about_its_meaning_not_about_its_spelling():
    """Чек питає поняття; словник вирішує, якими словами воно виражається."""
    from app.audit import vocab
    from app.audit.vocab.enums import Concept

    assert vocab.means(Concept.TELLING, "pricing")
    assert vocab.means(Concept.TELLING, "ціни")
    assert vocab.means(Concept.TELLING, "precios"), "іспанська покрита з E-12"
