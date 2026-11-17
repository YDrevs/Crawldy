"""Поставити лист власнику адреси після 409 «пошта вже зареєстрована».

Не частіше за раз на `REGISTRATION_NOTICE_WINDOW_S` на адресу: інакше
перебір адрес перетворився б на розсилку спаму чужими руками в чужі
скриньки. Будь-який збій тут мовчить — 409 людині мусить дійти завжди.
"""

from __future__ import annotations

from starlette.requests import Request

from app.core.logging import log
from app.identity import service
from app.worker.queue import enqueue_registration_notice

REGISTRATION_NOTICE_WINDOW_S = 3600


async def notify_address_owner(request: Request, email: str) -> None:
    try:
        limiter = getattr(request.app.state, "rate_limiter", None)
        if limiter is None:
            return
        key = f"regnotice:email:{service.hash_token(email.strip().lower())}"
        decision = await limiter.check(key, limit=1, window=REGISTRATION_NOTICE_WINDOW_S)
        if not decision.allowed:
            return
        await enqueue_registration_notice(email=email)
    except Exception as exc:  # noqa: BLE001 — сповіщення не має ламати відповідь
        log.warning("registration_notice_enqueue_failed", error=type(exc).__name__)
