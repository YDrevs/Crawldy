"""Факти прогону присутності — з того, що аудит прочитав.

Перевіряється саме те, через що ця логіка існує: клініку з
Кам'янця-Подільського не сміють питати про Київ, бренд береться словом,
а не всім заголовком, варіанти написання покривають кирилицю й латиницю,
а порожнє джерело дає порожнє поле, а не вигадку.
"""

from __future__ import annotations

import pytest

from app.presence.derive import derive, domain_label, transliterate

KA_DENT_TITLE = "Стоматологічна клініка Ка-Дент — Кам'янець-Подільский"


def test_ka_dent_gets_its_own_city_brand_and_category():
    facts = derive(
        origin="https://ka-dent.com.ua",
        home_title=KA_DENT_TITLE,
        cities=("Кам'янець-Подільський",),
        schema_types={"Organization": 10},
        lang="uk",
    )
    assert facts.brand == "Ка-Дент"
    assert facts.category == "стоматологічна клініка"
    assert facts.location == "Кам'янець-Подільський"
    assert facts.language == "uk"
    assert facts.sources == {"brand": "title", "category": "title", "location": "site"}


def test_aliases_cover_cyrillic_latin_hyphen_and_space():
    facts = derive(origin="https://ka-dent.com.ua", home_title=KA_DENT_TITLE, lang="uk")
    assert facts.brand_aliases == (
        "Ка-Дент", "Ка Дент", "КаДент", "Ka-Dent", "Ka Dent", "KaDent",
    )


def test_aliases_do_not_repeat_in_another_case():
    facts = derive(origin="https://smartkp.com.ua", home_title="SmartKP — безпека",
                   organization="SmartKP", lang="uk")
    assert facts.brand_aliases == ("SmartKP",)


def test_organization_from_schema_beats_the_title():
    facts = derive(
        origin="https://smartkp.com.ua",
        home_title="SmartKP — відеоспостереження та безпека",
        organization="СмартКП",
        lang="uk",
    )
    assert facts.brand == "СмартКП"
    assert facts.sources["brand"] == "schema"
    assert facts.category == "відеоспостереження та безпека"
    # Написання з заголовка — серед варіантів збігу, не в категорії.
    assert "SmartKP" in facts.brand_aliases
    assert "SmartKP" not in facts.category


def test_business_type_from_schema_beats_the_title():
    facts = derive(
        origin="https://crustula.com.ua",
        home_title="Крустула | Пекарня у Львові",
        cities=("Львів",),
        schema_types={"Bakery": 3},
        lang="uk",
    )
    assert facts.category == "пекарня"
    assert facts.sources["category"] == "schema"
    assert facts.location == "Львів"
    # Бренд із домену: у заголовку немає слова, схожого на «crustula».
    assert facts.brand == "Crustula"
    assert facts.sources["brand"] == "domain"


def test_city_segment_is_not_mistaken_for_the_category_despite_a_typo():
    # Заголовок пише «Подільский», розмітка — «Подільський».
    facts = derive(
        origin="https://ka-dent.com.ua",
        home_title="Ка-Дент — Кам'янець-Подільский",
        cities=("Кам'янець-Подільський",),
        lang="uk",
    )
    assert facts.category == ""


def test_generic_title_words_do_not_become_a_category():
    facts = derive(origin="https://www.python.org", home_title="Welcome to Python.org", lang="en")
    assert facts.brand == "Python.org"
    assert facts.category == ""
    assert facts.location is None


def test_nothing_known_gives_empty_fields_not_guesses():
    facts = derive(origin="https://example.com", home_title="", lang="")
    assert facts.brand == "Example"
    assert facts.sources == {"brand": "domain"}
    assert facts.category == ""
    assert facts.location is None
    assert facts.language == "en"


def test_english_business_type_names_follow_the_page_language():
    facts = derive(origin="https://smile.example", home_title="Smile Dental",
                   schema_types={"Dentist": 2}, lang="en-US")
    assert facts.category == "dental clinic"
    assert facts.language == "en"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Ка-Дент", "Ka-Dent"),
        ("Юлія", "Yuliia"),
        ("Щастя", "Shchastia"),
        ("Їжак", "Yizhak"),
        ("Львів", "Lviv"),
        ("SmartKP 2026", "SmartKP 2026"),
    ],
)
def test_transliteration_follows_the_official_table(text: str, expected: str):
    assert transliterate(text) == expected


def test_domain_label_drops_www_and_suffix():
    assert domain_label("https://www.ka-dent.com.ua/") == "ka-dent"
    assert domain_label("https://python.org") == "python"
    assert domain_label("garbage") == "garbage"


def test_umlauts_and_accents_still_find_the_brand_in_the_title():
    # Домен пишеться без умлаутів і наголосів, заголовок — з ними.
    german = derive(origin="https://zahnarzt-mueller.de",
                    home_title="Zahnarzt Müller — Ihre Zahnarztpraxis in Berlin",
                    cities=("Berlin",), schema_types={"Dentist": 3}, lang="de")
    assert german.brand == "Zahnarzt Müller"
    assert german.category == "dental clinic"
    assert german.location == "Berlin"
    spanish = derive(origin="https://clinicasol.es",
                     home_title="Clínica Sol | Dentista en Valencia", lang="es")
    assert spanish.brand == "Clínica Sol"


def test_prompt_language_is_ukrainian_or_english_only():
    # Промпти присутності існують двома мовами; решта сайтів питаються
    # англійською, і назви категорій із розмітки теж англійські.
    assert derive(origin="https://x.de", home_title="X", lang="de").language == "en"
    assert derive(origin="https://x.ua", home_title="X", lang="uk-UA").language == "uk"

