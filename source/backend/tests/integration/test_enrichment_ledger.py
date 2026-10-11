"""Журнал збагачення на живій базі: ідемпотентність, шлюз, провенанс.

Ці властивості неможливо перевірити на чистих шарах: унікальний індекс
ідентичності, поведінка при гонці двох запитів і те, що продуктові
маршрути не роблять жодного виклику, живуть саме в базі й у застосунку.

Жодного мережевого виклику: провайдер скриптований, лічильник звернень —
і є доказом «нуль викликів».
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import enrichment
from app.audit.enums import AuditStatus, Module, Severity
from app.enrich.contracts import EnrichmentStatus, ProviderError, TaskType
from app.enrich.providers.scripted import ScriptedProvider
from app.enrich.routing import RouteCandidate
from app.enrich.tasks import TASKS
from app.identity.enums import OrganizationKind
from app.models.audit import Audit, AuditIssue, AuditTarget
from app.models.enrich import EnrichmentAttempt, EnrichmentRun
from app.models.identity import Organization

pytestmark = pytest.mark.asyncio


async def _audit(
    db: AsyncSession,
    *,
    kind: OrganizationKind = OrganizationKind.TEAM,
    status: AuditStatus = AuditStatus.COMPLETED,
) -> Audit:
    """Готовий детерміністичний аудит: організація, ціль, знахідки."""
    org = Organization(name="test", slug=f"org-{uuid.uuid4().hex[:8]}", kind=kind)
    db.add(org)
    await db.flush()

    audit = Audit(
        organization_id=org.id,
        url="https://example.com/",
        origin="https://example.com",
        status=status,
        score_overall=61,
    )
    db.add(audit)
    await db.flush()

    target = AuditTarget(
        audit_id=audit.id,
        position=0,
        url="https://example.com/",
        origin="https://example.com",
        status=status,
        score_overall=61,
        scores={"seo": 55},
        evidence={"crawl": {"pages_ok": 4}},
    )
    db.add(target)
    await db.flush()

    for code, variant, severity in (
        ("seo.canonical", "missing", Severity.HIGH),
        ("seo.title", "duplicate", Severity.MEDIUM),
    ):
        db.add(
            AuditIssue(
                audit_id=audit.id,
                target_id=target.id,
                module=Module.SEO,
                code=code,
                issue_variant=variant,
                severity=severity,
                title=f"{code} {variant}",
                description="d",
                recommendation="r",
                evidence={"found": 3},
                weight=2,
                msg_key=code,
                msg_params={},
            )
        )
    await db.flush()
    await db.refresh(audit, ["targets"])
    return audit


def _routes(task: TaskType, provider: str = "fake") -> dict:
    return {task: (RouteCandidate(provider, "model-x"),)}


def _dry_provider(task: TaskType, payload: dict) -> ScriptedProvider:
    spec = TASKS[task]
    return ScriptedProvider("fake", lambda _call: spec.dry_output(payload))


async def _execute(
    db: AsyncSession, run_id: uuid.UUID, task: TaskType, payload: dict, provider: ScriptedProvider
) -> EnrichmentRun:
    """Виконання через ті самі двері, що й у продукті: маршрут + фабрика."""
    return await enrichment.execute_run(
        db, run_id, routes=_routes(task), provider_factory=lambda _name: provider
    )


# ── шлюз і придатність ────────────────────────────────────────────────────


async def test_disabled_by_default_refuses_to_start(db_session: AsyncSession):
    """Без явного експериментального тригера шар не запускається."""
    audit = await _audit(db_session)
    with pytest.raises(enrichment.EnrichmentDenied) as exc:
        await enrichment.start_run(db_session, audit.id, TaskType.ROOT_CAUSE_GROUPING)
    assert exc.value.reason == "enrichment.disabled"


async def test_free_guest_audit_is_never_eligible(db_session: AsyncSession):
    """Безкоштовний анонімний аудит лишається детерміністичним завжди.

    Не через глобальний прапорець: навіть із явним експериментальним
    тригером межа придатності відмовляє.
    """
    audit = await _audit(db_session, kind=OrganizationKind.GUEST)
    with pytest.raises(enrichment.EnrichmentDenied) as exc:
        await enrichment.start_run(
            db_session, audit.id, TaskType.ROOT_CAUSE_GROUPING, experimental=True
        )
    assert exc.value.reason == "audit.free"

    runs = (await db_session.scalars(select(EnrichmentRun))).all()
    assert not runs, "непридатний аудит не має лишати рядків у журналі"


async def test_unfinished_audit_is_not_eligible(db_session: AsyncSession):
    audit = await _audit(db_session, status=AuditStatus.RUNNING)
    with pytest.raises(enrichment.EnrichmentDenied) as exc:
        await enrichment.start_run(
            db_session, audit.id, TaskType.ROOT_CAUSE_GROUPING, experimental=True
        )
    assert exc.value.reason == "audit.not_finished"


async def test_eligibility_is_a_boundary_not_a_flag():
    """Межа придатності — чиста функція, придатна для майбутніх тарифів."""
    assert (
        enrichment.eligibility_reason(
            audit_status=AuditStatus.COMPLETED,
            organization_kind=OrganizationKind.GUEST,
            unlocked=False,
        )
        == "audit.free"
    )
    # Гість, що заплатив, — уже повний аудит.
    assert (
        enrichment.eligibility_reason(
            audit_status=AuditStatus.COMPLETED,
            organization_kind=OrganizationKind.GUEST,
            unlocked=True,
        )
        is None
    )
    assert (
        enrichment.eligibility_reason(
            audit_status=AuditStatus.PARTIAL,
            organization_kind=OrganizationKind.TEAM,
            unlocked=False,
        )
        is None
    )


# ── ідемпотентність ───────────────────────────────────────────────────────


async def test_same_logical_work_resolves_to_one_run(db_session: AsyncSession):
    """Друге звернення знаходить той самий рядок, а не створює новий."""
    audit = await _audit(db_session)
    task = TaskType.ROOT_CAUSE_GROUPING

    first = await enrichment.start_run(db_session, audit.id, task, experimental=True)
    second = await enrichment.start_run(db_session, audit.id, task, experimental=True)

    assert first.id == second.id
    rows = (await db_session.scalars(select(EnrichmentRun))).all()
    assert len(rows) == 1


async def test_completed_run_is_never_executed_twice(db_session: AsyncSession):
    """Повторне відкриття звіту не породжує другого платного виклику."""
    audit = await _audit(db_session)
    task = TaskType.ROOT_CAUSE_GROUPING
    run = await enrichment.start_run(db_session, audit.id, task, experimental=True)
    payload = await enrichment.build_task_input(db_session, audit, task)
    provider = _dry_provider(task, payload)

    done = await _execute(db_session, run.id, task, payload, provider)
    assert done.status is EnrichmentStatus.COMPLETED
    assert len(provider.calls) == 1

    again = await _execute(db_session, run.id, task, payload, provider)
    assert again.status is EnrichmentStatus.COMPLETED
    assert len(provider.calls) == 1, "завершений прогін виконали вдруге"
    assert again.result == done.result


async def test_identity_collision_is_settled_by_the_database(db_session: AsyncSession):
    """Гонка двох перших запитів не створює двох логічних робіт.

    Унікальний індекс, а не удача з порядком: перевіряємо, що вставка
    другого рядка з тією самою ідентичністю відбивається.
    """
    audit = await _audit(db_session)
    task = TaskType.ROOT_CAUSE_GROUPING
    run = await enrichment.start_run(db_session, audit.id, task, experimental=True)

    duplicate = EnrichmentRun(
        audit_id=run.audit_id,
        task_type=run.task_type,
        task_version=run.task_version,
        prompt_version=run.prompt_version,
        schema_version=run.schema_version,
        routing_version=run.routing_version,
        locale=run.locale,
        input_hash=run.input_hash,
    )
    from sqlalchemy.exc import IntegrityError

    # Савпойнт, а не rollback: відкат усієї транзакції забрав би базу
    # в решти тесту разом із фікстурою.
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            db_session.add(duplicate)
            await db_session.flush()


# ── провенанс ─────────────────────────────────────────────────────────────


async def test_run_and_attempts_persist_full_provenance(db_session: AsyncSession):
    audit = await _audit(db_session)
    task = TaskType.ROOT_CAUSE_GROUPING
    run = await enrichment.start_run(db_session, audit.id, task, experimental=True)
    payload = await enrichment.build_task_input(db_session, audit, task)
    done = await _execute(db_session, run.id, task, payload, _dry_provider(task, payload))

    spec = TASKS[task]
    assert done.task_version == spec.version
    assert done.prompt_version == spec.prompt_version
    assert done.schema_version == spec.schema_version
    assert done.routing_version
    assert len(done.input_hash) == 64
    assert done.started_at and done.completed_at

    attempts = (
        await db_session.scalars(
            select(EnrichmentAttempt).where(EnrichmentAttempt.run_id == run.id)
        )
    ).all()
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt.provider == "fake"
    assert attempt.model == "model-x"
    assert attempt.outcome == "ok"
    assert attempt.input_tokens and attempt.output_tokens
    assert attempt.total_tokens == attempt.input_tokens + attempt.output_tokens
    assert attempt.latency_ms is not None
    # Цінової бази немає — і журнал каже саме це, а не правдоподібне число.
    assert attempt.cost_usd is None
    assert attempt.pricing_version is None


async def test_failed_attempts_are_kept_when_the_run_is_retried(db_session: AsyncSession):
    """Повтор невдалого прогону дописує спроби, а не стирає історію."""
    audit = await _audit(db_session)
    task = TaskType.ROOT_CAUSE_GROUPING
    run = await enrichment.start_run(db_session, audit.id, task, experimental=True)
    payload = await enrichment.build_task_input(db_session, audit, task)

    broken = ScriptedProvider("fake", fail_with=ProviderError("provider_error", "503"))
    failed = await _execute(db_session, run.id, task, payload, broken)
    assert failed.status is EnrichmentStatus.UNAVAILABLE

    fixed = await _execute(db_session, run.id, task, payload, _dry_provider(task, payload))
    assert fixed.status is EnrichmentStatus.COMPLETED

    attempts = (
        await db_session.scalars(
            select(EnrichmentAttempt)
            .where(EnrichmentAttempt.run_id == run.id)
            .order_by(EnrichmentAttempt.number)
        )
    ).all()
    assert len(attempts) >= 2, "історія невдалих спроб зникла"
    assert attempts[0].outcome == "provider_error"
    assert attempts[-1].outcome == "ok"
    assert [a.number for a in attempts] == sorted({a.number for a in attempts})


# ── межа правди ───────────────────────────────────────────────────────────


async def test_enrichment_never_touches_deterministic_truth(db_session: AsyncSession):
    """Бал, знахідки й серйозності до і після збагачення — ті самі."""
    audit = await _audit(db_session)
    task = TaskType.ROOT_CAUSE_GROUPING

    before_score = audit.score_overall
    before_issues = sorted(
        (i.code, i.issue_variant, i.severity, i.title)
        for i in (await db_session.scalars(select(AuditIssue))).all()
    )
    target = (await db_session.scalars(select(AuditTarget))).one()
    before_target = (target.score_overall, dict(target.scores or {}))

    run = await enrichment.start_run(db_session, audit.id, task, experimental=True)
    payload = await enrichment.build_task_input(db_session, audit, task)
    done = await _execute(db_session, run.id, task, payload, _dry_provider(task, payload))
    assert done.status is EnrichmentStatus.COMPLETED

    await db_session.refresh(audit)
    await db_session.refresh(target)
    after_issues = sorted(
        (i.code, i.issue_variant, i.severity, i.title)
        for i in (await db_session.scalars(select(AuditIssue))).all()
    )
    assert audit.score_overall == before_score
    assert after_issues == before_issues
    assert (target.score_overall, dict(target.scores or {})) == before_target


async def test_task_failure_leaves_the_audit_and_report_usable(db_session: AsyncSession):
    """Провал збагачення не робить аудит невдалим і не ламає звіт."""
    from app.report import build_report
    from app.services import report_service

    audit = await _audit(db_session)
    task = TaskType.ROOT_CAUSE_GROUPING
    run = await enrichment.start_run(db_session, audit.id, task, experimental=True)
    payload = await enrichment.build_task_input(db_session, audit, task)

    broken = ScriptedProvider("fake", fail_with=ProviderError("provider_error", "провайдер лежить"))
    done = await _execute(db_session, run.id, task, payload, broken)

    assert done.status is EnrichmentStatus.UNAVAILABLE
    assert done.result == {}
    await db_session.refresh(audit)
    assert audit.status is AuditStatus.COMPLETED, "збій AI зробив аудит невдалим"

    target = (await db_session.scalars(select(AuditTarget))).one()
    document = build_report(report_service.source_from_target(audit, target))
    assert document.recommendations, "звіт лишається придатним без збагачення"


async def test_input_hash_change_does_not_silently_rewrite_history(db_session: AsyncSession):
    """Якщо матеріал аудиту змінився після постановки — прогін не бреше.

    Старий вхід уже не описує аудит, і видати результат за актуальний
    означало б показати клієнту висновок про дані, яких більше немає.
    """
    audit = await _audit(db_session)
    task = TaskType.ROOT_CAUSE_GROUPING
    run = await enrichment.start_run(db_session, audit.id, task, experimental=True)
    payload = await enrichment.build_task_input(db_session, audit, task)

    issue = (await db_session.scalars(select(AuditIssue))).first()
    assert issue is not None
    await db_session.delete(issue)
    await db_session.flush()

    done = await _execute(db_session, run.id, task, payload, _dry_provider(task, payload))
    assert done.status is EnrichmentStatus.FAILED
    assert "змінився" in (done.error or "")


# ── нуль викликів на продуктових шляхах ───────────────────────────────────


async def test_report_rendering_makes_no_provider_calls(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """Рендер звіту — JSON і DOCX — не звертається до провайдера ніколи.

    Не «не має»: реєстр провайдерів підмінений на вибух, тож будь-яке
    звернення провалило б тест.
    """
    from app.report import build_report
    from app.report.docx import render_docx
    from app.services import report_service

    def explode(_name: str):
        raise AssertionError("рендер звіту звернувся до провайдера")

    monkeypatch.setattr("app.enrich.providers.registry.get_provider", explode)
    monkeypatch.setattr("app.enrich.runner.get_provider", explode)

    audit = await _audit(db_session)
    target = (await db_session.scalars(select(AuditTarget))).one()
    document = build_report(report_service.source_from_target(audit, target))

    assert document.to_json()["summary"]
    assert render_docx(document)[:2] == b"PK"


async def test_public_guest_flow_makes_no_provider_calls(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    """Анонімна воронка проходить свій шлях, не торкнувшись провайдера."""

    def explode(_name: str):
        raise AssertionError("гостьовий потік звернувся до провайдера")

    monkeypatch.setattr("app.enrich.providers.registry.get_provider", explode)
    monkeypatch.setattr("app.enrich.runner.get_provider", explode)

    session = await client.post("/v1/public/sessions")
    assert session.status_code == 201
    token = session.json()["token"]

    started = await client.post(
        "/v1/public/audits",
        json={"url": "https://example.com/"},
        headers={"X-Guest-Token": token},
    )
    assert started.status_code == 202

    short = await client.get(
        f"/v1/public/audits/{started.json()['audit_id']}",
        headers={"X-Guest-Token": token},
    )
    assert short.status_code == 200, short.text
    assert short.json()["unlocked"] is False


async def test_owner_report_download_never_calls_a_provider(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    """`?enrich=true` більше не може купити виклик під час рендеру.

    Раніше кожне повторне завантаження того самого файлу робило новий
    платний виклик: результат ніде не зберігався. Тепер маршрут просить
    розширення з `enabled=False`, тож аналітик — завжди `NullAnalyst`,
    незалежно від того, що стоїть у налаштуваннях.
    """
    from app.audit.llm import factory
    from app.report.owner_enrich import build_owner_extras

    def explode(*_args: object, **_kwargs: object):
        raise AssertionError("рендер звіту створив клієнта провайдера")

    monkeypatch.setattr(factory, "AnthropicAnalyst", explode, raising=False)
    # Навіть з увімкненим legacy-шаром і ключем виклику бути не має.
    monkeypatch.setattr("app.core.config.settings.llm_enabled", True)
    monkeypatch.setattr("app.core.config.settings.anthropic_api_key", "test-key-not-used")

    from app.report import build_report
    from app.services import report_service

    audit = await _audit(db_session)
    target = (await db_session.scalars(select(AuditTarget))).one()
    document = build_report(report_service.source_from_target(audit, target))

    extras = await build_owner_extras(document, enabled=False)

    # Доказ — у тому, що `explode` не спрацював: клієнта провайдера ніхто
    # не створив. Прапорець `analysed` тут не показник: він буває True і
    # на порожньому переліку проблем, без жодного виклику.
    assert extras.requested is True
    assert not extras.notes, "у звіт потрапив переказ від моделі"
    assert not extras.opening


async def test_no_api_route_exposes_enrichment(client: httpx.AsyncClient):
    """Клієнтських дверей у фазу 1 немає — вона за внутрішнім тригером."""
    openapi = (await client.get("/openapi.json")).json()
    paths = " ".join(openapi["paths"])
    assert "enrich" not in paths.lower()
