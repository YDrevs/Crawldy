"""CRO-сигнали: чи видно на сторінці, що робити далі."""

from __future__ import annotations

from app.audit.checks.conversion import NoWayToActCheck, PhoneNotTappableCheck
from app.audit.types import RenderResult, SiteContext
from tests.factories import context, page_from_html


def rendered(*pages) -> SiteContext:
    """Контекст, у якому сторінки справді відкривали в браузері.

    Чек навмисно судить лише про відрендерені сторінки: у статичному
    HTML заклик часто відсутній не тому, що його немає, а тому, що його
    домальовує скрипт.
    """
    ctx = context(*pages)
    for page in pages:
        ctx.renders[page.url] = RenderResult(
            url=page.url, rendered=True, html="", signals=page
        )
    return ctx

SERVICE_URL = "https://example.com/services/roof-repair"

# Сторінка мусить мати справжній текст: чек навмисно мовчить на коротких
# сторінках, бо не відрізняє «немає кнопки» від «тіло домальовує скрипт».
SERVICE_TEXT = (
    "<p>Ремонтуємо покрівлю будь-якої складності: бітумну черепицю, "
    "металочерепицю, фальцеву покрівлю та мʼяку покрівлю на пласких дахах. "
    "Виїжджаємо на обʼєкт, оглядаємо конструкцію, шукаємо причину протікання "
    "й показуємо фотозвіт до початку робіт. Працюємо з приватними будинками, "
    "багатоквартирними будівлями й комерційними обʼєктами по всій області. "
    "Матеріали закуповуємо в постачальника напряму, тому ціна виходить нижчою "
    "за роздрібну, а на роботи діє гарантія три роки. Бригада виходить на "
    "обʼєкт протягом двох робочих днів після узгодження кошторису, а термінові "
    "аварійні виїзди робимо того ж дня, включно з вихідними та святами.</p>"
)


def _service(body: str) -> object:
    html = (
        "<html lang='uk'><head><title>Ремонт покрівлі під ключ у Києві</title></head>"
        f"<body><h1>Ремонт покрівлі</h1>{SERVICE_TEXT}{body}</body></html>"
    )
    return page_from_html(html, url=SERVICE_URL, depth=1)


def test_service_page_with_no_way_to_act_is_a_finding():
    page = _service("<a href='/about'>Про нас</a><a href='/blog'>Блог</a>")
    issues = list(NoWayToActCheck().run(rendered(page)))
    assert len(issues) == 1
    assert issues[0].page_url == SERVICE_URL


def test_a_form_counts_as_a_way_to_act():
    page = _service("<form action='/lead'><input name='phone'></form>")
    assert not list(NoWayToActCheck().run(rendered(page)))


def test_a_clickable_phone_counts():
    page = _service("<a href='tel:+380441234567'>044 123 45 67</a>")
    assert not list(NoWayToActCheck().run(rendered(page)))


def test_a_link_to_contacts_counts():
    page = _service("<a href='/contacts/'>Наші контакти</a>")
    assert not list(NoWayToActCheck().run(rendered(page)))


def test_a_call_to_action_in_the_anchor_counts():
    """Кнопка може вести на будь-яку адресу — впізнаємо її за текстом."""
    page = _service("<a href='/x7/'>Замовити прорахунок</a>")
    assert not list(NoWayToActCheck().run(rendered(page)))


def test_an_article_is_not_required_to_sell():
    """Вимагати кнопки від статті означало б карати за те, що вона стаття."""
    article = page_from_html(
        "<html lang='uk'><head><title>Як обрати покрівлю для будинку</title></head>"
        "<body><h1>Як обрати покрівлю</h1><p>Текст статті.</p>"
        "<a href='/blog'>Усі статті</a></body></html>",
        url="https://example.com/blog/how-to-choose",
        depth=1,
    )
    assert not list(NoWayToActCheck().run(rendered(article)))


# ── телефон, з якого не подзвонити ─────────────────────────────────────────


def _page_with_printed_phone(url: str, number: str = "+38 (044) 123-45-67") -> object:
    return page_from_html(
        f"<html lang='uk'><head><title>Контакти нашої компанії у Києві</title></head>"
        f"<body><h1>Контакти</h1><p>Телефонуйте: {number}</p></body></html>",
        url=url,
        depth=1,
    )


def test_printed_phone_without_a_dial_link_is_a_finding():
    ctx = context(
        _page_with_printed_phone("https://example.com/contacts"),
        _page_with_printed_phone("https://example.com/about"),
    )
    issues = list(PhoneNotTappableCheck().run(ctx))
    assert len(issues) == 1
    assert issues[0].params["count"] == 2


def test_one_dial_link_anywhere_makes_the_check_silent():
    """Якщо номер клікабельний хоч десь, проблеми з версткою немає."""
    ctx = context(
        _page_with_printed_phone("https://example.com/contacts"),
        page_from_html(
            "<html><head><title>Головна сторінка компанії</title></head>"
            "<body><h1>Головна</h1><a href='tel:+380441234567'>Подзвонити</a>"
            "</body></html>"
        ),
    )
    assert not list(PhoneNotTappableCheck().run(ctx))


def test_a_number_on_one_page_only_is_not_the_site_phone():
    """Одна сторінка — це може бути число зі статті, а не номер компанії."""
    ctx = context(_page_with_printed_phone("https://example.com/blog/post"))
    assert not list(PhoneNotTappableCheck().run(ctx))


def test_a_long_number_without_separators_is_not_a_phone():
    """Артикул і рахунок — це не телефон, і плутати їх дорого."""
    ctx = context(
        page_from_html(
            "<html><head><title>Товар у каталозі магазину меблів</title></head>"
            "<body><h1>Товар</h1><p>Артикул 900123456789 у наявності.</p></body></html>",
            url="https://example.com/p/1",
        ),
        page_from_html(
            "<html><head><title>Інший товар у каталозі магазину</title></head>"
            "<body><h1>Товар</h1><p>Артикул 900123456788 у наявності.</p></body></html>",
            url="https://example.com/p/2",
        ),
    )
    assert not list(PhoneNotTappableCheck().run(ctx))


def test_a_page_we_could_not_read_is_not_a_page_without_a_button():
    """Нуль внутрішніх посилань — це наш недочитаний краул, а не сайт.

    На hubspot.com такою виявилась /pricing/sales: вміст приходить
    скриптом, рендер до неї не дійшов, і знахідка описувала б нас.
    """
    shell = page_from_html(
        "<html lang='uk'><head><title>Ціни на послуги компанії у Києві</title></head>"
        "<body><div id='app'></div>" + "<span class='x'></span>" * 400 + "</body></html>",
        url="https://example.com/services/pricing",
        depth=1,
    )
    assert not list(NoWayToActCheck().run(rendered(shell)))


def test_a_glossary_entry_is_not_a_commercial_page():
    """Слово всередині терміна не робить довідник послугою."""
    entry = page_from_html(
        "<html lang='en'><head><title>Configure Price Quote — what it means</title></head>"
        f"<body><h1>Configure price quote</h1>{SERVICE_TEXT}"
        "<a href='/glossary'>All terms</a></body></html>",
        url="https://example.com/glossary/configure-price-quote",
        depth=1,
    )
    assert not list(NoWayToActCheck().run(rendered(entry)))


def test_a_contact_link_in_the_menu_does_not_count_as_the_page_offering_it():
    """Меню з «Контактами» має кожен сайт — воно нічого не каже про сторінку.

    Поки посилання рахувались будь-де, чек не спрацював на жодній із
    сорока однієї комерційної сторінки восьми живих сайтів.
    """
    page = page_from_html(
        "<html lang='uk'><head><title>Ремонт покрівлі під ключ у Києві</title></head>"
        "<body><nav><a href='/contacts/'>Контакти</a></nav>"
        f"<h1>Ремонт покрівлі</h1>{SERVICE_TEXT}"
        "<footer><a href='tel:+380441234567'>044 123 45 67</a></footer>"
        "</body></html>",
        url=SERVICE_URL,
        depth=1,
    )
    assert list(NoWayToActCheck().run(rendered(page)))


def test_the_same_action_inside_the_page_body_counts():
    page = _service("<p>Готові почати? <a href='/contacts/'>Напишіть нам</a></p>")
    assert not list(NoWayToActCheck().run(rendered(page)))


def test_a_phone_in_the_page_body_counts():
    page = _service("<p>Дзвоніть: <a href='tel:+380441234567'>044 123 45 67</a></p>")
    assert not list(NoWayToActCheck().run(rendered(page)))


def test_a_button_in_the_header_is_not_treated_as_menu():
    """У шапці часто стоїть головна кнопка — викидати її не можна."""
    page = page_from_html(
        "<html lang='uk'><head><title>Ремонт покрівлі під ключ у Києві</title></head>"
        "<body><header><a href='/order/'>Замовити прорахунок</a></header>"
        f"<h1>Ремонт покрівлі</h1>{SERVICE_TEXT}</body></html>",
        url=SERVICE_URL,
        depth=1,
    )
    assert not list(NoWayToActCheck().run(rendered(page)))


def test_a_site_search_box_is_not_a_way_to_get_in_touch():
    """Пошук по сайту — теж форма, але звертанням він не є."""
    page = _service(
        "<nav><a href='/about'>Про нас</a></nav>"
        "<form method='get' action='/?s='><input name='s'></form>"
    )
    assert list(NoWayToActCheck().run(rendered(page)))


# ── доступність: що ми називаємо блокуючим ─────────────────────────────────


def test_contrast_alone_is_not_a_blocking_failure():
    """Наші дані не відрізняють нечитабельну сторінку від сірого підпису.

    На калібрувальній вибірці контраст провалювався на 17 сайтах із 31 і
    на шести був єдиною причиною «блокуючої» знахідки — тобто заявою про
    зламане користування там, де її нема чим довести.
    """
    from app.audit.checks.accessibility import BLOCKING

    assert "color-contrast" not in BLOCKING


def test_a_button_without_a_name_still_blocks():
    """Межа лишилась там, де факт однозначний: натиснути справді нічим."""
    from app.audit.checks.accessibility import BLOCKING

    assert {"button-name", "link-name", "meta-viewport", "label"} <= BLOCKING
