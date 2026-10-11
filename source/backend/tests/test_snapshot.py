"""Знімок зібраного: чи можна перерахувати аудит, не краулячи сайт заново."""

from __future__ import annotations

import json

from app.audit import snapshot
from app.audit.orchestrator import rescore
from app.audit.types import RenderResult
from tests.factories import context, page_from_html
from tests.test_i18n import _rich_context, _tech_context


def _roundtrip(ctx):
    """Через JSON навмисно: у базі знімок лежатиме саме так."""
    return snapshot.load(json.loads(json.dumps(snapshot.dump(ctx), default=str)))


def test_pages_survive_the_roundtrip_with_links_and_markup():
    """Саме цього бракувало `to_json`: посилання, розмітка й текст."""
    page = page_from_html(
        "<html lang='uk'><head><title>Сторінка про ремонт покрівлі</title></head>"
        "<body><h1>Ремонт</h1><p>Текст сторінки.</p>"
        "<nav><a href='/about'>Про нас</a></nav>"
        "<a href='/contacts/'>Контакти</a><a href='tel:+380441234567'>Дзвоніть</a>"
        '<script type="application/ld+json">{"@type":"Service","name":"Ремонт"}</script>'
        "</body></html>"
    )
    back = _roundtrip(context(page)).pages[0]
    assert [link.url for link in back.links] == [link.url for link in page.links]
    assert [link.in_chrome for link in back.links] == [link.in_chrome for link in page.links]
    assert back.jsonld == page.jsonld
    assert back.text == page.text
    assert back.tel_links == page.tel_links
    assert back.body_contacts == page.body_contacts


def test_rescoring_a_snapshot_gives_the_same_findings():
    """Головний інваріант: перерахунок без мережі не змінює висновків."""
    before = rescore(_rich_context())
    after = rescore(_roundtrip(_rich_context()))
    assert _keys(before) == _keys(after)
    assert before.scores == after.scores
    assert before.overall == after.overall


def test_rescoring_a_technical_snapshot_gives_the_same_findings():
    """Другий контекст: заголовки відповіді, форми, зовнішні хости."""
    before = rescore(_tech_context())
    after = rescore(_roundtrip(_tech_context()))
    assert _keys(before) == _keys(after)
    assert before.scores == after.scores


def _keys(outcome) -> set:
    return {(issue.msg, issue.page_url, issue.severity) for issue in outcome.issues}


def test_performance_measurements_survive():
    ctx = _rich_context()
    back = _roundtrip(ctx)
    assert back.performance[0].lab["LCP"].value == ctx.performance[0].lab["LCP"].value
    assert back.performance[0].strategy is ctx.performance[0].strategy


def test_rendered_signals_survive_but_html_does_not():
    """Розмітку не зберігаємо: чеки читають сигнали, а не HTML."""
    page = page_from_html(
        "<html lang='uk'><head><title>Сторінка з рендером для перевірки</title></head>"
        "<body><h1>Заголовок</h1><p>Текст.</p></body></html>"
    )
    ctx = context(page)
    ctx.renders[page.url] = RenderResult(
        url=page.url, rendered=True, html="<html>довга розмітка</html>", signals=page
    )
    back = _roundtrip(ctx)
    assert back.renders[page.url].rendered is True
    assert back.renders[page.url].signals.title == page.title
    assert back.renders[page.url].html == ""


def test_a_snapshot_from_an_older_schema_still_opens():
    """Нове поле не має робити непридатним усе, збережене раніше."""
    data = snapshot.dump(context(page_from_html("<html><body><h1>x</h1></body></html>")))
    data["pages"][0]["a_field_from_the_future"] = 42
    data["robots"]["another_one"] = "..."
    back = snapshot.load(data)
    assert len(back.pages) == 1


def test_a_snapshot_is_plain_json_without_a_stringifying_fallback():
    """Знімок мусить серіалізуватися без `default=str`.

    Той аргумент рятує від падіння й тим ховає помилку: `RobotsInfo.parsed`
    став рядком «RobotsFile(groups=[...])», знімок зберігся без скарг, а
    впав уже перерахунок — `evaluate` на рядку. Тест навмисно кличе
    `json.dumps` без запобіжника: обʼєкт, якому немає місця в JSON, має
    падати тут, а не на живих даних.
    """
    import json

    from app.audit import robots as robots_rfc
    from app.audit.types import RobotsInfo

    content = "User-agent: *\nDisallow: /admin\nSitemap: https://example.com/sitemap.xml\n"
    info = RobotsInfo(exists=True, status_code=200, content=content)
    info.parsed = robots_rfc.parse(content)
    ctx = context(_rich_context().pages[0], robots=info)

    raw = json.dumps(snapshot.dump(ctx), ensure_ascii=False)
    restored = snapshot.load(json.loads(raw))
    # Розібране повертається обʼєктом, а не рядком, і відповідає на питання.
    assert restored.robots.parsed.evaluate("*", "/admin").allowed is False
    assert restored.robots.parsed.evaluate("*", "/pricing").allowed is True
