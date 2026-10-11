from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import i18n
from app.audit.enums import AuditTrigger
from app.audit.fetcher import origin_of
from app.audit.orchestrator import AuditOutcome, rescore
from app.audit.snapshot import dump as dump_snapshot
from app.audit.snapshot import load as load_snapshot
from app.core.run_enums import FailureClass
from app.models.audit import (
    Audit,
    AuditAttempt,
    AuditIssue,
    AuditPage,
    AuditStatus,
    AuditTarget,
)
from app.report.benchmark import Benchmark, Contender
from app.report.benchmark import compare as compare_contenders
from app.report.builder import build_evidence
from app.report.history import ScorePoint
from app.schemas.audit import AuditCreate

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


async def create_audit(
    session: AsyncSession,
    payload: AuditCreate,
    *,
    organization_id: uuid.UUID,
    site_id: uuid.UUID | None = None,
    created_by_user_id: uuid.UUID | None = None,
    trigger: AuditTrigger = AuditTrigger.MANUAL,
    schedule_id: uuid.UUID | None = None,
    scheduled_for: datetime | None = None,
    requested_options: dict[str, Any] | None = None,
) -> Audit:
    targets = payload.targets
    audit = Audit(
        organization_id=organization_id,
        site_id=site_id,
        created_by_user_id=created_by_user_id,
        trigger=trigger,
        schedule_id=schedule_id,
        scheduled_for=scheduled_for,
        # Порожньо означає «просили рівно те, що зробили»: так виглядають
        # аудити, створені не через продуктовий шар (CLI, перерахунок).
        requested_options=requested_options or {},
        # url/origin на аудиті — первинна ціль: так старі клієнти API,
        # які читають ці поля, не ламаються при кількох URL.
        url=targets[0],
        origin=origin_of(targets[0]),
        status=AuditStatus.QUEUED,
        options=payload.options.model_dump(mode="json"),
    )
    session.add(audit)
    await session.flush()

    for position, url in enumerate(targets):
        session.add(
            AuditTarget(
                audit_id=audit.id,
                position=position,
                url=url,
                origin=origin_of(url),
                status=AuditStatus.QUEUED,
            )
        )

    await session.commit()
    await session.refresh(audit)
    return audit


async def get_audit(
    session: AsyncSession,
    audit_id: uuid.UUID,
    *,
    organization_id: uuid.UUID | None = None,
) -> Audit | None:
    """Аудит за id, за потреби звужений до організації.

    `organization_id=None` лишається для воркера, який працює від імені
    системи й уже знає, який саме аудит виконує. Усі шляхи, куди приходить
    запит ззовні, зобов'язані його передавати — інакше чужий ідентифікатор
    дає чужі дані.

    Фільтр стоїть в умові запиту, а не після вибірки: перевірку після
    вибірки легко забути, і забуття не видно в коді. Відсутній рядок в
    умові видно одразу.
    """
    if organization_id is None:
        return await session.get(Audit, audit_id)
    stmt = select(Audit).where(Audit.id == audit_id, Audit.organization_id == organization_id)
    return (await session.scalars(stmt)).one_or_none()


async def list_audits(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID,
    site_id: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Audit]:
    stmt = select(Audit).where(Audit.organization_id == organization_id)
    if site_id is not None:
        stmt = stmt.where(Audit.site_id == site_id)
    stmt = stmt.order_by(Audit.created_at.desc()).limit(limit).offset(offset)
    return list((await session.scalars(stmt)).all())


async def count_audits(session: AsyncSession, *, organization_id: uuid.UUID) -> int:
    stmt = select(func.count(Audit.id)).where(Audit.organization_id == organization_id)
    return int(await session.scalar(stmt) or 0)


async def mark_running(session: AsyncSession, audit_id: uuid.UUID) -> None:
    audit = await session.get(Audit, audit_id)
    if audit is None:
        return
    audit.status = AuditStatus.RUNNING
    audit.started_at = datetime.now(UTC)
    await session.commit()


async def record_progress(
    session: AsyncSession,
    audit_id: uuid.UUID,
    *,
    stage: str,
    read: int,
    known: int,
) -> None:
    """Записати, де саме зараз аудит.

    Пишеться лише поки аудит РОБИТЬСЯ. Аудит із остаточним станом уже має
    результат, і рухати його показник ходу назад — значить показати
    клієнту рух там, де все скінчилось: черга вміє доставити те саме
    повідомлення двічі, а слухач живе стільки ж, скільки краул.
    """
    audit = await session.get(Audit, audit_id)
    if audit is None or audit.status.is_terminal:
        return
    audit.progress = {"stage": stage, "pages_read": read, "pages_known": known}
    await session.commit()


async def mark_failed(
    session: AsyncSession,
    audit_id: uuid.UUID,
    error: str,
    *,
    failure: FailureClass | None = None,
) -> None:
    audit = await session.get(Audit, audit_id)
    if audit is None:
        return
    audit.status = AuditStatus.FAILED
    audit.error = error[:2000]
    audit.failure_class = failure
    audit.finished_at = datetime.now(UTC)
    await session.commit()


async def mark_requeued(session: AsyncSession, audit_id: uuid.UUID, error: str) -> None:
    """Спроба не вийшла, але буде наступна.

    Статус повертається в `QUEUED`, бо це правда: запуск знову чекає на
    воркера. `finished_at` навмисно лишається порожнім — запуск не
    завершився. Текст останньої помилки зберігається: якщо повтори теж
    не вийдуть, він і буде відповіддю, а журнал спроб покаже, чи всі
    вони були однакові.
    """
    audit = await session.get(Audit, audit_id)
    if audit is None:
        return
    audit.status = AuditStatus.QUEUED
    audit.error = error[:2000]
    audit.started_at = None
    audit.finished_at = None
    await session.commit()


# ── журнал спроб ───────────────────────────────────────────────────────────


async def begin_attempt(
    session: AsyncSession, audit_id: uuid.UUID, number: int
) -> AuditAttempt | None:
    """Відкрити спробу під заданим номером.

    Номер приходить ззовні, а не рахується тут, і це важливо: черга може
    доставити те саме повідомлення двічі, і тоді обидві доставки мусять
    описувати **одну** спробу. Якби номер брався з лічильника, друга
    доставка дописала б спробу, якої не було.

    Гонку двох одночасних доставок ловить `uq_attempt_number`; тут же —
    звичайний шлях без винятків.
    """
    audit = await session.get(Audit, audit_id)
    if audit is None:
        return None

    stmt = select(AuditAttempt).where(
        AuditAttempt.audit_id == audit_id, AuditAttempt.number == number
    )
    attempt = (await session.execute(stmt)).scalars().first()
    if attempt is None:
        attempt = AuditAttempt(audit_id=audit_id, number=number, status=AuditStatus.RUNNING)
        session.add(attempt)

    audit.attempts = max(audit.attempts, number)
    audit.last_attempt_at = datetime.now(UTC)
    await session.commit()
    return attempt


async def finish_attempt(
    session: AsyncSession,
    audit_id: uuid.UUID,
    number: int,
    *,
    status: AuditStatus,
    failure: FailureClass | None = None,
    error: str = "",
    retry_decision_key: str = "",
    retry_decision_params: dict[str, Any] | None = None,
) -> None:
    """Закрити спробу. Мовчить, якщо її не відкривали: журнал — не тригер."""
    stmt = select(AuditAttempt).where(
        AuditAttempt.audit_id == audit_id, AuditAttempt.number == number
    )
    attempt = (await session.execute(stmt)).scalars().first()
    if attempt is None:
        return
    attempt.status = status
    attempt.failure_class = failure
    attempt.error = error[:2000]
    attempt.retry_decision_key = retry_decision_key
    attempt.retry_decision_params = _jsonable(retry_decision_params or {})
    # Канонічний рендер поруч із ключем: технічний слід у логах і в
    # старих клієнтах API, які поля ключа ще не знають.
    attempt.retry_decision = (
        i18n.notice(retry_decision_key, retry_decision_params or {})
        if retry_decision_key
        else ""
    )
    attempt.finished_at = datetime.now(UTC)
    await session.commit()


async def persist_outcome(
    session: AsyncSession, target_id: uuid.UUID, outcome: AuditOutcome
) -> None:
    """Зберігає результат ОДНІЄЇ цілі. Зведення по аудиту — у finalize_audit."""
    target = await session.get(AuditTarget, target_id)
    if target is None:
        return
    audit_id = target.audit_id

    page_ids: dict[str, uuid.UUID] = {}
    for signals in outcome.context.pages:
        # id генеруємо вручну: Python-side default застосовується лише на flush,
        # а нам треба зв'язати issue зі сторінкою до нього.
        page = AuditPage(
            id=uuid.uuid4(),
            audit_id=audit_id,
            target_id=target.id,
            url=signals.url,
            status_code=signals.status_code,
            content_type=signals.content_type,
            html_bytes=signals.html_bytes,
            response_ms=signals.response_ms,
            depth=signals.depth,
            raw=signals.to_json(),
        )
        session.add(page)
        page_ids[signals.url] = page.id

    # Обовʼязковий flush перед issues. Між audit_issues.page_id і audit_pages
    # є зовнішній ключ, але немає relationship — а порядок INSERT'ів при flush
    # SQLAlchemy будує саме за relationship'ами, не за FK на рівні таблиць.
    # Без цього рядка issues летять в INSERT раніше за сторінки, на які
    # посилаються, і Postgres відбиває їх ForeignKeyViolationError.
    await session.flush()

    for issue in outcome.issues:
        session.add(
            AuditIssue(
                audit_id=audit_id,
                target_id=target.id,
                page_id=page_ids.get(issue.page_url or ""),
                module=issue.module,
                code=issue.code,
                severity=issue.severity,
                title=issue.title,
                description=issue.description,
                recommendation=issue.recommendation,
                evidence=_evidence(issue),
                weight=issue.weight,
                issue_variant=issue.key,
                msg_key=issue.msg or issue.code,
                msg_params=_jsonable(issue.params),
            )
        )

    failures = [d for d in outcome.degraded if d.is_failure]
    target.url = outcome.context.entry_url
    target.origin = outcome.context.origin
    target.scores = outcome.scores
    target.score_overall = outcome.overall
    target.status = AuditStatus.PARTIAL if failures else AuditStatus.COMPLETED
    target.error = "; ".join(str(d) for d in failures)[:2000] if failures else None
    target.degraded = [d.to_json() for d in outcome.degraded]
    target.skipped_modules = sorted(m.value for m in outcome.skipped_modules)
    target.evidence = build_evidence(outcome.context)
    target.versions = outcome.versions
    # Знімок зібраного: з нього аудит перераховується за новими
    # правилами без повторного краулу — тобто по тому самому сайту,
    # а не по тому, яким він став через місяць.
    target.snapshot = dump_snapshot(outcome.context)
    target.finished_at = datetime.now(UTC)
    await session.commit()


async def mark_target_running(session: AsyncSession, target_id: uuid.UUID) -> None:
    target = await session.get(AuditTarget, target_id)
    if target is None:
        return
    target.status = AuditStatus.RUNNING
    target.started_at = datetime.now(UTC)
    # Слід минулої спроби стирається на початку наступної. Інакше ціль,
    # яка з другого разу вийшла, лишалася б із текстом першої помилки —
    # і звіт описував би невдачу, якої в результаті не було.
    target.error = None
    target.failure_class = None
    target.finished_at = None
    await session.commit()


async def mark_target_failed(
    session: AsyncSession,
    target_id: uuid.UUID,
    error: str,
    *,
    failure: FailureClass | None = None,
) -> None:
    """Падіння однієї цілі не має валити решту — аудит стане partial."""
    target = await session.get(AuditTarget, target_id)
    if target is None:
        return
    target.status = AuditStatus.FAILED
    target.error = error[:2000]
    target.failure_class = failure
    target.finished_at = datetime.now(UTC)
    await session.commit()


async def finalize_audit(session: AsyncSession, audit_id: uuid.UUID) -> None:
    """Зводить цілі в один результат аудиту.

    Загальний скор — незважене середнє по успішних цілях. Зважувати за
    кількістю сторінок не можна: великий сайт затопив би малий, хоча в
    аудиті вони рівноправні.
    """
    audit = await session.get(Audit, audit_id)
    if audit is None:
        return

    targets = sorted(audit.targets, key=lambda t: t.position)
    scored = [t for t in targets if t.score_overall is not None]

    if scored:
        audit.score_overall = round(sum(t.score_overall or 0 for t in scored) / len(scored))
    # Помодульні оцінки зводяться з усіх цілей, а не лише з тих, що мають
    # загальний бал. Без цього аудит сайту з простроченим хостингом
    # показував порожньо там, де ми таки виміряли швидкість і захист:
    # загального бала немає чесно, але викидати виміряне — ні.
    audit.scores = _average_module_scores(targets) or None

    primary = targets[0] if targets else None
    if primary is not None:
        audit.url = primary.url
        audit.origin = primary.origin
        audit.degraded = primary.degraded
        audit.skipped_modules = primary.skipped_modules
        audit.evidence = primary.evidence
        # Версії однакові для всіх цілей одного аудиту: вони про нас, а
        # не про сайт. Беремо з першої.
        audit.versions = primary.versions

    audit.status = _combined_status(targets)
    # Клас невдачі має існувати рівно тоді, коли є невдача: успішний
    # повтор мусить прибрати клас, залишений попередньою спробою.
    audit.failure_class = (
        _combined_failure(targets) if audit.status is AuditStatus.FAILED else None
    )
    errors = [f"{t.url}: {t.error}" for t in targets if t.error]
    audit.error = "; ".join(errors)[:2000] if errors else None
    audit.findings_summary = summarize_findings(audit.issues)
    audit.finished_at = datetime.now(UTC)
    await session.commit()


# Скільки різних проблем називати поіменно у зведенні.
#
# Двадцять п'ять — приблизно стільки, скільки пояснюють бал: далі йде
# хвіст поодиноких знахідок, які на оцінку майже не впливають, а місце в
# JSON займають. Зведення має пережити знахідки, а не замінити їх.
SUMMARY_TOP_KEYS = 25


def summarize_findings(issues: list[AuditIssue]) -> dict[str, Any]:
    """Зведення, яке лишиться, коли самих знахідок уже не буде.

    Рахується при завершенні аудиту, а не при чистці. Різниця в тому, чи
    можна на нього покластися: порахований при чистці, він залежав би від
    того, коли job дійшов до цього рядка, і для аудиту, видаленого раніше
    строку, його б не існувало взагалі.
    """
    by_severity: Counter[str] = Counter()
    by_module: Counter[str] = Counter()
    by_key: Counter[str] = Counter()
    severity_of: dict[str, str] = {}
    module_of: dict[str, str] = {}

    for issue in issues:
        key = f"{issue.code}:{issue.issue_variant}" if issue.issue_variant else issue.code
        by_severity[issue.severity.value] += 1
        by_module[issue.module.value] += 1
        by_key[key] += 1
        # Серйозність однієї проблеми однакова в усіх її входженнях;
        # беремо найгіршу на випадок, коли чек її все ж змінює.
        current = severity_of.get(key)
        if current is None or SEVERITY_ORDER[issue.severity.value] < SEVERITY_ORDER[current]:
            severity_of[key] = issue.severity.value
        module_of.setdefault(key, issue.module.value)

    top = sorted(
        by_key.items(), key=lambda kv: (SEVERITY_ORDER[severity_of[kv[0]]], -kv[1], kv[0])
    )[:SUMMARY_TOP_KEYS]
    return {
        "total": sum(by_key.values()),
        "distinct_keys": len(by_key),
        "by_severity": dict(by_severity),
        "by_module": dict(by_module),
        "top": [
            {
                "issue_key": key,
                "severity": severity_of[key],
                "module": module_of[key],
                "count": count,
            }
            for key, count in top
        ],
    }


def _average_module_scores(targets: list[AuditTarget]) -> dict[str, int]:
    """Середнє по модулях. Модуль, пропущений скрізь, у зведення не потрапляє."""
    totals: dict[str, list[int]] = {}
    for target in targets:
        for module, score in (target.scores or {}).items():
            totals.setdefault(module, []).append(score)
    return {m: round(sum(v) / len(v)) for m, v in totals.items() if v}


# Чия невдача важить більше, коли цілі впали з різних причин.
#
# Порядок не за серйозністю, а за тим, **чиє** це: сумнів вирішується на
# користь клієнта. Аудит, у якому одна ціль не достукалася до сайту, а
# друга впала на нашому коді, — це наша невдача, і платити за неї має не
# він. Зворотний порядок дав би рівно протилежне.
_FAILURE_PRECEDENCE = (
    FailureClass.INTERNAL_ERROR,
    FailureClass.PROVIDER_FAILED,
    FailureClass.CANCELLED,
    FailureClass.SITE_BLOCKED,
    FailureClass.SITE_UNREACHABLE,
)


def _combined_failure(targets: list[AuditTarget]) -> FailureClass | None:
    """Клас невдачі всього запуску за класами його цілей."""
    found = {t.failure_class for t in targets if t.failure_class is not None}
    for candidate in _FAILURE_PRECEDENCE:
        if candidate in found:
            return candidate
    return None


def _combined_status(targets: list[AuditTarget]) -> AuditStatus:
    if not targets:
        return AuditStatus.FAILED
    statuses = {t.status for t in targets}
    if statuses == {AuditStatus.FAILED}:
        return AuditStatus.FAILED
    if statuses <= {AuditStatus.COMPLETED}:
        return AuditStatus.COMPLETED
    # Щось виконалось, щось ні — це саме partial, а не failed.
    return AuditStatus.PARTIAL


def summarize(audit: Audit) -> dict[str, int]:
    return dict(Counter(issue.severity.value for issue in audit.issues))


def sort_issues(issues: list[AuditIssue]) -> list[AuditIssue]:
    return sorted(issues, key=lambda i: (SEVERITY_ORDER[i.severity.value], i.module.value, i.code))


def _evidence(issue) -> dict:
    """Кладемо page_url всередину evidence, щоб API міг показати його без join."""
    base = _jsonable(issue.evidence)
    return base | ({"page_url": issue.page_url} if issue.page_url else {})


def _jsonable(value: object) -> dict:
    """evidence може містити tuple/set — приводимо до JSON-сумісного вигляду."""
    import json

    try:
        json.dumps(value)
        return dict(value) if isinstance(value, dict) else {"value": value}
    except (TypeError, ValueError):
        return json.loads(json.dumps(value, default=str))


async def score_history(
    session: AsyncSession,
    origin: str,
    *,
    organization_id: uuid.UUID,
    limit: int = 50,
    since: datetime | None = None,
) -> list[ScorePoint]:
    """Точки історії для одного сайту, від найстарішої до найновішої.

    Ключ — origin цілі, а не URL аудиту: той самий сайт замовляють і як
    `example.com`, і як `https://www.example.com/`, і історія від цього
    не має розпадатися на дві.

    Обов'язково в межах організації. Без цього достатньо було б знати
    чужий домен, щоб побачити чужу історію балів — а це і є те, за що
    платять. Приєднання до `audits` тут не оптимізація, а межа доступу.
    """
    stmt = (
        select(AuditTarget)
        .join(Audit, Audit.id == AuditTarget.audit_id)
        .where(Audit.organization_id == organization_id)
        .where(AuditTarget.origin == origin)
        .where(AuditTarget.status.in_((AuditStatus.COMPLETED, AuditStatus.PARTIAL)))
        .order_by(AuditTarget.finished_at.desc())
        .limit(limit)
    )
    if since is not None:
        # Вікно видимості тарифу. Дані старіші за нього існують і не
        # чіпаються — їх просто не показуємо, і апгрейд поверне їх.
        #
        # Точка без часу лишається видимою: щоб сховати, треба довести,
        # що вона за вікном, а недатоване довести нема чим.
        stmt = stmt.where(
            or_(AuditTarget.finished_at.is_(None), AuditTarget.finished_at >= since)
        )
    targets = list((await session.scalars(stmt)).all())
    points = [
        ScorePoint(
            audit_id=str(target.audit_id),
            at=target.finished_at or datetime.now(UTC),
            overall=target.score_overall,
            scores=dict(target.scores or {}),
            versions=dict(target.versions or {}),
            has_snapshot=bool(target.snapshot),
        )
        for target in targets
    ]
    return sorted(points, key=lambda p: p.at)


async def score_history_for_site(
    session: AsyncSession,
    *,
    site_id: uuid.UUID,
    organization_id: uuid.UUID,
    limit: int = 50,
    since: datetime | None = None,
) -> list[ScorePoint]:
    """Історія балів сайту як бізнес-ресурсу.

    Ключ — `site_id`, а не рядок origin. Різниця в тому, що переживе
    зміну адреси: сайт лишається тим самим ресурсом організації, навіть
    якщо завтра він відповідатиме на іншому хості, а історія за origin
    розсипалася б надвоє.

    Саме тому об'єднання двох сайтів у майбутньому не потребує
    переписування минулого: досить перевести `audits.site_id` — самі
    аудити, їхні origin і бали лишаються недоторканими.
    """
    stmt = (
        select(AuditTarget)
        .join(Audit, Audit.id == AuditTarget.audit_id)
        .where(Audit.organization_id == organization_id, Audit.site_id == site_id)
        .where(AuditTarget.status.in_((AuditStatus.COMPLETED, AuditStatus.PARTIAL)))
        .order_by(AuditTarget.finished_at.desc())
        .limit(limit)
    )
    if since is not None:
        stmt = stmt.where(
            or_(AuditTarget.finished_at.is_(None), AuditTarget.finished_at >= since)
        )
    targets = list((await session.scalars(stmt)).all())
    points = [
        ScorePoint(
            audit_id=str(target.audit_id),
            at=target.finished_at or datetime.now(UTC),
            overall=target.score_overall,
            scores=dict(target.scores or {}),
            versions=dict(target.versions or {}),
            has_snapshot=bool(target.snapshot),
        )
        for target in targets
    ]
    return sorted(points, key=lambda p: p.at)


async def rescore_target(
    session: AsyncSession, target_id: uuid.UUID, *, organization_id: uuid.UUID
) -> tuple[ScorePoint, ScorePoint] | None:
    """Перерахунок збереженого аудиту нинішніми правилами.

    Нічого не переписує в базі: повертає стару точку й нову поруч. Що
    робити з різницею — рішення читача, а мовчки підмінити збережений
    бал означало б переписати історію.

    Ціль шукається разом з умовою про організацію: чужа ціль для того,
    хто питає, не існує.
    """
    stmt = (
        select(AuditTarget)
        .join(Audit, Audit.id == AuditTarget.audit_id)
        .where(AuditTarget.id == target_id, Audit.organization_id == organization_id)
    )
    target = (await session.scalars(stmt)).one_or_none()
    if target is None or not target.snapshot:
        return None
    outcome = rescore(load_snapshot(target.snapshot))
    stored = ScorePoint(
        audit_id=str(target.audit_id),
        at=target.finished_at or datetime.now(UTC),
        overall=target.score_overall,
        scores=dict(target.scores or {}),
        versions=dict(target.versions or {}),
        has_snapshot=True,
    )
    recomputed = ScorePoint(
        audit_id=str(target.audit_id),
        at=stored.at,
        overall=outcome.overall,
        scores=outcome.scores,
        versions=outcome.versions,
        has_snapshot=True,
    )
    return stored, recomputed


async def benchmark_targets(
    session: AsyncSession,
    audit_id: uuid.UUID,
    subject_id: uuid.UUID | None = None,
    *,
    organization_id: uuid.UUID,
) -> Benchmark | None:
    """Порівняння цілей одного аудиту: ви й конкуренти.

    Носій для порівняння вже був — аудит на кілька URL. Бракувало саме
    прочитання: кілька цілей це не просто кілька звітів, а ви на тлі
    решти.

    Ціль за замовчуванням — перша (position 0): її й замовляли, решту
    додали для порівняння.
    """
    audit = await get_audit(session, audit_id, organization_id=organization_id)
    if audit is None or not audit.targets:
        return None

    contenders = [_contender(t) for t in audit.targets]
    by_id = {str(t.id): c for t, c in zip(audit.targets, contenders, strict=True)}
    subject = by_id.get(str(subject_id)) if subject_id else contenders[0]
    if subject is None:
        return None
    return compare_contenders(subject, [c for c in contenders if c is not subject])


def _contender(target: AuditTarget) -> Contender:
    return Contender(
        label=target.url,
        origin=target.origin,
        overall=target.score_overall,
        scores=dict(target.scores or {}),
        versions=dict(target.versions or {}),
        # Ключ повідомлення, а не код: різні проблеми під одним кодом —
        # різні дії, і в порівнянні так само.
        findings={issue.msg_key or issue.code for issue in target.issues},
    )
