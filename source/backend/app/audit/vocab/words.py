"""Самі словники: слово → поняття, по мові.

Дані, не логіка. Розділені навмисно: додати мову має бути правкою одного
файла з рядками, яку може зробити перекладач, а не зміною коду.

**Порожній словник — це не помилка, а факт.** Мова, оголошена й не
заповнена, означає, що сайти нею ми впізнаємо гірше, ніж англомовні; це
видно через `vocab.coverage()` і зафіксовано тестом. Приховати це,
підсунувши англійські слова як заглушку, було б гірше за порожнечу:
`/preise` не схоже на `pricing` жодною буквою, і фальшиве покриття лише
відклало б виявлення проблеми.

Транслітерації живуть у тій самій мові, що й оригінал: `tsiny` — це
українське слово латиницею, а не окрема мова. Так їх пише половина
українських CMS, і не впізнавати їх означало б не впізнавати половину
українських сайтів.
"""

from __future__ import annotations

from app.audit.vocab.enums import Concept, ContentLanguage
from app.audit.vocab.enums import Concept as C
from app.audit.vocab.enums import ContentLanguage as L


def _build() -> dict[ContentLanguage, dict[Concept, frozenset[str]]]:
    table: dict[L, dict[C, frozenset[str]]] = {language: {} for language in L}

    table[L.EN] = {
        C.TELLING: frozenset({
            "contact", "contacts", "about", "company", "about-us", "team",
            "pricing", "price", "prices", "tariff", "tariffs",
            "services", "service", "products", "product", "shop", "store",
            "catalog", "catalogue",
            "locations", "location", "stores", "store-locator", "storelocator",
            "find-a-store",
        }),
        C.ARCHIVE: frozenset({
            "blog", "news", "article", "articles", "post", "posts", "stories",
            "press", "tag", "tags", "category", "categories", "archive",
            "author", "page", "feed",
        }),
        C.BOILERPLATE: frozenset({
            "legal", "terms", "tos", "privacy", "policy", "policies", "cookie",
            "cookies", "gdpr", "dpa", "license", "licence", "disclaimer", "eula",
            "cart", "checkout", "my-account", "wishlist", "compare",
        }),
        C.CALL_TO_ACTION: frozenset({
            "contact", "contacts", "quote", "request", "book", "booking", "order",
            "buy", "cart", "checkout", "signup", "register", "demo", "trial",
            "pricing", "prices", "consultation",
        }),
        C.CALL_TO_ACTION_TEXT: frozenset({
            "book", "buy", "order", "get started", "get a quote", "request a",
            "contact us", "sign up", "start free", "try free", "add to cart",
            "talk to", "schedule a",
        }),
    }

    table[L.UK] = {
        C.TELLING: frozenset({
            "контакти", "контакт", "kontakt", "kontakty", "kontakti",
            "про-нас", "pro-nas", "команда",
            "ціни", "cini", "тарифи", "послуги", "poslugy", "poslugi",
            "каталог", "магазини", "адреси", "філії",
        }),
        C.ARCHIVE: frozenset({"новини", "novyny"}),
        C.BOILERPLATE: frozenset({"оферта", "конфіденційності"}),
        C.CALL_TO_ACTION: frozenset({
            "контакти", "замовити", "zamovyty", "zamovlennya", "kupyty", "kupiti",
            "koshyk",
        }),
        #: «придба» додано за виміряним випадком: підпис «Придбати пакет» не
        #: збігався з жодним записом, тоді як англійське «Buy the pack» і
        #: російське «Купить пакет» збігались — та сама сторінка, різний вирок.
        C.CALL_TO_ACTION_TEXT: frozenset({
            "замов", "купуй", "придба", "зателефон", "подзвон",
            "звʼяж", "зв'яж", "звяж", "залиш заявку", "отримати консультац",
            "написати нам", "у кошик", "в кошик",
        }),
    }

    # Німецька, іспанська, французька й російська — мови запуску. Заповнені
    # рівно ті поняття, які читає `page_kinds`: TELLING, ARCHIVE, BOILERPLATE.
    #
    # `CALL_TO_ACTION` (слова АДРЕСИ) лишається порожнім для цих чотирьох, як і
    # було: його читає `checks/conversion.py`, і розширення зсунуло б
    # `cro.no_action` на сайтах, яких E-12 не стосується.
    #
    # `CALL_TO_ACTION_TEXT` (підписи посилань і кнопок) заповнено навмисно —
    # саме його порожнеча й була дефектом. Підпис «Придбати пакет» не збігався
    # ні з чим, тоді як «Buy the pack» і «Купить пакет» збігались, і та сама
    # сторінка отримувала різний вирок залежно від мови підпису. Перелік
    # словником, а не кортежем у чеку: додати мову має бути правкою рядків.
    #
    # Покриття мови це не применшує: `covered()` питає «чи є хоч одне слово»,
    # а не «чи заповнені всі поняття».
    #
    # Слова — ОДНОСЛІВНІ. `path_words` ріже сегмент по дефісах, тож запис на
    # кшталт `ueber-uns` не збігся б ніколи: у множині лежать `ueber` і `uns`
    # окремо. З тієї ж причини сюди не потрапляють надто загальні токени
    # (`uns`, `nos`), які в чужій мові трапляються самі по собі.

    table[L.DE] = {
        C.TELLING: frozenset({
            "kontakt", "kontakte", "ueber", "über", "unternehmen",
            "preise", "preis", "preisliste", "tarife",
            "leistungen", "dienstleistungen", "produkte",
            "katalog", "filialen", "standorte", "standort",
        }),
        C.ARCHIVE: frozenset({
            "nachrichten", "neuigkeiten", "presse", "artikel",
            "kategorie", "kategorien", "archiv",
        }),
        C.BOILERPLATE: frozenset({
            "impressum", "datenschutz", "agb", "nutzungsbedingungen",
            "widerruf", "warenkorb", "kasse", "konto",
        }),
        C.CALL_TO_ACTION_TEXT: frozenset({
            "kaufen", "bestellen", "jetzt buchen", "in den warenkorb",
            "kontakt aufnehmen", "angebot anfordern", "kostenlos testen",
            "termin vereinbaren",
        }),
    }

    table[L.ES] = {
        C.TELLING: frozenset({
            "contacto", "contactos", "nosotros", "empresa", "equipo",
            "precios", "precio", "tarifas", "servicios", "servicio",
            "productos", "producto", "tienda", "tiendas", "catalogo",
            "catálogo", "ubicaciones",
        }),
        C.ARCHIVE: frozenset({
            "noticias", "articulos", "artículos", "prensa",
            "categoria", "categoría", "categorias", "archivo",
        }),
        C.BOILERPLATE: frozenset({
            "privacidad", "terminos", "términos", "condiciones",
            "carrito", "pago", "cuenta",
        }),
        C.CALL_TO_ACTION_TEXT: frozenset({
            "comprar", "solicitar", "contactar", "contáctenos",
            "añadir al carrito", "reservar", "pedir presupuesto",
            "empezar gratis",
        }),
    }

    table[L.FR] = {
        C.TELLING: frozenset({
            "contacts", "propos", "entreprise", "equipe", "équipe",
            "tarifs", "tarif", "prix", "produits", "boutique",
            "magasins", "adresses",
        }),
        C.ARCHIVE: frozenset({
            "actualites", "actualités", "nouvelles", "presse",
            "categorie", "catégorie", "archives", "auteur",
        }),
        C.BOILERPLATE: frozenset({
            "mentions", "legales", "légales", "confidentialite",
            "confidentialité", "cgv", "cgu", "panier", "commande", "compte",
        }),
        #: «commander» сюди НЕ входить, хоч це й природне французьке «замовити».
        #: Підпис зіставляється і входженням, а не лише початком рядка, тож воно
        #: збігалося з англійським іменником: на `en.ponant.com` кнопка «The
        #: Commander Charcot…» (назва судна) ставала закликом до дії й гасила
        #: `cro.no_action`. Виміряно на канонічному корпусі, не припущення. Та
        #: сама межа, що й для `uns`/`nos` вище: надто загальний у чужій мові
        #: токен коштує дорожче за пропущений підпис.
        C.CALL_TO_ACTION_TEXT: frozenset({
            "acheter", "nous contacter", "ajouter au panier",
            "réserver", "demander un devis", "essai gratuit",
        }),
    }

    table[L.RU] = {
        C.TELLING: frozenset({
            "контакты", "контакт", "kontakty", "компания", "компании",
            "kompaniya", "kompanii",
            "цены", "цена", "tseny", "тарифы", "tarify",
            "услуги", "uslugi", "товары", "продукция",
            "магазин", "магазины", "адреса",
        }),
        C.ARCHIVE: frozenset({
            "новости", "novosti", "статьи", "stati", "пресса",
            "категория", "категории", "архив",
        }),
        C.BOILERPLATE: frozenset({
            "политика", "конфиденциальности", "соглашение", "условия",
            "politika", "konfidencialnosti", "soglashenie", "usloviya",
            "корзина", "korzina", "кабинет",
        }),
        C.CALL_TO_ACTION_TEXT: frozenset({
            "купит", "заказат", "закажи", "свяжит", "связат", "позвонит",
            "оставить заявку", "в корзину", "написать нам",
        }),
    }

    # Українська вже покрита; сюди додано лише латиничні написання цін, які
    # E-12 вимагає для `/uk/tsiny`. Половина українських CMS пише саме так,
    # і транслітерація живе в мові оригіналу, а не окремою мовою.
    table[L.UK][C.TELLING] |= frozenset({"tsiny", "tsina"})

    # Решта мов оголошена й порожня. Див. докстрінг модуля: порожньо
    # чесніше за англійські слова під виглядом перекладу.
    return table


VOCABULARIES = _build()

__all__ = ["VOCABULARIES"]


# ── Сторінка «про нас» (E-10) ────────────────────────────────────────────
#
# Окремі таблиці, а не нове поняття в `Concept`: тут лише дані шести мов
# запуску, дослівно з `contracts/e10-signals.json`, і жодне з цих слів не
# розширює жодного наявного поняття. Три види, бо контракт розрізняє три
# питання: чому ДОРІВНЮЄ останній сегмент маршруту (P1), з чого
# ПОЧИНАЄТЬСЯ заголовок або пункт меню (P2, P3), і як виглядає форма
# «Про <бренд>» — де сам бренд бере детектор із фактів сайту.
#
# Синонімів «на око» тут немає навмисно: `/about-cookies`, `aboutique` і
# `team-building-tips` не мають збігатися, а зайве слово в цій таблиці —
# рівно той підрядок, який E-10 і прибирає.

ABOUT_ROUTE_TOKENS: dict[ContentLanguage, frozenset[str]] = {
    L.EN: frozenset({"about", "about-us", "company", "team", "who-we-are"}),
    L.UK: frozenset({"pro-nas", "про-нас", "kompaniya", "komanda", "команда"}),
    L.DE: frozenset({"ueber-uns", "uber-uns", "unternehmen", "team"}),
    L.ES: frozenset({"sobre-nosotros", "quienes-somos", "empresa", "equipo"}),
    L.FR: frozenset({"a-propos", "qui-sommes-nous", "entreprise", "equipe"}),
    L.RU: frozenset({"o-nas", "о-нас", "o-kompanii", "kompaniya", "komanda"}),
}

ABOUT_PHRASES: dict[ContentLanguage, tuple[str, ...]] = {
    L.EN: ("About us", "Our team"),
    L.UK: ("Про нас", "Наша команда"),
    L.DE: ("Über uns", "Unser Team"),
    L.ES: ("Sobre nosotros", "Nuestro equipo"),
    L.FR: ("À propos", "Notre équipe"),
    L.RU: ("О нас", "Наша команда"),
}

# «About <brand>»: префікс, за яким мусить стояти назва самого сайту.
ABOUT_BRAND_PREFIXES: dict[ContentLanguage, tuple[str, ...]] = {
    L.EN: ("About",),
    L.UK: ("Про",),
    L.DE: ("Über",),
    L.ES: ("Sobre",),
    L.FR: ("À propos de",),
    L.RU: ("О",),
}
