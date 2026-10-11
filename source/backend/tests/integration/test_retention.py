"""Чистка за строком: важке зникає, аудит лишається зрозумілим.

Головний інваріант: після чистки сирих даних історичний аудит мусить
відповідати на всі питання, які до нього ставлять, — що аудитували, коли,
з якими опціями, якими версіями, з яким результатом і чому не вийшло,
якщо не вийшло. Тест `test_a_purged_audit_still_answers_every_question`
перевіряє цей перелік буквально, полем за полем.

Другий інваріант: чистка — не видалення. Рядок `audits` не зникає за
жодного строку; видалення — окремий шлях з окремими запобіжниками,
і він перевіряється в `test_deletion.py`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.application import retention
from app.audit.enums import AuditStatus, AuditTrigger, Module, Severity
from app.billing import service as billing
from app.identity import service as identity
from app.models.audit import Audit, AuditAttempt, AuditIssue, AuditPage, AuditTarget

PASSWORD = "correct-horse-battery"


def _now() -> datetime:
    return datetime.now(UTC)


def _long_ago(days: int) -> datetime:
    return _now() - timedelta(days=days)


async def _org(db, email: str) -> uuid.UUID:
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    return reg.organization.id


async def _finished_audit(
    db,
    organization_id: uuid.UUID,
    *,
    finished_days_ago: int,
    origin: str = "https://example.com",
) -> uuid.UUID:
    """Завершений аудит з усім важким: сторінки, знімок, знахідки, спроби."""
    audit = Audit(
        organization_id=organization_id,
        url=f"{origin}/",
        origin=origin,
        status=AuditStatus.COMPLETED,
        trigger=AuditTrigger.MANUAL,
        score_overall=64,
        scores={"seo": 55, "performance": 70},
        options={"max_pages": 10},
        requested_options={"max_pages": 100},
        versions={"detector": "d1", "scoring": "s1", "crawler": "c1"},
        evidence={"crawl": {"read": 10, "known": 40}},
        degraded=[{"scope": "performance", "kind": "partial_data", "reason": "без ключа PSI"}],
        findings_summary={
            "total": 2,
            "distinct_keys": 2,
            "by_severity": {"high": 1, "low": 1},
            "by_module": {"seo": 2},
            "top": [
                {"issue_key": "seo.h1:multiple", "severity": "high", "module": "seo", "count": 1}
            ],
        },
        finished_at=_long_ago(finished_days_ago),
        started_at=_long_ago(finished_days_ago),
    )
    db.add(audit)
    await db.flush()

    target = AuditTarget(
        audit_id=audit.id,
        position=0,
        url=audit.url,
        origin=audit.origin,
        status=AuditStatus.COMPLETED,
        score_overall=64,
        scores={"seo": 55},
        snapshot={"schema": 1, "pages": [{"url": audit.url, "text": "великий" * 1000}]},
        evidence={"crawl": {"read": 10}},
        versions=audit.versions,
        finished_at=audit.finished_at,
    )
    db.add(target)
    await db.flush()

    page = AuditPage(
        audit_id=audit.id, target_id=target.id, url=audit.url, status_code=200,
        raw={"html_excerpt": "багато байтів"},
    )
    db.add(page)
    await db.flush()
    db.add(
        AuditIssue(
            audit_id=audit.id, target_id=target.id, page_id=page.id,
            module=Module.SEO, code="seo.h1", severity=Severity.HIGH,
            title="cached", evidence={"found": 2}, weight=3,
            issue_variant="multiple", msg_key="seo.h1.multiple", msg_params={"count": 2},
        )
    )
    db.add(AuditAttempt(audit_id=audit.id, number=1, status=AuditStatus.COMPLETED))
    await db.flush()
    # Ідентифікатор, а не живий обʼєкт: тести роблять expire_all, і доступ
    # до атрибута простроченого обʼєкта став би синхронним довантаженням
    # усередині async — MissingGreenlet. На id прострочення не діє.
    return audit.id


async def _count(db, model, audit_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(model).where(model.audit_id == audit_id)
    return int((await db.execute(stmt)).scalar_one())


# ── класи чистяться в правильному порядку ──────────────────────────────────


@pytest.mark.asyncio
async def test_young_audits_are_not_touched(db_session):
    org = await _org(db_session, "young@example.com")
    audit_id = await _finished_audit(db_session, org, finished_days_ago=5)

    report = await retention.purge_expired(db_session)

    assert report.raw_purged == 0
    db_session.expire_all()
    fresh = await db_session.get(Audit, audit_id)
    assert fresh.raw_purged_at is None
    assert await _count(db_session, AuditPage, audit_id) == 1


@pytest.mark.asyncio
async def test_raw_goes_first_findings_stay(db_session):
    """Між строками сирих даних і знахідок аудит читабельний, але не
    перераховуваний — і обидва факти видно з міток."""
    org = await _org(db_session, "raw@example.com")
    audit_id = await _finished_audit(db_session, org, finished_days_ago=100)

    report = await retention.purge_expired(db_session)

    assert report.raw_purged == 1
    assert report.findings_purged == 0
    db_session.expire_all()
    fresh = await db_session.get(Audit, audit_id)
    assert fresh.raw_purged_at is not None
    assert fresh.findings_purged_at is None
    assert await _count(db_session, AuditPage, audit_id) == 0
    assert await _count(db_session, AuditIssue, audit_id) == 1, "знахідки живі"
    target = (
        (await db_session.execute(select(AuditTarget).where(AuditTarget.audit_id == audit_id)))
        .scalars().one()
    )
    assert target.snapshot == {}, "знімок порожній"
    assert target.scores == {"seo": 55}, "бали цілі лишились"


@pytest.mark.asyncio
async def test_after_the_findings_term_only_the_record_remains(db_session):
    org = await _org(db_session, "findings@example.com")
    audit_id = await _finished_audit(db_session, org, finished_days_ago=1000)

    report = await retention.purge_expired(db_session)

    assert report.findings_purged == 1
    db_session.expire_all()
    assert await _count(db_session, AuditIssue, audit_id) == 0
    assert await _count(db_session, AuditAttempt, audit_id) == 0
    fresh = await db_session.get(Audit, audit_id)
    assert fresh is not None, "рядок аудиту живий"
    assert fresh.findings_purged_at is not None


@pytest.mark.asyncio
async def test_a_purged_audit_still_answers_every_question(db_session):
    """Перелік з інваріанта, полем за полем."""
    org = await _org(db_session, "questions@example.com")
    audit_id = await _finished_audit(db_session, org, finished_days_ago=1000)

    await retention.purge_expired(db_session)

    db_session.expire_all()
    fresh = await db_session.get(Audit, audit_id)
    assert fresh.url and fresh.origin, "що аудитували"
    assert fresh.finished_at is not None, "коли"
    assert fresh.options == {"max_pages": 10}, "з якими опціями"
    assert fresh.requested_options == {"max_pages": 100}, "і що просили до обрізання"
    assert fresh.versions["detector"] == "d1", "якими версіями"
    assert fresh.status is AuditStatus.COMPLETED, "з яким статусом"
    assert fresh.score_overall == 64 and fresh.scores, "бали"
    assert fresh.findings_summary["total"] == 2, "зведення знахідок"
    assert fresh.findings_summary["top"], "головні проблеми поіменно"
    assert fresh.degraded, "причини деградації"
    assert fresh.evidence["crawl"]["read"] == 10, "покриття"
    assert fresh.organization_id == org, "чий це запуск"


# ── ідемпотентність і межі ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_second_pass_does_nothing(db_session):
    org = await _org(db_session, "twice@example.com")
    audit_id = await _finished_audit(db_session, org, finished_days_ago=1000)

    first = await retention.purge_expired(db_session)
    db_session.expire_all()
    marks = await db_session.get(Audit, audit_id)
    stamped = (marks.raw_purged_at, marks.findings_purged_at)

    second = await retention.purge_expired(db_session)

    assert first.did_anything
    assert not second.did_anything
    db_session.expire_all()
    fresh = await db_session.get(Audit, audit_id)
    assert (fresh.raw_purged_at, fresh.findings_purged_at) == stamped, "мітки не пересунулись"


@pytest.mark.asyncio
async def test_an_unfinished_audit_is_never_a_candidate(db_session):
    """`finished_at IS NULL` — не «дуже старий», а «ще живий»."""
    org = await _org(db_session, "running@example.com")
    audit = Audit(
        organization_id=org, url="https://example.com/", origin="https://example.com",
        status=AuditStatus.RUNNING, options={}, created_at=_long_ago(1000),
    )
    db_session.add(audit)
    await db_session.flush()

    report = await retention.purge_expired(db_session)
    assert report.considered == 0


@pytest.mark.asyncio
async def test_purge_never_deletes_the_audit_row(db_session):
    """Скільки б не минуло — запис лишається. Це межа механізму, а не
    налаштування: чистка фізично не вміє видаляти рядок."""
    org = await _org(db_session, "never@example.com")
    ids = [
        await _finished_audit(db_session, org, finished_days_ago=d)
        for d in (40, 400, 4000)
    ]

    for _ in range(3):
        await retention.purge_expired(db_session)

    for audit_id in ids:
        assert await db_session.get(Audit, audit_id) is not None


# ── строк — властивість організації ────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_extended_plan_keeps_its_snapshots_while_others_lose_them(db_session):
    """Той самий прохід, різні організації — різні строки."""
    keeper = await _org(db_session, "keeper@example.com")
    await billing.grant_override(
        db_session, organization_id=keeper, key="raw_retention_days",
        value=100_000, reason="агенція: перерахунок старих аудитів",
    )
    ordinary = await _org(db_session, "ordinary@example.com")

    kept = await _finished_audit(
        db_session, keeper, finished_days_ago=100, origin="https://a.example"
    )
    lost = await _finished_audit(
        db_session, ordinary, finished_days_ago=100, origin="https://b.example"
    )

    report = await retention.purge_expired(db_session)

    assert report.raw_purged == 1
    db_session.expire_all()
    assert (await db_session.get(Audit, kept)).raw_purged_at is None
    assert (await db_session.get(Audit, lost)).raw_purged_at is not None


@pytest.mark.asyncio
async def test_a_stuck_head_does_not_starve_the_queue(db_session):
    """Регресія голодування.

    Найстаріші аудити належать організації з подовженим строком — вони
    завжди в голові черги й ніколи не чистяться. З порцією в один рядок
    прохід без курсора застрягав би на них вічно, а придатний аудит
    позаду не дочекався б ніколи.
    """
    keeper = await _org(db_session, "head@example.com")
    await billing.grant_override(
        db_session, organization_id=keeper, key="raw_retention_days",
        value=100_000, reason="подовжений строк",
    )
    ordinary = await _org(db_session, "behind@example.com")

    for days in (900, 800, 700):
        await _finished_audit(db_session, keeper, finished_days_ago=days,
                              origin=f"https://k{days}.example")
    eligible = await _finished_audit(db_session, ordinary, finished_days_ago=100,
                                     origin="https://e.example")

    cursor = None
    purged = 0
    for _ in range(10):
        report = await retention.purge_expired(db_session, batch=1, after=cursor)
        purged += report.raw_purged
        if report.considered == 0:
            break
        cursor = report.last_seen

    assert purged == 1
    db_session.expire_all()
    assert (await db_session.get(Audit, eligible)).raw_purged_at is not None


@pytest.mark.asyncio
async def test_the_batch_is_respected(db_session):
    org = await _org(db_session, "batch@example.com")
    for i in range(3):
        await _finished_audit(db_session, org, finished_days_ago=100 + i,
                              origin=f"https://b{i}.example")

    report = await retention.purge_expired(db_session, batch=2)
    assert report.considered == 2
