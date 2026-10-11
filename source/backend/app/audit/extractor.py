"""Детерміністичне витягування сигналів зі статичного HTML."""

from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

from selectolax.parser import HTMLParser

from app.audit import form_protection
from app.audit.fetcher import FetchResult
from app.audit.site_scope import SiteScope
from app.audit.standards import analytics_vendors
from app.audit.types import (
    FormSignals,
    HreflangRef,
    InsecureRef,
    LinkRef,
    PageSignals,
)

_WS = re.compile(r"\s+")
_NON_CONTENT_TAGS = ("script", "style", "noscript", "template", "svg")
_IMG_EXT = re.compile(r"\.(avif|webp|png|jpe?g|gif|svg|bmp|ico)(\?|$)", re.I)

# Хости, що роздають шрифти: їх наявність = зовнішня залежність критичного шляху.
_FONT_HOSTS = ("fonts.googleapis.com", "fonts.gstatic.com", "use.typekit.net", "fast.fonts.net")

# Аналітика й теги: самі правила живуть у `standards/analytics_vendors`,
# бо це дані, що старіють швидше за код, і їх треба звіряти з хостом.
#
# Перелік свідомо ширший за Google: на вибірці з 50 сайтів «аналітики немає»
# спрацьовувало на 85%, і майже завжди хибно — Stripe і Replicate міряють
# Heap'ом, Linear і Scale — Segment'ом, Hugging Face — самостійно піднятим
# Plausible. Вузький список перетворював чек на генератор неправди.
#
# Підрядок помилявся й у другий бік, і дорожче. `/v1/p` будь-де в адресі
# зараховував наш власний `/v1/plans` за Segment, а заразом `/youtubei/v1/
# player` і Wix `/v1/tags`; токен `analytics` робив «власним лічильником»
# чужий `sandbox-checkout-analytics.paddle.com` і маршрут `/admin/analytics`
# (E-11a, E-11b, E-11c). Тепер кожне спостереження має вид, правило й канал.


def vendors_in_urls(urls: Iterable[str]) -> set[str]:
    """Вендори, доведені самою адресою запиту: хост вендора або його файл.

    Найнадійніше з трьох джерел: адресу скрипта можна проксувати,
    глобального обʼєкта може не бути зовсім (SDK через import живе в
    модулі бандла), але подію лічильник мусить кудись відправити.

    Тут вирішується лише те, чому не потрібне походження сайту. Проксі на
    власному домені й загальні ознаки вимірювання класифікує сайтовий
    рівень, де є і походження, і співсигнали.
    """
    found: set[str] = set()
    for url in urls:
        match = analytics_vendors.vendor_by_host(url) or analytics_vendors.vendor_by_loader(
            url, own_origin=False
        )
        if match is not None:
            found.add(match[0].name)
    return found


# Мета-теги верифікації власності сайту.
_VERIFICATION_META = {
    "google-site-verification": "google_search_console",
    "msvalidate.01": "bing_webmaster",
    "yandex-verification": "yandex_webmaster",
    "facebook-domain-verification": "facebook",
}

# Сумісність: перелік провайдерів і назв приманок живе тепер у
# `form_protection`, разом із правилом, ЯК їх шукати. Ці імена лишились
# для чужого коду, який їх імпортує; нового вжитку в них немає.
CAPTCHA_MARKERS = tuple(form_protection.PROVIDER_MARKERS)
HONEYPOT_FIELD_NAMES = form_protection.HONEYPOT_NAMES


def clean(text: str | None) -> str:
    return _WS.sub(" ", text or "").strip()



# Заголовок `Link` за RFC 8288: <url>; rel="alternate"; hreflang="de".
# Google окремо радить цей спосіб для файлів, які не є HTML, — насамперед
# PDF, де іншого місця для анотації просто немає.
_LINK_HEADER = re.compile(r"<([^>]+)>\s*;\s*([^,]*)")
_LINK_PARAM = re.compile(r'(\w+)\s*=\s*"?([^";]+)"?')


def _hreflang_from_header(value: str) -> list[HreflangRef]:
    refs = []
    for href, params in _LINK_HEADER.findall(value or ""):
        found = {k.lower(): v.strip() for k, v in _LINK_PARAM.findall(params)}
        if found.get("rel", "").lower() != "alternate":
            continue
        code = found.get("hreflang")
        if code and href.strip():
            refs.append(HreflangRef(value=code, href=href.strip(), source="http_header"))
    return refs


def extract(result: FetchResult, origin: str, depth: int = 0) -> PageSignals:
    signals = PageSignals(
        url=result.final_url,
        depth=depth,
        status_code=result.status_code,
        content_type=result.content_type,
        html_bytes=result.body_bytes,
        response_ms=result.elapsed_ms,
        redirected_from=result.url if result.url != result.final_url else None,
        redirect_chain=tuple((h.status_code, h.url) for h in result.redirects),
        headers={k.lower(): v for k, v in result.headers.items()},
        http_version=result.http_version,
        accept_encoding=result.accept_encoding,
    )
    # Заголовок читається до перевірки на HTML навмисно: Google радить
    # цей спосіб саме для файлів, які HTML не є, і PDF без нього не має
    # де оголосити свої мовні версії взагалі.
    signals.hreflang.extend(_hreflang_from_header(signals.header("link") or ""))

    if not result.is_html or not result.text:
        return signals

    tree = HTMLParser(result.text)
    # Порядок важливий: _extract_text деструктивний (decompose script/style),
    # тому він іде останнім. Усе, що читає <script>, має бути до нього.
    _extract_head(tree, signals)
    _extract_headings(tree, signals)
    _extract_links(tree, signals, base=result.final_url, origin=origin)
    _extract_images(tree, signals, base=result.final_url)
    _extract_structured_data(tree, signals)
    _extract_perf_hints(tree, signals)
    _extract_third_party(tree, signals, base=result.final_url, origin=origin)
    _extract_insecure(tree, signals, base=result.final_url)
    _extract_forms(tree, signals)
    _extract_buttons(tree, signals)
    _extract_breadcrumb_ui(tree, signals)
    _extract_text(tree, signals)
    return signals


def signals_from_html(url: str, html: str, origin: str, depth: int = 0) -> PageSignals:
    """PageSignals із готового HTML — для сторінки після рендеру.

    Відрендерений HTML розбираємо тим самим кодом, що й статичний:
    інакше різниця між ними частково пояснювалася б різницею парсерів,
    а не сайтом. Синтетичний FetchResult тут — плата за те, щоб
    `extract` лишився однією точкою входу.
    """
    result = FetchResult(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        text=html,
        body_bytes=len(html.encode("utf-8", errors="replace")),
        elapsed_ms=0,
        headers={},
    )
    return extract(result, origin=origin, depth=depth)


def _extract_head(tree: HTMLParser, s: PageSignals) -> None:
    if (node := tree.css_first("title")) is not None:
        s.title = clean(node.text())
    if (html := tree.css_first("html")) is not None:
        s.lang = clean(html.attributes.get("lang"))
    for meta in tree.css("meta"):
        attrs = meta.attributes
        name = (attrs.get("name") or "").lower()
        prop = (attrs.get("property") or "").lower()
        content = clean(attrs.get("content"))
        if "charset" in attrs:
            s.charset = attrs.get("charset")
        if name == "description":
            s.meta_description = content
        elif name == "robots":
            s.meta_robots = content.lower()
        elif (attrs.get("http-equiv") or "").lower() == "refresh":
            s.meta_refresh = content
        elif name == "viewport":
            s.viewport = content
        elif prop.startswith("og:"):
            s.opengraph[prop] = content
        elif name.startswith("twitter:"):
            s.twitter_card[name] = content
    if (link := tree.css_first('link[rel="canonical"]')) is not None:
        s.canonical = clean(link.attributes.get("href"))

    for node in tree.css('link[rel="alternate"][hreflang]'):
        code = clean(node.attributes.get("hreflang"))
        href = clean(node.attributes.get("href"))
        if code and href:
            s.hreflang.append(HreflangRef(value=code, href=href, source="html"))


_HEADING_TAGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


def _extract_headings(tree: HTMLParser, s: PageSignals) -> None:
    """Заголовки в порядку документа, одним обходом дерева.

    Обхід, а не `css("h1,h2,h3,h4,h5,h6")`: selectolax віддає збіги за
    СЕЛЕКТОРАМИ, тобто спершу всі `h1`, потім усі `h2` — той самий групований
    порядок, що й старий цикл по рівнях, лише коротшим записом. Перевірено на
    цій версії й закріплено тестом: селектор із комою тут не рятує.
    """
    root = tree.root
    if root is None:
        # Розібрати не вдалося взагалі: заголовків немає, і порядку ми не
        # бачили. Прапорець лишається `False` — це те саме «не дивилися», що й
        # у старого знімка, і воно чесніше за `True` над порожнечею.
        return
    for node in root.traverse(include_text=False):
        level = _HEADING_TAGS.get(node.tag)
        if level is None:
            continue
        text = clean(node.text())
        if not text:
            continue
        s.headings.append((level, text))
        if level == 1:
            s.h1.append(text)
    # Ставиться тут і тільки тут: провенанс належить тому, хто справді обійшов
    # документ. Сторінка без заголовків теж має право на `True` — твердження
    # про обхід, а не про вміст.
    s.headings_in_document_order = True


def _extract_text(tree: HTMLParser, s: PageSignals) -> None:
    for tag in _NON_CONTENT_TAGS:
        for node in tree.css(tag):
            node.decompose()
    body = tree.css_first("main") or tree.css_first("body")
    s.text = clean(body.text(separator=" ")) if body else ""
    s.word_count = len(s.text.split())


def _extract_links(tree: HTMLParser, s: PageSignals, *, base: str, origin: str) -> None:
    # Межа сайту — спільне правило, не порівняння рядків. Раніше тут
    # стояло `parsed.netloc == origin_host`, і `www.kernel.org` для
    # `kernel.org` ставав чужим сайтом.
    scope = SiteScope.from_url(origin)
    chrome = _chrome_links(tree)
    seen: set[str] = set()
    for node in tree.css("a[href]"):
        href = (node.attributes.get("href") or "").strip()
        if href.startswith("mailto:"):
            s.mailto_addresses.append(href[7:].split("?")[0])
            if node not in chrome:
                s.body_contacts += 1
            continue
        if href.startswith("tel:"):
            s.tel_links.append(href[4:])
            if node not in chrome:
                s.body_contacts += 1
            continue
        if not href or href.startswith(("#", "javascript:", "data:")):
            continue
        absolute, _ = urldefrag(urljoin(base, href))
        if absolute in seen:
            continue
        seen.add(absolute)
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        s.links.append(
            LinkRef(
                url=absolute,
                anchor=clean(node.text())[:200],
                rel=(node.attributes.get("rel") or "").lower(),
                is_internal=scope.contains(absolute),
                in_chrome=node in chrome,
                image_alt=_image_alt(node),
                label=clean(
                    node.attributes.get("aria-label") or node.attributes.get("title") or ""
                )[:200],
            )
        )


def _image_alt(node: Any) -> str:
    """`alt` першої картинки всередині посилання, якщо вона там є.

    Порожній `alt` — валідний для декоративної картинки, і саме тому він
    тут не відрізняється від відсутнього: обидва означають «текстом
    посилання це не є».
    """
    for image in node.css("img[alt]"):
        if alt := clean(image.attributes.get("alt") or ""):
            return alt[:200]
    return ""


# Підресурси, які браузер піде вантажити сам. Навігація (`<a href>`)
# сюди не входить навмисно: перехід на http-сторінку — це не змішаний
# вміст, а звичайне посилання, і плутати їх означало б лаяти сайт за те,
# чого не сталося.
_SUBRESOURCE_ATTRS = (
    ("script[src]", "src", "script"),
    ("iframe[src]", "src", "iframe"),
    ("embed[src]", "src", "embed"),
    ("object[data]", "data", "object"),
    ("img[src]", "src", "img"),
    ("audio[src]", "src", "audio"),
    ("video[src]", "src", "video"),
    ("video[poster]", "poster", "video"),
    ("source[src]", "src", "source"),
    ("track[src]", "src", "track"),
)

# `rel`, за яких браузер справді піде по адресу.
_FETCHING_RELS = ("stylesheet", "preload", "icon", "shortcut icon", "apple-touch-icon")


def _extract_insecure(tree: HTMLParser, s: PageSignals, *, base: str) -> None:
    """Підресурси, запитані по http, коли сама сторінка на https.

    На http-сторінці не збираємо нічого: змішаний вміст існує лише в
    захищеному контексті, а про незахищений документ уже є свій чек.
    """
    if not base.lower().startswith("https://"):
        return

    def note(raw: str, kind: str, *, in_srcset: bool = False) -> None:
        value = (raw or "").strip()
        if not value:
            return
        absolute = urljoin(base, value)
        if absolute.lower().startswith("http://"):
            s.insecure_refs.append(
                InsecureRef(url=absolute[:300], kind=kind, in_srcset=in_srcset)
            )

    for selector, attribute, kind in _SUBRESOURCE_ATTRS:
        for node in tree.css(selector):
            note(node.attributes.get(attribute) or "", kind)

    for node in tree.css("link[href]"):
        rel = (node.attributes.get("rel") or "").lower().strip()
        if rel in _FETCHING_RELS:
            # `rel`, а не «link»: таблиця стилів і фавікон — різні
            # призначення запиту, і браузер поводиться з ними по-різному.
            note(node.attributes.get("href") or "", rel.replace("shortcut ", ""))

    # `srcset` — набір кандидатів: «url 2x, url 800w». Беремо кожен.
    for selector in ("img[srcset]", "source[srcset]"):
        for node in tree.css(selector):
            for candidate in (node.attributes.get("srcset") or "").split(","):
                note(candidate.strip().split(" ")[0], selector.split("[")[0],
                     in_srcset=True)

    # Завантаження з захищеної сторінки по http браузери блокують окремо.
    for node in tree.css("a[download][href]"):
        note(node.attributes.get("href") or "", "download")


def _extract_buttons(tree: HTMLParser, s: PageSignals) -> None:
    """Написи на кнопках у тілі сторінки, поза меню й підвалом."""
    chrome = {
        node
        for area in ("nav", "footer")
        for selector in ("button", "input[type=submit]", "[role=button]")
        for node in tree.css(f"{area} {selector}")
    }
    for selector in ("button", "input[type=submit]", "[role=button]"):
        for node in tree.css(selector):
            if node in chrome:
                continue
            label = clean(node.text() or node.attributes.get("value") or "")
            if label:
                s.body_buttons.append(label[:120])


#: Значення атрибутів, якими розмітка називає видимий слід «хлібних крихт».
#: Атрибути, а НЕ текст: абзац зі словом «breadcrumb» — це стаття про
#: навігацію, а не навігація. Той самий клас помилки, що колись зараховував
#: речення «ми використовуємо reCAPTCHA» за встановлений захист форми.
BREADCRUMB_MARKERS = ("breadcrumb", "breadcrumbs", "brotkrumen", "fil-ariane")


def _extract_breadcrumb_ui(tree: HTMLParser, s: PageSignals) -> None:
    """Чи є на сторінці НАМАЛЬОВАНИЙ слід навігації.

    Факт зберігається, бо він справжній і корисний: видимий слід, що веде
    на батьківську сторінку, — одна з трьох зʼєднувальних згадок E-15.
    Заміною структурованих даних він не є й бути не може: `BreadcrumbList`
    читає машина, а намальований слід — людина.

    Шукається за роллю й за іменами класів, і лише в АТРИБУТАХ.
    """
    for node in tree.css('nav[aria-label], [role="navigation"][aria-label]'):
        label = (node.attributes.get("aria-label") or "").strip().lower()
        if any(marker in label for marker in BREADCRUMB_MARKERS):
            s.breadcrumb_ui = True
            return
    for node in tree.css("nav, ol, ul, div"):
        attrs = node.attributes
        haystack = " ".join(
            (attrs.get(name) or "") for name in ("class", "id", "itemtype", "typeof")
        ).lower()
        if any(marker in haystack for marker in BREADCRUMB_MARKERS):
            s.breadcrumb_ui = True
            return


def _chrome_links(tree: HTMLParser) -> set[Any]:
    """Посилання зі спільної обвʼязки сайту: `<nav>` і `<footer>`.

    `<header>` навмисно лишається тілом сторінки: там часто стоїть
    головна кнопка дії, і зарахувати її до меню означало б викинути
    єдиний справжній заклик.
    """
    return {node for area in ("nav", "footer") for node in tree.css(f"{area} a[href]")}


def _extract_images(tree: HTMLParser, s: PageSignals, *, base: str) -> None:
    for node in tree.css("img"):
        attrs = node.attributes
        s.images_total += 1
        if "alt" not in attrs:  # alt="" — валідний варіант для декоративних зображень
            s.images_without_alt += 1
        if not (attrs.get("width") and attrs.get("height")):
            s.images_without_dimensions += 1
        if (attrs.get("loading") or "").lower() == "lazy":
            s.lazy_images += 1
        if attrs.get("srcset") or attrs.get("data-srcset"):
            s.images_with_srcset += 1
        src = attrs.get("src") or attrs.get("data-src") or ""
        if match := _IMG_EXT.search(urljoin(base, src)):
            fmt = match.group(1).lower().replace("jpeg", "jpg")
            s.images_by_format[fmt] = s.images_by_format.get(fmt, 0) + 1


def _extract_structured_data(tree: HTMLParser, s: PageSignals) -> None:
    for node in tree.css('script[type="application/ld+json"]'):
        raw = node.text() or ""
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            s.jsonld_errors.append(f"line {exc.lineno}: {exc.msg}")
            continue
        for item in _flatten_jsonld(parsed):
            s.jsonld.append(item)
    s.microdata_types = sorted(
        {
            (node.attributes.get("itemtype") or "").rsplit("/", 1)[-1]
            for node in tree.css("[itemtype]")
            if node.attributes.get("itemtype")
        }
    )


def _flatten_jsonld(node: object) -> list[dict[str, Any]]:
    """@graph розгортаємо, щоб чеки бачили плаский список сутностей."""
    if isinstance(node, list):
        return [item for child in node for item in _flatten_jsonld(child)]
    if isinstance(node, dict):
        if "@graph" in node:
            return _flatten_jsonld(node["@graph"])
        return [node]
    return []


def _extract_third_party(tree: HTMLParser, s: PageSignals, *, base: str, origin: str) -> None:
    """Зовнішні хости, аналітика й шрифти. Читає <script>, тому до _extract_text."""
    own_host = urlparse(origin).netloc.lower()
    hosts: set[str] = set()
    fonts: set[str] = set()
    sources: list[str] = []

    def note_host(raw: str) -> str:
        absolute = urljoin(base, raw)
        host = urlparse(absolute).netloc.lower()
        if host and host != own_host:
            hosts.add(host)
        if host in _FONT_HOSTS:
            fonts.add(host)
        return absolute

    for node in tree.css("script[src]"):
        sources.append(note_host(node.attributes.get("src") or ""))

    for node in tree.css("link[href]"):
        rel = (node.attributes.get("rel") or "").lower()
        href = node.attributes.get("href") or ""
        if rel in ("stylesheet", "preconnect", "dns-prefetch", "preload"):
            sources.append(note_host(href))
        if rel == "preload":
            s.preloads.append((node.attributes.get("as") or "").lower() or "unknown")

    for node in tree.css("iframe[src]"):
        sources.append(note_host(node.attributes.get("src") or ""))

    # Inline-код теж рахуємо: gtag() і clarity() часто вставляють без src.
    # Разом із ним — адреси скриптів, іфреймів і link-підказок: Stripe і
    # Linear ініціалізують лічильники всередині __NEXT_DATA__ і
    # preconnect'ів, а не тегом скрипта.
    #
    # Видимий текст сторінки й підписи посилань у стіг сіна свідомо не
    # потрапляють: блог про SEO згадує «google-analytics.com» у статті, і
    # сканування всього HTML зарахувало б статтю за встановлений лічильник.
    # Раніше туди йшли ВСІ атрибути `src` і `href` документа, тобто й
    # `<a href>`; тепер — лише ті теги, що справді завантажують ресурс.
    observations = analytics_vendors.observe_page(
        origin=origin, sources=sources, inline=_inline_scripts(tree)
    )

    for node in tree.css("meta[name][content]"):
        name = (node.attributes.get("name") or "").lower()
        if name in _VERIFICATION_META:
            s.verifications.append(_VERIFICATION_META[name])

    s.third_party_hosts = sorted(hosts)
    s.font_hosts = sorted(fonts)
    # Поле лишається переліком ВПІЗНАНИХ вендорів — саме його читають
    # чеки й збережені знімки. Чим їх упізнано й що лишилось невпізнаним,
    # каже `analytics_observations` поруч.
    s.analytics_observations = [observation.to_json() for observation in observations]
    s.analytics = analytics_vendors.vendors_of(observations)
    s.verifications = sorted(set(s.verifications))


def _inline_scripts(tree: HTMLParser) -> str:
    """Текст скриптів без `src`: єдине місце, де шукаються inline-маркери."""
    return "\n".join(
        node.text() or "" for node in tree.css("script") if "src" not in node.attributes
    )


def _attrs(node: Any) -> dict[str, str]:
    """Атрибути вузла рядками. `None` у selectolax означає порожній атрибут."""
    return {k: (v or "") for k, v in node.attributes.items()}


def _form_identity(node: Any, index: int) -> str:
    """Безпечний селектор форми для доказу. Значень полів тут немає."""
    attributes = _attrs(node)
    if attributes.get("id"):
        return f"form#{attributes['id']}"
    if attributes.get("name"):
        return f"form[name={attributes['name']}]"
    return f"form:nth-of-type({index + 1})"


def _extract_forms(tree: HTMLParser, s: PageSignals) -> None:
    # Бібліотеки провайдерів, підключені сторінкою. Збираються окремо від
    # форм: скрипт у <head> нічого не каже про конкретну форму, але не
    # дає стверджувати, що захисту не видно (невидима reCAPTCHA v3).
    libraries: list[str] = []
    for node in tree.css("script[src]"):
        for provider, _marker in form_protection.markers_in(_attrs(node)):
            if provider not in libraries:
                libraries.append(provider)
    s.protection_libraries = libraries
    # Дивилися. Навіть якщо форм не виявилось — це різні стани.
    s.forms_scanned = True

    for index, node in enumerate(tree.css("form")):
        fields = node.css("input, textarea, select")
        visible = [
            f
            for f in fields
            if (f.attributes.get("type") or "text").lower() not in ("hidden", "submit", "button")
        ]

        # Маркери шукаються в АТРИБУТАХ вузлів форми, а не в її HTML
        # цілком: абзац «ми використовуємо reCAPTCHA» усередині форми
        # раніше зараховувався за встановлений захист.
        providers: list[str] = []
        markers: list[str] = []
        for element in [node, *node.css("*")]:
            for provider, marker in form_protection.markers_in(_attrs(element)):
                if provider not in providers:
                    providers.append(provider)
                pair = f"{provider}:{marker}"
                if pair not in markers:
                    markers.append(pair)

        honeypots: list[str] = []
        for f in fields:
            name = form_protection.is_honeypot(_attrs(f))
            if name and name not in honeypots:
                honeypots.append(name)

        s.forms.append(
            FormSignals(
                method=(node.attributes.get("method") or "get").lower(),
                method_declared=bool(node.attributes.get("method")),
                action=node.attributes.get("action") or "",
                field_count=len(visible),
                identity=_form_identity(node, index),
                protections=tuple(providers),
                honeypots=tuple(honeypots),
                protection_markers=tuple(markers),
                scanned=True,
                has_captcha=bool(providers),
                has_honeypot=bool(honeypots),
                has_email_field=any(
                    (f.attributes.get("type") or "").lower() == "email"
                    or "email" in (f.attributes.get("name") or "").lower()
                    for f in fields
                ),
                has_password_field=any(
                    (f.attributes.get("type") or "").lower() == "password" for f in fields
                ),
            )
        )


def _extract_perf_hints(tree: HTMLParser, s: PageSignals) -> None:
    head = tree.css_first("head")
    if head is None:
        return
    for node in head.css("script[src]"):
        attrs = node.attributes
        if "async" not in attrs and "defer" not in attrs:
            s.render_blocking_scripts += 1
    for node in head.css('link[rel="stylesheet"]'):
        media = (node.attributes.get("media") or "all").lower()
        if media in ("all", "screen"):
            s.render_blocking_styles += 1
    for node in tree.css("script"):
        if "src" not in node.attributes:
            s.inline_script_bytes += len(node.text() or "")
