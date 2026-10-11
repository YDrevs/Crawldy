"""Чи є `BreadcrumbList` на сторінці ДІЙСНИМ — за задокументованим контрактом Google.

## Навіщо окремий модуль

Чек питав `"BreadcrumbList" not in types_on(page)`, тобто рівно одне: чи
стоїть на сторінці вузол із таким типом. Розмітка з одного пункту, з
пропущеною назвою, з переплутаними позиціями і з посиланням на чужий
сайт зараховувалась однаково — просто тому, що вузол є. Клієнт чув «у вас
усе гаразд» про розмітку, яку Google не покаже.

Дійсність — окреме питання від ієрархії, тож і модуль окремий:
`hierarchy.py` вирішує, чи є на сайті ієрархія, а цей — чи описує знайдена
розмітка шлях, який Google визнає.

## Правила

Джерело — довідка Google *Breadcrumb (BreadcrumbList) structured data*.
Сім правил контракту, тими самими іменами:

| id | правило |
|---|---|
| V1 | щонайменше ДВА `ListItem` |
| V2 | у кожного цілочисельна `position`; вони починаються з 1 і зростають
|    | послідовно В ПОРЯДКУ СЛІДУ |
| V3 | у кожного є назва — `ListItem.name` або `item.name` |
| V4 | у кожного, КРІМ останнього, є адреса `item` |
| V5 | в останнього адреси МОЖЕ не бути |
| V6 | слід НЕ зобовʼязаний закінчуватись посиланням на саму сторінку |
| V7 | наявні адреси мають належати сайту — за СПІЛЬНИМ контрактом меж |

Два останні правила — виправлення v1.3, і обидва знімають вимогу,
суворішу за документацію: попередня редакція вимагала, щоб останній
пункт був самою сторінкою або її canonical, а адреси лежали буквально на
тому самому origin.

## Чого тут немає

Власного правила «той самий сайт». Межі сайту знає `site_scope`, і саме
він відповідає, що `http://example.com` і `https://www.example.com:443` —
один сайт. Свій варіант цього правила означав би третє місце з тією самою
відповіддю, і воно розійшлося б із двома першими — рівно так, як колись
розійшлися екстрактор і фронтир.

Порядку сліду теж не вигадуємо: `itemListElement` читається в тому
порядку, у якому його написав сайт. Пересортувати за `position` означало
б лагодити за сайт його ж помилку й зараховувати слід, якого Google не
прийме — саме це і є випадок BV-f4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.audit.logical_pages import normalize
from app.audit.site_scope import SiteScope
from app.audit.types import PageSignals

# Причини недійсності, іменами правил контракту. Рядки, а не enum: вони
# йдуть у доказ і мусять читатися там без словника.
V1_TOO_FEW_ITEMS = "V1_fewer_than_two_items"
V2_POSITIONS = "V2_positions_not_consecutive_from_one"
V3_MISSING_NAME = "V3_item_without_a_name"
V4_MISSING_URL = "V4_non_final_item_without_a_url"
V7_OUT_OF_SCOPE = "V7_item_url_outside_the_site"


@dataclass(frozen=True, slots=True)
class Crumb:
    """Один `ListItem` сліду, зведений до трьох фактів, які судить контракт."""

    position: Any
    name: str
    url: str | None

    @property
    def has_name(self) -> bool:
        return bool(self.name.strip())


@dataclass(frozen=True, slots=True)
class Trail:
    """Один `BreadcrumbList` і вирок про нього."""

    items: tuple[Crumb, ...]
    valid: bool
    reasons: tuple[str, ...] = ()
    # Адреса вузла, якщо сайт її назвав, — щоб доказ показував, ЯКИЙ слід.
    node_id: str | None = None

    def as_evidence(self) -> dict[str, Any]:
        return {
            "items": len(self.items),
            "valid": self.valid,
            "reasons": list(self.reasons),
            "names": [crumb.name for crumb in self.items],
            "urls": [crumb.url for crumb in self.items],
        }


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _crumb(node: Any) -> Crumb:
    """`ListItem` → три факти.

    Назва береться з `ListItem.name` або з `item.name` — обидві форми
    канонічні, і документація показує обидві. Адреса буває рядком
    (`"item": "https://..."`) або вузлом з `@id`; це теж дві форми одного
    і того ж, а не два різні випадки.
    """
    if not isinstance(node, dict):
        return Crumb(position=None, name="", url=None)
    item = node.get("item")
    name = _text(node.get("name"))
    url: str | None = None
    if isinstance(item, str):
        url = _text(item) or None
    elif isinstance(item, dict):
        url = _text(item.get("@id")) or _text(item.get("url")) or None
        if not name:
            name = _text(item.get("name"))
    return Crumb(position=node.get("position"), name=name, url=url)


def _positions_ascend(items: tuple[Crumb, ...]) -> bool:
    """1, 2, 3 … у порядку, у якому пункти написані.

    Ціле число — і саме ціле: `"2"` рядком і `2.0` не є `position` за
    документацією. `bool` відсікається окремо, бо в Python `True == 1`, і
    без цього `"position": true` пройшов би як перший пункт.
    """
    for index, crumb in enumerate(items, start=1):
        if isinstance(crumb.position, bool) or not isinstance(crumb.position, int):
            return False
        if crumb.position != index:
            return False
    return True


def validate(node: Any, *, entry: str) -> Trail:
    """Вирок про один вузол `BreadcrumbList`."""
    raw = node.get("itemListElement") if isinstance(node, dict) else None
    if isinstance(raw, dict):
        # Один пункт без списка-обгортки — сайт має право написати й так.
        raw = [raw]
    items = tuple(_crumb(entry_node) for entry_node in (raw or []))
    node_id = _text(node.get("@id")) if isinstance(node, dict) else ""

    scope = SiteScope.from_url(entry)
    reasons: list[str] = []
    if len(items) < 2:
        reasons.append(V1_TOO_FEW_ITEMS)
    if not _positions_ascend(items):
        reasons.append(V2_POSITIONS)
    if any(not crumb.has_name for crumb in items):
        reasons.append(V3_MISSING_NAME)
    # V4 і V5 — одне правило з двох боків: адреса обовʼязкова всюди, крім
    # ОСТАННЬОГО пункту, де її може не бути. Останній визначається
    # порядком сліду, а не тим, чи він описує саму сторінку (V6).
    if any(crumb.url is None for crumb in items[:-1]):
        reasons.append(V4_MISSING_URL)
    if any(crumb.url is not None and not scope.contains(crumb.url) for crumb in items):
        reasons.append(V7_OUT_OF_SCOPE)
    return Trail(items=items, valid=not reasons, reasons=tuple(reasons), node_id=node_id or None)


def _nodes(payload: Any) -> list[dict[str, Any]]:
    """Кожен вузол `BreadcrumbList` у розмітці, хоч би як глибоко він лежав.

    Сайти публікують слід і голим вузлом, і всередині `@graph`, і вкладеним
    у `WebPage.breadcrumb`. Це три канонічні форми одного й того ж, тож
    обхід іде по всьому дереву — так само, як це вже робить `types_on`.
    """
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            raw = node.get("@type")
            declared = [raw] if isinstance(raw, str) else (raw if isinstance(raw, list) else [])
            if any(isinstance(t, str) and t.strip() == "BreadcrumbList" for t in declared):
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(payload)
    return found


def trails_on(page: PageSignals, *, entry: str) -> list[Trail]:
    """Кожен слід сторінки з вироком про нього."""
    return [validate(node, entry=entry) for payload in page.jsonld for node in _nodes(payload)]


@dataclass(frozen=True, slots=True)
class PageTrails:
    """Що сторінка показала — і що з цього дійсне."""

    url: str
    trails: tuple[Trail, ...] = field(default_factory=tuple)
    # Видимий слід у розмітці: збережений факт, не заміна розмітці.
    ui: bool = False

    @property
    def present(self) -> bool:
        return bool(self.trails)

    @property
    def valid(self) -> bool:
        return any(trail.valid for trail in self.trails)

    @property
    def reasons(self) -> tuple[str, ...]:
        """Чому жоден слід не дійсний. Порожньо, коли дійсний хоч один."""
        if self.valid:
            return ()
        return tuple(sorted({reason for trail in self.trails for reason in trail.reasons}))

    def as_evidence(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "breadcrumblist_present": self.present,
            "valid": self.valid,
            "reasons": list(self.reasons),
            "breadcrumb_ui": self.ui,
        }


def read(page: PageSignals, *, entry: str) -> PageTrails:
    """Слід сторінки разом із видимим слідом — обидва факти в одному місці."""
    return PageTrails(
        url=page.url,
        trails=tuple(trails_on(page, entry=entry)),
        ui=bool(getattr(page, "breadcrumb_ui", False)),
    )


def ancestors_named(page: PageSignals) -> set[str]:
    """Сторінки, які розмітка називає предками цієї.

    Пункти її ж `BreadcrumbList` і `isPartOf`. Це друга з трьох
    зʼєднувальних згадок R1: дитина сама каже, хто її батько, і
    посилання від батька для цього не потрібне.

    Дійсність тут не питається навмисно: зіпсований слід — це дефект
    РОЗМІТКИ, і карати за нього двічі, ще й стираючи спостережений звʼязок
    між сторінками, означало б сплутати два різні твердження.
    """
    found: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            part_of = node.get("isPartOf")
            for candidate in (part_of if isinstance(part_of, list) else [part_of]):
                if isinstance(candidate, str) and candidate.strip():
                    found.add(normalize(candidate.strip()))
                elif isinstance(candidate, dict):
                    target = _text(candidate.get("@id")) or _text(candidate.get("url"))
                    if target:
                        found.add(normalize(target))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for payload in page.jsonld:
        walk(payload)
        for node in _nodes(payload):
            for crumb in validate(node, entry=page.url).items:
                if crumb.url:
                    found.add(normalize(crumb.url))
    found.discard(normalize(page.url))
    return found


__all__ = [
    "V1_TOO_FEW_ITEMS",
    "V2_POSITIONS",
    "V3_MISSING_NAME",
    "V4_MISSING_URL",
    "V7_OUT_OF_SCOPE",
    "Crumb",
    "PageTrails",
    "Trail",
    "ancestors_named",
    "read",
    "trails_on",
    "validate",
]
