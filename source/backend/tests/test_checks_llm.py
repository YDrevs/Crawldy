"""Чеки видимості для LLM: там, де евристика мусить рахуватися з наміром."""

from __future__ import annotations

import ast
import inspect
import re

import pytest

from app.audit import about_page, applicability, i18n
from app.audit.applicability import ClaimVerdict, Coverage
from app.audit.checks.llm_visibility import (
    AboutPageCheck,
    BrandConsistencyCheck,
    ClientRenderedCheck,
)
from app.audit.enums import DegradationKind, Module, Severity
from app.audit.orchestrator import AuditOptions, _module_coverage, rescore
from app.audit.types import (
    Degradation,
    PageSignals,
    RenderResult,
    SiteContext,
    SitemapInfo,
)
from app.report import passed
from app.report.builder import _reason_params
from tests.factories import context, page_from_html

SHELL_HTML_BYTES = 300_000


def shell(url: str, title: str = "") -> PageSignals:
    """Сторінка-оболонка: багато розмітки, майже немає тексту."""
    page = PageSignals(url=url, status_code=200, html_bytes=SHELL_HTML_BYTES, title=title)
    page.text = "Loading"
    page.word_count = 1
    return page


def filled(url: str) -> PageSignals:
    page = PageSignals(url=url, status_code=200, html_bytes=50_000)
    page.text = "слово " * 800
    page.word_count = 800
    return page


def ctx(*pages: PageSignals) -> SiteContext:
    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.pages = list(pages)
    return site


def test_contact_page_hiding_its_content_is_not_a_defect():
    """Ховати контакти від парсерів — вимога специфікації, а не помилка."""
    site = ctx(filled("https://example.com/"), shell("https://example.com/contact"))
    assert list(ClientRenderedCheck().run(site)) == []


def test_legal_pages_may_hide_too():
    site = ctx(
        filled("https://example.com/"),
        shell("https://example.com/privacy-policy"),
        shell("https://example.com/terms"),
    )
    assert list(ClientRenderedCheck().run(site)) == []


def test_contact_page_recognised_by_title_not_only_by_url():
    site = ctx(filled("https://example.com/"), shell("https://example.com/x", title="Contact us"))
    assert list(ClientRenderedCheck().run(site)) == []


def test_whole_site_rendered_on_client_is_critical():
    site = ctx(*(shell(f"https://example.com/{n}") for n in range(5)))
    issues = list(ClientRenderedCheck().run(site))

    assert len(issues) == 5
    assert all(i.severity is Severity.CRITICAL for i in issues)


def test_one_page_in_twenty_is_not_a_site_wide_verdict():
    """Критична проблема на 5% сайту не має важити як на 100%."""
    pages = [filled(f"https://example.com/{n}") for n in range(19)]
    pages.append(shell("https://example.com/broken"))
    issues = list(ClientRenderedCheck().run(ctx(*pages)))

    assert len(issues) == 1
    assert issues[0].severity is Severity.MEDIUM
    assert issues[0].evidence["affected_share"] == 0.05


def test_a_third_of_the_site_is_high_not_critical():
    pages = [filled(f"https://example.com/{n}") for n in range(6)]
    pages += [shell(f"https://example.com/s{n}") for n in range(3)]
    issues = list(ClientRenderedCheck().run(ctx(*pages)))

    assert all(i.severity is Severity.HIGH for i in issues)


def test_server_rendered_site_produces_nothing():
    site = ctx(*(filled(f"https://example.com/{n}") for n in range(5)))
    assert list(ClientRenderedCheck().run(site)) == []


# ── вимірювання проти здогадки ─────────────────────────────────────────────


def with_render(site: SiteContext, url: str, *, words_after: int) -> SiteContext:
    """Кладе поруч зі сторінкою її відрендерену версію."""
    after = PageSignals(url=url, status_code=200, html_bytes=60_000)
    after.text = "слово " * words_after
    after.word_count = words_after
    site.renders[url] = RenderResult(url=url, rendered=True, html="<html/>", signals=after)
    return site


def test_measurement_replaces_the_heuristic_when_a_render_exists():
    """Сторінка з важким інлайновим CSS виглядає «оболонкою» для евристики.
    Рендер показує, що текст був у HTML із самого початку."""
    page = shell("https://example.com/")
    page.word_count = 40
    page.text = "слово " * 40
    site = with_render(ctx(page), "https://example.com/", words_after=45)

    assert list(ClientRenderedCheck().run(site)) == [], "89% тексту видно без JS"


def test_content_that_appears_only_after_js_is_reported_with_numbers():
    page = shell("https://example.com/")
    site = with_render(ctx(page), "https://example.com/", words_after=900)

    issues = list(ClientRenderedCheck().run(site))

    assert len(issues) == 1
    assert issues[0].evidence["measured"] is True
    assert issues[0].evidence["words_without_js"] == 1
    assert issues[0].evidence["words_after_render"] == 900
    assert issues[0].evidence["visible_without_js"] == "0%"


def test_pages_without_a_render_fall_back_to_the_heuristic():
    """Бюджет рендеру — три сторінки. Решта судиться як раніше, інакше
    сайт із двадцяти оболонок виглядав би чистим."""
    site = ctx(shell("https://example.com/deep"))

    issues = list(ClientRenderedCheck().run(site))

    assert len(issues) == 1
    assert "measured" not in issues[0].evidence


def test_render_that_adds_almost_nothing_is_not_judged():
    """Сторінка на сто слів після рендеру — замало, щоб частка щось означала."""
    page = shell("https://example.com/")
    site = with_render(ctx(page), "https://example.com/", words_after=30)

    assert list(ClientRenderedCheck().run(site)) == []


def test_severity_follows_how_much_of_the_site_is_affected():
    pages = [shell(f"https://example.com/p{n}") for n in range(4)]
    site = ctx(*pages)
    for page in pages:
        with_render(site, page.url, words_after=900)

    issues = list(ClientRenderedCheck().run(site))

    assert len(issues) == 4
    assert all(i.severity is Severity.CRITICAL for i in issues), "весь сайт за JS"


# --- факти, яких немає ніде на сайті ------------------------------------

def _facts(missing: tuple[str, ...], *, area: bool = True, priced: bool = True):
    from app.audit.llm.base import Fact, SiteFacts

    keys = ("offering", "location", "pricing")
    return SiteFacts(
        analysed=True,
        facts=[
            Fact(key=k, stated=k not in missing, quote="" if k in missing else "цитата")
            for k in keys
        ],
        serves_an_area=area,
        sells_listed_items=priced,
        read_pages=["https://example.com/", "https://example.com/contacts"],
    )


def _ctx_with(facts) -> SiteContext:
    ctx = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    ctx.pages = [filled("https://example.com/")]
    ctx.facts = facts
    return ctx


def _run(facts) -> list:
    from app.audit.checks.llm_visibility import UnstatedFactsCheck

    return list(UnstatedFactsCheck().run(_ctx_with(facts)))


def test_missing_fact_becomes_an_issue_with_the_pages_we_read():
    issues = _run(_facts(("offering",)))

    assert [i.msg for i in issues] == ["llm.unstated_facts.offering"]
    assert issues[0].evidence["pages_read"] == [
        "https://example.com/", "https://example.com/contacts"
    ]


def test_a_site_that_states_everything_gives_nothing():
    assert _run(_facts(())) == []


def test_global_business_is_not_punished_for_having_no_street_address():
    """Stripe теж не називає вулиці, і це не дефект. Без цього гейта чек
    спрацьовував на шести з десяти сайтів живої вибірки, включно з усіма
    добре зробленими."""
    issues = _run(_facts(("location",), area=False))

    assert issues == []


def test_local_business_without_a_city_is_a_real_problem():
    """Той самий факт, інший бізнес: покупець шукає виконавця поруч."""
    issues = _run(_facts(("location",), area=True))

    assert [i.msg for i in issues] == ["llm.unstated_facts.location"]


def test_free_project_is_not_punished_for_having_no_price_list():
    assert _run(_facts(("pricing",), priced=False)) == []


def test_shop_without_prices_is_a_real_problem():
    assert [i.msg for i in _run(_facts(("pricing",), priced=True))] == [
        "llm.unstated_facts.pricing"
    ]


def test_without_analysis_the_check_stays_silent():
    """Аналізу не було — це не те саме, що «все гаразд». Мовчазне
    спрацювання тут звинуватило б кожен сайт, аудит якого йшов без ключа."""
    from app.audit.llm.base import SiteFacts

    assert _run(None) == []
    assert _run(SiteFacts(analysed=False, error="ключа немає")) == []


def _ctx_linking_to(path: str, facts) -> SiteContext:
    """Сайт, де потрібна сторінка існує й видима з головної."""
    from app.audit.types import LinkRef

    ctx = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    home = filled("https://example.com/")
    home.links = [LinkRef(url=f"https://example.com{path}", anchor="Ціни", rel="", is_internal=True)]
    ctx.pages = [home]
    ctx.facts = facts
    return ctx


def _run_on(ctx) -> list:
    from app.audit.checks.llm_visibility import UnstatedFactsCheck

    return list(UnstatedFactsCheck().run(ctx))


def test_a_page_we_never_read_is_not_evidence_of_absence():
    """На stripe.com краул приносив самі юридичні сторінки, /pricing лишалась
    за бортом — і чек звинувачував сайт у тому, чого ми не дивилися."""
    facts = _facts(("pricing",))
    facts.read_pages = ["https://example.com/"]

    assert _run_on(_ctx_linking_to("/pricing", facts)) == []


def test_no_such_page_anywhere_is_evidence_of_absence():
    """Іншу гілку теж треба довести, інакше чек просто ніколи не спрацює."""
    facts = _facts(("pricing",))
    facts.read_pages = ["https://example.com/"]
    ctx = _ctx_with(facts)

    issues = _run_on(ctx)

    assert [i.msg for i in issues] == ["llm.unstated_facts.pricing"]
    assert issues[0].evidence["conventional_page"] == "немає на сайті"


def test_reading_the_page_makes_the_absence_provable():
    facts = _facts(("pricing",))
    facts.read_pages = ["https://example.com/", "https://example.com/pricing"]

    issues = _run_on(_ctx_linking_to("/pricing", facts))

    assert [i.msg for i in issues] == ["llm.unstated_facts.pricing"]
    assert issues[0].evidence["conventional_page"] == "прочитано"


def test_offering_needs_no_special_page_because_the_home_page_is_always_read():
    facts = _facts(("offering",))
    facts.read_pages = ["https://example.com/"]

    assert [i.msg for i in _run_on(_ctx_with(facts))] == ["llm.unstated_facts.offering"]


# --- чек не стверджує відсутність, маючи доказ присутності --------------

def _client_rendered_ctx() -> SiteContext:
    """Сторінка, де розмітка з'являється тільки після JS."""
    from app.audit.extractor import signals_from_html
    from app.audit.types import RenderResult

    url = "https://spa.example/"
    static = signals_from_html(
        url,
        "<html><head><title>Магазин</title></head><body><div id=root></div>"
        + "<p>" + "слово " * 400 + "</p></body></html>",
        origin="https://spa.example",
    )
    after = signals_from_html(
        url,
        "<html><head><title>Магазин</title>"
        '<meta name="description" content="Печиво на замовлення">'
        '<script type="application/ld+json">{"@type":"Organization","name":"Ф"}</script>'
        "</head><body><h1>Печиво на замовлення</h1>"
        "<h2>Доставка</h2><h2>Оплата</h2>"
        "<p>Ми печемо печиво. Доставляємо по місту. " + "слово " * 400 + "</p></body></html>",
        origin="https://spa.example",
    )
    ctx = SiteContext(entry_url=url, origin="https://spa.example")
    ctx.pages = [static]
    ctx.renders = {url: RenderResult(url=url, rendered=True, signals=after)}
    return ctx


def _codes_from(ctx: SiteContext) -> set[str]:
    from app.audit.checks import all_checks

    return {
        issue.msg or issue.code
        for check in all_checks()
        for issue in check.run(ctx)
    }


def test_google_is_not_told_the_page_lacks_what_javascript_adds():
    """Google виконує JS. Писати йому «немає H1» про заголовок, який він
    бачить, — брехня, яку клієнт спростує за десять секунд, відкривши
    власну сторінку."""
    codes = _codes_from(_client_rendered_ctx())

    assert "seo.h1.missing" not in codes
    assert "seo.meta_description.missing" not in codes


def test_assistants_are_told_the_truth_about_the_same_page():
    """Асистенти здебільшого JS не виконують: для них розмітки, якої немає
    у відповіді сервера, не існує. Той самий факт коштує різного різним
    читачам, і спільна відповідь помилилася б для обох."""
    codes = _codes_from(_client_rendered_ctx())

    assert "ai.jsonld.missing" in codes


def test_the_model_does_not_overrule_what_we_already_know():
    """Модель сказала «ніде не вказано, де ви працюєте», а місто лежить у
    мета-описі головної. Порядок джерел істини: детерміністичні докази
    вище за висновок моделі, а не навпаки."""
    from app.audit.site_facts import SiteKnowledge

    ctx = _ctx_with(_facts(("location",), area=True))
    ctx.known = SiteKnowledge(cities=["Кам'янець-Подільський"])

    assert _run_on(ctx) == []


def test_without_deterministic_facts_the_model_is_still_heard():
    """Інакше чек замовк би на сайтах, де міста справді немає ніде."""
    from app.audit.site_facts import SiteKnowledge

    ctx = _ctx_with(_facts(("location",), area=True))
    ctx.known = SiteKnowledge()

    assert [i.msg for i in _run_on(ctx)] == ["llm.unstated_facts.location"]


# ── контакти в тілі сторінки — теж контакти ────────────────────────────────


def _page_with_contacts(url: str, contacts: int = 2) -> PageSignals:
    page = filled(url)
    page.body_contacts = contacts
    return page


def test_contacts_in_the_body_count_as_a_way_to_reach_the_company():
    """Чек шукав адресу виду /contact і на цьому зупинявся.

    Односторінкова пекарня на Wix і історичне товариство, у якого телефон
    стоїть на всіх девʼяти сторінках, отримували «немає сторінки Contact».
    Це перекіс проти класу: малий сайт кладе контакти на єдину сторінку.
    """
    from app.audit.checks.llm_visibility import ContactPageCheck

    site = ctx(_page_with_contacts("https://example.com/"))
    assert list(ContactPageCheck().run(site)) == []


def test_no_contacts_anywhere_is_still_a_finding():
    from app.audit.checks.llm_visibility import ContactPageCheck

    site = ctx(filled("https://example.com/"), filled("https://example.com/pricing"))
    assert len(list(ContactPageCheck().run(site))) == 1


def test_a_separate_contact_page_still_counts():
    from app.audit.checks.llm_visibility import ContactPageCheck

    site = ctx(filled("https://example.com/"), filled("https://example.com/contact"))
    assert list(ContactPageCheck().run(site)) == []


# ── E-10: сторінка «про нас» визначається за наміром, а не за підрядком ──
#
# Дев'ятнадцять фікстур контракту (`contracts/fixtures.json → E-10`) зібрані
# тут як справжні контексти двигуна — тими самими фабриками, що й решта
# тестів. Очікування кожної — дослівно з контракту, тож тест звіряє двигун
# із контрактом, а не з моїм прочитанням контракту.

E10_ORIGIN = "https://example.com"

E10_PROSE_EN = ("We are a small studio. We design and build measurement tools for teams who care "
            "about what their pages actually say. Our founders started the company in 2019 and "
            "our team has grown steadily since. ")
E10_PROSE_UK = ("Ми невелика студія. Ми проєктуємо інструменти вимірювання для команд, яким важливо, "
            "що саме кажуть їхні сторінки. Наша команда працює з 2019 року. ")

E10_ORGANIZATION_LD = ('<script type="application/ld+json">'
                   '{"@context":"https://schema.org","@type":"Organization","name":"Crawldy",'
                   '"url":"https://example.com"}</script>')
E10_ABOUTPAGE_LD = ('<script type="application/ld+json">'
                '{"@context":"https://schema.org","@type":"AboutPage","name":"Our story"}'
                '</script>')


def _e10_chrome(*links: tuple[str, str]) -> str:
    """A site-chrome navigation block: `<nav>` is what makes LinkRef.in_chrome true."""
    items = "".join(f'<li><a href="{href}">{text}</a></li>' for href, text in links)
    return f"<nav><ul>{items}</ul></nav>"


def _e10_document(*, lang: str = "en", title: str = "", h1: str = "", body: str = "",
             head_extra: str = "", nav: str = "") -> str:
    head = f"<title>{title}</title>{head_extra}" if title else head_extra
    heading = f"<h1>{h1}</h1>" if h1 else ""
    return (f'<html lang="{lang}"><head>{head}</head><body>{nav}'
            f"<main>{heading}{body}</main></body></html>")


def _e10_hreflang(*locales: str) -> str:
    """Declared launch locales, the accepted G4a way: the site says so itself."""
    return "".join(
        f'<link rel="alternate" hreflang="{code}" href="{E10_ORIGIN}/{code}/">' for code in locales)


# (id, locale, pages, expectations). `pages` entries are
# (url, html, status) — status None means the URL is known but was never fetched.
def _e10_six(locale: str, path: str, title: str, anchor: str, h1: str) -> list[tuple]:
    nav = _e10_chrome((f"/{locale}/", "Home"), (f"/{path}", anchor))
    home = _e10_document(lang=locale, title="Crawldy", h1="Crawldy", nav=nav,
                    body=f"<p>{E10_PROSE_EN}</p>", head_extra=_e10_hreflang(locale, "en"))
    about = _e10_document(lang=locale, title=title, h1=h1, nav=nav,
                     body=f"<p>{E10_PROSE_EN}</p>", head_extra=_e10_hreflang(locale, "en") + E10_ORGANIZATION_LD)
    return [(f"{E10_ORIGIN}/{locale}/", home, 200), (f"{E10_ORIGIN}/{path}", about, 200)]


E10_NAV_EN = _e10_chrome(("/", "Home"), ("/about", "About us"))
E10_NAV_CONTACT = _e10_chrome(("/", "Home"), ("/contact", "Contact"))
# Fixtures whose contract `primary_signals` carry no P3 must not link /about from the chrome:
# the sets in contracts/fixtures.json are exact, and a menu link would add a signal the case
# does not declare (E10-f4, f6, f13, f14, f15).
E10_NAV_HOME = _e10_chrome(("/", "Home"))
E10_NAV_TEAM = _e10_chrome(("/", "Home"), ("/team", "Our team"))

E10_FIXTURES: dict[str, dict] = {
    "E10-f1": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy", nav=E10_NAV_EN,
                                    body=f"<p>{E10_PROSE_EN}</p>", head_extra=E10_ORGANIZATION_LD), 200),
            (f"{E10_ORIGIN}/about", _e10_document(title="About us", h1="About us", nav=E10_NAV_EN,
                                         body=f"<p>{E10_PROSE_EN}</p>",
                                         head_extra=E10_ORGANIZATION_LD), 200),
        ],
        "candidate": True, "verdict": "PASS", "coverage": "COMPLETE", "conclusive": True,
        "selected": f"{E10_ORIGIN}/about",
        "primary": ["P1_route_token", "P2_title_or_h1_intent", "P3_chrome_anchor"],
        "corroborating": ["C1_organization_jsonld", "C3_first_person_prose"],
        "finding": False, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f2": {
        "locale": "de",
        "pages": _e10_six("de", "de/ueber-uns", "Über Crawldy", "Über uns", "Über Crawldy"),
        "candidate": True, "verdict": "PASS", "coverage": "COMPLETE", "conclusive": True,
        "selected": f"{E10_ORIGIN}/de/ueber-uns",
        "primary": ["P1_route_token", "P2_title_or_h1_intent", "P3_chrome_anchor"],
        "corroborating": ["C1_organization_jsonld"],
        "finding": False, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f2-fr": {
        "locale": "fr",
        "pages": _e10_six("fr", "fr/a-propos", "À propos de Crawldy", "À propos",
                      "À propos de Crawldy"),
        "candidate": True, "verdict": "PASS", "coverage": "COMPLETE", "conclusive": True,
        "selected": f"{E10_ORIGIN}/fr/a-propos",
        "primary": ["P1_route_token", "P2_title_or_h1_intent", "P3_chrome_anchor"],
        "corroborating": ["C1_organization_jsonld"],
        "finding": False, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f2-es": {
        "locale": "es",
        "pages": _e10_six("es", "es/sobre-nosotros", "Sobre Crawldy", "Sobre nosotros",
                      "Sobre Crawldy"),
        "candidate": True, "verdict": "PASS", "coverage": "COMPLETE", "conclusive": True,
        "selected": f"{E10_ORIGIN}/es/sobre-nosotros",
        "primary": ["P1_route_token", "P2_title_or_h1_intent", "P3_chrome_anchor"],
        "corroborating": ["C1_organization_jsonld"],
        "finding": False, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f2-ru": {
        "locale": "ru",
        "pages": _e10_six("ru", "ru/o-nas", "О Crawldy", "О нас", "О Crawldy"),
        "candidate": True, "verdict": "PASS", "coverage": "COMPLETE", "conclusive": True,
        "selected": f"{E10_ORIGIN}/ru/o-nas",
        "primary": ["P1_route_token", "P2_title_or_h1_intent", "P3_chrome_anchor"],
        "corroborating": ["C1_organization_jsonld"],
        "finding": False, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f2-uk": {
        "locale": "uk",
        "pages": _e10_six("uk", "uk/pro-nas", "Про Crawldy", "Про нас", "Про Crawldy"),
        "candidate": True, "verdict": "PASS", "coverage": "COMPLETE", "conclusive": True,
        "selected": f"{E10_ORIGIN}/uk/pro-nas",
        "primary": ["P1_route_token", "P2_title_or_h1_intent", "P3_chrome_anchor"],
        "corroborating": ["C1_organization_jsonld"],
        "finding": False, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    # Навігаційний якір є, ціль не відкривали.
    "E10-f3": {
        "locale": "de",
        "pages": [
            (f"{E10_ORIGIN}/de/", _e10_document(lang="de", title="Crawldy", h1="Crawldy",
                                       nav=_e10_chrome(("/de/", "Start"), ("/de/ueber-uns", "Über uns")),
                                       body=f"<p>{E10_PROSE_EN}</p>",
                                       head_extra=_e10_hreflang("de", "en")), 200),
            (f"{E10_ORIGIN}/de/ueber-uns", "", None),
        ],
        "candidate": True, "verdict": "NO_VERDICT", "coverage": "PARTIAL", "conclusive": False,
        "selected": f"{E10_ORIGIN}/de/ueber-uns",
        "primary": ["P3_chrome_anchor"], "corroborating": [],
        "finding": False, "module_partial": True, "unread_applicable": True, "also_seen": [],
        "notice": "notice.about_page.candidate_unread",
    },
    "E10-f4": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy", nav=E10_NAV_HOME,
                                    body=f"<p>{E10_PROSE_EN}</p>"), 200),
            (f"{E10_ORIGIN}/about", _e10_document(title="Forbidden", h1="403"), 403),
        ],
        "candidate": True, "verdict": "NO_VERDICT", "coverage": "NOT_MEASURED",
        "conclusive": False, "selected": f"{E10_ORIGIN}/about",
        "primary": ["P1_route_token"], "corroborating": [],
        "finding": False, "module_partial": True, "unread_applicable": False, "also_seen": [],
        "notice": "notice.about_page.candidate_unreadable", "reason": "failed_read",
    },
    "E10-f5": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy", nav=E10_NAV_CONTACT,
                                    body=f"<p>{E10_PROSE_EN}</p>", head_extra=E10_ORGANIZATION_LD), 200),
            (f"{E10_ORIGIN}/contact", _e10_document(title="Contact", h1="Contact", nav=E10_NAV_CONTACT,
                                           body="<p>Write to us at hello@example.com.</p>"), 200),
        ],
        "candidate": False, "verdict": "FAIL", "coverage": "COMPLETE", "conclusive": True,
        "selected": None, "primary": [],
        "corroborating": ["C1_organization_jsonld", "C3_first_person_prose"],
        "finding": True, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f6": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy",
                                    nav=E10_NAV_TEAM, body=f"<p>{E10_PROSE_EN}</p>"), 200),
            (f"{E10_ORIGIN}/about", _e10_document(title="About us", h1="About us",
                                         nav=E10_NAV_TEAM, body=f"<p>{E10_PROSE_EN}</p>",
                                         head_extra=E10_ORGANIZATION_LD), 200),
            (f"{E10_ORIGIN}/team", "", None),
        ],
        "candidate": True, "verdict": "PASS", "coverage": "COMPLETE", "conclusive": True,
        "selected": f"{E10_ORIGIN}/about",
        "primary": ["P1_route_token", "P2_title_or_h1_intent"],
        "corroborating": ["C1_organization_jsonld"],
        "finding": False, "module_partial": False, "unread_applicable": False,
        "also_seen": [f"{E10_ORIGIN}/team"], "notice": None,
    },
    "E10-f7": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy", nav=E10_NAV_CONTACT,
                                    body=f"<p>{E10_PROSE_EN} Our mission and our values guide us. "
                                         "We were founded in 2019.</p>",
                                    head_extra=E10_ORGANIZATION_LD), 200),
            (f"{E10_ORIGIN}/contact", _e10_document(title="Contact", h1="Contact", nav=E10_NAV_CONTACT,
                                           body="<p>Write to us.</p>"), 200),
        ],
        "candidate": False, "verdict": "FAIL", "coverage": "COMPLETE", "conclusive": True,
        "selected": None, "primary": [],
        "corroborating": ["C1_organization_jsonld", "C3_first_person_prose", "C4_company_prose"],
        "finding": True, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f8": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy", nav=E10_NAV_CONTACT,
                                    body="<p>Measurement tools.</p>"), 200),
            (f"{E10_ORIGIN}/contact", _e10_document(title="Contact", h1="Contact", nav=E10_NAV_CONTACT,
                                           body="<p>Write to us at hello@example.com.</p>",
                                           head_extra=E10_ORGANIZATION_LD), 200),
        ],
        "candidate": False, "verdict": "FAIL", "coverage": "COMPLETE", "conclusive": True,
        "selected": None, "primary": [], "corroborating": ["C1_organization_jsonld"],
        "finding": True, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f9": {
        "locale": "uk",
        "pages": [
            (f"{E10_ORIGIN}/uk/", _e10_document(lang="uk", title="Crawldy", h1="Crawldy",
                                       nav=_e10_chrome(("/uk/", "Головна"), ("/uk/posluhy", "Послуги")),
                                       body=f"<p>{E10_PROSE_UK}</p>",
                                       head_extra=_e10_hreflang("uk", "en") + E10_ORGANIZATION_LD), 200),
            (f"{E10_ORIGIN}/uk/posluhy",
             _e10_document(lang="uk", title="Послуги Crawldy", h1="Послуги",
                      nav=_e10_chrome(("/uk/", "Головна"), ("/uk/posluhy", "Послуги")),
                      body=f"<p>{E10_PROSE_UK} Crawldy робить аудит сайтів.</p>",
                      head_extra=_e10_hreflang("uk", "en")), 200),
        ],
        "candidate": False, "verdict": "FAIL", "coverage": "COMPLETE", "conclusive": True,
        "selected": None, "primary": [],
        "corroborating": ["C2_organisation_name", "C3_first_person_prose"],
        "finding": True, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f10": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy",
                                    nav=_e10_chrome(("/", "Home"), ("/about-cookies", "Cookies")),
                                    body="<p>Measurement tools.</p>"), 200),
            (f"{E10_ORIGIN}/about-cookies",
             _e10_document(title="About cookies", h1="About cookies",
                      nav=_e10_chrome(("/", "Home"), ("/about-cookies", "Cookies")),
                      body="<p>This page explains which cookies this website stores.</p>"), 200),
        ],
        "candidate": False, "verdict": "FAIL", "coverage": "COMPLETE", "conclusive": True,
        "selected": None, "primary": [], "corroborating": ["C6_substring"],
        "finding": True, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f11": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy",
                                    nav=_e10_chrome(("/", "Home"), ("/blog", "Blog")),
                                    body="<p>Measurement tools.</p>"), 200),
            (f"{E10_ORIGIN}/blog/how-the-rust-team-ships",
             _e10_document(title="How the Rust team ships", h1="How the Rust team ships",
                      nav=_e10_chrome(("/", "Home"), ("/blog", "Blog")),
                      body="<p>The Rust team runs a release train. Their team of maintainers "
                           "publishes every six weeks, and the company behind it is a "
                           "foundation.</p>"), 200),
        ],
        "candidate": False, "verdict": "FAIL", "coverage": "COMPLETE", "conclusive": True,
        "selected": None, "primary": [], "corroborating": ["C5_team_mention"],
        "finding": True, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    "E10-f12": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy",
                                    nav=_e10_chrome(("/", "Home"), ("/company-story", "Story")),
                                    body="<p>Measurement tools.</p>"), 200),
            (f"{E10_ORIGIN}/company-story",
             _e10_document(title="Our story", h1="Our story",
                      nav=_e10_chrome(("/", "Home"), ("/company-story", "Story")),
                      body="<p>The company was founded in 2019 with a mission to measure what "
                           "pages say.</p>", head_extra=E10_ABOUTPAGE_LD), 200),
        ],
        "candidate": True, "verdict": "PASS", "coverage": "COMPLETE", "conclusive": True,
        "selected": f"{E10_ORIGIN}/company-story",
        "primary": ["P4_aboutpage_schema"], "corroborating": ["C4_company_prose"],
        "finding": False, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None,
    },
    # Дванадцять слів і жодного порогу довжини.
    "E10-f13": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy", nav=E10_NAV_HOME,
                                    body="<p>Measurement tools.</p>",
                                    head_extra=E10_ORGANIZATION_LD), 200),
            (f"{E10_ORIGIN}/about",
             _e10_document(title="About us", h1="About us", nav=E10_NAV_HOME,
                      body="<p>Crawldy is a two-person studio in Kyiv building measurement "
                           "tools since 2019.</p>"), 200),
        ],
        "candidate": True, "verdict": "PASS", "coverage": "COMPLETE", "conclusive": True,
        "selected": f"{E10_ORIGIN}/about",
        "primary": ["P1_route_token", "P2_title_or_h1_intent"],
        "corroborating": ["C2_organisation_name"],
        "finding": False, "module_partial": False, "unread_applicable": False, "also_seen": [],
        "notice": None, "word_count": 12,
    },
    "E10-f14": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy", nav=E10_NAV_HOME,
                                    body="<p>Measurement tools.</p>"), 200),
            (f"{E10_ORIGIN}/about",
             _e10_document(title="Sign in", h1="Sign in", nav=E10_NAV_HOME,
                      body='<form method="post" action="/session">'
                           '<input type="email" name="email">'
                           '<input type="password" name="password">'
                           "<button>Sign in</button></form>"), 200),
        ],
        "candidate": True, "verdict": "NO_VERDICT", "coverage": "NOT_MEASURED",
        "conclusive": False, "selected": f"{E10_ORIGIN}/about",
        "primary": ["P1_route_token"], "corroborating": [],
        "finding": False, "module_partial": True, "unread_applicable": False, "also_seen": [],
        "notice": "notice.about_page.candidate_unreadable", "reason": "login_wall",
    },
    "E10-f15": {
        "locale": "en",
        "pages": [
            (f"{E10_ORIGIN}/", _e10_document(title="Crawldy", h1="Crawldy", nav=E10_NAV_HOME,
                                    body="<p>Measurement tools.</p>"), 200),
            (f"{E10_ORIGIN}/about", None, 200),  # built as a shell below
        ],
        "candidate": True, "verdict": "NO_VERDICT", "coverage": "NOT_MEASURED",
        "conclusive": False, "selected": f"{E10_ORIGIN}/about",
        "primary": ["P1_route_token"], "corroborating": [],
        "finding": False, "module_partial": True, "unread_applicable": False, "also_seen": [],
        "notice": "notice.about_page.candidate_unreadable", "reason": "content_shell",
    },
}


def e10_shell_document() -> str:
    """An application shell: plenty of markup, effectively no text.

    Built to satisfy the ENGINE's existing `is_content_shell` predicate rather than a
    description of one — the contract insists the same predicate decides, so the fixture has to
    be something that predicate actually accepts.
    """
    filler = "".join(f'<div class="c{i}" data-k="{i}"><span aria-hidden="true"></span></div>'
                     for i in range(400))
    # A generic application title, not an About phrase: the contract lists P1 alone for f15.
    return (f'<html lang="en"><head><title>Crawldy</title></head><body>{E10_NAV_HOME}'
            f'<div id="root">{filler}</div><noscript>Enable JavaScript</noscript>'
            "</body></html>")


def e10_build(fixture_id: str):
    """A live SiteContext for one fixture, using the engine's own factories."""
    spec = E10_FIXTURES[fixture_id]
    pages, known_unread = [], []
    for url, html, status in spec["pages"]:
        if status is None:
            known_unread.append(url)
            continue
        if html is None:
            html = e10_shell_document()
        page = page_from_html(html, url=url)
        page.status_code = status
        pages.append(page)
    ctx = context(*pages)
    return ctx, known_unread

E10_IDS = tuple(E10_FIXTURES)


def _e10_padding() -> PageSignals:
    """Стороння сторінка, щоб сайт мав більше за `MIN_WORDS_FOR_A_SITE` слів.

    Фікстури контракту навмисно короткі, а двигун виключає контентні модулі
    з сайту на кілька десятків слів — це давнє правило, не E-10. Щоб судити
    про стан МОДУЛЯ, сайту потрібен звичайний обсяг тексту; сама сторінка
    не несе жодної ознаки «про нас», і рішення від неї змінитись не має.
    """
    words = " ".join(f"слово{i}" for i in range(160))
    return page_from_html(
        f"<html><head><title>Нотатки</title></head><body><main><h1>Нотатки</h1>"
        f"<p>{words}</p></main></body></html>",
        url=f"{E10_ORIGIN}/notes",
    )


def e10_padded(fixture_id: str) -> SiteContext:
    site, _known_unread = e10_build(fixture_id)
    site.pages.append(_e10_padding())
    return site


def _about_gaps(degraded: list[Degradation]) -> list[Degradation]:
    return [d for d in degraded if d.scope == about_page.CHECK]


@pytest.mark.parametrize("fixture_id", E10_IDS)
def test_e10_fixture_decision_matches_the_contract(fixture_id: str) -> None:
    """Кожна поверхня рішення — вердикт, покриття, кандидат, ознаки, стан."""
    site, _ = e10_build(fixture_id)
    want = E10_FIXTURES[fixture_id]
    about = about_page.detect(site)
    assert about is not None
    assert (about.verdict.value, about.coverage.value) == (want["verdict"], want["coverage"])
    assert about.candidate is want["candidate"]
    assert about.selected == want["selected"]
    chosen = about.selected_candidate
    # Первинні ознаки — рівно ті, що оголошує фікстура: жодної зайвої.
    assert list(chosen.primary if chosen else ()) == want["primary"]
    # Підтверджувальні ніколи не вирішують, тож контракт називає ті, що
    # мусять бути помічені; двигун має право побачити й більше.
    observed = set(chosen.corroborating) if chosen else set(about.corroborating_seen)
    assert set(want["corroborating"]) <= observed
    assert about.finding is want["finding"]
    assert about.module_partial is want["module_partial"]
    assert bool(about.unread_applicable) is want["unread_applicable"]
    assert [c.url for c in about.also_seen] == want["also_seen"]
    assert (about.notice[0] if about.notice else None) == want["notice"]
    if want.get("reason"):
        assert about.reason == want["reason"]
    assert about.conclusive is (want["verdict"] == "PASS")
    assert about.locales == tuple(site.declared_locales())


@pytest.mark.parametrize("fixture_id", E10_IDS)
def test_e10_fixture_check_finding_and_applicability_row(fixture_id: str) -> None:
    """Чек, рядок застосовності й право на «пройдені» — з того самого рішення."""
    site, _ = e10_build(fixture_id)
    want = E10_FIXTURES[fixture_id]
    issues = list(AboutPageCheck().run(site))
    assert bool(issues) is want["finding"]
    if issues:
        (issue,) = issues
        assert issue.evidence["candidate"] is False
        assert issue.evidence["selected"] is None
        assert issue.evidence["verdict"] == "FAIL"
        assert issue.evidence["crawled"]
    block = applicability.finalise(applicability.evidence_for_context(site), issues)
    row = block["llm.about_page"]
    assert (row["verdict"], row["coverage"]) == (want["verdict"], want["coverage"])
    assert row["detail"]["selected"] == want["selected"]
    assert row["detail"]["primary"] == want["primary"]
    if want.get("reason"):
        assert row["detail"]["reason"] == want["reason"]
    unreadable = want["notice"] == about_page.NOTICE_UNREADABLE
    assert row["not_measured"] == (1 if unreadable else 0)
    # Не кураторський пункт «пройдених»: єдиний числовий шлях — штраф FAIL.
    assert "llm.about_page" not in {key for key, _module, _evaluate in passed.CURATED}
    assert "llm.about_page" not in passed.GOVERNED_BY
    assert passed.eligible({"applicability": block}, "llm.about_page") is (
        want["verdict"] == "PASS"
    )


@pytest.mark.parametrize("fixture_id", E10_IDS)
def test_e10_fixture_module_state_under_rescore(fixture_id: str) -> None:
    """Стан модуля: прогалина даних і `partial` рівно там, де немає вердикту."""
    want = E10_FIXTURES[fixture_id]
    padded = e10_padded(fixture_id)
    outcome = rescore(padded)
    assert Module.LLM_VISIBILITY not in outcome.skipped_modules
    gaps = _about_gaps(outcome.degraded)
    assert [g.reason_key for g in gaps] == ([want["notice"]] if want["notice"] else [])
    assert (Module.LLM_VISIBILITY in outcome.partial_modules) is want["module_partial"]
    assert any(i.code == "llm.about_page" for i in outcome.issues) is want["finding"]
    # Стороння сторінка рішення не змінює.
    plain, _ = e10_build(fixture_id)
    before, after = about_page.detect(plain), about_page.detect(padded)
    assert before is not None and after is not None
    assert (before.verdict, before.coverage, before.selected, before.reason) == (
        after.verdict, after.coverage, after.selected, after.reason
    )


def test_the_about_decision_reaches_module_coverage_before_any_check_runs() -> None:
    """Оркестратор питає рішення в `_module_coverage` — до `_run_checks`.

    `partial_modules` вирішується саме там і після чеків не перераховується,
    тож чек не міг би зробити модуль неповним, навіть якби хотів.
    """
    site = e10_padded("E10-f3")
    degraded: list[Degradation] = []
    skipped, partial = _module_coverage(AuditOptions(), site, [], degraded)
    assert Module.LLM_VISIBILITY not in skipped
    assert Module.LLM_VISIBILITY in partial
    (gap,) = _about_gaps(degraded)
    assert gap.kind is DegradationKind.PARTIAL_DATA
    assert gap.affected_modules == [Module.LLM_VISIBILITY]
    # Модуль, якого не замовляли, прогалини не отримує.
    degraded = []
    _skipped, partial = _module_coverage(
        AuditOptions(modules={Module.SEO}), site, [], degraded)
    assert Module.LLM_VISIBILITY not in partial
    assert _about_gaps(degraded) == []


def test_unread_nav_candidate_is_a_data_gap_not_a_finding() -> None:
    outcome = rescore(e10_padded("E10-f3"))
    assert all(i.code != "llm.about_page" for i in outcome.issues)
    (gap,) = _about_gaps(outcome.degraded)
    assert (gap.scope, gap.kind, gap.reason_key) == (
        about_page.CHECK, DegradationKind.PARTIAL_DATA, about_page.NOTICE_UNREAD
    )
    assert gap.reason_params == {"url": f"{E10_ORIGIN}/de/ueber-uns", "anchor": "Über uns"}
    assert gap.affected_modules == [Module.LLM_VISIBILITY]
    assert Module.LLM_VISIBILITY in outcome.partial_modules


@pytest.mark.parametrize(
    ("fixture_id", "reason", "status"),
    [("E10-f4", "failed_read", 403), ("E10-f14", "login_wall", 200),
     ("E10-f15", "content_shell", 200)],
)
def test_unreadable_candidate_names_its_observed_state(
    fixture_id: str, reason: str, status: int
) -> None:
    """Причина йде слагом, а читач бачить речення своєю мовою.

    Деградація локаленейтральна за побудовою — вона пишеться один раз і
    читається будь-якою з шести мов, — тож у ній стоїть слаг, а складає
    речення каталог при показі. Той самий механізм, що й у причин покриття.
    """
    outcome = rescore(e10_padded(fixture_id))
    assert all(i.code != "llm.about_page" for i in outcome.issues)
    (gap,) = _about_gaps(outcome.degraded)
    assert gap.reason_key == about_page.NOTICE_UNREADABLE
    assert gap.reason_params == {"url": f"{E10_ORIGIN}/about",
                                 "reasons": [about_page.REASON_SLUG[reason]],
                                 "status": status}
    assert Module.LLM_VISIBILITY in outcome.partial_modules


def test_settled_claim_with_unread_sibling_is_neither_degraded_nor_partial() -> None:
    """Правка A контракту v1.3: закрита екзистенційна претензія — COMPLETE."""
    outcome = rescore(e10_padded("E10-f6"))
    assert _about_gaps(outcome.degraded) == []
    assert Module.LLM_VISIBILITY not in outcome.partial_modules
    about = about_page.detect(outcome.context)
    assert about is not None and about.conclusive
    (sibling,) = about.also_seen
    assert (sibling.url, sibling.primary, sibling.read, sibling.anchor) == (
        f"{E10_ORIGIN}/team", ("P3_chrome_anchor",), False, "Our team"
    )
    assert about.unread_applicable == 0


def test_unread_applicable_counts_about_candidates_without_touching_the_sitemap_rule() -> None:
    f3, _ = e10_build("E10-f3")
    f1, _ = e10_build("E10-f1")
    f6, _ = e10_build("E10-f6")
    assert applicability.unread_applicable(f3, "llm.about_page") == 1
    assert applicability.unread_applicable(f1, "llm.about_page") == 0
    assert applicability.unread_applicable(f6, "llm.about_page") == 0
    assert applicability.unread_applicable(f3, "seo.title") == 0
    # Гілка карти сайту — та сама, що й в ухваленому G4b, і кандидати «про
    # нас» на неї не впливають.
    f3.sitemap = SitemapInfo(exists=True, is_index=True, index_complete=False,
                             children_total=5, children_read=["a", "b"])
    assert applicability.unread_applicable(f3, "seo.sitemap") == 3
    assert applicability.unread_applicable(f3, "llm.about_page") == 1
    f3.sitemap = SitemapInfo(exists=True, is_index=True, index_complete=True,
                             children_total=5, children_read=["a"])
    assert applicability.unread_applicable(f3, "seo.sitemap") == 0


def test_the_decision_is_pure_and_independent_of_page_order() -> None:
    """Той самий контекст — те саме рішення, скільки не питай і в якому порядку.

    Головна лишається першою: `ctx.home` — це перша сторінка, що відповіла,
    і переставити її означало б спитати про інший сайт, а не інший порядок.
    """
    site = e10_padded("E10-f6")
    first, second = about_page.detect(site), about_page.detect(site)
    assert first == second
    site.pages[1:] = reversed(site.pages[1:])
    assert about_page.detect(site) == first


def test_without_the_vocabulary_every_consumer_returns_to_the_previous_behaviour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Важіль відкату: без словника рішення немає, і споживачі мовчать.

    Канонічний відкат G5a прибирає словник і ключі повідомлень і повертає
    чек до старого помічника. Оркестратор і застосовність при цьому не
    правляться взагалі — їхні гілки стають порожніми самі.
    """
    monkeypatch.setattr(about_page, "AVAILABLE", False)
    f3 = e10_padded("E10-f3")
    f5, _ = e10_build("E10-f5")
    assert about_page.detect(f3) is None
    assert about_page.degradation(about_page.detect(f3)) is None
    assert list(AboutPageCheck().run(f5)) == []
    assert applicability.unread_applicable(f3, "llm.about_page") == 0
    assert about_page.selected_pages(f5) == []
    degraded: list[Degradation] = []
    _skipped, partial = _module_coverage(AuditOptions(), f3, [], degraded)
    assert Module.LLM_VISIBILITY not in partial
    assert _about_gaps(degraded) == []
    row = applicability.evidence_for_context(f3)["llm.about_page"]
    assert "detail" not in row


def _site(*pages: PageSignals, declared: str = "") -> SiteContext:
    return context(*pages)


def _html(*, title: str, h1: str = "", body: str = "", head: str = "", nav: str = "") -> str:
    return _e10_document(title=title, h1=h1 or title, body=body, head_extra=head, nav=nav)


def test_substring_routes_never_create_a_candidate() -> None:
    """`about-cookies`, `aboutique`, `team-building-tips`: підрядок — не маршрут."""
    prose = f"<p>{E10_PROSE_EN} Our mission and our values guide us since we were founded.</p>"
    pages = [page_from_html(_html(title="Crawldy", body=prose, head=E10_ORGANIZATION_LD),
                            url=f"{E10_ORIGIN}/")]
    for path in ("/about-cookies", "/aboutique", "/team-building-tips", "/company-news",
                 "/blog/all-about-us-and-them"):
        pages.append(page_from_html(_html(title="Crawldy", body=prose), url=E10_ORIGIN + path))
    about = about_page.detect(_site(*pages))
    assert about is not None
    assert (about.verdict, about.coverage, about.candidate) == (
        ClaimVerdict.FAIL, Coverage.COMPLETE, False
    )
    assert about.candidates == ()
    assert {"C1_organization_jsonld", "C3_first_person_prose", "C4_company_prose",
            "C5_team_mention", "C6_substring"} <= set(about.corroborating_seen)


def test_a_route_with_a_file_extension_is_the_same_route() -> None:
    home = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>"), url=f"{E10_ORIGIN}/")
    about = page_from_html(_html(title="Crawldy", body="<p>Two people in Kyiv.</p>"),
                           url=f"{E10_ORIGIN}/about.html")
    decision = about_page.detect(_site(home, about))
    assert decision is not None and decision.conclusive
    assert decision.selected_candidate is not None
    assert decision.selected_candidate.primary == ("P1_route_token",)


def test_routes_are_normalised_per_segment_the_g4a_way() -> None:
    """Відсоткове кодування й регістр — як у G4a: сегмент, а не рядок."""
    nav = _e10_chrome(("/uk/", "Головна"))
    home = page_from_html(_html(title="Crawldy", body="<p>Інструменти.</p>", nav=nav,
                                head=_e10_hreflang("uk", "en")), url=f"{E10_ORIGIN}/uk/")
    encoded = page_from_html(_html(title="Crawldy", body="<p>Двоє людей у Києві.</p>", nav=nav,
                                   head=_e10_hreflang("uk", "en")),
                             url=f"{E10_ORIGIN}/uk/%D0%9F%D0%A0%D0%9E-%D0%9D%D0%90%D0%A1")
    decision = about_page.detect(_site(home, encoded))
    assert decision is not None and decision.conclusive
    assert decision.selected == encoded.url
    assert decision.selected_candidate is not None
    assert "P1_route_token" in decision.selected_candidate.primary


@pytest.mark.parametrize(
    ("title", "intent"),
    [
        ("About us — Crawldy", True),
        ("About Crawldy", True),
        ("Über uns", True),
        ("Our team", True),
        ("About useful things", False),
        ("Everything about us", False),
        ("About cookies", False),
        ("О насекомых", False),
        ("Team building tips", False),
    ],
)
def test_title_intent_is_a_phrase_at_the_start_not_a_word_anywhere(
    title: str, intent: bool
) -> None:
    """Фраза на початку — намір; те саме слово посеред заголовка — ні.

    Бренд для форми «About <brand>» береться з фактів сайту (розмітка
    ідентичності), а не з назви головної: джерело мусить не залежати від
    порядку обходу.
    """
    home = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>",
                                head=E10_ORGANIZATION_LD), url=f"{E10_ORIGIN}/")
    page = page_from_html(_html(title=title, body="<p>Some readable text.</p>"),
                          url=f"{E10_ORIGIN}/page-7")
    decision = about_page.detect(_site(home, page))
    assert decision is not None
    assert decision.candidate is intent
    if intent:
        assert decision.selected_candidate is not None
        assert decision.selected_candidate.primary == ("P2_title_or_h1_intent",)


def test_the_brand_comes_from_site_facts_not_from_whichever_page_answered_first() -> None:
    """«About <brand>» потребує бренду з фактів сайту — розмітки ідентичності.

    Назва головної сторінки джерелом бути не може: «головна» для двигуна —
    перша сторінка, що відповіла, і рішення, яке залежить від неї,
    змінювалося б від порядку обходу. Без розмітки бренд невідомий, і
    «About Crawldy» — ще не намір; з нею — намір, у будь-якому порядку.
    """
    home = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>"), url=f"{E10_ORIGIN}/")
    page = page_from_html(_html(title="About Crawldy", body="<p>Two people in Kyiv.</p>"),
                          url=f"{E10_ORIGIN}/page-7")
    unknown = about_page.detect(_site(home, page))
    assert unknown is not None and unknown.verdict is ClaimVerdict.FAIL
    assert about_page.detect(_site(page, home)) == unknown
    marked = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>",
                                  head=E10_ORGANIZATION_LD), url=f"{E10_ORIGIN}/")
    known = about_page.detect(_site(marked, page))
    assert known is not None and known.conclusive and known.selected == page.url
    reversed_order = about_page.detect(_site(page, marked))
    assert reversed_order is not None and reversed_order.selected == page.url
    assert reversed_order.selected_candidate == known.selected_candidate


def test_login_wall_needs_both_the_password_field_and_the_missing_intent() -> None:
    """Жоден із двох фактів окремо не є стіною входу."""
    home = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>"), url=f"{E10_ORIGIN}/")
    form = ('<form method="post" action="/session"><input type="email" name="email">'
            '<input type="password" name="password"><button>Sign in</button></form>')

    def decide(title: str, body: str) -> about_page.AboutEvidence:
        page = page_from_html(_html(title=title, body=body), url=f"{E10_ORIGIN}/about")
        decision = about_page.detect(_site(home, page))
        assert decision is not None
        return decision

    wall = decide("Sign in", form)
    assert (wall.verdict, wall.coverage, wall.reason) == (
        ClaimVerdict.NO_VERDICT, Coverage.NOT_MEASURED, about_page.LOGIN_WALL
    )
    # Той самий пароль поруч із заголовком «про нас» — сторінка про компанію
    # з формою входу для клієнтів, а не стіна.
    assert decide("About us", f"<p>We are two people.</p>{form}").conclusive
    # Форма без пароля стіною входу не є, хай як зветься сторінка.
    no_password = form.replace('<input type="password" name="password">', "")
    assert decide("Sign in", no_password).conclusive


def test_redirect_placeholder_needs_both_the_meta_refresh_and_the_missing_intent() -> None:
    home = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>"), url=f"{E10_ORIGIN}/")
    refresh = '<meta http-equiv="refresh" content="0; url=/company">'
    placeholder = page_from_html(
        _html(title="Redirecting", body="<p>Redirecting…</p>", head=refresh),
        url=f"{E10_ORIGIN}/about")
    assert placeholder.meta_refresh == "0; url=/company"
    decision = about_page.detect(_site(home, placeholder))
    assert decision is not None
    assert (decision.verdict, decision.reason) == (
        ClaimVerdict.NO_VERDICT, about_page.REDIRECT_PLACEHOLDER
    )
    real = page_from_html(_html(title="About us", body="<p>We are two people.</p>", head=refresh),
                          url=f"{E10_ORIGIN}/about")
    decision = about_page.detect(_site(home, real))
    assert decision is not None and decision.conclusive


def test_the_extractor_retains_the_two_facts_the_predicates_need() -> None:
    page = page_from_html(
        '<html><head><meta http-equiv="Refresh" content="5; url=/x"></head><body>'
        '<form><input type="text" name="q"></form>'
        '<form><input type="Password" name="pw"></form></body></html>')
    assert page.meta_refresh == "5; url=/x"
    assert [f.has_password_field for f in page.forms] == [False, True]
    plain = page_from_html("<html><head><meta name='robots' content='index'></head>"
                           "<body><form><input type='email' name='e'></form></body></html>")
    assert plain.meta_refresh is None
    assert [f.has_password_field for f in plain.forms] == [False]


def test_a_menu_target_with_an_about_route_that_was_never_fetched_keeps_the_claim_open() -> None:
    """«Company» → /company, якого краул не відкрив: покриття неповне, не FAIL.

    Контракт (relevant coverage): усі цілі меню й адреси карти з маршрутом
    «про нас» мають бути прочитані, перш ніж сказати, що сторінки немає.
    Підпис «Company» — не фраза наміру, тож ознака тут — маршрут (P1).
    """
    nav = _e10_chrome(("/", "Home"), ("/company", "Company"), ("/blog", "Blog"))
    home = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>", nav=nav),
                          url=f"{E10_ORIGIN}/")
    blog = page_from_html(_html(title="Blog", body="<p>Posts.</p>", nav=nav),
                          url=f"{E10_ORIGIN}/blog")
    decision = about_page.detect(_site(home, blog))
    assert decision is not None
    assert (decision.verdict, decision.coverage) == (ClaimVerdict.NO_VERDICT, Coverage.PARTIAL)
    (unread,) = decision.unread
    assert (unread.url, unread.primary, unread.anchor) == (
        f"{E10_ORIGIN}/company", ("P1_route_token",), "Company"
    )
    assert decision.notice == (about_page.NOTICE_UNREAD,
                               {"url": f"{E10_ORIGIN}/company", "anchor": "Company"})
    # Ціль без маршруту «про нас» і без фрази в підписі покриття не тримає.
    plain = _e10_chrome(("/", "Home"), ("/pricing", "Pricing"), ("/blog", "Blog"))
    home = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>", nav=plain),
                          url=f"{E10_ORIGIN}/")
    settled = about_page.detect(_site(home))
    assert settled is not None and settled.verdict is ClaimVerdict.FAIL


def test_a_sitemap_about_url_that_was_never_fetched_keeps_the_claim_open() -> None:
    home = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>",
                                nav=_e10_chrome(("/", "Home"), ("/contact", "Contact"))),
                          url=f"{E10_ORIGIN}/")
    site = _site(home)
    site.sitemap = SitemapInfo(exists=True, url_count=2,
                               urls=[f"{E10_ORIGIN}/about-us", f"{E10_ORIGIN}/blog"])
    decision = about_page.detect(site)
    assert decision is not None
    assert (decision.verdict, decision.coverage, decision.candidate) == (
        ClaimVerdict.NO_VERDICT, Coverage.PARTIAL, True
    )
    (unread,) = decision.unread
    assert (unread.url, unread.primary, unread.anchor) == (
        f"{E10_ORIGIN}/about-us", ("P1_route_token",), "about-us"
    )
    assert decision.notice == (about_page.NOTICE_UNREAD,
                               {"url": f"{E10_ORIGIN}/about-us", "anchor": "about-us"})
    assert applicability.unread_applicable(site, "llm.about_page") == 1
    # Чужий хост у карті — чужа сторінка. Питання «той самий сайт» має в
    # двигуні одну відповідь, і детектор бере саме її.
    site.sitemap = SitemapInfo(exists=True, url_count=2,
                               urls=["https://partner.example.org/about-us",
                                     f"{E10_ORIGIN}/blog"])
    foreign = about_page.detect(site)
    assert foreign is not None
    assert (foreign.verdict, foreign.unread) == (ClaimVerdict.FAIL, ())


def test_brand_consistency_reads_the_about_page_only_when_it_is_conclusive() -> None:
    other = ('<script type="application/ld+json">{"@type":"Organization",'
             '"name":"Other Corp"}</script>')
    home = page_from_html(_html(title="Crawldy", body="<p>Tools.</p>"), url=f"{E10_ORIGIN}/")
    conclusive = page_from_html(_html(title="About us", body="<p>We are two.</p>", head=other),
                                url=f"{E10_ORIGIN}/about")
    (issue,) = BrandConsistencyCheck().run(_site(home, conclusive))
    assert issue.evidence["schema_names"] == ["other corp"]
    # Той самий вузол на стіні входу: вердикту немає, судиться лише
    # головна — а на ній розмітки немає, тож чек мовчить.
    wall = page_from_html(
        _html(title="Sign in", head=other,
              body='<form><input type="password" name="p"></form>'),
        url=f"{E10_ORIGIN}/about")
    assert list(BrandConsistencyCheck().run(_site(home, wall))) == []


def test_no_content_length_threshold_exists_in_the_detector() -> None:
    """Сторож на рівні джерела: жодного порога довжини в жодній формі.

    Заборонено порівнювати довжини й лічильники слів/абзаців/токенів;
    читабельність — лише присутність тексту. Сортування кандидатів за
    глибиною маршруту лічильником НЕ є: воно обирає між кандидатами, а не
    вирішує, чи кандидат прочитаний.
    """
    source = inspect.getsource(about_page)
    tree = ast.parse(source)
    banned = re.compile(r"threshold|min_words|word_count|paragraph|token_count|min_len|"
                        r"max_len|too_short|enough_text", re.IGNORECASE)
    assert not banned.search(source), banned.search(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare):
            literal = ast.unparse(node)
            assert "len(" not in literal, literal
            assert "word" not in literal.lower(), literal
    assert "readable = read and bool(page.text.strip())" in source


def test_about_notice_keys_exist_in_six_locales_with_identical_placeholders() -> None:
    """Обидва ключі всіма шістьма мовами — і жодного нашого слова в тексті.

    Слаг причини (`login_wall`) — внутрішній ідентифікатор. Німецький звіт із
    ним у реченні продавав би клієнтові наше слово; речення складається з
    каталогу, і цей тест стереже саме це.
    """
    placeholder = re.compile(r"\{(\w+)\}")
    params = {
        about_page.NOTICE_UNREAD: {"url": "https://x.example/about", "anchor": "About us"},
        about_page.NOTICE_UNREADABLE: {"url": "https://x.example/about",
                                       "reasons": ["about_page_login_wall"], "status": 200},
    }
    for key, values in params.items():
        expected = set(placeholder.findall(i18n.NOTICES[i18n.Locale.EN][key]))
        assert expected == set(values)
        for code in ("en", "uk", "de", "es", "fr", "ru"):
            locale = i18n.Locale(code)
            template = i18n.NOTICES[locale][key]
            assert set(placeholder.findall(template)) == expected, (code, key)
            rendered = i18n.notice(key, _reason_params(values, locale), locale)
            assert "https://x.example/about" in rendered and "{" not in rendered, (code, key)
            for slug in about_page.REASON_SLUG.values():
                assert slug not in rendered, (code, key, slug)
                assert i18n.notice(f"coverage.reason.{slug}", {}, locale)                     != f"coverage.reason.{slug}", (code, slug)
