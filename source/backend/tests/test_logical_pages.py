"""Логічний документ замість адреси: що зливається, а що ні."""

from __future__ import annotations

from app.audit.logical_pages import group, normalize, same_content
from app.audit.types import PageSignals


def page(url: str, title: str = "Головна", words: int = 400, canonical: str = "") -> PageSignals:
    signals = PageSignals(url=url, status_code=200, title=title, html_bytes=20_000)
    signals.word_count = words
    signals.text = "слово " * words
    signals.canonical = canonical or None
    return signals


def test_trailing_slash_is_not_a_second_page():
    """На smartkp.com.ua адреса зі слешем і без нього ставали двома
    сторінками й давали дубль title на порожньому місці."""
    pages = group([page("https://s.com"), page("https://s.com/")])

    assert len(pages) == 1
    assert pages[0].url_variants


def test_tracking_parameters_do_not_make_a_new_page():
    pages = group([
        page("https://s.com/p"),
        page("https://s.com/p?utm_source=fb&utm_campaign=x"),
    ])

    assert len(pages) == 1


def test_form_variants_collapse_into_the_canonical_page():
    """На dronehub.ai /contact?subject=License+IP та інші — це одна
    сторінка, де параметр міняє стан форми. Canonical на чистий URL тут
    правильний, і з нього виходило чотири різні претензії."""
    pages = group([
        page("https://d.ai/contact", words=300),
        page("https://d.ai/contact?subject=License", words=300, canonical="https://d.ai/contact"),
        page("https://d.ai/contact?subject=Press", words=302, canonical="https://d.ai/contact"),
    ])

    assert len(pages) == 1
    assert pages[0].url == "https://d.ai/contact"
    assert len(pages[0].url_variants) == 2


def test_canonical_to_a_different_page_stays_a_finding():
    """Найважливіша межа. Картка товару, канонізована на головну, — це
    справжня проблема, і сховати її під виглядом дедуплікації означало б
    проміняти шість хибних знахідок на одну пропущену справжню."""
    pages = group([
        page("https://s.com/", title="Магазин", words=500),
        page("https://s.com/product/x", title="Товар X", words=120,
             canonical="https://s.com/"),
    ])

    assert len(pages) == 2


def test_query_parameters_that_change_the_page_are_kept_apart():
    pages = group([
        page("https://old.ua/index?id=12", title="Сторінка 12"),
        page("https://old.ua/index?id=13", title="Сторінка 13"),
    ])

    assert len(pages) == 2


def test_parameter_order_does_not_matter():
    assert normalize("https://s.com/x?b=2&a=1") == normalize("https://s.com/x?a=1&b=2")


def test_the_canonical_address_becomes_the_representative():
    """Представник — не перший-ліпший, а та адреса, яку сайт вважає
    головною: саме вона потрапить у звіт і в llms.txt."""
    pages = group([
        page("https://s.com/p?utm_source=x", words=400),
        page("https://s.com/p", words=400),
    ])

    assert pages[0].url == "https://s.com/p"


def test_same_content_tolerates_a_few_words_of_difference():
    assert same_content(page("https://s.com/a", words=300), page("https://s.com/b", words=305))
    assert not same_content(page("https://s.com/a", words=300), page("https://s.com/b", words=80))
    assert not same_content(
        page("https://s.com/a", title="Про нас"), page("https://s.com/b", title="Контакти")
    )
