"""Факти сайту, зведені з розмітки й посилань, а не з висновку моделі."""

from __future__ import annotations

from app.audit.site_facts import collect
from app.audit.types import PageSignals, SiteContext


def page(url: str = "https://s.com/", **kwargs) -> PageSignals:
    signals = PageSignals(url=url, status_code=200, html_bytes=20_000, title="Сторінка")
    signals.word_count = 400
    signals.text = kwargs.pop("text", "слово " * 400)
    for name, value in kwargs.items():
        setattr(signals, name, value)
    return signals


def ctx(*pages: PageSignals) -> SiteContext:
    site = SiteContext(entry_url="https://s.com/", origin="https://s.com")
    site.pages = list(pages)
    return site


def test_city_from_a_meta_description_counts_as_knowing_where_you_are():
    """Той самий звіт стверджував «ніде не вказано, де ви працюєте» і
    містив у згенерованому нами ж llms.txt «у місті Кам'янець-Подільський».
    Місто лежало в мета-описі — ми його бачили, просто питали не там."""
    known = collect(ctx(page(meta_description="Відеоспостереження в місті Кам'янець-Подільський.")))

    assert known.cities == ["Кам'янець-Подільський"]
    assert known.has_location


def test_city_in_english_form_is_found_too():
    known = collect(ctx(page(text="We install CCTV in Tyler, TX and nearby towns.")))

    assert "Tyler" in known.cities


def test_address_from_schema_counts_as_location():
    known = collect(ctx(page(jsonld=[{
        "@type": "LocalBusiness",
        "address": {"@type": "PostalAddress", "streetAddress": "вул. Коріатовичів 25",
                    "addressLocality": "Кам'янець-Подільський"},
    }])))

    assert known.addresses and known.has_location
    assert "Кам'янець-Подільський" in known.cities


def test_a_capital_letter_alone_is_not_a_city():
    """Інакше кожне друге слово речення стає адресою, і чек про місто
    перестане спрацьовувати навіть там, де міста справді немає."""
    known = collect(ctx(page(text="Компанія Смарт пропонує BAS Бухгалтерія та MEDoc.")))

    assert known.cities == []


def test_contacts_come_from_links_and_from_schema():
    known = collect(ctx(
        page(tel_links=["+380441234567"], mailto_addresses=["office@s.com"]),
        page("https://s.com/x", jsonld=[{"@type": "Organization", "telephone": "+380509999999",
                                        "name": "Смарт"}]),
    ))

    assert known.has_contact
    assert len(known.phones) == 2
    assert known.organization == "Смарт"


def test_every_fact_says_where_it_came_from():
    """Твердження «це у вас є» спростовує знахідку моделі, тож воно саме
    має бути перевірним."""
    known = collect(ctx(page(tel_links=["+380441234567"])))

    assert "https://s.com/" in known.sources["+380441234567"]


def test_schema_coverage_is_a_share_not_a_yes_or_no():
    known = collect(ctx(
        page(jsonld=[{"@type": "Organization"}]),
        page("https://s.com/a"),
        page("https://s.com/b"),
        page("https://s.com/c"),
    ))

    assert known.pages_with_schema == 1
    assert known.pages_total == 4
    assert known.schema_coverage == 0.25
