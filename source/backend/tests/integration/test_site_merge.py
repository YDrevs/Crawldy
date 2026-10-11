"""Об'єднання сайтів не переписує минулого.

Завершений аудит — історичний факт. Єдине, що має право змінитися після
завершення, — `site_id`: організаційне групування, відповідь на питання
«до якого ресурсу організації належить цей запис», а не «що ми виміряли».

Тест знімає повний зліпок усіх полів аудиту й цілі до злиття та після
нього й вимагає, щоб різниця була рівно в одному полі. Перелічувати поля
руками тут було б помилкою: нова колонка з'явиться, а тест її не
перевірить — і саме так інваріанти тихо перестають діяти.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.inspection import inspect as sa_inspect

from app.audit.enums import AuditStatus
from app.core.run_enums import QuotaState
from app.models.audit import Audit, AuditIssue, AuditPage, AuditTarget
from app.models.sites import SiteMerge
from app.sites import service as sites
from tests.integration.conftest import register, sign_in_as

# Єдине поле аудиту, якому дозволено змінитися після завершення.
GROUPING_FIELD = "site_id"


def _now() -> datetime:
    return datetime.now(UTC)


def _snapshot(record: object) -> dict[str, object]:
    """Усі колонки запису як є. Без переліку імен руками."""
    columns = sa_inspect(type(record)).columns.keys()
    return {name: getattr(record, name) for name in columns}


async def _org(client) -> uuid.UUID:
    body = (await client.get("/v1/auth/me")).json()
    return uuid.UUID(body["organization"]["id"])


async def _full_audit(db, *, org: uuid.UUID, site_id: uuid.UUID, origin: str) -> Audit:
    """Аудит із усім, що вважається виміряним фактом."""
    audit = Audit(
        organization_id=org,
        site_id=site_id,
        url=f"{origin}/",
        origin=origin,
        status=AuditStatus.COMPLETED,
        score_overall=68,
        scores={"seo": 70, "performance": 60},
        options={"max_pages": 10, "llm": False},
        requested_options={"max_pages": 100, "llm": True},
        evidence={"crawl": {"pages_ok": 9, "pages_total": 10}},
        versions={"detector": "9bed4b4719a4", "scoring": "3fdd28054fda", "crawler": "3"},
        degraded=[{"scope": "llm", "kind": "layer_disabled", "reason": "вимкнено"}],
        skipped_modules=["accessibility"],
        quota_state=QuotaState.CONSUMED,
        started_at=_now(),
        finished_at=_now(),
    )
    db.add(audit)
    await db.flush()

    target = AuditTarget(
        audit_id=audit.id,
        position=0,
        url=f"{origin}/",
        origin=origin,
        status=AuditStatus.COMPLETED,
        score_overall=68,
        scores={"seo": 70},
        versions={"detector": "9bed4b4719a4", "scoring": "3fdd28054fda"},
        snapshot={"schema": "1", "site": {"entry_url": f"{origin}/", "origin": origin}},
        evidence={"crawl": {"pages_ok": 9}},
        finished_at=_now(),
    )
    db.add(target)
    await db.flush()

    page = AuditPage(
        audit_id=audit.id, target_id=target.id, url=f"{origin}/", status_code=200, depth=0
    )
    db.add(page)
    await db.flush()

    db.add(
        AuditIssue(
            audit_id=audit.id,
            target_id=target.id,
            page_id=page.id,
            module="seo",
            code="seo.title",
            issue_variant="missing",
            severity="high",
            title="Немає title",
            weight=5,
            msg_key="seo.title.missing",
            evidence={"found": None},
        )
    )
    await db.flush()
    return audit


@pytest.mark.asyncio
async def test_merge_changes_only_the_grouping_and_nothing_else(client, db_session):
    """Головний регресійний тест інваріанта.

    Зліпок береться з усіх колонок, а не з переліку: нове поле, додане
    завтра, потрапить під перевірку саме тому, що його ніхто не
    перелічував.
    """
    await register(client, "a@example.com")
    org = await _org(client)
    old = (await client.post("/v1/sites", json={"url": "http://example.com"})).json()
    new = (await client.post("/v1/sites", json={"url": "https://example.com"})).json()

    audit = await _full_audit(
        db_session, org=org, site_id=uuid.UUID(old["id"]), origin="http://example.com"
    )
    target = (
        await db_session.scalars(select(AuditTarget).where(AuditTarget.audit_id == audit.id))
    ).one()
    issue = (
        await db_session.scalars(select(AuditIssue).where(AuditIssue.audit_id == audit.id))
    ).one()

    before_audit = _snapshot(audit)
    before_target = _snapshot(target)
    before_issue = _snapshot(issue)

    await sites.merge(
        db_session,
        organization_id=org,
        source_site_id=uuid.UUID(old["id"]),
        target_site_id=uuid.UUID(new["id"]),
        reason="сайт переїхав на https, це той самий ресурс",
    )
    await db_session.refresh(audit)
    await db_session.refresh(target)
    await db_session.refresh(issue)

    after_audit = _snapshot(audit)
    changed = {k for k in before_audit if before_audit[k] != after_audit[k]}

    assert changed == {GROUPING_FIELD}, f"змінилося зайве: {sorted(changed - {GROUPING_FIELD})}"
    assert after_audit[GROUPING_FIELD] == uuid.UUID(new["id"])
    assert _snapshot(target) == before_target, "ціль аудиту — виміряний факт"
    assert _snapshot(issue) == before_issue, "знахідки — виміряний факт"


@pytest.mark.asyncio
async def test_the_measured_facts_survive_by_name(client, db_session):
    """Те саме, але названо вголос: що саме мусить вижити.

    Дублює перевірку вище навмисно. Зліпок ловить будь-яку зміну, але не
    пояснює, чому вона неприпустима; цей тест називає поля, і його
    провал читається без коментарів.
    """
    await register(client, "a@example.com")
    org = await _org(client)
    old = (await client.post("/v1/sites", json={"url": "http://example.com"})).json()
    new = (await client.post("/v1/sites", json={"url": "https://example.com"})).json()
    audit = await _full_audit(
        db_session, org=org, site_id=uuid.UUID(old["id"]), origin="http://example.com"
    )

    await sites.merge(
        db_session,
        organization_id=org,
        source_site_id=uuid.UUID(old["id"]),
        target_site_id=uuid.UUID(new["id"]),
        reason="переїзд",
    )
    await db_session.refresh(audit)

    assert audit.organization_id == org
    assert audit.url == "http://example.com/"
    assert audit.origin == "http://example.com", "адреса, яку читав аудит"
    assert audit.requested_options == {"max_pages": 100, "llm": True}
    assert audit.options == {"max_pages": 10, "llm": False}
    assert audit.score_overall == 68
    assert audit.scores == {"seo": 70, "performance": 60}
    assert audit.evidence["crawl"]["pages_ok"] == 9
    assert audit.versions["scoring"] == "3fdd28054fda"
    assert audit.versions["detector"] == "9bed4b4719a4"
    assert audit.degraded[0]["kind"] == "layer_disabled"
    assert audit.quota_state is QuotaState.CONSUMED
    assert audit.started_at is not None and audit.finished_at is not None


@pytest.mark.asyncio
async def test_the_snapshot_is_untouched_so_the_audit_can_still_be_recomputed(client, db_session):
    """Знімок — те, чим стара оцінка робиться порівнянною з новою.

    Втратити його при групуванні означало б втратити єдиний чесний
    спосіб порівняти два аудити після зміни методології.
    """
    await register(client, "a@example.com")
    org = await _org(client)
    old = (await client.post("/v1/sites", json={"url": "http://example.com"})).json()
    new = (await client.post("/v1/sites", json={"url": "https://example.com"})).json()
    audit = await _full_audit(
        db_session, org=org, site_id=uuid.UUID(old["id"]), origin="http://example.com"
    )
    target = (
        await db_session.scalars(select(AuditTarget).where(AuditTarget.audit_id == audit.id))
    ).one()
    snapshot_before = dict(target.snapshot)

    await sites.merge(
        db_session,
        organization_id=org,
        source_site_id=uuid.UUID(old["id"]),
        target_site_id=uuid.UUID(new["id"]),
        reason="переїзд",
    )
    await db_session.refresh(target)

    assert target.snapshot == snapshot_before


@pytest.mark.asyncio
async def test_the_merge_leaves_an_explanation(client, db_session):
    """Через рік «чому ці аудити належать іншому сайту» має мати
    відповідь у базі, а не в чиїйсь пам'яті."""
    await register(client, "a@example.com")
    org = await _org(client)
    old = (await client.post("/v1/sites", json={"url": "http://example.com"})).json()
    new = (await client.post("/v1/sites", json={"url": "https://example.com"})).json()
    await _full_audit(
        db_session, org=org, site_id=uuid.UUID(old["id"]), origin="http://example.com"
    )

    await sites.merge(
        db_session,
        organization_id=org,
        source_site_id=uuid.UUID(old["id"]),
        target_site_id=uuid.UUID(new["id"]),
        reason="сайт переїхав на https",
    )

    record = (await db_session.scalars(select(SiteMerge))).one()
    assert record.source_origin == "http://example.com"
    assert record.target_origin == "https://example.com"
    assert record.audits_moved == 1
    assert "https" in record.reason


@pytest.mark.asyncio
async def test_a_merge_without_a_reason_is_refused(client, db_session):
    await register(client, "a@example.com")
    org = await _org(client)
    old = (await client.post("/v1/sites", json={"url": "http://example.com"})).json()
    new = (await client.post("/v1/sites", json={"url": "https://example.com"})).json()

    with pytest.raises(sites.CannotMerge, match="причини"):
        await sites.merge(
            db_session,
            organization_id=org,
            source_site_id=uuid.UUID(old["id"]),
            target_site_id=uuid.UUID(new["id"]),
            reason="   ",
        )


@pytest.mark.asyncio
async def test_sites_of_another_organization_cannot_be_merged(client, db_session):
    """Об'єднання — теж дія над ресурсом, і власність перевіряється так само."""
    await register(client, "victim@example.com")
    victim_site = (await client.post("/v1/sites", json={"url": "https://victim.example"})).json()

    await sign_in_as(client, "attacker@example.com")
    org = await _org(client)
    mine = (await client.post("/v1/sites", json={"url": "https://mine.example"})).json()

    with pytest.raises(sites.CannotMerge, match="не знайдено"):
        await sites.merge(
            db_session,
            organization_id=org,
            source_site_id=uuid.UUID(victim_site["id"]),
            target_site_id=uuid.UUID(mine["id"]),
            reason="спроба",
        )


@pytest.mark.asyncio
async def test_the_source_site_is_archived_not_deleted(client, db_session):
    """Видалення звільнило б адресу, і повторне додавання створило б
    дубль мовчки."""
    await register(client, "a@example.com")
    org = await _org(client)
    old = (await client.post("/v1/sites", json={"url": "http://example.com"})).json()
    new = (await client.post("/v1/sites", json={"url": "https://example.com"})).json()

    await sites.merge(
        db_session,
        organization_id=org,
        source_site_id=uuid.UUID(old["id"]),
        target_site_id=uuid.UUID(new["id"]),
        reason="переїзд",
    )

    still_there = await sites.get(
        db_session, site_id=uuid.UUID(old["id"]), organization_id=org
    )
    assert still_there is not None
    assert still_there.archived_at is not None


@pytest.mark.asyncio
async def test_history_follows_the_resource_after_the_merge(client, db_session):
    await register(client, "a@example.com")
    org = await _org(client)
    old = (await client.post("/v1/sites", json={"url": "http://example.com"})).json()
    new = (await client.post("/v1/sites", json={"url": "https://example.com"})).json()
    await _full_audit(
        db_session, org=org, site_id=uuid.UUID(old["id"]), origin="http://example.com"
    )

    await sites.merge(
        db_session,
        organization_id=org,
        source_site_id=uuid.UUID(old["id"]),
        target_site_id=uuid.UUID(new["id"]),
        reason="переїзд",
    )

    moved = (await client.get(f"/v1/sites/{new['id']}/history")).json()
    assert len(moved["points"]) == 1
