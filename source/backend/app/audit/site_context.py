"""Збір сигналів рівня сайту: robots.txt, sitemap.xml, llms.txt, транспорт."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

from app.audit import robots as robots_rfc
from app.audit.fetcher import Fetcher
from app.audit.standards import AI_CRAWLERS
from app.audit.types import (
    HreflangRef,
    InfraInfo,
    LlmsTxtInfo,
    RobotsInfo,
    SitemapInfo,
)

# Шлях, якого свідомо не існує: перевіряємо, що сервер віддає саме 404.
_NOT_FOUND_PROBE = "seo-agent-404-probe-9f3a2c"

# Реєстр AI-краулерів переїхав у `app/audit/standards/ai_crawlers.py`:
# плаский кортеж не казав ані звідки взялося ім'я, ані навіщо цей бот
# ходить, і через це блокування пошукового краулера виглядало так само,
# як свідома відмова від навчання. Тут лишається тільки збір сигналів.


async def collect_robots(fetcher: Fetcher, origin: str) -> RobotsInfo:
    result = await fetcher.get(urljoin(origin, "/robots.txt"))
    info = RobotsInfo(status_code=result.status_code, content=result.text[:100_000])
    if not result.ok or not info.content.strip():
        return info
    # Деякі сайти віддають 200 + HTML-сторінку 404 на /robots.txt.
    if result.is_html:
        return info
    info.exists = True
    _parse_robots(info)
    return info


def _parse_robots(info: RobotsInfo) -> None:
    """Розібрати robots.txt за RFC 9309 і зняти з нього похідні факти.

    Сам розбір живе в `app/audit/robots.py` — він нічого не знає ані про
    AI, ані про наші чеки. Тут лишаються лише відповіді, потрібні звіту:
    чи закрито сайт для всіх, які карти оголошено, і кого з відомих
    AI-краулерів не пускають на корінь.

    `blocked_ai_agents` навмисно означає саме «заборонено `/`»: на цьому
    полі тримаються наявні звіти й docx. Часткові заборони — окреме
    питання, і на нього відповідає детектор, бо для цього треба знати,
    які сторінки ми справді читали.
    """
    parsed = robots_rfc.parse(info.content)
    info.parsed = parsed
    info.sitemaps = list(parsed.sitemaps)
    info.crawl_delay = parsed.crawl_delay
    info.disallows_all = not parsed.evaluate("*", "/").allowed
    info.blocked_ai_agents = [
        crawler.key
        for crawler in AI_CRAWLERS
        # Агент, про якого вендор пише, що robots.txt він ігнорує, сюди не
        # потрапляє: заборона для нього не є доказом блокування.
        if crawler.obeys_robots and not parsed.evaluate(crawler.token, "/").allowed
    ]


async def collect_sitemap(fetcher: Fetcher, origin: str, robots: RobotsInfo) -> SitemapInfo:
    candidates = [
        *robots.sitemaps,
        urljoin(origin, "/sitemap.xml"),
        urljoin(origin, "/sitemap_index.xml"),
    ]
    seen: set[str] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        result = await fetcher.get(candidate)
        if not result.ok or not result.text.strip():
            continue
        info = SitemapInfo(exists=True, status_code=result.status_code, url=candidate)
        try:
            parsed = _parse_sitemap(result.text)
        except ElementTree.ParseError as exc:
            info.parse_error = str(exc)
            return info

        info.has_lastmod = _has_lastmod(result.text)
        info.is_index = parsed.is_index
        pages: list[str] = list(parsed.pages)
        holders: dict[str, str] = {url: candidate for url in pages}
        images = dict(parsed.images)
        alternates = dict(parsed.hreflang)

        if parsed.is_index and parsed.children:
            info.children_total = len(parsed.children)
            for child_url in _spread(parsed.children, MAX_SITEMAP_CHILDREN):
                child = await fetcher.get(child_url)
                if not child.ok:
                    continue
                try:
                    child_parsed = _parse_sitemap(child.text)
                except ElementTree.ParseError as exc:
                    info.parse_error = info.parse_error or str(exc)
                    continue
                info.children_read.append(child_url)
                info.has_lastmod = info.has_lastmod or _has_lastmod(child.text)
                for url in child_parsed.pages:
                    holders.setdefault(url, child_url)
                pages.extend(child_parsed.pages)
                images.update(child_parsed.images)
                alternates.update(child_parsed.hreflang)
            info.index_complete = len(info.children_read) == info.children_total

        # Дедуплікат за записом: та сама адреса у двох дітях — одна
        # сторінка. Порядок зберігаємо: він визначає засів краулу.
        pages = list(dict.fromkeys(pages))
        info.url_count = len(pages)
        info.urls = _spread(pages, MAX_SITEMAP_URLS)
        retained = set(info.urls)
        info.sources = {url: holders.get(url, candidate) for url in info.urls}
        info.images = {url: media for url, media in images.items() if url in retained}
        # Скільки адрес карти взагалі анотовані — рахуємо до зрізу, бо
        # зріз описує наш бюджет, а не сайт.
        info.hreflang_url_count = len(alternates)
        info.hreflang = {loc: refs for loc, refs in alternates.items() if loc in retained}
        return info
    return SitemapInfo(exists=False)


# Скільки дочірніх карт індексу читаємо. Не «одну, бо так вийшло»:
# індекс на сотню файлів коштував би сотні запитів, а вибірка з пʼяти
# дає уявлення про сайт за ціну, порівнянну з рештою збору. Береться
# рівномірно по всьому індексу з тієї ж причини, що й `_spread` для
# адрес: початок індексу — це те, що генератор поклав першим.
#
# Бюджет сторінок це не рухає: скільки їх читати, вирішує `max_pages`.
MAX_SITEMAP_CHILDREN = 5


# Скільки адрес із карти лишаємо. Обмеження потрібне: карта на 8 тисяч
# рядків нікуди далі не поміщається.
MAX_SITEMAP_URLS = 5000


def _spread(urls: list[str], limit: int) -> list[str]:
    """Рівномірна вибірка по всій карті, а не її початок.

    Обрізання за позицією бере те, що сайт випадково поклав першим. На
    furniturerow.com у карті 8149 адрес і 112 сторінок магазинів,
    розкиданих від 32-ї позиції до 8131-ї, — а в перші 5000 потрапляла
    рівно одна з них, бо початок карти зайнятий тисячами однакових
    товарних адрес із GUID. Далі оркестратор брав перші 50 уже з цього
    зрізу, і сторінка міста не діставалась ні краулу, ні звіту: клієнт
    отримав пораду додати розмітку, яка в нього була.

    Перша адреса лишається першою: у картах вона зазвичай головна.
    """
    if len(urls) <= limit:
        return urls
    step = len(urls) / limit
    return [urls[int(i * step)] for i in range(limit)]


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


@dataclass(slots=True)
class ParsedSitemap:
    """Розібраний файл карти: структурно, а не пласким перебором.

    Раніше адреси збиралися через `root.iter()` по кожному тегу `loc`.
    Це ловило й `image:loc`, тобто змішувало сторінки з картинками в
    один список — і на crustula.com.ua пʼять зниклих світлин виглядали
    як пʼять зламаних сторінок. Латати це фільтром розширень означало б
    вирішувати структурне питання рядковою евристикою: розширення в
    адреси картинки може не бути взагалі, а `/report.pdf` цілком може
    бути справжнім документом сайту.

    Схема ж каже все однозначно: `<url><loc>` — це запис карти,
    `<image:image><image:loc>` — метадані ресурсу, причепленого до
    цього запису. Тому й розбираємо за схемою.
    """

    # Адреси записів карти: лише прямі `<loc>` усередині `<url>`.
    pages: list[str] = field(default_factory=list)
    # Адреси дочірніх карт із `<sitemapindex>`.
    children: list[str] = field(default_factory=list)
    is_index: bool = False
    # Медіа, причеплені до запису: адреса сторінки → адреси ресурсів.
    # Зберігаємо для майбутньої роботи з вертикальними картами; жодного
    # чека на них зараз немає й у цій задачі не заводимо.
    images: dict[str, list[str]] = field(default_factory=dict)
    hreflang: dict[str, list[HreflangRef]] = field(default_factory=dict)


# Дочірні теги, які несуть власний `loc` і сторінкою не є.
_MEDIA_CONTAINERS = frozenset({"image", "video", "news"})


def _direct_loc(entry: ElementTree.Element) -> str:
    """Прямий `<loc>` запису — не вкладений у медіаконтейнер."""
    for child in entry:
        if _local(child.tag) == "loc" and child.text:
            return child.text.strip()
    return ""


def _parse_sitemap(xml: str) -> ParsedSitemap:
    """XML карти → її записи, діти й медіа, кожне окремо."""
    root = ElementTree.fromstring(xml.encode("utf-8", errors="replace"))
    parsed = ParsedSitemap(is_index=_local(root.tag) == "sitemapindex")

    for entry in root:
        tag = _local(entry.tag)
        if parsed.is_index:
            if tag != "sitemap":
                continue
            if loc := _direct_loc(entry):
                parsed.children.append(loc)
            continue

        if tag != "url":
            continue
        own = _direct_loc(entry)
        if not own:
            continue
        parsed.pages.append(own)

        media: list[str] = []
        refs: list[HreflangRef] = []
        for child in entry:
            name = _local(child.tag)
            if name in _MEDIA_CONTAINERS:
                media.extend(
                    (node.text or "").strip()
                    for node in child
                    if _local(node.tag).endswith("loc") and node.text
                )
            elif (
                name == "link"
                and child.attrib.get("rel", "").lower() == "alternate"
                and (code := child.attrib.get("hreflang", ""))
                and (href := child.attrib.get("href", ""))
            ):
                refs.append(
                    HreflangRef(value=code.strip(), href=href.strip(), source="sitemap")
                )
        if media:
            parsed.images[own] = media
        if refs:
            parsed.hreflang[own] = refs

    return parsed


def _has_lastmod(xml: str) -> bool:
    return "<lastmod" in xml or ":lastmod" in xml


async def collect_infra(fetcher: Fetcher, origin: str) -> InfraInfo:
    """Дві проби, яких не видно з краулу: 404-сторінка й www/non-www.

    Обидві коштують один запит і дають те, що інакше помітить лише
    людина, яка вручну відкриє неіснуючу адресу.
    """
    info = InfraInfo()

    probe = urljoin(origin, f"/{_NOT_FOUND_PROBE}")
    result = await fetcher.get(probe)
    if result.error is None:
        info.not_found_checked = True
        info.not_found_status = result.status_code
        # М'який 404: сервер віддає 200 на неіснуючу адресу, і пошук
        # індексує сміттєві сторінки як повноцінні.
        info.not_found_is_soft = result.status_code is not None and 200 <= result.status_code < 300

    alt = _alternate_host(origin)
    if alt:
        info.alt_host = alt
        alt_result = await fetcher.get(alt)
        if alt_result.error is None:
            info.alt_host_checked = True
            info.alt_host_status = alt_result.status_code
            info.alt_host_redirects_home = _same_host(alt_result.final_url, origin)
    return info


def _alternate_host(origin: str) -> str | None:
    """example.com ↔ www.example.com. Для інших піддоменів проби немає."""
    parsed = urlparse(origin)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        other = host[4:]
    elif host.count(".") == 1:
        other = f"www.{host}"
    else:
        return None
    return f"{parsed.scheme}://{other}/"


def _same_host(url: str, origin: str) -> bool:
    return urlparse(url).netloc.lower() == urlparse(origin).netloc.lower()


async def collect_llms_txt(fetcher: Fetcher, origin: str) -> LlmsTxtInfo:
    result = await fetcher.get(urljoin(origin, "/llms.txt"))
    info = LlmsTxtInfo(status_code=result.status_code, content=result.text[:200_000])
    if not result.ok or result.is_html or not info.content.strip():
        return info
    info.exists = True
    info.has_h1 = bool(re.search(r"^#\s+\S", info.content, re.M))
    info.section_count = len(re.findall(r"^##\s+\S", info.content, re.M))
    info.link_count = len(re.findall(r"\[[^\]]+\]\([^)]+\)", info.content))
    return info
