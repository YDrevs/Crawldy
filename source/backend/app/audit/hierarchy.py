"""Чи має сайт ієрархію — доведену звʼязком між сторінками, а не глибиною адрес.

## Що було не так

Чек про «хлібні крихти» вважав ієрархією будь-яку прочитану сторінку,
глибшу за вхідну: `p.depth > 0`. Глибина краулу — це наша власна черга, а
не структура сайту. Пекарня з меню на чотири пункти віддавала чотири
сторінки на глибині 1 і отримувала знахідку про відсутні крихти; те саме
діставалося сайтові, який ми прочитали наполовину, і сайтові, у якого
взагалі немає сторінок для пошуку.

Виміряно на девʼятнадцяти канонічних випадках: девʼять станів із
пʼятнадцяти були неправильні, сім знахідок — хибні.

## Що доводить ієрархію

**Один перевірений звʼязок «батько → дитина» між різними придатними
сторінками.** Одного досить, і жодного числа тут немає: ані мінімуму
дітей, ані мінімуму сторінок, ані мінімуму розділів. Попередня редакція
контракту вимагала «три або більше» — це число прибрано, і замінити його
іншим не можна.

Два види звʼязку, і будь-який із них, один раз:

- **R1 — вкладеність шляху ЗІ ЗГАДКОЮ.** Шлях дитини (після зняття
  оголошеної мови) продовжує шлях батька, **і** існує згадка, яка їх
  сполучає: батько посилається на дитину, або розмітка дитини називає
  батька предком (`BreadcrumbList`, `isPartOf`), або видимий слід дитини
  веде на батька.
- **R2 — розділ до одиниці.** Сторінка-перелік (LISTING/ARCHIVE)
  посилається на товар чи статтю, або розмітка дитини називає її своїм
  розділом. Форма адрес тут не важить: плаский набір адрес зі справжньою
  структурою «розділ → товар» — це ієрархія.

**Сама глибина не доводить нічого.** `/a/b` і `/c/d` без жодної згадки —
це дві адреси, а не дерево. Згрупований жирним шрифтом меню-блок, чий
заголовок не є сторінкою, теж нічого не доводить: групування — це
оформлення, а звʼязок мусить вести на сторінку, яку ми бачили.

## Що НЕ придатне

Корінь сайту (він предок усього й тому не доводить нічого), пагінація,
мовні корені (шляхи порівнюються вже без оголошеного префікса, тож `/de`
не батько `/de/about`), а також воронка, кабінет, адмінка, службові й
помилкові маршрути.

## Чому «не знаємо» — окремий стан

Плаский сайт і напівпрочитаний сайт виглядають однаково: в обох немає
доведеного звʼязку. Різниця в тому, чи ми ДИВИЛИСЯ. Тому `FLAT` вимагає
повного покриття придатних сторінок і ствердної відсутності звʼязку, а
неповне покриття дає `UNKNOWN` — і ніколи не `FLAT`.

## Важіль відкату

Класифікації немає без двох таблиць: придатних класів маршруту й видів
звʼязку. Порожні — `classify()` віддає `None`, і кожна гілка споживача
згасає сама: чек не судить, гачок застосовності не спрацьовує. Та сама
побудова, що в `applicability.COMPATIBILITY_MODE` і `about_page.AVAILABLE`
— відкат одним важелем, без зворотних правок у споживачах.

## Чого тут немає

Власного правила «той самий сайт», власної нормалізації адрес, власного
зняття мовного префікса й власного класифікатора маршрутів. Усе це вже є
в `site_scope`, `logical_pages` і `page_kinds`/`route_classes`, і E-15
питає саме їх. Друге місце з тією самою відповіддю розійшлося б із
першим — на цьому проєкт уже губив сторінки.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.audit import breadcrumbs
from app.audit.applicability import ClaimVerdict, Coverage
from app.audit.enums import DegradationKind
from app.audit.logical_pages import normalize
from app.audit.page_kinds import PageType
from app.audit.route_classes import INTENT_CONFIRMED_CLASSES, RouteClass, classify_route
from app.audit.site_scope import SiteScope
from app.audit.types import Degradation, Module, PageSignals, SiteContext

# ── Важіль відкату ────────────────────────────────────────────────────────
# Дві таблиці, без яких класифікувати нема чого. Прибрати їх — і модуль
# стає інертним, а споживачі гаснуть без зворотної правки.

#: Класи маршруту, чиї сторінки взагалі можуть стояти в ієрархії.
ELIGIBLE_ROUTE_CLASSES: frozenset[RouteClass] = frozenset({
    RouteClass.PUBLIC_INDEXABLE_CONTENT,
    RouteClass.PUBLIC_NOINDEX_INFORMATIONAL,
    RouteClass.PUBLIC_SHAREABLE_CONTENT,
})

#: Види перевіреного звʼязку, іменами контракту.
R1 = "R1_path_nesting_with_link"
R2 = "R2_category_to_item"
RELATIONSHIP_KINDS: tuple[str, ...] = (R1, R2)

AVAILABLE = bool(ELIGIBLE_ROUTE_CLASSES and RELATIONSHIP_KINDS)

#: Чек, якому належить ця претензія. Один рядок, щоб деградація, доказ і
#: рядок застосовності називали його однаково.
CHECK = "ai.schema.breadcrumb"

#: Класифікації контракту.
HIERARCHY_EVIDENT = "HIERARCHY_EVIDENT"
FLAT = "FLAT"
UNKNOWN = "UNKNOWN"
NOT_APPLICABLE = "NOT_APPLICABLE"

#: Коди причин `contracts/E05-APPLICABILITY-CONTRACT.md`.
A09_NO_RELATIONSHIP = "A-09"
A10_NO_ELIGIBLE_PAGES = "A-10"

#: Ключ каталогу, яким прогалина називається читачеві. Один, бо стан один:
#: контракт оголошує `module_partial` для UNKNOWN і лише для нього. Доведена
#: ієрархія з непрочитаним обсягом називає свій непрочитаний обсяг сама —
#: покриттям PARTIAL і переліком адрес у рядку застосовності.
NOTICE_UNKNOWN = "notice.breadcrumb.hierarchy_unknown"

#: Типи сторінок, які можуть бути батьком і дитиною в R2.
SECTION_TYPES = frozenset({PageType.LISTING, PageType.ARCHIVE})
ITEM_TYPES = frozenset({PageType.PRODUCT, PageType.ARTICLE})

#: Класи, чий маршрут не може стояти в ієрархії навіть непрочитаним:
#: намір власника тримати їх поза пошуком уже підтверджено формою.
_INELIGIBLE_SHAPES = frozenset(INTENT_CONFIRMED_CLASSES | {RouteClass.ERROR_TRANSIENT})


@dataclass(frozen=True, slots=True)
class Relationship:
    """Один перевірений звʼязок «батько → дитина»."""

    parent: str
    child: str
    kinds: tuple[str, ...]
    reference: str

    def as_evidence(self) -> dict[str, Any]:
        return {"parent": self.parent, "child": self.child, "kinds": list(self.kinds),
                "verified_by": self.reference}


@dataclass(frozen=True, slots=True)
class Hierarchy:
    """Рішення E-15 цілком: класифікація, її докази і стан претензії."""

    classification: str
    relationships: tuple[Relationship, ...]
    # Прочитані сторінки ВМІСТУ — ширше за придатні: сюди входять корінь,
    # мовні корені й пагінація. На цьому полі, і лише на ньому, тримається
    # різниця між A-10 і A-09.
    content: tuple[str, ...]
    eligible: tuple[str, ...]
    unread_eligible: tuple[str, ...]
    unread_sitemap_children: int
    supporting: tuple[str, ...]
    pages: tuple[breadcrumbs.PageTrails, ...]
    verdict: ClaimVerdict
    coverage: Coverage
    rule: str | None
    notice: str | None

    @property
    def coverage_complete(self) -> bool:
        return not self.unread_eligible and not self.unread_sitemap_children

    @property
    def valid_trail_pages(self) -> tuple[str, ...]:
        return tuple(record.url for record in self.pages if record.valid)

    @property
    def conclusive(self) -> bool:
        """Претензія вирішена: є вердикт і покриття повне."""
        return (self.verdict in (ClaimVerdict.PASS, ClaimVerdict.FAIL)
                and self.coverage is Coverage.COMPLETE)

    @property
    def finding(self) -> bool:
        """Знахідка є рівно тоді, коли ієрархія доведена, а дійсного сліду немає."""
        return self.classification == HIERARCHY_EVIDENT and not self.valid_trail_pages

    @property
    def missing_evidence(self) -> tuple[str, ...]:
        """Чого саме бракує — фактами, а не ключем каталогу.

        Ключ каталогу — це ручка подання: він стає текстом там, де є мова
        читача. У доказі стоїть сам факт, і він однаковий шістьма мовами.
        """
        missing = []
        if self.unread_eligible:
            missing.append("eligible_pages_not_read")
        if self.unread_sitemap_children:
            missing.append("sitemap_index_not_read_completely")
        if not missing and self.classification == UNKNOWN:
            missing.append("only_supporting_evidence_was_observed")
        return tuple(missing)

    @property
    def unread_applicable(self) -> int:
        """Скільки придатного лишилось непрочитаним і ще може змінити відповідь.

        Нуль після PASS: екзистенційну претензію закриває одне достатнє
        спостереження, і непрочитане вже не може її перевернути.
        """
        if self.verdict is ClaimVerdict.PASS:
            return 0
        return len(self.unread_eligible) + self.unread_sitemap_children

    def as_evidence(self) -> dict[str, Any]:
        """Доказ рішення. Часток і відсотків тут немає — лише переліки."""
        return {
            "classification": self.classification,
            "relationships": [r.as_evidence() for r in self.relationships],
            "relationship_kinds": sorted({k for r in self.relationships for k in r.kinds}),
            "content_pages": list(self.content),
            "eligible_pages": list(self.eligible),
            "unread_eligible_pages": list(self.unread_eligible),
            "unread_sitemap_children": self.unread_sitemap_children,
            "eligible_coverage_complete": self.coverage_complete,
            "supporting_evidence_only": list(self.supporting),
            # Посторінкове покриття крихт — ІНФОРМАЦІЙНО. Жодна частка
            # звідси нічого не вирішує: PASS дає сам факт дійсного сліду.
            "breadcrumb_coverage": [record.as_evidence() for record in self.pages],
            "pages_with_a_valid_breadcrumblist": list(self.valid_trail_pages),
            "verdict": self.verdict.value,
            "coverage": self.coverage.value,
            "rule": self.rule,
            "missing_evidence": list(self.missing_evidence),
            "conclusive": self.conclusive,
            "unread_applicable": self.unread_applicable,
        }


# ── придатність ───────────────────────────────────────────────────────────

def _chunks(ctx: SiteContext, url: str) -> list[str]:
    """Сегменти шляху без ОГОЛОШЕНОЇ мови — правилом G4a, не власним.

    `_route_chunks` приватна, і береться вона свідомо: контракт вимагає
    порівнювати шляхи «after the E-12 declared-locale stripping» і прямо
    забороняє E-15 нести власне правило. Друга реалізація того самого
    зняття розійшлася б із першою на першому ж сайті, що оголошує мову
    інакше, ніж я вгадав.
    """
    from app.audit.page_kinds import _route_chunks

    chunks, _locale, _basis = _route_chunks(url, ctx.declared_locales())
    return chunks


def _is_pagination(ctx: SiteContext, url: str) -> bool:
    """Правило пагінації двигуна, а не власне."""
    from app.audit.page_kinds import _is_pagination as engine_rule

    return engine_rule(_chunks(ctx, url))


def _content_page(ctx: SiteContext, page: PageSignals) -> bool:
    """Чи є ця прочитана сторінка ВМІСТОМ — питання про маршрут, не про місце.

    Окремо від придатності навмисно. «Сайт, у якого немає сторінок вмісту
    взагалі» (A-10) і «сайт, у якого одна сторінка вмісту» (A-09) — різні
    відповіді, і злити їх означає сказати про односторінковий сайт, що
    вмісту в нього немає. Саме це й сталося на пʼятьох сайтах вибірки,
    кожен з яких віддав рівно головну сторінку з кодом 200.
    """
    from app.audit.route_classes import classify_page

    return classify_page(ctx, page).route_class in ELIGIBLE_ROUTE_CLASSES


def _eligible_page(ctx: SiteContext, page: PageSignals) -> bool:
    """Чи може ця ПРОЧИТАНА сторінка стояти в ієрархії.

    Вужче за «бути вмістом»: корінь сайту, корінь мовної версії й сторінка
    пагінації — це вміст, який не може бути БАТЬКОМ.
    """
    if not _content_page(ctx, page):
        return False
    chunks = _chunks(ctx, page.url)
    # Порожні сегменти — це корінь сайту або корінь мовної версії. Ані
    # той, ані той не доводить ієрархії: перший предок усього, другий —
    # початок своєї копії сайту, а не розділ над нею.
    return bool(chunks) and not _is_pagination(ctx, page.url)


def _could_be_eligible(ctx: SiteContext, url: str) -> bool:
    """Чи могла б НЕПРОЧИТАНА адреса виявитись придатною сторінкою.

    Тут навмисно не стверджується, що вона придатна: клас маршруту
    визначається з фактів відповіді, а відповіді немає. Стверджується
    слабше й чесніше — що виключити її ми не можемо, і саме це означає
    «покриття неповне». Виключаються лише ті адреси, чия ФОРМА вирішує
    питання без відповіді: пагінація, корінь, воронка, кабінет, адмінка,
    службовий і помилковий маршрут.
    """
    chunks = _chunks(ctx, url)
    if not chunks or _is_pagination(ctx, url):
        return False
    shape = classify_route(url, locales=tuple(ctx.declared_locales())).shape
    return shape not in _INELIGIBLE_SHAPES


def _known_urls(ctx: SiteContext, scope: SiteScope) -> set[str]:
    """Кожна внутрішня адреса, про яку ми дізналися: посилання й карта сайту."""
    known: set[str] = set()
    for page in ctx.ok_pages:
        for link in page.links or ():
            target = (link.url or "").strip()
            if target and scope.contains(target):
                known.add(normalize(target))
    for url in getattr(ctx.sitemap, "urls", ()) or ():
        target = (url or "").strip()
        if target and scope.contains(target):
            known.add(normalize(target))
    return known


def _unread_sitemap_children(ctx: SiteContext) -> int:
    """Скільки файлів карти лишилось невідкритими — збирач каже це сам."""
    sitemap = ctx.sitemap
    if not getattr(sitemap, "is_index", False) or getattr(sitemap, "index_complete", True):
        return 0
    total = int(getattr(sitemap, "children_total", 0) or 0)
    read = len(getattr(sitemap, "children_read", ()) or ())
    return max(total - read, 0)


# ── звʼязки ───────────────────────────────────────────────────────────────

def _extends(child: list[str], parent: list[str]) -> bool:
    """Чи ВЛАСНЕ продовжує шлях дитини шлях батька."""
    return len(child) > len(parent) and child[:len(parent)] == parent


def _relationship(
    ctx: SiteContext,
    parent: PageSignals,
    child: PageSignals,
    *,
    links: dict[str, set[str]],
    ancestors: dict[str, set[str]],
    chunks: dict[str, list[str]],
) -> Relationship | None:
    """Перевірений звʼязок між двома придатними сторінками, або нічого."""
    parent_key, child_key = normalize(parent.url), normalize(child.url)
    parent_links_to_child = child_key in links.get(parent_key, set())
    child_names_parent = parent_key in ancestors.get(child_key, set())
    # Видимий слід дитини веде на батька: збережений факт `breadcrumb_ui`
    # каже, що слід є, а граф посилань — що він веде саме туди.
    child_ui_points_at_parent = (
        bool(getattr(child, "breadcrumb_ui", False))
        and parent_key in links.get(child_key, set())
    )

    kinds: list[str] = []
    reference = ""
    if _extends(chunks[child_key], chunks[parent_key]):
        if parent_links_to_child:
            kinds.append(R1)
            reference = "the parent links to the child"
        elif child_names_parent:
            kinds.append(R1)
            reference = "the child's structured data names the parent as an ancestor"
        elif child_ui_points_at_parent:
            kinds.append(R1)
            reference = "the child's breadcrumb UI links to the parent"

    if ctx.type_of(parent) in SECTION_TYPES and ctx.type_of(child) in ITEM_TYPES:
        if parent_links_to_child:
            kinds.append(R2)
            reference = reference or "a section page links to an item page"
        elif child_names_parent:
            kinds.append(R2)
            reference = reference or "the item's structured data names its section"

    if not kinds:
        return None
    return Relationship(parent=parent.url, child=child.url, kinds=tuple(kinds),
                        reference=reference)


def _supporting(ctx: SiteContext, eligible: list[PageSignals],
                relationships: list[Relationship], chunks: dict[str, list[str]]) -> list[str]:
    """Що ми бачили, але чого замало. Записується, щоб мовчання мало причину."""
    notes: list[str] = []
    if not relationships:
        keys = {normalize(page.url) for page in eligible}
        if any(_extends(chunks[a], chunks[b]) for a in keys for b in keys if a != b):
            notes.append("eligible paths nest, but no connecting reference was observed")
        # "has a parent path at all" — said with the path itself rather than with a
        # number, because a number here would be a threshold whatever it decided.
        if any(chunks[key][:-1] for key in keys):
            notes.append("deep URLs exist, which on their own prove no relationship")
    if any(bool(getattr(page, "breadcrumb_ui", False)) for page in eligible):
        notes.append("a visible breadcrumb trail was seen on at least one page")
    return notes


# ── рішення ───────────────────────────────────────────────────────────────

def classify(ctx: SiteContext) -> Hierarchy | None:
    """Рішення E-15 для цього сайту. `None` — модуль інертний (відкат)."""
    if not AVAILABLE:
        return None

    scope = SiteScope.from_url(ctx.entry_url or ctx.origin or "")
    if not scope.is_valid:
        scope = SiteScope.from_url(ctx.origin or "")

    # Порядок обходу — наш, а не сайту: краул приносить сторінки хвилями, і доказ,
    # відсортований ним, не можна порівняти із самим собою між прогонами.
    content = [page for page in ctx.ok_pages if _content_page(ctx, page)]
    eligible = sorted((page for page in ctx.ok_pages if _eligible_page(ctx, page)),
                      key=lambda page: normalize(page.url))
    read_keys = {normalize(page.url) for page in ctx.ok_pages}
    unread = sorted(
        url for url in _known_urls(ctx, scope)
        if url not in read_keys and _could_be_eligible(ctx, url)
    )
    unread_children = _unread_sitemap_children(ctx)

    chunks = {normalize(page.url): _chunks(ctx, page.url) for page in eligible}
    links = {
        normalize(page.url): {
            normalize(link.url) for link in (page.links or ())
            if (link.url or "").strip() and scope.contains(link.url)
        }
        for page in ctx.ok_pages
    }
    ancestors = {normalize(page.url): breadcrumbs.ancestors_named(page) for page in eligible}

    relationships: list[Relationship] = []
    for parent in eligible:
        for child in eligible:
            if normalize(parent.url) == normalize(child.url):
                continue
            found = _relationship(ctx, parent, child, links=links, ancestors=ancestors,
                                  chunks=chunks)
            if found is not None:
                relationships.append(found)

    entry = ctx.entry_url or ctx.origin or ""
    pages = tuple(breadcrumbs.read(page, entry=entry) for page in eligible)
    complete = not unread and not unread_children

    if not content and not unread and not unread_children:
        # Жодного маршруту вмісту — не «жодного батька». Односторінковий
        # сайт має вміст і не має ієрархії, і це A-09, а не A-10.
        classification = NOT_APPLICABLE
    elif relationships:
        classification = HIERARCHY_EVIDENT
    elif complete:
        classification = FLAT
    else:
        classification = UNKNOWN

    valid_trail = any(record.valid for record in pages)
    rule: str | None = None
    notice: str | None = None
    if classification == HIERARCHY_EVIDENT:
        if valid_trail:
            # Екзистенційна претензія: один дійсний слід її закриває, і
            # непрочитані сусіди вже не можуть її перевернути.
            verdict, coverage = ClaimVerdict.PASS, Coverage.COMPLETE
        else:
            verdict = ClaimVerdict.FAIL
            coverage = Coverage.COMPLETE if complete else Coverage.PARTIAL
    elif classification == FLAT:
        verdict, coverage, rule = (ClaimVerdict.NOT_APPLICABLE, Coverage.COMPLETE,
                                   A09_NO_RELATIONSHIP)
    elif classification == NOT_APPLICABLE:
        verdict, coverage, rule = (ClaimVerdict.NOT_APPLICABLE, Coverage.COMPLETE,
                                   A10_NO_ELIGIBLE_PAGES)
    else:
        verdict, coverage = ClaimVerdict.NO_VERDICT, Coverage.PARTIAL
        notice = NOTICE_UNKNOWN

    return Hierarchy(
        classification=classification,
        relationships=tuple(sorted(relationships,
                                   key=lambda r: (r.parent, r.child, r.kinds))),
        content=tuple(sorted(page.url for page in content)),
        eligible=tuple(page.url for page in eligible),
        unread_eligible=tuple(unread),
        unread_sitemap_children=unread_children,
        supporting=tuple(_supporting(ctx, eligible, relationships, chunks)),
        pages=pages,
        verdict=verdict,
        coverage=coverage,
        rule=rule,
        notice=notice,
    )


def degradation(decision: Hierarchy | None) -> Degradation | None:
    """Прогалина для `missing_data` — лише для стану без вердикту.

    Та сама побудова, що в `about_page.degradation`: рішення ухвалює
    детектор, оркестратор лише переносить його в деградацію, і ключ
    каталогу їде в `reason_key`, де його чекає рендер. У доказ він не
    потрапляє ніколи — сирий ключ у звіті це сирий ключ у звіті.
    """
    if decision is None or decision.notice is None:
        return None
    return Degradation(
        scope=CHECK,
        kind=DegradationKind.PARTIAL_DATA,
        reason=("ієрархію сайту не встановлено: "
                + ", ".join(decision.missing_evidence or ("немає доказів",))),
        affected_modules=[Module.AI_READY],
        reason_key=decision.notice,
        reason_params={},
    )


__all__ = [
    "A09_NO_RELATIONSHIP",
    "A10_NO_ELIGIBLE_PAGES",
    "AVAILABLE",
    "CHECK",
    "ELIGIBLE_ROUTE_CLASSES",
    "FLAT",
    "HIERARCHY_EVIDENT",
    "ITEM_TYPES",
    "NOTICE_UNKNOWN",
    "NOT_APPLICABLE",
    "R1",
    "R2",
    "RELATIONSHIP_KINDS",
    "SECTION_TYPES",
    "UNKNOWN",
    "Hierarchy",
    "Relationship",
    "classify",
    "degradation",
]
