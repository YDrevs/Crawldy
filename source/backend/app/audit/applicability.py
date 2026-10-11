"""Чи стосується це твердження цього маршруту (E-05).

Політика, а не класифікація. `route_classes` відповідає «що це за маршрут»;
тут — «чи має claim-клас X що сказати про маршрут класу Y». Розділення
навмисне: інакше зміна політики вимагала б правки класифікатора, а новий
словник маршрутів мовчки рухав би політику.

## Чому це мусить бути в одному місці

Доти застосовність жила розсипом усередині чеків: кожен сам вирішував, на
яких сторінках його правило має сенс, і ніхто не бачив картини цілком.
Наслідок був конкретний: відсутній title, суперечливий canonical і великі
літери в адресі рахувались як SEO-штраф на `/login` і `/checkout` — тобто
сайт втрачав бали за те, що його сторінка входу не оптимізована під пошук,
у який вона й не призначена. Тридцять вісім таких знахідок на одному
синтетичному сайті з десяти маршрутів.

Тепер відповідь одна на весь двигун: `(claim_class, route_class) → mode`.
Таблиця 13×8 — копія `contracts/claim-classes.json`, і кожна клітинка
оголошує вісім полів, а не «так/ні».

## Що виключення НЕ означає

Виключений маршрут ніколи не стає пройденою перевіркою. `NOT_APPLICABLE` і
`PASS` — різні стани з різних осей: перший каже «правило сюди не
застосовне», другий — «застосовне й виконується». Сплутати їх означало б
хвалити сайт за сторінки, яких ми не судили; саме тому `passed_checks`
приймає рівно `PASS + COMPLETE`, і жодна стратегія агрегації не має
винятку.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.audit.page_kinds import NOT_FOR_SEARCH
from app.audit.route_classes import (
    ATTRIBUTES,
    INTENT_CONFIRMED_CLASSES,
    RouteClass,
    RouteVerdict,
)


class ClaimVerdict(StrEnum):
    """Вісь ОЦІНКИ (`contracts/state-model.json`).

    Навмисно не `enums.Verdict`: той тримає вердикт ЛЮДИНИ про знахідку
    (погодився, виправив, не робитиму). Два різні поняття під одним іменем
    одного дня передали б одне замість одного.
    """

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    NO_VERDICT = "NO_VERDICT"


class Coverage(StrEnum):
    """Вісь ВИМІРЮВАННЯ: скільки з потрібного ми справді прочитали."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NOT_MEASURED = "NOT_MEASURED"
    EXCLUDED_BY_REQUEST = "EXCLUDED_BY_REQUEST"


class AggregationStrategy(StrEnum):
    ALL_APPLICABLE_PAGES = "ALL_APPLICABLE_PAGES"
    ANY_SUFFICIENT_EVIDENCE = "ANY_SUFFICIENT_EVIDENCE"
    SITE_LEVEL = "SITE_LEVEL"
    ENTRY_PAGE_ONLY = "ENTRY_PAGE_ONLY"


class NoRelevantPage(StrEnum):
    """Що означає «жодної придатної сторінки» для цього чека.

    Пʼять значень `contracts/applicability-source.json`, тими самими іменами.
    Мовчазного дефолта тут немає навмисно: «нема чого судити» буває чотирма
    різними станами, і саме їх злиття робило порожнечу пройденою перевіркою.
    """

    # Немає сторінки судимого роду: NOT_APPLICABLE + COMPLETE, або
    # NO_VERDICT + PARTIAL, якщо непрочитане ще могло б бути застосовним.
    NOT_APPLICABLE_COMPLETE = "NOT_APPLICABLE_COMPLETE"
    # Екзистенційне твердження: відсутність очікуваного — це FAIL.
    FAIL_IF_COMPLETE = "FAIL_IF_COMPLETE"
    # Входу не існувало взагалі: NO_VERDICT + NOT_MEASURED.
    NO_VERDICT_NOT_MEASURED = "NO_VERDICT_NOT_MEASURED"
    # Site-level збирач: судиться завжди.
    ALWAYS_RELEVANT = "ALWAYS_RELEVANT"
    # Вирішує класифікатор ієрархії E-15 (сюди не входить: G5b).
    CLASSIFIER = "CLASSIFIER"


class ClaimClass(StrEnum):
    """Тринадцять claim-класів контракту, тими самими іменами."""

    PAGE_FACT = "PAGE_FACT"
    STRUCTURE_PUBLIC = "STRUCTURE_PUBLIC"
    PUBLIC_CONTENT = "PUBLIC_CONTENT"
    INDEX_ONLY = "INDEX_ONLY"
    SOCIAL_PREVIEW = "SOCIAL_PREVIEW"
    NOINDEX_INTENT = "NOINDEX_INTENT"
    TYPE_GATED_INDEXABLE = "TYPE_GATED_INDEXABLE"
    TYPE_GATED_PUBLIC = "TYPE_GATED_PUBLIC"
    HOME_ONLY = "HOME_ONLY"
    HOME_OR_ABOUT = "HOME_OR_ABOUT"
    HIERARCHY_GATED = "HIERARCHY_GATED"
    SITE_LEVEL = "SITE_LEVEL"
    ENTRY_PAGE_ONLY = "ENTRY_PAGE_ONLY"


class Mode(StrEnum):
    """Чотирнадцять режимів клітинки."""

    EVALUATE = "EVALUATE"
    COND = "COND"
    SITE = "SITE"
    ENTRY = "ENTRY"
    NA_A01 = "NA_A01"
    NA_A02 = "NA_A02"
    NA_A03 = "NA_A03"
    NA_A04 = "NA_A04"
    NA_A05 = "NA_A05"
    NA_A06 = "NA_A06"
    NA_A08 = "NA_A08"
    NA_A12 = "NA_A12"
    NA_A13 = "NA_A13"
    NO_VERDICT_UNKNOWN = "NO_VERDICT_UNKNOWN"


# Коди причин. Рядок — частина контракту й доказу, тож він тут, а не в
# каталозі: каталог перекладають, а код причини читає машина.
REASON_TEXT: dict[str, str] = {
    "R-APPLIES": "applies",
    "R-TYPE-GATE": "type_or_selection_gate",
    "R-SITE-LEVEL": "site_level",
    "R-ENTRY-ONLY": "entry_page_only",
    "R-UNKNOWN-ROUTE-CLASS": "unknown_route_class",
    "A-01": "noindex_not_a_search_target",
    "A-02": "known_non_search_funnel",
    "A-03": "authenticated_account",
    "A-04": "private_admin_system",
    "A-05": "error_or_transient",
    "A-06": "not_shareable",
    "A-08": "noindex_intent_known",
    "A-09": "no_hierarchical_relationship_observed",
    "A-10": "no_eligible_content_pages",
    "A-11": "funnel_shaped_but_indexable",
    "A-12": "no_noindex_observed",
    "A-13": "not_the_selected_page",
}

_A = Mode
_R = RouteClass

# Таблиця 13×8 — копія `contracts/claim-classes.json`. Порядок стовпців той
# самий, що в контракті, щоб рядок можна було звірити очима.
POLICY: dict[ClaimClass, dict[RouteClass, Mode]] = {
    ClaimClass.SITE_LEVEL: dict.fromkeys(RouteClass, _A.SITE),
    ClaimClass.ENTRY_PAGE_ONLY: dict.fromkeys(RouteClass, _A.ENTRY),
    ClaimClass.PAGE_FACT: dict.fromkeys(RouteClass, _A.EVALUATE),
    ClaimClass.STRUCTURE_PUBLIC: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.EVALUATE,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.EVALUATE,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.EVALUATE,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A02,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A03,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A04,
        _R.ERROR_TRANSIENT: _A.NA_A05,
        _R.UNKNOWN_UNCLASSIFIED: _A.NO_VERDICT_UNKNOWN,
    },
    ClaimClass.PUBLIC_CONTENT: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.EVALUATE,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.EVALUATE,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.EVALUATE,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A02,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A03,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A04,
        _R.ERROR_TRANSIENT: _A.NA_A05,
        _R.UNKNOWN_UNCLASSIFIED: _A.NO_VERDICT_UNKNOWN,
    },
    ClaimClass.INDEX_ONLY: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.EVALUATE,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.NA_A01,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.NA_A01,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A02,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A03,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A04,
        _R.ERROR_TRANSIENT: _A.NA_A05,
        _R.UNKNOWN_UNCLASSIFIED: _A.NO_VERDICT_UNKNOWN,
    },
    # Соціальне прев'ю застосовне рівно там, де маршрут спільний. Публічний
    # `noindex` цього не скасовує: сторінку без пошуку все одно надсилають
    # у месенджері, і картка їй потрібна.
    ClaimClass.SOCIAL_PREVIEW: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.EVALUATE,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.EVALUATE,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.EVALUATE,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A06,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A06,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A06,
        _R.ERROR_TRANSIENT: _A.NA_A06,
        _R.UNKNOWN_UNCLASSIFIED: _A.NO_VERDICT_UNKNOWN,
    },
    ClaimClass.NOINDEX_INTENT: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.NA_A12,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.COND,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.COND,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A08,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A08,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A08,
        _R.ERROR_TRANSIENT: _A.NA_A05,
        _R.UNKNOWN_UNCLASSIFIED: _A.NO_VERDICT_UNKNOWN,
    },
    ClaimClass.TYPE_GATED_INDEXABLE: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.COND,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.NA_A01,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.NA_A01,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A02,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A03,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A04,
        _R.ERROR_TRANSIENT: _A.NA_A05,
        _R.UNKNOWN_UNCLASSIFIED: _A.NO_VERDICT_UNKNOWN,
    },
    ClaimClass.TYPE_GATED_PUBLIC: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.COND,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.COND,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.COND,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A02,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A03,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A04,
        _R.ERROR_TRANSIENT: _A.NA_A05,
        _R.UNKNOWN_UNCLASSIFIED: _A.NO_VERDICT_UNKNOWN,
    },
    ClaimClass.HOME_ONLY: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.COND,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.NA_A13,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.NA_A13,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A13,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A13,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A13,
        _R.ERROR_TRANSIENT: _A.NA_A13,
        _R.UNKNOWN_UNCLASSIFIED: _A.NA_A13,
    },
    ClaimClass.HOME_OR_ABOUT: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.COND,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.COND,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.COND,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A13,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A13,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A13,
        _R.ERROR_TRANSIENT: _A.NA_A13,
        _R.UNKNOWN_UNCLASSIFIED: _A.NA_A13,
    },
    ClaimClass.HIERARCHY_GATED: {
        _R.PUBLIC_INDEXABLE_CONTENT: _A.COND,
        _R.PUBLIC_NOINDEX_INFORMATIONAL: _A.COND,
        _R.PUBLIC_SHAREABLE_CONTENT: _A.COND,
        _R.KNOWN_NON_SEARCH_FUNNEL: _A.NA_A02,
        _R.AUTHENTICATED_ACCOUNT: _A.NA_A03,
        _R.PRIVATE_ADMIN_SYSTEM: _A.NA_A04,
        _R.ERROR_TRANSIENT: _A.NA_A05,
        _R.UNKNOWN_UNCLASSIFIED: _A.NO_VERDICT_UNKNOWN,
    },
}

# Шість полів, які оголошує кожен режим (`contracts/claim-classes.json`).
_EVALUATING = (True, True, True)
MODE_FIELDS: dict[Mode, tuple[bool, bool, bool, str | None, str, str]] = {
    _A.EVALUATE: (*_EVALUATING, None, "applicability.evaluated", "R-APPLIES"),
    _A.COND: (*_EVALUATING,
              "NOT_APPLICABLE + COMPLETE when the check's own type or selection gate is not met",
              "applicability.evaluated when the gate is met, applicability.not_applicable with "
              "the gate's reason otherwise",
              "R-TYPE-GATE"),
    _A.SITE: (*_EVALUATING, None, "site-level collector result", "R-SITE-LEVEL"),
    _A.ENTRY: (*_EVALUATING, None, "entry-page measurement", "R-ENTRY-ONLY"),
    _A.NO_VERDICT_UNKNOWN: (True, False, False, "NO_VERDICT + PARTIAL",
                            "missing_data (PARTIAL_DATA): route purpose undecided",
                            "R-UNKNOWN-ROUTE-CLASS"),
}
for _mode, _code in (
    (_A.NA_A01, "A-01"), (_A.NA_A02, "A-02"), (_A.NA_A03, "A-03"), (_A.NA_A04, "A-04"),
    (_A.NA_A05, "A-05"), (_A.NA_A06, "A-06"), (_A.NA_A08, "A-08"), (_A.NA_A12, "A-12"),
    (_A.NA_A13, "A-13"),
):
    MODE_FIELDS[_mode] = (True, False, False, "NOT_APPLICABLE + COMPLETE",
                          "applicability.not_applicable", _code)


@dataclass(frozen=True, slots=True)
class Declaration:
    """Вісім полів однієї клітинки (чек × варіант × клас маршруту)."""

    claim_class: ClaimClass
    aggregation_strategy: AggregationStrategy
    mode: Mode
    executes: bool
    can_emit_factual_finding: bool
    score_affecting: bool
    result_when_not_applicable: str | None
    coverage_contribution: str
    reason_code: str

    @property
    def applies(self) -> bool:
        """Чи може ця клітинка дати знахідку, що впливає на бал."""
        return self.can_emit_factual_finding and self.score_affecting

    @property
    def reason(self) -> str:
        return REASON_TEXT.get(self.reason_code, self.reason_code)

    def as_evidence(self) -> dict[str, Any]:
        return {
            "claim_class": self.claim_class.value,
            "aggregation_strategy": self.aggregation_strategy.value,
            "mode": self.mode.value,
            "executes": self.executes,
            "can_emit_factual_finding": self.can_emit_factual_finding,
            "score_affecting": self.score_affecting,
            "result_when_not_applicable": self.result_when_not_applicable,
            "coverage_contribution": self.coverage_contribution,
            "reason_code": self.reason_code,
            "reason": self.reason,
        }


def mode_for(claim_class: ClaimClass, route_class: RouteClass) -> Mode:
    """Режим клітинки. Порожньої клітинки в таблиці немає за побудовою."""
    return POLICY[claim_class][route_class]


def declaration_for(
    claim_class: ClaimClass,
    route_class: RouteClass,
    aggregation_strategy: AggregationStrategy,
) -> Declaration:
    """Вісім полів для (claim-клас, клас маршруту, стратегія)."""
    mode = mode_for(claim_class, route_class)
    executes, factual, scoring, when_na, coverage, reason = MODE_FIELDS[mode]
    return Declaration(
        claim_class=claim_class,
        aggregation_strategy=aggregation_strategy,
        mode=mode,
        executes=executes,
        can_emit_factual_finding=factual,
        score_affecting=scoring,
        result_when_not_applicable=when_na,
        coverage_contribution=coverage,
        reason_code=reason,
    )


def shareable(route_class: RouteClass) -> bool | None:
    """Чи спільний маршрут. Соціальне прев'ю тримається саме на цьому."""
    return ATTRIBUTES[route_class].shareable


@dataclass(slots=True)
class PageOutcome:
    """Що політика сказала про одну сторінку для одного claim-класу."""

    url: str
    route: RouteVerdict
    declaration: Declaration
    importance: float = 0.0
    failed: bool = False

    @property
    def evaluated(self) -> bool:
        return self.declaration.applies

    @property
    def unknown(self) -> bool:
        return self.declaration.mode is Mode.NO_VERDICT_UNKNOWN

    @property
    def not_applicable(self) -> bool:
        return not self.evaluated and not self.unknown


@dataclass(slots=True)
class Applicability:
    """Зведення застосовності одного чека, придатне і для доказу, і для стану."""

    check: str
    variant: str = ""
    claim_class: ClaimClass = ClaimClass.PAGE_FACT
    aggregation_strategy: AggregationStrategy = AggregationStrategy.ALL_APPLICABLE_PAGES
    evaluated: int = 0
    failed: int = 0
    not_applicable: int = 0
    no_verdict: int = 0
    not_measured: int = 0
    unread_applicable: int = 0
    verdict: ClaimVerdict = ClaimVerdict.NO_VERDICT
    coverage: Coverage = Coverage.NOT_MEASURED
    rules: dict[str, int] = field(default_factory=dict)
    examples: dict[str, list[str]] = field(default_factory=dict)
    # Доказ претензії, чиє рішення ухвалює окремий детектор (E-10): вердикт
    # такої претензії не виводиться з посторінкових клітинок, і те, на чому
    # він тримається, мусить лежати поруч. Порожньо для всіх інших, і тоді
    # ключа в доказі немає: старі рядки лишаються байт у байт тими самими.
    detail: dict[str, Any] = field(default_factory=dict)

    def as_evidence(self) -> dict[str, Any]:
        if self.detail:
            return {**self._base_evidence(), "detail": dict(self.detail)}
        return self._base_evidence()

    def _base_evidence(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "variant": self.variant,
            "claim_class": self.claim_class.value,
            "aggregation_strategy": self.aggregation_strategy.value,
            "evaluated": self.evaluated,
            "failed": self.failed,
            "not_applicable": self.not_applicable,
            "no_verdict": self.no_verdict,
            "not_measured": self.not_measured,
            "verdict": self.verdict.value,
            "coverage": self.coverage.value,
            "rules": dict(sorted(self.rules.items())),
            "examples": {state: list(urls) for state, urls in sorted(self.examples.items())},
        }


# Скільки прикладів на стан. Межа контрактна: доказ має бути читабельним,
# а не повним переліком сайту.
EVIDENCE_CAP = 5


def _examples(outcomes: Sequence[PageOutcome]) -> list[str]:
    """≤5 адрес, за спаданням важливості, далі за адресою.

    Порядок фіксований навмисно: доказ, чий порядок залежить від обходу,
    не порівняти із самим собою між прогонами.
    """
    ordered = sorted(outcomes, key=lambda o: (-o.importance, o.url))
    return [o.url for o in ordered[:EVIDENCE_CAP]]


def summarise(
    check: str,
    outcomes: Iterable[PageOutcome],
    *,
    variant: str = "",
    claim_class: ClaimClass = ClaimClass.PAGE_FACT,
    strategy: AggregationStrategy = AggregationStrategy.ALL_APPLICABLE_PAGES,
    no_relevant_page: NoRelevantPage = NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    unread_applicable: int = 0,
) -> Applicability:
    """Звести посторінкові рішення в стан чека за оголошеною стратегією."""
    rows = list(outcomes)
    evaluated = [o for o in rows if o.evaluated]
    unknown = [o for o in rows if o.unknown]
    excluded = [o for o in rows if o.not_applicable]
    failed = [o for o in evaluated if o.failed]

    rules: dict[str, int] = {}
    for outcome in rows:
        code = outcome.declaration.reason_code
        rules[code] = rules.get(code, 0) + 1

    result = Applicability(
        check=check,
        variant=variant,
        claim_class=claim_class,
        aggregation_strategy=strategy,
        evaluated=len(evaluated),
        failed=len(failed),
        not_applicable=len(excluded),
        no_verdict=len(unknown),
        not_measured=unread_applicable,
        unread_applicable=unread_applicable,
        rules=rules,
        examples={
            "evaluated": _examples(evaluated),
            "failed": _examples(failed),
            "not_applicable": _examples(excluded),
            "no_verdict": _examples(unknown),
        },
    )

    # Жодної застосовної сторінки: відповідь диктує оголошене правило чека,
    # а не мовчазний дефолт. «Нема чого судити» і «судили й не знайшли» —
    # різні стани, і саме їх плутанина робила порожнечу пройденою.
    if not evaluated:
        if unknown:
            result.verdict, result.coverage = ClaimVerdict.NO_VERDICT, Coverage.PARTIAL
        elif no_relevant_page is NoRelevantPage.FAIL_IF_COMPLETE:
            result.verdict = ClaimVerdict.FAIL if not unread_applicable else ClaimVerdict.NO_VERDICT
            result.coverage = Coverage.COMPLETE if not unread_applicable else Coverage.PARTIAL
        elif no_relevant_page is NoRelevantPage.NO_VERDICT_NOT_MEASURED:
            result.verdict, result.coverage = ClaimVerdict.NO_VERDICT, Coverage.NOT_MEASURED
        elif no_relevant_page is NoRelevantPage.ALWAYS_RELEVANT:
            # Site-level збирач судиться завжди: «жодної застосовної сторінки»
            # для нього не стан, а лише відсутність посторінкового внеску.
            result.verdict = ClaimVerdict.FAIL if failed else ClaimVerdict.PASS
            result.coverage = Coverage.PARTIAL if unread_applicable else Coverage.COMPLETE
        elif no_relevant_page is NoRelevantPage.CLASSIFIER:
            # Ієрархію вирішує E-15, якого тут немає: чесна відповідь — не знаємо.
            result.verdict, result.coverage = ClaimVerdict.NO_VERDICT, Coverage.PARTIAL
        else:
            result.verdict = ClaimVerdict.NOT_APPLICABLE
            result.coverage = Coverage.PARTIAL if unread_applicable else Coverage.COMPLETE
        return result

    if strategy is AggregationStrategy.ANY_SUFFICIENT_EVIDENCE:
        # Екзистенційне твердження: одне достатнє спостереження закриває
        # питання, і непрочитане вже не може його змінити.
        settled = len(evaluated) > len(failed)
        if settled:
            result.verdict, result.coverage = ClaimVerdict.PASS, Coverage.COMPLETE
        elif unread_applicable:
            result.verdict, result.coverage = ClaimVerdict.NO_VERDICT, Coverage.PARTIAL
        else:
            result.verdict, result.coverage = ClaimVerdict.FAIL, Coverage.COMPLETE
        return result

    result.verdict = ClaimVerdict.FAIL if failed else ClaimVerdict.PASS
    result.coverage = Coverage.PARTIAL if unread_applicable else Coverage.COMPLETE
    if unknown:
        result.coverage = Coverage.PARTIAL
    return result


def eligible_for_passed_checks(verdict: ClaimVerdict, coverage: Coverage) -> bool:
    """Рівно `PASS + COMPLETE`, у КОЖНІЙ стратегії, без винятків.

    `PASS + PARTIAL` не допускається ніде: «не знайшли на тому, що
    прочитали» — не те саме, що «перевірили». Екзистенційні чеки винятку не
    мають, бо їхній PASS уже означає COMPLETE за побудовою.
    """
    return verdict is ClaimVerdict.PASS and coverage is Coverage.COMPLETE


@dataclass(frozen=True, slots=True)
class CheckDeclaration:
    """Що оголошує про себе один чек: клас претензії, стратегія, порожній випадок.

    Оголошення лежать ТУТ, а не в кожному чеку, і це вимога контракту, а не
    зручність: «applicability is policy-driven and centralized, not scattered
    ad hoc through checks». Розсип по 81 класу — саме той стан, у якому
    ніхто не бачив картини цілком і `/login` роками втрачав бали за
    відсутній title.

    Побічний, але важливий наслідок: 25 чеків живуть у файлах, яких ця
    хвиля не має права редагувати (`tech.py`, `performance.py`,
    `accessibility.py`). Централізована таблиця робить їхню правку
    непотрібною.
    """

    claim_class: ClaimClass
    aggregation_strategy: AggregationStrategy
    no_relevant_page: NoRelevantPage
    # Варіанти, чий клас відрізняється від класу самого чека.
    variants: dict[str, ClaimClass] = field(default_factory=dict)

    def claim_for(self, variant: str = "") -> ClaimClass:
        """Клас претензії конкретного варіанта; без варіанта — клас чека."""
        return self.variants.get(variant, self.claim_class)


def declaration_of(code: str, variant: str = "") -> CheckDeclaration:
    """Оголошення чека. Відсутнього коду немає за побудовою — гейт це стереже."""
    return CHECK_DECLARATIONS[code]


def claim_class_of(code: str, variant: str = "") -> ClaimClass:
    return CHECK_DECLARATIONS[code].claim_for(variant)


def declare(code: str, route_class: RouteClass, variant: str = "") -> Declaration:
    """Вісім полів для (чек, варіант, клас маршруту) — єдиний вхід для всіх."""
    record = CHECK_DECLARATIONS[code]
    return declaration_for(record.claim_for(variant), route_class, record.aggregation_strategy)


def route_of(ctx: Any, page: Any) -> RouteVerdict:
    """Клас маршруту сторінки. Одне джерело для чеків, дублікатів і карти."""
    from app.audit.route_classes import classify_page

    return classify_page(ctx, page)


def _importance(ctx: Any, page: Any) -> float:
    graph = getattr(ctx, "links", None)
    if graph is None:
        return 0.0
    try:
        return float(graph.importance(page))
    except Exception:  # noqa: BLE001 — граф необовʼязковий, порядок прикладів не критичний
        return 0.0


def unread_applicable(ctx: Any, code: str) -> int:
    """Скільки застосовного до цієї претензії лишилось непрочитаним.

    Майже завжди нуль, і це не пропуск, а межа знання. Клас маршруту
    визначається з ФАКТІВ відповіді — noindex, robots, статус, — тож про
    адресу, якої ми не завантажили, сказати «вона була б застосовна»
    неможливо. Вивести це число з «карта заявила 3407, прочитали 20»
    означало б стверджувати, що всі 3387 непрочитаних застосовні до
    кожної претензії, — рівно та вигадана конкретика, через яку аудит
    колись хвалив сайт за сторінки, яких не відкривав.

    Одне джерело таке число все ж дає, і контракт називає його прямо
    («PARTIAL when it read part of its input — index sitemap children»):
    збирач карти сам каже, скільки дітей індексу лишилось невідкритими.
    Його твердження стосується всієї карти, тож неповний індекс робить
    покриття `seo.sitemap` частковим — і виводить його з пройдених, поки
    карту не прочитано цілком.
    """
    if code == "llm.about_page":
        # Кандидати, яких ми знаємо й не відкривали: пункт меню «про нас»,
        # адреса карти з таким маршрутом. Рахує детектор E-10 — одне рішення
        # для чека, оркестратора й цього лічильника.
        from app.audit import about_page

        about = about_page.detect(ctx)
        return about.unread_applicable if about is not None else 0
    if code == "ai.schema.breadcrumb":
        # Придатні сторінки, яких ми знаємо й не відкривали, плюс невідкриті
        # файли карти. Рахує класифікатор E-15 — те саме одне рішення, що й
        # для чека та для рядка застосовності. Без цього числа «плаский сайт»
        # і «сайт, дочитаний до половини» дають однаковий рядок.
        from app.audit import hierarchy

        decision = hierarchy.classify(ctx)
        return decision.unread_applicable if decision is not None else 0
    if code != "seo.sitemap":
        return 0
    sitemap = getattr(ctx, "sitemap", None)
    if sitemap is None or not getattr(sitemap, "is_index", False):
        return 0
    if getattr(sitemap, "index_complete", True):
        return 0
    total = int(getattr(sitemap, "children_total", 0) or 0)
    read = len(getattr(sitemap, "children_read", ()) or ())
    return max(total - read, 0)


def outcomes_for(ctx: Any, code: str, variant: str = "") -> list[PageOutcome]:
    """Рішення політики для кожної прочитаної сторінки цього чека й варіанта."""
    record = CHECK_DECLARATIONS.get(code)
    if record is None:
        return []
    claim = record.claim_for(variant)
    rows = []
    for page in getattr(ctx, "ok_pages", []) or []:
        route = route_of(ctx, page)
        rows.append(PageOutcome(
            url=page.url,
            route=route,
            declaration=declaration_for(claim, route.route_class, record.aggregation_strategy),
            importance=_importance(ctx, page),
        ))
    return rows


# Класи, чия закритість від пошуку — задум власника, а не вада сайту:
# три підтверджені наміром плюс документ помилки. Саме їх мають на увазі
# дублікати, карта сайту й граф посилань, коли кажуть «службова сторінка».
SERVICE_CLASSES = frozenset(INTENT_CONFIRMED_CLASSES | {RouteClass.ERROR_TRANSIENT})


def _policy_is_always_applicable() -> bool:
    """Чи стоїть таблиця політики в канонічному режимі сумісності.

    Питання ставиться САМІЙ таблиці, а не окремому прапорцю, і в цьому вся
    суть важеля. Контракт описує відкат одним реченням — «policy table to
    always-applicable restores today's behaviour», — тож якщо режим
    сумісності доводиться вмикати ще чимось, крім таблиці, відкат уже не
    один важіль, а два, і про другий хтось забуде.

    Клітинка «застосовується» тоді, коли вона може дати знахідку І та
    знахідка впливає на бал. Щойно жодна клітинка не притримує нічого —
    політики немає, і кожен споживач мусить повернутись до поведінки,
    прийнятої в G4a.
    """
    return all(MODE_FIELDS[mode][1] and MODE_FIELDS[mode][2]
               for row in POLICY.values() for mode in row.values())


# Рахується раз при імпорті: таблиця незмінна, а питання ставиться на
# кожній сторінці кожного споживача.
COMPATIBILITY_MODE = _policy_is_always_applicable()


def service_route(ctx: Any, page: Any) -> bool:
    """Чи ДОВЕДЕНО, що маршрут службовий: намір підтверджено спостереженням.

    Питання для споживача, якому потрібен саме намір власника: посилання
    на закрите (`seo.links_to_noindex`). Посилання на власний вхід чи
    кошик, які сайт САМ тримає поза пошуком, — задум; посилання на статтю
    під `noindex` — вада, і розрізняє їх рівно підтвердження.

    У режимі сумісності відповідь завжди «ні»: до G4b граф посилань не
    питав про службовість узагалі й повідомляв КОЖНЕ посилання на
    закриту сторінку. Відновити треба саме це, а не інший набір.
    """
    if COMPATIBILITY_MODE:
        return False
    return route_of(ctx, page).route_class in SERVICE_CLASSES


def service_shaped(ctx: Any, page: Any) -> bool:
    """Чи маршрут МАЄ ФОРМУ службового — без вимоги підтвердити намір.

    Питання для споживачів, яким намір власника не потрібен: дублікатів і
    звірки карти. Контракт розводить ці два питання явно
    (`owner_intent_required`), і плутати їх не можна в жоден бік: вимагати
    підтвердження там, де воно не потрібне, — значить рахувати `/wp-login.php`
    суперником головної сторінки за однаковий текст; не вимагати там, де
    воно потрібне, — значить мовчати про посилання на закритий вміст.

    Джерело форми одне — таблиця класів маршруту, — і саме це замінює
    приватний набір `PageType` у кожного зі споживачів (E-12).

    Відповідає спільна таблиця, і відповідає двома кроками. Перший —
    клас маршруту: якщо намір ПІДТВЕРДЖЕНО спостереженням, питання
    закрите. Другий — тип сторінки, який та сама таблиця вже несе: він
    локаль-свідомий після E-12 і саме він був старим джерелом обох
    споживачів.

    Другого кроку спершу не було: замість типу питалася ФОРМА маршруту,
    тобто збіг одного слова в адресі. На numpy.org це оголосило
    `/pt/report-handling-manual/` службовою сторінкою — бо в словнику
    адмінки є слово `report`, яким Crawldy зве ВЛАСНІ сторінки звітів, —
    і сказало власнику, що в його карті сайту лежить службова адреса.
    Здогад зі слова гірший за класифікацію, яка дивиться на всю адресу
    разом із заголовком і розміткою, і саме такий здогад E-05 і прибирає.
    Форма лишається в доказі (`RouteVerdict.shape`) як запис, а не як
    відповідь.

    У режимі сумісності лишається рівно перший рядок старого джерела:
    `type_of(page) in NOT_FOR_SEARCH`. Фолбек стоїть ТУТ, а не в кожного
    споживача, щоб важіль лишався один — і щоб «службова сторінка» не
    почала знову означати в них різне.
    """
    if COMPATIBILITY_MODE:
        return bool(ctx.type_of(page) in NOT_FOR_SEARCH)
    verdict = route_of(ctx, page)
    if verdict.route_class in SERVICE_CLASSES:
        return True
    return verdict.page_type in NOT_FOR_SEARCH


def applies_to(ctx: Any, page: Any, code: str, variant: str = "") -> bool:
    """Чи має ця претензія що сказати про цю сторінку.

    Єдина відповідь на весь двигун: чеки, дублікати, карта сайту й граф
    посилань питають саме її, тож виключення не може означати різне в
    різних місцях.
    """
    record = CHECK_DECLARATIONS.get(code)
    if record is None:
        return True
    route = route_of(ctx, page)
    return declaration_for(
        record.claim_for(variant), route.route_class, record.aggregation_strategy
    ).applies


def pages_for(ctx: Any, code: str, variant: str = "") -> list[Any]:
    """Прочитані сторінки, яких ця претензія СТОСУЄТЬСЯ.

    Потрібна тим чекам, які зводять кілька сторінок в одне site-level
    твердження: «однаковий title на трьох адресах», «розмітки немає на
    жодній сторінці». Центральний фільтр знахідок їм не допомагає —
    знахідка в них одна й без адреси, — тож застосовність мусить
    відсіятися на ВХОДІ, поки твердження ще складається.

    Без цього `/login`, `/checkout` і `/app` рахувалися б суперниками
    головної сторінки за однаковий заголовок, а сайт, у якого розмітка є
    всюди, крім кошика, виглядав би сайтом без розмітки.
    """
    return [page for page in (getattr(ctx, "ok_pages", []) or [])
            if applies_to(ctx, page, code, variant)]


def filter_issues(ctx: Any, code: str, issues: Iterable[Any]) -> list[Any]:
    """Прибрати знахідки, що стосуються маршрутів, яких претензія не стосується.

    Site-level знахідка (без адреси сторінки) не чіпається: її claim-клас
    оголошений SITE і застосовний на будь-якому класі маршруту.
    """
    record = CHECK_DECLARATIONS.get(code)
    if record is None:
        return list(issues)
    by_url = {page.url: page for page in (getattr(ctx, "ok_pages", []) or [])}
    kept = []
    for issue in issues:
        page = by_url.get(getattr(issue, "page_url", None) or "")
        if page is None or applies_to(ctx, page, code, getattr(issue, "key", "") or ""):
            kept.append(issue)
    return kept


def evidence_for_context(ctx: Any) -> dict[str, Any]:
    """Застосовність кожного чека, порахована з контексту.

    Без знахідок: їх тут ще немає. `failed`, вердикт і покриття дописує
    `finalise`, коли знахідки стають відомі, — і саме там, де вони відомі
    й на свіжому аудиті, і на перебудованому з бази.
    """
    block: dict[str, Any] = {}
    for code, record in sorted(CHECK_DECLARATIONS.items()):
        variants = ("",) if not record.variants else ("", *sorted(record.variants))
        for variant in variants:
            key = f"{code}:{variant}" if variant else code
            summary = summarise(
                code,
                outcomes_for(ctx, code, variant),
                variant=variant,
                claim_class=record.claim_for(variant),
                strategy=record.aggregation_strategy,
                no_relevant_page=record.no_relevant_page,
                unread_applicable=unread_applicable(ctx, code),
            )
            if code == "llm.about_page":
                # Екзистенційна претензія з ОДНИМ вирішальним доказом: чи є
                # прочитана сторінка «про нас». Посторінкова згортка цього не
                # знає — вона бачить лише, що сторінки прочитані, — тож
                # вердикт і покриття тут диктує детектор E-10.
                from app.audit import about_page

                about = about_page.detect(ctx)
                if about is not None:
                    summary.verdict, summary.coverage = about.verdict, about.coverage
                    summary.not_measured = about.unreadable if not about.conclusive else 0
                    summary.detail = about.as_evidence()
            elif code == "ai.schema.breadcrumb":
                # Претензія, застосовність якої вирішує КЛАСИФІКАТОР
                # (`NoRelevantPage.CLASSIFIER`, оголошено ще в G4b). Посторінкова
                # згортка бачить лише класи маршрутів і тому вміє сказати
                # рівно два стани — PASS і FAIL при повному покритті. Чотири
                # інші стани контракту — плаский сайт (A-09), сайт без
                # придатних сторінок (A-10), недостатнє покриття і доведена
                # ієрархія з непрочитаним обсягом — вона не виражає взагалі.
                #
                # Тому вердикт, покриття, код причини й доказ приходять
                # звідти ж, звідки їх бере чек: з одного рішення E-15.
                from app.audit import hierarchy

                decision = hierarchy.classify(ctx)
                if decision is not None:
                    summary.verdict, summary.coverage = decision.verdict, decision.coverage
                    summary.detail = decision.as_evidence()
                    if decision.rule:
                        summary.rules = {**summary.rules, decision.rule: 1}
            block[key] = summary.as_evidence()
    return block


def finalise(block: dict[str, Any], issues: Iterable[Any]) -> dict[str, Any]:
    """Дописати `failed`, вердикт і покриття з фактичних знахідок."""
    failures: dict[str, int] = {}
    for issue in issues:
        code = getattr(issue, "code", "")
        variant = getattr(issue, "key", "") or ""
        for key in {code, f"{code}:{variant}" if variant else code}:
            failures[key] = failures.get(key, 0) + 1
    out: dict[str, Any] = {}
    for key, row in block.items():
        row = dict(row)
        row["failed"] = failures.get(key, 0)
        # Рядок, чиє рішення ухвалив детектор (E-10, `detail`), його й
        # зберігає: вердикт там уже є, і «без вердикту» не стає PASS від
        # того, що знахідок немає, — сторінку, якої ми не прочитали, хвалити
        # нема за що. Решта рядків — як і досі, без жодної різниці.
        if row["evaluated"] and "detail" not in row:
            row["verdict"] = (ClaimVerdict.FAIL if row["failed"] else ClaimVerdict.PASS).value
        out[key] = row
    return out


def module_totals(block: dict[str, Any], module_of: Any) -> dict[str, dict[str, Any]]:
    """Підсумки застосовності по модулях — для `summary.applicability`.

    Одиниця підсумку — ПРЕТЕНЗІЯ, а не клітинка політики. Блок доказу
    несе і рядок чека, і рядок кожного його варіанта; порахувати обидва
    означало б показати читачеві 104 там, де перевірок 81, і подвоїти
    кожну сторінку в лічильниках. Тому беруться лише базові рядки —
    ті, чий `variant` порожній.

    Поруч із посторінковими лічильниками стоять розклади по вердикту й
    покриттю: без них «модуль має 14 перевірок» не каже, скільки з них
    справді судилося, а скільки промовчало.
    """
    totals: dict[str, dict[str, Any]] = {}
    for row in block.values():
        if row.get("variant"):
            continue
        module = module_of(row["check"])
        if module is None:
            continue
        bucket = totals.setdefault(str(module), {
            "checks": 0, "evaluated": 0, "not_applicable": 0, "no_verdict": 0,
            "not_measured": 0, "failed": 0,
            "verdicts": {v.value: 0 for v in ClaimVerdict},
            "coverage": {c.value: 0 for c in Coverage},
        })
        bucket["checks"] += 1
        for field_name in ("evaluated", "not_applicable", "no_verdict", "not_measured", "failed"):
            bucket[field_name] += int(row.get(field_name, 0) or 0)
        verdict, coverage = str(row.get("verdict") or ""), str(row.get("coverage") or "")
        if verdict in bucket["verdicts"]:
            bucket["verdicts"][verdict] += 1
        if coverage in bucket["coverage"]:
            bucket["coverage"][coverage] += 1
    return dict(sorted(totals.items()))


def policy_table() -> list[dict[str, Any]]:
    """Уся таблиця рядками — для доказу й для тесту, що звіряє її з контрактом."""
    return [
        {"claim_class": claim.value, "route_class": route.value, "mode": mode.value,
         "reason_code": MODE_FIELDS[mode][5]}
        for claim, row in POLICY.items()
        for route, mode in row.items()
    ]


# --- BEGIN GENERATED: check declarations (contracts/applicability-source.json) ---
# Згенеровано з `contracts/applicability-source.json` скриптом
# `g4b_emit_declarations.py`. Руками не правити: джерело — контракт.
CHECK_DECLARATIONS: dict[str, CheckDeclaration] = {
    "a11y.blocking": CheckDeclaration(
        claim_class=ClaimClass.ENTRY_PAGE_ONLY,
        aggregation_strategy=AggregationStrategy.ENTRY_PAGE_ONLY,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "a11y.failures": CheckDeclaration(
        claim_class=ClaimClass.ENTRY_PAGE_ONLY,
        aggregation_strategy=AggregationStrategy.ENTRY_PAGE_ONLY,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "ai.entity.sameas": CheckDeclaration(
        claim_class=ClaimClass.HOME_ONLY,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "ai.jsonld.invalid": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "ai.jsonld.missing": CheckDeclaration(
        claim_class=ClaimClass.PUBLIC_CONTENT,
        aggregation_strategy=AggregationStrategy.ANY_SUFFICIENT_EVIDENCE,
        no_relevant_page=NoRelevantPage.FAIL_IF_COMPLETE,
    ),
    "ai.lang": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "ai.llms_txt": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "ai.opengraph": CheckDeclaration(
        claim_class=ClaimClass.SOCIAL_PREVIEW,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "ai.schema.breadcrumb": CheckDeclaration(
        claim_class=ClaimClass.HIERARCHY_GATED,
        aggregation_strategy=AggregationStrategy.ANY_SUFFICIENT_EVIDENCE,
        no_relevant_page=NoRelevantPage.CLASSIFIER,
    ),
    "ai.schema.contact": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "ai.schema.content_type": CheckDeclaration(
        claim_class=ClaimClass.TYPE_GATED_INDEXABLE,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    # `ai.schema.faq` стояв тут до 13 вересня 2026 (G6: E-07). Рядок знято
    # разом із реєстрацією чека: `build_evidence()` обходить цю таблицю
    # незалежно від REGISTRY, тож залишений рядок дав би застосовність
    # чекові, якого більше немає, — і свіжий доказ ніс би рядок про
    # неіснуючу перевірку. Канонічний VERSIONING-PLAN для G6 так і каже:
    # «declaration row disappears».
    "ai.schema.graph": CheckDeclaration(
        claim_class=ClaimClass.HOME_ONLY,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "ai.schema.organization": CheckDeclaration(
        claim_class=ClaimClass.HOME_OR_ABOUT,
        aggregation_strategy=AggregationStrategy.ANY_SUFFICIENT_EVIDENCE,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "ai.twitter_card": CheckDeclaration(
        claim_class=ClaimClass.SOCIAL_PREVIEW,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "cro.no_action": CheckDeclaration(
        claim_class=ClaimClass.TYPE_GATED_PUBLIC,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "cro.phone_not_tappable": CheckDeclaration(
        claim_class=ClaimClass.PUBLIC_CONTENT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "llm.about_page": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.ANY_SUFFICIENT_EVIDENCE,
        no_relevant_page=NoRelevantPage.FAIL_IF_COMPLETE,
    ),
    "llm.authorship": CheckDeclaration(
        claim_class=ClaimClass.TYPE_GATED_INDEXABLE,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "llm.brand_consistency": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "llm.client_rendered": CheckDeclaration(
        claim_class=ClaimClass.PUBLIC_CONTENT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "llm.contact_page": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.ANY_SUFFICIENT_EVIDENCE,
        no_relevant_page=NoRelevantPage.FAIL_IF_COMPLETE,
    ),
    "llm.crawler_blocked": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "llm.stale_content": CheckDeclaration(
        claim_class=ClaimClass.TYPE_GATED_INDEXABLE,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "llm.structure": CheckDeclaration(
        claim_class=ClaimClass.PUBLIC_CONTENT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "llm.unstated_facts": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "perf.core_web_vitals": CheckDeclaration(
        claim_class=ClaimClass.ENTRY_PAGE_ONLY,
        aggregation_strategy=AggregationStrategy.ENTRY_PAGE_ONLY,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "perf.external_fonts": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "perf.images": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "perf.lighthouse_score": CheckDeclaration(
        claim_class=ClaimClass.ENTRY_PAGE_ONLY,
        aggregation_strategy=AggregationStrategy.ENTRY_PAGE_ONLY,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "perf.mobile_gap": CheckDeclaration(
        claim_class=ClaimClass.ENTRY_PAGE_ONLY,
        aggregation_strategy=AggregationStrategy.ENTRY_PAGE_ONLY,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "perf.page_weight": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "perf.render_blocking": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "perf.responsive_images": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "perf.server_response": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "perf.third_party": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "perf.unavailable": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "seo.anchor_text": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.broken_links": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.canonical": CheckDeclaration(
        claim_class=ClaimClass.STRUCTURE_PUBLIC,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
        variants={"missing": ClaimClass.INDEX_ONLY},
    ),
    "seo.clean_url": CheckDeclaration(
        claim_class=ClaimClass.STRUCTURE_PUBLIC,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
        variants={"query": ClaimClass.INDEX_ONLY},
    ),
    "seo.click_depth": CheckDeclaration(
        claim_class=ClaimClass.INDEX_ONLY,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.duplicate_content": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.h1": CheckDeclaration(
        claim_class=ClaimClass.STRUCTURE_PUBLIC,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.heading_hierarchy": CheckDeclaration(
        claim_class=ClaimClass.STRUCTURE_PUBLIC,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.hreflang_broken": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.hreflang_conflict": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.hreflang_invalid": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.hreflang_missing": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "seo.hreflang_reciprocity": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.https": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "seo.image_alt": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.links_to_noindex": CheckDeclaration(
        claim_class=ClaimClass.INDEX_ONLY,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.meta_description": CheckDeclaration(
        claim_class=ClaimClass.INDEX_ONLY,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.noindex": CheckDeclaration(
        claim_class=ClaimClass.NOINDEX_INTENT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.orphan_pages": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "seo.redirect_chain": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.redirect_loop": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.redirect_target": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.render_delta": CheckDeclaration(
        claim_class=ClaimClass.PUBLIC_CONTENT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.robots_txt": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "seo.sitemap": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "seo.sitemap.lastmod": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "seo.sitemap_consistency": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "seo.thin_content": CheckDeclaration(
        claim_class=ClaimClass.PUBLIC_CONTENT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.title": CheckDeclaration(
        claim_class=ClaimClass.STRUCTURE_PUBLIC,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
        variants={"too_long": ClaimClass.INDEX_ONLY, "too_short": ClaimClass.INDEX_ONLY},
    ),
    "seo.title.duplicate": CheckDeclaration(
        claim_class=ClaimClass.INDEX_ONLY,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.topic_islands": CheckDeclaration(
        claim_class=ClaimClass.TYPE_GATED_INDEXABLE,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "seo.viewport": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "tech.analytics": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.ANY_SUFFICIENT_EVIDENCE,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "tech.caching": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "tech.crawler_blocked": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "tech.demo_content": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "tech.email_exposed": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "tech.form_protection": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "tech.host_canonical": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "tech.mixed_content": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
    "tech.nap": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "tech.security_headers": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.ENTRY_PAGE_ONLY,
        no_relevant_page=NoRelevantPage.NO_VERDICT_NOT_MEASURED,
    ),
    "tech.soft_404": CheckDeclaration(
        claim_class=ClaimClass.SITE_LEVEL,
        aggregation_strategy=AggregationStrategy.SITE_LEVEL,
        no_relevant_page=NoRelevantPage.ALWAYS_RELEVANT,
    ),
    "tech.transport": CheckDeclaration(
        claim_class=ClaimClass.PAGE_FACT,
        aggregation_strategy=AggregationStrategy.ALL_APPLICABLE_PAGES,
        no_relevant_page=NoRelevantPage.NOT_APPLICABLE_COMPLETE,
    ),
}
# --- END GENERATED ---

__all__ = [
    "CHECK_DECLARATIONS",
    "COMPATIBILITY_MODE",
    "EVIDENCE_CAP",
    "MODE_FIELDS",
    "POLICY",
    "REASON_TEXT",
    "SERVICE_CLASSES",
    "AggregationStrategy",
    "Applicability",
    "CheckDeclaration",
    "ClaimClass",
    "ClaimVerdict",
    "Coverage",
    "Declaration",
    "Mode",
    "NoRelevantPage",
    "PageOutcome",
    "applies_to",
    "claim_class_of",
    "declaration_for",
    "declaration_of",
    "declare",
    "eligible_for_passed_checks",
    "evidence_for_context",
    "filter_issues",
    "finalise",
    "mode_for",
    "module_totals",
    "outcomes_for",
    "pages_for",
    "policy_table",
    "route_of",
    "service_route",
    "service_shaped",
    "shareable",
    "summarise",
]
