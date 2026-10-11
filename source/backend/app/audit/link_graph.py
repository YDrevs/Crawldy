"""Граф внутрішніх посилань: що на що посилається і що з цього випливає.

Сайт — не список сторінок, а структура. З того, звідки й скільки разів
на сторінку посилаються, видно те, чого не видно з самої сторінки: чи
вона взагалі досяжна, чи вважає її важливою сам сайт, чи не веде він
відвідувача в глухий кут.

Найпотрібніше тут — важливість сторінки. Досі знахідка на головній і на
забутій сторінці третього рівня важили в пріоритеті однаково, хоча
коштують клієнту різного. Важливість рахується з двох сигналів, які сайт
подає сам: скільки сторінок на неї посилаються й на якій вона глибині.
Жодного зовнішнього джерела, жодного здогаду.

Кількість посилань сама собою не оцінюється: сторінка з трьома
посиланнями не гірша за сторінку з тридцятьма. Значення має лише те,
чого структура не дає — недосяжність, глухий кут, шлях у нікуди.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.audit import applicability
from app.audit.logical_pages import normalize
from app.audit.types import PageSignals, SiteContext


@dataclass(slots=True)
class LinkGraph:
    """Хто на кого посилається, у нормалізованих адресах."""

    incoming: dict[str, int] = field(default_factory=dict)
    outgoing: dict[str, int] = field(default_factory=dict)
    depth: dict[str, int] = field(default_factory=dict)
    # Сторінки, які сайт заявив у карті, але не пов'язав із рештою.
    orphans: list[str] = field(default_factory=list)
    # Внутрішні посилання, що ведуть на сторінку, закриту від індексації.
    to_noindex: list[tuple[str, str]] = field(default_factory=list)

    def importance(self, page: PageSignals) -> float:
        """Наскільки сторінка важлива за версією самого сайту, 0..1.

        Головна — одиниця за побудовою. Далі вирішують вхідні посилання
        (сайт голосує за власні сторінки меню й перелінковкою) і глибина
        (те, що далі від входу, зазвичай і задумувалось як другорядне).

        Це не наша думка про сторінку, а прочитаний намір власника.
        """
        key = normalize(page.url)
        if self.depth.get(key, page.depth) == 0:
            return 1.0

        links = self.incoming.get(key, 0)
        most = max(self.incoming.values(), default=0)
        by_links = links / most if most else 0.0

        level = self.depth.get(key, page.depth)
        by_depth = 1.0 / (1 + level)

        # Посилання важать більше за глибину: сторінка, на яку веде все
        # меню, важлива навіть якщо лежить глибоко.
        return round(min(1.0, 0.65 * by_links + 0.35 * by_depth), 3)


def build(ctx: SiteContext) -> LinkGraph:
    graph = LinkGraph()
    known = {normalize(p.url): p for p in ctx.ok_pages}
    for variant_owner in ctx.ok_pages:
        for variant in variant_owner.url_variants:
            known.setdefault(normalize(variant), variant_owner)

    for page in ctx.ok_pages:
        source = normalize(page.url)
        graph.depth[source] = page.depth
        # Посилання з відповіді сервера плюс ті, що домальовує JS. Не
        # заміна, а обʼєднання: рендер бачили не для кожної сторінки, і
        # там, де його не було, статичний перелік лишається всім, що є.
        # Без цього сторінка, знайдена лише через рендер, виглядала б
        # сиротою — при тому, що ми на власні очі бачили посилання на неї.
        links = list(page.links)
        rendered = ctx.renders.get(page.url)
        if rendered is not None and rendered.signals is not None:
            links.extend(rendered.signals.links)
        targets = {
            normalize(link.url)
            for link in links
            if link.is_internal and normalize(link.url) != source
        }
        graph.outgoing[source] = len(targets)
        for target in targets:
            graph.incoming[target] = graph.incoming.get(target, 0) + 1
            destination = known.get(target)
            if (
                destination is not None
                and "noindex" in (destination.meta_robots or "")
                # Посилання на власний вхід, кошик, кабінет чи сторінку
                # помилки — не вада: їхня закритість від пошуку і є задум,
                # і сайт мусить на них посилатися, щоб ними користувались.
                # Вадою лишається посилання на ЗАКРИТИЙ ВМІСТ: стаття під
                # `noindex`, на яку сайт водить читача, — саме той випадок,
                # заради якого чек існує.
                and not applicability.service_route(ctx, destination)
            ):
                graph.to_noindex.append((page.url, destination.url))

    graph.orphans = _orphans(ctx, graph, known)
    return graph


def _orphans(ctx: SiteContext, graph: LinkGraph, known: dict[str, PageSignals]) -> list[str]:
    """Сторінки з карти сайту, на які не веде жодне внутрішнє посилання.

    Судимо лише про те, що прочитали: сторінка, на яку посилається
    непрочитана нами сторінка, сиротою не є, і назвати її такою означало б
    описати нашу вибірку замість сайту. Тому беремо адреси з карти, які
    ми відкривали, — про них ми знаємо і що вони існують, і хто на них
    посилається серед прочитаного.
    """
    from_sitemap = {normalize(u) for u in ctx.sitemap.urls}
    if not from_sitemap:
        return []
    return sorted(
        known[key].url
        for key in from_sitemap & set(known)
        if graph.depth.get(key, 1) > 0 and not graph.incoming.get(key)
    )


__all__ = ["LinkGraph", "build"]
