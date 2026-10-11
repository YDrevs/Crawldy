"""Фонове виконання прогону Actual AI Presence.

Окреме завдання окремого домену: жодного шляху в аудит, скоринг чи
збагачення. Провал провайдера — часткова відповідь прогону, не падіння
задачі; ідемпотентність тримається на клітинках, що вже мають рядки.
"""

from __future__ import annotations

import uuid

from app.core import runtime_config as runtime
from app.core.db import SessionLocal
from app.core.logging import log
from app.services import presence_service


async def run_presence_task(_ctx: dict, run_id: str) -> dict:
    rid = uuid.UUID(run_id)
    async with SessionLocal() as session:
        # Ключі провайдерів можуть бути збережені адміністратором після
        # старту воркера: задача читає чинну конфігурацію, а не ту, з
        # якою процес піднявся.
        await runtime.refresh(session)
        try:
            run = await presence_service.execute(session, rid)
            await session.commit()
        except Exception:
            await session.rollback()
            async with SessionLocal() as recovery:
                stored = await recovery.get(
                    presence_service.PresenceRun, rid
                )
                if stored is not None:
                    stored.status = "failed"
                    stored.error = "виконання перервано"
                    # Клієнт не платить за прогін, що впав: право
                    # повертається, вже витрачене провайдерам поглинаємо
                    # ми. Розрахунок — той самий одноразовий механізм.
                    await presence_service._settle_entitlement(
                        recovery, stored, deliverable=False
                    )
                    await recovery.commit()
            log.exception("presence_run_failed", run_id=run_id)
            raise
    log.info("presence_run_done", run_id=run_id, status=run.status,
             ok=run.observations_ok, cost_usd=round(run.cost_usd, 4))
    return {"status": run.status, "ok": run.observations_ok}
