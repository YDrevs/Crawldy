"""Факти для прогону присутності — з того, що аудит уже прочитав.

## Навіщо

Прогін присутності потребує бренду, категорії й міста, і досі їх вписувала
людина. Клієнт разової покупки вводить лише адресу сайту — тож або
факти виводяться з аудиту, або присутність для нього не існує. Рішення
власника 2026-09-06: виводити всі три й показувати з можливістю змінити.

Три, а не два — не дрібниця. Без міста пʼятнадцять питань стосуються
«стоматологічних клінік» узагалі, і клініку з райцентру асистент не
назве майже ніколи: число буде технічно правильним і по суті хибним,
бо міряє не той ринок. З чужим містом — та сама помилка з іншого боку
(Ка-Дент із Кам'янця питали про Київ).

## Звідки береться кожен факт, у порядку довіри

- **бренд** — назва організації з розмітки (`Organization.name`); без неї
  — сегмент заголовка головної, найближчий до мітки домену; без нього —
  сама мітка домену;
- **варіанти написання** — бренд, бренд без дефіса й через пробіл,
  транслітерація українського написання латиницею, мітка домену. Збіг у
  тлумаченні вимагає точного слова, і відповідь кирилицею проти
  латинської назви давала б нуль згадок;
- **категорія** — тип бізнесу з розмітки (`Dentist`, `Restaurant`, …),
  інакше сегмент заголовка головної, що не є ані брендом, ані містом;
- **місто** — перше з тих, що аудит знайшов у розмітці адреси чи в
  сталих зворотах тексту («у місті Х», «м. Х»).

Кожен факт несе джерело: клієнт бачить, звідки ми це взяли, і виправляє
те, що взяли неправильно. Порожнє поле чесніше за вигадане — коли
джерела немає, факт лишається порожнім і форма просить його ввести.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from urllib.parse import urlsplit

# Роздільники заголовка: «Бренд — Місто», «Бренд | Категорія», «Бренд: слоган».
_TITLE_SPLIT = re.compile(r"\s+[—–|·]\s+|\s+-\s+|\s*:\s+")

# Типи schema.org, які називають бізнес. Ключ — тип, значення — категорія
# двома мовами. Перелік короткий навмисно: лише те, що справді трапляється
# в малому бізнесі; невідомий тип падає на заголовок, а не на здогад.
_BUSINESS_TYPES: dict[str, dict[str, str]] = {
    "Dentist": {"uk": "стоматологічна клініка", "en": "dental clinic"},
    "MedicalClinic": {"uk": "медична клініка", "en": "medical clinic"},
    "Physician": {"uk": "лікар", "en": "physician"},
    "Restaurant": {"uk": "ресторан", "en": "restaurant"},
    "Cafe": {"uk": "кавʼярня", "en": "cafe"},
    "Bakery": {"uk": "пекарня", "en": "bakery"},
    "Hotel": {"uk": "готель", "en": "hotel"},
    "LawFirm": {"uk": "юридична фірма", "en": "law firm"},
    "Attorney": {"uk": "адвокат", "en": "attorney"},
    "AutoRepair": {"uk": "автосервіс", "en": "auto repair"},
    "BeautySalon": {"uk": "салон краси", "en": "beauty salon"},
    "HairSalon": {"uk": "перукарня", "en": "hair salon"},
    "RealEstateAgent": {"uk": "агентство нерухомості", "en": "real estate agency"},
    "Plumber": {"uk": "сантехнік", "en": "plumber"},
    "Electrician": {"uk": "електрик", "en": "electrician"},
    "VeterinaryCare": {"uk": "ветеринарна клініка", "en": "veterinary clinic"},
    "Pharmacy": {"uk": "аптека", "en": "pharmacy"},
    "Store": {"uk": "магазин", "en": "store"},
    "SoftwareApplication": {"uk": "програмний продукт", "en": "software"},
}

# Транслітерація української латиницею (постанова КМУ № 55 від 2010 р.).
# Лише в один бік: зворотна неоднозначна, і вигаданий кириличний варіант
# латинського бренду гірший за його відсутність.
_UA_LATIN: dict[str, str] = {
    "а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e",
    "є": "ie", "ж": "zh", "з": "z", "и": "y", "і": "i", "ї": "i", "й": "i",
    "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ю": "iu", "я": "ia", "ь": "", "'": "", "’": "",
}
_UA_LATIN_INITIAL: dict[str, str] = {"є": "ye", "ї": "yi", "й": "y", "ю": "yu", "я": "ya"}
_CYRILLIC = re.compile(r"[а-яіїєґ]", re.IGNORECASE)

# Слова заголовка, які не називають бізнес. «Welcome to Python.org» дає
# сегмент «welcome to», і без цього списку він ставав би категорією.
_TITLE_NOISE = frozenset({
    "welcome", "to", "the", "home", "homepage", "official", "site", "website",
    "page", "головна", "сторінка", "офіційний", "сайт", "вітаємо",
})


@dataclass(frozen=True, slots=True)
class DerivedFacts:
    """Пропозиція для форми прогону. Кожне поле може бути порожнім."""

    brand: str
    brand_aliases: tuple[str, ...]
    category: str
    location: str | None
    language: str
    # Звідки взято кожен непорожній факт: brand / category / location.
    sources: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> dict[str, object]:
        return {
            "brand": self.brand,
            "brand_aliases": list(self.brand_aliases),
            "category": self.category,
            "location": self.location,
            "language": self.language,
            "sources": dict(self.sources),
        }


def domain_label(origin: str) -> str:
    """Перша мітка хоста без www: `ka-dent` для `https://ka-dent.com.ua`."""
    host = (urlsplit(origin).hostname or origin).lower().removeprefix("www.")
    return host.split(".", 1)[0] if host else ""


def transliterate(text: str) -> str:
    """Українське написання латиницею; латиниця й цифри лишаються як є."""
    out: list[str] = []
    for i, ch in enumerate(text):
        lower = ch.lower()
        at_start = i == 0 or not text[i - 1].isalpha()
        mapped = _UA_LATIN_INITIAL.get(lower) if at_start else None
        if mapped is None:
            mapped = _UA_LATIN.get(lower)
        if mapped is None:
            out.append(ch)
            continue
        out.append(mapped.capitalize() if ch.isupper() and mapped else mapped)
    return "".join(out)


def _fold_word(value: str) -> str:
    return re.sub(r"[^a-z0-9а-яіїєґ]", "", value.casefold())


def _same_word(a: str, b: str) -> bool:
    return _fold_word(a) == _fold_word(b)


def _title_segments(title: str) -> list[str]:
    return [seg.strip() for seg in _TITLE_SPLIT.split(title) if seg and seg.strip()]


_GERMAN = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _plain_forms(text: str) -> tuple[str, str]:
    """Два «голі» написання: без діакритики і з німецьким розгортанням.

    Домен пишеться без наголосів і умлаутів, заголовок — з ними:
    «Clínica Sol» проти `clinicasol`, «Müller» проти `mueller` або
    `muller`. Прибирати не-ASCII літери цілком, як робив перший варіант,
    означало порівнювати «clnicasol» із «clinicasol» і не знаходити бренд
    у власному заголовку.
    """
    folded = transliterate(text).casefold()
    german = folded.translate(_GERMAN)
    stripped = unicodedata.normalize("NFKD", folded)
    stripped = "".join(ch for ch in stripped if not unicodedata.combining(ch))
    german = unicodedata.normalize("NFKD", german)
    german = "".join(ch for ch in german if not unicodedata.combining(ch))
    return _ascii_only(stripped), _ascii_only(german)


def _ascii_only(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value)


def _plain(text: str) -> str:
    return _plain_forms(text)[0]


def _brand_in_segment(segment: str, label: str) -> str | None:
    """Бренд усередині сегмента заголовка — за міткою домену.

    «Стоматологічна клініка Ка-Дент» містить і категорію, і бренд;
    брендом є найкоротший ряд сусідніх слів, який збігається з міткою
    домену (`ka-dent`), — а не весь сегмент. Точний збіг сильніший за
    входження: «Python.org» для мітки `python` береться цілим словом.
    """
    if not label:
        return None
    plain_label = _plain(label)
    if not plain_label:
        return None
    tokens = segment.split()
    # (ранг, покриття, текст). Ранг: точний збіг → мітка всередині слів →
    # слова всередині мітки. У третьому випадку кращий той ряд, що
    # покриває БІЛЬШЕ мітки: для `zahnarzt-mueller` «Zahnarzt Müller»
    # правильніший за саме «Zahnarzt», хоч обидва в мітці містяться.
    best: tuple[int, int, str] | None = None
    for width in (1, 2, 3):
        for start in range(0, len(tokens) - width + 1):
            run = " ".join(tokens[start:start + width])
            forms = [f for f in _plain_forms(run) if f]
            if not forms:
                continue
            rank: int | None = None
            coverage = 0
            for folded in forms:
                if folded == plain_label:
                    rank, coverage = 0, len(folded)
                    break
                if plain_label in folded and len(folded) <= len(plain_label) + 4:
                    rank, coverage = 1, -len(folded)
                elif folded in plain_label and len(folded) >= 4 and rank is None:
                    rank, coverage = 2, len(folded)
            if rank is None:
                continue
            key = (rank, -coverage, run)
            if best is None or key[:2] < best[:2]:
                best = key
    return best[2].strip(" ,.-—–") if best else None


def _matches_domain(segment: str, label: str) -> bool:
    return _brand_in_segment(segment, label) is not None


def _names_city(segment: str, city: str) -> bool:
    """Чи сегмент — це місто, з допуском на різницю в одній літері.

    Заголовок пише «Подільский», розмітка — «Подільський»; порівняння
    рівно по першій частині назви («Кам'янець») ловить обидва.
    """
    head = re.split(r"[\s-]", city.strip())[0].casefold()
    return len(head) >= 4 and head in segment.casefold()


def _aliases(brand: str, origin: str) -> tuple[str, ...]:
    variants: list[str] = []

    def add(value: str) -> None:
        # Збіг у тлумаченні нечутливий до регістру, тож «ka-dent» поруч
        # із «Ka-Dent» нічого не додає — лишається перше написання.
        value = value.strip()
        if len(value) >= 2 and value.casefold() not in {v.casefold() for v in variants}:
            variants.append(value)

    add(brand)
    if "-" in brand:
        add(brand.replace("-", " "))
        add(brand.replace("-", ""))
    if _CYRILLIC.search(brand):
        latin = transliterate(brand)
        add(latin)
        if "-" in latin:
            add(latin.replace("-", " "))
            add(latin.replace("-", ""))
    label = domain_label(origin)
    if label and not label.isdigit():
        add(label)
        if "-" in label:
            add(label.replace("-", ""))
    return tuple(variants[:10])


def derive(
    *,
    origin: str,
    home_title: str,
    organization: str = "",
    cities: tuple[str, ...] | list[str] = (),
    schema_types: dict[str, int] | None = None,
    lang: str = "",
) -> DerivedFacts:
    """Пропозиція фактів прогону з того, що аудит уже прочитав."""
    language = "uk" if (lang or "").lower().startswith("uk") else "en"
    sources: dict[str, str] = {}
    label = domain_label(origin)
    segments = _title_segments(home_title)
    city = next((c for c in cities if c.strip()), None)

    # ── бренд ──────────────────────────────────────────────────────────
    # Написання з заголовка потрібне навіть коли є назва з розмітки: сайт
    # може називати себе «СмартКП» у розмітці й «SmartKP» у заголовку, і
    # обидва написання мають бути серед варіантів збігу.
    title_brand = next(
        (found for seg in segments if (found := _brand_in_segment(seg, label))), ""
    )
    brand = organization.strip()
    if brand:
        sources["brand"] = "schema"
    elif title_brand:
        brand = title_brand
        sources["brand"] = "title"
    elif label:
        brand = label.replace("-", " ").title()
        sources["brand"] = "domain"

    # ── місто ──────────────────────────────────────────────────────────
    if city:
        sources["location"] = "site"

    # ── категорія ──────────────────────────────────────────────────────
    category = ""
    for schema_type, names in _BUSINESS_TYPES.items():
        if (schema_types or {}).get(schema_type):
            category = names[language]
            sources["category"] = "schema"
            break
    if not category:
        for seg in segments:
            if city and _names_city(seg, city):
                continue
            # Сегмент може містити і категорію, і бренд: «Стоматологічна
            # клініка Ка-Дент». Бренд вирізається, решта — категорія.
            text = seg
            for spelling in (brand, title_brand):
                if spelling:
                    text = re.sub(re.escape(spelling), "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s+", " ", text).strip(" ,.-—–")
            if not text or _same_word(text, brand):
                continue
            words = [w for w in re.split(r"[^\wʼ'’-]+", text.casefold()) if w]
            if not words or all(w in _TITLE_NOISE for w in words):
                continue
            if 3 <= len(text) <= 60:
                lead = text[:1]
                category = (
                    lead.lower() + text[1:]
                    if lead.isupper() and not text[:2].isupper()
                    else text
                )
                sources["category"] = "title"
                break

    aliases: list[str] = list(_aliases(brand, origin)) if brand else []
    if title_brand and title_brand.casefold() not in {a.casefold() for a in aliases}:
        for variant in _aliases(title_brand, origin):
            if variant.casefold() not in {a.casefold() for a in aliases}:
                aliases.append(variant)

    return DerivedFacts(
        brand=brand,
        brand_aliases=tuple(aliases[:10]),
        category=category,
        location=city,
        language=language,
        sources=sources,
    )


__all__ = ["DerivedFacts", "derive", "domain_label", "transliterate"]
