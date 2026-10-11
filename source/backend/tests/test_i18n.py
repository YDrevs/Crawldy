"""Каталог повідомлень: повнота і відповідність параметрів шаблонам.

Це головний запобіжник i18n. Без нього переклад тихо деградує:
чек додається, ключа в каталозі немає, клієнт бачить у звіті `seo.foo.bar`.
"""

from __future__ import annotations

import pathlib
import re

import pytest

from app.audit import i18n
from app.audit.checks import all_checks
from app.audit.checks.base import all_message_keys
from app.audit.i18n import CATALOGS, DEFAULT_LOCALE, FIELDS, Locale
from app.audit.types import (
    InfraInfo,
    LlmsTxtInfo,
    MetricValue,
    PerformanceResult,
    RenderResult,
    ResourceLoad,
    RobotsInfo,
    SitemapInfo,
    Strategy,
)
from tests.factories import context, page_from_html

# Сторінка, зроблена так, щоб зачепити якнайбільше чеків одночасно.
BAD_HTML = """<html><head>
<title>Ко</title>
<meta name="description" content="Замало">
<meta name="robots" content="noindex">
<script src="/a.js"></script><script src="/b.js"></script><script src="/c.js"></script>
</head><body>
<h1>Один</h1><h1>Два</h1>
<a href="tel:+380441234567">Подзвоніть</a>
<h2>Розділ</h2><h4>Стрибок рівня</h4>
<img src="a.jpg"><img src="b.png"><img src="c.gif"><img src="d.jpg">
<script type="application/ld+json">{ не json }</script>
<script type="application/ld+json">{"name": "Без типу"}</script>
</body></html>"""


def _rich_context():
    page = page_from_html(BAD_HTML)
    inner = page_from_html(BAD_HTML, url="https://example.com/inner/", depth=1)
    perf = PerformanceResult(
        provider="psi",
        strategy=Strategy.MOBILE,
        url="https://example.com/",
        fetched=True,
        lighthouse_score=35.0,
        lab={
            "LCP": MetricValue(6000.0, "ms", "poor"),
            "INP": MetricValue(700.0, "ms", "poor"),
            "CLS": MetricValue(0.4, "", "poor"),
            "TTFB": MetricValue(2500.0, "ms", "poor"),
            "TBT": MetricValue(900.0, "ms", "poor"),
        },
    )
    return context(
        page,
        inner,
        is_https=False,
        hsts=False,
        robots=RobotsInfo(
            exists=True,
            status_code=200,
            disallows_all=True,
            blocked_ai_agents=["gptbot", "claudebot"],
            content="User-agent: *\nDisallow: /\n",
        ),
        sitemap=SitemapInfo(exists=True, status_code=200, url_count=1, urls=["https://other/"]),
        llms_txt=LlmsTxtInfo(exists=True, status_code=200, has_h1=False, section_count=0),
        performance=[perf],
        failed_urls={"https://example.com/gone": "HTTP 404"},
    )


# Дзеркальний контекст: порожній сайт замість зламаного. Разом вони
# покривають взаємовиключні гілки чеків (немає sitemap проти sitemap неповний).
EMPTY_HTML = (
    "<html><head></head><body><div id=app></div>"
    + "<span class='x'></span>" * 500
    + "</body></html>"
)


def _sparse_context():
    page = page_from_html(EMPTY_HTML)
    perf = PerformanceResult(
        provider="psi",
        strategy=Strategy.MOBILE,
        url="https://example.com/",
        fetched=False,
        error="429 Too Many Requests",
    )
    return context(
        page,
        is_https=True,
        hsts=False,
        robots=RobotsInfo(exists=False, status_code=404),
        sitemap=SitemapInfo(exists=False, status_code=404),
        llms_txt=LlmsTxtInfo(exists=False, status_code=404),
        performance=[perf],
    )


# Третій контекст: довга контентна сторінка. Суцільний потік без крапок і
# підзаголовків — саме те, на що реагують чеки читабельності й структури.
RUN_ON_TEXT = "аудит сайту для мовних моделей та пошукових систем " * 60
LONG_HTML = f"""<html lang="uk"><head>
<title>Дуже довгий заголовок сторінки, який гарантовано перевищує шістдесят символів межі</title>
<meta name="description" content="{'докладний опис сторінки ' * 12}">
<link rel="canonical" href="https://example.com/somewhere-else/">
<meta name="viewport" content="width=device-width">
</head><body>
<h1>Заголовок</h1>
<p>{RUN_ON_TEXT}</p>
{"".join(f'<img src="i{n}.webp" alt="a" width="10" height="10">' for n in range(10))}
</body></html>"""


def _content_context():
    page = page_from_html(LONG_HTML, url="https://example.com/blog/how-it-works", depth=1)
    return context(
        page,
        is_https=True,
        hsts=True,
        robots=RobotsInfo(exists=True, status_code=200, sitemaps=["https://example.com/s.xml"]),
        sitemap=SitemapInfo(exists=True, status_code=200, parse_error="not well-formed"),
        llms_txt=LlmsTxtInfo(exists=True, status_code=200, has_h1=True, section_count=3,
                             link_count=9),
    )


def _empty_sitemap_context():
    """seo.sitemap.empty і .invalid — взаємовиключні гілки, потрібен окремий контекст."""
    return context(
        page_from_html(BAD_HTML),
        sitemap=SitemapInfo(exists=True, status_code=200, url_count=0),
    )


def _slow_server_context(response_ms: int):
    """TTFB із власних вимірювань: slow і very_slow — різні пороги."""
    page = page_from_html(BAD_HTML)
    page.response_ms = response_ms
    return context(page)


PLACEHOLDER = re.compile(r"\{(\w+)\}")


def _placeholders(entry: dict[str, str]) -> set[str]:
    return {name for text in entry.values() for name in PLACEHOLDER.findall(text)}


# Сторінка з формами, зовнішніми хостами, mailto й «брудною» адресою.
TECH_HTML = """<html lang="uk"><head>
<title>Сторінка з формою та зовнішніми залежностями сайту</title>
<meta name="description" content="Опис довжиною десь у межах норми для перевірки чеків.">
<meta property="og:title" content="t"><meta property="og:description" content="d">
<meta property="og:type" content="website"><meta property="og:url" content="u">
<meta property="og:image" content="https://example.com/og.png">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">
<script src="https://cdn-a.example.net/a.js"></script>
<script src="https://cdn-b.example.net/b.js"></script>
<script src="https://cdn-c.example.net/c.js"></script>
<script src="https://cdn-d.example.net/d.js"></script>
<script src="https://cdn-e.example.net/e.js"></script>
<script src="https://cdn-f.example.net/f.js"></script>
<script src="https://www.googletagmanager.com/gtag/js?id=G-X"></script>
<script src="https://cdn-h.example.net/h.js"></script>
<script src="https://cdn-i.example.net/i.js"></script>
</head><body>
<h1>Заголовок</h1>
<a href="mailto:hello@example.com">Напишіть нам</a>
<a href="tel:+380441234567">Подзвоніть</a>
<form method="get" action="/lead">
  <input name="name"><input type="email" name="email"><textarea name="msg"></textarea>
</form>
<script type="application/ld+json">{"@type":"LocalBusiness","name":"X"}</script>
<script type="application/ld+json">{"@type":"WebSite","name":"X"}</script>
</body></html>"""


def _tech_context():
    """Захист, аналітика, зовнішні залежності — і «брудна» адреса сторінки."""
    page = page_from_html(TECH_HTML, url="https://example.com/Some_Section/?ref=ads")
    page.headers = {"content-type": "text/html"}
    return context(
        page,
        infra=InfraInfo(
            not_found_checked=True,
            not_found_status=200,
            not_found_is_soft=True,
            alt_host_checked=True,
            alt_host="https://www.example.com/",
            alt_host_status=200,
            alt_host_redirects_home=False,
        ),
    )


def _nap_context():
    """Різні телефони на сторінках і третій — у розмітці."""
    first = page_from_html(
        '<html><body><a href="tel:+380441234567">a</a>'
        '<script type="application/ld+json">'
        '{"@type":"LocalBusiness","telephone":"+380509999999"}</script></body></html>'
    )
    second = page_from_html(
        '<html><body><a href="tel:044 765 43 21">b</a></body></html>',
        url="https://example.com/contacts",
    )
    return context(first, second)


def _partial_headers_context():
    """Частина security-заголовків є: спрацьовує .missing, а не .none."""
    page = page_from_html(TECH_HTML, url="https://example.com/")
    page.headers = {
        "content-security-policy": "default-src 'self'",
        "x-frame-options": "DENY",
        "cache-control": "public, max-age=600",
    }
    page.analytics = ["google_analytics"]
    return context(page)


def _headingless_context():
    """Сторінка з title, але без жодного HTML-заголовка h1–h6.

    Чіпляє seo.h1.no_headings: варіант «заголовків немає взагалі»
    відрізняється від «немає h1, але є h2» і мусить мати власний
    синтетичний контекст.
    """
    page = page_from_html(
        "<html><head><title>Сторінка без заголовків</title></head>"
        "<body><main><p>" + "слово " * 120 + "</p></main></body></html>",
        url="https://example.com/headless",
    )
    # Друга сторінка: h1 немає, але h2 є — чіпляє варіант `missing`,
    # який тепер вимагає наявності ІНШОГО заголовка.
    with_h2 = page_from_html(
        "<html><head><title>Т</title></head>"
        "<body><main><h2>Розділ</h2><p>" + "слово " * 120 + "</p></main></body></html>",
        url="https://example.com/h2-only",
    )
    return context(page, with_h2)



def _bare_meta_context():
    """Голий title і надто короткий опис — нижні пороги змістовності."""
    page = page_from_html(
        '<html><head><title>Dronehub</title>'
        '<meta name="description" content="Коротко."></head>'
        "<body><h1>x</h1></body></html>"
    )
    return context(page)


def _broken_tls_context():
    """Сайт відкрився лише з вимкненою перевіркою сертифіката."""
    page = page_from_html(BAD_HTML)
    return context(
        page,
        is_https=True,
        tls_error="ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer",
    )


def _blocked_context():
    """Сайт віддав 403 замість контенту: жодної ok-сторінки немає."""
    page = page_from_html("<html><body>Access denied</body></html>")
    page.status_code = 403
    return context(page)


def _faq_context():
    """Сторінка з готовими питаннями, але без розмітки FAQPage."""
    html = """<html lang="uk"><head><title>Питання про доставку та оплату замовлень</title>
    <meta name="description" content="Відповіді на часті питання клієнтів про доставку.">
    </head><body><h1>Часті питання</h1>
    <h2>Скільки триває доставка?</h2><p>Один-три робочі дні по всій Україні.</p>
    <h2>Чи можна оплатити карткою?</h2><p>Так, картками Visa і Mastercard.</p>
    <h2>Як повернути товар?</h2><p>Протягом чотирнадцяти днів без пояснення причин.</p>
    </body></html>"""
    return context(page_from_html(html, url="https://example.com/faq/"))


def _rendered_context():
    """Сторінку відкрили в браузері — і лічильник так і не з'явився.

    Той самий факт, що й у _sparse_context, але підтверджений
    рендером, а не відсутністю рядка в HTML: різні твердження й різні
    ключі каталогу.
    """
    page = page_from_html(BAD_HTML)
    after = page_from_html(BAD_HTML)
    site = context(page)
    site.renders[page.url] = RenderResult(
        url=page.url, rendered=True, html=BAD_HTML, signals=after
    )
    return site


def _heavy_third_party_context():
    """Сторінка, три чверті ваги якої — чужі домени."""
    page = page_from_html(BAD_HTML)
    site = context(page)
    site.renders[page.url] = RenderResult(
        url=page.url,
        rendered=True,
        html=BAD_HTML,
        signals=page_from_html(BAD_HTML),
        resources=[
            ResourceLoad(
                url="https://example.com/app.js",
                host="example.com",
                resource_type="script",
                bytes=100_000,
            ),
            ResourceLoad(
                url="https://ads.example.net/tag.js",
                host="ads.example.net",
                resource_type="script",
                bytes=300_000,
                is_third_party=True,
            ),
        ],
    )
    return site


def _mobile_gap_context():
    """Швидко на комп'ютері, повільно на телефоні — розрив між пристроями."""
    fast = PerformanceResult(
        provider="psi",
        strategy=Strategy.DESKTOP,
        url="https://example.com/",
        fetched=True,
        lighthouse_score=92.0,
        lab={"LCP": MetricValue(1200.0, "ms", "good")},
    )
    slow = PerformanceResult(
        provider="psi",
        strategy=Strategy.MOBILE,
        url="https://example.com/",
        fetched=True,
        lighthouse_score=41.0,
        lab={"LCP": MetricValue(4800.0, "ms", "poor")},
    )
    return context(page_from_html(BAD_HTML), performance=[slow, fast])


def _issues_of(ctx) -> list:
    return [issue for check in all_checks() for issue in check.run(ctx)]



def _crawler_purpose_context(kind: str):
    """robots.txt, що блокує рівно одне призначення краулерів.

    Три окремі контексти, бо детектор навмисно віддає одну знахідку на
    аудит — ту, що описує найважливіше із заблокованого. Побачити всі
    три формулювання можна лише на трьох різних сайтах, і саме так вони
    трапляються насправді.
    """
    tokens = {
        "search": ("OAI-SearchBot", "Claude-SearchBot"),
        "grounding": ("Google-Extended",),
        "user": ("ChatGPT-User", "Claude-User"),
        "training": ("GPTBot", "ClaudeBot"),
    }[kind]
    lines = "".join(f"User-agent: {t}\nDisallow: /\n\n" for t in tokens)
    return context(
        page_from_html(BAD_HTML),
        robots=RobotsInfo(exists=True, status_code=200, content=lines),
    )



RENDER_BASE = (
    "<html><head><title>Server title</title></head>"
    '<body><h1>Heading</h1><a href="/a">a</a><p>text</p></body></html>'
)


def _render_delta_context(kind: str):
    """Сторінка, у якої після рендеру різниться рівно одна група сигналів.

    Чотири окремі контексти, бо чек навмисно віддає одну знахідку на
    сторінку — найважливішу з груп. Побачити всі чотири формулювання
    можна лише на чотирьох різних сторінках.
    """
    from app.audit.extractor import signals_from_html
    from app.audit.types import RenderResult

    rendered_html = {
        "indexing": RENDER_BASE.replace(
            "<head>", '<head><meta name="robots" content="noindex">'
        ),
        "identity": RENDER_BASE.replace("Server title", "Client title"),
        "markup": RENDER_BASE.replace(
            "</head>",
            '<script type="application/ld+json">{"@type":"Organization"}</script></head>',
        ),
        "links": RENDER_BASE.replace(
            '<a href="/a">a</a>', '<a href="/a">a</a><a href="/b">b</a>'
        ),
    }[kind]

    page = page_from_html(RENDER_BASE)
    ctx = context(page)
    result = RenderResult(url=page.url, rendered=True, html=rendered_html)
    result.signals = signals_from_html(
        page.url, rendered_html, origin="https://example.com", depth=0
    )
    ctx.renders[page.url] = result
    return ctx



def _hreflang_html(links, canonical=None, lang="en", robots=None):
    """Сторінка з оголошеними версіями. Порожній список — жодного оголошення."""
    head = "".join(
        f'<link rel="alternate" hreflang="{code}" href="{href}">' for code, href in links
    )
    if canonical:
        head += f'<link rel="canonical" href="{canonical}">'
    if robots:
        head += f'<meta name="robots" content="{robots}">'
    return (
        f'<html lang="{lang}"><head><title>Page</title>{head}</head>'
        "<body><h1>Heading</h1><p>Text about the product.</p></body></html>"
    )


def _hreflang_context(kind: str):
    """Один дефект оголошених версій на контекст.

    Родина чеків мовчить на сайті без оголошень, тож кожен контекст
    мусить щось оголосити — крім останнього, який якраз про мовчання.
    """
    home = "https://example.com/"
    de = "https://example.com/de"

    if kind == "invalid":
        return context(page_from_html(_hreflang_html([("en_US", home), ("gb", de)])))

    if kind == "self":
        return context(page_from_html(_hreflang_html([("de", de)])))

    if kind == "return":
        # Друга сторінка існує, ми її прочитали, і вона мовчить у відповідь.
        return context(
            page_from_html(_hreflang_html([("en", home), ("de", de)])),
            page_from_html(_hreflang_html([], lang="de"), url=de),
        )

    if kind == "duplicate":
        return context(
            page_from_html(
                _hreflang_html([("en", home), ("de", de), ("de", home + "de-at")])
            )
        )

    if kind == "x_default":
        return context(
            page_from_html(
                _hreflang_html(
                    [("en", home), ("x-default", home), ("x-default", de)]
                )
            )
        )

    if kind == "canonical":
        return context(
            page_from_html(
                _hreflang_html([("en", home), ("de", de)], canonical=home + "other")
            )
        )

    if kind == "unreachable":
        gone = page_from_html(_hreflang_html([], lang="de"), url=de)
        gone.status_code = 404
        return context(page_from_html(_hreflang_html([("en", home), ("de", de)])), gone)

    if kind == "noindex":
        closed = page_from_html(_hreflang_html([("en", home)], lang="de", robots="noindex"), url=de)
        return context(page_from_html(_hreflang_html([("en", home), ("de", de)])), closed)

    # kind == "missing": кілька мов і жодного оголошення ніде.
    pages = [
        page_from_html(_hreflang_html([], lang=lang), url=f"https://example.com/{slug}")
        for slug, lang in (("a", "en"), ("b", "en-GB"), ("c", "de"), ("d", "de-AT"))
    ]
    return context(*pages)



def _redirect_context(kind: str):
    """Сторінка, до якої вів той чи інший шлях перенаправлень."""
    page = page_from_html(BAD_HTML, url="https://example.com/final")

    if kind == "chain":
        page.redirected_from = "https://example.com/old"
        page.redirect_chain = (
            (301, "https://example.com/mid"),
            (302, "https://example.com/final"),
        )
        return context(page)

    if kind == "repeated":
        page.redirected_from = "https://example.com/a"
        page.redirect_chain = (
            (302, "https://example.com/b"),
            (302, "https://example.com/a"),
            (302, "https://example.com/final"),
        )
        return context(page)

    if kind == "target":
        page.redirected_from = "https://example.com/gone"
        page.redirect_chain = ((301, "https://example.com/final"),)
        page.status_code = 404
        return context(page)

    # kind == "limit": сторінки немає взагалі, є лише факт про краул.
    ctx = context(page_from_html(BAD_HTML))
    ctx.redirect_limited = ["https://example.com/spins"]
    return ctx



def _sitemap_consistency_context():
    """Карта, у якій кожна адреса неузгоджена по-своєму.

    Один контекст на всі пʼять причин: чек віддає окрему знахідку на
    кожну, тож розводити їх по різних контекстах не потрібно.
    """
    from app.audit.types import SitemapInfo

    # BAD_HTML сам несе `noindex`, а він у пріоритеті вищий за canonical і
    # службовий тип — на ньому дві причини з пʼяти ніколи б не спрацювали.
    plain = (
        "<html lang='en'><head><title>Page</title></head>"
        "<body><h1>Heading</h1><p>Some words on the page.</p></body></html>"
    )
    site = "https://example.com"
    urls = [
        f"{site}/gone",       # відповість помилкою
        f"{site}/moved",      # перенаправляє
        f"{site}/hidden",     # noindex
        f"{site}/dupe",       # canonical в інше місце
        f"{site}/cart",       # службова сторінка
    ]

    gone = page_from_html(plain, url=f"{site}/gone")
    gone.status_code = 404

    moved = page_from_html(plain, url=f"{site}/final")
    moved.redirected_from = f"{site}/moved"
    moved.redirect_chain = ((301, f"{site}/final"),)

    hidden = page_from_html(BAD_HTML, url=f"{site}/hidden")
    hidden.meta_robots = "noindex, follow"

    dupe = page_from_html(plain, url=f"{site}/dupe")
    dupe.canonical = f"{site}/canonical-one"

    cart = page_from_html(plain, url=f"{site}/cart")

    ctx = context(gone, moved, hidden, dupe, cart)
    ctx.sitemap = SitemapInfo(
        exists=True,
        status_code=200,
        url=f"{site}/sitemap.xml",
        url_count=len(urls),
        urls=urls,
        sources={u: f"{site}/sitemap.xml" for u in urls},
    )
    return ctx



def _anchor_text_context():
    """Сторінки, де той самий підпис веде на різні цілі.

    Підпис мусить бути контекстним, а не в меню: обвʼязку сайту чек
    навмисно не судить. Мова сторінки потрібна теж — без неї перелік
    загальних фраз не застосовується.
    """
    plain = (
        "<html lang='en'><head><title>Blog</title></head><body><h1>Blog</h1>"
        '<a href="https://example.com/a">Learn more</a>'
        '<a href="https://example.com/b">Learn more</a>'
        "<p>Some words on the page.</p></body></html>"
    )
    target = (
        "<html lang='en'><head><title>Target</title></head>"
        "<body><h1>Target</h1><p>Some words on the page.</p></body></html>"
    )
    return context(
        page_from_html(plain, url="https://example.com/blog"),
        page_from_html(target, url="https://example.com/a"),
        page_from_html(target, url="https://example.com/b"),
    )



def _mixed_content_context(kind: str):
    """Захищена сторінка, яка просить підресурс по http.

    Чотири випадки: блокований клас, підвищуваний, завантаження й запит,
    якого в розмітці немає — його бачив лише браузер.
    """
    from app.audit.types import RenderResult

    markup = {
        "blockable": '<script src="http://cdn.old/a.js"></script>',
        "upgradeable": '<img src="http://img.old/p.jpg">',
        "download": '<a download href="http://files.old/report.pdf">Report</a>',
        "runtime": "",
    }[kind]
    html = (
        "<html lang='en'><head><title>Page</title>" + markup + "</head>"
        "<body><h1>Heading</h1><p>Some words here.</p></body></html>"
    )
    page = page_from_html(html, url="https://example.com/")
    ctx = context(page)
    if kind == "runtime":
        result = RenderResult(url=page.url, rendered=True, html=html)
        result.requests = ["http://beacon.old/hit"]
        ctx.renders[page.url] = result
    return ctx



def _duplicate_content_context(kind: str):
    """Дві адреси з однаковим вмістом і різним станом canonical."""
    body = (
        "<html lang='en'><head><title>Same</title>{c}</head><body><h1>Same</h1>"
        "<p>" + " ".join(f"sentence number {i} about the product" for i in range(40)) +
        "</p></body></html>"
    )
    other = "<html lang='en'><head><title>X</title></head><body><h1>X</h1><p>" +         " ".join(f"different words {i} entirely here" for i in range(40)) + "</p></body></html>"
    if kind == "conflicting":
        first = body.format(c='<link rel="canonical" href="https://example.com/one">')
        second = body.format(c='<link rel="canonical" href="https://example.com/elsewhere">')
    else:
        first = second = body.format(c="")
    return context(
        page_from_html(first, url="https://example.com/one"),
        page_from_html(second, url="https://example.com/two"),
        page_from_html(other, url="https://example.com/three"),
    )



def _transport_context(kind: str):
    """Відповідь без стиснення або віддана старішим протоколом."""
    page = page_from_html(BAD_HTML)
    page.content_type = "text/html"
    page.html_bytes = 60_000
    page.accept_encoding = "gzip, deflate"
    if kind == "uncompressed":
        page.http_version = "HTTP/2"
        page.headers = {"content-length": "60000"}
    else:
        page.http_version = "HTTP/1.1"
        page.headers = {"content-encoding": "gzip", "content-length": "9000"}
    return context(page)


def _all_issues():
    return (
        _issues_of(_rich_context())
        + _issues_of(_sparse_context())
        + _issues_of(_content_context())
        + _issues_of(_empty_sitemap_context())
        + _issues_of(_slow_server_context(1200))
        + _issues_of(_slow_server_context(3000))
        + _issues_of(_tech_context())
        + _issues_of(_partial_headers_context())
        + _issues_of(_nap_context())
        + _issues_of(_bare_meta_context())
        + _issues_of(_headingless_context())
        + _issues_of(_broken_tls_context())
        + _issues_of(_blocked_context())
        + _issues_of(_faq_context())
        + _issues_of(_rendered_context())
        + _issues_of(_heavy_third_party_context())
        + _issues_of(_mobile_gap_context())
        + _issues_of(_unstated_facts_context())
        + _issues_of(_demo_content_context())
        + _issues_of(_accessibility_context())
        + _issues_of(_crawler_purpose_context("search"))
        + _issues_of(_crawler_purpose_context("grounding"))
        + _issues_of(_crawler_purpose_context("user"))
        + _issues_of(_crawler_purpose_context("training"))
        + _issues_of(_render_delta_context("indexing"))
        + _issues_of(_render_delta_context("identity"))
        + _issues_of(_render_delta_context("markup"))
        + _issues_of(_render_delta_context("links"))
        + _issues_of(_link_graph_context())
        + _issues_of(_hierarchy_context())
        + _issues_of(_topic_islands_context())
        + _issues_of(_no_conversion_context())
        + _issues_of(_stale_content_context())
        + _issues_of(_stale_content_sparse_context())
        + _issues_of(_heavy_page_context())
        + _issues_of(_truncated_page_context())
        + _issues_of(_hreflang_context("invalid"))
        + _issues_of(_hreflang_context("self"))
        + _issues_of(_hreflang_context("return"))
        + _issues_of(_hreflang_context("duplicate"))
        + _issues_of(_hreflang_context("x_default"))
        + _issues_of(_hreflang_context("canonical"))
        + _issues_of(_hreflang_context("unreachable"))
        + _issues_of(_hreflang_context("noindex"))
        + _issues_of(_hreflang_context("missing"))
        + _issues_of(_redirect_context("chain"))
        + _issues_of(_redirect_context("repeated"))
        + _issues_of(_redirect_context("target"))
        + _issues_of(_redirect_context("limit"))
        + _issues_of(_sitemap_consistency_context())
        + _issues_of(_anchor_text_context())
        + _issues_of(_mixed_content_context("blockable"))
        + _issues_of(_mixed_content_context("upgradeable"))
        + _issues_of(_mixed_content_context("download"))
        + _issues_of(_mixed_content_context("runtime"))
        + _issues_of(_duplicate_content_context("unconsolidated"))
        + _issues_of(_duplicate_content_context("conflicting"))
        + _issues_of(_transport_context("uncompressed"))
        + _issues_of(_transport_context("http1"))
    )


def _heavy_page_context():
    """Сторінка, розмітка якої важить понад два мегабайти."""
    page = page_from_html(LONG_HTML, url="https://example.com/heavy", depth=1)
    page.html_bytes = 3 * 1024 * 1024
    return context(page)


def _truncated_page_context():
    """Сторінка, яка не помістилася в межу завантаження.

    Знайдено на myfriendlythai.ca: головна ресторану впиралася в пʼять
    мегабайтів і містила 111 тисяч слів спам-коментарів.
    """
    from app.core.config import settings

    page = page_from_html(LONG_HTML, url="https://example.com/spammed", depth=1)
    page.html_bytes = settings.max_response_bytes
    page.word_count = 111028
    return context(page)


def _stale_content_context():
    """Блог, найсвіжіша дата якого — багаторічної давнини."""
    pages = [
        page_from_html(
            "<html lang='uk'><head><title>Стаття про доставку меблів "
            f"номер {n}</title></head><body><h1>Заголовок</h1><p>Текст.</p>"
            '<script type="application/ld+json">'
            '{"@type":"BlogPosting","datePublished":"2019-03-1'
            f'{n}","dateModified":"2019-04-1{n}"}}</script>'
            "</body></html>",
            url=f"https://example.com/blog/article-{n}",
            depth=1,
        )
        for n in range(3)
    ]
    return context(*pages)


def _stale_content_sparse_context():
    """Той самий давній блог, але дати лише на меншості прочитаних сторінок.

    Саме цей випадок дає вузьке формулювання: три датовані сторінки з
    двадцяти чотирьох не дозволяють судити про сайт цілком.
    """
    dated = _stale_content_context().pages
    plain = [
        page_from_html(
            "<html lang='uk'><head><title>Сторінка послуги номер "
            f"{n}</title></head><body><h1>Послуга</h1><p>Опис послуги.</p></body></html>",
            url=f"https://example.com/service-{n}",
            depth=1,
        )
        for n in range(9)
    ]
    return context(*dated, *plain)


def _topic_islands_context():
    """Блог із трьох статей, жодна з яких не згадує сусідніх."""
    pages = [
        page_from_html(
            f"<html><head><title>Стаття номер {n} про доставку меблів</title></head>"
            "<body><h1>Заголовок</h1><p>Текст.</p>"
            '<a href="/">на головну</a><a href="/contacts/">контакти</a>'
            "</body></html>",
            url=f"https://example.com/blog/article-{n}",
            depth=1,
        )
        for n in range(3)
    ]
    return context(*pages)


def _hierarchy_context():
    """Сайт із доведеною ієрархією й без «хлібних крихт».

    Розділ каталогу посилається на сторінку товару, і шлях товару
    продовжує шлях розділу — один перевірений звʼязок «батько → дитина»,
    якого E-15 і вимагає. Розмітки `BreadcrumbList` немає ніде, тож
    `ai.schema.breadcrumb` спрацьовує саме на тому, про що він говорить.

    Без такого сайту ключ цього чека не чіпляв жоден синтетичний контекст:
    решта тридцяти пʼяти плаcкі, і це виміряно, а не припущено.
    """
    prose = (
        "<p>Ми робимо дубові стільці та столи для кухні й вітальні. Кожен виріб "
        "збирається вручну, тож у майстерні завжди знають, з якого дерева зроблено "
        "конкретний стілець і коли його віддали на фарбування. Нижче — розділи "
        "каталогу з описом матеріалів, розмірів і термінів виготовлення.</p>"
    )
    nav = '<nav><ul><li><a href="/">Головна</a></li>' \
          '<li><a href="/catalog/chairs/">Стільці</a></li></ul></nav>'
    home = page_from_html(
        f'<html><head><title>Меблева майстерня: дубові стільці та столи</title></head>'
        f"<body>{nav}<main><h1>Майстерня</h1>{prose}</main></body></html>"
    )
    section = page_from_html(
        f'<html><head><title>Стільці з дуба — каталог майстерні</title>'
        f'<script type="application/ld+json">'
        f'{{"@context":"https://schema.org","@type":"CollectionPage","name":"Стільці"}}'
        f"</script></head>"
        f"<body>{nav}<main><h1>Стільці</h1>{prose}"
        f'<a href="/catalog/chairs/oak/">Дубовий стілець</a></main></body></html>',
        url="https://example.com/catalog/chairs/",
        depth=1,
    )
    item = page_from_html(
        f'<html><head><title>Дубовий стілець ручної роботи</title>'
        f'<script type="application/ld+json">'
        f'{{"@context":"https://schema.org","@type":"Product","name":"Дубовий стілець"}}'
        f"</script></head>"
        f"<body>{nav}<main><h1>Дубовий стілець</h1>{prose}</main></body></html>",
        url="https://example.com/catalog/chairs/oak/",
        depth=2,
    )
    return context(
        home,
        section,
        item,
        sitemap=SitemapInfo(
            exists=True,
            status_code=200,
            url_count=3,
            urls=[
                "https://example.com/",
                "https://example.com/catalog/chairs/",
                "https://example.com/catalog/chairs/oak/",
            ],
            index_complete=True,
        ),
    )


def _link_graph_context():
    """Сайт, де карта сайту багатша за навігацію: одна сторінка в карті й
    без жодного посилання на неї, друга — в меню, але закрита від пошуку."""
    from app.audit.link_graph import build as build_graph

    home = page_from_html(
        '<html><head><title>Головна сторінка магазину меблів у місті</title></head>'
        '<body><h1>Головна</h1><a href="/hidden/">Особистий кабінет</a></body></html>'
    )
    hidden = page_from_html(
        '<html><head><title>Кабінет</title><meta name="robots" content="noindex">'
        "</head><body><h1>Кабінет</h1></body></html>",
        url="https://example.com/hidden/",
        depth=1,
    )
    lonely = page_from_html(BAD_HTML, url="https://example.com/lonely/", depth=1)
    ctx = context(
        home,
        hidden,
        lonely,
        sitemap=SitemapInfo(
            exists=True,
            status_code=200,
            url_count=3,
            urls=[
                "https://example.com/",
                "https://example.com/hidden/",
                "https://example.com/lonely/",
            ],
        ),
    )
    ctx.links = build_graph(ctx)
    return ctx


def _no_conversion_context():
    """Сторінка послуги без жодного способу діяти й номер лише текстом.

    Сторінку треба саме відрендерити: чек про відсутню дію судить лише
    про те, що ми відкривали в браузері.
    """
    body = (
        "<p>Ремонтуємо покрівлю будь-якої складності: бітумну черепицю, "
        "металочерепицю та мʼяку покрівлю на пласких дахах. Виїжджаємо на "
        "обʼєкт, оглядаємо конструкцію й показуємо фотозвіт до початку робіт. "
        "Працюємо з приватними будинками та комерційними обʼєктами по всій "
        "області. Матеріали закуповуємо напряму, тому ціна виходить нижчою за "
        "роздрібну, а на роботи діє гарантія три роки. Бригада виходить на "
        "обʼєкт протягом двох робочих днів після узгодження кошторису, а "
        "термінові аварійні виїзди робимо того ж дня, включно з вихідними та "
        "святами. Кошторис складаємо після огляду й не змінюємо його в "
        "процесі робіт. Телефонуйте: +38 (044) 123-45-67</p>"
    )
    service = page_from_html(
        "<html lang='uk'><head><title>Ремонт покрівлі під ключ у Києві</title></head>"
        f"<body><h1>Ремонт покрівлі</h1>{body}"
        "<a href='/about'>Про нас</a></body></html>",
        url="https://example.com/services/roof-repair",
        depth=1,
    )
    about = page_from_html(
        "<html lang='uk'><head><title>Про компанію та її команду</title></head>"
        "<body><h1>Про нас</h1><p>Телефон: +38 (044) 123-45-67</p></body></html>",
        url="https://example.com/about",
        depth=1,
    )
    ctx = context(service, about)
    ctx.renders[service.url] = RenderResult(
        url=service.url, rendered=True, html="", signals=service
    )
    return ctx


def _accessibility_context():
    """Доступність приходить із Lighthouse, тож контекст мусить мати
    вимірювання: без нього чек мовчить — і правильно робить."""
    from app.audit.types import PerformanceResult, Strategy

    ctx = context(page_from_html(BAD_HTML))
    measured = PerformanceResult(
        provider="psi", strategy=Strategy.MOBILE, url="https://example.com/", fetched=True
    )
    measured.accessibility_score = 73.0
    measured.accessibility_failures = [
        {"id": "meta-viewport", "title": "[user-scalable=no] is used", "impact": ""},
        {"id": "color-contrast", "title": "Contrast is insufficient", "impact": ""},
        {"id": "tabindex", "title": "Some elements have a [tabindex] over 0", "impact": ""},
    ]
    ctx.performance = [measured]
    return ctx


def _demo_content_context():
    """Сайт на конструкторі з демо-даними: пошта на домені теми, телефон-
    заглушка й вигадана команда. Знахідка потребує збігу сигналів, тож
    контекст мусить дати щонайменше два."""
    from app.audit.site_facts import SiteKnowledge

    ctx = context(page_from_html(BAD_HTML))
    for slug, title in (("mark-liuw", "Mark Liuw - Smart"), ("angela-kwang", "Angela Kwang - Smart")):
        person = page_from_html(BAD_HTML, url=f"https://example.com/team/{slug}/")
        person.title = title
        ctx.pages.append(person)
    ctx.known = SiteKnowledge(
        emails=["seofy@mail.com"], phones=["+8(123)985789"],
    )
    return ctx


def _unstated_facts_context():
    """Сайт, що не називає жодного з фактів, і бізнес, якому потрібні всі
    чотири: інакше гейти чека відсіяли б половину ключів."""
    from app.audit.llm.base import Fact, SiteFacts

    ctx = context(page_from_html(BAD_HTML))
    ctx.facts = SiteFacts(
        analysed=True,
        facts=[
            Fact(key=key, stated=False)
            for key in ("offering", "location", "pricing")
        ],
        serves_an_area=True,
        sells_listed_items=True,
        read_pages=["https://example.com/"],
    )
    return ctx


@pytest.mark.parametrize("locale", sorted(i18n.COMPLETE_LOCALES))
def test_a_complete_catalog_covers_every_declared_key(locale: Locale):
    """Повнота вимагається лише від повних мов.

    Вимагати її від усіх одинадцяти означало б, що кожен новий чек не
    можна змерджити без одинадцяти перекладів того самого дня — тобто
    або зупинити двигун, або писати переклади абияк.
    """
    missing = i18n.missing_keys(all_message_keys())[locale]
    assert not missing, f"немає перекладу {locale.value}: {sorted(missing)}"


def test_a_partial_catalog_is_allowed_to_be_incomplete():
    """Часткова мова працює — просто окремі рядки в ній англійські."""
    partial = set(i18n.LOCALES) - i18n.COMPLETE_LOCALES
    assert partial, "хоч одна мова має бути частковою, інакше поділ не потрібен"
    for locale in partial:
        text = i18n.render("seo.h1.missing", locale=locale)
        assert text.title, "рядок є"
        assert text.locale is Locale.EN, "і він англійський"


def test_the_english_catalog_is_the_one_that_must_be_complete():
    """Фолбек мусить бути повним: інакше падати нікуди."""
    assert i18n.FALLBACK_LOCALE in i18n.COMPLETE_LOCALES


def test_catalog_has_no_orphan_keys():
    """Ключ у каталозі, який жоден чек не віддає, — мертвий переклад.

    Виняток — свідомо вилучені ключі: їхні рядки живуть заради
    ЗБЕРЕЖЕНИХ аудитів, які мусять рендеритися й після вилучення чека.
    """
    from app.audit.checks.base import RETIRED_MESSAGE_KEYS

    declared = all_message_keys() | RETIRED_MESSAGE_KEYS
    for locale, catalog in CATALOGS.items():
        orphans = set(catalog) - declared
        assert not orphans, f"зайві ключі в {locale.value}: {sorted(orphans)}"


def test_every_key_has_nonempty_title():
    """Базове поле обовʼязкове, а форми множини — дозволені поруч із ним.

    `title.one`, `title.few` — той самий заголовок для іншої кількості.
    Базовий `title` при цьому лишається обовʼязковим: він і є формою
    `other`, тобто тим, що побачить мова без власного правила.
    """
    from app.audit.i18n import allowed_catalog_keys

    permitted = allowed_catalog_keys()
    for locale, catalog in CATALOGS.items():
        for key, entry in catalog.items():
            assert entry.get("title"), f"{locale.value}/{key}: порожній title"
            assert set(entry) <= permitted, f"{locale.value}/{key}: невідомі поля"


def test_plural_titles_are_rendered_for_every_form_they_declare():
    """Оголошена форма мусить бути досяжною: інакше вона мертвий рядок."""
    from app.audit.i18n import PLURAL_FORMS, plural_form, render

    for locale, catalog in CATALOGS.items():
        for key, entry in catalog.items():
            declared = {
                f.split(".", 1)[1] for f in entry if f.startswith("title.")
            }
            if not declared:
                continue
            reachable = {
                plural_form(locale.value, n) for n in range(0, 200)
            }
            unreachable = declared - reachable
            assert not unreachable, f"{locale.value}/{key}: недосяжні форми {unreachable}"
            assert declared <= set(PLURAL_FORMS), f"{locale.value}/{key}: чужа форма"
            for n in (1, 2, 5, 21):
                title = render(key, {"count": n}, locale).title
                assert "{count}" not in title, f"{locale.value}/{key}/{n}"
                assert str(n) in title, f"{locale.value}/{key}/{n}"


def test_every_key_explains_the_consequence_in_plain_language():
    """Нетехнічна частина звіту складається саме з consequence — він обовʼязковий."""
    for locale, catalog in CATALOGS.items():
        for key, entry in catalog.items():
            text = entry.get("consequence", "")
            assert text, f"{locale.value}/{key}: немає consequence"
            assert text[-1] in ".!?", f"{locale.value}/{key}: consequence не речення"


def test_consequence_avoids_the_jargon_of_the_technical_wording():
    """Наслідок пишеться для людини, яка не знає, що таке canonical чи JSON-LD.

    Саме з цих рядків складається звіт для власника бізнесу, і планка
    там вища, ніж «зрозуміло керівнику»: читач може не знати навіть
    слова «індексація». Слова на кшталт «мовна модель» замінені на
    «ChatGPT», а «трафік» — на «відвідувачі»: назва сервісу зрозуміла
    без пояснень, категорія — ні.
    """
    jargon = ("canonical", "JSON-LD", "json-ld", "meta ", "robots.txt", "sitemap.xml",
              "H1", "H2", "alt", "viewport", "LCP", "CLS", "TTFB", "INP", "schema.org",
              "мовн", "language model", "трафік", "traffic", "індекс", "render", "рендер",
              "краул", "crawl", "парс", "parse")
    offenders = [
        f"{locale.value}/{key}: {word}"
        for locale, catalog in CATALOGS.items()
        for key, entry in catalog.items()
        for word in jargon
        if _term_in(word, entry.get("consequence", ""))
        and not key.startswith(_allowed_prefix(word))
    ]
    assert not offenders, f"жаргон у нетехнічному тексті: {offenders}"


def _term_in(word: str, text: str) -> bool:
    """Коротке латинське слово шукається як слово, а не як підрядок.

    Підрядок брехав би шістьма мовами одразу: німецьке «Inhalt» і
    іспанське «falta» містять «alt», хоч жодного стосунку до атрибута
    не мають. Кириличні основи («мовн», «краул») лишаються підрядками
    навмисно — вони й задумані ловити відмінкові форми.
    """
    import re

    if re.fullmatch(r"[A-Za-z0-9]+", word):
        return re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text) is not None
    return word in text


def _allowed_prefix(word: str) -> str:
    """Кілька термінів неминучі там, де сама проблема — про цей файл.

    `meta ` доданий за тим самим правилом, а не як послаблення: чек
    `seo.meta_description` НАЗИВАЄТЬСЯ описом сторінки в пошуку, і
    назвати його інакше — це або описова перифраза на пів рядка, або
    неправда про те, чого бракує. Виняток вузький: він діє лише на
    ключі цього чека, і будь-де ще `meta ` у нетехнічному тексті
    лишається помилкою.
    """
    return {
        "robots.txt": "seo.robots_txt",
        "sitemap.xml": "seo.sitemap",
        "meta ": "seo.meta_description",
    }.get(word, "\0")


def test_synthetic_contexts_fire_every_message():
    """Гарантія, що перевірка плейсхолдерів нижче охоплює весь каталог.

    Новий ключ без контексту, який його чіпляє, валить цей тест — інакше
    його шаблон ніколи не перевірявся б на відповідність params.
    """
    never_fired = all_message_keys() - {issue.msg for issue in _all_issues()}
    assert not never_fired, f"жоден синтетичний контекст не чіпляє: {sorted(never_fired)}"


def test_every_issue_carries_evidence():
    """Інваріант: знахідка без доказів клієнта не переконує.

    На вибірці з 67 сайтів 16 чеків віддавали знахідки з порожнім
    evidence — зокрема «немає canonical» і «немає H1», найчастотніші
    у звітах. Перевірити таку знахідку неможливо, а сперечатися з нею
    легко: саме доказ відрізняє аудит від переліку припущень.
    """
    without = sorted({issue.msg for issue in _all_issues() if not issue.evidence})
    assert not without, f"знахідки без доказів: {without}"


def test_rendered_issues_have_no_unfilled_placeholders():
    """Параметри чека мають покривати всі {плейсхолдери} шаблону."""
    for issue in _all_issues():
        for field in FIELDS:
            text = getattr(issue, field)
            assert "{" not in text, f"{issue.msg}.{field}: незаповнений плейсхолдер у «{text}»"


def test_issue_carries_key_and_params_for_relocalisation():
    issues = _all_issues()
    assert all(issue.msg for issue in issues), "issue без msg не можна перекласти у звіті"

    parametrised = [i for i in issues if i.params]
    assert parametrised, "жоден чек не передав params — перевір міграцію на i18n"


def test_locales_are_actually_different_texts():
    """Захист від «переклад = копія української».

    Порівнюємо запис цілком, а не title: у метрик заголовок навмисне
    однаковий («LCP = {value}{unit}»), бо це формула, а не текст.
    """
    same = [key for key in all_message_keys() if CATALOGS[Locale.EN][key] == CATALOGS[Locale.UK][key]]
    assert not same, f"англійська дублює українську: {sorted(same)}"


def test_a_missing_translation_falls_back_to_english_not_to_ukrainian():
    """Найважливіше правило фолбеку, і воно довго було іншим.

    Поки фолбеком була українська, читач із неперекладеним ключем
    отримував не англійський рядок, а український — і виглядало це не як
    прогалина перекладу, а як помилка в продукті.
    """
    # Португальська — приклад мови без каталогу. Колись тут стояла
    # французька, але шість мов запуску тепер повні, і неповну довелося
    # шукати далі за ними.
    text = i18n.render("seo.h1.missing", locale=Locale.PT)
    assert text.title == i18n.render("seo.h1.missing", locale=Locale.EN).title
    assert text.title != i18n.render("seo.h1.missing", locale=Locale.UK).title
    assert text.locale is Locale.EN
    assert text.fell_back is True, "факт фолбеку видно програмно"


def test_a_translation_that_exists_does_not_report_a_fallback():
    text = i18n.render("seo.h1.missing", locale=Locale.UK)
    assert text.locale is Locale.UK
    assert text.fell_back is False


def test_unknown_key_degrades_to_key_name_instead_of_raising():
    assert i18n.render("does.not.exist").title == "does.not.exist"


@pytest.mark.parametrize("locale", list(CATALOGS))
def test_placeholders_match_across_locales(locale: Locale):
    """Один ключ — однакові плейсхолдери в усіх мовах, інакше params не підійдуть."""
    for key in all_message_keys():
        base = _placeholders(CATALOGS[DEFAULT_LOCALE][key])
        assert _placeholders(CATALOGS[locale][key]) == base, f"{locale.value}/{key}"


# Твердження про поведінку асистента, яких ми не вимірюємо. Пункт AN ТЗ:
# «this change will make ChatGPT cite you» — саме така обіцянка.
UNMEASURED_CLAIMS = (
    # Заперечення + дієслово згадування, у будь-якому порядку слів.
    # Переліком точних фраз це не ловилось: «вас не називають» проходило,
    # хоча «не називають вас» у переліку було.
    r"не\s+(?:\w+\s+){0,2}?(?:згад|назив|назв|порекоменд|рекоменд|радять|цитуют)",
    r"(?:вас|тебе)\s+не\s+(?:\w+\s+){0,2}?"
    r"(?:згад|назив|назв|порекоменд|рекоменд|радять|пропон|цитуют)",
    r"не\s+(?:\w+\s+){0,2}?(?:упомин|назыв|порекоменд|рекоменд|советуют|цитируют)",
    r"(?:вас|тебя)\s+не\s+(?:\w+\s+){0,2}?"
    r"(?:упомин|назыв|порекоменд|рекоменд|советуют|предлагают|цитируют)",
    r"процитують\s+ваш",
    r"(?:will|do(?:es)?\s+not|won'?t|never)\s+(?:\w+\s+){0,2}?"
    r"(?:mention|cite|recommend|suggest|name)\s+you",
    r"nobody\s+suggests\s+you",
    r"do not connect the site to your company",
)

# Слова, якими висновок відрізняється від факту. Наявність будь-якого
# перетворює обіцянку на оцінку ймовірності — і робить її чесною.
HEDGES = (
    "рідше", "менш", "ймовірн", "може", "можуть", "шанс", "навряд",
    "less likely", "lowers the chance", "may ", "can ", "unlikely", "chance",
)


def test_consequence_does_not_promise_what_we_never_measured():
    """Ми не питаємо ChatGPT про клієнта й не знаємо, кого він називає.

    Категоричним може бути факт: robots.txt із забороною GPTBot ми
    прочитали на власні очі. Висновок про поведінку асистента — ні.
    """
    offenders = [
        f"{locale.value}/{key}: {claim}"
        for locale, catalog in CATALOGS.items()
        for key, entry in catalog.items()
        for claim in UNMEASURED_CLAIMS
        if _categorical(entry.get("consequence", ""), claim)
    ]
    assert not offenders, f"обіцянка без доказу: {offenders}"


def _categorical(text: str, claim: str) -> bool:
    """Чи стверджується `claim` категорично.

    Пом'якшення мусить стояти БІЛЯ твердження, а не будь-де в тексті.
    Раніше воно шукалось будь-де, і `tech.crawler_blocked` проходив
    перевірку: «ChatGPT і подібні сервіси не **можуть** прочитати ваш
    сайт і **не згадують вас у відповідях**». Одне речення, дві різні
    заяви: «можуть» пом'якшувало першу, а виправдовувало другу.

    Різниця між ними не стилістична. Про першу ми хоч щось бачили —
    власний запит і його код відповіді. Про другу не бачили нічого:
    ChatGPT ми не питаємо й питати не збираємось.

    Вікно вузьке навмисно: пом'якшена форма використовує ІНШЕ дієслово
    («можуть не згадувати»), тож поруч із категоричним «не згадують»
    пом'якшення просто не буває.
    """
    import re as _re

    window = 15
    for m in _re.finditer(claim, text, _re.I):
        before = text[max(0, m.start() - window) : m.start()]
        if not any(hedge in before for hedge in HEDGES):
            return True
    return False


def test_the_module_name_does_not_promise_brand_tracking():
    """«LLM Visibility = 93» читається як «ChatGPT згадує вас у 93%».

    Ми міряємо придатність сайту до цитування, а не факт цитування, і
    назва напряму має казати саме це.
    """
    from app.report.i18n import STRINGS

    for locale, strings in STRINGS.items():
        name = strings["module_llm_visibility"].lower()
        assert "visibility" not in name and "видимість" not in name, locale
        owner = strings["owner_area_llm_visibility"].lower()
        assert "радить" not in owner and "recommends" not in owner, locale


# ── контракт issue_key ─────────────────────────────────────────────────────


def test_every_finding_of_a_multi_problem_check_names_its_problem():
    """Чек, що розрізняє кілька проблем, мусить казати, яку саме знайшов.

    Це головна страховка від того, щоб забути `key` в одному з місць
    виклику: забуте місце злило б проблему з сусідньою під одну стелю
    штрафу — рівно той дефект, заради якого поділ і робився.
    """
    by_code = {c.code: c for c in all_checks()}
    for issue in _all_issues():
        check = by_code[issue.code]
        if not check.variants:
            continue
        assert issue.key, f"{issue.code}: знахідка без key ({issue.msg})"
        assert issue.key in check.variants, f"{issue.code}: невідомий key {issue.key!r}"


def test_declared_variants_are_all_reachable():
    """Оголошений, але недосяжний варіант — мертвий ідентифікатор.

    Він нічого не ламає одразу, але бере участь у detector_version і
    створює враження поділу, якого насправді немає.
    """
    seen = {(i.code, i.key) for i in _all_issues() if i.key}
    for check in all_checks():
        for variant in check.variants:
            assert (check.code, variant) in seen, f"{check.code}:{variant} не досягається фікстурами"


def test_a_check_that_knows_one_problem_keys_on_its_code():
    for issue in _all_issues():
        if not issue.key:
            assert issue.issue_key == issue.code


# ── однорядкові повідомлення домену ────────────────────────────────────────


def all_notice_keys() -> set[str]:
    """Ключі, які справді вживає код, а не просто лежать у каталозі."""
    import re

    keys: set[str] = set()
    for path in ("app/audit/orchestrator.py", "app/application/retries.py",
                 "app/worker/tasks.py"):
        keys |= set(re.findall(r'"(notice\.[a-z_.]+)"', pathlib.Path(path).read_text("utf-8")))
    return keys


@pytest.mark.parametrize("locale", sorted(i18n.COMPLETE_LOCALES))
def test_every_notice_used_by_the_code_is_translated(locale: Locale):
    missing = i18n.missing_notices(all_notice_keys())[locale]
    assert not missing, f"немає повідомлення {locale.value}: {sorted(missing)}"


def test_notices_have_the_same_placeholders_in_every_language():
    """Інакше params, зібрані в двигуні, не підійдуть до перекладу."""
    for key, english in i18n.NOTICES[Locale.EN].items():
        base = set(PLACEHOLDER.findall(english))
        assert set(PLACEHOLDER.findall(i18n.NOTICES[Locale.UK][key])) == base, key


def test_a_notice_in_a_partial_language_falls_back_to_english():
    text = i18n.notice("notice.module.excluded", locale=Locale.JA)
    assert text == i18n.notice("notice.module.excluded", locale=Locale.EN)


def test_an_unknown_notice_key_degrades_to_the_key_itself():
    """Звіт має вижити: краще показати ключ, ніж 500."""
    assert i18n.notice("notice.does.not.exist") == "notice.does.not.exist"


# ── G6 / E-07: збережений звіт мусить рендеритись після вилучення чека ──
#
# Рішення власника OD-01 лишає рядки `ai.schema.faq` в каталозі саме
# заради аудитів, порахованих ДО вилучення: такий звіт відкриють завтра,
# і відкриють тією мовою, якою його замовили. Нові аудити цього ключа не
# віддають — чека в реєстрі немає, — тож жоден тест активного каталогу
# сюди не дивиться. Звідси окрема перевірка.

G6_RETAINED = "ai.schema.faq"

# Шість мов запуску — ті, від каталогів яких вимагається повнота.
LAUNCH_LOCALES = sorted(i18n.COMPLETE_LOCALES, key=lambda loc: loc.value)


def _locales_missing(key: str, catalogs) -> set[str]:
    """Мови запуску, у чиєму каталозі ключа немає або він порожній.

    Функція бере каталоги аргументом, а не читає глобальні: інакше
    перевірити її саму можна було б лише правкою продукційного файлу.
    Той самий предикат обслуговує і справжній каталог, і навмисно
    зіпсовану копію нижче — позитивний і негативний контроль.
    """
    missing = set()
    for locale in i18n.COMPLETE_LOCALES:
        entry = catalogs.get(locale, {}).get(key)
        if not entry or not entry.get("title"):
            missing.add(locale.value)
    return missing


def test_g6_the_retained_key_is_present_in_every_launch_locale():
    """Позитивний контроль: справжній каталог паритет тримає."""
    assert len(LAUNCH_LOCALES) == 6
    assert _locales_missing(G6_RETAINED, CATALOGS) == set()


def test_g6_dropping_one_locale_breaks_retained_key_parity():
    """Негативний контроль: якби мову загубили, предикат мусить це сказати.

    Без цього тесту попередній довів би лише те, що сьогодні все на
    місці, і мовчав би про те, чи вміє він взагалі впіймати втрату.
    Каталог не змінюється: псується КОПІЯ.
    """
    for victim in LAUNCH_LOCALES:
        damaged = {loc: dict(cat) for loc, cat in CATALOGS.items()}
        damaged[victim].pop(G6_RETAINED)
        assert _locales_missing(G6_RETAINED, damaged) == {victim.value}
    # І порожній заголовок — теж втрата, не лише відсутній ключ.
    blanked = {loc: dict(cat) for loc, cat in CATALOGS.items()}
    blanked[Locale.DE][G6_RETAINED] = {**blanked[Locale.DE][G6_RETAINED], "title": ""}
    assert _locales_missing(G6_RETAINED, blanked) == {"de"}


@pytest.mark.parametrize("locale", LAUNCH_LOCALES, ids=[loc.value for loc in LAUNCH_LOCALES])
def test_g6_a_retained_key_renders_in_its_own_language(locale: Locale):
    """Ключ віддає СВОЮ мову, а не англійський фолбек."""
    text = i18n.render(G6_RETAINED, {"count": 4}, locale)
    assert text.locale is locale, "підставився фолбек там, де є переклад"
    assert text.title and text.title != G6_RETAINED
    assert "{count}" not in text.title and "4" in text.title
    assert text.description and text.recommendation


def test_g6_the_retained_translations_are_not_all_the_same_string():
    """Шість однакових рядків означали б, що переклад загублено мовчки."""
    titles = {i18n.render(G6_RETAINED, {"count": 4}, loc).title for loc in LAUNCH_LOCALES}
    assert len(titles) == 6


@pytest.mark.parametrize("locale", LAUNCH_LOCALES, ids=[loc.value for loc in LAUNCH_LOCALES])
def test_g6_a_historical_report_renders_in_every_launch_locale(locale: Locale):
    """Аудит, збережений ДО вилучення, проходить увесь шар звіту.

    Знахідка будується так, як її прочитали б з бази: `code`, `msg`,
    `params`, серйозність і вага — збережені значення, а текст шар звіту
    рендерить наново потрібною мовою. Саме заради цього шляху рядки й
    лишились у каталозі.
    """
    import uuid
    from datetime import UTC, datetime

    from app.audit.enums import AuditStatus, Module, Severity
    from app.audit.types import Issue
    from app.report.builder import build_report
    from app.report.types import ReportSource
    from app.report.web import to_web

    stored = Issue(
        code=G6_RETAINED,
        module=Module.AI_READY,
        severity=Severity.LOW,
        title="(збережений заголовок мовою аудиту)",
        evidence={"questions": 4, "path": "/faq"},
        weight=2,
        page_url="https://example.com/faq",
        msg=G6_RETAINED,
        params={"count": 4},
    )
    source = ReportSource(
        url="https://example.com",
        entry_url="https://example.com/",
        origin="https://example.com",
        overall=61,
        scores={m.value: 61 for m in Module},
        issues=[stored],
        degraded=[],
        skipped_modules=set(),
        evidence={},
        pages_crawled=9,
        status=AuditStatus.COMPLETED,
    )

    document = build_report(source, locale)

    rendered = document.issues[0]
    assert rendered.code == G6_RETAINED, "збережений ідентифікатор лишився читаним"
    assert rendered.severity == Severity.LOW.value
    assert rendered.title and rendered.title != G6_RETAINED, "сирий ключ у звіті"
    assert rendered.title == i18n.render(G6_RETAINED, {"count": 4}, locale).title
    assert rendered.evidence["questions"] == 4, "збережений доказ лишився"
    assert document.recommendations, "вилучений чек не позбавляє старий звіт поради"

    response = to_web(
        document,
        audit_id=uuid.UUID(int=7),
        site_id=None,
        status="completed",
        finished_at=datetime(2026, 9, 1, tzinfo=UTC),
        fallback_locale=locale.value,
    )
    payload = response.model_dump_json()
    assert G6_RETAINED in payload, "код знахідки зник із публічного контракту"
    assert f'"{G6_RETAINED}"' in payload
    assert rendered.title in payload, "сирий ключ замість тексту в контракті"


def test_g6_the_same_historical_finding_reads_differently_in_two_locales():
    """Один збережений рядок — шість документів, а не шість копій англійської."""
    from app.audit.enums import AuditStatus, Module, Severity
    from app.audit.types import Issue
    from app.report.builder import build_report
    from app.report.types import ReportSource

    def document(locale: Locale):
        stored = Issue(
            code=G6_RETAINED, module=Module.AI_READY, severity=Severity.LOW,
            title="t", evidence={}, weight=2, msg=G6_RETAINED, params={"count": 4},
        )
        return build_report(ReportSource(
            url="https://example.com", entry_url="https://example.com/",
            origin="https://example.com", overall=61,
            scores={m.value: 61 for m in Module}, issues=[stored], degraded=[],
            skipped_modules=set(), evidence={}, pages_crawled=9,
            status=AuditStatus.COMPLETED,
        ), locale)

    titles = {loc: document(loc).issues[0].title for loc in LAUNCH_LOCALES}
    assert len(set(titles.values())) == 6, f"мови злилися: {titles}"


# ── E1-01: наслідок для відсутньої карти сайту ────────────────────────────────
#
# Текст казав, що пошук знаходить сторінки лише за посиланнями, «тож нові й
# глибокі сторінки потрапляють у видачу із затримкою». Чек цього не бачить:
# `collect_sitemap` перевіряє стандартні адреси й ту, яку назвав сам сайт, і
# все, що він спостерігає, — відсутність файла. Поведінка пошукової системи й
# строки потрапляння у видачу — не наш вимір, і казати про них у звіті означало
# б продавати здогад.
#
# Затверджені власником рядки закріплені тут дослівно. Вони навмисно не
# називають ані файла robots.txt, ані конкретних адрес: `consequence` — це
# нетехнічна частина звіту, і сторож жаргону вище пропускає назву файла лише
# на ключах того чека, який САМЕ про цей файл. Заміна одного рядка рядком
# іншої мови теж падає тут, бо порівняння дослівне.
#
# Той самий текст доходить до читача ДВОМА проєкціями: `Recommendation
# .consequence` у повному звіті й перше речення того ж рядка як `problem`
# короткого звіту (`short.py`). Обидві закріплені нижче — інакше правка
# каталогу могла б зупинитися на півдорозі й лишити гостьовий екран зі старим
# текстом, а це рівно той випадок, коли розходження помічає клієнт, а не тест.

E1_01_KEY = "seo.sitemap.missing"

E1_01_CONSEQUENCE = {
    "uk": (
        "Карту сайту не знайдено: за стандартними адресами її немає, а іншу адресу сайт не "
        "вказав."
    ),
    "en": (
        "No sitemap was found: it is absent from the standard locations, and the site did not "
        "specify another address."
    ),
    "de": (
        "Keine Sitemap gefunden: An den Standardadressen ist keine vorhanden, und die Website "
        "hat keine andere Adresse angegeben."
    ),
    "es": (
        "No se encontró ningún mapa del sitio: no está en las ubicaciones estándar y el sitio "
        "no indicó otra dirección."
    ),
    "fr": (
        "Aucun plan du site trouvé : il est absent des emplacements standard et le site n’a "
        "indiqué aucune autre adresse."
    ),
    "ru": (
        "Карта сайта не найдена: по стандартным адресам её нет, а другой адрес сайт не указал."
    ),
}


def _sitemap_source():
    """Знахідка про відсутню карту так, як її прочитали б з бази."""
    from app.audit.enums import AuditStatus, Module, Severity
    from app.audit.types import Issue
    from app.report.types import ReportSource

    stored = Issue(
        code="seo.sitemap",
        module=Module.SEO,
        severity=Severity.MEDIUM,
        title="(збережений заголовок мовою аудиту)",
        evidence={"declared_in_robots": False},
        weight=3,
        page_url="https://example.com/",
        msg=E1_01_KEY,
        params={},
    )
    return ReportSource(
        url="https://example.com", entry_url="https://example.com/",
        origin="https://example.com", overall=61,
        scores={m.value: 61 for m in Module}, issues=[stored], degraded=[],
        skipped_modules=set(), evidence={}, pages_crawled=9,
        status=AuditStatus.COMPLETED,
    )


@pytest.mark.parametrize("locale", LAUNCH_LOCALES, ids=[loc.value for loc in LAUNCH_LOCALES])
def test_e1_01_missing_sitemap_consequence_states_only_what_was_observed(locale: Locale):
    """Наслідок описує відсутність карти, а не поведінку пошуку — в обох проєкціях."""
    from app.report.builder import build_report
    from app.report.short import to_short

    approved = E1_01_CONSEQUENCE[locale.value]

    text = CATALOGS[locale][E1_01_KEY]["consequence"]
    assert text == approved, (
        f"{locale.value}/{E1_01_KEY}: наслідок розійшовся із затвердженим текстом"
    )
    for term in ("robots.txt", "sitemap.xml", "sitemap_index", "/sitemap"):
        assert term not in text, f"{locale.value}: у нетехнічному тексті назва «{term}»"
    assert len(set(E1_01_CONSEQUENCE.values())) == 6, "шість мов не можуть мати спільний рядок"

    document = build_report(_sitemap_source(), locale)
    rec = next(r for r in document.recommendations if r.msg == E1_01_KEY)
    assert rec.consequence == approved, "повний звіт віддає інший наслідок"

    # Друга проєкція: короткий звіт бере перше речення того самого рядка.
    # Затверджений текст — одне речення, тож `problem` дорівнює йому цілком.
    brief = to_short(document, audit_id="00000000-0000-0000-0000-000000000007")
    problems = [p for p in brief.problems if p.problem]
    assert problems, "коротким звітом проблема не дійшла до читача"
    assert problems[0].problem == approved, "короткий звіт лишився зі старим текстом"
