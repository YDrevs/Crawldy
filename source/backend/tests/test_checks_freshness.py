"""Свіжість сайту: чи оновлювали його бодай колись."""

from __future__ import annotations

from datetime import UTC, datetime

from app.audit.checks.llm_visibility import StaleContentCheck
from tests.factories import context, page_from_html


def _dated(n: int, year: int) -> object:
    return page_from_html(
        f"<html lang='uk'><head><title>Стаття номер {n} про ремонт покрівлі</title>"
        "</head><body><h1>Заголовок</h1><p>Текст статті.</p>"
        '<script type="application/ld+json">'
        f'{{"@type":"BlogPosting","dateModified":"{year}-05-1{n}"}}</script>'
        "</body></html>",
        url=f"https://example.com/blog/post-{n}",
        depth=1,
    )


def test_site_whose_newest_page_is_years_old_is_a_finding():
    ctx = context(*[_dated(n, 2019) for n in range(3)])
    issues = list(StaleContentCheck().run(ctx))
    assert len(issues) == 1
    assert issues[0].evidence["newest_date"].startswith("2019")


def test_one_recent_page_is_enough_to_stay_silent():
    """Твердження про сайт, а не про сторінку: свіже щось — уже не покинутий."""
    this_year = datetime.now(UTC).year
    ctx = context(_dated(0, 2019), _dated(1, 2019), _dated(2, this_year))
    assert not list(StaleContentCheck().run(ctx))


def test_two_dated_pages_are_not_enough_to_judge_a_site():
    ctx = context(_dated(0, 2019), _dated(1, 2019))
    assert not list(StaleContentCheck().run(ctx))


def test_a_site_without_dates_in_markup_is_not_called_stale():
    """Немає дат — немає твердження. Вигадувати вік сайту ми не беремось."""
    pages = [
        page_from_html(
            f"<html lang='uk'><head><title>Сторінка послуги номер {n}</title></head>"
            "<body><h1>Послуга</h1><p>Опис послуги.</p></body></html>",
            url=f"https://example.com/services/s-{n}",
            depth=1,
        )
        for n in range(4)
    ]
    assert not list(StaleContentCheck().run(context(*pages)))


def test_a_broken_date_string_does_not_crash_the_check():
    pages = [_dated(0, 2019), _dated(1, 2019), _dated(2, 2019)]
    broken = page_from_html(
        "<html lang='uk'><head><title>Сторінка з поламаною датою в розмітці</title>"
        "</head><body><h1>Заголовок</h1>"
        '<script type="application/ld+json">'
        '{"@type":"BlogPosting","dateModified":"позавчора"}</script></body></html>',
        url="https://example.com/blog/broken",
        depth=1,
    )
    assert list(StaleContentCheck().run(context(*pages, broken)))
