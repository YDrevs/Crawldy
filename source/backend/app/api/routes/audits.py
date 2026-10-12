import uuid
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api.deps import ActorDep, SessionDep
from app.application import audits as application
from app.application.locale import resolve as resolve_locale
from app.application.visibility import history_window
from app.audit.enums import AuditStatus, AuditTrigger, Module, Severity
from app.audit.fetcher import origin_of
from app.audit.i18n import FALLBACK_LOCALE, Locale
from app.core.run_enums import FailureClass
from app.report.builder import build_report
from app.report.docx import filename_for, render_docx
from app.report.docx_owner import filename_for as owner_filename
from app.report.docx_owner import render_owner_docx
from app.report.history import compare, needs_recompute, timeline
from app.report.owner_enrich import build_owner_extras
from app.report.web import to_web
from app.schemas.audit import (
    AttemptOut,
    AuditCreate,
    AuditDetailOut,
    AuditOut,
    IssueOut,
    LlmModelOut,
    PageOut,
    ShareLinkCreate,
    ShareLinkCreated,
    ShareLinkOut,
    VerdictIn,
)
from app.schemas.history import HistoryOut
from app.schemas.result import AuditResultResponse
from app.services import audit_service, link_service, report_service, verdict_service
from app.worker.queue import enqueue_audit

REPORTABLE = {AuditStatus.COMPLETED, AuditStatus.PARTIAL}
DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


class ReportFormat(StrEnum):
    JSON = "json"
    DOCX = "docx"
    # Ті самі два документи під новими іменами. Види звіту звуться
    # «загальний» і «технічний» (рішення власника 2026-09-06), і
    # контракт мусить це називати. Старі значення лишаються робочими
    # назавжди: за ними ходять збережені посилання, і перейменування
    # ідентифікатора зламало б їх мовчки.
    DOCX_TECHNICAL = "docx-technical"
    DOCX_OWNER = "docx-owner"
    DOCX_GENERAL = "docx-general"
    # Не звіт, а готовий файл, який клієнт кладе собі на сайт.
    LLMS_TXT = "llms-txt"


# Загальний звіт: власнику бізнесу, який не читає ні JSON, ні технічну
# частину Word-документа.
GENERAL_FORMATS = {ReportFormat.DOCX_OWNER, ReportFormat.DOCX_GENERAL}


TargetParam = Annotated[
    uuid.UUID | None, Query(description="ціль аудиту; без неї береться первинна")
]

EnrichParam = Annotated[
    bool,
    Query(description="docx-owner: додати пояснення від моделі (платний виклик)"),
]

router = APIRouter(prefix="/v1/audits", tags=["audits"])


@router.get("/llm-models", response_model=list[LlmModelOut])
async def llm_models(actor: ActorDep) -> list[LlmModelOut]:
    """Моделі, доступні для семантичного аналізу.

    Стоїть перед /{audit_id}, інакше FastAPI спробує розібрати «llm-models»
    як UUID аудиту.
    """
    return LlmModelOut.catalogue()


@router.post("", response_model=AuditOut, status_code=status.HTTP_202_ACCEPTED)
async def create_audit(payload: AuditCreate, session: SessionDep, actor: ActorDep) -> AuditOut:
    """Запуск аудиту. Права й квота перевіряються до запису, не після.

    Порядок кроків живе в `application.start_audit`; маршрут лише
    перекладає доменну відмову на код відповіді й ставить задачу в чергу.
    """
    try:
        started = await application.start_audit(
            session,
            payload,
            organization_id=actor.organization_id,
            created_by_user_id=actor.user_id,
            trigger=AuditTrigger.API if actor.auth == "api_key" else AuditTrigger.MANUAL,
            site_id=await application.ensure_site_for(
                session,
                organization_id=actor.organization_id,
                url=payload.targets[0],
                created_by_user_id=actor.user_id,
            ),
        )
    except application.NotAllowed as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"reason": exc.reason, "limit": exc.limit, "used": exc.used},
        ) from exc

    await session.commit()
    try:
        await enqueue_audit(started.audit.id)
    except Exception as exc:
        # Квота повертається: аудит не виконається з нашої причини, а не
        # через сайт клієнта. Списане за роботу, якої не було, — це
        # рахунок за нашу поломку.
        await audit_service.mark_failed(session, started.audit.id, f"черга недоступна: {exc}")
        await application.settle_quota(
            session, started.audit, failure=FailureClass.INTERNAL_ERROR
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="черга недоступна, спробуйте пізніше",
        ) from exc

    return AuditOut.of(started.audit)


@router.get("", response_model=list[AuditOut])
async def list_audits(
    session: SessionDep,
    actor: ActorDep,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    site_id: uuid.UUID | None = None,
) -> list[AuditOut]:
    audits = await audit_service.list_audits(
        session,
        organization_id=actor.organization_id,
        limit=limit,
        offset=offset,
        site_id=site_id,
    )
    return [AuditOut.of(a) for a in audits]




async def _refuse_refunded_paid_content(session: SessionDep, audit_id: uuid.UUID) -> None:
    """Повернені гроші закривають платний вміст і в кабінеті.

    Аудит, що потрапив в організацію привласненням гостя, міг бути
    куплений і повернутий. Історія (рядок розблокування, покупка зі
    статусом REFUNDED) лишається; повний звіт — ні. Звичайних аудитів
    кабінету це не торкається: у них немає історії розблокування.
    """
    from app.application import guest as guest_app

    if await guest_app.paid_content_denied(session, audit_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="покупку цього звіту повернено",
        )


@router.get("/{audit_id}", response_model=AuditDetailOut)
async def get_audit(
    audit_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    include_pages: bool = Query(False),
    lang: Locale | None = None,
) -> AuditDetailOut:
    """Деталі аудиту потрібною мовою.

    Мова тут працює точно так само, як у звіті, і це не збіг: обидва
    рендерять із того самого `msg_key` через той самий каталог. Поки
    деталі віддавалися зі збережених стовпців, той самий аудит через
    `/report` читався німецькою, а через цей маршрут — завжди однією
    мовою; інтерфейс, який читає саме його, був одномовним через API.
    """
    audit = await audit_service.get_audit(session, audit_id, organization_id=actor.organization_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="аудит не знайдено")
    await _refuse_refunded_paid_content(session, audit_id)
    locale = resolve_locale(
        requested=lang,
        user_locale=actor.user_locale,
        organization_locale=actor.organization_locale,
    ).locale
    detail = AuditDetailOut.model_validate(audit)
    detail.locale = locale.value
    detail.pages_count = len(audit.pages)
    detail.issues_count = len(audit.issues)
    detail.issues_by_severity = audit_service.summarize(audit)
    detail.issues = [
        IssueOut.from_issue(i, locale) for i in audit_service.sort_issues(list(audit.issues))
    ]
    detail.attempt_log = [AttemptOut.of(a, locale) for a in audit.attempt_log]
    if include_pages:
        detail.pages = [PageOut.model_validate(p) for p in audit.pages]
    return detail


@router.get("/{audit_id}/result", response_model=AuditResultResponse)
async def get_audit_result(
    audit_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    lang: Locale | None = None,
    target: TargetParam = None,
) -> AuditResultResponse:
    """Результат аудиту в продуктовому вигляді — для інтерфейсу.

    Окремий контракт від `?format=json`, і навмисно. Той — файл, який
    клієнт зберігає й віддає підряднику; цей — те, що малює екран. Через
    спільний серіалізатор вони злиплися б: зміна формату файла ламала б
    інтерфейс, а вимога інтерфейсу спотворювала б файл. Бізнес-логіка при
    цьому одна — `build_report`.

    Інтерфейс тут нічого не рахує: пріоритети, наслідки, impact, смуги,
    покриття й потенційний бал приходять готовими.
    """
    audit = await audit_service.get_audit(session, audit_id, organization_id=actor.organization_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="аудит не знайдено")
    await _refuse_refunded_paid_content(session, audit_id)
    locale = resolve_locale(
        requested=lang,
        user_locale=actor.user_locale,
        organization_locale=actor.organization_locale,
    ).locale
    if AuditStatus(audit.status) not in REPORTABLE:
        raise HTTPException(
            status_code=409,
            detail=f"результат недоступний: аудит у статусі {audit.status}",
        )

    chosen = report_service.pick_target(audit, target)
    if target is not None and chosen is None:
        raise HTTPException(status_code=404, detail="ціль не знайдено в цьому аудиті")
    source = (
        report_service.source_from_target(audit, chosen)
        if chosen is not None
        else report_service.source_from_audit(audit)
    )
    document = build_report(source, locale)

    # Ідентифікатори знахідок і вердикти людей — з бази: документ про
    # рядки БД не знає й не має знати. Інтерфейсу вони потрібні, щоб
    # записати відповідь на знахідку.
    ids: dict[str, uuid.UUID] = {}
    said: dict[str, tuple[str, str]] = {}
    for row in audit.issues:
        key = f"{row.code}:{row.issue_variant}" if row.issue_variant else row.code
        page = (row.evidence or {}).get("page_url")
        handle = f"{key}@{page or ''}"
        ids[handle] = row.id
        recorded = row.human_verdict
        if recorded is not None:
            said[handle] = (recorded.verdict.value, recorded.note)

    return to_web(
        document,
        audit_id=audit.id,
        site_id=audit.site_id,
        status=audit.status.value,
        finished_at=audit.finished_at,
        fallback_locale=FALLBACK_LOCALE.value,
        issue_ids=ids,
        verdicts=said,
    )


@router.get(
    "/{audit_id}/report",
    responses={
        200: {
            "content": {
                "application/json": {},
                DOCX_MEDIA_TYPE: {"schema": {"type": "string", "format": "binary"}},
            }
        }
    },
)
async def get_report(
    audit_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    format: ReportFormat = ReportFormat.JSON,
    lang: Locale | None = None,
    target: TargetParam = None,
    enrich: EnrichParam = False,
) -> Response:
    """Звіт одним артефактом однією мовою.

    json — технічний шлях, docx — для людини. Мова обирається на рівні
    файлу, а не всередині нього: так кожен документ лишається чистим.

    Мова резолвиться тим самим порядком, що й у деталях аудиту:
    запит → користувач → організація → англійська. Поки тут стояв
    жорсткий дефолт `uk`, налаштування профілю на цьому маршруті просто
    не діяли — і два маршрути з однаковим `msg_key` віддавали різні
    мови тому самому читачеві.
    При кількох URL звіт будується по одній цілі — `?target=<id>`,
    перелік цілей віддає GET /v1/audits/{id}.
    """
    audit = await audit_service.get_audit(session, audit_id, organization_id=actor.organization_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="аудит не знайдено")
    await _refuse_refunded_paid_content(session, audit_id)
    lang = resolve_locale(
        requested=lang,
        user_locale=actor.user_locale,
        organization_locale=actor.organization_locale,
    ).locale
    if AuditStatus(audit.status) not in REPORTABLE:
        raise HTTPException(
            status_code=409,
            detail=f"звіт недоступний: аудит у статусі {audit.status}",
        )

    chosen = report_service.pick_target(audit, target)
    if target is not None and chosen is None:
        raise HTTPException(status_code=404, detail="ціль не знайдено в цьому аудиті")
    if chosen is not None and AuditStatus(chosen.status) not in REPORTABLE:
        raise HTTPException(
            status_code=409,
            detail=f"звіт по цій цілі недоступний: статус {chosen.status}",
        )

    source = (
        report_service.source_from_target(audit, chosen)
        if chosen is not None
        else report_service.source_from_audit(audit)
    )
    document = build_report(source, lang)
    if format is ReportFormat.JSON:
        return JSONResponse(jsonable_encoder(document.to_json()))

    if format is ReportFormat.LLMS_TXT:
        draft = str((document.evidence or {}).get("llms_txt_draft") or "")
        if not draft:
            raise HTTPException(
                status_code=409,
                detail="немає з чого скласти llms.txt: сайт не віддав сторінок із назвами",
            )
        host = str(document.target.get("origin", "")).replace("https://", "").strip("/")
        return Response(
            content=draft,
            media_type="text/plain; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="llms-{host or "site"}.txt"'
            },
        )

    if format in GENERAL_FORMATS:
        # Рендер звіту НЕ ходить у мережу — це інваріант, а не налаштування.
        #
        # Раніше саме тут був єдиний виняток, і він мав дефект: кожне
        # повторне завантаження того самого файлу робило новий платний
        # виклик, бо результат ніде не зберігався. `enabled=False`
        # закриває це структурно — не покладаючись на те, що
        # `llm_enabled` вимкнений.
        #
        # Параметр `enrich` лишається заради сумісності й далі формує
        # пояснення, чому розширеного розділу немає. Коли шар збагачення
        # вийде з експерименту, він читатиме ЗБЕРЕЖЕНИЙ результат, а не
        # викликатиме провайдера з обробника HTTP-запиту.
        extras = await build_owner_extras(document, enabled=False) if enrich else None
        return Response(
            content=render_owner_docx(document, lang, extras),
            media_type=DOCX_MEDIA_TYPE,
            headers={
                "Content-Disposition": (
                    f'attachment; filename="{owner_filename(document, lang, extras)}"'
                )
            },
        )

    return Response(
        content=render_docx(document, lang),
        media_type=DOCX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename_for(document, lang)}"'},
    )


@router.post("/{audit_id}/links", response_model=ShareLinkCreated, status_code=201)
async def create_share_link(
    audit_id: uuid.UUID,
    payload: ShareLinkCreate,
    session: SessionDep,
    actor: ActorDep,
) -> ShareLinkCreated:
    """Створює публічне посилання. Токен віддається один раз і не зберігається."""
    audit = await audit_service.get_audit(session, audit_id, organization_id=actor.organization_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="аудит не знайдено")
    await _refuse_refunded_paid_content(session, audit_id)
    if AuditStatus(audit.status) not in REPORTABLE:
        raise HTTPException(status_code=409, detail=f"аудит у статусі {audit.status}")

    if payload.target is not None and report_service.pick_target(audit, payload.target) is None:
        raise HTTPException(status_code=404, detail="ціль не знайдено в цьому аудиті")

    # Мова фіксується в посиланні назавжди. Не вказали — беремо ту, якою
    # автор читає продукт: одержувач налаштувань не має, і питати їх у
    # його браузера означало б віддати документ мовою, якої автор не
    # обирав.
    lang = resolve_locale(
        requested=payload.lang,
        user_locale=actor.user_locale,
        organization_locale=actor.organization_locale,
    ).locale
    link, token = await link_service.create_link(
        session,
        audit_id,
        target_id=payload.target,
        lang=lang.value,
        ttl_days=payload.ttl_days,
    )
    return ShareLinkCreated(
        **ShareLinkOut.model_validate(link).model_dump(),
        token=token,
        path=f"/r/{token}",
    )


@router.get("/{audit_id}/links", response_model=list[ShareLinkOut])
async def list_share_links(
    audit_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> list[ShareLinkOut]:
    audit = await audit_service.get_audit(session, audit_id, organization_id=actor.organization_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="аудит не знайдено")
    links = await link_service.list_links(session, audit_id)
    return [ShareLinkOut.model_validate(link) for link in links]


@router.delete("/{audit_id}/links/{link_id}", response_model=ShareLinkOut)
async def revoke_share_link(
    audit_id: uuid.UUID, link_id: uuid.UUID, session: SessionDep, actor: ActorDep
) -> ShareLinkOut:
    # Власність перевіряється ДО запису: раніше відкликання комітилось
    # для будь-якого link_id, а 404 приходив уже після.
    audit = await audit_service.get_audit(session, audit_id, organization_id=actor.organization_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="аудит не знайдено")
    link = await link_service.revoke(session, audit_id, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail="посилання не знайдено")
    return ShareLinkOut.model_validate(link)


@router.get("/{audit_id}/issues", response_model=list[IssueOut])
async def list_issues(
    audit_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    module: Module | None = None,
    severity: Severity | None = None,
) -> list[IssueOut]:
    audit = await audit_service.get_audit(session, audit_id, organization_id=actor.organization_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="аудит не знайдено")
    await _refuse_refunded_paid_content(session, audit_id)
    issues = [
        i
        for i in audit_service.sort_issues(list(audit.issues))
        if (module is None or i.module == module) and (severity is None or i.severity == severity)
    ]
    return [IssueOut.from_issue(i) for i in issues]


@router.get("/history/by-origin", response_model=HistoryOut)
async def score_history(
    session: SessionDep,
    actor: ActorDep,
    origin: Annotated[str, Query(description="origin сайту, напр. https://example.com")],
    limit: int = Query(50, ge=2, le=200),
) -> dict[str, object]:
    """Історія балів сайту з позначкою, де порівняння недійсне.

    Повертає не лише криву, а й відповідь на питання, якого клієнт не
    поставить сам: чи це сайт змінився. Кожен крок, у якому змінилася
    версія детекторів або скорингу, позначений — а якщо в старого аудиту
    є знімок, сказано, що його можна перерахувати й отримати чесне
    порівняння.
    """
    window = await history_window(session, organization_id=actor.organization_id)
    points = await audit_service.score_history(
        session,
        origin_of(origin),
        organization_id=actor.organization_id,
        limit=limit,
        since=window.since,
    )
    if not points:
        raise HTTPException(status_code=404, detail="історії для цього сайту немає")
    steps = timeline(points)
    fixable = needs_recompute(steps)
    return {
        "origin": origin_of(origin),
        # Вікно йде у відповідь: обрізана крива без пояснення читається
        # як «раніше аудитів не було», а це неправда.
        "visible_days": window.days,
        "points": [p.to_json() for p in points],
        "steps": [s.to_json() for s in steps],
        "incomparable_steps": sum(1 for s in steps if not s.comparable),
        "fixable_by_recompute": len(fixable),
    }


@router.post("/targets/{target_id}/rescore")
async def rescore_target(
    target_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
) -> dict[str, object]:
    """Перерахунок збереженого аудиту нинішніми правилами.

    Збережений бал не змінюється: у відповіді два — той, що був, і той,
    що вийшов би сьогодні. Підмінити перший другим означало б переписати
    історію, а вона потрібна саме такою, якою була.
    """
    result = await audit_service.rescore_target(
        session, target_id, organization_id=actor.organization_id
    )
    if result is None:
        raise HTTPException(
            status_code=404,
            detail="цілі немає або в неї немає знімка — перерахувати нічим",
        )
    stored, recomputed = result
    return {
        "stored": stored.to_json(),
        "recomputed": recomputed.to_json(),
        "difference": compare(stored, recomputed, rebased=True).to_json(),
    }


@router.put("/issues/{issue_id}/verdict")
async def set_verdict(
    issue_id: uuid.UUID,
    body: VerdictIn,
    session: SessionDep,
    actor: ActorDep,
) -> dict[str, object]:
    """Що людина сказала про знахідку.

    PUT, а не POST: вердикт один на знахідку, і повторний виклик його
    замінює. Думка може змінитися — потрібна нинішня відповідь, а не
    історія вагань.
    """
    saved = await verdict_service.record(
        session,
        issue_id,
        body.verdict,
        organization_id=actor.organization_id,
        note=body.note,
        author=body.author,
    )
    if saved is None:
        raise HTTPException(status_code=404, detail="знахідки не знайдено")
    return {
        "issue_id": str(saved.issue_id),
        "code": saved.code,
        "verdict": saved.verdict.value,
        "note": saved.note,
    }


@router.get("/{audit_id}/benchmark")
async def benchmark(
    audit_id: uuid.UUID,
    session: SessionDep,
    actor: ActorDep,
    subject: Annotated[
        uuid.UUID | None, Query(description="чия це сторона; типово перша ціль")
    ] = None,
) -> dict[str, object]:
    """Ви на тлі конкурентів у межах одного аудиту.

    Найкорисніше тут не рейтинг, а поділ проблем: ті, що є в усіх, —
    норма галузі й виграшу не дадуть; ті, що лише у вас, — і є
    відставання, за яке платять.
    """
    result = await audit_service.benchmark_targets(
        session, audit_id, subject, organization_id=actor.organization_id
    )
    if result is None:
        raise HTTPException(status_code=404, detail="аудиту або цілі не знайдено")
    return result.to_json()
