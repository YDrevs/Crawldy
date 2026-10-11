"""Прохід чистки за строком. Раз на добу, порціями.

Job навмисно тонкий: уся політика в `application.retention`, тут лише
цикл по порціях і коміт. Причина та сама, що й у планувальника —
крон-обгортка не має знати правил, інакше правила стає неможливо
перевірити без Redis.
"""

from __future__ import annotations

from typing import Any

import structlog

from app.application import retention
from app.core.db import SessionLocal
from app.core.logging import log

# Скільки порцій за один прохід. Обмеження є, щоб нічна чистка не тривала
# до ранку й не зустрілася з запланованими аудитами: недороблене
# доробиться наступної ночі, і це нормально — строк утримання не година.
MAX_BATCHES = 25


async def sweep(_ctx: dict[str, Any]) -> dict[str, int]:
    structlog.contextvars.bind_contextvars(job="retention")
    totals = retention.PurgeReport()
    cursor = None
    try:
        for _ in range(MAX_BATCHES):
            async with SessionLocal() as session:
                report = await retention.purge_expired(session, after=cursor)
                await session.commit()
            _add(totals, report)
            # Зупинка — коли кандидати скінчилися, а не коли порція
            # нічого не зробила: порція, повна аудитів із подовженим
            # строком, законно не робить нічого, але за нею можуть
            # стояти придатні.
            if report.considered == 0:
                break
            cursor = report.last_seen
        if totals.did_anything:
            log.info("retention_sweep", **totals.as_log())
        return totals.as_log()
    finally:
        structlog.contextvars.clear_contextvars()


def _add(totals: retention.PurgeReport, part: retention.PurgeReport) -> None:
    totals.considered += part.considered
    totals.raw_purged += part.raw_purged
    totals.findings_purged += part.findings_purged
    totals.pages_deleted += part.pages_deleted
    totals.issues_deleted += part.issues_deleted
    totals.attempts_deleted += part.attempts_deleted
    totals.snapshots_cleared += part.snapshots_cleared
    totals.organizations |= part.organizations


__all__ = ["MAX_BATCHES", "sweep"]
