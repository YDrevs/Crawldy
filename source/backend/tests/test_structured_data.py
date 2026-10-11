"""Структуровані дані: чесна відсутність, визнані формати, нуль штрафу.

Затверджена політика (гілка B — RDFa зі знімків не відновлюється):
відсутність — INFO/0 із явним «RDFa не оцінювався»; часткове покриття —
не вада; сутність ідентичності — інформаційна можливість, що визнає
підтипи Organization, Person, WebSite, вкладені вузли, регістр і
about-сторінки, і мовчить, коли кореневої розмітки немає взагалі.
"""

from __future__ import annotations

import pytest

from app.audit import about_page
from app.audit.checks.ai_ready import (
    JsonLdPresenceCheck,
    OrganizationSchemaCheck,
    types_on,
)
from app.audit.enums import Module
from app.audit.scoring import module_score
from app.audit.standards.schema_entities import (
    IDENTITY_TYPES,
    is_identity_type,
    registry_problems,
)
from tests.factories import context, page_from_html

PLAIN = "<html><body><main>слова про сайт і ще слова</main></body></html>"


def _jsonld(payload: str, url: str = "https://example.com/") -> object:
    return page_from_html(
        f'<html><head><script type="application/ld+json">{payload}</script>'
        f"</head><body><main>текст</main></body></html>",
        url=url,
    )


def _score(issues) -> int:
    return module_score(list(issues), Module.AI_READY)


# ── відсутність: лише коли дивилися й не знайшли ──────────────────────


def test_no_eligible_pages_is_silent() -> None:
    assert list(JsonLdPresenceCheck().run(context())) == []


def test_jsonld_present_means_no_absence_finding() -> None:
    ctx = context(_jsonld('{"@type": "WebSite", "name": "x"}'))
    assert list(JsonLdPresenceCheck().run(ctx)) == []


def test_microdata_present_means_no_absence_finding() -> None:
    """Google підтримує три формати. Microdata — валідна розмітка, і
    «структурованих даних немає» поруч із нею було б неправдою: на
    night3 таких сайтів 136."""
    page = page_from_html(PLAIN)
    page.microdata_types = ["Organization", "PostalAddress"]
    assert list(JsonLdPresenceCheck().run(context(page))) == []


def test_total_absence_is_info_zero_and_names_rdfa_as_unassessed() -> None:
    """Гілка B: RDFa зі збережених сторінок не відновлюється, тож і
    твердження обмежене, і штраф нульовий."""
    issues = list(JsonLdPresenceCheck().run(context(page_from_html(PLAIN))))
    assert len(issues) == 1
    issue = issues[0]
    assert issue.severity.value == "info"
    assert issue.evidence["rdfa_assessed"] is False
    assert issue.evidence["microdata_found"] == 0
    assert _score(issues) == 100, "штраф нуль"


def test_partial_coverage_produces_no_problem() -> None:
    covered = _jsonld('{"@type": "Organization", "name": "Acme"}')
    bare = page_from_html(PLAIN, url="https://example.com/b")
    assert list(JsonLdPresenceCheck().run(context(covered, bare))) == []


def test_malformed_jsonld_yields_invalid_only_not_missing() -> None:
    """Зіпсована спроба — не відсутність: корінь один, ключ один."""
    page = page_from_html(PLAIN)
    page.jsonld_errors = ["line 1: Expecting value"]
    assert list(JsonLdPresenceCheck().run(context(page))) == []


# ── сутність ідентичності ─────────────────────────────────────────────


def _org_ctx(payload: str):
    return context(_jsonld(payload))


def test_organization_absent_with_other_markup_is_info_zero() -> None:
    issues = list(OrganizationSchemaCheck().run(
        _org_ctx('{"@type": "Article", "headline": "x"}')
    ))
    assert len(issues) == 1
    assert issues[0].severity.value == "info"
    assert _score(issues) == 100, "AI_READY не штрафується"


def test_root_absence_suppresses_the_entity_finding() -> None:
    """Розмітки немає взагалі — про це вже сказав кореневий чек.

    Два ключі за один корінь — подвійний штраф: 544 сайти night3.
    """
    ctx = context(page_from_html(PLAIN))
    assert list(OrganizationSchemaCheck().run(ctx)) == []


def test_organization_descendants_are_accepted() -> None:
    """Google рекомендує найконкретніший підтип — і його не можна карати."""
    for subtype in ("AutoDealer", "FastFoodRestaurant", "AmusementPark",
                    "ShoppingCenter", "NewsMediaOrganization",
                    "EducationalOrganization", "OnlineStore", "Corporation"):
        ctx = _org_ctx(f'{{"@type": "{subtype}", "name": "x"}}')
        assert list(OrganizationSchemaCheck().run(ctx)) == [], subtype


def test_localbusiness_descendant_person_and_website_are_accepted() -> None:
    for kind in ("Dentist", "Person", "WebSite", "LocalBusiness"):
        ctx = _org_ctx(f'{{"@type": "{kind}", "name": "x"}}')
        assert list(OrganizationSchemaCheck().run(ctx)) == [], kind


def test_type_matching_is_case_insensitive() -> None:
    """`Website` у дикій природі трапляється поруч із `WebSite`."""
    ctx = _org_ctx('{"@type": "website", "name": "x"}')
    assert list(OrganizationSchemaCheck().run(ctx)) == []
    assert is_identity_type("WEBSITE") and is_identity_type("organization")


def test_graph_arrays_and_nested_entities_are_seen() -> None:
    graph = (
        '{"@context": "https://schema.org", "@graph": ['
        '{"@type": "Article", "publisher": {"@type": "Organization", "name": "Acme"}}]}'
    )
    page = _jsonld(graph)
    assert "Organization" in types_on(page), "вкладений видавець — теж сутність"
    assert list(OrganizationSchemaCheck().run(context(page))) == []


def test_entity_on_an_about_page_is_accepted() -> None:
    """Google: місце Organization — головна АБО сторінка про організацію."""
    home = _jsonld('{"@type": "Article", "headline": "x"}', url="https://example.com/")
    about = _jsonld('{"@type": "Organization", "name": "Acme"}',
                    url="https://example.com/about-us")
    assert list(OrganizationSchemaCheck().run(context(home, about))) == []


def test_microdata_entity_is_accepted() -> None:
    home = _jsonld('{"@type": "Article", "headline": "x"}')
    home.microdata_types = ["Organization"]
    assert list(OrganizationSchemaCheck().run(context(home))) == []


# ── знімок типів ──────────────────────────────────────────────────────


def test_the_vendored_type_registry_is_not_silently_truncated() -> None:
    assert registry_problems() == []
    assert len(IDENTITY_TYPES) >= 150


# ── формулювання ──────────────────────────────────────────────────────


def test_wording_makes_no_ai_requirement_or_frequency_claims() -> None:
    """Жодною з шести мов: ні «мусять здогадуватися», ні «рідше називають»,
    ні вимог sameAs/logo, ні гарантій."""
    # «не гарантує» — навмисне чесне заперечення, його НЕ забороняємо;
    # заборонені лише позитивні обіцянки й вимоги.
    forbidden = ("рідше назива", "реже упомина", "must guess", "мусять здогадуватися",
                 "должны догадываться", "guarantees rich", "гарантує розширені",
                 "невидим", "invisible", "обовʼязково додайте",
                 # стара вимога переліку властивостей; нове формулювання їх
                 # не називає взагалі («без обовʼязкових властивостей» — це
                 # чесне заперечення, а не вимога)
                 "sameas", "contactpoint")
    for locale in ("uk", "en", "de", "es", "fr", "ru"):
        module = __import__(f"app.audit.i18n.{locale}", fromlist=["MESSAGES"])
        for key in ("ai.jsonld.missing", "ai.schema.organization"):
            blob = " ".join(module.MESSAGES[key].values()).lower()
            for mark in forbidden:
                assert mark not in blob, f"{locale}/{key}: «{mark}»"


def test_absence_wording_is_scoped_to_server_responses() -> None:
    """Ми читаємо статичні відповіді — і кажемо рівно це, а не «весь сайт»."""
    markers = {"uk": "відповід", "en": "server responses", "de": "serverantwort",
               "es": "respuestas", "fr": "réponses", "ru": "ответ"}
    for locale, mark in markers.items():
        module = __import__(f"app.audit.i18n.{locale}", fromlist=["MESSAGES"])
        blob = " ".join(module.MESSAGES["ai.jsonld.missing"].values()).lower()
        assert mark in blob, f"{locale}: обсяг не названо"
        assert "rdfa" in blob, f"{locale}: RDFa не згадано як неоцінений"


def test_old_partial_and_current_keys_render_in_all_six_locales() -> None:
    from app.audit.i18n import COMPLETE_LOCALES, render

    for locale in sorted(COMPLETE_LOCALES, key=lambda x: x.value):
        for key in ("ai.jsonld.missing", "ai.jsonld.partial", "ai.schema.organization"):
            entry = render(key, {"covered": 2, "total": 5}, locale)
            assert entry.title and key not in entry.title, f"{locale.value}/{key}"


def test_the_passed_check_stays_jsonld_specific_and_bonus_free() -> None:
    """Пройдене «JSON-LD виявлено» правдиве саме про JSON-LD; Microdata
    його не вмикає, бонусів не існує."""
    from app.report.passed import PassState, evaluate_all

    ev = {"structured_data": {"pages_with_jsonld": 0, "pages_total": 5}}
    assert evaluate_all(ev, set())["ai.jsonld"] is PassState.FAILED
    ev = {"structured_data": {"pages_with_jsonld": 2, "pages_total": 5}}
    assert evaluate_all(ev, set())["ai.jsonld"] is PassState.PASSED


# ── E-10: яка сторінка є «про нас», вирішує детектор, а не підрядок ────


def _nav(*links: tuple[str, str]) -> str:
    items = "".join(f'<li><a href="{href}">{text}</a></li>' for href, text in links)
    return f"<nav><ul>{items}</ul></nav>"


def _page(url: str, *, title: str, text: str = "слова про сайт", head: str = "",
          nav: str = "") -> object:
    return page_from_html(
        f"<html><head><title>{title}</title>{head}</head><body>{nav}"
        f"<main><h1>{title}</h1><p>{text}</p></main></body></html>",
        url=url,
    )


ORG = '<script type="application/ld+json">{"@type": "Organization", "name": "Acme"}</script>'
WEBPAGE = '<script type="application/ld+json">{"@type": "WebPage", "name": "Home"}</script>'
HREFLANG_DE = ('<link rel="alternate" hreflang="de" href="https://example.com/de/">'
               '<link rel="alternate" hreflang="en" href="https://example.com/">')


def test_organization_markup_on_a_localized_about_page_is_accepted() -> None:
    """`/de/ueber-uns` — сторінка про організацію, коли сайт оголосив `de`."""
    home = _page("https://example.com/", title="Acme", head=HREFLANG_DE)
    about = _page("https://example.com/de/ueber-uns", title="Über uns", head=HREFLANG_DE + ORG)
    assert about_page.selected_pages(context(home, about)) == [about]
    assert list(OrganizationSchemaCheck().run(context(home, about))) == []


def test_markup_on_a_substring_route_is_not_the_about_page() -> None:
    """`/about-cookies` розмітки організації не «розміщує»: судиться головна."""
    home = _page("https://example.com/", title="Acme")
    cookies = _page("https://example.com/about-cookies", title="Cookie policy", head=ORG)
    assert about_page.selected_pages(context(home, cookies)) == []
    (issue,) = OrganizationSchemaCheck().run(context(home, cookies))
    assert issue.evidence["checked_pages"] == [home.url]


def test_an_unread_about_candidate_leaves_only_the_home_page_to_judge() -> None:
    """Пункт меню «About us», ціль не відкрита: судиться лише головна.

    Коренева розмітка на сайті є (WebPage), тож чек не мовчить через її
    відсутність — він мовчав би лише тоді, коли б розмітки не було ніде.
    """
    nav = _nav(("/", "Home"), ("/about", "About us"))
    home = _page("https://example.com/", title="Acme", nav=nav, head=WEBPAGE)
    (issue,) = OrganizationSchemaCheck().run(context(home))
    assert issue.evidence["checked_pages"] == [home.url]
    marked = _page("https://example.com/", title="Acme", nav=nav, head=WEBPAGE + ORG)
    assert list(OrganizationSchemaCheck().run(context(marked))) == []


def test_a_substitute_about_document_is_not_a_place_for_markup() -> None:
    """Розмітка на стіні входу під `/about` не рахується: вердикту немає."""
    home = _page("https://example.com/", title="Acme")
    wall = page_from_html(
        f"<html><head><title>Sign in</title>{ORG}</head><body><main><h1>Sign in</h1>"
        '<form method="post"><input type="password" name="p"></form></main></body></html>',
        url="https://example.com/about",
    )
    decision = about_page.detect(context(home, wall))
    assert decision is not None and decision.reason == about_page.LOGIN_WALL
    assert about_page.selected_pages(context(home, wall)) == []
    (issue,) = OrganizationSchemaCheck().run(context(home, wall))
    assert issue.evidence["checked_pages"] == [home.url]


def test_the_selection_is_the_detectors_and_not_a_second_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Одне рішення на всіх: без словника детектора немає — і вибору теж."""
    home = _page("https://example.com/", title="Acme")
    about = _page("https://example.com/about", title="About us", head=ORG)
    assert list(OrganizationSchemaCheck().run(context(home, about))) == []
    monkeypatch.setattr(about_page, "AVAILABLE", False)
    assert about_page.selected_pages(context(home, about)) == []
    (issue,) = OrganizationSchemaCheck().run(context(home, about))
    assert issue.evidence["checked_pages"] == [home.url]
