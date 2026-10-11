"""Публічний доступ до звіту за токеном.

Єдиний роутер без X-API-Key. Усе, що тут є, свідомо параноїдальне:
жодних деталей у 404, заборона індексації, заборона кешування.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Path, Response

from app.api.deps import SessionDep
from app.audit.enums import AuditStatus
from app.audit.i18n import DEFAULT_LOCALE, FALLBACK_LOCALE, Locale, parse
from app.report.builder import build_report
from app.report.docx import filename_for, render_docx
from app.report.docx_owner import filename_for as general_filename
from app.report.docx_owner import render_owner_docx
from app.services import audit_service, link_service, report_service

router = APIRouter(prefix="/r", tags=["public"])

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
REPORTABLE = {AuditStatus.COMPLETED, AuditStatus.PARTIAL}

# Публічне посилання не має потрапити в пошук і не має кешуватися проксі.
PRIVATE_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Cache-Control": "no-store, private",
    "Referrer-Policy": "no-referrer",
}

# Довжина токена з secrets.token_urlsafe(32). Перевіряємо до звернення в БД.
TokenPath = Path(min_length=32, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


@router.get("/{token}")
async def public_report(
    session: SessionDep,
    token: str = TokenPath,
    format: str = "docx",
) -> Response:
    """Звіт за публічним посиланням.

    Будь-яка причина відмови — прострочення, відкликання, неіснуючий
    токен — дає однаковий 404: інакше сторонній міг би перебором
    зʼясувати, які токени існували.
    """
    # Видів Word-документа два, і публічне посилання віддає обидва:
    # разова покупка продається власнику бізнесу, а він читає загальний.
    # `docx` лишається технічним заради вже виданих посилань.
    if format not in {"json", "docx", "docx-general", "docx-technical", "web"}:
        raise HTTPException(status_code=404, detail="посилання недійсне")

    link = await link_service.resolve(session, token)
    if link is None:
        raise HTTPException(status_code=404, detail="посилання недійсне")

    # Екранний вигляд — лише для оплаченого доступу. Постійне платне
    # посилання — це вхід у куплений продукт, а не лише в файл: сесія
    # гостя мине за сім днів, а екран купленого звіту — ні. Звичайне
    # поділене посилання лишається тим, чим було, — документом: чи має
    # воно відкривати інтерактивний звіт, окреме продуктове рішення, і
    # тут воно не ухвалюється. Відмова та сама, що й на все: 404 без
    # пояснення, інакше формат став би способом розрізняти типи токенів.
    if format == "web" and link.unlock_id is None:
        raise HTTPException(status_code=404, detail="посилання недійсне")

    # Повернені гроші закривають і поділені посилання. Платні при
    # поверненні відкликаються самі; це — про посилання з кабінету на
    # аудит, чию покупку повернули вже після того, як ним поділилися.
    # Причина відмови не розрізняється: той самий 404, що й на все.
    from app.application import guest as guest_app

    if await guest_app.paid_content_denied(session, link.audit_id):
        raise HTTPException(status_code=404, detail="посилання недійсне")

    audit = await audit_service.get_audit(session, link.audit_id)
    if audit is None or AuditStatus(audit.status) not in REPORTABLE:
        raise HTTPException(status_code=404, detail="посилання недійсне")

    target = report_service.pick_target(audit, link.target_id)
    if link.target_id is not None and target is None:
        raise HTTPException(status_code=404, detail="посилання недійсне")

    source = (
        report_service.source_from_target(audit, target)
        if target is not None
        else report_service.source_from_audit(audit)
    )
    locale = _locale(link.lang)
    document = build_report(source, locale)

    if format == "web":
        # Та сама форма, що в кабінеті й у /full: подання звіту одне на
        # весь продукт, і другого тут не зʼявляється. Документ уже
        # зібраний вище тим самим шляхом, що для json і docx, — екран і
        # файл описують один аудит за побудовою.
        from app.report.web import to_web

        view = to_web(
            document,
            audit_id=audit.id,
            site_id=audit.site_id,
            status=audit.status.value,
            finished_at=audit.finished_at,
            fallback_locale=FALLBACK_LOCALE.value,
        )
        return Response(
            content=_json_bytes(view.model_dump(mode="json")),
            media_type="application/json",
            headers=PRIVATE_HEADERS,
        )

    if format == "json":
        return Response(
            content=_json_bytes(document.to_json()),
            media_type="application/json",
            headers=PRIVATE_HEADERS,
        )

    if format == "docx-general":
        return Response(
            content=render_owner_docx(document, locale, None),
            media_type=DOCX_MEDIA_TYPE,
            headers={
                **PRIVATE_HEADERS,
                "Content-Disposition": (
                    f'attachment; filename="{general_filename(document, locale, None)}"'
                ),
            },
        )

    return Response(
        content=render_docx(document, locale),
        media_type=DOCX_MEDIA_TYPE,
        headers={
            **PRIVATE_HEADERS,
            "Content-Disposition": f'attachment; filename="{filename_for(document, locale)}"',
        },
    )


def _locale(value: str) -> Locale:
    """Мова збереженого посилання. Невідома — англійська, як усюди."""
    return parse(value) or DEFAULT_LOCALE


def _json_bytes(payload: dict[str, Any]) -> bytes:
    import json

    return json.dumps(payload, ensure_ascii=False, default=str).encode()


__all__ = ["router"]
