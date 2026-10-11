"""Що карта сайту заявляє проти того, що ми побачили на власні очі.

## Що це, а що ні

Карта — це заявка власника: «ось адреси, які варто знайти». Тут вона
звіряється з тим, що краул справді отримав за цими адресами. Жодного
нового збору: статус, перенаправлення, `noindex` і canonical уже лежать
у `PageSignals`, а ланцюг розбирає `redirects.py`.

Це **не** твердження про індексацію. Наявність у карті нічого не
гарантує, а відсутність нічого не забороняє: карта — підказка, і Google
пише про неї саме так. Тому все, що тут є, — це неузгодженість між двома
джерелами на самому сайті.

## Дві межі, які тримають чесність

**Не відкривали ≠ зламано.** Адреса з карти, до якої не дійшов бюджет
краулу, не потрапляє в жодну знахідку. Вона рахується в `unchecked`, і
це число завжди поруч із висновком: сказати «карта чиста», прочитавши
20 адрес із 20 000, було б неправдою про сайт.

**Одна адреса — одна причина.** Сторінка буває водночас `noindex` і з
canonical на іншу; це один корінь і одна дія, а не дві. Причини
впорядковані за пріоритетом, і в знахідку йде найважча; решта лишається
в доказі поруч.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.audit import applicability, redirects
from app.audit.frontier import SKIP_EXTENSIONS
from app.audit.logical_pages import normalize
from app.audit.types import PageSignals


class Reason(StrEnum):
    """Чому адреса з карти не узгоджується з побаченим."""

    # Сервер відповів кодом помилки.
    ERROR = "error"
    # Адреса веде не туди, де врешті лежить сторінка.
    REDIRECTS = "redirects"
    # Сторінка є, але закрита від пошуку.
    NOINDEX = "noindex"
    # Сторінка сама каже, що головна — інша адреса.
    CANONICAL = "canonical"
    # Службова сторінка: вхід, кошик, архів. У карті їй нема чого робити.
    NOT_FOR_SEARCH = "not_for_search"


# Порядок = пріоритет. Найважче першим: адреса, яка не відповідає,
# важливіша за адресу, яка відповідає не тим canonical.
ORDER = (
    Reason.ERROR,
    Reason.REDIRECTS,
    Reason.NOINDEX,
    Reason.CANONICAL,
    Reason.NOT_FOR_SEARCH,
)


@dataclass(frozen=True, slots=True)
class Entry:
    """Одна адреса з карти й усе, що ми про неї знаємо."""

    url: str
    normalized: str
    # Файли карти, у яких вона трапилась. Порожньо — знімок старший за
    # поле походження, і це «невідомо», а не «жодного».
    sources: tuple[str, ...]
    observed: bool
    status: int | None = None
    reasons: tuple[Reason, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def primary(self) -> Reason | None:
        for reason in ORDER:
            if reason in self.reasons:
                return reason
        return None

    def as_evidence(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "reasons": [r.value for r in self.reasons],
            "sitemaps": list(self.sources),
            **self.detail,
        }


@dataclass(slots=True)
class Audit:
    """Звірка карти з побаченим, разом із межами цієї звірки."""

    entries: list[Entry] = field(default_factory=list)
    # Скільки адрес карта заявляє взагалі — до нашого зрізу й бюджету.
    declared: int = 0
    # Чи знаємо ми, з яких файлів походять адреси.
    provenance_known: bool = True
    is_index: bool = False
    children_read: int = 0
    children_total: int = 0
    # Чи бачили ми індекс цілком. Хибно — усі числа нижче описують
    # прочитану частину, і жодне твердження не про всю карту.
    index_complete: bool = True
    # Адреси карти, які сторінками не є: картинки, файли. Судити їх
    # правилами для сторінок — помилка категорії, а не знахідка.
    non_pages: int = 0

    @property
    def checked(self) -> int:
        return sum(1 for e in self.entries if e.observed)

    @property
    def unchecked(self) -> int:
        return max(0, self.declared - self.checked)

    @property
    def inconsistent(self) -> list[Entry]:
        return [e for e in self.entries if e.reasons]

    def by_reason(self) -> dict[Reason, list[Entry]]:
        """Знахідки, згруповані за головною причиною кожної адреси.

        Саме головною, а не всіма: інакше та сама сторінка потрапляла б
        у дві групи, і клієнт бачив би дві дії там, де дія одна.
        """
        out: dict[Reason, list[Entry]] = {}
        for entry in self.inconsistent:
            reason = entry.primary
            if reason is not None:
                out.setdefault(reason, []).append(entry)
        return out

    def coverage(self) -> dict[str, Any]:
        """Межі звірки — поруч із висновком, а не в примітці."""
        return {
            "declared": self.declared,
            "checked": self.checked,
            "unchecked": self.unchecked,
            "inconsistent": len(self.inconsistent),
            "provenance_known": self.provenance_known,
            "sitemap_is_index": self.is_index,
            "children_read": self.children_read,
            "children_total": self.children_total,
            "index_complete": self.index_complete,
            "non_pages": self.non_pages,
        }


def _observed(ctx: Any) -> dict[str, PageSignals]:
    """Нормалізована адреса → сторінка, яку ми за нею отримали.

    Варіанти теж: логічне зведення могло скласти `/a` і `/a/` в одну
    сторінку, і адреса з карти може вказувати на будь-який із них.
    """
    found: dict[str, PageSignals] = {}
    for page in ctx.pages:
        found.setdefault(normalize(page.url), page)
        for variant in page.url_variants:
            found.setdefault(normalize(variant), page)
        if page.redirected_from:
            found.setdefault(normalize(page.redirected_from), page)
    return found


def _reasons_for(
    ctx: Any,
    url: str,
    page: PageSignals,
    observed: dict[str, PageSignals],
    declared: set[str],
) -> tuple[list[Reason], dict[str, Any]]:
    """Причини й доказ для однієї адреси карти."""
    reasons: list[Reason] = []
    detail: dict[str, Any] = {}

    if page.status_code is not None and page.status_code >= 400:
        reasons.append(Reason.ERROR)

    chain = redirects.chain_of(page)
    if chain is not None and normalize(chain.source) == normalize(url) and chain.length > 0:
        reasons.append(Reason.REDIRECTS)
        detail["redirects"] = chain.length
        detail["final_url"] = chain.final_url
        detail["hops"] = [{"status": h.status, "url": h.url} for h in chain.hops]

    # `noindex` очима Google: він виконує JS, тож директиву, дописану
    # скриптом, він бачить. Розбіжність відповіді й DOM — окреме питання,
    # і на нього вже відповідає `seo.render_delta`.
    seen = ctx.as_seen(page)
    directive = (seen.meta_robots or "").lower()
    if "noindex" in directive:
        reasons.append(Reason.NOINDEX)
        detail["meta_robots"] = seen.meta_robots
        detail["noindex_source"] = (
            "render" if seen is not page and "noindex" not in (page.meta_robots or "").lower()
            else "response"
        )

    canonical = (seen.canonical or "").strip()
    if canonical:
        target = normalize(canonical)
        if target != normalize(url) and target != normalize(page.url):
            reasons.append(Reason.CANONICAL)
            detail["canonical"] = canonical
            detail["canonical_normalized"] = target
            detail["canonical_observed"] = target in observed
            # Чи заявлена сама канонічна адреса в карті. Якщо ні —
            # карта вказує на сторінку, яку сайт головною не вважає,
            # і жодної з них там немає в потрібному вигляді.
            detail["canonical_in_sitemap"] = target in declared

    # «Службовій сторінці в карті нема чого робити» — твердження про намір
    # власника, тож намір мусить бути спостережений. Тип адреси його лише
    # припускає: `/checkout`, який сайт САМ подає в карті й індексує, — не
    # службова сторінка, а сторінка, яку власник хоче бачити в пошуку.
    served = bool(page.status_code and 200 <= page.status_code < 300)
    if served and applicability.service_shaped(ctx, page):
        reasons.append(Reason.NOT_FOR_SEARCH)
        detail["page_type"] = str(ctx.type_of(page))
        if not applicability.COMPATIBILITY_MODE:
            # Клас маршруту — новий доказ нової відповіді. У режимі
            # сумісності його не має бути взагалі: доказ старої знахідки
            # мусить збігтися байт у байт із прийнятим.
            detail["route_class"] = applicability.route_of(ctx, page).route_class.value

    return reasons, detail


def collect(ctx: Any) -> Audit:
    """Звірити карту з тим, що краул справді побачив."""
    sitemap = ctx.sitemap
    audit = Audit(
        declared=sitemap.url_count,
        provenance_known=bool(sitemap.sources),
        is_index=sitemap.is_index,
        children_read=len(sitemap.children_read),
        children_total=sitemap.children_total,
        index_complete=sitemap.index_complete,
    )
    if not sitemap.exists or sitemap.parse_error or not sitemap.urls:
        return audit

    observed = _observed(ctx)
    declared = {normalize(u) for u in sitemap.urls}
    # Семантичний дедуплікат: та сама сторінка, записана в карті двічі,
    # — одна адреса з двома джерелами, а не дві знахідки.
    merged: dict[str, list[str]] = {}
    for url in sitemap.urls:
        merged.setdefault(normalize(url), []).append(url)

    for key, written in merged.items():
        # Сумісність зі знімками, знятими до структурного розбору.
        # Тепер картинки не потрапляють у `sitemap.urls` взагалі —
        # `<image:image><image:loc>` розбирається окремо від
        # `<url><loc>`, — але у старих знімках вони там лежать, і без
        # цієї межі перерахунок відтворював би стару ваду: на
        # crustula.com.ua пʼять зниклих світлин виглядали як пʼять
        # зламаних сторінок. Для свіжих аудитів гілка мертва.
        if key.rsplit("?", 1)[0].lower().endswith(SKIP_EXTENSIONS):
            audit.non_pages += 1
            continue

        sources = tuple(dict.fromkeys(sitemap.sources.get(u, "") for u in written if u))
        page = observed.get(key)
        if page is None:
            audit.entries.append(
                Entry(url=written[0], normalized=key, sources=tuple(s for s in sources if s),
                      observed=False)
            )
            continue
        reasons, detail = _reasons_for(ctx, written[0], page, observed, declared)
        if len(written) > 1:
            detail["written_as"] = written
        audit.entries.append(
            Entry(
                url=written[0],
                normalized=key,
                sources=tuple(s for s in sources if s),
                observed=True,
                status=page.status_code,
                reasons=tuple(reasons),
                detail=detail,
            )
        )
    return audit


def in_sitemap(audit: Audit, url: str) -> bool:
    """Чи заявлена ця адреса в карті — за нормалізованим записом."""
    key = normalize(url)
    return any(entry.normalized == key for entry in audit.entries)


__all__ = ["ORDER", "Audit", "Entry", "Reason", "collect", "in_sitemap"]
