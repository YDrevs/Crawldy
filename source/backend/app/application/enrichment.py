"""AI-збагачення як застосунок: придатність, ідемпотентність, виконання.

Шар стоїть ПІСЛЯ детерміністичної правди й читає її лише на читання:
збережені знахідки, знімок, звіт. Записує — виключно у власні таблиці
журналу (`enrichment_runs` / `enrichment_attempts`). Жодного шляху, яким
результат моделі міг би змінити знахідку, серйозність чи бал, звідси
фізично немає.

## Два замки, і обидва мусять відімкнутися

1. **Експериментальний шлюз** — `settings.enrich_enabled` (дефолт
   `False`) АБО явний `experimental=True` від внутрішнього тригера
   (CLI/бенчмарк). Клієнтських шляхів, що передають цей прапорець, не
   існує: жоден маршрут API його не виставляє.
2. **Придатність аудиту** — окрема від глобального прапорця межа:
   безкоштовний гостьовий аудит без викупленого розблокування збагачення
   не отримує ніколи, незалежно від конфігурації. Майбутні тарифні
   entitlement-и підключаються сюди, не в AI-шар.

Рендеринг звіту НІКОЛИ не викликає провайдера: він читає збережені
результати (яких поки що жоден звіт і не читає — фаза експериментальна).
Мережева інференція живе тут і у фонових задачах.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application import guest as guest_app
from app.audit.enums import AuditStatus
from app.audit.snapshot import load as load_snapshot
from app.audit.types import SiteContext
from app.core.config import settings
from app.enrich.budgets import budget_for
from app.enrich.contracts import EnrichmentStatus, TaskRequest, TaskType
from app.enrich.providers import AIProvider, get_provider
from app.enrich.routing import ROUTING_VERSION, Routes
from app.enrich.runner import execute as run_task
from app.enrich.tasks import TASKS, build_request
from app.identity.enums import OrganizationKind
from app.models import Audit, AuditTarget, EnrichmentAttempt, EnrichmentRun, Organization
from app.report import build_report
from app.report.coverage import coverage_facts
from app.report.types import ReportDocument
from app.services import report_service

# Канонічна мова фази 1. Локаль — частина ідентичності результату, тож
# майбутня локалізація наративу створить НОВІ рядки, а не перепише ці.
CANONICAL_LOCALE = "en"


class EnrichmentDenied(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def eligibility_reason(
    *,
    audit_status: AuditStatus,
    organization_kind: OrganizationKind,
    unlocked: bool,
) -> str | None:
    """Чиста функція межі придатності: None — можна, інакше причина.

    Безкоштовний аудит детерміністичний завжди: гостьова організація без
    викупленого розблокування — це «free», і жоден глобальний прапорець
    цього не перекриває. Гість, що заплатив, — уже «повний» аудит.
    """
    if audit_status not in (AuditStatus.COMPLETED, AuditStatus.PARTIAL):
        return "audit.not_finished"
    if organization_kind is OrganizationKind.GUEST and not unlocked:
        return "audit.free"
    return None


async def ensure_eligible(db: AsyncSession, audit: Audit) -> None:
    org = await db.get(Organization, audit.organization_id)
    if org is None:
        raise EnrichmentDenied("organization.missing")
    unlocked = False
    if org.kind is OrganizationKind.GUEST:
        unlocked = await guest_app.is_unlocked(db, audit.id)
    reason = eligibility_reason(
        audit_status=audit.status, organization_kind=org.kind, unlocked=unlocked
    )
    if reason is not None:
        raise EnrichmentDenied(reason)


async def _load_audit(db: AsyncSession, audit_id: uuid.UUID) -> Audit:
    """Аудит разом із цілями та знахідками — усе, з чого збирається вхід.

    Явна жадібна вибірка, бо збирачі входів синхронні: ліниве
    підвантаження звідти падає `MissingGreenlet` замість того, щоб
    просто спрацювати повільніше.
    """
    audit = await db.scalar(
        select(Audit)
        .where(Audit.id == audit_id)
        .options(selectinload(Audit.targets).selectinload(AuditTarget.issues))
        # Стан із бази, а не з мапи ідентичності сесії: на цьому читанні
        # тримається перевірка «чи не змінився вхід», і закешований
        # обʼєкт відповів би на неї вчорашніми даними.
        .execution_options(populate_existing=True)
    )
    if audit is None:
        raise EnrichmentDenied("audit.missing")
    return audit


def _ensure_gate(experimental: bool) -> None:
    """Фаза 1 за шлюзом: без явного експериментального тригера — відмова.

    Клієнтських шляхів із `experimental=True` не існує; його передають
    лише внутрішні інструменти (CLI, бенчмарк). Це і є вимога «не лише
    env-прапорець»: навіть із `ENRICH_ENABLED=true` жоден наявний
    продуктовий потік збагачення не запускає — його ніхто не викликає.
    """
    if not (settings.enrich_enabled or experimental):
        raise EnrichmentDenied("enrichment.disabled")


async def start_run(
    db: AsyncSession,
    audit_id: uuid.UUID,
    task_type: TaskType,
    *,
    experimental: bool = False,
    locale: str = CANONICAL_LOCALE,
) -> EnrichmentRun:
    """Ідемпотентно отримати або створити логічний прогін.

    Той самий аудит + задача + версії + вхід → той самий рядок: повторний
    виклик (оновлення сторінки, повторна постановка в чергу, конкурентний
    запит) не породжує другої логічної роботи. Гонка двох перших викликів
    вирішується унікальним індексом, а не удачею.
    """
    _ensure_gate(experimental)
    audit = await _load_audit(db, audit_id)
    await ensure_eligible(db, audit)

    spec = TASKS[task_type]
    payload = await build_task_input(db, audit, task_type)
    request = build_request(spec, payload, locale=locale)

    existing = await _find_run(db, audit_id, request)
    if existing is not None:
        return existing

    run = EnrichmentRun(
        audit_id=audit_id,
        task_type=task_type,
        task_version=spec.version,
        prompt_version=spec.prompt_version,
        schema_version=spec.schema_version,
        routing_version=ROUTING_VERSION,
        locale=locale,
        input_hash=request.input_hash,
        status=EnrichmentStatus.PENDING,
    )
    db.add(run)
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        # Хтось створив той самий логічний прогін між нашим SELECT і
        # INSERT. Його рядок і є результатом — наш не потрібен.
        db.expunge(run)
        found = await _find_run(db, audit_id, request)
        if found is None:
            raise
        return found
    return run


async def _find_run(
    db: AsyncSession, audit_id: uuid.UUID, request: TaskRequest
) -> EnrichmentRun | None:
    return await db.scalar(
        select(EnrichmentRun).where(
            EnrichmentRun.audit_id == audit_id,
            EnrichmentRun.task_type == request.task_type,
            EnrichmentRun.task_version == request.task_version,
            EnrichmentRun.prompt_version == request.prompt_version,
            EnrichmentRun.schema_version == request.schema_version,
            EnrichmentRun.input_hash == request.input_hash,
        )
    )


async def execute_run(
    db: AsyncSession,
    run_id: uuid.UUID,
    *,
    routes: Routes | None = None,
    provider_factory: Callable[[str], AIProvider] = get_provider,
) -> EnrichmentRun:
    """Виконати прогін і записати результат та кожну спробу.

    COMPLETED-рядок не виконується вдруге ніколи: збережений результат
    зберігає свою провенансію, скільки б разів виконання не просили.
    Перегенерація завершеного — лише новою версією задачі/промпта/схеми
    (це нова ідентичність, отже новий рядок). FAILED/UNAVAILABLE рядок
    повторний виклик перезапускає: спроби додаються до журналу далі,
    старі не зникають.
    """
    run = await db.get(EnrichmentRun, run_id)
    if run is None:
        raise EnrichmentDenied("run.missing")
    if run.status is EnrichmentStatus.COMPLETED:
        return run
    if run.status is EnrichmentStatus.RUNNING:
        return run

    audit = await _load_audit(db, run.audit_id)

    spec = TASKS[run.task_type]
    payload = await build_task_input(db, audit, run.task_type)
    request = build_request(spec, payload, locale=run.locale)
    if request.input_hash != run.input_hash:
        # Детерміністичний матеріал аудиту змінився з моменту постановки
        # (наприклад, перерахунок). Результат для старого входу вводив би
        # в оману; новий вхід — нова ідентичність, окремий прогін.
        run.status = EnrichmentStatus.FAILED
        run.error = "вхід аудиту змінився після постановки прогону"
        run.completed_at = datetime.now(UTC)
        return run

    run.status = EnrichmentStatus.RUNNING
    run.started_at = datetime.now(UTC)
    await db.flush()

    # Бюджет виконання — задачі, а не глобальний: одна стеля на всіх
    # обривала більші задачі v2 на середині JSON.
    budget = budget_for(run.task_type)
    outcome = await run_task(
        spec,
        request,
        routes=routes,
        provider_factory=provider_factory,
        timeout_s=budget.timeout_s,
        max_attempts=settings.enrich_max_attempts,
        max_output_tokens=budget.max_output_tokens,
    )

    offset = await db.scalar(
        select(EnrichmentAttempt.number)
        .where(EnrichmentAttempt.run_id == run.id)
        .order_by(EnrichmentAttempt.number.desc())
        .limit(1)
    )
    base = int(offset or 0)
    for attempt in outcome.attempts:
        db.add(
            EnrichmentAttempt(
                run_id=run.id,
                number=base + attempt.number,
                provider=attempt.provider,
                model=attempt.model,
                requested_model=attempt.requested_model or attempt.model,
                pricing_key=attempt.pricing_key,
                request_id=attempt.request_id,
                started_at=datetime.fromisoformat(attempt.started_at),
                finished_at=datetime.fromisoformat(attempt.finished_at),
                latency_ms=attempt.latency_ms,
                outcome=attempt.outcome.value,
                error_category=attempt.error_category,
                error=attempt.error,
                input_tokens=attempt.input_tokens,
                output_tokens=attempt.output_tokens,
                cache_write_tokens=attempt.cache_write_tokens,
                cache_read_tokens=attempt.cache_read_tokens,
                total_tokens=attempt.total_tokens,
                cost_usd=attempt.cost_usd,
                pricing_version=attempt.pricing_version,
            )
        )

    run.status = outcome.status
    run.result = outcome.result or {}
    run.error = outcome.error
    run.completed_at = datetime.now(UTC)
    await db.flush()
    return run


# ── входи задач зі збереженого детерміністичного матеріалу ────────────────


async def build_task_input(
    db: AsyncSession, audit: Audit, task_type: TaskType
) -> dict[str, object]:
    if task_type is TaskType.SITE_UNDERSTANDING:
        return _site_understanding_input(audit)
    if task_type is TaskType.ROOT_CAUSE_GROUPING:
        return _findings_input(audit, with_site=True)
    return await _remediation_input(db, audit)


def _coverage_of(document: ReportDocument) -> dict[str, object]:
    """Канонічні факти покриття — ті самі, що бачить клієнт у звіті.

    Без них модель не могла поважати межі прочитаного: на аудиті, де сім
    адрес із десяти не відповіли, вона написала «site-wide», бо ніхто не
    сказав їй протилежного. Другої системи покриття тут не заводиться —
    береться `report.coverage`.
    """
    return dict(coverage_facts(document))


def _primary_target(audit: Audit) -> AuditTarget:
    targets = sorted(audit.targets, key=lambda t: t.position)
    if not targets:
        raise EnrichmentDenied("audit.no_targets")
    return targets[0]


def site_understanding_payload(
    ctx: SiteContext, document: ReportDocument
) -> dict[str, object]:
    """Публічний вміст сторінок плюс канонічні межі прочитаного.

    Чиста функція: той самий вхід збирає і продуктовий шлях (зі знімка в
    БД), і бенчмарк (зі знімка у файлі). Інакше харнес міряв би не те,
    що виконує продукт.

    `document` потрібен саме заради покриття: воно живе у звіті, а не в
    контексті, і виводити його тут удруге означало б завести другу
    правду про те саме.
    """
    from app.enrich.tasks.site_understanding import MAX_PAGE_CHARS, MAX_PAGES

    pages = [p for p in ctx.ok_pages if p.text][:MAX_PAGES]
    if not pages:
        raise EnrichmentDenied("audit.no_content")
    return {
        "origin": ctx.origin,
        "coverage": _coverage_of(document),
        "pages": [
            {"url": p.url, "title": p.title or "", "text": p.text[:MAX_PAGE_CHARS]}
            for p in pages
        ],
    }


def findings_payload(document: ReportDocument, *, with_site: bool) -> dict[str, object]:
    """Знахідки з того самого детермінованого звіту, що бачить клієнт.

    Береться звіт, а не сирі issue-рядки: звіт уже згрупував входження в
    проблеми (5 сторінок без canonical = 1 пункт) і має стабільний
    `issue_key` — рівно той ідентифікатор, за яким рахується бал.
    Внутрішні UUID знахідок назовні не йдуть.
    """
    from app.enrich.tasks.root_cause import MAX_EVIDENCE_CHARS, MAX_FINDINGS

    findings = [
        {
            "ref": rec.issue_key,
            "module": rec.module.value,
            "severity": rec.severity.value,
            "title": rec.title,
            "pages": rec.affected_pages,
            # Детерміністичний обсяг знахідки: «site» чи «page». Модель
            # називала знахідки site-wide там, де двигун поставив page —
            # тепер вона бачить, що саме він стверджував.
            "scope": rec.scope,
            "examples": rec.affected_examples[:3],
            "evidence": _compact_evidence(rec.evidence, MAX_EVIDENCE_CHARS),
        }
        for rec in document.recommendations[:MAX_FINDINGS]
    ]
    site = ""
    if with_site:
        brief = (document.evidence or {}).get("site_brief") or {}
        if brief.get("analysed"):
            site = str(brief.get("tagline") or brief.get("description") or "")
    return {"findings": findings, "site": site, "coverage": _coverage_of(document)}


def remediation_payload(
    document: ReportDocument, groups: list[dict[str, object]]
) -> dict[str, object]:
    """Детерміністичний ранг пріоритету плюс кластери з їхньою впевненістю.

    `cause_confidence` переноситься з групування навмисно: саме на ньому
    тримається стеля причинності в плані. Група без цього поля (старий
    артефакт v1) читається як `unknown` — тобто найобережніше з можливого,
    а не як мовчазний дозвіл стверджувати причину.
    """
    base = findings_payload(document, with_site=True)
    base_findings: list[dict[str, object]] = list(base["findings"])  # type: ignore[call-overload]
    known = {f["ref"] for f in base_findings}
    return {
        "findings": [
            {"ref": f["ref"], "severity": f["severity"], "title": f["title"], "rank": rank}
            for rank, f in enumerate(base_findings, start=1)
        ],
        "groups": [
            {
                "id": g["id"],
                "cluster_summary": g.get("cluster_summary", g.get("title", "")),
                "cause_confidence": g.get("cause_confidence", "unknown"),
                "finding_refs": [r for r in g["finding_refs"] if r in known],  # type: ignore[union-attr]
            }
            for g in groups
            if any(r in known for r in g["finding_refs"])  # type: ignore[union-attr]
        ],
        "site": base["site"],
        "coverage": base["coverage"],
    }


def _document_of(audit: Audit) -> ReportDocument:
    target = _primary_target(audit)
    return build_report(report_service.source_from_target(audit, target))


def _site_understanding_input(audit: Audit) -> dict[str, object]:
    target = _primary_target(audit)
    snapshot = target.snapshot or {}
    if not snapshot:
        raise EnrichmentDenied("audit.no_snapshot")
    return site_understanding_payload(load_snapshot(snapshot), _document_of(audit))


def _findings_input(audit: Audit, *, with_site: bool) -> dict[str, object]:
    return findings_payload(_document_of(audit), with_site=with_site)


async def _remediation_input(db: AsyncSession, audit: Audit) -> dict[str, object]:
    """План спирається на групи причин, якщо їх уже отримано.

    Групи — частина канонічного входу, а отже й хеша: план, складений до
    групування, і план після нього — різні логічні роботи з власною
    провенансією, а не перезапис одна одної.
    """
    grouping = await db.scalar(
        select(EnrichmentRun)
        .where(
            EnrichmentRun.audit_id == audit.id,
            EnrichmentRun.task_type == TaskType.ROOT_CAUSE_GROUPING,
            EnrichmentRun.status == EnrichmentStatus.COMPLETED,
        )
        .order_by(EnrichmentRun.completed_at.desc())
        .limit(1)
    )
    groups = list(grouping.result.get("groups", [])) if grouping is not None else []
    return remediation_payload(_document_of(audit), groups)


def _compact_evidence(evidence: dict[str, object], limit: int) -> str:
    parts = []
    for key, value in evidence.items():
        rendered = str(value)
        if len(rendered) > 60:
            rendered = rendered[:60] + "…"
        parts.append(f"{key}={rendered}")
    return "; ".join(parts)[:limit]
