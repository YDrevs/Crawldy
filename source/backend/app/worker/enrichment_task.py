"""Фонове виконання AI-збагачення.

Окремий модуль і окреме завдання: збагачення виконується ПІСЛЯ того, як
детерміністичний аудит уже завершений і збережений, і не має жодного
впливу на його долю. Провал тут ніколи не робить аудит невдалим —
завдання просто повертає статус прогону.

Рендеринг звіту сюди не заходить ніколи: звіт читає збережені
результати, мережева інференція живе тільки тут.
"""

from __future__ import annotations

import uuid

from app.application import enrichment
from app.core.db import SessionLocal
from app.core.logging import log
from app.enrich import policy as analysis_policy
from app.enrich.contracts import TaskType
from app.services.ai_policy_service import load_analysis


async def run_enrichment_task(_ctx: dict, audit_id: str, task_type: str) -> dict:
    """Ідемпотентно: та сама логічна робота — той самий рядок і результат.

    Повторна доставка того самого повідомлення чергою не породжує другого
    платного виклику: `start_run` знаходить наявний прогін, а
    `execute_run` не виконує завершений удруге.
    """
    aid = uuid.UUID(audit_id)
    task = TaskType(task_type)
    try:
        async with SessionLocal() as session:
            run = await enrichment.start_run(session, aid, task, experimental=True)
            run_id = run.id
            await session.commit()

        async with SessionLocal() as session:
            analysis = await load_analysis(session)
            done = await enrichment.execute_run(
                session, run_id, routes=analysis_policy.routes_for(analysis)
            )
            status = done.status.value
            error = done.error
            await session.commit()
    except enrichment.EnrichmentDenied as exc:
        # Непридатний аудит чи вимкнений шлюз — не збій, а відмова за
        # правилом. Її треба бачити в логу, але не як помилку.
        log.info("enrichment_denied", audit_id=audit_id, task=task_type, reason=exc.reason)
        return {"audit_id": audit_id, "task": task_type, "status": "denied", "reason": exc.reason}

    log.info("enrichment_finished", audit_id=audit_id, task=task_type, status=status)
    return {"audit_id": audit_id, "task": task_type, "status": status, "error": error}
