"""Чужий шаблонний вміст: коли це знахідка, а коли збіг."""

from __future__ import annotations

from app.audit.demo_content import detect
from app.audit.site_facts import SiteKnowledge
from app.audit.types import PageSignals, SiteContext


def page(url: str, title: str = "Сторінка", text: str = "") -> PageSignals:
    signals = PageSignals(url=url, status_code=200, title=title, html_bytes=20_000)
    signals.text = text or "текст " * 300
    signals.word_count = 300
    return signals


def site(*pages: PageSignals, **known) -> SiteContext:
    ctx = SiteContext(entry_url=pages[0].url, origin="https://s.com")
    ctx.pages = list(pages)
    ctx.known = SiteKnowledge(**known)
    return ctx


def test_one_signal_alone_is_not_a_finding():
    """Пошта на чужому домені буває справжньою. Один сигнал — привід
    подивитись, а не привід звинуватити."""
    found = detect(site(page("https://s.com/"), emails=["seofy@mail.com"]))

    assert found.kinds == 1


def test_signals_that_converge_are_a_finding():
    """На smartkp.com.ua зійшлися пошта на домені теми, службові сторінки
    конструктора й вісім вигаданих людей у розділі команди."""
    found = detect(site(
        page("https://s.com/", text="Ми автоматизуємо бізнес у місті Кам'янець."),
        page("https://s.com/footer/footer-home-1/"),
        page("https://s.com/team/mark-liuw/", title="Mark Liuw - Smart"),
        emails=["seofy@mail.com"],
    ))

    assert found.kinds >= 3
    assert found.template_pages and found.foreign_person_pages


def test_a_latin_site_is_not_accused_of_foreign_names():
    """Найнебезпечніше хибне спрацювання: англомовна компанія з
    англійськими іменами в команді — це норма, а не шаблон."""
    found = detect(site(
        page("https://s.com/", text="We build autonomous drone infrastructure for energy."),
        page("https://s.com/team/john-smith/", title="John Smith - Acme"),
        emails=["hello@acme.com"],
    ))

    assert found.foreign_person_pages == []


def test_an_obviously_fake_phone_counts():
    found = detect(site(page("https://s.com/"), phones=["+380 12 3456789", "+1 (555) 0000000"]))

    assert found.placeholder_contacts


def test_a_real_phone_does_not():
    found = detect(site(page("https://s.com/"), phones=["+380969105796"]))

    assert found.placeholder_contacts == []


def test_template_parts_exposed_as_pages_are_a_signal():
    found = detect(site(
        page("https://s.com/"),
        page("https://s.com/elementor/library/"),
        page("https://s.com/header/main/"),
    ))

    assert len(found.template_pages) == 2


def test_a_clean_site_gives_nothing():
    found = detect(site(
        page("https://s.com/", text="Ми ремонтуємо ноутбуки в місті Львів."),
        page("https://s.com/kontakty/"),
        emails=["office@s.com"], phones=["+380671112233"],
    ))

    assert found.kinds == 0
