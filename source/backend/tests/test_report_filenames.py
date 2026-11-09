"""Імʼя файлу з хоста клієнта не ламає `Content-Disposition`."""

from __future__ import annotations

import re

import pytest

from app.report.filenames import host_part, safe_part

SAFE = re.compile(r"^[A-Za-z0-9._-]+$")

HOSTILE = [
    'https://evil".com/',
    "https://a.com\r\nSet-Cookie: x=1",
    "https://ціна.укр/",
    "https://a.com/../../etc",
    "",
]


@pytest.mark.parametrize("raw", HOSTILE)
def test_host_part_is_always_header_safe(raw: str) -> None:
    assert SAFE.match(host_part(raw))


def test_an_ordinary_host_is_kept() -> None:
    assert host_part("https://www.example.com/path") == "www.example.com"


def test_empty_falls_back() -> None:
    assert safe_part("", "audit") == "audit"
    assert safe_part('""', "audit") == "audit"


@pytest.mark.parametrize("raw", HOSTILE)
def test_every_report_filename_is_header_safe(raw: str) -> None:
    from types import SimpleNamespace

    from app.audit.i18n import Locale
    from app.report import docx, docx_owner, presence_docx

    report = SimpleNamespace(target={"origin": raw})
    for name in (
        docx.filename_for(report, Locale.UK),  # type: ignore[arg-type]
        docx_owner.filename_for(report, Locale.UK),  # type: ignore[arg-type]
        presence_docx.filename_for(raw, "uk"),
    ):
        assert SAFE.match(name), name
