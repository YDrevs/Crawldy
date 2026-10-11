"""Планувальник: раз на хвилину питає, чому час.

Окрема функція, а не окремий процес: ARQ вміє крон, і другий деплой-юніт
тут нічого не дав би. Але й запускати її в кількох екземплярах безпечно —
захист від подвійного запуску живе в базі, а не в тому, що процес один.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.application import scheduled
from app.core.db import SessionLocal
from app.core.logging import log
from app.worker.queue import enqueue_audit

# Скільки розкладів беремо за один прохід.
#
# Обмеження не через продуктивність, а через оренду: захоплений і не
# запущений розклад чекає, поки вона мине. Менша порція означає менше
# втраченого часу, якщо процес упаде посеред проходу.
BATCH = 20


async def tick(_ctx: dict[str, Any]) -> dict[str, int]:
    """Один прохід планувальника."""
    structlog.contextvars.bind_contextvars(job="scheduler")
    created = 0
    missed = 0
    try:
        async with SessionLocal() as session:
            runs = await scheduled.run_all_due(session, batch=BATCH)
            await session.commit()

        for run in runs:
            if run.started and run.audit_id is not None:
                try:
                    await enqueue_audit(run.audit_id)
                    created += 1
                except Exception as exc:  # noqa: BLE001 — черга не має валити прохід
                    # Запис уже є й уже вказує на розклад; лишити його
                    # queued назавжди не можна, тож позначаємо невдалим і
                    # повертаємо квоту — черга це наша інфраструктура.
                    log.error(
                        "scheduled_enqueue_failed",
                        audit_id=str(run.audit_id),
                        schedule_id=str(run.schedule_id),
                        scheduled_for=run.scheduled_for.isoformat(),
                        error=str(exc),
                    )
                    await _fail_queued(run.audit_id, run.schedule_id, str(exc))
            else:
                missed += 1
                log.info(
                    "scheduled_run_missed",
                    schedule_id=str(run.schedule_id),
                    scheduled_for=run.scheduled_for.isoformat(),
                    audit_id=str(run.audit_id) if run.audit_id else None,
                    reused=run.reused,
                    reason=run.reason,
                )

        if runs:
            log.info("scheduler_tick", claimed=len(runs), created=created, missed=missed)
        return {"claimed": len(runs), "created": created, "missed": missed}
    finally:
        structlog.contextvars.clear_contextvars()


async def _fail_queued(audit_id: Any, schedule_id: Any, error: str) -> None:
    """Запис є, черги немає.

    Спроби тут не було: жоден воркер за аудит не брався, тож у журналі
    спроб порожньо, і це правда. Повтору теж немає — його ставить та сама
    черга, яка щойно відмовила.
    """
    from app.application import audits as application
    from app.core.run_enums import FailureClass
    from app.scheduling import service as schedules
    from app.services import audit_service

    reason = f"черга недоступна: {error}"
    async with SessionLocal() as session:
        await audit_service.mark_failed(
            session, audit_id, reason, failure=FailureClass.INTERNAL_ERROR
        )
        audit = await audit_service.get_audit(session, audit_id)
        if audit is not None:
            await application.settle_quota(
                session, audit, failure=FailureClass.INTERNAL_ERROR
            )
        await schedules.note_outcome(session, schedule_id=schedule_id, ok=False, reason=reason)
        await session.commit()
