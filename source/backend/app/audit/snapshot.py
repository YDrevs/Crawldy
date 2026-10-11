"""Знімок зібраного: усе, що потрібно, щоб перерахувати аудит без мережі.

Різниця з `to_json()` навмисна. Той компактний і призначений для звіту —
з нього видно, що ми знайшли, але зібрати з нього `SiteContext` назад
неможливо: посилання згорнуті в лічильники, розмітка — в перелік типів,
тексту немає взагалі.

Тут навпаки: втрат нема, читабельність не мета. Знімок відповідає на
питання, якого без нього немає як поставити — **що дав би цей самий
краул за новими правилами**. Без нього кожна зміна скорингу чи чека
відрізає нас від усіх попередніх аудитів: порівняти можна лише те, що
пораховано однаково, а перерахувати старе можна лише повторним краулом,
тобто вже по іншому сайту.

Чого в знімку немає навмисно:

- **HTML сторінок.** Чеки працюють із `PageSignals`, а не з розміткою;
  зберігати мегабайти, щоб ніхто їх не читав, — марно.
- **Висновки моделі** (`brief`, `facts`). Вони належать конкретній моделі
  й конкретному прогону: перерахувати їх з тими самими вхідними даними
  не можна, а видати старий висновок за новий — значить збрехати про те,
  чим порахований аудит. Модуль llm_visibility на перерахунку тому
  спирається лише на детерміністичні сигнали.
- **`known` і `links`.** Вони не збираються з мережі, а виводяться зі
  сторінок, тож відновлюються обчисленням — зберігати означало б
  тримати дві версії однієї правди.
"""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import Any

from app.audit import robots as robots_rfc
from app.audit.types import (
    FormSignals,
    HreflangRef,
    InfraInfo,
    InsecureRef,
    LinkRef,
    LlmsTxtInfo,
    MetricValue,
    PageSignals,
    PerformanceResult,
    RenderResult,
    ResourceLoad,
    RobotsInfo,
    SiteContext,
    SitemapInfo,
    Strategy,
)

SNAPSHOT_SCHEMA = "2"

# Поля SiteContext, які не зберігаються. Причини — у docstring модуля.
# `raw_pages` — бухгалтерія часу краулу: він потрібен, щоб звести
# логічні сторінки по всьому набору, коли краул іде хвилями. У знімку
# лежать уже зведені `pages`, тож зберігати сирий список означало б
# тримати ту саму правду двічі й розійтися з нею на першій же правці.
_NOT_STORED = frozenset(
    {"pages", "raw_pages", "performance", "renders", "brief", "facts", "known", "links"}
)


def dump(ctx: SiteContext) -> dict[str, Any]:
    """SiteContext → JSON-придатний словник без втрат."""
    site = {
        f.name: getattr(ctx, f.name)
        for f in fields(ctx)
        if f.name not in _NOT_STORED and not is_dataclass(getattr(ctx, f.name))
    }
    return {
        "schema": SNAPSHOT_SCHEMA,
        "site": site,
        "robots": _dump_robots(ctx.robots),
        "sitemap": _dump(ctx.sitemap),
        "llms_txt": _dump(ctx.llms_txt),
        "infra": _dump(ctx.infra),
        "pages": [_dump(page) for page in ctx.pages],
        "performance": [_dump_performance(p) for p in ctx.performance],
        "renders": {url: _dump_render(r) for url, r in ctx.renders.items()},
    }


def load(data: dict[str, Any]) -> SiteContext:
    """Словник → SiteContext, придатний для повторного прогону чеків."""
    ctx = SiteContext(**data["site"])
    ctx.robots = _load(RobotsInfo, data.get("robots"))
    # Розібраний robots.txt виводиться з `content`, тож зберігати його
    # означало б тримати дві версії однієї правди — і одна з них уже
    # розійшлася: `json.dumps(default=str)` мовчки клав туди рядок, а
    # `evaluate` на рядку падав аж на перерахунку живого знімка.
    ctx.robots.parsed = robots_rfc.parse(ctx.robots.content) if ctx.robots.exists else None
    ctx.sitemap = _load(SitemapInfo, data.get("sitemap"))
    ctx.sitemap.hreflang = {
        url: [_load(HreflangRef, ref) for ref in refs]
        for url, refs in ((data.get("sitemap") or {}).get("hreflang") or {}).items()
    }
    ctx.llms_txt = _load(LlmsTxtInfo, data.get("llms_txt"))
    ctx.infra = _load(InfraInfo, data.get("infra"))
    rows = data.get("pages") or []
    ctx.pages = [_load_page(row) for row in rows]
    # Знімок схеми 1 робився до того, як ми навчилися читати мовні версії.
    # Порожній список там означає «не дивилися», і чек, який стверджує
    # відсутність, мусить це знати: інакше перерахунок старого аудиту
    # породжує знахідку про сайт із нашої власної прогалини.
    ctx.hreflang_observed = all("hreflang" in row for row in rows) if rows else True
    ctx.performance = [_load_performance(row) for row in data.get("performance") or []]
    ctx.renders = {
        url: _load_render(row) for url, row in (data.get("renders") or {}).items()
    }
    return ctx


def _dump_robots(info: RobotsInfo) -> dict[str, Any]:
    row = _dump(info)
    row.pop("parsed", None)
    return row


def _dump(obj: Any) -> dict[str, Any]:
    """Пласкі dataclass'и — поле в поле, вкладені — рекурсивно."""
    out: dict[str, Any] = {}
    for f in fields(obj):
        value = getattr(obj, f.name)
        if isinstance(value, list) and value and is_dataclass(value[0]):
            out[f.name] = [_dump(item) for item in value]
        elif isinstance(value, dict) and _holds_dataclasses(value):
            # Словник списків dataclass'ів — так карта сайту тримає
            # анотації мовних версій. Без цієї гілки вони пішли б у
            # json.dumps обʼєктами, а знімок мовчки перестав би зберігатись.
            out[f.name] = {k: [_dump(item) for item in v] for k, v in value.items()}
        else:
            out[f.name] = value
    return out


def _holds_dataclasses(value: dict[Any, Any]) -> bool:
    return any(isinstance(v, list) and v and is_dataclass(v[0]) for v in value.values())


def _load(cls: Any, row: dict[str, Any] | None) -> Any:
    """Створює dataclass, ігноруючи поля, яких у ньому вже немає.

    Знімок переживає зміну структури: аудит, збережений до появи поля,
    має відкриватися й після неї. Інакше перша ж нова ознака зробила б
    непридатним усе, що збережено раніше, — тобто перекреслила б саму
    мету знімка.
    """
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (row or {}).items() if k in known})


def _load_page(row: dict[str, Any]) -> PageSignals:
    page: PageSignals = _load(PageSignals, row)
    page.links = [_load(LinkRef, link) for link in row.get("links") or []]
    page.forms = [_load(FormSignals, form) for form in row.get("forms") or []]
    page.hreflang = [_load(HreflangRef, ref) for ref in row.get("hreflang") or []]
    page.insecure_refs = [
        _load(InsecureRef, ref) for ref in row.get("insecure_refs") or []
    ]
    # JSON не знає кортежів, і після знімка ланцюг приходив списками
    # списків при оголошеному `tuple[tuple[int, str], ...]`. Ітерація
    # від цього не ламалась, тому й не помічалось; тип відновлюємо, щоб
    # наступний, хто напише `isinstance`, не наступив.
    page.redirect_chain = tuple(
        (int(hop[0]), str(hop[1])) for hop in row.get("redirect_chain") or ()
    )
    return page


def _dump_performance(result: PerformanceResult) -> dict[str, Any]:
    row = _dump(result)
    row["strategy"] = result.strategy.value
    row["lab"] = {name: _dump(value) for name, value in result.lab.items()}
    row["field_data"] = {name: _dump(value) for name, value in result.field_data.items()}
    return row


def _load_performance(row: dict[str, Any]) -> PerformanceResult:
    result: PerformanceResult = _load(
        PerformanceResult, {**row, "strategy": Strategy(row["strategy"])}
    )
    result.lab = {name: _load(MetricValue, v) for name, v in (row.get("lab") or {}).items()}
    result.field_data = {
        name: _load(MetricValue, v) for name, v in (row.get("field_data") or {}).items()
    }
    return result


def _dump_render(result: RenderResult) -> dict[str, Any]:
    row = _dump(result)
    # HTML не зберігаємо: чеки читають сигнали, а не розмітку.
    row["html"] = ""
    row["signals"] = _dump(result.signals) if result.signals is not None else None
    return row


def _load_render(row: dict[str, Any]) -> RenderResult:
    result: RenderResult = _load(RenderResult, row)
    result.signals = _load_page(row["signals"]) if row.get("signals") else None
    result.resources = [_load(ResourceLoad, item) for item in row.get("resources") or []]
    return result


__all__ = ["SNAPSHOT_SCHEMA", "dump", "load"]
