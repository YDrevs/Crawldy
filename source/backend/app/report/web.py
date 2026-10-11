"""`ReportDocument` → контракт веб-інтерфейсу.

Один із чотирьох виходів спільної бізнес-логіки, поруч із DOCX,
JSON-експортом і публічним посиланням. Живе в `report/`, а не в
маршруті: маршрут має віддавати готове, а не збирати presentation-шар
дорогою.

Нічого не рахує. Пріоритети, наслідки, impact, смуги, покриття й
потенційний бал уже пораховані білдером — тут лише перекладання полів у
стабільні імена контракту. Щойно тут зʼявиться арифметика, вона стане
другим місцем правди про бал.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.audit.enums import Module
from app.report.i18n import locale_of as i18n_locale_of
from app.report.i18n import t as report_t
from app.report.types import ReportDocument
from app.schemas.result import (
    AccessibilityFindingOut,
    AccessibilitySnapshotOut,
    ApplicabilityTotalsOut,
    AuditResultResponse,
    CoverageOut,
    FindingOut,
    LocalizationOut,
    MissingDataOut,
    ModuleScoreOut,
    NextActionOut,
    PassedCheckOut,
    PriorityOut,
    ResultSummaryOut,
)


def _applicability(document: ReportDocument) -> dict[str, ApplicabilityTotalsOut]:
    """Підсумки застосовності по модулях — з доказу, не з нового підрахунку.

    Арифметику робить `app.audit.applicability.module_totals`: правило про
    те, що рахується претензією, мусить жити в одному місці з самою
    політикою, інакше контракт інтерфейсу й двигун розійдуться мовчки.
    Тут лишається перекладання полів, як і в усьому файлі.

    Порожньо для аудитів, знятих до E-05: у їхньому доказі блока немає, і
    нуль там означав би «порахували й вийшов нуль».
    """
    from app.audit import applicability
    from app.audit.checks.base import REGISTRY

    block = (document.evidence or {}).get("applicability")
    if not isinstance(block, dict) or not block:
        return {}
    module_of = {cls.code: cls.module.value for cls in REGISTRY}.get
    return {
        module: ApplicabilityTotalsOut(**totals)
        for module, totals in applicability.module_totals(block, module_of).items()
    }


def to_web(
    document: ReportDocument,
    *,
    audit_id: uuid.UUID,
    site_id: uuid.UUID | None,
    status: str,
    finished_at: datetime | None,
    fallback_locale: str,
    issue_ids: dict[str, uuid.UUID] | None = None,
    verdicts: dict[str, tuple[str, str]] | None = None,
) -> AuditResultResponse:
    """Зібрати відповідь інтерфейсу з готового документа.

    `issue_ids` і `verdicts` приходять ззовні: сам документ про рядки БД
    не знає й знати не має — він однаковий для свіжого аудиту й для
    відновленого з бази. Ідентифікатор потрібен лише інтерфейсу, щоб
    записати вердикт людини.
    """
    ids = issue_ids or {}
    said = verdicts or {}
    summary = document.summary or {}
    crawl = summary.get("coverage") or {}
    withheld = summary.get("withheld") or {}

    return AuditResultResponse(
        audit_id=audit_id,
        site_id=site_id,
        url=str(document.target.get("url") or document.audit.get("url") or ""),
        origin=str(document.target.get("origin") or document.audit.get("origin") or ""),
        status=status,  # type: ignore[arg-type]  — валідує сам enum схеми
        generated_at=document.generated_at,
        finished_at=finished_at,
        overall_score=document.overall_score,
        overall_band=document.overall_band,
        potential_score=document.potential_score,
        modules=[
            ModuleScoreOut(
                module=entry.module,
                # Виключений модуль віддається порожнім балом, а не нулем.
                # Усередині `ScoreEntry.score` — int, і невиміряний модуль
                # тримає там 0 як службове значення; docx це щоразу
                # обходить перевіркою `excluded`. У контракті поле
                # оголошене `int | None` саме тому, що нуль тут читається
                # як «модуль провалено», тобто як вигадане вимірювання.
                score=None if entry.excluded else entry.score,
                band=entry.band,
                weight=entry.effective_weight,
                issues_count=entry.issues_count,
                excluded=entry.excluded,
                partial=entry.partial,
                # Чому `excluded`: причину виводить білдер, тут лише поле.
                withheld_reason=withheld.get(entry.module.value),
            )
            for entry in document.scores
        ],
        summary=ResultSummaryOut(
            issues_total=int(summary.get("issues_total") or 0),
            by_severity=dict(summary.get("by_severity") or {}),
            by_module=dict(summary.get("by_module") or {}),
            coverage=CoverageOut(
                state=str(crawl.get("state") or "scored"),
                state_reasons=[str(r) for r in (crawl.get("state_reasons") or [])],
                pages_read=int(crawl.get("pages_read") or 0),
                pages_fetched=int(crawl.get("pages_fetched") or 0),
                pages_failed=int(crawl.get("pages_failed") or 0),
                urls_known=int(crawl.get("pages_known") or 0),
            ),
            impact_is_independent=bool(summary.get("impact_is_independent", True)),
            applicability=_applicability(document),
        ),
        priorities=[
            PriorityOut(
                rank=rec.rank,
                issue_key=rec.issue_key,
                module=rec.module,
                severity=rec.severity,
                title=rec.title,
                problem=rec.problem,
                action=rec.action,
                consequence=rec.consequence,
                scope=rec.scope,
                affected_pages=rec.affected_pages,
                affected_examples=list(rec.affected_examples),
                evidence=dict(rec.evidence),
                impact_points=rec.impact_points,
                impact_by_module=dict(rec.impact_by_module),
                effort=rec.effort,
                confidence=rec.confidence,
            )
            for rec in document.recommendations
        ],
        next_actions=[
            NextActionOut(
                rank=action.rank,
                issue_key=action.issue_key,
                module=action.module,
                action=action.action,
                why=action.why,
                expected_gain_points=action.expected_gain_points,
                expected_gain=action.expected_gain,
                effort=action.effort,
                affected_pages=action.affected_pages,
            )
            for action in document.next_actions
        ],
        findings=[
            FindingOut(
                id=ids.get(_finding_key(entry.issue_key, entry.page_url)),
                code=entry.code,
                issue_key=entry.issue_key,
                module=entry.module,
                severity=entry.severity,
                title=entry.title,
                description=entry.description,
                recommendation=entry.recommendation,
                page_url=entry.page_url,
                evidence=dict(entry.evidence),
                verdict=said.get(
                    _finding_key(entry.issue_key, entry.page_url), (None, "")
                )[0],  # type: ignore[arg-type]
                verdict_note=said.get(
                    _finding_key(entry.issue_key, entry.page_url), (None, "")
                )[1],
            )
            for entry in document.issues
        ],
        accessibility=_accessibility_out(document),
        passed_checks=_passed_out(document),
        missing_data=[
            MissingDataOut(
                scope=gap.scope,
                kind=gap.kind,
                reason=gap.reason,
                affects=list(gap.affects),
                note=gap.note,
            )
            for gap in document.missing_data
        ],
        engine_versions=dict(document.versions or {}),
        localization=LocalizationOut(
            locale=document.locale,
            fallback_locale=fallback_locale,
        ),
    )


def _accessibility_out(document: ReportDocument) -> AccessibilitySnapshotOut:
    """Знімок доступності в публічний контракт.

    Немає даних — `available: False`, а не нулі. Нуль провалених
    перевірок при нулі застосовних читався б як «усе гаразд», хоча
    означає протилежне: ми нічого не виміряли.
    """
    snapshot = document.accessibility
    # `available: False` сам не розрізняє «вимкнено клієнтом» і «не
    # виміряно»: без знаменника буває й виміряний модуль.
    withheld = ((document.summary or {}).get("withheld") or {}).get(Module.ACCESSIBILITY.value)
    if snapshot is None or not snapshot.available:
        # Навіть без знаменника модуль може мати бал і вагу: аудит,
        # знятий до появи лічильників, — саме такий випадок.
        return AccessibilitySnapshotOut(
            available=False,
            counts_toward_overall=bool(snapshot and snapshot.counts_toward_overall),
            overall_weight=snapshot.overall_weight if snapshot else None,
            withheld_reason=withheld,
        )
    return AccessibilitySnapshotOut(
        available=True,
        counts_toward_overall=snapshot.counts_toward_overall,
        overall_weight=snapshot.overall_weight,
        withheld_reason=withheld,
        measured_url=snapshot.measured_url,
        strategy=snapshot.strategy,
        applicable=snapshot.applicable,
        passed=snapshot.passed,
        failed=snapshot.failed,
        findings=[
            AccessibilityFindingOut(
                audit_id=f.audit_id,
                title=f.title,
                impact=f.impact,
                also_reported_as=f.also_reported_as,
                also_reported_module=(
                    Module(f.also_reported_module) if f.also_reported_module else None
                ),
            )
            for f in snapshot.findings
        ],
        lighthouse_score=snapshot.lighthouse_score,
    )


def _passed_out(document: ReportDocument) -> list[PassedCheckOut]:
    """Пройдені перевірки з локалізованим заголовком.

    Заголовок складається тут, бо мова відома лише при рендері; факт
    лишається locale-нейтральним у `facts`.
    """
    locale = i18n_locale_of(document)
    return [
        PassedCheckOut(
            key=check.key,
            module=check.module,
            scope=check.scope,
            title=report_t(f"passed.{check.key}", locale, **check.facts),
            facts=check.facts,
        )
        for check in document.passed_checks
    ]


def _finding_key(issue_key: str, page_url: str | None) -> str:
    """Чим знахідка в документі відповідає рядку в базі.

    Пара «проблема + сторінка» — саме те, чим вони й розрізняються:
    один `issue_key` буває на двадцяти сторінках, і це двадцять рядків.
    """
    return f"{issue_key}@{page_url or ''}"


__all__ = ["to_web"]
