"""Службові аналітика й тестування. Клієнт сюди не ходить.

Аналітика — читання наявних таблиць за період; тестування — справжні
конвеєри без комерційних обмежень. Обидва розділи під `StaffDep`: без
платформної ролі маршрут відповідає 403 незалежно від того, що показує
інтерфейс.

Звіт службового прогону будується тим самим `build_report` і тими самими
рендерами, що й клієнтський, — окремого генератора немає. Різниця лише в
тому, хто має право попросити.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, StaffDep
from app.audit.enums import AuditStatus
from app.audit.i18n import Locale
from app.report.builder import build_report
from app.report.docx import filename_for, render_docx
from app.report.docx_owner import filename_for as owner_filename
from app.report.docx_owner import render_owner_docx
from app.schemas.ai_admin import PresenceAuditCostOut
from app.schemas.audit import AuditCreate, AuditOptionsIn, IssueOut
from app.services import (
    admin_analytics_service as analytics,
)
from app.services import (
    admin_testing_service as testing,
)
from app.services import audit_service, presence_service, report_service
from app.worker.queue import enqueue_audit, enqueue_presence

router = APIRouter(prefix="/v1/admin", tags=["admin"])

DOCX_MEDIA_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
)


@router.get("/analytics")
async def analytics_overview(
    session: SessionDep,
    _: StaffDep,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> dict[str, Any]:
    """Продажі, клієнти, використання за період. Порожній період — за весь час."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="початок періоду пізніший за кінець",
        )
    return await analytics.overview(session, start=date_from, end=date_to)


# ── зарахування оплат ─────────────────────────────────────────────────


@router.get("/payments/pending")
async def pending_payments(
    session: SessionDep,
    _: StaffDep,
    include_closed: bool = False,
    include_unspent: bool = False,
) -> list[dict[str, Any]]:
    """Покупки, за якими подія провайдера не прийшла. Без запитів до нього.

    `include_closed` додає погашені каси: вони прибрані з робочого
    переліку, але не зникли, і подивитися на них має бути де.

    `include_unspent` додає оплачені покупки анонімної воронки, на які
    ще не запущено перевірку: гроші прийшли, а сайт покупець ще не
    назвав. Ані перший, ані другий перелік цього стану не описують.
    """
    from app.application import reconciliation

    return await reconciliation.pending(
        session, include_closed=include_closed, include_unspent=include_unspent
    )


@router.post("/payments/verify")
async def verify_all_payments(
    session: SessionDep, _: StaffDep, include_closed: bool = False
) -> dict[str, Any]:
    """Звірити з провайдером усі незараховані покупки одразу.

    Заради цього дія й існує: кожне натискання «Купити» лишає рядок,
    навіть коли людина не заплатила, тож у переліку майже все — покинуті
    каси. Шукати серед них оплачену по одній означало б тридцять
    натискань заради однієї відповіді.
    """
    from app.application import reconciliation

    answers = await reconciliation.verify_all(session, include_closed=include_closed)
    return {
        purchase_id: {
            "settlement": answer.settlement.value,
            "amount_minor": answer.amount_minor,
            "currency": answer.currency,
            "invoice": answer.invoice,
            "customer_ref": answer.customer_ref,
            "email": answer.email,
            "detail": answer.detail,
        }
        for purchase_id, answer in answers.items()
    }


class SweepIn(BaseModel):
    """Що саме гасити. Порожньо — лише підрахунок, нічого не змінюється."""

    purchase_ids: list[uuid.UUID] | None = None


@router.post("/payments/sweep")
async def sweep_payments(
    payload: SweepIn, session: SessionDep, _: StaffDep
) -> dict[str, Any]:
    """Погасити каси, за які не заплатили, щоб перелік не заростав.

    Без `purchase_ids` — лише рахує й повертає їхні ідентифікатори.
    З ними — гасить рівно ті з них, що й зараз підпадають під правило:
    набір може звузитись, але не вирости.

    Гасіння — це СТАН, а не видалення: пізніша оплата оживляє покупку.
    """
    from app.application import reconciliation

    result = await reconciliation.sweep(session, apply_to=payload.purchase_ids)
    if payload.purchase_ids is not None:
        await session.commit()
    return result


@router.post("/payments/{purchase_id}/verify")
async def verify_payment(
    purchase_id: uuid.UUID, session: SessionDep, _: StaffDep
) -> dict[str, Any]:
    """Що каже провайдер про транзакцію цієї покупки. Нічого не змінює."""
    from app.application import reconciliation

    try:
        answer = await reconciliation.verify(session, purchase_id=purchase_id)
    except reconciliation.NotPending as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {
        "settlement": answer.settlement.value,
        "amount_minor": answer.amount_minor,
        "currency": answer.currency,
        "invoice": answer.invoice,
        "customer_ref": answer.customer_ref,
        "email": answer.email,
        "detail": answer.detail,
    }


@router.post("/payments/{purchase_id}/credit")
async def credit_payment(
    purchase_id: uuid.UUID, session: SessionDep, actor: StaffDep
) -> dict[str, Any]:
    """Зарахувати покупку, якщо провайдер підтверджує оплату.

    Провайдера питаємо тут ще раз: попередня звірка могла бути давно, а
    гроші могли повернути. Відмова — 409: це не помилка запиту, а стан
    оплати, і людині треба показати саме його.
    """
    from app.application import reconciliation

    try:
        result = await reconciliation.credit(
            session, purchase_id=purchase_id, actor_id=actor.user_id
        )
    except reconciliation.NotPending as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except reconciliation.NotSettled as exc:
        raise HTTPException(
            status_code=409,
            detail=f"провайдер не підтверджує оплату: {exc}",
        ) from exc
    await session.commit()
    return result


# ── тестування: стандартний аудит ──────────────────────────────────────


class AuditTestIn(BaseModel):
    url: str
    options: AuditOptionsIn = Field(default_factory=AuditOptionsIn)


@router.post("/testing/audits", status_code=status.HTTP_202_ACCEPTED)
async def start_test_audit(
    payload: AuditTestIn, session: SessionDep, actor: StaffDep
) -> dict[str, Any]:
    """Справжній аудит без квоти, кредитів і продажу."""
    try:
        create = AuditCreate(url=payload.url, options=payload.options)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    audit = await testing.start_audit(
        session,
        create,
        organization_id=actor.organization_id,
        created_by_user_id=actor.user_id,
    )
    await session.commit()
    try:
        await enqueue_audit(audit.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"черга недоступна: {exc}",
        ) from exc
    return {"id": str(audit.id), "status": audit.status.value, "url": audit.url}


@router.get("/testing/audits")
async def list_test_audits(session: SessionDep, _: StaffDep) -> list[dict[str, Any]]:
    return [
        {
            "id": str(a.id),
            "url": a.url,
            "status": a.status.value,
            "score_overall": a.score_overall,
            "created_at": a.created_at.isoformat() if a.created_at else None,
            "finished_at": a.finished_at.isoformat() if a.finished_at else None,
        }
        for a in await testing.recent_audits(session)
    ]


@router.get("/testing/audits/{audit_id}")
async def test_audit_detail(
    audit_id: uuid.UUID, session: SessionDep, _: StaffDep, lang: Locale = Locale.UK
) -> dict[str, Any]:
    audit = await testing.owned_test_audit(session, audit_id)
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    return {
        "run": testing.diagnostics(audit),
        "issues": _issue_rows(audit, lang),
    }


def _issue_rows(audit: Any, lang: Locale) -> list[dict[str, Any]]:
    """Кожна знахідка з доказом — без згортання й без пріоритезації.

    Живе в маршруті, а не в сервісі, і це не смак: `services` не ходить
    у двигун напряму (межа перевіряється тестом), а каталог повідомлень
    і `IssueOut` — саме двигун. Тип аудиту тут `Any` з дзеркальної
    причини: `api` не імпортує моделі — рядок приходить із сервісу.

    Порядок той самий, що бачить клієнт
    (`sort_issues`), але нічого не відкидається: калібрування дивиться
    на все, що детектор сказав.
    """
    rows: list[dict[str, Any]] = []
    for row in audit_service.sort_issues(list(audit.issues)):
        out = IssueOut.from_issue(row, lang)
        rows.append({
            "id": str(out.id),
            "module": out.module.value,
            "code": out.code,
            "issue_key": f"{row.code}:{row.issue_variant}" if row.issue_variant else row.code,
            "severity": out.severity.value,
            "confidence": getattr(out, "confidence", None),
            "title": out.title,
            "description": out.description,
            "recommendation": out.recommendation,
            "evidence": out.evidence,
            "page_url": out.page_url,
            "msg": out.msg,
            "text_locale": out.text_locale,
            "verdict": out.verdict.value if out.verdict else None,
        })
    return rows


@router.get("/testing/audits/{audit_id}/report")
async def test_audit_report(
    audit_id: uuid.UUID,
    session: SessionDep,
    _: StaffDep,
    format: str = "json",
    lang: Locale = Locale.UK,
) -> Response:
    """Той самий звіт, що отримує клієнт: той самий білдер, ті самі рендери."""
    audit = await testing.owned_test_audit(session, audit_id)
    if audit is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if AuditStatus(audit.status) not in testing.REPORTABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"звіт недоступний: аудит у статусі {audit.status.value}",
        )
    document = build_report(report_service.source_from_audit(audit), lang)
    if format == "json":
        return JSONResponse(jsonable_encoder(document.to_json()))
    if format == "docx":
        return Response(
            content=render_docx(document, lang),
            media_type=DOCX_MEDIA_TYPE,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{filename_for(document, lang)}"'
                )
            },
        )
    if format == "docx_owner":
        return Response(
            content=render_owner_docx(document, lang, None),
            media_type=DOCX_MEDIA_TYPE,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{owner_filename(document, lang, None)}"'
                )
            },
        )
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="формат: json | docx | docx_owner",
    )


# ── тестування: Actual AI Presence ─────────────────────────────────────


class PresenceTestIn(BaseModel):
    url: str
    brand: str
    brand_aliases: list[str] = Field(default_factory=list)
    category: str = ""
    services: list[str] = Field(default_factory=list)
    location: str | None = None
    language: str = "en"
    # None — усі увімкнені провайдери; імʼя — рівно один, для калібрування.
    provider: str | None = None
    # Benchmark-only: модель для ЦЬОГО прогону, без зміни продуктової
    # політики. Потребує provider. Модель мусить бути в каталозі.
    model: str | None = None


@router.post("/testing/presence", status_code=status.HTTP_202_ACCEPTED)
async def start_test_presence(
    payload: PresenceTestIn, session: SessionDep, _: StaffDep
) -> dict[str, Any]:
    """Справжній прогін присутності без прав клієнта й без списань."""
    try:
        run = await testing.start_presence(
            session,
            url=payload.url,
            brand=payload.brand,
            brand_aliases=payload.brand_aliases,
            category=payload.category,
            services=payload.services,
            location=payload.location,
            language=payload.language,
            only_provider=payload.provider,
            model_override=payload.model,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    await session.commit()
    try:
        await enqueue_presence(run.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"черга недоступна: {exc}",
        ) from exc
    planned = run.policy_snapshot.get("providers", {})
    return {
        "id": str(run.id),
        "status": run.status,
        "url": run.url,
        "providers": sorted(
            name for name, p in planned.items() if p.get("enabled")
        ),
        "prompts": len(run.prompts),
    }


@router.get("/ai/audit-cost", response_model=PresenceAuditCostOut)
async def presence_audit_cost(
    session: SessionDep, _: StaffDep
) -> dict[str, Any]:
    """Собівартість одного повного аудиту присутності — для ціноутворення.

    Вартість спостереження кожної каталожної моделі + останній справжній
    адмінський аудит. Оцінку рахує клієнт із живих параметрів сторінки
    (повтори, промпти) й обраних моделей, тож зміна моделі або поля
    одразу перераховує число.
    """
    return await testing.audit_cost(session)


@router.get("/testing/presence")
async def list_test_presence(session: SessionDep, _: StaffDep) -> list[dict[str, Any]]:
    return [
        {
            "id": str(r.id),
            "url": r.url,
            "brand": r.brand,
            "status": r.status,
            "observations_ok": r.observations_ok,
            "observations_total": r.observations_total,
            "cost_usd": round(r.cost_usd, 4),
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in await testing.recent_presence(session)
    ]


@router.get("/testing/presence/{run_id}")
async def test_presence_detail(
    run_id: uuid.UUID, session: SessionDep, _: StaffDep
) -> dict[str, Any]:
    run = await testing.owned_test_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    computed = await presence_service.run_metrics(session, run)
    observations = await presence_service.observations_for(session, run.id)
    return {
        "run": {
            "id": str(run.id),
            "url": run.url,
            "origin": run.origin,
            "brand": run.brand,
            "status": run.status,
            "error": run.error,
            "prompt_set_version": run.prompt_set_version,
            "observations_total": run.observations_total,
            "observations_ok": run.observations_ok,
            "cost_usd": round(run.cost_usd, 4),
            "entitlement_source": run.entitlement_source,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            # Знімок політики несе провайдерів, моделі й бюджети прогону —
            # секретів у ньому немає за побудовою.
            "policy_snapshot": run.policy_snapshot,
        },
        "metrics": computed["metrics"],
        "coverage": computed["coverage"],
        "observations": [
            {
                "provider": o.provider,
                "model": o.model,
                "tool_version": o.tool_version,
                "prompt_id": o.prompt_id,
                "prompt_text": o.prompt_text,
                "category": o.category,
                "segment": o.segment,
                "language": o.language,
                "country": o.country,
                "mode": o.mode,
                "run_index": o.run_index,
                "status": o.status,
                "searched": o.searched,
                "search_queries": list(o.search_queries or []),
                "brand_mentioned": o.brand_mentioned,
                "matched_alias": o.matched_alias,
                "domain_cited": o.domain_cited,
                "domain_linked": o.domain_linked,
                "pages_cited": list(o.pages_cited or []),
                "cited_domains": list(o.cited_domains or []),
                "recommended": o.recommended,
                "answer_excerpt": o.answer_excerpt,
                "error": o.error,
                "input_tokens": o.input_tokens,
                "output_tokens": o.output_tokens,
                "searches": o.searches,
                "cost_usd": round(o.cost_usd, 6),
                "retries": o.retries,
                "duration_ms": o.duration_ms,
            }
            for o in observations
        ],
    }


@router.get("/testing/presence/{run_id}/report")
async def test_presence_report(
    run_id: uuid.UUID,
    session: SessionDep,
    _: StaffDep,
    kind: str = "general",
    lang: str = "uk",
) -> Response:
    """Ті самі два документи присутності, що отримує клієнт.

    Службовий екран не має власного рендеру: він викликає той самий
    застосунковий шлях. Інакше «перевірено в адмінці» перестало б
    означати «перевірено те, що поїде клієнту».
    """
    from app.application import presence as presence_app

    if kind not in presence_app.KINDS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="вид: general | technical",
        )
    run = await testing.owned_test_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    payload = await presence_app.export_docx(session, run, lang=lang, kind=kind)
    return Response(
        content=payload,
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": 'attachment; filename="'
                 + presence_app.export_filename(run, lang, kind) + '"'},
    )
