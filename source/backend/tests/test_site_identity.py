"""Що вважати одним сайтом.

Найдорожча помилка тут не хибне спрацювання, а тихе злиття: дві криві
історії, зведені в одну, розділити вже неможливо. Тому правила
синтаксичні, суворі й нудні.
"""

from __future__ import annotations

import pytest

from app.audit.fetcher import origin_of
from app.sites.identity import (
    InvalidSiteUrl,
    display_name_for,
    looks_like_the_same_site,
    normalize_origin,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://example.com", "https://example.com"),
        ("https://example.com/", "https://example.com"),
        ("https://example.com/pricing?utm=1#top", "https://example.com"),
        ("https://EXAMPLE.com", "https://example.com"),
        ("https://example.com.", "https://example.com"),
        ("https://example.com:443", "https://example.com"),
        ("http://example.com:80", "http://example.com"),
        ("https://example.com:8443", "https://example.com:8443"),
        ("example.com", "https://example.com"),
        ("  https://example.com  ", "https://example.com"),
    ],
)
def test_origin_is_scheme_and_host_and_nothing_else(raw, expected):
    assert normalize_origin(raw) == expected


def test_an_internationalised_domain_is_one_site_not_two():
    """`düsseldorf.de` і його punycode — та сама адреса, записана двома
    способами. Розділити їх означало б розділити історію."""
    assert normalize_origin("https://düsseldorf.de") == normalize_origin(
        "https://xn--dsseldorf-q9a.de"
    )


def test_http_and_https_are_different_sites():
    """Незручно навмисно.

    Тихе зведення http до https схоже на послугу рівно доти, доки два
    різні сайти на одному хості не змішають історію в одну криву.
    """
    assert normalize_origin("http://example.com") != normalize_origin("https://example.com")


def test_www_and_bare_host_are_different_sites():
    assert normalize_origin("https://www.example.com") != normalize_origin("https://example.com")


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "ftp://example.com",
        "https://",
        "not a url at all ",
        "https://exa mple.com",
        "https://-bad.com",
        "https://bad-.com",
        "https://a..b.com",
        "https://localhost:3000",
    ],
)
def test_what_cannot_be_a_site(raw):
    """`str.encode("idna")` для чисто-ASCII рядка не валідує нічого, тож
    без окремої перевірки «not a url at all» ставало сайтом із пробілами
    в хості. Односкладовий хост теж не приймаємо: продукт аудитує сайти в
    інтернеті, і помилку краще показати одразу, а не через дві хвилини
    рядком «DNS не резолвиться» у звіті."""
    with pytest.raises(InvalidSiteUrl):
        normalize_origin(raw)


@pytest.mark.parametrize(
    "raw",
    ["https://has_underscore.example.com", "https://192.0.2.10", "https://xn--80ak6aa92e.com"],
)
def test_what_is_unusual_but_real(raw):
    """Бути суворішими за реальність означає відмовляти клієнтам через
    букву. Підкреслення в піддоменах трапляється, IP-літерал теж буває."""
    assert normalize_origin(raw)


def test_the_default_name_drops_www_because_it_is_only_a_label():
    """У підписі `www.` прибрати можна: це напис для людини, а не
    ідентичність."""
    assert display_name_for("https://www.example.com") == "example.com"
    assert display_name_for("https://shop.example.com") == "shop.example.com"


def test_similarity_is_a_hint_not_an_identity():
    """`looks_like_the_same_site` існує, щоб запитати людину, і тільки.

    Підказка має право помилятися; ідентичність не має.
    """
    assert looks_like_the_same_site("https://example.com", "https://www.example.com")
    assert looks_like_the_same_site("http://example.com", "https://example.com")
    assert not looks_like_the_same_site("https://example.com", "https://example.org")
    assert not looks_like_the_same_site("https://shop.example.com", "https://example.com")


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/",
        "https://example.com/pricing",
        "http://sub.example.com/a/b?c=d",
    ],
)
def test_sites_and_crawler_agree_on_simple_cases(url):
    """Дві нормалізації існують окремо — але не мають розходитися дарма.

    `audit.fetcher.origin_of` служить краулеру й може змінитися разом із
    ним; `sites.normalize_origin` визначає, до якого сайту належить
    історія. Розділені вони саме тому, що зміна правил краулу не повинна
    розділяти чиюсь історію надвоє. Але на звичайних адресах вони мусять
    давати те саме, інакше сайт і його аудити опиняться в різних місцях.
    """
    assert normalize_origin(url) == origin_of(url)
