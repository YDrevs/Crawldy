"""API Actual AI Presence: явний запуск, асинхронне виконання, статус.

Запуск НЕ є частиною звичайного аудиту і не стається сам: окремий
ендпойнт, окрема черга, окрема адмін-політика з вимкненим дефолтом.
API-процес зовнішніх викликів не робить — лише ставить задачу.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError

from app.api.deps import ActorDep, SessionDep
from app.schemas.presence import (
    PresenceModelOut,
    PresenceObservationOut,
    PresencePlanOut,
    PresenceRunCreate,
    PresenceRunDetailOut,
    PresenceRunOut,
    PresenceSuggestionOut,
)
from app.services import presence_service
from app.sites import service as site_service
from app.worker.queue import enqueue_presence

router = APIRouter(prefix="/v1/presence", tags=["presence"])


def _run_out(run: presence_service.PresenceRun) -> PresenceRunOut:
    return PresenceRunOut(
        id=run.id,
        url=run.url,
        brand=run.brand,
        status=run.status,
        site_id=run.site_id,
        prompt_set_version=run.prompt_set_version,
        created_at=run.created_at,
        finished_at=run.finished_at,
        observations_total=run.observations_total,
        observations_ok=run.observations_ok,
        cost_usd=round(run.cost_usd, 4),
        error=run.error,
        entitlement_source=run.entitlement_source,
        entitlement_settled=run.entitlement_settled,
        deliverable=run.deliverable,
    )


@router.get("/models", response_model=list[PresenceModelOut])
async def models(session: SessionDep) -> list[PresenceModelOut]:
    """Якими моделями зараз міряється присутність — БЕЗ входу.

    Вітрина публічної сторінки, як `/v1/offers` для цін: покупець мусить
    бачити, чим саме ми міряємо, ще до будь-якого акаунта. Джерело —
    та сама політика, що виконує прогін, тож сторінка не може розійтися
    з продуктом. Порожній перелік (шар вимкнено) — теж чесна відповідь:
    сторінка тоді не називає жодної моделі, а не вигадує її.
    """
    return [
        PresenceModelOut(**row)
        for row in await presence_service.public_models(session)
    ]


@router.get("/plan", response_model=PresencePlanOut)
async def plan(session: SessionDep, actor: ActorDep) -> PresencePlanOut:
    """Що буде виміряно й чи є право — до запуску, без резервування."""
    policy = await presence_service.load_policy(session)
    if not policy.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Actual AI Presence вимкнено")
    view = await presence_service.plan_view(
        session, organization_id=actor.organization_id
    )
    return PresencePlanOut(**view)


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
async def create_run(
    payload: PresenceRunCreate, session: SessionDep, actor: ActorDep
) -> PresenceRunOut:
    policy = await presence_service.load_policy(session)
    if not policy.enabled:
        # Бета за прапорцем: вимкнено — функції не існує, а не «помилка».
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Actual AI Presence вимкнено",
        )
    if payload.site_id is not None:
        # `site_id` приходить від клієнта, тож на нього не можна
        # спиратися без перевірки: чужий сайт віддає 404, як усюди в
        # цьому продукті — «доступ заборонено» підтвердило б, що
        # ресурс існує.
        owned = await site_service.get(
            session,
            site_id=payload.site_id,
            organization_id=actor.organization_id,
        )
        if owned is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="сайт не знайдено"
            )
    # Повтор того самого ключа ідемпотентності повертає наявний прогін:
    # черга не отримує другої задачі, право не резервується вдруге.
    if payload.idempotency_key:
        existing = await presence_service.find_by_idempotency(
            session, organization_id=actor.organization_id,
            idempotency_key=payload.idempotency_key,
        )
        if existing is not None:
            return _run_out(existing)
    try:
        run = await _create(session, payload, actor)
        await session.commit()
    except presence_service.PresenceEntitlementRequired as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)
        ) from exc
    except IntegrityError:
        # Гонка двох перших запитів з одним ключем: UNIQUE вирішила її
        # базою — той, хто програв, читає прогін переможця.
        await session.rollback()
        existing = await presence_service.find_by_idempotency(
            session, organization_id=actor.organization_id,
            idempotency_key=payload.idempotency_key or "",
        )
        if existing is None:
            raise
        return _run_out(existing)
    await enqueue_presence(run.id)
    return _run_out(run)


async def _create(session, payload: PresenceRunCreate, actor):  # type: ignore[no-untyped-def]
    return await presence_service.create_run(
        session,
        url=payload.url,
        brand=payload.brand,
        brand_aliases=list(payload.brand_aliases),
        category=payload.category,
        services=list(payload.services),
        location=payload.location,
        language=payload.language,
        organization_id=actor.organization_id,
        site_id=payload.site_id,
        idempotency_key=payload.idempotency_key,
    )


@router.get("/runs/{run_id}/export.docx")
async def export_docx(
    run_id: uuid.UUID, session: SessionDep, actor: ActorDep,
    lang: str = "en", kind: str = "technical",
) -> Response:
    """Word-експорт прогону присутності — з персистованого, без мережі.

    Видів два: `general` для власника й `technical` для спеціаліста.
    Невідомий вид — 404, а не мовчазна підміна іншим документом.
    """
    from app.application import presence as presence_app

    if kind not in presence_app.KINDS:
        raise HTTPException(status_code=404, detail="невідомий вид документа")
    run = await _owned_run(session, actor, run_id)

    payload = await presence_app.export_docx(session, run, lang=lang, kind=kind)
    return Response(
        content=payload,
        media_type=("application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"),
        headers={"Content-Disposition": 'attachment; filename="'
                 + presence_app.export_filename(run, lang, kind) + '"'},
    )


@router.get("/suggest", response_model=PresenceSuggestionOut)
async def suggest(
    url: str, session: SessionDep, actor: ActorDep
) -> PresenceSuggestionOut:
    """Факти для форми прогону — з останнього прочитаного аудиту цього сайту.

    Нічого не запускає й не резервує: це підстановка в поля, які людина
    бачить і може змінити. Без аудиту сайту в організації — 404: вигадати
    бренд і місто нам нема з чого.
    """
    from app.audit.fetcher import normalize_url, origin_of
    from app.services import presence_facts_service

    try:
        origin = origin_of(normalize_url(url))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="адреса не читається") from exc
    audit = await presence_facts_service.latest_readable_audit(
        session, organization_id=actor.organization_id, origin=origin
    )
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="немає прочитаного аудиту цього сайту")
    facts = await presence_facts_service.suggest_for_audit(session, audit)
    return PresenceSuggestionOut(audit_id=audit.id, url=audit.url, **facts.to_json())


@router.get("/runs")
async def list_runs(session: SessionDep, actor: ActorDep) -> list[PresenceRunOut]:
    policy = await presence_service.load_policy(session)
    if not policy.enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="Actual AI Presence вимкнено")
    runs = await presence_service.runs_for(session, actor.organization_id)
    return [_run_out(run) for run in runs]


async def _owned_run(
    session: SessionDep, actor: ActorDep, run_id: uuid.UUID
) -> presence_service.PresenceRun:
    run = await presence_service.owned_run(session, actor.organization_id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return run


@router.get("/runs/{run_id}")
async def get_run(
    run_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> PresenceRunDetailOut:
    run = await _owned_run(session, actor, run_id)
    computed = await presence_service.run_metrics(session, run)
    observations = await presence_service.observations_for(session, run.id)
    base = _run_out(run)
    return PresenceRunDetailOut(
        **base.model_dump(),
        metrics=computed["metrics"],
        coverage=computed["coverage"],
        observations=[
            PresenceObservationOut(
                provider=o.provider,
                model=o.model,
                prompt_id=o.prompt_id,
                prompt_text=o.prompt_text,
                category=o.category,
                segment=o.segment,
                run_index=o.run_index,
                mode=o.mode,
                status=o.status,
                searched=o.searched,
                search_queries=list(o.search_queries or []),
                brand_mentioned=o.brand_mentioned,
                domain_cited=o.domain_cited,
                domain_linked=o.domain_linked,
                pages_cited=o.pages_cited,
                cited_domains=o.cited_domains,
                recommended=o.recommended,
                answer_excerpt=o.answer_excerpt,
                error=o.error,
            )
            for o in observations
        ],
    )
