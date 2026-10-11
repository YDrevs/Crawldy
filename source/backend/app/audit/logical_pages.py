"""Логічний документ замість адреси.

Краулер бачить URL, а сайт має сторінки. Одна сторінка легко дає кілька
адрес: `site` і `site/`, `/contact` і `/contact?subject=Press`, той самий
шлях під іншим регістром хоста. Кожна така пара породжувала дубль title,
знахідку «немає в карті сайту» й зауваження про canonical — три різні
претензії до одного нормального патерну.

Групування свідомо консервативне. Варіанти зливаються лише тоді, коли
вміст справді той самий: canonical, що вказує на сторінку з ІНШИМ
вмістом, — це справжня проблема, і сховати її під виглядом дедуплікації
означало б проміняти шість хибних знахідок на одну пропущену справжню.

Представник групи — не перший-ліпший: береться саме канонічна адреса,
якщо ми її бачили, бо це та, яку сайт вважає головною.
"""

from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.audit.types import PageSignals

# Параметри, які не міняють сторінку, а лише позначають, звідки прийшли.
TRACKING_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "gclid", "fbclid", "msclkid", "yclid", "_ga", "mc_cid", "mc_eid",
    "ref", "referrer", "source",
})

# Наскільки вміст може відрізнятися, щоб сторінки лишалися тією самою.
# Форма зворотного звʼязку з іншим значенням поля міняє кілька слів, тож
# нуль тут був би надто суворим.
SAME_CONTENT_TOLERANCE = 0.1


def normalize(url: str) -> str:
    """Адреса без того, що не міняє сторінку.

    Прибирається фрагмент, регістр хоста, кінцевий слеш і мітки джерела.
    Решта параметрів лишається, але впорядкованою: `?a=1&b=2` і `?b=2&a=1`
    — одна адреса, а `?id=12` і `?id=13` — різні.
    """
    parsed = urlparse(url.strip())
    query = sorted(
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS
    )
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        "",
        urlencode(query),
        "",
    ))


def same_content(one: PageSignals, other: PageSignals) -> bool:
    """Чи це та сама сторінка під іншою адресою.

    Порівнюються заголовок і обсяг тексту. Точне порівняння самого тексту
    тут не потрібне й шкідливе: варіанти форми відрізняються кількома
    словами, а сторінка, канонізована на чужу тему, відрізняється всім.
    """
    if (one.title or "").strip() != (other.title or "").strip():
        return False
    biggest = max(one.word_count, other.word_count)
    if biggest == 0:
        return True
    return abs(one.word_count - other.word_count) / biggest <= SAME_CONTENT_TOLERANCE


def group(pages: list[PageSignals]) -> list[PageSignals]:
    """Логічні сторінки зі списку адрес, у тому ж порядку.

    Два проходи. Перший зводить адреси, які нормалізуються в одну, —
    `site` і `site/` не можуть бути різними сторінками ні за яких умов.
    Другий приєднує варіанти до їхньої канонічної адреси, але лише коли
    вміст збігається.
    """
    by_url: dict[str, PageSignals] = {}
    order: list[str] = []
    for page in pages:
        key = normalize(page.url)
        kept = by_url.get(key)
        if kept is None:
            by_url[key] = page
            order.append(key)
            continue
        winner, loser = _prefer(kept, page, key)
        winner.url_variants = _merged_variants(winner, loser)
        winner.discovered_via = _merged_sources(winner, loser)
        by_url[key] = winner

    for key in list(order):
        page = by_url[key]
        if not page.canonical:
            continue
        target_key = normalize(page.canonical)
        target = by_url.get(target_key)
        if target is None or target is page:
            continue
        # Canonical на сторінку з іншим вмістом — справжня знахідка, і
        # чек про неї має спрацювати. Тут ми лише прибираємо шум від
        # варіантів однієї сторінки, а не ховаємо розбіжності.
        if not same_content(page, target):
            continue
        target.url_variants = _merged_variants(target, page)
        target.discovered_via = _merged_sources(target, page)
        del by_url[key]
        order.remove(key)

    return [by_url[key] for key in order]


def _prefer(kept: PageSignals, other: PageSignals, key: str) -> tuple[PageSignals, PageSignals]:
    """Представником стає канонічна адреса, інакше — та, де більше вмісту."""
    if normalize(other.url) == key and normalize(kept.url) != key:
        return other, kept
    if other.url == key and kept.url != key:
        return other, kept
    if other.word_count > kept.word_count:
        return other, kept
    return kept, other


def _merged_sources(keeper: PageSignals, dropped: PageSignals) -> list[str]:
    """Походження зливається, а не перезаписується.

    Дві адреси однієї логічної сторінки могли прийти різними шляхами —
    одна з меню, друга з карти. Лишити походження лише представника
    означало б загубити половину відповіді на питання «звідки ми про неї
    дізналися».
    """
    return sorted({*keeper.discovered_via, *dropped.discovered_via})


def _merged_variants(keeper: PageSignals, dropped: PageSignals) -> list[str]:
    seen = {keeper.url, *keeper.url_variants, *dropped.url_variants, dropped.url}
    seen.discard(keeper.url)
    return sorted(seen)


__all__ = ["SAME_CONTENT_TOLERANCE", "TRACKING_PARAMS", "group", "normalize", "same_content"]
