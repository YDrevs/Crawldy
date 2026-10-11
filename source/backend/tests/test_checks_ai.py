import json

import pytest

from app.audit import applicability, breadcrumbs, hierarchy
from app.audit.checks.ai_ready import (
    BreadcrumbCheck,
    JsonLdPresenceCheck,
    LlmsTxtCheck,
    OrganizationSchemaCheck,
)
from app.audit.checks.llm_visibility import AiCrawlerAccessCheck, ClientRenderedCheck
from app.audit.enums import DegradationKind
from app.audit.logical_pages import normalize
from app.audit.orchestrator import AuditOptions, rescore
from app.audit.types import LlmsTxtInfo, Module, RobotsInfo, Severity, SitemapInfo
from app.report.builder import build_evidence
from tests.factories import context, page_from_html

ORG = """<html><head><title>t</title>
<script type="application/ld+json">{"@type":"Organization","name":"Acme","sameAs":["https://x"]}</script>
</head><body><h1>h</h1></body></html>"""


def test_llms_txt_missing():
    """404 — спостережена відсутність: можливість називається, штраф нуль."""
    info = LlmsTxtInfo(exists=False, status_code=404)
    issues = list(LlmsTxtCheck().run(context(page_from_html(ORG), llms_txt=info)))
    assert [i.code for i in issues] == ["ai.llms_txt"]
    assert issues[0].severity.value == "info"
    assert issues[0].evidence["response"] == "not_found"


def test_llms_txt_unknown_request_makes_no_absence_claim():
    """Немає відповіді — немає й твердження: за замовчуванням фабрики
    status_code=None, і чек мовчить, а не каже «файла немає»."""
    assert list(LlmsTxtCheck().run(context(page_from_html(ORG)))) == []


def test_llms_txt_present_and_rich():
    info = LlmsTxtInfo(exists=True, has_h1=True, section_count=3, link_count=9)
    assert list(LlmsTxtCheck().run(context(page_from_html(ORG), llms_txt=info))) == []


def test_jsonld_missing_flagged():
    issues = list(JsonLdPresenceCheck().run(context(page_from_html("<html><body>x</body></html>"))))
    assert issues and issues[0].module.value == "ai_ready"


def test_organization_schema_found():
    assert list(OrganizationSchemaCheck().run(context(page_from_html(ORG)))) == []


def test_blocked_ai_crawlers_flagged():
    """Джерелом тепер є сам robots.txt, а не заздалегідь зведений список.

    Раніше тест підставляв `blocked_ai_agents` напряму й тому не бачив би
    ані часткової заборони, ані призначення краулера. Тепер контекст дає
    справжній текст, і чек читає його тим самим розбирачем, що в проді.
    """
    robots = RobotsInfo(
        exists=True,
        status_code=200,
        content="User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n",
    )
    issues = list(AiCrawlerAccessCheck().run(context(page_from_html(ORG), robots=robots)))

    assert len(issues) == 1
    # Обидва — навчальні, тож і формулювання про навчання, а не про видимість.
    assert issues[0].msg == "llm.crawler_blocked.training"
    assert [e["token"] for e in issues[0].evidence["blocked"]] == ["GPTBot", "ClaudeBot"]
    assert {tuple(e["purposes"]) for e in issues[0].evidence["blocked"]} == {("training",)}


def test_client_rendered_detected():
    html = "<html><head><title>t</title></head><body><div id=root></div>" + "<div class='x'></div>" * 400 + "</body></html>"
    issues = list(ClientRenderedCheck().run(context(page_from_html(html))))
    assert issues and issues[0].severity.value == "critical"


def _schema_ctx(*pairs):
    """(url, чи є розмітка) → контекст."""
    from app.audit.types import PageSignals, SiteContext

    site = SiteContext(entry_url="https://s.com/", origin="https://s.com")
    for url, has_schema in pairs:
        page = PageSignals(url=url, status_code=200, title="Сторінка", html_bytes=20_000)
        page.word_count = 400
        page.text = "слово " * 400
        page.jsonld = [{"@type": "Organization", "name": "Смарт"}] if has_schema else []
        site.pages.append(page)
    return site


def _jsonld_issues(ctx):
    from app.audit.checks.ai_ready import JsonLdPresenceCheck

    return list(JsonLdPresenceCheck().run(ctx))


def test_partial_coverage_is_no_longer_a_finding():
    """Часткове покриття — не вада: розмітка не мусить бути на кожній
    сторінці (Google кладе Organization на головну або about), а
    посторінкову застосовність ми надійно не визначаємо. Раніше 150
    сайтів night3 діставали MEDIUM за «є не всюди»."""
    with_schema = page_from_html(ORG, url="https://example.com/")
    without = page_from_html("<html><body>text</body></html>", url="https://example.com/b")
    issues = list(JsonLdPresenceCheck().run(context(with_schema, without)))
    assert issues == []

def test_no_markup_anywhere_is_a_different_problem():
    """«Немає ніде» дорожче виправити, ніж «поставили не всюди»: у
    другому випадку шаблон уже вміє, і роботи менше."""
    issues = _jsonld_issues(_schema_ctx(("https://s.com/", False), ("https://s.com/a", False)))

    assert [i.msg for i in issues] == ["ai.jsonld.missing"]


def test_markup_everywhere_gives_nothing():
    assert _jsonld_issues(_schema_ctx(("https://s.com/", True), ("https://s.com/a", True))) == []


def test_a_docs_page_is_not_a_product_because_of_its_url():
    """`startswith("/product")` ловив `/products-prices/manage-prices`.

    Та сама пастка, що з `/legal/ssa-services-terms`: підрядок у шляху
    бреше. Тип сторінки тепер бере `type_of`.
    """
    from app.audit.checks.ai_ready import ContentSchemaCheck

    page = page_from_html(
        "<html lang='en'><head><title>How products and prices work in the API</title></head>"
        "<body><h1>Manage prices</h1><p>" + "documentation text " * 200 + "</p></body></html>",
        url="https://example.com/products-prices/manage-prices",
        depth=1,
    )
    assert not list(ContentSchemaCheck().run(context(page)))


def test_a_category_listing_is_not_an_article():
    """Article на сторінці-переліку був би неправдою."""
    from app.audit.checks.ai_ready import ContentSchemaCheck

    page = page_from_html(
        "<html lang='en'><head><title>Product blog category listing page</title></head>"
        "<body><h1>Category</h1><p>" + "listing text " * 200 + "</p></body></html>",
        url="https://example.com/blog/category/product-blog/page/4/",
        depth=2,
    )
    assert not list(ContentSchemaCheck().run(context(page)))


def test_a_real_article_without_markup_is_still_a_finding():
    from app.audit.checks.ai_ready import ContentSchemaCheck

    page = page_from_html(
        "<html lang='uk'><head><title>Як обрати покрівлю для приватного будинку</title></head>"
        "<body><h1>Як обрати покрівлю</h1><p>" + "текст статті " * 200 + "</p></body></html>",
        url="https://example.com/blog/yak-obraty-pokrivlyu",
        depth=1,
    )
    issues = list(ContentSchemaCheck().run(context(page)))
    assert len(issues) == 1
    assert issues[0].evidence["page_type"] == "article"


def test_documentation_is_not_an_article():
    """У довідки немає автора й дати, і це не недбалість.

    Спершу розділи документації жили серед статей — щоб глосарій не
    ставав послугою через слово «price» усередині терміна. Це полагодило
    одне, зламавши інше: від кожної сторінки документації почали
    вимагати автора, дату й розмітку Article.
    """
    from app.audit.page_kinds import EXPECTS_AUTHORSHIP, PageType, type_of

    for url in (
        "https://linear.app/docs/joining-your-team",
        "https://supabase.com/docs/guides/auth",
        "https://example.com/glossary/configure-price-quote",
    ):
        assert type_of(url) is PageType.DOCS, url
        assert type_of(url) not in EXPECTS_AUTHORSHIP


def test_a_docs_subdomain_beats_a_system_word_in_the_path():
    """`docs.stripe.com/payments/checkout` — це довідка, а не кошик."""
    from app.audit.page_kinds import PageType, type_of

    assert type_of("https://docs.stripe.com/payments/checkout") is PageType.DOCS


def test_a_blog_post_is_still_an_article():
    from app.audit.page_kinds import EXPECTS_AUTHORSHIP, PageType, type_of

    assert type_of("https://backlinko.com/blog/seo-tips") is PageType.ARTICLE
    assert PageType.ARTICLE in EXPECTS_AUTHORSHIP


# ── E-12: тип сторінки враховує оголошену мову ────────────────────────────


def test_a_declared_language_root_is_the_home_page():
    """`/de` на сайті, що оголосив німецьку, — та сама головна, що й `/`.

    Доти це була невпізнана сторінка: слово `de` не означає нічого, тож
    головна німецької версії судилась як звичайна адреса — без вимог до
    розмітки, які має головна, і без її ваги.
    """
    from app.audit.page_kinds import PageType, type_of

    assert type_of("https://s.com/de", locales=("de",)) is PageType.HOME
    assert type_of("https://s.com/de/", locales=("de",)) is PageType.HOME


def test_a_localized_pricing_route_is_a_service_page():
    """П'ять мов, одне поняття."""
    from app.audit.page_kinds import PageType, type_of

    assert type_of("https://s.com/de/preise", locales=("de",)) is PageType.SERVICE
    assert type_of("https://s.com/fr/tarifs", locales=("fr",)) is PageType.SERVICE
    assert type_of("https://s.com/es/precios", locales=("es",)) is PageType.SERVICE
    assert type_of("https://s.com/ru/tseny", locales=("ru",)) is PageType.SERVICE
    assert type_of("https://s.com/uk/tsiny", locales=("uk",)) is PageType.SERVICE


def test_an_undeclared_language_prefix_is_not_stripped():
    """`/de/folder` на сайті без оголошених мов — тека, а не мовна версія.

    Дві літери в шляху — здогад. Знімати їх без оголошення означало б
    перетворити теку `/de/` на корінь мовної версії й судити її сторінки
    правилами, яких вони не стосуються.
    """
    from app.audit.page_kinds import Basis, classify

    found = classify("https://s.com/de/folder")

    assert found.locale is None
    assert found.basis is Basis.LOCALE_NOT_DECLARED
    assert not found.conclusive


def test_an_unsupported_language_prefix_is_never_stripped():
    """`/it/` на англомовному сайті лишається як є.

    Італійська не є мовою запуску, словника для неї немає, і сегмент `it`
    так само ймовірно означає відділ інформаційних технологій.
    """
    from app.audit.page_kinds import Basis, classify

    found = classify("https://s.com/it/helpdesk", locales=("en",))

    assert found.locale is None
    assert found.basis is Basis.NO_LOCALE_SEGMENT
    assert found.conclusive


def test_only_the_leading_segment_is_treated_as_a_language():
    """`/de/de/preise` втрачає один префікс, а не обидва."""
    from app.audit.page_kinds import PageType, type_of

    assert type_of("https://s.com/de/de/preise", locales=("de",)) is PageType.SERVICE


def test_case_and_trailing_slash_do_not_change_the_answer():
    from app.audit.page_kinds import PageType, type_of

    for url in (
        "https://s.com/DE/PREISE",
        "https://s.com/de/preise/",
        "https://s.com/de/preise?utm_source=x",
        "https://s.com/de/preise#top",
    ):
        assert type_of(url, locales=("de",)) is PageType.SERVICE, url


def test_a_declared_locale_does_not_override_a_system_or_legal_route():
    """Порядок джерел не змінився: службове й юридичне визначаються першими."""
    from app.audit.page_kinds import PageType, type_of

    assert type_of("https://s.com/de/impressum", locales=("de",)) is PageType.LEGAL
    assert type_of("https://s.com/de/login-preise", locales=("de",)) is PageType.SYSTEM


def test_declared_locales_are_derived_from_what_the_site_says_about_itself():
    """Джерела — `<html lang>`, hreflang і карта сайту. Не шлях.

    `de-DE` нормалізується в `de`: регіон іншої мови не робить.
    `x-default`, недійсний тег і непідтримувана мова оголошенням не є.
    """
    from app.audit import hreflang
    from app.audit.types import HreflangRef, PageSignals, SiteContext

    ctx = SiteContext(entry_url="https://s.com/", origin="https://s.com")
    ctx.pages = [
        PageSignals(url="https://s.com/", status_code=200, lang="de-DE", hreflang=[
            HreflangRef(value="fr-CA", href="https://s.com/fr/", source="html"),
            HreflangRef(value="x-default", href="https://s.com/", source="html"),
            HreflangRef(value="en_US", href="https://s.com/en/", source="html"),
            HreflangRef(value="it", href="https://s.com/it/", source="html"),
        ]),
    ]

    assert hreflang.declared_locales(ctx) == ["de", "fr"]
    evidence = hreflang.declared_locale_evidence(ctx)
    assert evidence["de"] == ["html_lang"]
    assert evidence["fr"] == ["hreflang_html"]


def test_declared_locales_are_ordered_and_deduplicated():
    """Список їде у знімок, тож його порядок не сміє залежати від обходу."""
    from app.audit import hreflang
    from app.audit.types import HreflangRef, PageSignals, SiteContext

    ctx = SiteContext(entry_url="https://s.com/", origin="https://s.com")
    ctx.pages = [
        PageSignals(url="https://s.com/a", status_code=200, lang="ru", hreflang=[
            HreflangRef(value="de-AT", href="https://s.com/de/a", source="html"),
            HreflangRef(value="de-CH", href="https://s.com/de/b", source="html"),
        ]),
        PageSignals(url="https://s.com/b", status_code=200, lang="de", hreflang=[]),
    ]

    assert hreflang.declared_locales(ctx) == ["de", "ru"]


def test_the_context_derives_declared_locales_once():
    """Поле лишається порожнім, поки його не спитали, і рахується один раз."""
    from app.audit.types import PageSignals, SiteContext

    ctx = SiteContext(entry_url="https://s.com/", origin="https://s.com")
    ctx.pages = [PageSignals(url="https://s.com/", status_code=200, lang="de")]

    assert ctx.locales_declared is None
    assert ctx.declared_locales() == ["de"]
    assert ctx.locales_declared == ["de"]


# ── E-12: адреса подорожує закодованою ────────────────────────────────────
#
# Словник написаний людськими літерами, а в адресі вони їдуть у відсотках.
# Доки сегмент не декодувати, двигун бачить `%c3%bcber` і не збігається з
# `über` — тобто правильний словник мовчить через подання, а не через зміст.


@pytest.mark.parametrize(("locale", "raw", "encoded", "expected"), [
    ("de", "/de/über-uns", "/de/%C3%BCber-uns", "about"),
    ("es", "/es/términos", "/es/t%C3%A9rminos", "legal"),
    ("uk", "/uk/компанії",
     "/uk/%D0%BA%D0%BE%D0%BC%D0%BF%D0%B0%D0%BD%D1%96%D1%97", "about"),
    ("ru", "/ru/услуги", "/ru/%D1%83%D1%81%D0%BB%D1%83%D0%B3%D0%B8", "service"),
])
def test_a_percent_encoded_route_classifies_like_its_unicode_twin(
    locale: str, raw: str, encoded: str, expected: str
) -> None:
    """Та сама сторінка, два подання — одна відповідь.

    Порівнюємо не лише тип: мова, підстава й певність мусять збігтися теж,
    інакше «однаково класифіковано» ховало б розбіжність у тому, ЧОМУ.
    """
    from app.audit.page_kinds import classify

    first = classify(f"https://site.example{raw}", locales=(locale,))
    second = classify(f"https://site.example{encoded}", locales=(locale,))

    assert first.page_type.value == expected
    assert second.page_type.value == expected
    assert (first.page_type, first.locale, first.basis, first.conclusive) == (
        second.page_type, second.locale, second.basis, second.conclusive
    )


def test_precomposed_and_decomposed_unicode_are_the_same_route() -> None:
    """`ü` буває одним символом і буває `u` плюс комбінований умляут.

    Обидва записи трапляються в живих адресах, і доки їх не звести до NFC,
    половина німецьких маршрутів просто не збігається зі словником.
    """
    from app.audit.page_kinds import PageType, classify

    precomposed = classify("https://s.example/de/über-uns", locales=("de",))
    decomposed = classify("https://s.example/de/u%CC%88ber-uns", locales=("de",))

    assert precomposed.page_type is PageType.ABOUT
    assert decomposed.page_type is PageType.ABOUT
    assert precomposed.basis is decomposed.basis


def test_a_percent_encoded_hyphen_separates_words_like_a_literal_one() -> None:
    """`%2D` — це дефіс, тож після декодування він ріже сегмент так само."""
    from app.audit.page_kinds import PageType, type_of

    assert type_of("https://s.example/de/ueber%2Duns", locales=("de",)) is PageType.ABOUT


def test_an_encoded_slash_stays_inside_its_segment() -> None:
    """`%2F` — це дані, а не межа маршруту.

    Якби шлях декодували цілком і лише потім ділили, `/de/a%2Fb` стало б
    двома теками: зʼявився б сегмент, якого в адресі немає, і глибина
    розділу поїхала б разом із типом сторінки.
    """
    from app.audit.page_kinds import _route_chunks, path_words

    chunks, locale, _basis = _route_chunks("https://s.example/de/a%2Fb", ("de",))

    assert chunks == ["a/b"]
    assert locale == "de"
    assert path_words("https://s.example/de/a%2Fb", ("de",)) == {"a/b"}


@pytest.mark.parametrize("path", ["/de/%", "/de/%zz", "/de/%C3", "/de/preise%"])
def test_a_broken_percent_escape_does_not_break_classification(path: str) -> None:
    """Обірване екранування не сміє ані впасти, ані вигадати слово словника."""
    from app.audit.page_kinds import classify

    found = classify(f"https://s.example{path}", locales=("de",))

    assert found.locale == "de"
    assert found.page_type is not None


def test_decoding_does_not_reach_the_query_or_the_fragment() -> None:
    """Класифікація дивиться на шлях; решта адреси її не стосується."""
    from app.audit.page_kinds import PageType, type_of

    for url in (
        "https://s.example/de/%C3%BCber-uns?q=%C3%A4",
        "https://s.example/de/%C3%BCber-uns#%C3%A4",
        "https://s.example/de/%C3%BCber-uns/?utm_source=x",
    ):
        assert type_of(url, locales=("de",)) is PageType.ABOUT, url


def test_ascii_routes_are_untouched_by_decoding() -> None:
    """Нормалізація не сміє зрушити жодну з наявних англійських адрес."""
    from app.audit.page_kinds import PageType, type_of

    assert type_of("https://stripe.com/legal/ssa-services-terms") is PageType.LEGAL
    assert type_of("https://backlinko.com/blog/seo-tips") is PageType.ARTICLE
    assert type_of("https://docs.stripe.com/payments/checkout") is PageType.DOCS
    assert type_of("https://example.com/wp-login.php") is PageType.SYSTEM
    assert type_of("https://example.com/pricing") is PageType.SERVICE
    assert type_of("https://example.com/") is PageType.HOME


def test_decoding_does_not_change_the_undeclared_or_unsupported_rules() -> None:
    """E12-f3 і E12-f4 лишаються тим, чим були, і в закодованому вигляді.

    Декодування відповідає на питання «що це за слово», а не «чи можна
    зняти префікс». Друге рішення так само тримається на оголошенні.
    """
    from app.audit.page_kinds import Basis, classify

    undeclared = classify("https://s.example/de/%C3%BCber-uns")
    assert undeclared.locale is None
    assert undeclared.basis is Basis.LOCALE_NOT_DECLARED
    assert not undeclared.conclusive

    unsupported = classify("https://s.example/it/%C3%BCber-uns", locales=("en",))
    assert unsupported.locale is None
    assert unsupported.basis is Basis.NO_LOCALE_SEGMENT
    assert unsupported.conclusive


def test_a_translated_slug_never_overrides_an_observed_error():
    """Сторінка, що відповіла помилкою, не стає сторінкою послуг.

    Тип береться з адреси, а `ok_pages` — зі статусу. Сторінка з 404 не
    потрапляє ні в контентні чеки, ні в оголошення мов: слоґ не може
    перекрити те, що ми бачили на власні очі.
    """
    from app.audit import hreflang
    from app.audit.types import PageSignals, SiteContext

    ctx = SiteContext(entry_url="https://s.com/", origin="https://s.com")
    ctx.pages = [PageSignals(url="https://s.com/de/preise", status_code=404, lang="de")]

    assert ctx.ok_pages == []
    assert hreflang.declared_locales(ctx) == []
    assert ctx.declared_locales() == []


# ── ai.llms_txt: необовʼязкова можливість зі штрафом нуль ─────────────


def _score_with(issues):
    from app.audit.enums import Module
    from app.audit.scoring import module_score

    return module_score(list(issues), Module.AI_READY)


def test_llms_txt_absence_costs_exactly_zero_points():
    """404 — знахідка є, штраф нуль: AI_READY не знижується.

    Специфікація v2 досі називає себе пропозицією, Lighthouse ставить
    404 у Not Applicable. Карати за відсутність необовʼязкового не можна.
    """
    info = LlmsTxtInfo(exists=False, status_code=404)
    issues = list(LlmsTxtCheck().run(context(page_from_html(ORG), llms_txt=info)))
    assert issues, "можливість називається"
    assert _score_with(issues) == 100, "але не коштує ані бала"
    assert _score_with(issues) == _score_with([]), "рівно як без знахідки"


def test_llms_txt_410_is_observed_absence_with_zero_penalty():
    info = LlmsTxtInfo(exists=False, status_code=410)
    issues = list(LlmsTxtCheck().run(context(page_from_html(ORG), llms_txt=info)))
    assert issues and issues[0].evidence["response"] == "not_found"
    assert _score_with(issues) == 100


def test_llms_txt_html_fallback_is_not_a_valid_file():
    """200 зі звичайною сторінкою — файла немає, і збирач це бачить."""
    import asyncio

    from app.audit.site_context import collect_llms_txt

    class _FakeFetcher:
        async def get(self, url):
            class R:
                ok = True
                is_html = True
                status_code = 200
                text = "<html><body>Home page</body></html>"
            return R()

    info = asyncio.run(collect_llms_txt(_FakeFetcher(), "https://example.com"))
    assert info.exists is False
    issues = list(LlmsTxtCheck().run(context(page_from_html(ORG), llms_txt=info)))
    assert issues and issues[0].evidence["response"] == "fallback_page"
    assert _score_with(issues) == 100


def test_llms_txt_timeout_and_5xx_are_not_reported_as_absence():
    """Таймаут чи 5xx — ми не знаємо, чи є файл. Мовчимо, а не вигадуємо.

    На night3 таких «невідомо» 20 із 969, і всі вони раніше звалися
    «немає» — твердження про відсутність без погляду на неї.
    """
    for status in (None, 500, 503, 403, 429):
        info = LlmsTxtInfo(exists=False, status_code=status)
        assert list(LlmsTxtCheck().run(context(page_from_html(ORG), llms_txt=info))) == [], (
            f"HTTP {status}: відсутності не стверджуємо"
        )


def test_llms_txt_quality_notes_on_an_existing_file_cost_nothing():
    """Файл є, але тонкий — зауваження інформаційне, штраф нуль."""
    info = LlmsTxtInfo(exists=True, has_h1=False, section_count=0, link_count=0)
    issues = list(LlmsTxtCheck().run(context(page_from_html(ORG), llms_txt=info)))
    assert {i.key for i in issues} == {"no_h1", "thin"}
    assert _score_with(issues) == 100


def test_a_valid_llms_txt_earns_no_scoring_bonus():
    """Пройдена перевірка — це відсутність знахідки, а не додані бали.

    Бал модуля без жодної знахідки — 100 і для сайту з файлом, і без
    нього: механізму бонусів не існує, і цей тест тримає його
    неіснування.
    """
    rich = LlmsTxtInfo(exists=True, has_h1=True, section_count=3, link_count=9)
    with_file = list(LlmsTxtCheck().run(context(page_from_html(ORG), llms_txt=rich)))
    assert with_file == []
    absent = LlmsTxtInfo(exists=False, status_code=404)
    without = list(LlmsTxtCheck().run(context(page_from_html(ORG), llms_txt=absent)))
    assert _score_with(with_file) == _score_with(without) == 100


def test_llms_txt_wording_never_guarantees_ai_outcomes():
    """Жодною мовою не обіцяємо ані обходу, ані цитувань, ані позицій."""
    guarantee_free = {
        "uk": "не заважає",
        "en": "does not prevent",
        "de": "hindert",
        "es": "no impide",
        "fr": "n'empêche pas",
        "ru": "не мешает",
    }
    for locale, marker in guarantee_free.items():
        module = __import__(f"app.audit.i18n.{locale}", fromlist=["MESSAGES"])
        blob = " ".join(module.MESSAGES["ai.llms_txt.missing"].values()).lower()
        assert marker in blob, f"{locale}: не сказано, що відсутність не заважає ШІ"
        assert "оптимізуйте сайт" not in blob


def test_old_stored_llms_results_remain_readable():
    """Збережена знахідка ai.llms_txt.missing читається старим ключем."""
    from app.audit.i18n import COMPLETE_LOCALES, render

    for locale in COMPLETE_LOCALES:
        text = render("ai.llms_txt.missing", {}, locale)
        assert "ai.llms_txt" not in str(text), f"{locale}: сирий ключ у рендері"


# ── E-05: соціальне прев'ю застосовне рівно там, де маршрут спільний ───

from app.audit.applicability import ClaimVerdict, Coverage, declare, shareable  # noqa: E402
from app.audit.checks.base import all_checks  # noqa: E402
from app.audit.route_classes import ATTRIBUTES, RouteClass, classify_page  # noqa: E402
from app.audit.site_context import _parse_robots  # noqa: E402

_TEXT = "<p>%s</p>" % ("Текст, якого вистачає, щоб сторінку було з чого судити. " * 10)


def _page(url: str, *, title: str = "", noindex: bool = False, og: bool = False):
    head = f"<title>{title}</title>" if title else ""
    if noindex:
        head += '<meta name="robots" content="noindex,follow">'
    if og:
        head += ('<meta property="og:title" content="t">'
                 '<meta property="og:image" content="https://example.com/i.png">'
                 '<meta property="og:description" content="d">')
    page = page_from_html(f'<html lang="uk"><head>{head}</head>'
                          f'<body><h1>{title or "Заголовок"}</h1>{_TEXT}</body></html>', url=url)
    page.status_code = 200
    return page


def _robots_of(*disallow: str) -> RobotsInfo:
    lines = ["User-agent: *", *(f"Disallow: {path}" for path in disallow)] if disallow else [
        "User-agent: *", "Allow: /"]
    info = RobotsInfo(status_code=200, content=chr(10).join(lines) + chr(10))
    info.exists = True
    _parse_robots(info)
    return info


def _emitted(ctx, code: str) -> list[str]:
    check = next(c for c in all_checks() if c.code == code)
    return sorted(i.issue_key for i in check.run(ctx))


def test_e05_f9_a_social_preview_finding_survives_noindex():
    """E05-f9. `noindex` закриває сторінку від пошуку, а не від людей.

    Юридичну сторінку надсилають у месенджері так само, як будь-яку іншу,
    і картка прев'ю там така сама видима. Притримати цю знахідку через
    `noindex` означало б переплутати дві різні аудиторії.
    """
    ctx = context(_page("https://example.com/privacy", title="Приватність", noindex=True),
                  robots=_robots_of())
    assert classify_page(ctx, ctx.ok_pages[0]).route_class is RouteClass.PUBLIC_NOINDEX_INFORMATIONAL
    assert "ai.opengraph:tags" in _emitted(ctx, "ai.opengraph")
    assert declare("ai.opengraph", RouteClass.PUBLIC_NOINDEX_INFORMATIONAL,
                   "tags").mode.value == "EVALUATE"


def test_e05_f10_twitter_card_is_not_applicable_on_an_admin_route():
    """E05-f10. Сторінку адмінки не надсилають — ділитися нема чим."""
    ctx = context(_page("https://example.com/admin/payments"), robots=_robots_of("/admin"))
    assert classify_page(ctx, ctx.ok_pages[0]).route_class is RouteClass.PRIVATE_ADMIN_SYSTEM
    assert _emitted(ctx, "ai.twitter_card") == []
    declaration = declare("ai.twitter_card", RouteClass.PRIVATE_ADMIN_SYSTEM)
    assert declaration.reason_code == "A-06"
    assert declaration.can_emit_factual_finding is False


def test_e05_social_preview_applies_exactly_where_the_route_is_shareable():
    """Ознака `shareable` — єдине джерело для всієї родини прев'ю.

    Перевіряється не список класів, а ЗБІГ: претензія застосовна рівно
    там, де таблиця класів каже «спільний». Список розійшовся б із
    таблицею при першій же правці, збіг — ні.
    """
    for route in RouteClass:
        expected = ATTRIBUTES[route].shareable
        assert shareable(route) is expected
        for code in ("ai.opengraph", "ai.twitter_card"):
            applies = declare(code, route).mode.value not in ("NA_A06", "NO_VERDICT_UNKNOWN")
            assert applies is bool(expected), f"{code} на {route.value}"


def test_e05_structured_data_absence_is_claimed_only_of_pages_that_should_carry_it():
    """«Розмітки немає ніде» — твердження про вміст, а не про кошик.

    Знахідка тут одна й без адреси, тож центральний фільтр їй не
    допомагає: застосовність мусить відсіятися на ВХОДІ, поки твердження
    ще складається. Сайт, у якого розмітка є всюди, крім входу й
    оплати, розмітку має.
    """
    marked = page_from_html(
        '<html lang="uk"><head><title>Ціни</title>'
        '<script type="application/ld+json">{"@type":"Organization","name":"Acme"}</script>'
        f'</head><body><h1>Ціни</h1>{_TEXT}</body></html>',
        url="https://example.com/pricing")
    marked.status_code = 200
    ctx = context(marked, _page("https://example.com/login"),
                  _page("https://example.com/checkout"), robots=_robots_of("/login", "/checkout"))
    assert _emitted(ctx, "ai.jsonld.missing") == []
    # А сайт без розмітки на самому вмісті лишається сайтом без розмітки.
    bare = context(_page("https://example.com/pricing", title="Ціни"),
                   _page("https://example.com/login"), robots=_robots_of("/login"))
    assert _emitted(bare, "ai.jsonld.missing") == ["ai.jsonld.missing"]


def test_e05_passed_checks_admit_only_pass_with_complete_coverage():
    """Жодна стратегія агрегації не має винятку з `PASS + COMPLETE`.

    Перевіряється саме правило, а не його наслідок на одному сайті:
    чотири стратегії, чотири вердикти, чотири покриття — і рівно одна
    придатна пара.
    """
    from app.audit.applicability import eligible_for_passed_checks

    admitted = {(verdict, coverage) for verdict in ClaimVerdict for coverage in Coverage
                if eligible_for_passed_checks(verdict, coverage)}
    assert admitted == {(ClaimVerdict.PASS, Coverage.COMPLETE)}


# ══════════════════════════════════════════════════════════════════════════
# E-15 — «хлібні крихти» на ДОВЕДЕНІЙ ієрархії
#
# Двадцять чотири канонічні випадки контракту, побудовані як справжні
# контексти двигуна: пʼятнадцять про ієрархію, девʼять про дійсність
# `BreadcrumbList`. Фікстури тут — ті самі, що в доказовому зонді групи, і
# це навмисно: два різні будівники означали б два різні сайти, і різниця
# між прийнятим деревом і кандидатом стала б невідрізненною від різниці
# між фікстурами.
#
# Нижче кожного блоку фікстур ідуть цільові тести, кожен з яких ЛАМАЄТЬСЯ
# від конкретної мутації правила. Список мутацій — у ділянці 12 інструкції
# групи; тест, який мутація не ламає, не є воротами.
# ══════════════════════════════════════════════════════════════════════════

E15_ORIGIN = "https://example.com"

# Long enough that every fixture clears MIN_WORDS_FOR_A_SITE on its own. A shorter paragraph made
# the two-page cases trip the crawl-blindness rule instead of the hierarchy rule, and a fixture
# that fails for a reason it does not name is testing the wrong thing.
E15_PROSE = ("We build measurement tools for teams who care what their pages actually say. "
         "Every page here carries enough text to be a real document rather than an empty shell, "
         "because a page the crawler judges thin is judged by a different rule entirely and would "
         "never reach the question this fixture exists to ask. The paragraph is ordinary prose "
         "about an ordinary business: what it makes, who it makes it for, and where to find the "
         "rest of the catalogue. Nothing in it carries a signal that any check reads. ")


# ── document helpers ──────────────────────────────────────────────────────

def e15_chrome(*links: tuple[str, str]) -> str:
    """Site-chrome navigation: `<nav>` is what makes `LinkRef.in_chrome` true."""
    items = "".join(f'<li><a href="{href}">{text}</a></li>' for href, text in links)
    return f"<nav><ul>{items}</ul></nav>"


def _e15_grouped_menu(*groups: tuple[str, tuple[tuple[str, str], ...]]) -> str:
    """A DOM-grouped menu whose group LABEL IS NOT A LINK.

    This is E15-f6's "nested lists under non-link headings": the markup groups items visually,
    but the group label resolves to no page, so there is no parent to verify a relationship
    against. Supporting evidence only.
    """
    blocks = []
    for label, links in groups:
        items = "".join(f'<li><a href="{href}">{text}</a></li>' for href, text in links)
        blocks.append(f"<li><span>{label}</span><ul>{items}</ul></li>")
    return f"<nav><ul>{''.join(blocks)}</ul></nav>"


def e15_ld(payload: str) -> str:
    return f'<script type="application/ld+json">{payload}</script>'


def _e15_typed(schema_type: str, name: str = "Thing") -> str:
    """The site declaring its own page type — the strongest source `type_of` has."""
    return e15_ld(f'{{"@context":"https://schema.org","@type":"{schema_type}","name":"{name}"}}')


def e15_breadcrumb_ld(items: list[dict], *, container: str = "list") -> str:
    """A `BreadcrumbList`, in one of the canonical shapes.

    `container="list"` is the bare `BreadcrumbList`; `container="graph"` nests it in an `@graph`,
    which is the other shape sites actually publish. Both must be supported.
    """
    entries = []
    for item in items:
        parts = ['"@type":"ListItem"']
        if item.get("position") is not None:
            # JSON-encoded, not interpolated: a case that means to publish `"position": "1"`
            # must publish a STRING, or it quietly becomes the integer case and tests nothing.
            parts.append('"position":' + json.dumps(item["position"]))
        if item.get("name") is not None:
            parts.append(f'"name":{_e15_json(item["name"])}')
        if item.get("item") is not None:
            parts.append(f'"item":{_e15_json(item["item"])}')
        if item.get("item_object") is not None:
            inner = item["item_object"]
            fields = [f'"@id":{_e15_json(inner["id"])}'] if inner.get("id") else []
            if inner.get("name") is not None:
                fields.append(f'"name":{_e15_json(inner["name"])}')
            parts.append('"item":{' + ",".join(fields) + "}")
        entries.append("{" + ",".join(parts) + "}")
    body = ('{"@type":"BreadcrumbList","itemListElement":[' + ",".join(entries) + "]}")
    if container == "graph":
        return e15_ld('{"@context":"https://schema.org","@graph":[' + body + "]}")
    return e15_ld('{"@context":"https://schema.org",' + body[1:])


def _e15_json(value: str) -> str:
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _e15_document(*, title: str = "", h1: str = "", body: str = "", head_extra: str = "",
             nav: str = "", lang: str = "en", noindex: bool = False,
             breadcrumb_nav: str = "") -> str:
    head = f"<title>{title}</title>" if title else ""
    if noindex:
        head += '<meta name="robots" content="noindex">'
    head += head_extra
    heading = f"<h1>{h1}</h1>" if h1 else ""
    return (f'<html lang="{lang}"><head>{head}</head><body>{nav}{breadcrumb_nav}'
            f"<main>{heading}{body}<p>{E15_PROSE}</p></main></body></html>")


def e15_breadcrumb_ui(*links: tuple[str, str]) -> str:
    """A visible breadcrumb trail — retained evidence, never a substitute for the markup."""
    items = "".join(f'<li><a href="{href}">{text}</a></li>' for href, text in links)
    return f'<nav aria-label="Breadcrumb"><ol>{items}</ol></nav>'


# ── E-15-E15_VALIDITY: nine BreadcrumbList validity cases ─────────────────────
# Each case is the JSON-LD payload plus the entry URL its scope is judged against. The expected
# result is the contract's own `expected_valid`.

E15_C = f"{E15_ORIGIN}/catalog"
E15_CC = f"{E15_ORIGIN}/catalog/chairs"
E15_CCO = f"{E15_ORIGIN}/catalog/chairs/oak-chair"

E15_VALIDITY: dict[str, dict] = {
    "BV-f1": {
        "input": "trail of three ListItems, each with position, name and an in-scope item URL",
        "entry": E15_ORIGIN + "/",
        "page_url": E15_CCO,
        "items": [{"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
                  {"position": 2, "name": "Catalog", "item": E15_C},
                  {"position": 3, "name": "Oak chair", "item": E15_CCO}],
        "expected_valid": True,
        "reason": None,
    },
    "BV-f2": {
        "input": "trail of three ListItems where the FINAL item has no URL",
        "entry": E15_ORIGIN + "/",
        "page_url": E15_CCO,
        "items": [{"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
                  {"position": 2, "name": "Catalog", "item": E15_C},
                  {"position": 3, "name": "Oak chair"}],
        "expected_valid": True,
        "reason": "v1.3 correction E15_C: a trail must not be invalid solely because its final item "
                  "has no URL",
    },
    "BV-f3": {
        "input": "trail of two ListItems ending at the parent category; the audited page has no "
                 "self-referencing crumb",
        "entry": E15_ORIGIN + "/",
        "page_url": E15_CCO,
        "items": [{"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
                  {"position": 2, "name": "Catalog", "item": E15_C}],
        "expected_valid": True,
        "reason": "v1.3 correction E15_C: a self-referencing final crumb is not required",
    },
    "BV-f4": {
        "input": "positions 1, 3, 2 (not consecutively ascending in trail order)",
        "entry": E15_ORIGIN + "/",
        "page_url": E15_CCO,
        "items": [{"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
                  {"position": 3, "name": "Catalog", "item": E15_C},
                  {"position": 2, "name": "Oak chair", "item": E15_CCO}],
        "expected_valid": False,
        "reason": "V2 ordering",
    },
    "BV-f5": {
        "input": "second ListItem carries neither ListItem.name nor item.name",
        "entry": E15_ORIGIN + "/",
        "page_url": E15_CCO,
        "items": [{"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
                  {"position": 2, "item": E15_C},
                  {"position": 3, "name": "Oak chair", "item": E15_CCO}],
        "expected_valid": False,
        "reason": "V3 missing name",
    },
    "BV-f6": {
        "input": "BreadcrumbList with a single ListItem",
        "entry": E15_ORIGIN + "/",
        "page_url": E15_CCO,
        "items": [{"position": 1, "name": "Home", "item": E15_ORIGIN + "/"}],
        "expected_valid": False,
        "reason": "V1 fewer than two items",
    },
    "BV-f7": {
        "input": "a non-final item URL points at a different site (different registrable domain)",
        "entry": E15_ORIGIN + "/",
        "page_url": E15_CCO,
        "items": [{"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
                  {"position": 2, "name": "Partner", "item": "https://other-site.example.net/x"},
                  {"position": 3, "name": "Oak chair", "item": E15_CCO}],
        "expected_valid": False,
        "reason": "V7 out of scope per site_scope",
    },
    "BV-f8": {
        "input": "item URLs use the www alias and https while the entry origin is http without www",
        "entry": "http://example.com/",
        "page_url": "http://example.com/catalog/chairs/oak-chair",
        "items": [{"position": 1, "name": "Home", "item": "https://www.example.com/"},
                  {"position": 2, "name": "Catalog", "item": "https://www.example.com:443/catalog"},
                  {"position": 3, "name": "Oak chair",
                   "item": "https://www.example.com/catalog/chairs/oak-chair"}],
        "expected_valid": True,
        "reason": "the shared site_scope predicate treats www aliases, schemes and default ports "
                  "as the same site; literal origin equality is not the test",
    },
    "BV-f9": {
        "input": "a non-final ListItem has a name but no item URL",
        "entry": E15_ORIGIN + "/",
        "page_url": E15_CCO,
        "items": [{"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
                  {"position": 2, "name": "Catalog"},
                  {"position": 3, "name": "Oak chair", "item": E15_CCO}],
        "expected_valid": False,
        "reason": "V4 non-final item without a URL",
    },
}


# ── E-15: fifteen hierarchy cases ─────────────────────────────────────────
# `pages` entries are (url, html, status). `status is None` means the URL is KNOWN — from the
# chrome, from the sitemap — and was never fetched: that is what makes eligible coverage
# incomplete, and it is the difference between UNKNOWN and FLAT.

E15_VALID_TRAIL_CHAIRS = e15_breadcrumb_ld([
    {"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
    {"position": 2, "name": "Catalog", "item": E15_C},
    {"position": 3, "name": "Chairs", "item": E15_CC},
])
E15_VALID_TRAIL_OAK = e15_breadcrumb_ld([
    {"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
    {"position": 2, "name": "Chairs", "item": E15_CC},
    {"position": 3, "name": "Oak chair"},
])
E15_INVALID_TRAIL = e15_breadcrumb_ld([{"position": 1, "name": "Home", "item": E15_ORIGIN + "/"}])

E15_NAV_FLAT = e15_chrome(("/", "Home"), ("/about", "About"), ("/pricing", "Pricing"),
                  ("/contact", "Contact"))


E15_VALID_TRAIL_CATALOG = e15_breadcrumb_ld([
    {"position": 1, "name": "Home", "item": E15_ORIGIN + "/"},
    {"position": 2, "name": "Catalog", "item": E15_C},
])


def _e15_catalog_site(*, breadcrumbs: str = "none", unread: bool = False) -> list[tuple]:
    """`/catalog` → `/catalog/chairs` → `/catalog/chairs/oak-chair`, linked at every step.

    `breadcrumbs="all"` means EVERY eligible page carries a valid trail — including `/catalog`
    itself, which is an eligible page like any other. Leaving it out would make the case
    indistinguishable from `"some"`, and `"some"` is what E15-f8 exists to test.
    """
    nav = e15_chrome(("/", "Home"), ("/catalog", "Catalog"))
    trail_catalog = E15_VALID_TRAIL_CATALOG if breadcrumbs == "all" else ""
    trail_chairs = E15_VALID_TRAIL_CHAIRS if breadcrumbs in ("all", "some") else ""
    trail_oak = E15_VALID_TRAIL_OAK if breadcrumbs == "all" else ""
    pages = [
        (E15_ORIGIN + "/", _e15_document(title="Example", h1="Example", nav=nav), 200),
        (E15_C, _e15_document(title="Catalog", h1="Catalog", nav=nav,
                     body='<a href="/catalog/chairs">Chairs</a>',
                     head_extra=_e15_typed("CollectionPage", "Catalog") + trail_catalog), 200),
        (E15_CC, _e15_document(title="Chairs", h1="Chairs", nav=nav,
                      body='<a href="/catalog/chairs/oak-chair">Oak chair</a>',
                      head_extra=_e15_typed("CollectionPage", "Chairs") + trail_chairs), 200),
        (E15_CCO, _e15_document(title="Oak chair", h1="Oak chair", nav=nav,
                       head_extra=_e15_typed("Product", "Oak chair") + trail_oak), 200),
    ]
    if unread:
        pages.append((f"{E15_ORIGIN}/catalog/tables", None, None))
    return pages


E15_FIXTURES: dict[str, dict] = {
    # 1. one linked path-nested relationship → hierarchy, no breadcrumb → FAIL COMPLETE
    "E15-f1": {
        "input": "deep URLs /catalog/chairs/oak-chair; /catalog/chairs is a read page that links "
                 "to /catalog/chairs/oak-chair; no BreadcrumbList anywhere; eligible scope fully "
                 "measured",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(title="Example", h1="Example",
                                    nav=e15_chrome(("/", "Home"), ("/catalog/chairs", "Chairs"))), 200),
            (E15_CC, _e15_document(title="Chairs", h1="Chairs",
                          nav=e15_chrome(("/", "Home"), ("/catalog/chairs", "Chairs")),
                          body='<a href="/catalog/chairs/oak-chair">Oak chair</a>'), 200),
            (E15_CCO, _e15_document(title="Oak chair", h1="Oak chair",
                           nav=e15_chrome(("/", "Home"), ("/catalog/chairs", "Chairs"))), 200),
        ],
        "sitemap": "complete",
        "classification": "HIERARCHY_EVIDENT", "relationship_kind": "R1_path_nesting_with_link",
        "verified_relationships": 1, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "none",
        "verdict": "FAIL", "coverage": "COMPLETE", "rule": None,
        "unread_applicable": False, "conclusive": True, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": False, "finding": True,
        "notice": None,
    },
    # 2. one category-to-item relationship, flat URLs → hierarchy → FAIL COMPLETE
    "E15-f2": {
        "input": "flat URLs: /chairs is a LISTING page linking to ONE item page /oak-chair; "
                 "no breadcrumbs",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(title="Example", h1="Example",
                                    nav=e15_chrome(("/", "Home"), ("/chairs", "Chairs"))), 200),
            (f"{E15_ORIGIN}/chairs", _e15_document(title="Chairs", h1="Chairs",
                                          nav=e15_chrome(("/", "Home"), ("/chairs", "Chairs")),
                                          body='<a href="/oak-chair">Oak chair</a>',
                                          head_extra=_e15_typed("CollectionPage", "Chairs")), 200),
            (f"{E15_ORIGIN}/oak-chair", _e15_document(title="Oak chair", h1="Oak chair",
                                             nav=e15_chrome(("/", "Home"), ("/chairs", "Chairs")),
                                             head_extra=_e15_typed("Product", "Oak chair")), 200),
        ],
        "sitemap": "complete",
        "classification": "HIERARCHY_EVIDENT", "relationship_kind": "R2_category_to_item",
        "verified_relationships": 1, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "none",
        "verdict": "FAIL", "coverage": "COMPLETE", "rule": None,
        "unread_applicable": False, "conclusive": True, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": False, "finding": True,
        "notice": None,
        "expected": "v1.3 correction D: ONE verified category-to-item relationship proves "
                    "hierarchy; v1.2 required a count of item pages",
    },
    # 3. hierarchy with a valid BreadcrumbList on every hierarchy page → PASS COMPLETE
    "E15-f3": {
        "input": "hierarchy with a valid BreadcrumbList on every hierarchy page",
        "pages": _e15_catalog_site(breadcrumbs="all"),
        "sitemap": "complete",
        "classification": "HIERARCHY_EVIDENT", "relationship_kind": "R1_path_nesting_with_link",
        "verified_relationships": 2, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "all",
        "verdict": "PASS", "coverage": "COMPLETE", "rule": None,
        "unread_applicable": False, "conclusive": True, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": False, "finding": False,
        "notice": None,
    },
    # 4. one verified parent and one child is sufficient
    "E15-f4": {
        "input": "ONE verified parent with ONE verified child: menu group label /services is a "
                 "read page whose item links to /services/audit; no breadcrumbs",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(title="Example", h1="Example",
                                    nav=e15_chrome(("/", "Home"), ("/services", "Services"))), 200),
            (f"{E15_ORIGIN}/services", _e15_document(
                title="Services", h1="Services",
                nav=e15_chrome(("/", "Home"), ("/services", "Services")),
                body='<a href="/services/audit">Audit</a>'), 200),
            (f"{E15_ORIGIN}/services/audit", _e15_document(
                title="Audit", h1="Audit",
                nav=e15_chrome(("/", "Home"), ("/services", "Services"))), 200),
        ],
        "sitemap": "complete",
        "classification": "HIERARCHY_EVIDENT", "relationship_kind": "R1_path_nesting_with_link",
        "verified_relationships": 1, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "none",
        "verdict": "FAIL", "coverage": "COMPLETE", "rule": None,
        "unread_applicable": False, "conclusive": True, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": False, "finding": True,
        "notice": None,
        "expected": "v1.3 correction D: one verified parent-to-child relationship is sufficient; "
                    "no count threshold",
    },
    # 5. fully measured standalone flat site → A-09
    "E15-f5": {
        "input": "flat standalone site (home, about, pricing, contact); every eligible page read; "
                 "sitemap read completely; no listing pages and no path-extension with a "
                 "connecting reference",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(title="Example", h1="Example", nav=E15_NAV_FLAT), 200),
            (f"{E15_ORIGIN}/about", _e15_document(title="About", h1="About us", nav=E15_NAV_FLAT), 200),
            (f"{E15_ORIGIN}/pricing", _e15_document(title="Pricing", h1="Pricing", nav=E15_NAV_FLAT), 200),
            (f"{E15_ORIGIN}/contact", _e15_document(title="Contact", h1="Contact", nav=E15_NAV_FLAT), 200),
        ],
        "sitemap": "complete",
        "classification": "FLAT", "relationship_kind": None,
        "verified_relationships": 0, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "irrelevant",
        "verdict": "NOT_APPLICABLE", "coverage": "COMPLETE", "rule": "A-09",
        "unread_applicable": False, "conclusive": False, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": False,
        "notice": None,
    },
    # 6. grouped menu without verified targets plus incomplete coverage → UNKNOWN/PARTIAL
    "E15-f6": {
        "input": "flat URLs; a DOM-grouped menu (nested lists under non-link headings) whose "
                 "items do not resolve to a verified parent-to-child relationship; some eligible "
                 "pages not read",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(
                title="Example", h1="Example",
                nav=_e15_grouped_menu(("Solutions", (("/alpha", "Alpha"), ("/beta", "Beta"))),
                                 ("Company", (("/about", "About"),)))), 200),
            (f"{E15_ORIGIN}/alpha", _e15_document(
                title="Alpha", h1="Alpha",
                nav=_e15_grouped_menu(("Solutions", (("/alpha", "Alpha"), ("/beta", "Beta"))),
                                 ("Company", (("/about", "About"),)))), 200),
            (f"{E15_ORIGIN}/beta", None, None),
            (f"{E15_ORIGIN}/about", None, None),
        ],
        "sitemap": "complete",
        "classification": "UNKNOWN", "relationship_kind": None,
        "verified_relationships": 0, "eligible_coverage_complete": False,
        "breadcrumb_evidence": "irrelevant",
        "verdict": "NO_VERDICT", "coverage": "PARTIAL", "rule": None,
        "unread_applicable": True, "conclusive": False, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": False,
        "notice": "notice.breadcrumb.hierarchy_unknown",
        "expected": "grouped menu markup without verified parent-to-child targets is supporting "
                    "evidence only, and coverage is incomplete",
    },
    # 7. two pages read, sitemap unread → UNKNOWN/PARTIAL
    "E15-f7": {
        "input": "2 pages read, sitemap unread",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(title="Example", h1="Example",
                                    nav=e15_chrome(("/", "Home"), ("/about", "About"))), 200),
            (f"{E15_ORIGIN}/about", _e15_document(title="About", h1="About us",
                                         nav=e15_chrome(("/", "Home"), ("/about", "About"))), 200),
        ],
        "sitemap": "index_incomplete",
        "classification": "UNKNOWN", "relationship_kind": None,
        "verified_relationships": 0, "eligible_coverage_complete": False,
        "breadcrumb_evidence": "irrelevant",
        "verdict": "NO_VERDICT", "coverage": "PARTIAL", "rule": None,
        "unread_applicable": True, "conclusive": False, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": False,
        "notice": "notice.breadcrumb.hierarchy_unknown",
    },
    # 8. one valid BreadcrumbList on the hierarchical scope is sufficient
    "E15-f8": {
        "input": "hierarchy with ONE valid BreadcrumbList on /catalog/chairs and none on the "
                 "other measured hierarchy pages",
        "pages": _e15_catalog_site(breadcrumbs="some"),
        "sitemap": "complete",
        "classification": "HIERARCHY_EVIDENT", "relationship_kind": "R1_path_nesting_with_link",
        "verified_relationships": 2, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "some",
        "verdict": "PASS", "coverage": "COMPLETE", "rule": None,
        "unread_applicable": False, "conclusive": True, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": False,
        "notice": None,
        "expected": "no scored finding under the preserved current contract; informational "
                    "per-page coverage record only; no ratio or threshold",
    },
    # 9. verified nested navigation establishes hierarchy
    "E15-f9": {
        "input": "verified parent/child nested navigation: menu group label /services is a read "
                 "page and its items link to /services/a and /services/b",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(
                title="Example", h1="Example",
                nav=_e15_grouped_menu(("Services", (("/services/a", "A"), ("/services/b", "B"))))
                    + e15_chrome(("/", "Home"), ("/services", "Services"))), 200),
            (f"{E15_ORIGIN}/services", _e15_document(
                title="Services", h1="Services",
                nav=e15_chrome(("/", "Home"), ("/services", "Services")),
                body='<a href="/services/a">A</a><a href="/services/b">B</a>'), 200),
            (f"{E15_ORIGIN}/services/a", _e15_document(
                title="A", h1="Service A",
                nav=e15_chrome(("/", "Home"), ("/services", "Services"))), 200),
            (f"{E15_ORIGIN}/services/b", _e15_document(
                title="B", h1="Service B",
                nav=e15_chrome(("/", "Home"), ("/services", "Services"))), 200),
        ],
        "sitemap": "complete",
        "classification": "HIERARCHY_EVIDENT", "relationship_kind": "R1_path_nesting_with_link",
        "verified_relationships": 2, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "none",
        "verdict": "FAIL", "coverage": "COMPLETE", "rule": None,
        "unread_applicable": False, "conclusive": True, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": False, "finding": True,
        "notice": None,
    },
    # 10. proven hierarchy, no valid breadcrumb, unread eligible pages → FAIL/PARTIAL
    "E15-f10": {
        "input": "deep URLs with a verified relationship, no BreadcrumbList on the measured "
                 "hierarchy pages, and other eligible hierarchy pages not read",
        "pages": _e15_catalog_site(breadcrumbs="none", unread=True),
        "sitemap": "complete",
        "classification": "HIERARCHY_EVIDENT", "relationship_kind": "R1_path_nesting_with_link",
        "verified_relationships": 2, "eligible_coverage_complete": False,
        "breadcrumb_evidence": "none",
        "verdict": "FAIL", "coverage": "PARTIAL", "rule": None,
        "unread_applicable": True, "conclusive": False, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": True,
        "notice": "notice.breadcrumb.hierarchy_unknown",
        "expected": "FAIL + PARTIAL: the finding stands and the unread eligible scope is named",
    },
    # 11. unrelated deep URLs without a connecting reference → UNKNOWN/PARTIAL
    "E15-f11": {
        "input": "deep URLs /a/b and /c/d with NO connecting reference between any eligible "
                 "pages; some eligible pages unread",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(title="Example", h1="Example",
                                    nav=e15_chrome(("/", "Home"))), 200),
            (f"{E15_ORIGIN}/a/b", _e15_document(title="A B", h1="A B", nav=e15_chrome(("/", "Home"))), 200),
            (f"{E15_ORIGIN}/c/d", _e15_document(title="E15_C D", h1="E15_C D", nav=e15_chrome(("/", "Home"))), 200),
            (f"{E15_ORIGIN}/e/f", None, None),
        ],
        "sitemap": "complete",
        "classification": "UNKNOWN", "relationship_kind": None,
        "verified_relationships": 0, "eligible_coverage_complete": False,
        "breadcrumb_evidence": "irrelevant",
        "verdict": "NO_VERDICT", "coverage": "PARTIAL", "rule": None,
        "unread_applicable": True, "conclusive": False, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": False,
        "notice": "notice.breadcrumb.hierarchy_unknown",
        "expected": "v1.3 correction D: unrelated URL depth alone does not prove semantic "
                    "hierarchy",
    },
    # 12. pagination-only blog → FLAT/A-09
    "E15-f12": {
        "input": "a blog index with pagination /blog/page/2, /blog/page/3 and nothing else; "
                 "every eligible page read; sitemap read completely",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(title="Example", h1="Example",
                                    nav=e15_chrome(("/", "Home"), ("/blog", "Blog"))), 200),
            (f"{E15_ORIGIN}/blog", _e15_document(
                title="Blog", h1="Blog", nav=e15_chrome(("/", "Home"), ("/blog", "Blog")),
                body='<a href="/blog/page/2">2</a><a href="/blog/page/3">3</a>'), 200),
            (f"{E15_ORIGIN}/blog/page/2", _e15_document(
                title="Blog page 2", h1="Blog", nav=e15_chrome(("/", "Home"), ("/blog", "Blog")),
                body='<a href="/blog/page/3">3</a>'), 200),
            (f"{E15_ORIGIN}/blog/page/3", _e15_document(
                title="Blog page 3", h1="Blog",
                nav=e15_chrome(("/", "Home"), ("/blog", "Blog"))), 200),
        ],
        "sitemap": "complete",
        "classification": "FLAT", "relationship_kind": None,
        "verified_relationships": 0, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "irrelevant",
        "verdict": "NOT_APPLICABLE", "coverage": "COMPLETE", "rule": "A-09",
        "unread_applicable": False, "conclusive": False, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": False,
        "notice": None,
        "expected": "pagination is excluded from eligibility and cannot manufacture a hierarchy",
    },
    # 13. locale roots and one-level localized pages → FLAT/A-09
    "E15-f13": {
        "input": "six locale roots /de, /fr, /es, /ru, /uk and their one-level pages; declared "
                 "locales stripped; every eligible page read; sitemap read completely",
        "pages": None,  # built by `_e15_localized()` below: it needs the helpers defined after this
        "sitemap": "complete",
        "classification": "FLAT", "relationship_kind": None,
        "verified_relationships": 0, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "irrelevant",
        "verdict": "NOT_APPLICABLE", "coverage": "COMPLETE", "rule": "A-09",
        "unread_applicable": False, "conclusive": False, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": False,
        "notice": None,
        "expected": "locale prefixes are stripped and a locale root is not a hierarchy parent",
    },
    # 14. no eligible content pages → A-10
    "E15-f14": {
        "input": "every read route is a funnel, account, admin or error route; no eligible "
                 "content page exists",
        "pages": [
            (f"{E15_ORIGIN}/checkout", _e15_document(title="Checkout", h1="Checkout", noindex=True,
                                            nav=e15_chrome(("/checkout", "Checkout"))), 200),
            (f"{E15_ORIGIN}/account", _e15_document(title="Account", h1="Account", noindex=True,
                                           nav=e15_chrome(("/account", "Account"))), 200),
            (f"{E15_ORIGIN}/admin", _e15_document(title="Admin", h1="Admin", noindex=True,
                                         nav=e15_chrome(("/admin", "Admin"))), 200),
            (f"{E15_ORIGIN}/processing", _e15_document(title="Processing", h1="Processing",
                                              nav=e15_chrome(("/processing", "Processing"))), 200),
        ],
        "sitemap": "complete",
        "classification": "NOT_APPLICABLE", "relationship_kind": None,
        "verified_relationships": 0, "eligible_coverage_complete": True, "no_eligible_pages": True,
        "breadcrumb_evidence": "irrelevant",
        "verdict": "NOT_APPLICABLE", "coverage": "COMPLETE", "rule": "A-10",
        "unread_applicable": False, "conclusive": False, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": False,
        "notice": None,
        "expected": "documented eligibility makes breadcrumbs genuinely irrelevant",
    },
    # 15. noindex funnel chain cannot manufacture hierarchy → FLAT/A-09
    "E15-f15": {
        "input": "a funnel chain /buy -> /checkout -> /checkout/confirm, all noindex funnel "
                 "routes; every eligible content page read and flat",
        "pages": [
            (E15_ORIGIN + "/", _e15_document(title="Example", h1="Example",
                                    nav=e15_chrome(("/", "Home"), ("/about", "About")),
                                    body='<a href="/buy">Buy</a>'), 200),
            (f"{E15_ORIGIN}/about", _e15_document(title="About", h1="About us",
                                         nav=e15_chrome(("/", "Home"), ("/about", "About"))), 200),
            (f"{E15_ORIGIN}/buy", _e15_document(title="Buy", h1="Buy", noindex=True,
                                       nav=e15_chrome(("/", "Home"), ("/about", "About")),
                                       body='<a href="/checkout">Checkout</a>'), 200),
            (f"{E15_ORIGIN}/checkout", _e15_document(
                title="Checkout", h1="Checkout", noindex=True,
                nav=e15_chrome(("/", "Home"), ("/about", "About")),
                body='<a href="/checkout/confirm">Confirm</a>'), 200),
            (f"{E15_ORIGIN}/checkout/confirm", _e15_document(
                title="Confirm", h1="Confirm", noindex=True,
                nav=e15_chrome(("/", "Home"), ("/about", "About"))), 200),
        ],
        "sitemap": "complete",
        "classification": "FLAT", "relationship_kind": None,
        "verified_relationships": 0, "eligible_coverage_complete": True,
        "breadcrumb_evidence": "irrelevant",
        "verdict": "NOT_APPLICABLE", "coverage": "COMPLETE", "rule": "A-09",
        "unread_applicable": False, "conclusive": False, "passed_checks_entry": False,
        "numeric_success": False, "coverage_or_partial_metadata": True, "finding": False,
        "notice": None,
        "expected": "non-search funnel routes are excluded from eligibility and cannot "
                    "manufacture a hierarchy",
    },
}

E15_LOCALES = ("de", "fr", "es", "ru", "uk")


def _e15_hreflang(*codes: str) -> str:
    return "".join(f'<link rel="alternate" hreflang="{code}" href="{E15_ORIGIN}/{code}/">'
                   for code in ("en", *codes))


def _e15_localized() -> list[tuple]:
    """Locale roots plus one-level pages under each — the classic six-copy shape.

    Every path is one segment deep AFTER the declared locale is stripped, so nothing extends
    anything: `/de` is the root of its locale, not the parent of `/de/about`.
    """
    declared = _e15_hreflang(*E15_LOCALES)
    nav = e15_chrome(("/", "Home"), *[(f"/{code}/", code.upper()) for code in E15_LOCALES])
    pages = [(E15_ORIGIN + "/", _e15_document(title="Example", h1="Example", nav=nav,
                                     head_extra=declared), 200)]
    for code in E15_LOCALES:
        pages.append((f"{E15_ORIGIN}/{code}/", _e15_document(
            title=f"Example {code}", h1="Example", lang=code, nav=nav,
            head_extra=declared, body=f'<a href="/{code}/about">About</a>'), 200))
        pages.append((f"{E15_ORIGIN}/{code}/about", _e15_document(
            title=f"About {code}", h1="About", lang=code, nav=nav, head_extra=declared), 200))
    return pages


E15_FIXTURES["E15-f13"]["pages"] = _e15_localized()
E15_FIXTURES["E15-f13"]["locales_declared"] = ["en", *E15_LOCALES]

IDS = tuple(E15_FIXTURES)


def e15_build(fixture_id: str):
    """A real `SiteContext` for one hierarchy fixture, plus the URLs known but never fetched.

    Unfetched URLs are what makes eligible coverage incomplete. They reach the engine the two ways
    a real crawl learns about a URL and does not open it: a chrome link, and a sitemap entry. Both
    are recorded, because the classifier must treat them as eligible-but-unread rather than as
    pages that do not exist.
    """
    spec = E15_FIXTURES[fixture_id]
    fetched, known_unread = [], []
    for url, html, status in spec["pages"]:
        if status is None:
            known_unread.append(url)
            continue
        fetched.append(page_from_html(html, url=url))

    _e15_assign_crawl_depth(fetched)
    ctx = context(*fetched)
    ctx.entry_url = E15_ORIGIN + "/"
    ctx.origin = E15_ORIGIN
    if spec.get("locales_declared"):
        ctx.locales_declared = list(spec["locales_declared"])

    every_url = [url for url, _html, _status in spec["pages"]]
    if spec["sitemap"] == "complete":
        ctx.sitemap = SitemapInfo(exists=True, status_code=200, url=f"{E15_ORIGIN}/sitemap.xml",
                                  url_count=len(every_url), urls=list(every_url),
                                  is_index=False, index_complete=True)
    elif spec["sitemap"] == "index_incomplete":
        # The collector says so itself: an index whose children were not all opened. This is the
        # one source the engine accepts for "part of the input is unread" (E-05).
        ctx.sitemap = SitemapInfo(exists=True, status_code=200, url=f"{E15_ORIGIN}/sitemap.xml",
                                  url_count=len(every_url), urls=list(every_url),
                                  is_index=True, children_total=4,
                                  children_read=[f"{E15_ORIGIN}/sitemap-1.xml"], index_complete=False)
    else:  # pragma: no cover — every fixture declares one of the two
        raise AssertionError(f"{fixture_id}: unknown sitemap mode {spec['sitemap']!r}")
    return ctx, known_unread


def _e15_assign_crawl_depth(pages: list) -> None:
    """Crawl depth by breadth-first search from the entry, the way the crawler assigns it.

    It matters that this is CRAWL depth and not path depth: the accepted engine's defect is that it
    reads `page.depth > 0` as "this site has a hierarchy", and a fixture that hand-assigned path
    depth would be reproducing my description of the defect instead of the defect. Every page here
    is reached from the entry through links the extractor actually found, so a flat site whose menu
    links four pages gives four pages at depth 1 — which is exactly the case the accepted rule
    misreads as a hierarchy.
    """
    by_url = {normalize(page.url): page for page in pages}
    entry = normalize(E15_ORIGIN + "/")
    depth = {entry: 0}
    frontier = [entry]
    while frontier:
        nxt = []
        for key in frontier:
            page = by_url.get(key)
            if page is None:
                continue
            for link in getattr(page, "links", ()) or ():
                target = normalize(getattr(link, "url", "") or "")
                if target in by_url and target not in depth:
                    depth[target] = depth[key] + 1
                    nxt.append(target)
        frontier = nxt
    for key, page in by_url.items():
        # A page no link reached is still a page the crawl read — from the sitemap, at depth 1.
        page.depth = depth.get(key, 1)


def _e15_valid(markup: str, entry: str) -> bool:
    """Чи дійсний слід у цьому шматку розмітки — за спільним валідатором."""
    page = page_from_html(_e15_document(title="t", h1="h", head_extra=markup),
                          url=f"{E15_ORIGIN}/catalog/chairs/oak-chair")
    return any(trail.valid for trail in breadcrumbs.trails_on(page, entry=entry))

E15_IDS = tuple(E15_FIXTURES)
E15_VALIDITY_IDS = tuple(E15_VALIDITY)


def _e15_decision(fixture_id: str):
    """Рішення класифікатора для однієї фікстури."""
    ctx, _unread = e15_build(fixture_id)
    return hierarchy.classify(ctx), ctx


def _e15_row(ctx):
    """Рядок застосовності `ai.schema.breadcrumb` ПІСЛЯ знахідок.

    `build_evidence` рахує застосовність із контексту, де знахідок ще
    немає; вердикт дописує `finalise`, коли вони зʼявились. Читати
    дофінальний рядок означало б питати не те, що бачить читач звіту.
    """
    outcome = rescore(ctx)
    evidence = build_evidence(outcome.context)
    block = applicability.finalise(evidence.get("applicability") or {}, outcome.issues)
    return block.get("ai.schema.breadcrumb") or {}, outcome


@pytest.mark.parametrize("fixture_id", E15_IDS)
def test_e15_hierarchy_fixture_matches_the_contract(fixture_id):
    """Кожна з пʼятнадцяти фікстур ієрархії — на КОЖНІЙ оголошеній поверхні.

    Порівнюються не лише вердикт і знахідка: класифікація, покриття,
    завершеність, непрочитане, код причини, кількість перевірених звʼязків
    і їхній вид. Випадок, який зійшовся вердиктом і розійшовся покриттям,
    не пройдений.
    """
    spec = E15_FIXTURES[fixture_id]
    decision, ctx = _e15_decision(fixture_id)
    row, outcome = _e15_row(ctx)

    assert decision.classification == spec["classification"]
    assert row["verdict"] == spec["verdict"]
    assert row["coverage"] == spec["coverage"]
    assert decision.conclusive is spec["conclusive"]
    assert bool(decision.unread_applicable) is spec["unread_applicable"]
    assert decision.rule == spec["rule"]
    if spec["rule"]:
        assert spec["rule"] in (row.get("rules") or {})
    assert decision.coverage_complete is spec["eligible_coverage_complete"]

    emitted = [i for i in outcome.issues if i.code == "ai.schema.breadcrumb"]
    assert bool(emitted) is spec["finding"]

    pairs = {(r.parent, r.child) for r in decision.relationships}
    assert len(pairs) == spec["verified_relationships"]
    kinds = {k for r in decision.relationships for k in r.kinds}
    if spec["relationship_kind"]:
        assert spec["relationship_kind"] in kinds
    else:
        assert kinds == set()


@pytest.mark.parametrize("case_id", E15_VALIDITY_IDS)
def test_e15_breadcrumblist_validity_fixture_matches_the_contract(case_id):
    """Девʼять випадків дійсності — за задокументованим контрактом Google."""
    case = E15_VALIDITY[case_id]
    page = page_from_html(
        _e15_document(title="Oak chair", h1="Oak chair",
                      head_extra=e15_breadcrumb_ld(case["items"])),
        url=case["page_url"])
    trails = breadcrumbs.trails_on(page, entry=case["entry"])
    assert any(t.valid for t in trails) is case["expected_valid"], case["input"]


# ── ієрархія: що НЕ доводить її ───────────────────────────────────────────

def test_url_depth_alone_is_not_a_hierarchy():
    """Мутація 1. Глибокі адреси без жодної зʼєднувальної згадки.

    `/a/b` і `/c/d` лежать глибоко й не мають між собою нічого. Правило,
    що читає глибину, назве це ієрархією; правило контракту — ні. Саме на
    цьому прийнятий двигун помилявся на кожному плаcкому сайті.
    """
    decision, _ctx = _e15_decision("E15-f11")
    assert decision.relationships == ()
    assert decision.classification == hierarchy.UNKNOWN


def test_deep_urls_with_complete_coverage_are_flat_not_hierarchical():
    """Мутація 1, друга половина: те саме, але прочитане ціле.

    Тут покриття повне, тож «не знаємо» перетворюється на ствердне
    «звʼязку немає» — і це FLAT, а не ієрархія. Без цього тесту правило,
    що вважає глибину доказом, лишилося б непоміченим на повному покритті.
    """
    ctx, _unread = e15_build("E15-f11")
    ctx.sitemap.urls = [p.url for p in ctx.ok_pages]
    decision = hierarchy.classify(ctx)
    assert decision.relationships == ()
    assert decision.classification == hierarchy.FLAT
    assert decision.rule == hierarchy.A09_NO_RELATIONSHIP


def test_one_verified_relationship_is_enough():
    """Мутації 2 і 3: жодного мінімуму — ані звʼязків, ані дітей.

    Один батько, одна дитина, один звʼязок. Попередня редакція контракту
    вимагала «три або більше»; число прибрано, і замінити його іншим не
    можна.
    """
    for fixture_id in ("E15-f2", "E15-f4"):
        decision, _ctx = _e15_decision(fixture_id)
        assert len(decision.relationships) == 1
        assert decision.classification == hierarchy.HIERARCHY_EVIDENT


def test_a_grouped_menu_without_verified_targets_proves_nothing():
    """Мутація 4. Вкладені списки під заголовком, який не є сторінкою.

    Групування — це оформлення. Батьком може бути лише сторінка, яку ми
    бачили, і `Solutions` тут нею не є.
    """
    decision, _ctx = _e15_decision("E15-f6")
    assert decision.relationships == ()
    assert decision.classification == hierarchy.UNKNOWN


def test_pagination_cannot_manufacture_a_hierarchy():
    """Мутація 5. `/blog/page/2` — це та сама стрічка з іншого місця."""
    decision, _ctx = _e15_decision("E15-f12")
    assert decision.relationships == ()
    assert decision.classification == hierarchy.FLAT
    assert not any("page" in url for url in decision.eligible)


def test_locale_prefixes_cannot_manufacture_a_hierarchy():
    """Мутація 6. `/de` не батько `/de/about`.

    Шляхи порівнюються вже без ОГОЛОШЕНОЇ мови (правило G4a), тож обидві
    адреси зводяться до кореня й до `/about` — і жодна не продовжує іншу.
    """
    decision, _ctx = _e15_decision("E15-f13")
    assert decision.relationships == ()
    assert decision.classification == hierarchy.FLAT
    # Мовний корінь придатною сторінкою не є взагалі.
    assert not any(url.rstrip("/").endswith(("/de", "/fr", "/es", "/ru", "/uk"))
                   for url in decision.eligible)


def test_funnel_account_admin_and_error_routes_cannot_manufacture_a_hierarchy():
    """Мутація 7. Ланцюг `/buy → /checkout → /checkout/confirm` вкладений
    ідеально — і жодна його ланка не придатна, тож ієрархії з нього не
    виходить. Це рівно той випадок, у якому глибина виглядає найпереконливіше.
    """
    decision, _ctx = _e15_decision("E15-f15")
    assert decision.relationships == ()
    assert decision.classification == hierarchy.FLAT
    assert not any("checkout" in url or "/buy" in url for url in decision.eligible)


def test_incomplete_coverage_is_never_flat():
    """Мутація 8. Плаский сайт і недочитаний сайт виглядають однаково.

    Різниця в тому, чи ми ДИВИЛИСЯ, і вона мусить бути в стані, а не лише
    в наміри автора.
    """
    for fixture_id in ("E15-f6", "E15-f7", "E15-f11"):
        decision, _ctx = _e15_decision(fixture_id)
        assert decision.coverage_complete is False
        assert decision.classification == hierarchy.UNKNOWN
        assert decision.rule is None


def test_a_one_page_site_is_flat_and_not_a_site_without_content():
    """A-09 і A-10 — різні відповіді, і односторінковий сайт дає першу.

    Знайдено на A/B, не на фікстурах: пʼять сайтів вибірки віддали рівно
    головну сторінку з кодом 200 і чули «придатних сторінок вмісту немає».
    Вміст у них є — немає ієрархії, а це інша річ. Канонічна фікстура A-10
    складена лише з воронки й адмінки, тож цей випадок вона не покривала.
    """
    home = page_from_html(
        _e15_document(title="Studio", h1="Studio", nav=e15_chrome(("/", "Home"))),
        url=f"{E15_ORIGIN}/")
    ctx = context(home)
    ctx.sitemap = SitemapInfo(exists=True, status_code=200, urls=[f"{E15_ORIGIN}/"],
                              index_complete=True)
    decision = hierarchy.classify(ctx)

    assert decision.content == (f"{E15_ORIGIN}/",)
    assert decision.eligible == ()
    assert decision.classification == hierarchy.FLAT
    assert decision.rule == hierarchy.A09_NO_RELATIONSHIP

    # А сайт, у якого прочитані маршрути справді не є вмістом, лишається A-10.
    funnel = page_from_html(
        _e15_document(title="Checkout", h1="Checkout", noindex=True,
                      nav=e15_chrome(("/checkout", "Checkout"))),
        url=f"{E15_ORIGIN}/checkout")
    closed = context(funnel)
    closed.sitemap = SitemapInfo(exists=True, status_code=200,
                                 urls=[f"{E15_ORIGIN}/checkout"], index_complete=True)
    shut = hierarchy.classify(closed)
    assert shut.content == ()
    assert shut.classification == hierarchy.NOT_APPLICABLE
    assert shut.rule == hierarchy.A10_NO_ELIGIBLE_PAGES


def test_no_eligible_pages_is_a10_and_not_a09():
    """Мутація 9. «Плаский сайт» і «сайт без придатних сторінок» — різні
    відповіді, і код причини має їх розрізняти.
    """
    decision, _ctx = _e15_decision("E15-f14")
    assert decision.eligible == ()
    assert decision.classification == hierarchy.NOT_APPLICABLE
    assert decision.rule == hierarchy.A10_NO_ELIGIBLE_PAGES
    flat, _ctx = _e15_decision("E15-f5")
    assert flat.rule == hierarchy.A09_NO_RELATIONSHIP


def test_a_category_to_item_link_is_a_hierarchy_whatever_the_urls_look_like():
    """R2 не дивиться на форму адрес: `/chairs → /oak-chair` плаский за
    адресами й ієрархічний за змістом."""
    decision, _ctx = _e15_decision("E15-f2")
    kinds = {k for r in decision.relationships for k in r.kinds}
    assert hierarchy.R2 in kinds
    assert all("/" not in url.replace("https://example.com/", "") for url in decision.eligible)


def test_the_childs_own_markup_can_name_its_parent():
    """Друга зʼєднувальна згадка R1: батько не посилається на дитину, але
    дитина сама каже, хто її батько (`isPartOf`)."""
    parent_url = "https://example.com/guides"
    child_url = "https://example.com/guides/setup"
    nav = e15_chrome(("/", "Home"), ("/guides", "Guides"))
    parent = page_from_html(_e15_document(title="Guides", h1="Guides", nav=nav), url=parent_url)
    child = page_from_html(
        _e15_document(title="Setup", h1="Setup", nav=nav,
                      head_extra=e15_ld('{"@context":"https://schema.org","@type":"Article",'
                                        '"name":"Setup","isPartOf":{"@id":"' + parent_url + '"}}')),
        url=child_url)
    ctx = context(page_from_html(_e15_document(title="Home", h1="Home", nav=nav),
                                 url="https://example.com/"), parent, child)
    ctx.sitemap = SitemapInfo(exists=True, status_code=200, urls=[
        "https://example.com/", parent_url, child_url], index_complete=True)
    decision = hierarchy.classify(ctx)
    assert decision.classification == hierarchy.HIERARCHY_EVIDENT
    assert any("structured data" in r.reference for r in decision.relationships)


def test_a_visible_breadcrumb_trail_can_connect_a_child_to_its_parent():
    """Мутація 20. Третя зʼєднувальна згадка R1 — видимий слід дитини.

    Тест ламається двічі: якщо `breadcrumb_ui` перестає витягуватись, і
    якщо класифікатор перестає його питати. Та сама сторінка без розмітки
    сліду й без видимого сліду звʼязку не дає.
    """
    parent_url = "https://example.com/guides"
    child_url = "https://example.com/guides/setup"
    nav = e15_chrome(("/", "Home"))
    home = page_from_html(_e15_document(title="Home", h1="Home", nav=nav),
                          url="https://example.com/")
    parent = page_from_html(_e15_document(title="Guides", h1="Guides", nav=nav), url=parent_url)
    with_ui = page_from_html(
        _e15_document(title="Setup", h1="Setup", nav=nav,
                      breadcrumb_nav=e15_breadcrumb_ui(("/guides", "Guides"))), url=child_url)
    assert with_ui.breadcrumb_ui is True

    ctx = context(home, parent, with_ui)
    ctx.sitemap = SitemapInfo(exists=True, status_code=200,
                              urls=["https://example.com/", parent_url, child_url],
                              index_complete=True)
    assert hierarchy.classify(ctx).classification == hierarchy.HIERARCHY_EVIDENT

    plain = page_from_html(
        _e15_document(title="Setup", h1="Setup", nav=nav,
                      body='<a href="/guides">Guides</a>'), url=child_url)
    assert plain.breadcrumb_ui is False
    bare = context(home, parent, plain)
    bare.sitemap = ctx.sitemap
    assert hierarchy.classify(bare).classification == hierarchy.FLAT


def test_breadcrumb_ui_is_read_from_attributes_and_never_from_page_text():
    """Мутація 20, друга половина. Абзац ПРО навігацію — не навігація.

    Той самий клас помилки, що колись зараховував речення «ми
    використовуємо reCAPTCHA» за встановлений захист форми.
    """
    prose = page_from_html(
        _e15_document(title="Article", h1="Article",
                      body="<p>This article explains how a breadcrumb trail works.</p>"),
        url="https://example.com/a")
    assert prose.breadcrumb_ui is False
    marked = page_from_html(
        _e15_document(title="Page", h1="Page",
                      breadcrumb_nav='<ol class="breadcrumb"><li><a href="/">Home</a></li></ol>'),
        url="https://example.com/b")
    assert marked.breadcrumb_ui is True


# ── дійсність `BreadcrumbList` ────────────────────────────────────────────

def test_presence_of_a_breadcrumblist_is_not_validity():
    """Мутація 10. Прийнятий двигун питав лише «чи є вузол».

    Пʼять із девʼяти канонічних слідів присутні й недійсні. Тест тримає
    саме цю різницю: `BreadcrumbList` на сторінці є в усіх девʼятьох.
    """
    from app.audit.checks.ai_ready import types_on

    invalid = [case_id for case_id in E15_VALIDITY_IDS
               if not E15_VALIDITY[case_id]["expected_valid"]]
    assert len(invalid) == 5
    for case_id in invalid:
        case = E15_VALIDITY[case_id]
        page = page_from_html(
            _e15_document(title="t", h1="h", head_extra=e15_breadcrumb_ld(case["items"])),
            url=case["page_url"])
        assert "BreadcrumbList" in types_on(page)
        assert not any(t.valid for t in breadcrumbs.trails_on(page, entry=case["entry"]))


def test_the_final_item_url_may_be_omitted():
    """Мутації 11 і 14 разом, і вони протилежні.

    Останньому пункту адреса НЕ потрібна (V5); будь-якому іншому —
    потрібна (V4). Правило, що вимагає адресу скрізь, завалить перший
    випадок; правило, що не вимагає ніде, — другий.
    """
    entry = "https://example.com/"
    tail_free = e15_breadcrumb_ld([
        {"position": 1, "name": "Home", "item": entry},
        {"position": 2, "name": "Catalog", "item": "https://example.com/catalog"},
        {"position": 3, "name": "Oak chair"}])
    middle_free = e15_breadcrumb_ld([
        {"position": 1, "name": "Home", "item": entry},
        {"position": 2, "name": "Catalog"},
        {"position": 3, "name": "Oak chair", "item": "https://example.com/catalog/oak"}])
    assert _e15_valid(tail_free, entry) is True
    assert _e15_valid(middle_free, entry) is False


def test_the_final_crumb_need_not_point_at_the_audited_page():
    """Мутація 12. Слід, що закінчується на батьківському розділі, дійсний."""
    entry = "https://example.com/"
    ancestor_tail = e15_breadcrumb_ld([
        {"position": 1, "name": "Home", "item": entry},
        {"position": 2, "name": "Catalog", "item": "https://example.com/catalog"}])
    assert _e15_valid(ancestor_tail, entry) is True


def test_scope_is_the_shared_site_predicate_and_not_literal_origin_equality():
    """Мутація 13. Той самий сайт — це `site_scope`, а не збіг рядків.

    `http://example.com` і `https://www.example.com:443` — один сайт, і
    відповідає на це один модуль на весь двигун. Чужий домен лишається
    чужим: інакше тест проходив би від правила «приймати все».
    """
    entry = "http://example.com/"
    aliased = e15_breadcrumb_ld([
        {"position": 1, "name": "Home", "item": "https://www.example.com/"},
        {"position": 2, "name": "Catalog", "item": "https://www.example.com:443/catalog"}])
    foreign = e15_breadcrumb_ld([
        {"position": 1, "name": "Home", "item": "https://www.example.com/"},
        {"position": 2, "name": "Partner", "item": "https://other-site.example.net/x"},
        {"position": 3, "name": "Oak chair"}])
    assert _e15_valid(aliased, entry) is True
    assert _e15_valid(foreign, entry) is False


def test_positions_must_ascend_consecutively_in_trail_order():
    """Мутація 15. `1, 3, 2` недійсне, і пересортувати за `position` не можна.

    Пересортувати означало б полагодити за сайт його ж помилку й
    зарахувати слід, якого пошук не прийме.
    """
    entry = "https://example.com/"
    shuffled = e15_breadcrumb_ld([
        {"position": 1, "name": "Home", "item": entry},
        {"position": 3, "name": "Catalog", "item": "https://example.com/catalog"},
        {"position": 2, "name": "Oak", "item": "https://example.com/oak"}])
    from_two = e15_breadcrumb_ld([
        {"position": 2, "name": "Home", "item": entry},
        {"position": 3, "name": "Catalog", "item": "https://example.com/catalog"}])
    textual = e15_breadcrumb_ld([
        {"position": "1", "name": "Home", "item": entry},
        {"position": "2", "name": "Catalog", "item": "https://example.com/catalog"}])
    assert _e15_valid(shuffled, entry) is False
    assert _e15_valid(from_two, entry) is False
    assert _e15_valid(textual, entry) is False


def test_every_item_needs_a_name_from_either_documented_place():
    """Мутація 16. Назва береться з `ListItem.name` або з `item.name` —
    обидві форми канонічні, а її відсутність недійсна в обох."""
    entry = "https://example.com/"
    nested_name = e15_breadcrumb_ld([
        {"position": 1, "item_object": {"id": entry, "name": "Home"}},
        {"position": 2, "item_object": {"id": "https://example.com/catalog",
                                        "name": "Catalog"}}])
    nameless = e15_breadcrumb_ld([
        {"position": 1, "name": "Home", "item": entry},
        {"position": 2, "item": "https://example.com/catalog"}])
    assert _e15_valid(nested_name, entry) is True
    assert _e15_valid(nameless, entry) is False


def test_a_single_item_trail_is_not_a_trail():
    """Мутація 17. Один пункт — це не шлях, і це єдине число контракту."""
    entry = "https://example.com/"
    one = e15_breadcrumb_ld([{"position": 1, "name": "Home", "item": entry}])
    two = e15_breadcrumb_ld([{"position": 1, "name": "Home", "item": entry},
                             {"position": 2, "name": "Catalog"}])
    assert _e15_valid(one, entry) is False
    assert _e15_valid(two, entry) is True


def test_a_breadcrumblist_is_found_in_every_canonical_shape():
    """Сайти пишуть слід голим вузлом, усередині `@graph` і вкладеним у
    `WebPage`. Це три форми одного й того ж, і пропустити дві з них
    означало б назвати відсутнім те, що є."""
    entry = "https://example.com/"
    items = [{"position": 1, "name": "Home", "item": entry},
             {"position": 2, "name": "Catalog", "item": "https://example.com/catalog"}]
    assert _e15_valid(e15_breadcrumb_ld(items), entry) is True
    assert _e15_valid(e15_breadcrumb_ld(items, container="graph"), entry) is True


# ── межа знахідки: жодної частки ──────────────────────────────────────────

def test_one_valid_breadcrumblist_settles_the_claim():
    """Мутації 18 і 19. Одного дійсного сліду досить, і частки тут немає.

    На E15-f8 слід стоїть на ОДНІЙ придатній сторінці з трьох. Правило з
    часткою («більшість сторінок мусить мати крихти») дало б FAIL;
    правило контракту дає PASS і лишає посторінкове покриття
    інформаційним.
    """
    decision, ctx = _e15_decision("E15-f8")
    row, outcome = _e15_row(ctx)
    assert len(decision.valid_trail_pages) == 1
    assert len(decision.eligible) > len(decision.valid_trail_pages)
    assert row["verdict"] == ClaimVerdict.PASS.value
    assert row["coverage"] == Coverage.COMPLETE.value
    assert [i for i in outcome.issues if i.code == "ai.schema.breadcrumb"] == []
    # Посторінкове покриття є — але як перелік, а не як число, з яким
    # щось порівнюють.
    coverage = row["detail"]["breadcrumb_coverage"]
    assert {record["url"] for record in coverage} == set(decision.eligible)


def test_no_ratio_or_percentage_appears_in_the_decision():
    """Ділянка 11 інструкції: жодної частки в самому рішенні.

    Перевіряється доказ, який бачить читач: у ньому не сміє бути ані
    дробу, ані поля, чия назва зізнається, що воно частка.
    """
    forbidden = {"ratio", "percent", "share", "rate", "fraction", "proportion"}

    def offences(node, path=""):
        """Every place the evidence admits a proportion — by name or by being fractional."""
        if isinstance(node, dict):
            found = []
            for key, value in node.items():
                if set(str(key).lower().split("_")) & forbidden:
                    found.append(f"{path}.{key}")
                found.extend(offences(value, f"{path}.{key}"))
            return found
        if isinstance(node, list):
            return [hit for item in node for hit in offences(item, path)]
        return [path] if isinstance(node, float) else []

    for fixture_id in E15_IDS:
        decision, _ctx = _e15_decision(fixture_id)
        assert offences(decision.as_evidence()) == [], fixture_id


def test_the_exact_accepted_g5a_rule_is_rejected():
    """Мутація 23. Відновити прийняту поведінку — і тести мусять впасти.

    Прийняте правило: «кожна прочитана сторінка глибша за вхідну — це
    ієрархія; будь-який `BreadcrumbList` її закриває». Тут воно
    застосовується до плаского сайту буквально, і видно, що воно дало б
    знахідку там, де контракт її забороняє.
    """
    ctx, _unread = e15_build("E15-f5")
    accepted_inner = [p for p in applicability.pages_for(ctx, "ai.schema.breadcrumb")
                      if p.depth > 0]
    assert accepted_inner, "фікстура має відтворювати випадок, на якому старе правило спрацьовує"
    decision = hierarchy.classify(ctx)
    assert decision.classification == hierarchy.FLAT
    assert decision.finding is False


# ── централізація ─────────────────────────────────────────────────────────

def test_the_check_duplicates_no_rule_of_its_own():
    """Мутація 22. Чек не має власних меж сайту, нормалізації й порогів.

    Перевіряється джерело: у тілі `BreadcrumbCheck.run` не сміє бути ані
    роботи з адресами, ані звернення до глибини, ані числа. Він питає
    класифікатор і віддає його доказ.
    """
    import ast
    import inspect

    from app.audit.checks.ai_ready import BreadcrumbCheck

    source = inspect.getsource(BreadcrumbCheck.run)
    tree = ast.parse(source.lstrip())
    called = {node.func.attr for node in ast.walk(tree)
              if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
    assert "classify" in called
    names = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert "depth" not in names
    assert not {"urlparse", "netloc", "hostname", "normalize", "contains"} & names
    numbers = [n for n in ast.walk(tree)
               if isinstance(n, ast.Constant) and isinstance(n.value, (int, float))
               and not isinstance(n.value, bool)]
    assert numbers == []


def test_the_centralized_modules_reuse_the_shared_scope_and_url_rules():
    """Мутація 22, друга половина: спільні правила ІМПОРТУЮТЬСЯ, а не
    переписуються. Своє правило «той самий хост» — це третє місце з тією
    самою відповіддю, і воно розійдеться з двома першими."""
    import ast
    import inspect

    from app.audit import breadcrumbs as validity_module

    for module in (hierarchy, validity_module):
        tree = ast.parse(inspect.getsource(module))
        imported = {alias.name for node in ast.walk(tree)
                    if isinstance(node, ast.ImportFrom) for alias in node.names}
        modules = {node.module for node in ast.walk(tree)
                   if isinstance(node, ast.ImportFrom) and node.module}
        assert "app.audit.site_scope" in modules
        assert "SiteScope" in imported
        assert "app.audit.logical_pages" in modules or "normalize" in imported
        # Власного розбору хоста бути не може.
        source = inspect.getsource(module)
        assert "urlsplit" not in source
        assert ".netloc" not in source


def test_the_rollback_lever_makes_the_classifier_inert():
    """Відкат: без таблиць класифікатор віддає `None`, і споживачі гаснуть.

    Та сама побудова, що в `about_page.AVAILABLE`: важіль — самі дані, і
    зворотної правки в споживачах він не потребує.
    """
    ctx, _unread = e15_build("E15-f1")
    assert hierarchy.classify(ctx) is not None
    original = hierarchy.ELIGIBLE_ROUTE_CLASSES, hierarchy.RELATIONSHIP_KINDS, hierarchy.AVAILABLE
    try:
        hierarchy.ELIGIBLE_ROUTE_CLASSES = frozenset()
        hierarchy.RELATIONSHIP_KINDS = ()
        hierarchy.AVAILABLE = False
        assert hierarchy.classify(ctx) is None
        assert list(BreadcrumbCheck().run(ctx)) == []
        assert applicability.unread_applicable(ctx, "ai.schema.breadcrumb") == 0
        row = applicability.evidence_for_context(ctx)["ai.schema.breadcrumb"]
        assert "detail" not in row
    finally:
        (hierarchy.ELIGIBLE_ROUTE_CLASSES, hierarchy.RELATIONSHIP_KINDS,
         hierarchy.AVAILABLE) = original


# ── the orchestrator gap ──────────────────────────────────────────────────

def test_an_unknown_hierarchy_becomes_a_named_gap_and_a_partial_module():
    """Прогалина мусить дійти до читача, а не лишитись у рядку застосовності.

    `NO_VERDICT + PARTIAL` каже, що ми не знаємо; `missing_data` каже, ЧОМУ
    ми не знаємо, і робить модуль неповним. Друге народжується лише в
    оркестраторі — чек деградацій не створює, — тож без гачка стан був би
    видимий лише тому, хто читає застосовність.
    """
    for fixture_id in ("E15-f6", "E15-f7", "E15-f11"):
        ctx, _unread = e15_build(fixture_id)
        outcome = rescore(ctx)
        gaps = [d for d in outcome.degraded if d.scope == "ai.schema.breadcrumb"]
        assert len(gaps) == 1, fixture_id
        assert gaps[0].reason_key == hierarchy.NOTICE_UNKNOWN, fixture_id
        assert gaps[0].kind is DegradationKind.PARTIAL_DATA, fixture_id
        assert Module.AI_READY in outcome.partial_modules, fixture_id


def test_a_settled_hierarchy_makes_no_gap_at_all():
    """Зворотний бік того самого гачка: вирішене не стає прогалиною.

    Без цієї половини гачок, що завжди повідомляє прогалину, проходив би
    перший тест і був би неправильним — плаский сайт і сайт із крихтами
    отримували б застереження про те, чого ми нібито не знаємо.
    """
    for fixture_id in ("E15-f1", "E15-f3", "E15-f5", "E15-f12", "E15-f14"):
        ctx, _unread = e15_build(fixture_id)
        outcome = rescore(ctx)
        assert [d for d in outcome.degraded if d.scope == "ai.schema.breadcrumb"] == [], fixture_id
        assert Module.AI_READY not in outcome.partial_modules, fixture_id


def test_no_gap_is_recorded_for_a_module_the_caller_excluded():
    """Виключений модуль не має рости прогалинами, яких ніхто не замовляв."""
    ctx, _unread = e15_build("E15-f7")
    outcome = rescore(ctx, AuditOptions(modules={Module.SEO}))
    assert [d for d in outcome.degraded if d.scope == "ai.schema.breadcrumb"] == []
    assert Module.AI_READY not in outcome.partial_modules


def test_the_catalogue_key_travels_as_a_reason_key_and_never_as_evidence():
    """Сирий ключ — це ручка подання, і в звіті його бути не може.

    Він їде в `reason_key`, де його чекає рендер, і не потрапляє ані в
    доказ рішення, ані в рядок застосовності. Шість мов читають звіт, і
    ключ, що просочився в текст, однаково нечитабельний у кожній.
    """
    import json as _json

    ctx, _unread = e15_build("E15-f7")
    outcome = rescore(ctx)
    gap = next(d for d in outcome.degraded if d.scope == "ai.schema.breadcrumb")
    assert gap.reason_key == hierarchy.NOTICE_UNKNOWN
    assert "notice." not in gap.reason

    decision = hierarchy.classify(ctx)
    assert "notice." not in _json.dumps(decision.as_evidence(), ensure_ascii=False)
    row = build_evidence(outcome.context)["applicability"]["ai.schema.breadcrumb"]
    assert "notice." not in _json.dumps(row, ensure_ascii=False)
    # Те, чого бракує, названо фактом — і він однаковий шістьма мовами.
    assert decision.missing_evidence
    assert all("notice" not in fact for fact in decision.missing_evidence)


def test_the_message_catalogue_can_reach_this_check_from_a_synthetic_context():
    """Ключ чека мусить бути досяжним, інакше його шаблон ніхто не перевіряє.

    E-15 зробив `ai.schema.breadcrumb` досяжним лише на сайті з доведеною
    ієрархією, а таких серед синтетичних контекстів не було жодного — це
    виміряно на всіх тридцяти пʼятьох. Тест тримає межу з цього боку:
    контекст існує й справді запалює ключ.
    """
    from tests.test_i18n import _hierarchy_context, _issues_of

    fired = {issue.msg for issue in _issues_of(_hierarchy_context())}
    assert "ai.schema.breadcrumb" in fired
    decision = hierarchy.classify(_hierarchy_context())
    assert decision.classification == hierarchy.HIERARCHY_EVIDENT
    assert len(decision.relationships) == 1


# ── два авторизовані гачки застосовності ──────────────────────────────────

def test_the_applicability_row_takes_its_verdict_from_the_classifier():
    """Гачок 1 обовʼязковий: посторінкова згортка цих станів не виражає.

    Без нього рядок може бути тільки PASS або FAIL при повному покритті —
    саме це виміряно на прийнятому двигуні. Чотири стани контракту
    приходять від класифікатора, і тест вимагає кожного з них.
    """
    wanted = {
        "E15-f5": (ClaimVerdict.NOT_APPLICABLE, Coverage.COMPLETE, "A-09"),
        "E15-f14": (ClaimVerdict.NOT_APPLICABLE, Coverage.COMPLETE, "A-10"),
        "E15-f7": (ClaimVerdict.NO_VERDICT, Coverage.PARTIAL, None),
        "E15-f10": (ClaimVerdict.FAIL, Coverage.PARTIAL, None),
    }
    for fixture_id, (verdict, coverage, rule) in wanted.items():
        _decision, ctx = _e15_decision(fixture_id)
        row, _outcome = _e15_row(ctx)
        assert row["verdict"] == verdict.value, fixture_id
        assert row["coverage"] == coverage.value, fixture_id
        assert "detail" in row, fixture_id
        if rule:
            assert rule in row["rules"], fixture_id


def test_the_unread_count_comes_from_the_classifier():
    """Гачок 2 обовʼязковий: без нього `unread_applicable` завжди нуль, і
    доведена ієрархія з непрочитаним обсягом виглядала б дочитаною."""
    for fixture_id in ("E15-f6", "E15-f7", "E15-f10", "E15-f11"):
        _decision, ctx = _e15_decision(fixture_id)
        assert applicability.unread_applicable(ctx, "ai.schema.breadcrumb") > 0, fixture_id
    for fixture_id in ("E15-f1", "E15-f3", "E15-f5", "E15-f12", "E15-f14"):
        _decision, ctx = _e15_decision(fixture_id)
        assert applicability.unread_applicable(ctx, "ai.schema.breadcrumb") == 0, fixture_id


def test_a_settled_pass_does_not_count_unread_siblings():
    """Екзистенційну претензію закриває одне достатнє спостереження.

    На E15-f3 непрочитаних немає взагалі; на сайті, де вони є, PASS усе
    одно лишає покриття повним — інакше «знайшли» перетворилося б на
    «можливо, десь є ще».
    """
    ctx, _unread = e15_build("E15-f3")
    ctx.sitemap.urls = [*ctx.sitemap.urls, "https://example.com/catalog/tables"]
    decision = hierarchy.classify(ctx)
    assert decision.unread_eligible
    assert decision.verdict is ClaimVerdict.PASS
    assert decision.coverage is Coverage.COMPLETE
    assert decision.unread_applicable == 0


def test_the_g4b_declaration_of_the_breadcrumb_claim_is_unchanged():
    """Оголошення претензії — власність G4b, і G5b його не чіпає."""
    declaration = applicability.CHECK_DECLARATIONS["ai.schema.breadcrumb"]
    assert declaration.claim_class is applicability.ClaimClass.HIERARCHY_GATED
    assert declaration.aggregation_strategy is applicability.AggregationStrategy.\
        ANY_SUFFICIENT_EVIDENCE
    assert declaration.no_relevant_page is applicability.NoRelevantPage.CLASSIFIER
    assert not declaration.variants
    check = BreadcrumbCheck()
    assert check.code == "ai.schema.breadcrumb"
    assert check.severity is Severity.LOW
    assert check.weight == 1


def test_the_hooks_touch_no_other_claim():
    """Решта таблиці застосовності лишається такою, якою її лишив G4b.

    Рядок із `detail` — це рядок, чиє рішення ухвалив окремий детектор.
    Таких претензій рівно дві на весь двигун, і друга зʼявилась у G5a.
    """
    ctx, _unread = e15_build("E15-f5")
    block = applicability.evidence_for_context(ctx)
    with_detail = {key for key, row in block.items() if "detail" in row}
    assert with_detail == {"ai.schema.breadcrumb", "llm.about_page"}
    # І жоден інший рядок не отримав коду причини E-15.
    for key, row in block.items():
        if key == "ai.schema.breadcrumb":
            continue
        assert "A-09" not in (row.get("rules") or {}), key
        assert "A-10" not in (row.get("rules") or {}), key


def test_the_about_page_hook_still_decides_its_own_row():
    """G5a не зрушено: його гачок стоїть на місці й досі диктує свій рядок."""
    ctx, _unread = e15_build("E15-f5")
    row = applicability.evidence_for_context(ctx)["llm.about_page"]
    assert "detail" in row
    # Рядок диктує детектор: його вердикт стоїть і в рядку, і в доказі.
    assert row["detail"]["verdict"] == row["verdict"]
    assert "candidate" in row["detail"]


# ── G6 / E-07: ai.schema.faq вилучено зі скорингу ─────────────────────
#
# Рішення власника OD-01: придатність до FAQ-сніпета не є загальною вимогою
# до сайту, тож «у вас немає FAQ» перестало бути знахідкою. Чек лишається в
# коді — канонічний відкат повертає декоратор, а не відновлює видалене, —
# але активним він більше не є ніде: ані в реєстрі, ані в таблиці
# оголошень, ані в доказі, ані в балі.

G6_RETIRED = "ai.schema.faq"


def _g6_faq_site(headings, url="https://example.com/"):
    """Сторінка, яка ДО G6 гарантовано давала знахідку."""
    from tests.factories import context, page_from_html

    prose = "слово " * 120
    body = "".join(f"<h2>{h}</h2><p>{prose}</p>" for h in headings)
    page = page_from_html(
        f'<html lang="uk"><head><title>Ціни</title>'
        f'<link rel="canonical" href="{url}"></head>'
        f"<body><main><h1>Ціни</h1>{body}</main></body></html>", url=url)
    ctx = context(page)
    ctx.entry_url, ctx.origin = url, "https://example.com"
    return ctx


OLD_TRIGGERS = (
    ("три питальні заголовки", ("Чи знайде вас пошук?", "Скільки коштує аудит?",
                                "Як довго це триває?"), "https://example.com/"),
    ("маршрут faq з одним питанням", ("Скільки коштує аудит?",), "https://example.com/faq"),
)


def test_g6_the_faq_check_is_not_registered():
    from app.audit.checks import REGISTRY

    assert G6_RETIRED not in {c.code for c in REGISTRY}


def test_g6_the_class_survives_for_the_canonical_rollback():
    """Відкат — це повернути `@register`, а не відновити видалений код."""
    from app.audit.checks.ai_ready import FaqSchemaCheck

    assert FaqSchemaCheck.code == G6_RETIRED
    assert FaqSchemaCheck.weight == 2
    assert FaqSchemaCheck.severity is Severity.LOW


def test_g6_the_active_registry_holds_eighty_checks():
    from app.audit.checks import REGISTRY

    assert len(REGISTRY) == 80
    assert len({c.code for c in REGISTRY}) == 80, "дубль коду в реєстрі"


def test_g6_declaration_ids_equal_registry_ids():
    from app.audit import applicability
    from app.audit.checks import REGISTRY

    assert set(applicability.CHECK_DECLARATIONS) == {c.code for c in REGISTRY}
    assert len(applicability.CHECK_DECLARATIONS) == 80


def test_g6_the_retired_code_has_no_declaration():
    from app.audit import applicability

    assert G6_RETIRED not in applicability.CHECK_DECLARATIONS


@pytest.mark.parametrize("label,headings,url", OLD_TRIGGERS, ids=[t[0] for t in OLD_TRIGGERS])
def test_g6_a_fresh_audit_emits_no_faq_finding_on_the_old_triggers(label, headings, url):
    from app.audit.orchestrator import rescore

    outcome = rescore(_g6_faq_site(headings, url))
    assert not [i for i in outcome.issues if i.code == G6_RETIRED], label


def test_g6_fresh_evidence_carries_no_faq_applicability_row():
    from app.audit.orchestrator import rescore
    from app.report.builder import build_evidence

    outcome = rescore(_g6_faq_site(OLD_TRIGGERS[0][1]))
    evidence = build_evidence(outcome.context)
    assert G6_RETIRED not in (evidence.get("applicability") or {})


def test_g6_the_retired_check_reaches_neither_scoring_nor_passed_state():
    from app.audit.orchestrator import rescore
    from app.report.builder import build_evidence
    from app.report.passed import collect_passed, evaluate_all

    outcome = rescore(_g6_faq_site(OLD_TRIGGERS[0][1]))
    evidence = build_evidence(outcome.context)
    assert all(i.code != G6_RETIRED for i in outcome.issues)
    assert G6_RETIRED not in evaluate_all(evidence, set())
    assert G6_RETIRED not in {p.key.split(":")[0]
                              for p in collect_passed(evidence, set())}


def test_g6_no_replacement_faq_check_was_introduced():
    """Рішення власника прямо це забороняє в цій серії."""
    from app.audit.checks import REGISTRY

    faq_like = [c.code for c in REGISTRY
                if "faq" in c.code.lower() or "faq" in c.__name__.lower()]
    assert faq_like == []


def test_g6_every_other_registry_entry_is_untouched():
    """Єдина різниця з прийнятим G5c — зниклий рядок.

    Атрибути порівнюються з ОГОЛОШЕННЯМИ, а не з переліком у тесті: список,
    переписаний руками, розійшовся б з кодом при першій же зміні ваги.
    """
    from app.audit.checks import REGISTRY

    rows = {c.code: (c.module.value, c.severity.value, c.weight, c.effort.value,
                     tuple(c.variants)) for c in REGISTRY}
    assert G6_RETIRED not in rows
    assert len(rows) == 80
    # Дві перевірки сімʼї ai.schema, які лишились активними, і їхні ціни.
    assert rows["ai.schema.graph"][2] >= 1
    assert rows["ai.schema.organization"][1] in {"low", "medium", "high", "critical", "info"}


def test_g6_the_retired_catalogue_marker_exists_exactly_once():
    from app.audit.checks.base import RETIRED_MESSAGE_KEYS

    assert G6_RETIRED in RETIRED_MESSAGE_KEYS
    assert sum(1 for k in RETIRED_MESSAGE_KEYS if k == G6_RETIRED) == 1
    assert len(RETIRED_MESSAGE_KEYS) == len(set(RETIRED_MESSAGE_KEYS))


def test_g6_without_the_retired_marker_the_catalogue_has_an_orphan():
    """Зняття маркера мусить ламати — інакше він нічого не тримає."""
    from app.audit.checks.base import RETIRED_MESSAGE_KEYS, all_message_keys
    from app.audit.i18n import CATALOGS, DEFAULT_LOCALE

    catalogue = set(CATALOGS[DEFAULT_LOCALE])
    without = RETIRED_MESSAGE_KEYS - {G6_RETIRED}
    orphans = catalogue - all_message_keys() - without
    assert G6_RETIRED in orphans, "без маркера ключ став би сиротою в каталозі"


def test_g6_the_version_boundary_moved_on_both_axes():
    from app.audit import versions

    assert versions.DETECTOR_RULES == "14"
    assert versions.SCORING_RULES == "5"
    assert versions.CRAWLER_VERSION == "4"
    assert versions.detector_version() != "28aae132f233"
    assert versions.scoring_version() != "c6a1c3fd43d8"


def test_g6_the_attribute_digest_moved_by_exactly_one_disappearing_row():
    """Відбиток оголошень зсунувся рівно тому, що зник один рядок.

    Доводиться конструктивно: беремо живі рядки, доклеюємо ПРИЙНЯТИЙ рядок
    вилученого чека — і отримуємо прийнятий дайджест. Якби зсунулось щось
    іще, ця рівність не відновилась би.
    """
    import hashlib

    from app.audit.checks import REGISTRY

    def digest(rows):
        return hashlib.sha256("\n".join(sorted(rows)).encode()).hexdigest()[:16]

    live = [f"{c.code}:{c.module.value}:{c.severity.value}:{c.weight}:"
            f"{c.effort.value}:{','.join(c.variants)}" for c in REGISTRY]
    accepted_faq_row = "ai.schema.faq:ai_ready:low:2:medium:"

    assert len(live) == 80
    assert digest(live) != "e3b391e478f8c347"
    assert digest([*live, accepted_faq_row]) == "e3b391e478f8c347", (
        "прийнятий дайджест не відновлюється поверненням лише цього рядка"
    )
