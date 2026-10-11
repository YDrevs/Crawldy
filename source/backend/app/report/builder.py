"""Складання звіту з результату аудиту.

Чистий шар: без FastAPI і без ORM, як і app/audit/. На вході ReportSource,
на виході ReportDocument, який однаково лягає і в JSON, і в docx.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from app.audit import coverage, form_protection, i18n, sitemap_audit
from app.audit.checks.base import REGISTRY
from app.audit.checks.tech import security_header_gaps
from app.audit.enums import Confidence, DegradationKind, Effort, Module, Severity
from app.audit.i18n import Locale
from app.audit.scoring import (
    MODULE_WEIGHT,
    active_weights,
    band,
    compute_scores,
    overall_raw,
    penalty,
)
from app.audit.types import CRAWL_BLIND, Issue, SiteContext
from app.report import i18n as doc_i18n
from app.report.llms_txt import build_llms_txt
from app.report.passed import collect_passed
from app.report.types import (
    EFFORT_COST,
    EQUIVALENT_CHECK,
    MODULE_FIELD,
    NEXT_ACTIONS_LIMIT,
    SNAPSHOT_MODULES,
    AccessibilityFinding,
    AccessibilitySnapshot,
    IssueEntry,
    MissingData,
    NextAction,
    Recommendation,
    ReportDocument,
    ReportSource,
    ScoreEntry,
)

SEVERITY_ORDER = {s: i for i, s in enumerate(Severity)}
MAX_EXAMPLES = 10


def effort_by_code() -> dict[str, Effort]:
    return {cls.code: cls.effort for cls in REGISTRY}


def _reads_content() -> dict[str, bool]:
    return {cls.code: cls.reads_content for cls in REGISTRY}


def _only_what_we_saw(source: ReportSource) -> ReportSource:
    """Прибирає твердження про вміст, якого ми не читали.

    Гейт валідності вже вміє не називати числа: коли краул не приніс
    жодної сторінки, контентні модулі виключаються зі скора й `overall`
    стає None. Але їхні знахідки досі йшли в звіт, і клієнт, який нас не
    пустив, отримував «немає сторінки About», «немає sitemap», «немає
    розмітки Organization» — тринадцять тверджень про сайт, якого ми не
    бачили. Правдивим із них було одне: `tech.crawler_blocked`.

    Логіка проста: якщо даних не досить для бала модуля, їх не досить і
    для його тверджень. Не вигадувати число ми навчилися раніше, ніж не
    вигадувати зміст.

    Вужче за «виключений модуль → викинути знахідки», і навмисно:

    * Спрацьовує лише на `CRAWL_BLIND`. При `CRAWL_FAILURES` ми прочитали
      меншість адрес, але прочитане бачили; при `CRAWL_EMPTY` отримали
      HTML без тексту — розмітку в ньому теж бачили. Викидати там означало б
      втратити справжні знахідки, а низьке покриття вже знижує впевненість
      окремо (`_temper_by_coverage`).
    * Лишає чеки з `reads_content = False`. Недійсний сертифікат видно з
      відповіді сервера, і він лишається доказом навіть тоді, коли сторінки
      немає.
    """
    if not any(d.scope == CRAWL_BLIND for d in source.degraded):
        return source
    reads = _reads_content()
    kept = [
        issue
        for issue in source.issues
        if issue.module not in source.skipped_modules or not reads.get(issue.code, True)
    ]
    if len(kept) == len(source.issues):
        return source
    return replace(source, issues=kept)


def _finalised_evidence(source: ReportSource) -> dict[str, Any]:
    """Доказ застосовності з дописаними `failed`, вердиктом і покриттям.

    `build_evidence` рахує застосовність із контексту — там ще немає знахідок.
    Дописати їх можна лише тут, і саме тут це правильно: цей шлях однаковий
    для свіжого аудиту й для звіту, перебудованого з бази, тож обидва
    отримують той самий блок, а не два різні.
    """
    from app.audit import applicability

    evidence = dict(source.evidence or {})
    block = evidence.get("applicability")
    if isinstance(block, dict) and block:
        evidence["applicability"] = applicability.finalise(block, source.issues)
    return evidence


def build_report(source: ReportSource, locale: Locale = i18n.DEFAULT_LOCALE) -> ReportDocument:
    source = _only_what_we_saw(source)
    evidence = _finalised_evidence(source)
    issues = _localise(source.issues, locale)
    recommendations = _recommendations(source, locale)
    next_actions = _next_actions(recommendations, locale)
    return ReportDocument(
        locale=locale.value,
        generated_at=datetime.now(UTC),
        audit=_audit_block(source),
        target=_target_block(source),
        overall_score=source.overall,
        overall_band=band(source.overall),
        module_scores=_module_scores(source),
        scores=_score_entries(source),
        summary=_summary(source, recommendations),
        issues=issues,
        recommendations=recommendations,
        next_actions=next_actions,
        evidence=evidence,
        versions=source.versions,
        missing_data=_missing_data(source, locale),
        potential_score=_potential_score(source, next_actions),
        accessibility=_build_accessibility(source),
        # З доказів, не з тиші чеків; гейт по skipped_modules укриває
        # і вимкнене користувачем, і притримане покриттям. Застосовність
        # додає третю межу: перевірка без жодної застосовної сторінки не
        # стає пройденою від того, що знахідок у ній не було.
        passed_checks=collect_passed(evidence, source.skipped_modules),
    )


def _build_accessibility(source: ReportSource) -> AccessibilitySnapshot:
    """Знімок доступності однієї сторінки.

    Показуємо КОЖНУ провалену перевірку Lighthouse, включно з тими, що
    відсіяні з входу чеків. Фільтр дублів вирішує, за що штрафувати, а
    не що правда: на чотирьох сайтах вибірки придушена вада не була
    покрита ніде, і клієнт бачив би «проблем не знайдено» там, де
    Lighthouse знайшов справжню.

    Посилання «про це сказано ще й там» ставиться лише тоді, коли
    відповідна знахідка СПРАВДІ є в цьому аудиті. Мапа правил існує, але
    сама по собі покриття не доводить: на 150 сайтах відповідник
    спрацював на тій самій сторінці лише в 24.7% випадків для
    `heading-order` і 51.4% для `image-alt`.
    """
    raw = (source.evidence or {}).get("accessibility") or {}
    # Вага рахується незалежно від того, чи є знімок: модуль може мати
    # бал і вклад навіть тоді, коли PSI не віддав нам знаменника.
    # Вклад існує лише там, де є у що вкладатися. На заблокованому краулі
    # доступність має бал (PSI відповів) і не пропущена — але загального
    # бала немає взагалі, тож «дає 10% загальної оцінки» описувало б
    # величину, якої в звіті не існує.
    scored = (
        source.overall is not None
        and Module.ACCESSIBILITY not in source.skipped_modules
        and source.scores.get(Module.ACCESSIBILITY.value) is not None
    )
    weight = (
        active_weights(source.skipped_modules).get(Module.ACCESSIBILITY)
        if scored
        else None
    )
    if not raw.get("available"):
        return AccessibilitySnapshot(
            available=False, counts_toward_overall=scored, overall_weight=weight
        )

    fired: dict[str, Module] = {issue.code: issue.module for issue in source.issues}
    findings = []
    for item in raw.get("failures") or []:
        audit_id = str(item.get("id") or "")
        equivalent = EQUIVALENT_CHECK.get(audit_id)
        covered = equivalent if equivalent in fired else None
        findings.append(
            AccessibilityFinding(
                audit_id=audit_id,
                title=str(item.get("title") or ""),
                impact=str(item.get("impact") or ""),
                also_reported_as=covered,
                also_reported_module=fired[covered].value if covered else None,
            )
        )
    return AccessibilitySnapshot(
        available=True,
        measured_url=raw.get("measured_url"),
        strategy=str(raw.get("strategy") or "mobile"),
        applicable=raw.get("applicable"),
        passed=raw.get("passed"),
        failed=raw.get("failed"),
        findings=findings,
        lighthouse_score=raw.get("lighthouse_score"),
        counts_toward_overall=scored,
        overall_weight=weight,
    )


def _potential_score(source: ReportSource, actions: list[NextAction]) -> int | None:
    """Скор після виправлення всіх пунктів із next_actions.

    Саме перерахунок, а не сума impact_points: стеля штрафу на один
    code і нелінійність шкали роблять суму завищеною. Обіцяти клієнту
    приріст, якого не буде, — найгірше, що може зробити комерційний
    звіт.
    """
    if source.overall is None or not actions:
        return source.overall
    fixed = {action.issue_key for action in actions}
    remaining = [i for i in source.issues if i.issue_key not in fixed]
    potential, _ = compute_scores(remaining, skipped_modules=source.skipped_modules)
    return potential


# ── скори ──────────────────────────────────────────────────────────────────


def _module_scores(source: ReportSource) -> dict[str, int | None]:
    """Пропущений модуль — це null, а не 0: даних немає, а не все погано.

    Модулі зі `SNAPSHOT_MODULES` сюди не потрапляють: клієнт бачить їх
    знімком, а не балом. Вклад у загальний бал при цьому не змінюється —
    він рахується зі `source.scores`, якого ця функція не чіпає.
    """
    return {
        field: source.scores.get(module.value)
        for module, field in MODULE_FIELD.items()
        if module not in SNAPSHOT_MODULES
    }


def _score_entries(source: ReportSource) -> list[ScoreEntry]:
    weights = active_weights(source.skipped_modules)
    counts = Counter(i.module for i in source.issues)
    entries = []
    for module, field in MODULE_FIELD.items():
        if module in SNAPSHOT_MODULES:
            continue
        score = source.scores.get(module.value)
        excluded = module in source.skipped_modules or score is None
        entries.append(
            ScoreEntry(
                module=module,
                field=field,
                score=score if score is not None else 0,
                band=band(score) if score is not None else "unknown",
                weight=MODULE_WEIGHT[module],
                effective_weight=weights.get(module, 0.0),
                issues_count=counts.get(module, 0),
                excluded=excluded,
                partial=module in source.partial_modules and not excluded,
            )
        )
    return entries


# Чому модуль лишився без бала. `excluded` цього не каже, і перевантажувати
# його новим значенням не можна: споживачі вже читають його як «бала немає».
# Станів два, бо читачеві потрібні саме вони: вимкнене клієнтом за задумом
# нічого не вимірювало, а запитане, але не виміряне, — прогалина в даних.
# Малими літерами, як `DegradationKind` і стан покриття в тому ж контракті.
EXCLUDED_BY_REQUEST = "excluded_by_request"
WITHHELD_NOT_MEASURED = "withheld_not_measured"


def _withheld(source: ReportSource) -> dict[str, str]:
    """Причина для кожного модуля без бала, доступність включно.

    Береться з `skipped_modules` і деградацій, а не з `missing_data`:
    доступність, яку провайдер без відповіді не приніс, виключається
    мовчки — прогалину там пояснює деградація швидкості, і з самих
    прогалин цього не видно. Обидва джерела є і в свіжому аудиті, і в
    збереженому, тож старі звіти отримують причину без міграції.
    """
    named = {module.value: module for module in Module}
    by_request = {
        module
        for d in source.degraded
        if d.kind is DegradationKind.MODULE_EXCLUDED
        # Рядок, збережений без `affected_modules`, усе одно називає модуль
        # у `scope`: виключення пишеться саме так.
        for module in d.affected_modules or ([named[d.scope]] if d.scope in named else [])
    }
    return {
        module.value: EXCLUDED_BY_REQUEST if module in by_request else WITHHELD_NOT_MEASURED
        for module in MODULE_FIELD
        if module in source.skipped_modules or source.scores.get(module.value) is None
    }


# ── issues ─────────────────────────────────────────────────────────────────


def _localise(issues: list[Issue], locale: Locale) -> list[IssueEntry]:
    ordered = sorted(
        issues, key=lambda i: (SEVERITY_ORDER[i.severity], i.module.value, i.code, i.page_url or "")
    )
    entries = []
    for issue in ordered:
        text = i18n.render(issue.msg or issue.code, issue.params, locale)
        entries.append(
            IssueEntry(
                code=issue.code,
                issue_key=issue.issue_key,
                msg=issue.msg or issue.code,
                module=issue.module,
                severity=issue.severity,
                title=text.title,
                description=text.description,
                recommendation=text.recommendation,
                evidence=issue.evidence,
                page_url=issue.page_url,
                weight=issue.weight,
                penalty=penalty(issue),
            )
        )
    return entries


# ── рекомендації ───────────────────────────────────────────────────────────


def _recommendations(source: ReportSource, locale: Locale) -> list[Recommendation]:
    """Групуємо по `issue_key` — тій самій одиниці, якою міряє скоринг.

    Один `code` віддає різні проблеми («немає title» проти «title
    закороткий») — це різні дії для клієнта, зливати їх не можна. Раніше
    тут стояв `msg`, і він давав правильний поділ з неправильної причини:
    рядок каталогу — presentation layer, його перейменовують разом із
    текстом. Тепер поділ той самий, але спільний зі стелею штрафу, тож
    звіт і бал не можуть розійтися.
    """
    groups: dict[str, list[Issue]] = defaultdict(list)
    for issue in source.issues:
        groups[issue.issue_key].append(issue)

    efforts = effort_by_code()
    base_overall, base_scores = compute_scores(
        source.issues, skipped_modules=source.skipped_modules
    )
    base_raw = overall_raw(source.issues, source.skipped_modules)

    drafts = []
    for issue_key, group in groups.items():
        # Найважча знахідка групи задає і текст, і серйозність. Сортування
        # доповнене `msg`, щоб вибір не залежав від порядку перебору:
        # під одним ключем можуть бути два формулювання («сторінка важка»
        # проти «сторінку не дочитали»), і однакові дані мусять давати
        # однаковий звіт.
        worst = min(group, key=lambda i: (SEVERITY_ORDER[i.severity], i.msg or i.code))
        msg = worst.msg or worst.code
        text = i18n.render(msg, worst.params, locale)

        without = [i for i in source.issues if i.issue_key != issue_key]
        fixed_overall, fixed_scores = compute_scores(
            without, skipped_modules=source.skipped_modules
        )
        # Приріст без clamp: коли модуль уже на нулі, різниця заклампаних
        # скорів дорівнює нулю для будь-якого фікса, і сортувати нічим.
        priority_gain = overall_raw(without, source.skipped_modules) - base_raw
        # Загального бала може не бути взагалі — тоді приросту в балах теж
        # немає, а пріоритезація лишається на priority_gain.
        impact = (
            fixed_overall - base_overall
            if fixed_overall is not None and base_overall is not None
            else 0
        )

        pages = [i.page_url for i in group if i.page_url]
        effort = efforts.get(worst.code, Effort.MEDIUM)
        importance = _group_importance(group)
        drafts.append(
            (
                priority_gain * _importance_factor(importance) / EFFORT_COST[effort],
                Recommendation(
                    rank=0,
                    issue_key=issue_key,
                    msg=msg,
                    code=worst.code,
                    module=worst.module,
                    severity=worst.severity,
                    title=text.title,
                    problem=text.description,
                    action=text.recommendation,
                    consequence=text.consequence,
                    scope="page" if pages else "site",
                    affected_pages=len(pages),
                    affected_examples=pages[:MAX_EXAMPLES],
                    evidence=_merge_evidence(group),
                    impact_points=impact,
                    impact_by_module={
                        m: fixed_scores[m] - base_scores[m]
                        for m in fixed_scores
                        if fixed_scores[m] != base_scores[m]
                    },
                    effort=effort,
                    confidence=_group_confidence(group),
                    page_importance=importance,
                    priority_score=priority_gain
                    * _importance_factor(importance)
                    / EFFORT_COST[effort],
                    floored=impact == 0 and priority_gain > 0,
                ),
            )
        )

    # Спершу смуга серйозності, і лише всередині неї — вигода на вартість.
    #
    # Раніше порядок був чистим приростом на вартість виправлення, і дешева
    # косметика структурно спливала над дорогим критичним: на
    # furniturerow.com рекомендацією номер один стояла відсутня Twitter-картка
    # при Lighthouse 25 і TBT понад три секунди. Обидві знахідки правильні,
    # але порядок між ними був неправильний, а клієнт читає перші три рядки.
    drafts.sort(
        key=lambda d: (
            _priority_band(d[1]),
            -d[0],
            -d[1].affected_pages,
            d[1].msg,
        )
    )
    result = []
    for rank, (_, recommendation) in enumerate(drafts, start=1):
        recommendation.rank = rank
        result.append(recommendation)
    return result


# Наскільки важливість сторінки може посунути рекомендацію всередині її
# смуги. Половина, а не все: забута сторінка теж коштує грошей, і
# опускати її в нуль означало б сказати, що виправляти там нічого.
IMPORTANCE_FLOOR = 0.5


def _group_importance(group: list[Issue]) -> float | None:
    """Найважливіша зі сторінок групи, за версією самого сайту.

    Максимум, а не середнє: проблема, що є і на головній, і на десятку
    забутих сторінок, лишається проблемою головної. Середнє розмило б її
    саме тим, скільки ще сторінок нею вражено, — тобто масштабом.
    """
    values = [
        float(i.evidence["page_importance"])
        for i in group
        if isinstance(i.evidence.get("page_importance"), int | float)
    ]
    return max(values) if values else None


def _importance_factor(importance: float | None) -> float:
    """Множник пріоритету. Знахідка про сайт загалом нічого не втрачає."""
    if importance is None:
        return 1.0
    return IMPORTANCE_FLOOR + (1.0 - IMPORTANCE_FLOOR) * importance


def _group_confidence(group: list[Issue]) -> Confidence:
    """Найнижча з групи: рекомендація тверда рівно настільки, наскільки
    найслабший доказ під нею."""
    order = {Confidence.LOW: 0, Confidence.MEDIUM: 1, Confidence.HIGH: 2}
    return min((i.confidence for i in group), key=lambda c: order[c])


def _merge_evidence(group: list[Issue]) -> dict[str, Any]:
    """Доказ найважчого входження + скільки ще таких. Не зліплюємо все підряд."""
    worst = min(group, key=lambda i: SEVERITY_ORDER[i.severity])
    merged = dict(worst.evidence)
    if len(group) > 1:
        merged["occurrences"] = len(group)
    return merged


# ── план дій ───────────────────────────────────────────────────────────────


# Смуги пріоритету. Всередині смуги виграє дешевша вигода, між смугами —
# завжди серйозніша проблема.
_PRIORITY_BANDS: dict[Severity, int] = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 0,
    Severity.MEDIUM: 1,
    Severity.LOW: 2,
    Severity.INFO: 3,
}


def _priority_band(rec: Recommendation) -> int:
    """Смуга, у якій рекомендація змагається за місце.

    Низька впевненість опускає на смугу нижче. Судження моделі може бути
    правильним, але ставити його попереду виміряного факту не можна:
    один абсурдний пункт угорі списку коштує довіри дорожче, ніж кілька
    пропущених дрібних.
    """
    band = _PRIORITY_BANDS[rec.severity]
    if rec.confidence is Confidence.LOW:
        band += 2
    elif rec.confidence is Confidence.MEDIUM:
        band += 1
    return band


def _next_actions(
    recommendations: list[Recommendation], locale: Locale
) -> list[NextAction]:
    """Топ-N, а не весь список: клієнту потрібен початок, а не інвентаризація.

    Перед потраплянням сюди рекомендація проходить перевірку. INFO і
    здогади низької впевненості лишаються у повному переліку, але в
    «Що робити першим» не йдуть: це список, за яким клієнт починає
    витрачати гроші.
    """
    actionable = [
        r
        for r in recommendations
        if r.severity is not Severity.INFO
        and r.confidence is not Confidence.LOW
        and r.priority_score > 0
        and r.action
    ]
    actions = []
    for rank, rec in enumerate(actionable[:NEXT_ACTIONS_LIMIT], start=1):
        actions.append(
            NextAction(
                rank=rank,
                issue_key=rec.issue_key,
                msg=rec.msg,
                module=rec.module,
                action=rec.action,
                # Для плану дій пояснення «навіщо» пишеться простою мовою:
                # його читає той, хто вирішує, а не той, хто виправляє.
                why=rec.consequence or rec.problem or rec.title,
                expected_gain_points=rec.impact_points,
                expected_gain=_gain_label(rec, locale),
                effort=rec.effort,
                affected_pages=rec.affected_pages,
                evidence_ref=rec.msg,
            )
        )
    return actions


def _gain_label(rec: Recommendation, locale: Locale) -> str:
    # Тільки додатний приріст отримує плюс. Відʼємний вплив трапляється,
    # коли прибирання знахідки перерозподіляє ваги модулів, і рядок
    # «Ефект: +-1» у звіті клієнта виглядав саме так, як і є, — помилкою.
    if rec.impact_points > 0:
        return f"+{rec.impact_points}"
    # Модуль уже на нулі: чесніше сказати, що бал не зросте, ніж малювати
    # +0. Пояснення — з каталогу: зашитий українською рядок їхав у звіти
    # всіма шістьма мовами.
    return f"0 ({doc_i18n.t('impact_floored', locale)})" if rec.floored else "0"


# ── прогалини в даних ──────────────────────────────────────────────────────


def _reason_params(params: dict[str, Any] | None, locale: Locale) -> dict[str, Any]:
    """Параметри деградації, готові до підстановки в шаблон.

    Список причин зберігається locale-нейтральними слагами — деградація
    пишеться один раз, а читається будь-якою мовою. Компонування в рядок
    відбувається тут, де локаль уже відома: кожен слаг має власний ключ
    `coverage.reason.*`, і той самий словник параметрів доступний і
    фрагментам (щоб «{access} із {attempted}» підставилось усередині).
    """
    if not params or not isinstance(params.get("reasons"), list):
        return params or {}
    resolved = dict(params)
    resolved["reasons"] = "; ".join(
        i18n.notice(f"coverage.reason.{slug}", params, locale)
        for slug in params["reasons"]
    )
    return resolved


def _missing_data(source: ReportSource, locale: Locale) -> list[MissingData]:
    """Прогалини в даних мовою читача.

    Текст береться з ключа, а не з `Degradation.reason`: другий
    народжується в двигуні одним рядком однією мовою. Він лишається
    фолбеком для аудитів, збережених до появи ключів, — інакше старий
    звіт втратив би пояснення взагалі.
    """
    return [
        MissingData(
            scope=d.scope,
            kind=d.kind.value,
            reason=(
                i18n.notice(d.reason_key, _reason_params(d.reason_params, locale), locale)
                if d.reason_key
                else d.reason
            ),
            affects=[MODULE_FIELD[m] for m in d.affected_modules],
            note=_missing_note(d.affected_modules, source, locale),
        )
        for d in source.degraded
    ]


def _missing_note(affected: list[Module], source: ReportSource, locale: Locale) -> str:
    """Приписка до прогалини — теж мовою читача.

    Рядки жили тут жорстко українською, і англійський звіт віддавав
    клієнту «модуль виключено з overall» посеред англійського тексту.
    Тести цього не бачили: вони звіряли `reason`, який локалізується
    поруч, а `note` ніхто не читав. Знайдено читанням справжньої
    відповіді API.
    """
    if any(m in source.skipped_modules for m in affected):
        return doc_i18n.t("missing_note_excluded", locale)
    if any(m in source.partial_modules for m in affected):
        return doc_i18n.t("missing_note_partial", locale)
    return doc_i18n.t("missing_note_incomplete", locale)


# ── блоки шапки ────────────────────────────────────────────────────────────


def _audit_block(source: ReportSource) -> dict[str, Any]:
    duration = None
    if source.started_at and source.finished_at:
        duration = int((source.finished_at - source.started_at).total_seconds() * 1000)
    return {
        "id": str(source.audit_id) if source.audit_id else None,
        "status": source.status.value,
        "created_at": source.created_at.isoformat() if source.created_at else None,
        "started_at": source.started_at.isoformat() if source.started_at else None,
        "finished_at": source.finished_at.isoformat() if source.finished_at else None,
        "duration_ms": duration,
    }


def _target_block(source: ReportSource) -> dict[str, Any]:
    return {
        "url": source.url,
        "entry_url": source.entry_url,
        "origin": source.origin,
        "pages_crawled": source.pages_crawled,
    }


def _coverage(source: ReportSource) -> dict[str, Any]:
    """Скільки сайту ми справді прочитали — поруч із балом, а не в доказах.

    Бал за двадцятьма сторінками з трьох із половиною тисяч подавався так
    само впевнено, як бал за сайтом, прочитаним повністю: asana.com — 20
    адрес із 3407 і 59 балів. Покриття лежало в `evidence` окремих чеків,
    тобто там, куди читач підсумку не дивиться.

    Береться з evidence, а не з нових полів: обидва шляхи збірки звіту —
    свіжий аудит і рядки БД — уже несуть ці числа, і третє місце
    зберігання того самого факту тільки розійшлося б із першими двома.
    """
    crawl = source.evidence.get("crawl") or {}
    fetched = crawl.get("pages_total", source.pages_crawled)
    read = crawl.get("pages_ok", fetched)
    # Скільки адрес сайт сам за собою визнає. Карти немає — рівняємось на
    # те, що знайшли: інакше покриття завжди виходило б 100%.
    known = max((source.evidence.get("sitemap_xml") or {}).get("url_count") or 0, fetched)
    # Скільки адрес карти ми справді звірили. Мовчання чека про карту
    # означає «серед перевірених розбіжностей немає», а не «карта чиста»:
    # на dukescricket.co.uk перевірено 6 із 116. Без цих чисел читач
    # підсумку прочитав би тишу як підтвердження всієї карти.
    sitemap = source.evidence.get("sitemap_xml") or {}
    declared = sitemap.get("url_count") or 0
    verified = min(sitemap.get("checked") or 0, declared) if declared else 0
    assessment = source.evidence.get("coverage_assessment") or {}
    return {
        "state": assessment.get("state") or "scored",
        "state_reasons": list(assessment.get("reasons") or []),
        "pages_read": read,
        "pages_fetched": fetched,
        "pages_failed": crawl.get("pages_failed", 0),
        "pages_known": known,
        "share": round(read / known, 4) if known else None,
        "sitemap_declared": declared,
        "sitemap_verified": verified,
        "sitemap_unverified": max(declared - verified, 0),
    }


def _summary(source: ReportSource, recommendations: list[Recommendation]) -> dict[str, Any]:
    by_severity = Counter(i.severity.value for i in source.issues)
    by_module = Counter(i.module.value for i in source.issues)
    return {
        "issues_total": len(source.issues),
        # Читач має бачити, на якій частині сайту побудований бал, поруч
        # із самим балом. Аудит бачить не сайт, а свою вибірку.
        "coverage": _coverage(source),
        "by_severity": {s.value: by_severity.get(s.value, 0) for s in Severity},
        "by_module": {m.value: by_module.get(m.value, 0) for m in Module},
        "recommendations_total": len(recommendations),
        "quick_wins": sum(
            1 for r in recommendations if r.effort is Effort.LOW and r.impact_points > 0
        ),
        # Кожен impact_points міряний окремо проти того самого базового скора.
        # Сумувати їх не можна: стеля на code і clamp роблять ефект нелінійним.
        "impact_is_independent": True,
        # Чому модуль без бала: вимкнено клієнтом чи не виміряно. Поруч із
        # `coverage` з тієї ж причини: бал і те, на чому його немає, читач
        # підсумку має бачити разом.
        "withheld": _withheld(source),
        "worst_module": min(
            (m for m in MODULE_FIELD if m.value in source.scores),
            key=lambda m: source.scores[m.value],
            default=None,
        ),
    }


# ── докази ─────────────────────────────────────────────────────────────────


def _brief_snapshot(ctx: SiteContext) -> dict[str, Any]:
    """Плоский знімок SiteBrief. None означає, що аналізу не було —
    і це не те саме, що «модель нічого не зрозуміла»."""
    brief = ctx.brief
    if brief is None:
        return {"analysed": False, "error": "семантичного аналізу не було"}
    return {
        "analysed": bool(brief.analysed),
        "error": brief.error,
        "name": brief.name,
        "tagline": brief.tagline,
        "description": brief.description,
        "offerings": list(brief.offerings),
        "audience": brief.audience,
    }


def _accessibility_snapshot(ctx: SiteContext) -> dict[str, Any]:
    """Сирі числа для знімка доступності. Порожнеча лишається порожнечею.

    `available: False` означає «не виміряли», і це не те саме, що нуль
    знайдених проблем. Аудит, знятий до появи лічильників, теж потрапляє
    сюди — у нього немає знаменника, і вигадати його нізвідки.
    """
    measured = ctx.primary_performance()
    # Знаменник обовʼязковий, а не бажаний. Аудит, знятий до появи
    # лічильників, має бал, але не має кількості застосовних перевірок —
    # і саме кількість несе весь сенс знімка. Без неї «проблем не
    # знайдено серед None перевірок» було б гіршим за мовчання.
    if (
        measured is None
        or measured.accessibility_score is None
        or measured.accessibility_applicable is None
    ):
        return {"available": False}
    return {
        "available": True,
        "measured_url": measured.url,
        "strategy": measured.strategy.value,
        "applicable": measured.accessibility_applicable,
        "passed": measured.accessibility_passed,
        "failed": measured.accessibility_failed,
        # Зовнішній орієнтир, не наш бал. Лежить окремо саме тому.
        "lighthouse_score": measured.accessibility_score,
        # Усе, що впало, — включно з тим, що відсіяне з входу чеків.
        "failures": [
            {"id": f["id"], "title": f.get("title", ""), "impact": f.get("impact", "")}
            for f in measured.accessibility_failures_all
        ],
    }


def _security_headers_fact(ctx: SiteContext) -> dict[str, Any]:
    """Стан захисних заголовків перевіреної відповіді — фактом, не судженням."""
    page = ctx.home if ctx.home is not None else (ctx.ok_pages[0] if ctx.ok_pages else None)
    if page is None or not page.headers:
        return {"available": False}
    missing, invalid = security_header_gaps(page)
    return {
        "available": True,
        "checked_url": page.url,
        "complete": not missing,
        "missing": missing,
        **({"invalid_values": invalid} if invalid else {}),
    }


def _analytics_fact(ctx: SiteContext) -> dict[str, Any]:
    """Які системи вимірювання справді знайдено — і чи після рендеру.

    `found` лишається тим, чим було для читачів: іменами ВПІЗНАНИХ
    вендорів. Класифікація їде поруч окремими полями — вид доказу, стан,
    самі спостереження й окремо невпізнане вимірювання. Без них курована
    перевірка читала наявність рядка й називала пройденим будь-що, зокрема
    мітку `first_party`, яка вендором не була ніколи (E-11).
    """
    state = ctx.analytics_classification()
    return {
        "found": state.verified,
        "checked_after_render": state.rendered,
        "kind": state.kind.value,
        "verdict": state.verdict,
        "coverage": state.coverage,
        "observations": state.evidence(),
        "unidentified": state.unidentified_evidence(),
    }


def _form_protection_fact(ctx: SiteContext) -> dict[str, Any]:
    """Видимі ознаки захисту форм: що саме побачено і на якій сторінці.

    Позитивне спостереження ніде більше не зберігається: знахідка існує
    лише для протилежного випадку, і без цього блоку звіт не міг би
    назвати провайдера, якого ми впізнали. Межа твердження їде поруч
    із фактом, а не в коментарі: пасивна перевірка не бачить серверної
    частини й не пробує надсилати форму.
    """
    from app.audit.checks.tech import _is_lead_form, observe_forms

    scanned = False
    protected: list[dict[str, Any]] = []
    unprotected: list[dict[str, Any]] = []
    undetermined: list[dict[str, Any]] = []
    forms_total = 0

    for page in ctx.ok_pages:
        # «Дивилися» — властивість сторінки, а не її форм: сторінка без
        # форм не має де нести прапорець, і без нього «форм немає» не
        # відрізнити від «не шукали».
        if page.forms_scanned:
            scanned = True
        if not [form for form in page.forms if _is_lead_form(form)]:
            continue
        for observation, form in observe_forms(ctx, page):
            if not _is_lead_form(form) or not page.forms_scanned:
                continue
            forms_total += 1
            entry = {"page_url": page.url, **observation.to_json()}
            if observation.protected:
                protected.append(entry)
            elif observation.undetermined:
                undetermined.append(entry)
            else:
                unprotected.append(entry)

    return {
        # Старий аудит або аудит без прочитаних сторінок: ми не дивилися,
        # і сказати «форм немає» на цій підставі не можна.
        "available": scanned,
        "forms_total": forms_total,
        "protected": protected[:20],
        "unprotected": unprotected[:20],
        "undetermined": undetermined[:20],
        "providers_checked": list(form_protection.PROVIDER_MARKERS),
        # Межі пасивної перевірки. Вони частина доказу, а не примітка.
        "server_side_controls_assessed": False,
        "form_submission_tested": False,
        "rate_limiting_tested": False,
    }


def _coverage_assessment(ctx: SiteContext) -> dict[str, Any]:
    """Факти покриття і стан, у якому їх тлумачить продукт."""
    evidence = coverage.collect_evidence(ctx)
    state, reasons = coverage.assess(evidence)
    return {**evidence.to_json(), "state": state.value, "reasons": reasons}


def _applicability_snapshot(ctx: SiteContext) -> dict[str, Any]:
    """Застосовність кожної претензії до маршрутів цього сайту.

    Рахується з контексту, бо саме контекст знає маршрути. Знахідок тут ще
    немає — їх дописує `_finalised_evidence` у момент, коли вони відомі.
    """
    from app.audit import applicability

    try:
        return applicability.evidence_for_context(ctx)
    except Exception:  # noqa: BLE001 — доказ не має права завалити звіт
        return {}


def build_evidence(ctx: SiteContext) -> dict[str, Any]:
    """Знімок того, що ми справді побачили. Персиститься разом з аудитом.

    Інваріант 4: звіт без доказів не переконує клієнта. Це site-level
    доказ, на додачу до issue-level в кожній знахідці.
    """
    return {
        # Готова чернетка файлу, а не оцінка його відсутності. Чек лише
        # каже, що llms.txt немає; цінність — віддати клієнту готовий.
        "llms_txt_draft": build_llms_txt(ctx),
        # Те, як модель зрозуміла сайт. Ми за це вже заплатили під час
        # аудиту, і без збереження воно згорає разом із процесом: звіт,
        # згенерований завтра з рядків БД, мав би платити вдруге.
        "site_brief": _brief_snapshot(ctx),
        # Знімок доступності: сторінка, яку міряли, і скільки перевірок
        # на ній справді запустилось. Бал Lighthouse без цієї кількості
        # не читається — 37 при 3 провалах з 4 і 90 при 3 провалах з 29
        # описують однакову кількість вад.
        "accessibility": _accessibility_snapshot(ctx),
        # Застосовність: які маршрути ця перевірка взагалі стосується, а
        # яких — ні, і чому саме. Додається, а не замінює: старий читач
        # блок ігнорує, а старий знімок його просто не має (E-05).
        "applicability": _applicability_snapshot(ctx),
        # Факти покриття плюс стан: чи репрезентує прочитане живий сайт.
        # Стан перераховується з фактів детерміністично — тут немає
        # другого джерела правди, лише той самий `assess()`.
        "coverage_assessment": _coverage_assessment(ctx),
        # Що сайт сказав про себе: назва організації, міста, адреси,
        # телефони. Збиралося й раніше (для чеків), але згорало разом із
        # процесом; тепер із цього виводяться факти для прогону
        # присутності — бренд, категорія, місто — без другого краулу.
        "site_facts": ctx.known.to_json() if ctx.known is not None else {},
        "crawl": {
            "pages_ok": len(ctx.ok_pages),
            "pages_total": len(ctx.pages),
            "pages_failed": len(ctx.failed_urls),
            "failed_urls": dict(list(ctx.failed_urls.items())[:20]),
            "max_depth_reached": max((p.depth for p in ctx.pages), default=0),
        },
        "http": {
            "entry_url": ctx.entry_url,
            "origin": ctx.origin,
            "is_https": ctx.is_https,
            "hsts": ctx.hsts,
            # Для розділу пройдених перевірок: HTTPS «пройдено» вимагає
            # не лише схеми, а й того, що сертифікат НЕ дав помилки.
            "tls_error": ctx.tls_error,
        },
        # Явні позитивні факти для розділу пройдених перевірок. Пройдене
        # НЕ виводиться з відсутності знахідки — лише з побаченого, тому
        # факти збираються тут тим самим кодом, що й у детекторів.
        "security_headers": _security_headers_fact(ctx),
        "analytics": _analytics_fact(ctx),
        "form_protection": _form_protection_fact(ctx),
        "robots_txt": {
            "exists": ctx.robots.exists,
            "status_code": ctx.robots.status_code,
            "disallows_all": ctx.robots.disallows_all,
            "sitemaps": ctx.robots.sitemaps,
            "crawl_delay": ctx.robots.crawl_delay,
            "blocked_ai_agents": ctx.robots.blocked_ai_agents,
        },
        "sitemap_xml": {
            "exists": ctx.sitemap.exists,
            "status_code": ctx.sitemap.status_code,
            "url": ctx.sitemap.url,
            "url_count": ctx.sitemap.url_count,
            "parse_error": ctx.sitemap.parse_error,
            # Скільки адрес карти ми справді звірили з побаченим. Береться
            # з того самого розбору, що й чек: друге обчислення того самого
            # числа розійшлося б із першим.
            **sitemap_audit.collect(ctx).coverage(),
        },
        "llms_txt": {
            "exists": ctx.llms_txt.exists,
            "status_code": ctx.llms_txt.status_code,
            "has_h1": ctx.llms_txt.has_h1,
            "section_count": ctx.llms_txt.section_count,
            "link_count": ctx.llms_txt.link_count,
        },
        "structured_data": _structured_data(ctx),
        "performance": [_performance_entry(r) for r in ctx.performance],
        "pages": [
            {
                "url": p.url,
                "status_code": p.status_code,
                "depth": p.depth,
                "response_ms": p.response_ms,
                "html_bytes": p.html_bytes,
                "word_count": p.word_count,
                "title": p.title,
                "h1_count": len(p.h1),
            }
            for p in ctx.pages
        ],
    }


def _structured_data(ctx: SiteContext) -> dict[str, Any]:
    types: Counter[str] = Counter()
    with_jsonld = 0
    errors: list[str] = []
    for page in ctx.ok_pages:
        if page.jsonld:
            with_jsonld += 1
        types.update(page.to_json()["jsonld_types"])
        errors.extend(page.jsonld_errors)
    return {
        "pages_with_jsonld": with_jsonld,
        "pages_total": len(ctx.ok_pages),
        "types": dict(types.most_common()),
        "parse_errors": errors[:10],
    }


def _performance_entry(result: Any) -> dict[str, Any]:
    def metrics(source: dict[str, Any]) -> dict[str, Any]:
        return {
            name: {"value": value.value, "unit": value.unit, "rating": value.rating}
            for name, value in source.items()
        }

    return {
        "provider": result.provider,
        "strategy": result.strategy.value,
        "url": result.url,
        "fetched": result.fetched,
        "error": result.error,
        "lighthouse_score": result.lighthouse_score,
        "field_data": metrics(result.field_data),
        "lab": metrics(result.lab),
    }


__all__ = ["build_evidence", "build_report", "effort_by_code"]
