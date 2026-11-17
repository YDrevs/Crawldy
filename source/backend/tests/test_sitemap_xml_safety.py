"""Карту сайту пише чужий сервер — розбираємо її без розкриття сутностей.

Stdlib `ElementTree` розкриває внутрішні сутності: «billion laughs» на
кількох кілобайтах роздуває памʼять воркера до гігабайтів. Така карта —
це помилка розбору, а не привід падати.
"""

from __future__ import annotations

from xml.etree import ElementTree

import pytest

from app.audit.site_context import _parse_sitemap

BOMB = """<?xml version="1.0"?>
<!DOCTYPE lolz [
 <!ENTITY lol "lol">
 <!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">
 <!ENTITY lol3 "&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;&lol2;">
]>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>&lol3;</loc></url></urlset>"""

EXTERNAL = """<?xml version="1.0"?>
<!DOCTYPE x [<!ENTITY ext SYSTEM "file:///etc/passwd">]>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>&ext;</loc></url></urlset>"""


@pytest.mark.parametrize("xml", [BOMB, EXTERNAL])
def test_entity_tricks_are_a_parse_error(xml: str) -> None:
    with pytest.raises(ElementTree.ParseError):
        _parse_sitemap(xml)


def test_an_ordinary_sitemap_still_parses() -> None:
    parsed = _parse_sitemap(
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        "<url><loc>https://example.com/a</loc></url></urlset>"
    )
    assert list(parsed.pages) == ["https://example.com/a"]
