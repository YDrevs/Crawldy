"""Відповідь сервера проти відрендереного DOM: порівняння й знахідка.

Усе тут проходить справжнім шляхом: HTML розбирається тим самим
екстрактором, що в проді, порівняння робить `render_diff`, знахідку
віддає зареєстрований чек. Підміняти будь-що з цього означало б
перевіряти власну підміну — а перевіряється саме семантика.

Одна пастка, на яку варто зважати, читаючи ці тести: фабрика
`page_from_html` завжди бере origin `https://example.com`. Якщо дати
сторінці іншу адресу, її посилання стануть зовнішніми, а відрендереної
версії — внутрішніми, і порівняння покаже різницю, якої немає. Тому
адреса тут одна на весь файл.
"""

from __future__ import annotations

import importlib

import pytest

from app.audit.checks.seo import RenderDeltaCheck
from app.audit.extractor import signals_from_html
from app.audit.i18n import CATALOGS, COMPLETE_LOCALES
from app.audit.render_diff import DeltaKind, compare
from app.audit.types import RenderResult
from tests.factories import context, page_from_html

ORIGIN = "https://example.com"
URL = ORIGIN + "/"

BASE = (
    "<html><head><title>Server title</title></head>"
    '<body><h1>Server heading</h1><a href="/a">a</a><p>text</p></body></html>'
)


def _rendered(html: str, *, url: str = URL) -> RenderResult:
    result = RenderResult(url=url, rendered=True, html=html)
    result.signals = signals_from_html(url, html, origin=ORIGIN, depth=0)
    return result


def _diff(response_html: str, rendered_html: str):
    page = page_from_html(response_html, url=URL, depth=0)
    return compare(page, _rendered(rendered_html))


def _issues(response_html: str, rendered_html: str) -> list:
    page = page_from_html(response_html, url=URL, depth=0)
    ctx = context(page)
    ctx.renders[page.url] = _rendered(rendered_html)
    return list(RenderDeltaCheck().run(ctx))


# ── 1. однакові сторінки ───────────────────────────────────────────────────


def test_identical_response_and_dom_produce_no_differential():
    diff = _diff(BASE, BASE)
    assert diff.comparable is True
    assert diff.changed is False
    assert diff.fields == ()
    assert not diff.links.changed
    assert _issues(BASE, BASE) == []


# ── 2–7. поля, і напрямок зміни ────────────────────────────────────────────


def test_a_title_that_appears_only_after_rendering_is_added():
    diff = _diff(BASE.replace("<title>Server title</title>", ""), BASE)
    delta = diff.get("title")
    assert delta is not None
    assert delta.kind is DeltaKind.ADDED
    assert delta.before is None
    assert delta.after == "Server title"


def test_a_title_that_differs_is_changed_and_keeps_both_values():
    diff = _diff(BASE, BASE.replace("Server title", "Client title"))
    delta = diff.get("title")
    assert delta is not None
    assert delta.kind is DeltaKind.CHANGED
    assert delta.before == "Server title"
    assert delta.after == "Client title"


def test_a_canonical_rewritten_by_script_is_reported_with_both_urls():
    before = BASE.replace("<head>", '<head><link rel="canonical" href="/one">')
    after = BASE.replace("<head>", '<head><link rel="canonical" href="/two">')
    delta = _diff(before, after).get("canonical")
    assert delta is not None
    assert delta.kind is DeltaKind.CHANGED
    assert delta.before.endswith("/one")
    assert delta.after.endswith("/two")


def test_index_becoming_noindex_after_render_is_visible():
    """Найгостріший випадок: сервер дозволяє індексацію, скрипт забороняє."""
    after = BASE.replace("<head>", '<head><meta name="robots" content="noindex, follow">')
    delta = _diff(BASE, after).get("meta_robots")
    assert delta is not None
    assert delta.kind is DeltaKind.ADDED
    assert "noindex" in delta.after


def test_noindex_becoming_index_after_render_is_the_opposite_direction():
    """Протилежний напрямок — інша історія, і він мусить бути видимим окремо."""
    before = BASE.replace("<head>", '<head><meta name="robots" content="noindex">')
    delta = _diff(before, BASE).get("meta_robots")
    assert delta is not None
    assert delta.kind is DeltaKind.REMOVED
    assert "noindex" in delta.before
    assert delta.after is None


def test_an_h1_that_exists_only_after_rendering():
    without = BASE.replace("<h1>Server heading</h1>", "")
    delta = _diff(without, BASE).get("h1")
    assert delta is not None
    assert delta.kind is DeltaKind.ADDED
    assert delta.after == "Server heading"


# ── 8–9. структурована розмітка ────────────────────────────────────────────

SCHEMA = '<script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>'


def test_structured_data_appearing_only_after_render_is_reported():
    delta = _diff(BASE, BASE.replace("</head>", SCHEMA + "</head>")).get("jsonld")
    assert delta is not None
    assert delta.kind is DeltaKind.ADDED
    assert "Organization" in delta.after


def test_structured_data_removed_after_render_is_reported():
    delta = _diff(BASE.replace("</head>", SCHEMA + "</head>"), BASE).get("jsonld")
    assert delta is not None
    assert delta.kind is DeltaKind.REMOVED


def test_reformatted_structured_data_is_not_a_semantic_change():
    """Порядок ключів і пробіли — це запис, а не зміст."""
    reordered = (
        '<script type="application/ld+json">{ "name" : "Acme" ,\n'
        '  "@type"  :  "Organization" }</script>'
    )
    diff = _diff(BASE.replace("</head>", SCHEMA + "</head>"),
                 BASE.replace("</head>", reordered + "</head>"))
    assert diff.get("jsonld") is None
    assert diff.changed is False


def test_a_changed_entity_type_is_a_semantic_change():
    other = SCHEMA.replace("Organization", "LocalBusiness")
    delta = _diff(BASE.replace("</head>", SCHEMA + "</head>"),
                  BASE.replace("</head>", other + "</head>")).get("jsonld")
    assert delta is not None
    assert delta.kind is DeltaKind.CHANGED


# ── 10–12. внутрішні посилання ─────────────────────────────────────────────

TWO_LINKS = BASE.replace('<a href="/a">a</a>', '<a href="/a">a</a><a href="/b">b</a>')


def test_a_link_that_exists_only_after_rendering_is_recorded():
    diff = _diff(BASE, TWO_LINKS)
    assert diff.links.only_after_render == (ORIGIN + "/b",)
    assert diff.links.only_in_response == ()


def test_a_link_that_exists_only_in_the_response_is_recorded_separately():
    diff = _diff(TWO_LINKS, BASE)
    assert diff.links.only_in_response == (ORIGIN + "/b",)
    assert diff.links.only_after_render == ()


def test_link_order_alone_is_not_a_difference():
    reordered = BASE.replace('<a href="/a">a</a>', '<a href="/b">b</a><a href="/a">a</a>')
    diff = _diff(TWO_LINKS, reordered)
    assert not diff.links.changed
    assert diff.changed is False


# ── 13. шум нормалізації ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("before", "after", "why"),
    [
        (
            BASE,
            BASE.replace("<title>Server title</title>", "<title>  Server   title  </title>"),
            "зайві пробіли в заголовку",
        ),
        (
            BASE.replace("<head>", '<head><link rel="canonical" href="/a">'),
            BASE.replace("<head>", '<head><link rel="canonical" href="/a/">'),
            "кінцева скіса в адресі",
        ),
        (
            BASE.replace("<head>", '<head><meta name="robots" content="noindex, follow">'),
            BASE.replace("<head>", '<head><meta name="robots" content="FOLLOW,noindex">'),
            "порядок і регістр директив",
        ),
    ],
)
def test_normalisation_noise_does_not_create_a_difference(before, after, why):
    assert _diff(before, after).changed is False, why


# ── 14–15. невизначеність рендеру ──────────────────────────────────────────


def _ctx_with(result: RenderResult | None):
    page = page_from_html(BASE, url=URL, depth=0)
    ctx = context(page)
    if result is not None:
        ctx.renders[page.url] = result
    return ctx, page


@pytest.mark.parametrize(
    ("result", "expected_reason"),
    [
        (RenderResult(url=URL, rendered=False, disabled=True, error="off"), "render.disabled"),
        (RenderResult(url=URL, rendered=False, error="playwright missing"), "render.failed"),
        (RenderResult(url=URL, rendered=False, error="timeout"), "render.failed"),
        (RenderResult(url=URL, rendered=True, html="<html></html>"), "render.no_signals"),
    ],
)
def test_a_render_that_did_not_happen_is_not_a_difference(result, expected_reason):
    """«Рендер не вдався» — не те саме, що «сторінка без JS повноцінна».

    Найдорожча можлива помилка цього модуля: перетворити власний збій на
    твердження про сайт клієнта.
    """
    ctx, page = _ctx_with(result)
    diff = compare(page, ctx.renders.get(page.url))

    assert diff.comparable is False
    assert diff.changed is False
    assert diff.reason == expected_reason
    assert diff.as_evidence()["not_compared_because"] == expected_reason
    assert list(RenderDeltaCheck().run(ctx)) == []


def test_a_page_that_was_never_rendered_yields_nothing():
    ctx, page = _ctx_with(None)
    assert compare(page, None).reason == "render.not_attempted"
    assert list(RenderDeltaCheck().run(ctx)) == []


def test_a_failed_response_is_not_compared():
    page = page_from_html(BASE, url=URL, depth=0)
    page.status_code = 500
    assert compare(page, _rendered(BASE)).reason == "response.not_ok"


# ── знахідка: групування й пріоритет ───────────────────────────────────────


def test_indexing_signals_outrank_everything_else_in_the_headline():
    after = BASE.replace("<head>", '<head><meta name="robots" content="noindex">').replace(
        "Server title", "Client title"
    )
    issues = _issues(BASE, after)
    assert len(issues) == 1
    assert issues[0].msg == "seo.render_delta.indexing"
    # Але зміна заголовка не зникає — вона в доказі.
    assert "title" in issues[0].evidence["fields_changed"]


def test_a_links_only_difference_is_reported_as_links():
    issues = _issues(BASE, TWO_LINKS)
    assert len(issues) == 1
    assert issues[0].msg == "seo.render_delta.links"
    assert issues[0].params["count"] == 1


def test_the_finding_never_costs_the_customer_a_point():
    """Скоринг заморожений: знахідка інформаційна, штраф рівно нуль."""
    from app.audit.scoring import penalty

    issues = _issues(BASE, TWO_LINKS)
    assert issues and all(penalty(i) == 0 for i in issues)
    assert RenderDeltaCheck.weight == 0
    assert RenderDeltaCheck.severity.value == "info"


# ── 18. знімок дає той самий результат без повторного рендеру ──────────────


def test_a_snapshot_replay_reproduces_the_differential_without_rendering():
    """Перерахунок за знімком не має потребувати браузера.

    Знімок уже несе обидва набори сигналів; якби ні, порівняння на
    збереженому аудиті було б неможливе, і кожна зміна правил вимагала б
    повторного краулу з рендером.
    """
    from app.audit import snapshot

    page = page_from_html(BASE, url=URL, depth=0)
    ctx = context(page)
    ctx.renders[page.url] = _rendered(BASE.replace("Server title", "Client title"))

    live = compare(page, ctx.renders[page.url])
    restored = snapshot.load(snapshot.dump(ctx))
    replayed = compare(restored.pages[0], restored.renders[URL])

    assert replayed.comparable is True
    assert replayed.field_names() == live.field_names() == ("title",)
    assert replayed.get("title").after == "Client title"
    # HTML у знімку не зберігається — порівняння працює на сигналах.
    assert restored.renders[URL].html == ""


# ── 16. повнота мов звіту ──────────────────────────────────────────────────

KEYS = (
    "seo.render_delta.indexing",
    "seo.render_delta.identity",
    "seo.render_delta.markup",
    "seo.render_delta.links",
)


@pytest.mark.parametrize("key", KEYS)
def test_every_report_locale_carries_the_message(key: str):
    missing = [
        f"{locale.value}/{field}"
        for locale in COMPLETE_LOCALES
        for field in ("title", "description", "recommendation", "consequence")
        if not (CATALOGS[locale].get(key) or {}).get(field)
    ]
    assert not missing, f"немає рядків: {missing}"


@pytest.mark.parametrize("key", KEYS)
def test_no_locale_silently_borrows_english(key: str):
    from app.audit.i18n import Locale

    english = CATALOGS[Locale.EN][key]
    borrowed = [
        f"{locale.value}/{field}"
        for locale in COMPLETE_LOCALES
        if locale is not Locale.EN
        for field in ("title", "description", "recommendation", "consequence")
        if CATALOGS[locale][key][field] == english[field]
    ]
    assert not borrowed, f"англійський рядок у неанглійському каталозі: {borrowed}"


def test_the_wording_never_claims_google_ignores_the_rendered_signal():
    """Межа тлумачення: ми описуємо факт, а не поведінку Google.

    Google рендерить — його ж документація це каже, — просто відкладено.
    Стверджувати «Google це проігнорує» або «позиції впадуть» означало б
    вигадати причинність, якої ми не міряли.
    """
    forbidden = (
        "google ignores", "google will not", "google cannot see",
        "rankings will drop", "hurts your ranking", "penalis", "penaliz",
        "google проігнорує", "позиції впадуть", "google не побачить",
        "google ignoriert", "google ignora", "google ignore",
        "google проигнорирует", "позиции упадут",
    )
    offenders = [
        f"{locale.value}/{key}: {phrase}"
        for locale in COMPLETE_LOCALES
        for key in KEYS
        for field in ("title", "description", "recommendation", "consequence")
        for phrase in forbidden
        if phrase in CATALOGS[locale][key][field].lower()
    ]
    assert not offenders, f"вигадана поведінка пошуку: {offenders}"


def test_the_english_wording_quotes_what_google_actually_documents():
    """Твердження про чергу рендеру спирається на цитату, а не на памʼять."""
    from app.audit.i18n import Locale

    indexing = CATALOGS[Locale.EN]["seo.render_delta.indexing"]["description"]
    assert "can take longer" in indexing
    assert "not all bots can run JavaScript" in indexing


def test_every_locale_module_exposes_all_four_keys():
    for loc in ("en", "uk", "de", "es", "fr", "ru"):
        messages = importlib.import_module(f"app.audit.i18n.{loc}").MESSAGES
        present = {k for k in messages if k.startswith("seo.render_delta")}
        assert present == set(KEYS), loc
