"""Каталог клієнтських рядків.

Чек не пише текст — він віддає ключ повідомлення і параметри. Рендер у
конкретну мову відбувається двічі: одразу в канонічну локаль (щоб
`Issue.title` лишався заповненим, як і до i18n), і повторно в шарі звіту
чи API, коли клієнт просить іншу мову.

## Канонічна мова — англійська

`DEFAULT_LOCALE` і `FALLBACK_LOCALE` — два різні поняття, які довго були
одним, і обидва тепер `en`:

- **дефолт** — мова, коли про читача не відомо нічого;
- **фолбек** — мова, якою підставляється ключ, відсутній у потрібному
  каталозі.

Друге небезпечніше. Поки фолбеком була українська, французький клієнт із
неперекладеним ключем отримував не англійський рядок, а український — і
виглядало це не як прогалина перекладу, а як помилка в продукті.

## Каталоги бувають неповні, і це нормально

Вимагати одинадцяти перекладів у тому ж комміті, що й новий чек, означає
або зупинити розвиток двигуна, або писати переклади абияк. Тому локалі
діляться на **повні** (тест вимагає всіх ключів) і **часткові** (дозволено
фолбек). Часткова мова показується клієнту — просто окремі рядки в ній
англійські.

Щоб прогалини знаходилися самі, а не через скаргу клієнта, `MessageText`
несе мову, якою його **справді** віддали. Порівняння з тією, яку просили,
і є сигналом — без жодного технічного шуму в самому тексті.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from app.audit.i18n import de, en, es, fr, ru, uk
from app.audit.i18n.plural import PLURAL_FORMS, plural_form


class Locale(StrEnum):
    """Мова, якою продукт говорить із людиною.

    Не плутати з мовою сайту, який аудитують: іспанський сайт лишається
    іспанським незалежно від того, якою мовою відкритий інтерфейс. Та
    інша річ живе в `app.audit.vocab.ContentLanguage` і навмисно має інший
    тип, щоб їх не можна було передати одну замість одної.
    """

    EN = "en"
    ES = "es"
    FR = "fr"
    DE = "de"
    PT = "pt"
    UK = "uk"
    RU = "ru"
    PL = "pl"
    AR = "ar"
    HI = "hi"
    ZH = "zh"
    JA = "ja"


# Мова, коли про читача не відомо нічого.
DEFAULT_LOCALE = Locale.EN

# Мова, якою підставляється ключ, відсутній у потрібному каталозі.
#
# Окремо від дефолту навмисно: дефолт можна змінити продуктовим рішенням
# (наприклад, для регіонального запуску), а фолбек — це та мова, якою
# каталог гарантовано повний. Змішати їх означає одного дня віддати
# французу український рядок, як воно тут і було.
FALLBACK_LOCALE = Locale.EN


@dataclass(frozen=True, slots=True)
class LocaleInfo:
    """Що продукт знає про мову."""

    code: Locale
    english_name: str
    native_name: str
    rtl: bool = False
    # Чи вимагається від каталогу повнота. Неповна мова працює — просто
    # окремі рядки в ній англійські.
    complete: bool = False

    @property
    def direction(self) -> str:
        return "rtl" if self.rtl else "ltr"


LOCALES: dict[Locale, LocaleInfo] = {
    Locale.EN: LocaleInfo(Locale.EN, "English", "English", complete=True),
    Locale.ES: LocaleInfo(Locale.ES, "Spanish", "Español", complete=True),
    Locale.FR: LocaleInfo(Locale.FR, "French", "Français", complete=True),
    Locale.DE: LocaleInfo(Locale.DE, "German", "Deutsch", complete=True),
    Locale.PT: LocaleInfo(Locale.PT, "Portuguese", "Português"),
    Locale.UK: LocaleInfo(Locale.UK, "Ukrainian", "Українська", complete=True),
    Locale.RU: LocaleInfo(Locale.RU, "Russian", "Русский", complete=True),
    Locale.PL: LocaleInfo(Locale.PL, "Polish", "Polski"),
    Locale.AR: LocaleInfo(Locale.AR, "Arabic", "العربية", rtl=True),
    Locale.HI: LocaleInfo(Locale.HI, "Hindi", "हिन्दी"),
    Locale.ZH: LocaleInfo(Locale.ZH, "Chinese", "中文"),
    Locale.JA: LocaleInfo(Locale.JA, "Japanese", "日本語"),
}

# Мови, від каталогів яких тест вимагає повноти.
COMPLETE_LOCALES = frozenset(code for code, info in LOCALES.items() if info.complete)

# Поля, які лягають в Issue і зберігаються в БД.
FIELDS = ("title", "description", "recommendation")

# consequence не живе в Issue: він потрібен лише звіту й береться з каталогу
# за msg-ключем. Це пояснення наслідку простою мовою, без жаргону —
# нетехнічна частина звіту складається саме з нього.
CATALOG_FIELDS = (*FIELDS, "consequence")


def allowed_catalog_keys() -> frozenset[str]:
    """Ключі, які може мати запис каталогу: поля та їхні форми множини.

    `title.one`, `title.few` — той самий заголовок для іншої кількості.
    Значення лишаються рядками, тож усе, що обходить `entry.values()`,
    бачить у формах множини звичайні шаблони.
    """
    return frozenset(CATALOG_FIELDS) | frozenset(
        f"{field}.{form}" for field in CATALOG_FIELDS for form in PLURAL_FORMS
    )

CATALOGS: dict[Locale, dict[str, dict[str, str]]] = {
    Locale.UK: uk.MESSAGES,
    Locale.EN: en.MESSAGES,
    Locale.DE: de.MESSAGES,
    Locale.ES: es.MESSAGES,
    Locale.FR: fr.MESSAGES,
    Locale.RU: ru.MESSAGES,
}

# Однорядкові повідомлення домену: чому частина аудиту не виконалась, чому
# запуск повторили. Окремо від знахідок, бо в знахідки чотири поля й свої
# вимоги — наслідок без жаргону, збіг плейсхолдерів, досяжність
# синтетичним контекстом. Один рядок під ті перевірки не підходить.
NOTICES: dict[Locale, dict[str, str]] = {
    Locale.UK: uk.NOTICES,
    Locale.EN: en.NOTICES,
    Locale.DE: de.NOTICES,
    Locale.ES: es.NOTICES,
    Locale.FR: fr.NOTICES,
    Locale.RU: ru.NOTICES,
}

# Каталог тарифів — маркетингова поверхня, а не текст аудиту. Окремо, бо
# до знахідок застосовуються перевірки, придумані не для назв тарифів.
CATALOG: dict[Locale, dict[str, str]] = {
    Locale.UK: uk.CATALOG,
    Locale.EN: en.CATALOG,
    Locale.DE: de.CATALOG,
    Locale.ES: es.CATALOG,
    Locale.FR: fr.CATALOG,
    Locale.RU: ru.CATALOG,
}


def parse(value: str | None) -> Locale | None:
    """Рядок → локаль, або нічого.

    Приймає і `pt-BR`, і `PT_br`: регіон відкидається. Окремих каталогів
    на регіон немає й поки не планується — бразильська й європейська
    португальська різняться, але не настільки, щоб віддавати клієнту
    англійську через дефіс у заголовку.
    """
    if not value:
        return None
    base = value.strip().replace("_", "-").split("-")[0].lower()
    try:
        return Locale(base)
    except ValueError:
        return None


@dataclass(frozen=True, slots=True)
class MessageText:
    """Готовий текст і мова, якою його **справді** віддали.

    `locale` не завжди дорівнює тій, яку просили: у частковому каталозі
    окремі ключі падають в англійську. Різниця між `requested` і `locale`
    і є автоматичним сигналом про прогалину перекладу — без будь-якого
    технічного шуму в самому тексті.
    """

    title: str
    description: str = ""
    recommendation: str = ""
    consequence: str = ""
    locale: Locale = FALLBACK_LOCALE
    requested: Locale = FALLBACK_LOCALE

    @property
    def fell_back(self) -> bool:
        return self.locale is not self.requested


class _SafeParams(dict[str, Any]):
    """Забутий параметр не має валити аудит — лишаємо плейсхолдер видимим."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _format(template: str, params: dict[str, Any]) -> str:
    try:
        return template.format_map(_SafeParams(params))
    except (IndexError, ValueError):
        # Незбалансовані дужки в шаблоні — краще показати сирий текст, ніж впасти.
        return template


def lookup(key: str, locale: Locale) -> tuple[dict[str, str], Locale] | None:
    """Запис каталогу і мова, з якої його взяли.

    Спершу потрібна мова, потім англійська. Третього кроку немає
    навмисно: ланцюжок фолбеків довший за один робить непередбачуваним
    те, якою мовою клієнт побачить рядок.
    """
    entry = CATALOGS.get(locale, {}).get(key)
    if entry is not None:
        return entry, locale
    if locale is not FALLBACK_LOCALE:
        fallback = CATALOGS[FALLBACK_LOCALE].get(key)
        if fallback is not None:
            return fallback, FALLBACK_LOCALE
    return None


def render(
    key: str, params: dict[str, Any] | None = None, locale: Locale = DEFAULT_LOCALE
) -> MessageText:
    found = lookup(key, locale)
    if found is None:
        # Каталог неповний навіть в англійській — це баг, який ловить
        # test_i18n, але звіт має вижити: краще показати ключ, ніж 500.
        return MessageText(title=key, locale=locale, requested=locale)
    entry, actual = found
    values = params or {}
    return MessageText(
        **{f: _format(_field_for_count(entry, f, values, actual), values) for f in CATALOG_FIELDS},
        locale=actual,
        requested=locale,
    )


def _field_for_count(
    entry: dict[str, str], field: str, params: dict[str, Any], locale: Locale
) -> str:
    """Шаблон поля з урахуванням кількості.

    Коли в параметрах є ціле `count` і в записі є форма для його
    категорії (`title.one`, `title.few`…), береться вона. Інакше — базове
    поле, яке за домовленістю є формою `other`. Мова — та, з якої взято
    запис, а не запитана: форми рахуються за граматикою мови тексту.
    """
    count = params.get("count")
    if isinstance(count, bool) or not isinstance(count, int):
        return entry.get(field, "")
    return entry.get(f"{field}.{plural_form(locale.value, count)}", entry.get(field, ""))


def notice(key: str, params: dict[str, Any] | None = None, locale: Locale = DEFAULT_LOCALE) -> str:
    """Однорядкове повідомлення домену потрібною мовою.

    Той самий фолбек, що й у знахідок: потрібна мова, потім англійська.
    Невідомий ключ повертається як є — це видно в звіті й ловиться тестом,
    але звіт не падає.
    """
    template = NOTICES.get(locale, {}).get(key)
    if template is None and locale is not FALLBACK_LOCALE:
        template = NOTICES[FALLBACK_LOCALE].get(key)
    if template is None:
        return key
    return _format(template, params or {})


def catalog(key: str, params: dict[str, Any] | None = None, locale: Locale = DEFAULT_LOCALE) -> str:
    """Рядок каталогу тарифів. Той самий фолбек, що всюди: потрібна → en."""
    template = CATALOG.get(locale, {}).get(key)
    if template is None and locale is not FALLBACK_LOCALE:
        template = CATALOG[FALLBACK_LOCALE].get(key)
    if template is None:
        return key
    return _format(template, params or {})


def missing_catalog(keys: set[str]) -> dict[Locale, set[str]]:
    """Яких рядків каталогу бракує в повних мовах."""
    return {locale: keys - set(CATALOG.get(locale, {})) for locale in COMPLETE_LOCALES}


def missing_notices(keys: set[str]) -> dict[Locale, set[str]]:
    """Яких однорядкових повідомлень бракує в повних каталогах."""
    return {
        locale: keys - set(NOTICES.get(locale, {}))
        for locale in COMPLETE_LOCALES
    }


def missing_keys(keys: set[str], *, complete_only: bool = True) -> dict[Locale, set[str]]:
    """Яких ключів бракує в кожному каталозі.

    За замовчуванням дивиться лише на повні мови — від часткових повнота
    не вимагається, і показувати їхні прогалини як помилку означало б
    робити тест червоним за задумом. `complete_only=False` дає повну
    картину для звіту про покриття.
    """
    catalogs = (
        {loc: cat for loc, cat in CATALOGS.items() if loc in COMPLETE_LOCALES}
        if complete_only
        else {loc: CATALOGS.get(loc, {}) for loc in LOCALES}
    )
    return {locale: keys - set(catalog) for locale, catalog in catalogs.items()}


def coverage(keys: set[str]) -> dict[Locale, float]:
    """Частка перекладених ключів у кожній мові. Для звіту, не для тесту."""
    if not keys:
        return {locale: 1.0 for locale in LOCALES}
    return {
        locale: len(keys & set(CATALOGS.get(locale, {}))) / len(keys) for locale in LOCALES
    }


__all__ = [
    "CATALOG",
    "CATALOGS",
    "CATALOG_FIELDS",
    "COMPLETE_LOCALES",
    "DEFAULT_LOCALE",
    "FALLBACK_LOCALE",
    "FIELDS",
    "LOCALES",
    "NOTICES",
    "PLURAL_FORMS",
    "Locale",
    "LocaleInfo",
    "MessageText",
    "allowed_catalog_keys",
    "catalog",
    "coverage",
    "lookup",
    "missing_catalog",
    "missing_keys",
    "missing_notices",
    "notice",
    "parse",
    "plural_form",
    "render",
]
