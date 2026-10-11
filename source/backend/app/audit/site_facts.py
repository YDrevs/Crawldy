"""Що сайт сказав про себе — зведено з усіх сторінок і без здогадів.

Порядок джерел істини: детерміністичні докази, потім витягнуті факти,
потім зведення по сайту, і аж потім висновок моделі. Модель не повинна
вгадувати те, що краулер уже точно встановив.

Приводом був конкретний і соромний випадок. Звіт по smartkp.com.ua
одночасно стверджував «ніде не вказано, де ви працюєте» і містив у
згенерованому нами ж llms.txt рядок «відеоспостереження в місті
Кам'янець-Подільський». Місто лежало в мета-описі головної, тобто ми
його бачили — просто питали про нього не там.

Зведення робиться до семантичного шару й віддається чеку раніше за
модель. Модель лишається для того, чого в розмітці немає: чи зрозуміло
з тексту, що компанія продає.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.audit.types import PageSignals, SiteContext

# Поля schema.org, у яких лежить адреса.
_ADDRESS_FIELDS = ("streetAddress", "addressLocality", "addressRegion", "postalCode")

# Місто в тексті: «у місті Х», «м. Х», «in Tyler, TX».
_CITY_PATTERNS = (
    re.compile(r"(?:у|в)\s+міст[іе]\s+([А-ЯІЇЄҐ][\w'’-]+(?:-[А-ЯІЇЄҐ][\w'’-]+)*)"),
    re.compile(r"\bм\.\s*([А-ЯІЇЄҐ][\w'’-]+(?:-[А-ЯІЇЄҐ][\w'’-]+)*)"),
    re.compile(r"\bin\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?),\s*[A-Z]{2}\b"),
)


@dataclass(slots=True)
class SiteKnowledge:
    """Факти, зібрані з розмітки й посилань. Жодного висновку моделі."""

    phones: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    cities: list[str] = field(default_factory=list)
    organization: str = ""
    social_profiles: list[str] = field(default_factory=list)
    schema_types: dict[str, int] = field(default_factory=dict)
    pages_total: int = 0
    pages_with_schema: int = 0

    # Де саме кожен факт знайдено. Без цього твердження «це у вас є»
    # неможливо перевірити, а саме воно спростовує знахідку моделі.
    sources: dict[str, str] = field(default_factory=dict)

    @property
    def has_location(self) -> bool:
        return bool(self.addresses or self.cities)

    @property
    def has_contact(self) -> bool:
        return bool(self.phones or self.emails)

    @property
    def schema_coverage(self) -> float:
        """Частка сторінок із розміткою. Саме вона, а не сам факт наявності."""
        return self.pages_with_schema / self.pages_total if self.pages_total else 0.0

    def to_json(self) -> dict[str, Any]:
        return {
            "phones": self.phones,
            "emails": self.emails,
            "addresses": self.addresses,
            "cities": self.cities,
            "organization": self.organization,
            "social_profiles": self.social_profiles,
            "schema_types": self.schema_types,
            "pages_total": self.pages_total,
            "pages_with_schema": self.pages_with_schema,
            "sources": self.sources,
        }


def collect(ctx: SiteContext) -> SiteKnowledge:
    """Зводить факти з усіх прочитаних сторінок."""
    known = SiteKnowledge()
    pages = ctx.ok_pages
    known.pages_total = len(pages)

    for page in pages:
        if page.jsonld:
            known.pages_with_schema += 1
        _from_links(page, known)
        _from_schema(page, known)
        _from_text(page, known)

    for page in pages:
        for node in page.jsonld:
            for raw in _types(node):
                known.schema_types[raw] = known.schema_types.get(raw, 0) + 1

    for name in ("phones", "emails", "addresses", "cities", "social_profiles"):
        setattr(known, name, sorted(dict.fromkeys(getattr(known, name))))
    return known


def _from_links(page: PageSignals, known: SiteKnowledge) -> None:
    for phone in page.tel_links:
        _add(known.phones, phone, known, f"tel: на {page.url}")
    for email in page.mailto_addresses:
        _add(known.emails, email, known, f"mailto: на {page.url}")


def _from_schema(page: PageSignals, known: SiteKnowledge) -> None:
    for node in page.jsonld:
        telephone = node.get("telephone")
        if isinstance(telephone, str):
            _add(known.phones, telephone, known, f"розмітка на {page.url}")
        email = node.get("email")
        if isinstance(email, str):
            _add(known.emails, email, known, f"розмітка на {page.url}")

        address = node.get("address")
        if isinstance(address, dict):
            parts = [str(address[f]) for f in _ADDRESS_FIELDS if address.get(f)]
            if parts:
                _add(known.addresses, ", ".join(parts), known, f"розмітка на {page.url}")
            locality = address.get("addressLocality")
            if isinstance(locality, str) and locality.strip():
                _add(known.cities, locality.strip(), known, f"розмітка на {page.url}")

        same_as = node.get("sameAs")
        if isinstance(same_as, list):
            for link in same_as:
                if isinstance(link, str):
                    _add(known.social_profiles, link, known, f"sameAs на {page.url}")

        if not known.organization and str(node.get("@type", "")).lower() == "organization":
            name = node.get("name")
            if isinstance(name, str) and name.strip():
                known.organization = name.strip()
                known.sources["organization"] = f"розмітка на {page.url}"


def _from_text(page: PageSignals, known: SiteKnowledge) -> None:
    """Місто з мета-опису й тексту.

    Саме тут лежав Кам'янець-Подільський, через якого звіт суперечив сам
    собі. Шукаємо не будь-яку велику літеру, а сталі звороти: «у місті Х»,
    «м. Х», «in Tyler, TX».
    """
    haystack = f"{page.meta_description or ''} {page.text[:2000]}"
    for pattern in _CITY_PATTERNS:
        for match in pattern.finditer(haystack):
            _add(known.cities, match.group(1).strip(), known, f"текст на {page.url}")


def _add(bucket: list[str], value: str, known: SiteKnowledge, source: str) -> None:
    value = value.strip()
    if not value or value in bucket:
        return
    bucket.append(value)
    known.sources.setdefault(value, source)


def _types(node: dict[str, Any]) -> list[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [t for t in raw if isinstance(t, str)]
    return []


__all__ = ["SiteKnowledge", "collect"]
