"""Імʼя файлу звіту з адреси сайту мусить жити в заголовку відповіді."""

from __future__ import annotations

import pytest

from app.report.filenames import host_part


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://example.com", "example.com"),
        ("https://Example.com:8443/path?q=1", "example.com"),
        ("example.com/a/b", "example.com"),
        # Кирилиця не кодується в Latin-1: без punycode відповідь падала з 500.
        ("https://сайт.укр", "xn--80aswg.xn--j1amh"),
        # Лапка й керуючі символи ламали б сам заголовок.
        ('evil".com\r\nSet-Cookie: x=1', "evil-.com-set-cookie-x-1"),
        ("", "site"),
        ("https://", "site"),
    ],
)
def test_host_part_is_header_safe(raw: str, expected: str) -> None:
    part = host_part(raw)
    assert part == expected
    part.encode("latin-1")
    assert '"' not in part and "\r" not in part and "\n" not in part


def test_every_report_filename_goes_through_it() -> None:
    from app.report.presence_docx import filename_for as presence_filename

    assert presence_filename("https://сайт.укр/", "uk") == (
        "ai-presence-xn--80aswg.xn--j1amh-technical-uk.docx"
    )
