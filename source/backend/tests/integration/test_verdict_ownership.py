"""Вердикт можна поставити лише на знахідку свого аудиту.

`verdict_service.record` брав `AuditIssue` за ідентифікатором без жодної
перевірки організації: будь-хто з входом міг переписати оцінку знахідки
чужого аудиту — а вердикти — єдине джерело зовнішньої правди про чеки.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.audit.enums import Module, Severity
from app.models.audit import AuditIssue, AuditTarget, IssueVerdict
from tests.integration.conftest import register, sign_in_as
from tests.integration.test_audit_ownership import _make_audit, _own_organization


async def _issue_of_owner(client, db) -> uuid.UUID:
    await register(client, "owner@example.com")
    audit = await _make_audit(db, organization_id=await _own_organization(client))
    target = (
        await db.scalars(select(AuditTarget).where(AuditTarget.audit_id == audit.id))
    ).one()
    issue = AuditIssue(
        audit_id=audit.id,
        target_id=target.id,
        module=Module.SEO,
        code="seo.h1",
        severity=Severity.HIGH,
        title="H1",
        evidence={"found": 2, "expected": 1},
        weight=3,
    )
    db.add(issue)
    await db.commit()
    return issue.id


async def _verdicts(db, issue_id: uuid.UUID) -> list[IssueVerdict]:
    db.expire_all()
    return list(
        (await db.scalars(select(IssueVerdict).where(IssueVerdict.issue_id == issue_id))).all()
    )


@pytest.mark.asyncio
async def test_a_stranger_cannot_judge_someone_elses_finding(client, db_session):
    issue_id = await _issue_of_owner(client, db_session)

    await sign_in_as(client, "stranger@example.com")
    response = await client.put(
        f"/v1/audits/issues/{issue_id}/verdict", json={"verdict": "wrong"}
    )

    assert response.status_code == 404
    assert await _verdicts(db_session, issue_id) == []


@pytest.mark.asyncio
async def test_the_owner_records_a_verdict(client, db_session):
    issue_id = await _issue_of_owner(client, db_session)

    response = await client.put(
        f"/v1/audits/issues/{issue_id}/verdict", json={"verdict": "agreed"}
    )

    assert response.status_code == 200
    assert [v.verdict.value for v in await _verdicts(db_session, issue_id)] == ["agreed"]
