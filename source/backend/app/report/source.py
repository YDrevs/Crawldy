"""Адаптери до ReportSource.

Звіт будується двома шляхами: одразу після аудиту (є AuditOutcome в пам'яті)
і пізніше з БД. Обидва зводяться до ReportSource, щоб білдер був один.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from app.audit.enums import AuditStatus
from app.audit.orchestrator import AuditOutcome
from app.report.builder import build_evidence
from app.report.types import ReportSource


def source_from_outcome(
    outcome: AuditOutcome,
    *,
    url: str | None = None,
    audit_id: uuid.UUID | None = None,
    status: AuditStatus | None = None,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
) -> ReportSource:
    ctx = outcome.context
    return ReportSource(
        url=url or ctx.entry_url,
        entry_url=ctx.entry_url,
        origin=ctx.origin,
        overall=outcome.overall,
        scores=outcome.scores,
        issues=outcome.issues,
        degraded=outcome.degraded,
        skipped_modules=outcome.skipped_modules,
        partial_modules=outcome.partial_modules,
        evidence=build_evidence(ctx),
        versions=outcome.versions,
        pages_crawled=len(ctx.pages),
        audit_id=audit_id,
        status=status
        or (
            AuditStatus.PARTIAL
            if any(d.is_failure for d in outcome.degraded)
            else AuditStatus.COMPLETED
        ),
        created_at=created_at,
        started_at=started_at,
        finished_at=finished_at,
    )


__all__ = ["source_from_outcome"]
