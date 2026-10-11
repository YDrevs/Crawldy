"""Виключення дорослого вмісту: за доказом зі сторінки, не за назвою.

## Рішення, яке це реалізує

З корпусу виключається **лише порнографічний вміст**. Занедбані, старі,
негарні, погано зроблені сайти лишаються: заради них корпус і збирається.
«Виглядає дешево» не є причиною виключення й ніколи нею не стане — це
було б підганяння вибірки під те, що приємно бачити у звіті.

## Чому не за словами в домені

Домен — найслабший з доказів. `sexauer.de` — німецьке прізвище,
`analytics.example` містить `anal`, `essex.gov.uk` містить `sex`.
Виключати за підрядком означає викидати випадкові порядні сайти й
називати це політикою.

Тому головні докази — ті, які сайт дає про себе сам:

1. **Мітка RTA** (`RTA-5042-1996-1400-1577-RTA`) — стандарт
   самопозначення для дорослих сайтів. Сильніше свідчення уявити важко:
   сайт прямо каже, що він дорослий. Одного цього досить.
2. **`<meta name="rating">`** зі значенням `adult`/`mature`/`RTA` — те саме
   самопозначення іншим способом. Одного досить.
3. **Слова в заголовку, описі й ключових словах** — те, що сайт написав
   про себе для пошуковиків.

Слабкі докази (домен, окреме слово в заголовку) самі по собі не
виключають: потрібні два незалежні. Одинична згадка слова буває в
новинах, медицині та праві.

## Чому виключене записується

«Тихо викинув 40 сайтів» — це непомітна зміна складу корпусу. Кожне
виключення лишає причину `adult_content` і доказ, за яким рішення можна
переглянути або оскаржити.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Самопозначення. Це не здогад про сайт, а його власна заява.
RTA_LABEL = b"rta-5042-1996-1400-1577-rta"
_RATING = re.compile(
    rb"""<meta[^>]+name=["']rating["'][^>]+content=["']([^"']{0,60})["']""",
    re.IGNORECASE,
)
_RATING_ADULT = ("adult", "mature", "rta-5042", "restricted adult")

_TITLE = re.compile(rb"<title[^>]*>(.{0,300}?)</title>", re.IGNORECASE | re.DOTALL)
_META_TEXT = re.compile(
    rb"""<meta[^>]+name=["'](?:description|keywords)["'][^>]+content=["']([^"']{0,400})["']""",
    re.IGNORECASE,
)

# Слова однозначні: у звичайного бізнесу їх у заголовку не буває.
# Свідомо без `sex` і `adult` — обидва занадто часті в медицині, праві,
# новинах і назвах місць.
STRONG_TERMS = (
    "porn", "porno", "xxx", "hentai", "camgirl", "escort service",
    "nude photos", "sex cam", "webcam sex", "anal sex", "milf",
    "blowjob", "creampie", "doujin", "eroti", "nsfw",
)

# Токени в домені. Слабкий доказ: лише в парі з іншим.
DOMAIN_TOKENS = (
    "porn", "xxx", "hentai", "camgirl", "escort", "milf", "doujin",
    "erotic", "nsfw", "sexcam", "adultvideo",
)


@dataclass
class Verdict:
    """Рішення про один сайт і доказ, на якому воно стоїть."""

    excluded: bool = False
    reason: str = ""
    evidence: list[str] = field(default_factory=list)


def _tokens(host: str) -> list[str]:
    return [t for t in re.split(r"[.\-_/]", host.lower()) if t]


def classify(host: str, body: bytes) -> Verdict:
    """Чи виключати сайт як дорослий, і за яким доказом."""
    verdict = Verdict()
    low = body.lower()

    # ── самопозначення: одного досить ────────────────────────────────
    if RTA_LABEL in low:
        return Verdict(True, "adult_content", ["RTA label present on page"])
    rating = _RATING.search(body)
    if rating:
        value = rating.group(1).decode("utf-8", "replace").lower()
        if any(mark in value for mark in _RATING_ADULT):
            return Verdict(True, "adult_content", [f'meta rating="{value[:40]}"'])

    # ── слабші докази: потрібні два незалежні ────────────────────────
    signals: list[str] = []

    title_match = _TITLE.search(body)
    title = (
        title_match.group(1).decode("utf-8", "replace").lower()[:300]
        if title_match else ""
    )
    hit = next((t for t in STRONG_TERMS if t in title), "")
    if hit:
        signals.append(f'title contains "{hit}"')

    meta_text = " ".join(
        m.decode("utf-8", "replace").lower() for m in _META_TEXT.findall(body)[:4]
    )[:600]
    meta_hit = next((t for t in STRONG_TERMS if t in meta_text), "")
    if meta_hit:
        signals.append(f'meta contains "{meta_hit}"')

    host_tokens = _tokens(host)
    domain_hit = next(
        (t for t in DOMAIN_TOKENS
         if any(t == token or t in token for token in host_tokens)), "",
    )
    if domain_hit:
        signals.append(f'domain token "{domain_hit}"')

    # Домен плюс будь-що інше, або заголовок плюс опис.
    if len(signals) >= 2:
        return Verdict(True, "adult_content", signals)

    # Однозначне слово в заголовку — саме по собі досить: «porn» у
    # <title> звичайного бізнесу не трапляється.
    if hit and hit in ("porn", "porno", "xxx", "hentai"):
        return Verdict(True, "adult_content", signals)

    verdict.evidence = signals
    return verdict


__all__ = ["DOMAIN_TOKENS", "RTA_LABEL", "STRONG_TERMS", "Verdict", "classify"]
