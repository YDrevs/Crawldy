"""Вікно історії тарифу: приховує, а не знищує.

Найважливіше тут не те, що вікно працює, а те, що воно оборотне:
пониження тарифу звужує криву, апгрейд повертає її цілою. Якби тариф
керував видаленням, місяць на дешевшому тарифі знищував би рік історії —
і жодна підтримка не змогла б допомогти.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.audit.enums import AuditStatus
from app.billing import service as billing
from app.models.audit import Audit, AuditTarget
from tests.integration.conftest import register


async def _point(db, org: uuid.UUID, *, days_ago: int, score: int) -> None:
    """Одна точка історії: аудит із ціллю, завершений тоді-то."""
    finished = datetime.now(UTC) - timedelta(days=days_ago)
    audit = Audit(
        organization_id=org,
        url="https://example.com/",
        origin="https://example.com",
        status=AuditStatus.COMPLETED,
        score_overall=score,
        options={},
        finished_at=finished,
    )
    db.add(audit)
    await db.flush()
    db.add(
        AuditTarget(
            audit_id=audit.id,
            position=0,
            url=audit.url,
            origin=audit.origin,
            status=AuditStatus.COMPLETED,
            score_overall=score,
            scores={"seo": score},
            versions={"detector": "d1", "scoring": "s1"},
            finished_at=finished,
        )
    )
    await db.flush()


@pytest.mark.asyncio
async def test_the_window_hides_old_points_and_says_so(client, db_session):
    """Без прав тариф показує 30 днів — і чесно називає число."""
    body = (await register(client, "window@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    await _point(db_session, org, days_ago=5, score=70)
    await _point(db_session, org, days_ago=100, score=40)

    seen = (
        await client.get("/v1/audits/history/by-origin", params={"origin": "https://example.com"})
    ).json()

    assert seen["visible_days"] == 30
    assert len(seen["points"]) == 1
    assert seen["points"][0]["overall"] == 70, "лишилась свіжа точка"


@pytest.mark.asyncio
async def test_an_upgrade_brings_the_history_back_whole(client, db_session):
    """Головна перевірка: приховане повертається. Знищене не повернулося б."""
    body = (await register(client, "upgrade@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    await _point(db_session, org, days_ago=5, score=70)
    await _point(db_session, org, days_ago=100, score=40)

    before = (
        await client.get("/v1/audits/history/by-origin", params={"origin": "https://example.com"})
    ).json()
    assert len(before["points"]) == 1

    await billing.grant_override(
        db_session, organization_id=org, key="history_retention_days",
        value=None, reason="апгрейд тарифу",
    )

    after = (
        await client.get("/v1/audits/history/by-origin", params={"origin": "https://example.com"})
    ).json()
    assert after["visible_days"] is None
    assert len(after["points"]) == 2, "стара точка нікуди не зникала"
    assert {p["overall"] for p in after["points"]} == {40, 70}


@pytest.mark.asyncio
async def test_a_history_entirely_outside_the_window_reads_as_none_visible(client, db_session):
    """404 тут чесний: у вікні тарифу точок немає. Число поруч каже чому."""
    body = (await register(client, "outside@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    await _point(db_session, org, days_ago=100, score=40)

    response = await client.get(
        "/v1/audits/history/by-origin", params={"origin": "https://example.com"}
    )
    assert response.status_code == 404
