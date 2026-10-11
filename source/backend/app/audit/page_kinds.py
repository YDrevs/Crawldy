"""Про що сторінка: що це за сторінка і наскільки вона нам потрібна.

Два різні питання, тому дві функції над спільним словником.

`kind_of` відповідає «що тягнути раніше» — це пріоритет краулу й вибірки.
`type_of` відповідає «що це взагалі за сторінка» — і саме на нього
спираються правила. Змішувати їх не можна: сторінка входу в адмінку має
низький пріоритет краулу й водночас цілком конкретний тип, від якого
залежить, чи є `noindex` на ній проблемою.

Словник один навмисно. Три копії того самого переліку розійшлися б на
першій зміні, і наслідок був би тихий: краул приносить сторінку, яку
інший шар не впізнає.

Судження за адресою слабке, тому джерела впорядковані: спершу типи
JSON-LD, які сайт заявив про себе сам, потім слова шляху, потім заголовок.
Правило, що спирається на тип, мусить це враховувати — саме тому
`type_of` повертає ще й те, звідки взявся висновок.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from urllib.parse import unquote, urlparse

from app.audit import vocab
from app.audit.vocab.enums import Concept

# Слова, якими впізнають тип сторінки, живуть у `vocab`, а не тут.
#
# Причина не в охайності: доки вони лежали серед логіки чеків, додати
# мову означало правити код класифікації. А непокрита мова ламається
# тихо — іспанський `/precios` просто стає UNKNOWN, і з ним мовчки
# відпадають правила, що спираються на тип. Тепер додати мову — це
# дописати рядки в `vocab/words.py`.
#
# Мова сайту й мова інтерфейсу — різні речі й мають різні типи: див.
# `vocab.ContentLanguage`.

# Де компанії пишуть, хто вони, що продають і як з ними звʼязатися.
TELLING_WORDS = vocab.words_for(Concept.TELLING)

# Стрічки, архіви й пагінація. Кожна така сторінка окремо додає мало:
# вона переказує інші сторінки замість того, щоб щось стверджувати.
ARCHIVE_WORDS = vocab.words_for(Concept.ARCHIVE)

# Юридичне й службове: ні що продають, ні де вони. Сторінка договору
# буває на сто тисяч слів і витісняє з бюджету все інше.
BOILERPLATE_WORDS = vocab.words_for(Concept.BOILERPLATE)


# Параметри, які не відкривають нову сторінку, а показують ту саму
# інакше. Магазин на WooCommerce дає їх десятками з головної.
FACET_PARAMS = frozenset({
    "orderby", "order", "sort", "sortby", "per_page", "perpage", "per_row",
    "shop_view", "view", "layout", "columns", "filter", "filter_by",
    "min_price", "max_price", "paged", "page", "offset", "limit",
})


# Мови запуску, чий перший сегмент шляху ДОЗВОЛЕНО зняти. Сам перелік дозволом
# не є: сегмент знімається лише тоді, коли цю мову оголосив сам сайт (OD-05).
#
# Різниця не теоретична. Перелік префіксів, застосований без оголошення, зняв
# би `/it/` з англійського сайту, де це відділ, а не італійська, і сторінка
# `/it/helpdesk` стала б головною. Двох літер у шляху достатньо, щоб вигадати
# мову, і замало, щоб її встановити.
SUPPORTED_LOCALES = frozenset({"en", "uk", "de", "es", "fr", "ru"})


# Типи сторінок для правил. Не збігаються з PageKind: там пріоритет
# краулу, тут — застосовність правила.
class PageType(StrEnum):
    HOME = "home"
    PRODUCT = "product"
    LISTING = "listing"
    SERVICE = "service"
    ARTICLE = "article"
    # Документація: довідка, посібник, API-референс. Не стаття — у неї
    # немає автора, дати й розмітки Article, і це не недбалість, а те,
    # як документацію пишуть усі.
    DOCS = "docs"
    CASE_STUDY = "case_study"
    ABOUT = "about"
    CONTACT = "contact"
    LOCATION = "location"
    PERSON = "person"
    LEGAL = "legal"
    # Вхід, кошик, кабінет, пошук. Такі сторінки не мають ранжуватися, і
    # noindex на них — правильне рішення власника, а не дефект.
    SYSTEM = "system"
    ARCHIVE = "archive"
    OTHER = "other"


class Basis(StrEnum):
    """Що ми зробили з першим сегментом шляху — і чи впевнені у відповіді."""

    # Перший сегмент не схожий на мову запуску: звичайний шлях, звичайний висновок.
    NO_LOCALE_SEGMENT = "no_locale_segment"
    # Сегмент є мовою, і сайт цю мову оголосив. Знято, висновок повний.
    DECLARED_LOCALE = "declared_locale"
    # Сегмент СХОЖИЙ на мову запуску, але сайт її не оголошував. Не знімаємо —
    # і не вдаємо, що відповідь повна: `/de/folder` цілком може бути текою.
    LOCALE_NOT_DECLARED = "locale_not_declared"


@dataclass(frozen=True, slots=True)
class Classification:
    """Тип сторінки разом із тим, на чому він тримається.

    `type_of` віддає саме тип і нічого більше — на ньому тримаються всі наявні
    правила, і міняти його форму означало б міняти кожного споживача. Той, кому
    потрібна ще й підстава, питає `classify`.
    """

    page_type: PageType
    locale: str | None = None
    basis: Basis = Basis.NO_LOCALE_SEGMENT

    @property
    def conclusive(self) -> bool:
        """Чи можна подавати цей висновок як певний.

        Ні рівно в одному випадку: шлях починається з чогось, що виглядає
        мовою запуску, а доказів цієї мови сайт не дав. Тоді ми не знаємо,
        чи це мовна версія, чи тека з такою назвою, і кажемо це вголос.
        """
        return self.basis is not Basis.LOCALE_NOT_DECLARED


# Сторінки, які не призначені для пошуку. Для них noindex очікуваний, а
# вимоги до тексту й розмітки не мають сенсу.
NOT_FOR_SEARCH = frozenset({PageType.SYSTEM, PageType.ARCHIVE})

# Де текст меряти словами безглуздо: цінність несуть товари, фільтри й
# розмітка, а не проза. Категорія меблів із 90 слів — нормальна сторінка.
CONTENT_IS_NOT_PROSE = frozenset({PageType.PRODUCT, PageType.LISTING})

# Схема Article з автором і датою доречна тут і більше ніде. Зокрема
# не в документації: у довідки немає автора, і вимагати його означає
# просити вигадати людину.
EXPECTS_AUTHORSHIP = frozenset({PageType.ARTICLE})

# Сторінки, які існують заради дії: щось продають або кудись ведуть.
# Стаття, «про нас» і юридичний текст сюди не входять — вимагати від
# них кнопки означало б карати сайт за те, що він не все перетворив на
# лендинг.
SELLS_SOMETHING = frozenset({PageType.PRODUCT, PageType.SERVICE, PageType.LOCATION})

# Типи, для яких сусідство в розділі означає спільну тему. Стаття поруч
# зі статтею і послуга поруч із послугою мали б посилатися одна на одну;
# контакти й «про нас» існують в однині, і вимагати від них кластера —
# вимагати того, чого сайт і не задумував.
BUILDS_A_TOPIC = frozenset({
    PageType.ARTICLE,
    PageType.DOCS,
    PageType.SERVICE,
    PageType.PRODUCT,
    PageType.CASE_STUDY,
})

# Типи за розміткою, яку сайт заявив про себе сам. Найнадійніше джерело:
# це не наш здогад із адреси, а твердження сайту.
_SCHEMA_TYPES: dict[str, PageType] = {
    "product": PageType.PRODUCT,
    "offer": PageType.PRODUCT,
    "itemlist": PageType.LISTING,
    "collectionpage": PageType.LISTING,
    "searchresultspage": PageType.LISTING,
    "article": PageType.ARTICLE,
    "blogposting": PageType.ARTICLE,
    "newsarticle": PageType.ARTICLE,
    "techarticle": PageType.ARTICLE,
    "report": PageType.ARTICLE,
    "aboutpage": PageType.ABOUT,
    "contactpage": PageType.CONTACT,
    "profilepage": PageType.PERSON,
    "person": PageType.PERSON,
    "localbusiness": PageType.LOCATION,
    "store": PageType.LOCATION,
    "place": PageType.LOCATION,
    "service": PageType.SERVICE,
}

# Типи, які майже кожен сайт ставить на всі сторінки одразу. Робити з них
# висновок про тип сторінки не можна.
_SCHEMA_NOISE = frozenset({"webpage", "website", "organization", "breadcrumblist",
                           "sitenavigationelement", "imageobject", "webpageelement"})

_SYSTEM_WORDS = frozenset({
    "wp-login", "wp-admin", "login", "signin", "sign-in", "logout", "register",
    "admin", "cart", "checkout", "my-account", "account", "dashboard", "search",
    "wishlist", "compare", "basket", "kabinet", "koshyk",
})
_LEGAL_WORDS = frozenset({
    "legal", "terms", "tos", "privacy", "policy", "policies", "cookie", "cookies",
    "gdpr", "dpa", "license", "licence", "disclaimer", "eula", "оферта",
    "конфіденційності",
    # Мови запуску (E-12). Свідомо лише ті токени, які не є англійськими
    # словами: `conditions`, наприклад, сюди не потрапляє, бо воно змінило б
    # тип англійських сторінок, яких E-12 не стосується.
    "impressum", "datenschutz", "agb", "nutzungsbedingungen", "widerruf",
    "privacidad", "terminos", "términos", "condiciones",
    "mentions", "legales", "légales", "confidentialite", "confidentialité",
    "cgv", "cgu",
    "политика", "конфиденциальности", "соглашение", "условия",
    # Латиниця тут із тієї ж причини, що й `poslugy` в українській: половина
    # CMS пише адреси транслітерацією, і не впізнавати `/politika-
    # konfidencialnosti` означало б не впізнавати половину сайтів.
    "politika", "konfidencialnosti", "soglashenie", "usloviya",
})
_ARTICLE_SECTIONS = frozenset({"blog", "news", "novyny", "новини", "article",
                               "articles", "post", "posts", "stories", "press"})

# Розділи документації. Спершу вони жили серед статей — щоб глосарій не
# ставав послугою через слово «price» усередині терміна, — і це
# полагодило одне, зламавши інше: від кожної сторінки документації
# почали вимагати автора, дату й розмітку Article. Документація не має
# нічого з цього за задумом, тож у неї власний тип.
_DOCS_SECTIONS = frozenset({"docs", "documentation", "doc", "guide", "guides",
                            "reference", "manual", "handbook", "learn", "resources",
                            "glossary", "wiki", "dictionary", "encyclopedia",
                            "довідник", "документація"})
# «page» сюди не входить: воно трапляється в `/random-page` так само, як
# у `/page/2`. Пагінація впізнається окремо — за номером після слова.
_ARCHIVE_WORDS = frozenset({"tag", "tags", "category", "categories", "archive",
                            "author", "feed"})
_CASE_WORDS = frozenset({"projects", "project", "case", "cases", "case-study",
                         "case-studies", "portfolio", "roboty", "проекти"})
_PRODUCT_WORDS = frozenset({"product", "tovar", "item", "sku", "p"})
_LISTING_WORDS = frozenset({"catalog", "catalogue", "каталог", "shop", "store",
                            "collection", "collections", "category", "pl", "products"})
_SERVICE_WORDS = frozenset({"services", "service", "послуги", "poslugy", "poslugi",
                            "pricing", "price", "prices", "ціни", "tariffs", "тарифи",
                            # Мови запуску (E-12): ціни й послуги шістьма мовами.
                            "preise", "preis", "preisliste", "tarife",
                            "leistungen", "dienstleistungen",
                            "precios", "precio", "tarifas", "servicios", "servicio",
                            "tarifs", "tarif", "prix",
                            "цены", "цена", "tseny", "тарифы", "tarify",
                            "услуги", "uslugi",
                            "tsiny", "tsina"})
_ABOUT_WORDS = frozenset({"about", "about-us", "company", "про-нас", "pro-nas",
                          "history", "team", "команда",
                          # Мови запуску (E-12).
                          "ueber", "über", "unternehmen",
                          "nosotros", "empresa",
                          "propos", "entreprise",
                          "компания", "компанії", "компании",
                          "kompaniya", "kompanii"})
_CONTACT_WORDS = frozenset({"contact", "contacts", "kontakt", "kontakty", "kontakti",
                            "контакти", "контакт", "support", "help",
                            # Мови запуску (E-12).
                            "kontakte", "contacto", "contactos", "контакты"})
_LOCATION_WORDS = frozenset({"locations", "location", "stores", "store-locator",
                             "storelocator", "find-a-store", "магазини", "адреси", "філії"})
_PERSON_WORDS = frozenset({"team", "author", "people", "staff", "команда"})


class PageKind(IntEnum):
    """Порядок значень — це і є пріоритет краулу: менше тягнеться раніше."""

    HOME = 0
    TELLING = 1
    ORDINARY = 2
    ARCHIVE = 3
    # Та сама сторінка під іншим кутом. Окремий вид, а не архів: таких
    # адрес буває більше, ніж усіх справжніх сторінок разом, і одна з
    # них уже прочитана — це вона й є.
    FACET = 4
    BOILERPLATE = 5


def _normalise_path_chunk(chunk: str) -> str:
    """Один сегмент шляху у вигляді, придатному для звіряння зі словником.

    Адреса подорожує закодованою. `/de/über-uns` і `/de/%C3%BCber-uns` — та
    сама сторінка, але до словника доходив другий запис, і жодне неанглійське
    слово в ньому не збігалося: двигун бачив `%c3%bcber`. Словник при цьому
    був правильний — не збігалося подання.

    Порядок кроків не довільний:

    **Спершу ділимо шлях по `/`, і лише потім декодуємо.** `%2F` усередині
    сегмента — це дані, а не межа маршруту. Декодувати шлях цілком означало б
    вигадати сегмент, якого в адресі немає: `/de/a%2Fb` стало б двома теками,
    і глибина розділу поїхала б разом із типом сторінки.

    **`unquote`, а не `unquote_plus`.** Плюс у ШЛЯХУ — це плюс. Пробілом він
    буває лише у формі, закодованій у query, і переносити те правило сюди
    означало б ламати адреси, де плюс є частиною назви.

    **`errors="replace"`.** Обірване чи бите екранування (`%`, `%zz`, `%C3`)
    не сміє ані валити класифікацію, ані випадково скластися в слово
    словника: U+FFFD не дорівнює нічому.

    **NFC.** Та сама буква має два записи: `ü` буває одним символом, а буває
    `u` плюс комбінований умляут. Поки їх не звести до одного вигляду,
    половина німецьких адрес не збігається зі словником, який написаний
    першим.

    Нижній регістр лишається останнім і лишається `lower()`. Саме останнім:
    `%C3%9C` — це `Ü`, і опустити регістр ДО декодування означало б опустити
    його в шістнадцяткових цифрах, а не в букві. `casefold()` не беремо — він
    ширший (німецьке `ß` стало б `ss`), а доказів, що це комусь потрібно, у
    нас немає.
    """
    return unicodedata.normalize("NFC", unquote(chunk, encoding="utf-8", errors="replace")).lower()


def _route_chunks(url: str, locales: Iterable[str] = ()) -> tuple[list[str], str | None, Basis]:
    """Сегменти шляху без мовного префікса — і чому його знято або лишено.

    Знімається РІВНО ОДИН провідний сегмент і лише тоді, коли він є мовою
    запуску, яку оголосив сам сайт. `/de/de/x` втратить один `de`, а не
    обидва: другий уже частина маршруту, а не мовний префікс.

    Сегменти нормалізуються поштучно (`_normalise_path_chunk`) — уже після
    поділу по `/`, щоб `%2F` лишився даними всередині сегмента.
    """
    chunks = [_normalise_path_chunk(chunk) for chunk in urlparse(url).path.split("/") if chunk]
    if not chunks or chunks[0] not in SUPPORTED_LOCALES:
        return chunks, None, Basis.NO_LOCALE_SEGMENT
    declared = {str(code).strip().lower() for code in locales}
    if chunks[0] in declared:
        return chunks[1:], chunks[0], Basis.DECLARED_LOCALE
    return chunks, None, Basis.LOCALE_NOT_DECLARED


def _words_of(chunks: list[str]) -> set[str]:
    # Розширення відкидається: `wp-login.php` має дати «login», інакше
    # сторінка входу в адмінку не впізнається й отримує критичну знахідку
    # про noindex, який на ній цілком доречний.
    parts = (chunk.rsplit(".", 1)[0].replace("_", "-") for chunk in chunks)
    return {word for part in parts for word in part.split("-") if word}


def path_words(url: str, locales: Iterable[str] = ()) -> set[str]:
    """Слова шляху окремо, без склеювання.

    Підрядок бреше: у `/legal/ssa-services-terms` є «services», і на
    stripe.com саме через це у вибірку замість цін потрапляли дванадцять
    сторінок договорів.

    `locales` — мови, які сайт оголосив про себе. Порожньо означає «нічого не
    оголошено», і тоді жоден сегмент не знімається: саме цим `/de/folder` на
    одномовному сайті відрізняється від `/de/preise` на двомовному.
    """
    chunks, _locale, _basis = _route_chunks(url, locales)
    return _words_of(chunks)


def path_depth(url: str) -> int:
    """Скільки сегментів у шляху.

    Розрізнювач усередині одного виду: `/contacts` і `/product/moon-cake`
    обидва щось стверджують про компанію, але перша сторінка на сайті
    одна, а других буває сотня. Без цього краул на магазині читав пʼять
    карток печива й жодного разу — контакти.
    """
    return len([chunk for chunk in urlparse(url).path.split("/") if chunk])


def is_safe_topic_section(segment: str) -> bool:
    """Чи можна показати цей сегмент клієнтові як назву теми.

    Питання саме таке, і воно вужче, ніж «чи це маршрут». Ми не знаємо,
    як влаштована чужа CMS, і стверджувати про сегмент, що він
    маршрутизація, не маємо підстав: `/911/` цілком може бути серією
    автомобілів, `/360/` — лінійкою продуктів, `/24/` — цілодобовою
    послугою. Числовий сегмент буває і датою, і назвою.

    Тому відповідь тут — не про сайт, а про НАШУ впевненість: чи досить
    у нас доказів, щоб назвати це темою вголос.

    **Недостатньо** для такого твердження:

    - суцільні цифри. `/2024/05/31/slug/` і `/911/carrera` з адреси не
      розрізнити, а сказати власникові «сторінки вашої теми „2024“ не
      повʼязані» — це назвати темою рік;
    - один латинський символ. У корпусі night3 таких сегментів девʼять
      різних, і всі девʼять виявились скороченням маршруту
      (`/c/gin-company/…`, `/v/552089`, `/i/das-sind-wir`). Девʼять
      спостережень — це не закон, але й підстав називати темою літеру
      теж немає.

    **Достатньо**: сегмент із назви — `blog`, `products`,
    `featured-cases`. І один НЕлатинський символ теж: у китайській,
    японській та корейській один ієрогліф — повне слово, тобто цілком
    можлива назва розділу. Доказів про такі сегменти немає жодного (у
    корпусі їх нуль), а правило, виведене з латиниці й застосоване до
    ієрогліфа, мовчки викинуло б справжню тему.

    Сторінка, чий сегмент не пройшов, не зникає: вона групується за
    типом сторінки. Ми відмовляємось лише від твердження про тему, а не
    від самої сторінки.
    """
    chunk = (segment or "").strip().lower()
    if not chunk:
        return False
    if chunk.isdigit():
        return False
    if len(chunk) == 1 and chunk.isascii():
        return False
    return True


def section_of(url: str) -> str:
    """Перший сегмент шляху — розділ, до якого сайт сам віднiс сторінку.

    Не класифікація, а прочитане рішення власника: `/blog/how-it-works` і
    `/blog/pricing-guide` лежать в одному розділі, бо їх туди поклали.
    Для теми це надійніше за здогад із адреси — розділ не треба вгадувати.
    """
    chunks = [chunk for chunk in urlparse(url).path.split("/") if chunk]
    return chunks[0].lower() if len(chunks) > 1 else ""


def kind_of(url: str, title: str = "") -> PageKind:
    parsed = urlparse(url)
    words = path_words(url)

    if not words:
        # Порожній шлях із параметрами — не головна, а її варіант: та сама
        # сторінка, відсортована інакше. Без цієї умови вісім сортувань
        # каталогу отримували найвищий пріоритет і з'їдали весь бюджет,
        # лишаючи магазин без сторінки контактів.
        return PageKind.FACET if parsed.query else PageKind.HOME

    if _is_facet(parsed.query):
        return PageKind.FACET
    if words & BOILERPLATE_WORDS:
        return PageKind.BOILERPLATE
    # Службове важливіше за архівне: `/blog/pricing-guide` — стаття, але
    # `/pricing` під розділом новин трапляється рідше, ніж навпаки.
    if words & TELLING_WORDS or _title_words(title) & TELLING_WORDS:
        return PageKind.TELLING
    if words & ARCHIVE_WORDS:
        return PageKind.ARCHIVE
    return PageKind.ORDINARY


def type_of(
    url: str,
    title: str = "",
    schema_types: Iterable[str] = (),
    locales: Iterable[str] = (),
) -> PageType:
    """Що це за сторінка. Джерела за спаданням надійності.

    Спершу розмітка: якщо сайт сам заявив Product або BlogPosting, це
    твердження сайту, а не наш здогад із адреси. Типи, які ставлять на всі
    сторінки поспіль (WebPage, Organization), відкидаються — з них про тип
    сторінки не дізнатися нічого.

    Далі шлях, і в ньому важливий порядок: службове й юридичне
    визначаються першими, бо `/legal/services-terms` — це договір, а не
    сторінка послуг.

    Повертається сам тип: на ньому тримаються всі наявні правила. Кому
    потрібна ще й підстава висновку — `classify`.
    """
    return classify(url, title, schema_types, locales).page_type


def classify(
    url: str,
    title: str = "",
    schema_types: Iterable[str] = (),
    locales: Iterable[str] = (),
) -> Classification:
    """Тип сторінки разом із тим, що сталося з її мовним префіксом."""
    chunks, locale, basis = _route_chunks(url, locales)
    return Classification(
        page_type=_type_from(url, chunks, _words_of(chunks), title, schema_types),
        locale=locale,
        basis=basis,
    )


def _type_from(
    url: str,
    chunks: list[str],
    words: set[str],
    title: str,
    schema_types: Iterable[str],
) -> PageType:
    if not words:
        # Шлях, від якого після зняття оголошеної мови не лишилось нічого, —
        # це головна тієї мовної версії. `/de` при оголошеній німецькій —
        # та сама сторінка, що й `/`, і судити її треба так само.
        return PageType.HOME

    # Документація визначається першою, і за хостом теж. Інакше
    # `docs.stripe.com/payments/checkout` через слово «checkout» стає
    # сторінкою кошика, а `/docs/joining-your-team` — статтею, від якої
    # ми вимагаємо автора й дату.
    if _is_documentation(url, words):
        return PageType.DOCS

    if words & _SYSTEM_WORDS:
        return PageType.SYSTEM
    if words & _LEGAL_WORDS:
        return PageType.LEGAL

    for raw in schema_types:
        found = _SCHEMA_TYPES.get(str(raw).strip().lower())
        if found is not None:
            return found

    # Пагінація йде першою: `/blog/page/2` — це стрічка з іншого місця, а
    # не стаття, хоч і лежить під розділом статей.
    if _is_pagination(chunks) or words & _ARCHIVE_WORDS:
        return PageType.ARCHIVE
    # Сторінка всередині розділу статей — стаття; сам розділ — архів.
    if words & _ARTICLE_SECTIONS:
        return PageType.ARTICLE if _below_section(chunks, _ARTICLE_SECTIONS) else PageType.ARCHIVE
    if words & _CASE_WORDS:
        return PageType.CASE_STUDY
    if words & _LOCATION_WORDS:
        return PageType.LOCATION
    if words & _CONTACT_WORDS:
        return PageType.CONTACT
    if words & _PERSON_WORDS and _below_section(chunks, _PERSON_WORDS):
        return PageType.PERSON
    if words & _ABOUT_WORDS:
        return PageType.ABOUT
    if words & _PRODUCT_WORDS and _below_section(chunks, _PRODUCT_WORDS):
        return PageType.PRODUCT
    if words & _LISTING_WORDS:
        return PageType.LISTING
    if words & _SERVICE_WORDS:
        return PageType.SERVICE

    title_words = _title_words(title)
    if title_words & _CONTACT_WORDS:
        return PageType.CONTACT
    if title_words & _LOCATION_WORDS:
        return PageType.LOCATION
    return PageType.OTHER


def _is_documentation(url: str, words: set[str]) -> bool:
    """Довідка, посібник, API-референс — за розділом або за піддоменом."""
    host = urlparse(url).netloc.lower()
    return bool(words & _DOCS_SECTIONS) or host.startswith(("docs.", "developers.", "developer."))


def _is_pagination(chunks: list[str]) -> bool:
    """`/page/2`, `/p/3` — та сама стрічка з іншого місця.

    Приймає вже нарізані сегменти, а не адресу: після зняття оголошеної мови
    рахувати треба саме маршрут, інакше `/de/page/2` мав би на сегмент більше,
    ніж `/page/2`, і глибина розділу поїхала б на одиницю.
    """
    return any(
        chunk in ("page", "p", "storinka") and index + 1 < len(chunks)
        and chunks[index + 1].isdigit()
        for index, chunk in enumerate(chunks)
    )


def _below_section(chunks: list[str], section: frozenset[str]) -> bool:
    """Чи є під розділом ще щось. `/blog` — перелік, `/blog/стаття` — ні."""
    for index, chunk in enumerate(chunks):
        if {w for w in chunk.replace("_", "-").split("-") if w} & section:
            return index < len(chunks) - 1
    return False


def _is_facet(query: str) -> bool:
    """Чи це та сама сторінка під іншим кутом.

    Дивимось лише на відомі параметри: `?id=12` на старих сайтах — це
    справжня сторінка, і демоутити всі адреси з параметрами означало б
    їх утратити.
    """
    if not query:
        return False
    names = {pair.split("=", 1)[0].lower() for pair in query.split("&") if pair}
    return bool(names & FACET_PARAMS)


def _title_words(title: str) -> set[str]:
    return {w.strip(",.:;!?«»\"'") for w in title.lower().split()}


__all__ = [
    "ARCHIVE_WORDS",
    "BOILERPLATE_WORDS",
    "CONTENT_IS_NOT_PROSE",
    "EXPECTS_AUTHORSHIP",
    "FACET_PARAMS",
    "NOT_FOR_SEARCH",
    "SUPPORTED_LOCALES",
    "TELLING_WORDS",
    "Basis",
    "Classification",
    "PageKind",
    "PageType",
    "classify",
    "is_safe_topic_section",
    "kind_of",
    "path_depth",
    "path_words",
    "type_of",
]
