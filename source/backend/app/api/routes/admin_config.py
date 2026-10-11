"""Службова конфігурація: платіжний провайдер і AI-моделі присутності.

Окремий роутер під тим самим префіксом, що й решта службового API, з
тією самою залежністю `StaffDep`: клієнт із вгаданим URL отримує 403 так
само, як клієнт без URL, — і жодне значення секрету не проходить через
жодне поле відповіді.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, StaffDep
from app.services import admin_config_service as config_service

router = APIRouter(prefix="/v1/admin/config", tags=["admin"])


class SettingsIn(BaseModel):
    """Значення по ключах. `null` — прибрати збережене (повернутися до оточення)."""

    values: dict[str, str | None] = Field(default_factory=dict)


class AiSettingsIn(BaseModel):
    policy: dict[str, Any] | None = None
    values: dict[str, str | None] | None = None


@router.get("/payment")
async def payment_settings(
    request: Request, session: SessionDep, _: StaffDep
) -> dict[str, Any]:
    return await config_service.payment_view(
        session, webhook_base=str(request.base_url)
    )


@router.put("/payment")
async def update_payment_settings(
    payload: SettingsIn, request: Request, session: SessionDep, actor: StaffDep
) -> dict[str, Any]:
    errors = await config_service.save_payment(
        session, payload.values, updated_by=actor.user_id
    )
    if errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": errors}
        )
    # Публікація йде під ще не закоміченими налаштуваннями — вона мусить
    # питати провайдера НОВИМ ключем, а не старим. Ціна цього — мережеві
    # виклики при відкритій транзакції; це службова дія однієї людини, і
    # альтернатива (два коміти) лишала б вікно, у якому провайдер уже
    # новий, а прайси ще старі.
    published = await config_service.republish_after_save(session, payload.values)
    await session.commit()
    view = await config_service.payment_view(
        session, webhook_base=str(request.base_url)
    )
    # Що з каталогом після цього збереження: `None` — публікація не була
    # потрібна, список — стан кожного запису.
    view["published"] = published
    return view


@router.post("/payment/test")
async def test_payment_connection(session: SessionDep, _: StaffDep) -> dict[str, Any]:
    return await config_service.test_payment(session)


@router.get("/ai")
async def ai_settings(session: SessionDep, _: StaffDep) -> dict[str, Any]:
    return await config_service.ai_view(session)


@router.put("/ai")
async def update_ai_settings(
    payload: AiSettingsIn, session: SessionDep, actor: StaffDep
) -> dict[str, Any]:
    errors = await config_service.save_ai(
        session, policy=payload.policy, values=payload.values, updated_by=actor.user_id
    )
    if errors:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail={"errors": errors}
        )
    await session.commit()
    return await config_service.ai_view(session)


@router.post("/ai/{provider}/test")
async def test_ai_connection(
    provider: str, session: SessionDep, _: StaffDep
) -> dict[str, Any]:
    return await config_service.test_ai_provider(session, provider)
