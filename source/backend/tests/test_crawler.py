"""Порядок краулу: що тягнеться раніше, коли бюджету на все не вистачає."""

from __future__ import annotations

import pytest

from app.audit.crawler import crawl
from app.audit.fetcher import FetchResult
from app.audit.page_kinds import PageKind, kind_of

ORIGIN = "https://example.com"


class FakeFetcher:
    """Віддає сторінку з посиланнями за картою; чужі URL — 404."""

    def __init__(self, links: dict[str, list[str]]) -> None:
        self._links = links
        self.asked: list[str] = []

    async def get(self, url: str) -> FetchResult:
        self.asked.append(url)
        anchors = "".join(f'<a href="{href}">посилання</a>' for href in self._links.get(url, []))
        html = f"<html><head><title>Сторінка</title></head><body><h1>Ц</h1>{anchors}</body></html>"
        return FetchResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            text=html,
            body_bytes=len(html.encode()),
            elapsed_ms=10,
            headers={},
        )


def _home_linking_to(*targets: str) -> FakeFetcher:
    return FakeFetcher({f"{ORIGIN}/": [f"{ORIGIN}{path}" for path in targets]})


@pytest.mark.asyncio
async def test_service_pages_are_fetched_before_blog_articles():
    """На ka-dent.com.ua бюджет у 14 сторінок з'їдали одинадцять статей
    блогу, а сторінка послуг лишалася непрочитаною. Чек про ціни через
    таку вибірку мовчить на сайті, де цін справді немає."""
    fetcher = _home_linking_to(
        "/blog/stattya-1", "/blog/stattya-2", "/blog/stattya-3",
        "/blog/stattya-4", "/kontakty", "/poslugy",
    )

    pages, _ = await crawl(fetcher, f"{ORIGIN}/", ORIGIN, max_pages=3, max_depth=1)

    fetched = {p.url for p in pages}
    assert f"{ORIGIN}/kontakty" in fetched
    assert f"{ORIGIN}/poslugy" in fetched
    assert not any("/blog/" in url for url in fetched)


@pytest.mark.asyncio
async def test_legal_pages_go_last():
    """Сторінка договору буває на сто тисяч слів і не каже ні що продають,
    ні де вони."""
    fetcher = _home_linking_to("/legal/terms", "/privacy", "/pro-nas")

    pages, _ = await crawl(fetcher, f"{ORIGIN}/", ORIGIN, max_pages=2, max_depth=1)

    assert f"{ORIGIN}/pro-nas" in {p.url for p in pages}


@pytest.mark.asyncio
async def test_a_pure_blog_still_gets_crawled():
    """Пріоритет має значення лише там, де є з чого вибирати. На сайті,
    де все — статті, він не має залишити аудит без сторінок."""
    fetcher = _home_linking_to("/blog/a", "/blog/b", "/blog/c")

    pages, _ = await crawl(fetcher, f"{ORIGIN}/", ORIGIN, max_pages=4, max_depth=1)

    assert len(pages) == 4


@pytest.mark.asyncio
async def test_the_entry_page_is_always_first():
    fetcher = _home_linking_to("/ciny", "/kontakty")

    pages, _ = await crawl(fetcher, f"{ORIGIN}/", ORIGIN, max_pages=3, max_depth=1)

    assert pages[0].url == f"{ORIGIN}/"


@pytest.mark.asyncio
async def test_two_runs_of_the_same_site_read_the_same_pages():
    """Без лічильника порядку купа впорядковує однакові ключі за URL, і
    вибірка починає залежати від назв — а не від того, що ми хотіли."""
    links = [f"/rozdil-{n}" for n in range(12)]

    first, _ = await crawl(_home_linking_to(*links), f"{ORIGIN}/", ORIGIN, max_pages=5, max_depth=1)
    second, _ = await crawl(_home_linking_to(*links), f"{ORIGIN}/", ORIGIN, max_pages=5, max_depth=1)

    assert [p.url for p in first] == [p.url for p in second]


# --- сам словник --------------------------------------------------------


def test_substring_in_a_path_does_not_make_a_page_telling():
    """У `/legal/ssa-services-terms` є «services», і на stripe.com саме
    через це у вибірку замість цін потрапляли сторінки договорів."""
    assert kind_of("https://stripe.com/legal/ssa-services-terms") is PageKind.BOILERPLATE
    assert kind_of("https://stripe.com/services") is PageKind.TELLING


def test_home_page_is_its_own_kind():
    assert kind_of("https://example.com/") is PageKind.HOME
    assert kind_of("https://example.com") is PageKind.HOME


def test_service_page_under_a_blog_section_still_counts_as_telling():
    assert kind_of("https://example.com/blog/pricing") is PageKind.TELLING


def test_ordinary_page_is_neither():
    assert kind_of("https://example.com/dosvid") is PageKind.ORDINARY


def test_sorted_variants_of_the_home_page_are_not_the_home_page():
    """Магазин на WooCommerce дає їх десятками. З порожнім шляхом вони
    отримували найвищий пріоритет і з'їдали весь бюджет краулу, лишаючи
    сайт без сторінки контактів."""
    assert kind_of("https://shop.ua/") is PageKind.HOME
    assert kind_of("https://shop.ua?orderby=popularity") is PageKind.FACET
    assert kind_of("https://shop.ua?per_page=30") is PageKind.FACET
    assert kind_of("https://shop.ua/catalog?shop_view=list") is PageKind.FACET


def test_a_query_we_do_not_recognise_leaves_the_page_alone():
    """`?id=12` на старих сайтах — справжня сторінка. Демоутити все з
    параметрами означало б її втратити."""
    assert kind_of("https://old.ua/index?id=12") is PageKind.ORDINARY
    assert kind_of("https://old.ua/kontakty?id=12") is PageKind.TELLING


@pytest.mark.asyncio
async def test_facets_do_not_crowd_out_the_contact_page():
    fetcher = FakeFetcher({
        f"{ORIGIN}/": [
            f"{ORIGIN}?orderby=popularity", f"{ORIGIN}?orderby=rating",
            f"{ORIGIN}?per_page=15", f"{ORIGIN}?per_page=30",
            f"{ORIGIN}?shop_view=list", f"{ORIGIN}/kontakty",
        ]
    })

    pages, _ = await crawl(fetcher, f"{ORIGIN}/", ORIGIN, max_pages=2, max_depth=1)

    assert f"{ORIGIN}/kontakty" in {p.url for p in pages}


@pytest.mark.asyncio
async def test_top_level_contacts_beat_a_pile_of_product_cards():
    """І картка товару, і контакти щось стверджують про компанію. Але
    перша сторінка на сайті одна, а других сотня — і на crustula.com.ua
    краул читав п'ять карток печива й жодного разу контакти."""
    fetcher = _home_linking_to(
        "/product/moon-cake", "/product/asteroyid", "/product/vega",
        "/product/moon", "/product/vafelna-trubochka", "/contacts",
    )

    pages, _ = await crawl(fetcher, f"{ORIGIN}/", ORIGIN, max_pages=2, max_depth=1)

    assert f"{ORIGIN}/contacts" in {p.url for p in pages}


# --- засів із карти сайту -----------------------------------------------


def test_seeds_are_spread_across_the_whole_sitemap():
    """Обрізання за позицією бере те, що сайт випадково поклав першим."""
    from app.audit.orchestrator import SITEMAP_SEEDS, _seed_from_sitemap

    urls = [f"https://shop.ua/p/{n}" for n in range(5000)]

    seeds = _seed_from_sitemap(urls)

    assert len(seeds) == SITEMAP_SEEDS
    tail = [u for u in seeds if int(u.rsplit("/", 1)[1]) > 4000]
    assert tail, "хвіст карти не потрапив у засів"


def test_location_pages_survive_a_sitemap_where_they_are_a_rounding_error():
    """На furniturerow.com сторінки магазинів — півтора відсотка карти на
    8149 адрес, і рівномірна вибірка з пʼятдесяти не ловила жодної. Саме
    на них лежать адреса, години й geo."""
    from app.audit.orchestrator import _seed_from_sitemap

    urls = [f"https://chain.com/p/{n}" for n in range(5000)]
    for n in range(0, 5000, 70):  # ~70 сторінок магазинів, розкиданих по карті
        urls[n] = f"https://chain.com/locations/City{n}/TX/{n}"

    seeds = _seed_from_sitemap(urls)
    stores = [u for u in seeds if "/locations/" in u]

    assert stores, "жодної сторінки магазину в засіві"
    # Але й не всі: мережа має сотні точок, і віддати їм увесь бюджет
    # краулу означало б не побачити решти сайту. Кілька доводять шаблон.
    assert len(stores) <= 5, "розділ магазинів зʼїв засів"


def test_a_small_sitemap_is_taken_whole():
    from app.audit.orchestrator import _seed_from_sitemap

    urls = [f"https://shop.ua/p/{n}" for n in range(12)]

    assert _seed_from_sitemap(urls) == urls


def test_location_pages_are_worth_reading():
    """Без цього слова адреса сторінки магазину має звичайний пріоритет,
    і бюджет краулу з'їдають картки товарів."""
    assert kind_of("https://chain.com/locations/Tyler/TX/100011") is PageKind.TELLING
    assert kind_of("https://chain.com/store-locator") is PageKind.TELLING
    assert kind_of("https://chain.com/pl/Bedroom-Furniture") is PageKind.ORDINARY


@pytest.mark.asyncio
async def test_a_seeded_page_is_not_punished_for_a_deep_url():
    """Глибина шляху приборкує сотні карток товару, але для адреси з карти
    сайту вона нічого не означає: цю сторінку ми обрали свідомо. Без
    винятку /locations/Denver/CO/100048 програвала будь-якій службовій
    сторінці першого рівня, і мережа з трьомастами точками аудитувалась
    так, ніби точок у неї немає."""
    deep = f"{ORIGIN}/locations/Denver/CO/100048"
    fetcher = FakeFetcher({f"{ORIGIN}/": [f"{ORIGIN}/about-us", f"{ORIGIN}/contacts"]})

    pages, _ = await crawl(
        fetcher, f"{ORIGIN}/", ORIGIN, max_pages=2, max_depth=1, seed_urls=[deep]
    )

    assert deep in {p.url for p in pages}


# ── E-12: маршрути шести мов запуску ──────────────────────────────────────


@pytest.mark.parametrize(("url", "expected"), [
    ("https://s.de/preise", PageKind.TELLING),
    ("https://s.de/kontakt", PageKind.TELLING),
    ("https://s.de/impressum", PageKind.BOILERPLATE),
    ("https://s.de/nachrichten", PageKind.ARCHIVE),
    ("https://s.es/precios", PageKind.TELLING),
    ("https://s.es/contacto", PageKind.TELLING),
    ("https://s.es/privacidad", PageKind.BOILERPLATE),
    ("https://s.es/noticias", PageKind.ARCHIVE),
    ("https://s.fr/tarifs", PageKind.TELLING),
    ("https://s.fr/boutique", PageKind.TELLING),
    ("https://s.fr/panier", PageKind.BOILERPLATE),
    ("https://s.fr/actualites", PageKind.ARCHIVE),
    ("https://s.ru/tseny", PageKind.TELLING),
    ("https://s.ru/uslugi", PageKind.TELLING),
    ("https://s.ru/korzina", PageKind.BOILERPLATE),
    ("https://s.ru/novosti", PageKind.ARCHIVE),
])
def test_a_translated_route_gets_the_priority_its_english_twin_has(url: str, expected: PageKind) -> None:
    """Доти сторінка цін німецькою була для краулу звичайною сторінкою.

    `/pricing` тягнулося раніше за картки товарів, а `/preise`, `/precios`,
    `/tarifs` і `/tseny` не означали нічого — тобто на німецькому магазині
    бюджет краулу з'їдали товари, і сторінка цін у вибірку не потрапляла.
    Це не косметика: чого краул не приніс, про те звіт мовчить.
    """
    assert kind_of(url) is expected


def test_priority_does_not_depend_on_a_language_prefix() -> None:
    """`kind_of` вирішує, що тягнути раніше, ще ДО того, як щось прочитано.

    Оголошених мов тоді не існує: їх виводять із прочитаних сторінок. Тому
    пріоритет тримається на самому слові маршруту, а не на префіксі, і
    голий `/de` лишається звичайною адресою — доказів, що це мовний
    корінь, у краула в цю мить немає.
    """
    assert kind_of("https://s.com/de/preise") is PageKind.TELLING
    assert kind_of("https://s.com/de") is PageKind.ORDINARY
    assert kind_of("https://s.com/it/helpdesk") is PageKind.ORDINARY


@pytest.mark.parametrize(("raw", "encoded", "expected"), [
    # Німецька: `über` у словнику TELLING.
    ("https://s.de/über-uns", "https://s.de/%C3%BCber-uns", PageKind.TELLING),
    # Іспанська: `términos` у словнику BOILERPLATE.
    ("https://s.es/términos", "https://s.es/t%C3%A9rminos", PageKind.BOILERPLATE),
    # Французька: `actualités` у словнику ARCHIVE.
    ("https://s.fr/actualités", "https://s.fr/actualit%C3%A9s", PageKind.ARCHIVE),
    # Українська: `послуги` у словнику TELLING.
    ("https://s.ua/послуги",
     "https://s.ua/%D0%BF%D0%BE%D1%81%D0%BB%D1%83%D0%B3%D0%B8", PageKind.TELLING),
    # Російська: `услуги` у словнику TELLING.
    ("https://s.ru/услуги",
     "https://s.ru/%D1%83%D1%81%D0%BB%D1%83%D0%B3%D0%B8", PageKind.TELLING),
    # `компанії` — слово ТИПУ сторінки, а не пріоритету, тож правильний
    # наявний вид тут ORDINARY. Рівність форм пінимо й для нього: вона має
    # триматись і там, де вид звичайний, інакше перевірка доводила б лише
    # вдалі випадки.
    ("https://s.ua/компанії",
     "https://s.ua/%D0%BA%D0%BE%D0%BC%D0%BF%D0%B0%D0%BD%D1%96%D1%97", PageKind.ORDINARY),
])
def test_crawl_priority_is_the_same_however_the_address_is_encoded(
    raw: str, encoded: str, expected: PageKind
) -> None:
    """Пріоритет краулу вирішується зі слів шляху, а шлях приходить закодованим.

    Доки сегмент не декодувати, `%d1%83%d1%81...` не означає нічого, і
    сторінка послуг на російському сайті тягнеться як звичайна — тобто
    втрачає місце в бюджеті на користь карток товару. Чого краул не приніс,
    про те звіт мовчить.
    """
    assert kind_of(raw) is expected
    assert kind_of(encoded) is expected
    assert kind_of(raw) is kind_of(encoded)


def test_encoding_does_not_change_english_priority() -> None:
    """Декодування не сміє зрушити жодну з наявних англійських адрес."""
    assert kind_of("https://stripe.com/services") is PageKind.TELLING
    assert kind_of("https://stripe.com/legal/ssa-services-terms") is PageKind.BOILERPLATE
    assert kind_of("https://example.com/") is PageKind.HOME
    assert kind_of("https://shop.ua?orderby=popularity") is PageKind.FACET


def test_the_new_locales_leave_english_and_ukrainian_priority_alone() -> None:
    """Словник розширено додаванням, а не заміною.

    Ризик тут конкретний: чуже слово, що збіглося з англійським, мовчки
    зсунуло б пріоритет сайтів, яких E-12 не стосується взагалі. Тому в
    словник мов запуску не потрапило жодного англійського слова, і ця
    перевірка стереже саме це.
    """
    assert kind_of("https://stripe.com/services") is PageKind.TELLING
    assert kind_of("https://stripe.com/legal/ssa-services-terms") is PageKind.BOILERPLATE
    assert kind_of("https://example.com/blog/pricing") is PageKind.TELLING
    assert kind_of("https://example.com/dosvid") is PageKind.ORDINARY
    assert kind_of("https://old.ua/kontakty?id=12") is PageKind.TELLING
    assert kind_of("https://chain.com/pl/Bedroom-Furniture") is PageKind.ORDINARY
