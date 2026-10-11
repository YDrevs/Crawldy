"""Збірка ReportSource із рядків БД.

Живе в services, а не в app/report/, щоб шар звіту лишався вільним від ORM
так само, як app/audit/. Білдер звіту при цьому один на обидва шляхи —
свіжий аудит і давно збережений.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.audit.enums import AuditStatus, DegradationKind, Module, Severity
from app.audit.orchestrator import semantic_gaps
from app.audit.types import Degradation, Issue
from app.models.audit import Audit, AuditIssue, AuditTarget
from app.report.types import ReportSource


def source_from_target(audit: Audit, target: AuditTarget) -> ReportSource:
    """Звіт по одній цілі. Шапка бере часи з аудиту, решта — з цілі."""
    evidence = target.evidence or {}
    http = evidence.get("http", {})
    return ReportSource(
        url=target.url,
        entry_url=http.get("entry_url") or target.url,
        origin=http.get("origin") or target.origin,
        overall=target.score_overall,
        scores=target.scores or {},
        issues=[_issue_from_row(row) for row in target.issues],
        degraded=[Degradation.from_json(d) for d in (target.degraded or [])],
        skipped_modules={Module(m) for m in (target.skipped_modules or [])},
        # Неповні модулі відновлюються з деградацій — окрема колонка була б
        # третім місцем зберігання того самого факту.
        partial_modules=_partial_modules(target.degraded or [], target.skipped_modules or []),
        evidence=evidence,
        versions=dict(target.versions or {}),
        pages_crawled=len(target.pages),
        audit_id=audit.id,
        status=AuditStatus(target.status),
        created_at=audit.created_at,
        started_at=target.started_at or audit.started_at,
        finished_at=target.finished_at or audit.finished_at,
    )


def source_from_audit(audit: Audit) -> ReportSource:
    """Аудит з однією ціллю читається як раніше; з кількома — беремо первинну."""
    target = pick_target(audit, None)
    if target is not None:
        return source_from_target(audit, target)

    evidence = audit.evidence or {}
    http = evidence.get("http", {})
    return ReportSource(
        url=audit.url,
        entry_url=http.get("entry_url") or audit.url,
        origin=http.get("origin") or audit.origin,
        overall=audit.score_overall,
        scores=audit.scores or {},
        issues=[_issue_from_row(row) for row in audit.issues],
        degraded=[Degradation.from_json(d) for d in (audit.degraded or [])],
        skipped_modules={Module(m) for m in (audit.skipped_modules or [])},
        partial_modules=_partial_modules(audit.degraded or [], audit.skipped_modules or []),
        evidence=evidence,
        versions=dict(audit.versions or {}),
        pages_crawled=len(audit.pages),
        audit_id=audit.id,
        status=AuditStatus(audit.status),
        created_at=audit.created_at,
        started_at=audit.started_at,
        finished_at=audit.finished_at,
    )


def pick_target(audit: Audit, target_id: uuid.UUID | None) -> AuditTarget | None:
    """Ціль за id, або первинна, якщо id не вказано."""
    targets = sorted(audit.targets, key=lambda t: t.position)
    if not targets:
        return None
    if target_id is None:
        return targets[0]
    return next((t for t in targets if t.id == target_id), None)


def reportable_targets(audit: Audit) -> list[AuditTarget]:
    """Цілі, для яких є що показати. Провалена ціль звіту не має."""
    return [
        t
        for t in sorted(audit.targets, key=lambda t: t.position)
        if AuditStatus(t.status) in {AuditStatus.COMPLETED, AuditStatus.PARTIAL}
    ]


def _partial_modules(degraded: list[dict[str, Any]], skipped: list[str]) -> set[Module]:
    measured = {
        m
        for d in degraded
        if d.get("kind") == DegradationKind.PARTIAL_DATA.value
        for m in (Module(x) for x in d.get("affected_modules", []))
    }
    # Модуль, оцінений без семантичного детектора, неповний і в збереженому
    # аудиті. Окремого прапорця в рядку немає й міграції не буде: він
    # виводиться при показі з тих самих деградацій за правилом свіжого
    # аудиту. Старий звіт з вимкненим шаром казав `partial: false` поруч із
    # приміткою про неповні дані.
    semantic = semantic_gaps(
        (Degradation.from_json(d) for d in degraded), {Module(m) for m in skipped}
    )
    return measured | semantic


def _issue_from_row(row: AuditIssue) -> Issue:
    evidence = dict(row.evidence or {})
    # page_url кладеться всередину evidence при збереженні (щоб API не робив
    # join) — витягуємо назад, інакше в звіті зникне групування по сторінках.
    page_url = evidence.pop("page_url", None)
    return Issue(
        code=row.code,
        module=Module(row.module),
        severity=Severity(row.severity),
        title=row.title,
        description=row.description,
        recommendation=row.recommendation,
        evidence=evidence,
        weight=row.weight,
        page_url=page_url,
        msg=row.msg_key or row.code,
        params=dict(row.msg_params or {}),
        key=row.issue_variant or "",
    )


__all__ = ["pick_target", "reportable_targets", "source_from_audit", "source_from_target"]
