"""Відповідь сервера проти відрендереного DOM: що саме змінилося.

## Навіщо окремий модуль

Обидві версії сторінки в контексті вже лежать поруч: статичні
`PageSignals` і `RenderResult.signals` — той самий розбір, застосований
до HTML після виконання JS. Досі з цієї пари читалося одне число:
відношення обсягу тексту (`visible_without_js`). Воно відповідає на
питання «чи видно вміст без JS» і мовчить про те, що для краулера часто
важливіше: чи той самий у сторінки canonical, той самий title, ті самі
директиви індексації.

Порівняння живе окремо від чеків навмисно. Ним користується вже два
споживачі, а далі знадобиться третьому — виявленню посилань, які
існують лише після рендеру. Вбудувати його в один детектор означало б
переписувати те саме порівняння щоразу, коли по нього прийдуть.

## Чого цей модуль не робить

Не рендерить. Він працює з тим, що вже зібрано, тому однаково працює на
живому аудиті й на збереженому знімку — знімок несе обидва набори
сигналів без втрат, і повторний рендер для перерахунку не потрібен.

Не робить висновків. Він каже, що відрізняється; що це означає для
клієнта, вирішує чек, і саме там живе межа між фактом і тлумаченням.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.audit.logical_pages import normalize
from app.audit.types import PageSignals, RenderResult

# Поля, які порівнюються як текст. Порядок важливий: він задає
# пріоритет у звіті, коли змінилося кілька.
TEXT_FIELDS = ("title", "meta_description")


class DeltaKind(StrEnum):
    """Напрямок зміни. Три різні історії, а не одна.

    `index` → `noindex` після рендеру і `noindex` → `index` — протилежні
    за наслідками речі, і зливати їх в «відрізняється» означало б
    викинути саме те, заради чого порівняння робиться.
    """

    # Сигнал зʼявився лише після виконання JS.
    ADDED = "added"
    # Сигнал був у відповіді сервера й зник після рендеру.
    REMOVED = "removed"
    # Був і там, і там, але різний.
    CHANGED = "changed"


@dataclass(frozen=True, slots=True)
class FieldDelta:
    """Одне поле, що розійшлося між двома версіями сторінки."""

    field: str
    kind: DeltaKind
    before: str | None
    after: str | None

    def as_evidence(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "change": self.kind.value,
            "in_response": self.before,
            "after_render": self.after,
        }


@dataclass(frozen=True, slots=True)
class LinkDelta:
    """Внутрішні посилання, що є лише в одній із версій.

    Зберігається нормалізованим і повним: наступна задача — виявлення
    посилань, доступних лише через JS, — має взяти вже пораховане, а не
    рахувати вдруге власним способом.
    """

    only_after_render: tuple[str, ...] = ()
    only_in_response: tuple[str, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.only_after_render or self.only_in_response)


@dataclass(frozen=True, slots=True)
class RenderDiff:
    """Результат порівняння однієї сторінки.

    `comparable=False` — це не «різниці немає». Це «порівнювати не було
    чим», і чек мусить розрізняти ці два стани: збій рендеру не є
    доказом того, що сторінка без JS повноцінна.
    """

    url: str
    comparable: bool
    reason: str = ""
    fields: tuple[FieldDelta, ...] = ()
    links: LinkDelta = field(default_factory=LinkDelta)

    @property
    def changed(self) -> bool:
        return self.comparable and bool(self.fields or self.links.changed)

    def field_names(self) -> tuple[str, ...]:
        return tuple(delta.field for delta in self.fields)

    def get(self, name: str) -> FieldDelta | None:
        return next((d for d in self.fields if d.field == name), None)

    def as_evidence(self) -> dict[str, Any]:
        """Доказ, за яким твердження можна перевірити вручну."""
        evidence: dict[str, Any] = {
            "comparable": self.comparable,
            "fields_changed": list(self.field_names()),
            "deltas": [d.as_evidence() for d in self.fields],
        }
        if not self.comparable:
            evidence["not_compared_because"] = self.reason
        if self.links.changed:
            evidence["links"] = {
                "only_after_render": list(self.links.only_after_render[:10]),
                "only_after_render_count": len(self.links.only_after_render),
                "only_in_response": list(self.links.only_in_response[:10]),
                "only_in_response_count": len(self.links.only_in_response),
            }
        return evidence


# ── нормалізація ───────────────────────────────────────────────────────────


def _text(value: str | None) -> str | None:
    """Порожнє й відсутнє — те саме; зайві пробіли значення не мають."""
    if value is None:
        return None
    collapsed = " ".join(value.split())
    return collapsed or None


def _url(value: str | None) -> str | None:
    """Адреса через ту саму нормалізацію, що й решта проєкту.

    Інакше `/a` і `/a/` виглядали б зміною canonical, якою вони не є.
    """
    text = _text(value)
    return normalize(text) if text else None


def _directives(value: str | None) -> frozenset[str] | None:
    """robots-директиви як множина.

    Порядок і регістр у них не значать нічого: `noindex, follow` і
    `FOLLOW,NOINDEX` — та сама вказівка. Порівнювати їх рядком означало б
    повідомляти про зміну там, де змінили лише запис.
    """
    text = _text(value)
    if text is None:
        return None
    parts = {part.strip().lower() for part in text.split(",")}
    parts.discard("")
    return frozenset(parts) or None


def _headline(values: list[str]) -> str | None:
    """Перший H1: саме він відповідає на питання «про що ця сторінка»."""
    for item in values:
        text = _text(item)
        if text:
            return text
    return None


def _schema(nodes: list[dict[str, Any]]) -> frozenset[str]:
    """Розмітка як множина типів і тотожностей, а не як текст JSON.

    Порівняння серіалізованого JSON спрацьовувало б на порядку ключів і
    на пробілах — тобто на всьому, крім змісту. Значення мають дві речі:
    які типи оголошені й на які `@id` вони посилаються.
    """
    out: set[str] = set()
    for node in nodes:
        if not isinstance(node, dict):
            continue
        raw = node.get("@type")
        types = raw if isinstance(raw, list) else [raw]
        for item in types:
            if isinstance(item, str) and item.strip():
                out.add(f"type:{item.strip()}")
        identity = node.get("@id")
        if isinstance(identity, str) and identity.strip():
            out.add(f"id:{_url(identity)}")
    return frozenset(out)


def _internal_links(page: PageSignals) -> frozenset[str]:
    """Внутрішні посилання нормалізованою множиною — порядок не рахується."""
    return frozenset(
        normalize(link.url) for link in page.links if link.is_internal and link.url
    )


# ── порівняння ─────────────────────────────────────────────────────────────


def _delta(name: str, before: Any, after: Any) -> FieldDelta | None:
    """Одна пара значень → різниця, якщо вона змістовна."""
    if before == after:
        return None
    kind = (
        DeltaKind.ADDED
        if not before
        else DeltaKind.REMOVED
        if not after
        else DeltaKind.CHANGED
    )
    return FieldDelta(field=name, kind=kind, before=_show(before), after=_show(after))


def _show(value: Any) -> str | None:
    """Значення для доказу: множини читаються відсортованими."""
    if value is None or value == "":
        return None
    if isinstance(value, frozenset | set):
        return ", ".join(sorted(value)) or None
    return str(value)


def _why_not_comparable(page: PageSignals, result: RenderResult | None) -> str:
    """Причина, з якої порівняння не відбулося. Порожньо — можна порівнювати.

    Кожен випадок названий окремо, бо «рендер вимкнули» і «рендер
    зламався» — різні речі для звіту, і жодна з них не означає, що
    сторінка без JS повноцінна.
    """
    if page.status_code is None or not (200 <= page.status_code < 300):
        return "response.not_ok"
    if result is None:
        return "render.not_attempted"
    if result.disabled:
        return "render.disabled"
    if not result.rendered:
        return "render.failed"
    if result.signals is None:
        return "render.no_signals"
    return ""


def compare(page: PageSignals, result: RenderResult | None) -> RenderDiff:
    """Порівняти відповідь сервера з відрендереною версією тієї ж сторінки.

    Обидва аргументи вже зібрані аудитом; мережі тут немає, тож те саме
    порівняння однаково працює на знімку.
    """
    reason = _why_not_comparable(page, result)
    if reason:
        return RenderDiff(url=page.url, comparable=False, reason=reason)

    assert result is not None and result.signals is not None  # гарантовано вище
    after = result.signals

    deltas: list[FieldDelta] = []
    # Порядок перевірок = порядок важливості у звіті: спершу те, що керує
    # індексацією, потім те, як сторінка себе називає, потім розмітка.
    for name, before_value, after_value in (
        ("meta_robots", _directives(page.meta_robots), _directives(after.meta_robots)),
        ("canonical", _url(page.canonical), _url(after.canonical)),
        ("title", _text(page.title), _text(after.title)),
        ("h1", _headline(page.h1), _headline(after.h1)),
        ("meta_description", _text(page.meta_description), _text(after.meta_description)),
        ("jsonld", _schema(page.jsonld), _schema(after.jsonld)),
    ):
        delta = _delta(name, before_value, after_value)
        if delta is not None:
            deltas.append(delta)

    before_links = _internal_links(page)
    after_links = _internal_links(after)
    links = LinkDelta(
        only_after_render=tuple(sorted(after_links - before_links)),
        only_in_response=tuple(sorted(before_links - after_links)),
    )

    return RenderDiff(
        url=page.url, comparable=True, fields=tuple(deltas), links=links
    )


def compare_all(ctx: Any) -> list[RenderDiff]:
    """Порівняння для кожної сторінки, яку справді рендерили.

    Сторінки поза бюджетом рендеру сюди не потрапляють: про них ми не
    знаємо нічого, і мовчання — правильна відповідь.
    """
    out = []
    for page in ctx.ok_pages:
        result = ctx.renders.get(page.url)
        if result is None:
            continue
        out.append(compare(page, result))
    return out


__all__ = [
    "DeltaKind",
    "FieldDelta",
    "LinkDelta",
    "RenderDiff",
    "compare",
    "compare_all",
]
