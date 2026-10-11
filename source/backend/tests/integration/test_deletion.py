"""Видалення на запит: інший шлях, ніж чистка, і навмисно.

Три способи позбутися даних мають різних відповідальних і різні наслідки,
і найдорожча можлива помилка — викликати не той. Тому тут перевіряється
не лише те, що видалення працює, а й те, що воно **відмовляє**: без
причини, без підтвердження, для чужої організації.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.application import deletion, retention
from app.audit.enums import AuditStatus
from app.billing import quota
from app.identity import service as identity
from app.models.audit import Audit
from app.models.identity import Organization
from app.models.scheduling import AuditSchedule
from app.models.sites import Site
from app.scheduling import service as schedules
from app.scheduling.enums import Cadence
from app.sites import service as sites

PASSWORD = "correct-horse-battery"


async def _org(db, email: str) -> uuid.UUID:
    reg = await identity.register(db, email=email, password=PASSWORD)
    await db.flush()
    return reg.organization.id


async def _audit(db, organization_id: uuid.UUID) -> uuid.UUID:
    audit = Audit(
        organization_id=organization_id,
        url="https://example.com/",
        origin="https://example.com",
        status=AuditStatus.COMPLETED,
        options={},
        finished_at=datetime.now(UTC),
    )
    db.add(audit)
    await db.flush()
    return audit.id


# ── видалення одного аудиту ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deleting_an_audit_removes_the_record_itself(db_session):
    """На відміну від чистки: тут зникає сам рядок. Це і є різниця шляхів."""
    org = await _org(db_session, "del@example.com")
    audit_id = await _audit(db_session, org)

    done = await deletion.delete_audit(
        db_session, audit_id=audit_id, organization_id=org,
        reason="клієнт попросив прибрати тестовий запуск",
    )

    assert done is True
    assert await db_session.get(Audit, audit_id) is None


@pytest.mark.asyncio
async def test_deletion_without_a_reason_is_refused(db_session):
    """Через рік єдиним поясненням діри в історії буде рядок у журналі."""
    org = await _org(db_session, "noreason@example.com")
    audit_id = await _audit(db_session, org)

    with pytest.raises(deletion.DeletionRefused):
        await deletion.delete_audit(
            db_session, audit_id=audit_id, organization_id=org, reason="   "
        )
    assert await db_session.get(Audit, audit_id) is not None


@pytest.mark.asyncio
async def test_a_foreign_audit_cannot_be_deleted(db_session):
    """Чужий аудит для цієї функції не існує — навіть як помилка 403."""
    owner = await _org(db_session, "owner@example.com")
    stranger = await _org(db_session, "stranger@example.com")
    audit_id = await _audit(db_session, owner)

    done = await deletion.delete_audit(
        db_session, audit_id=audit_id, organization_id=stranger, reason="спроба"
    )

    assert done is False
    assert await db_session.get(Audit, audit_id) is not None


@pytest.mark.asyncio
async def test_deletion_does_not_refund_the_quota(db_session):
    """Видалення результату не скасовує роботи, яку ми зробили.

    Інакше повернення грошей влаштовувалося б кнопкою «видалити».
    """
    org = await _org(db_session, "paid@example.com")
    period = quota.period_for(None)
    await quota.consume(db_session, organization_id=org, period=period, limit=10)
    audit_id = await _audit(db_session, org)
    used_before = await quota.used_in(db_session, organization_id=org, period=period)

    await deletion.delete_audit(
        db_session, audit_id=audit_id, organization_id=org, reason="прибрати"
    )

    used_after = await quota.used_in(db_session, organization_id=org, period=period)
    assert used_after == used_before == 1


# ── закриття акаунта ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_closing_an_account_takes_everything_with_it(db_session):
    org = await _org(db_session, "close@example.com")
    site = await sites.create(
        db_session, organization_id=org, url="https://example.com", created_by_user_id=None
    )
    await schedules.create(
        db_session, organization_id=org, site_id=site.id, created_by_user_id=None,
        cadence=Cadence.DAILY,
    )
    await _audit(db_session, org)
    await _audit(db_session, org)

    counted = await deletion.delete_organization(
        db_session, organization_id=org, confirmation=org, reason="закриття акаунта"
    )

    assert counted.audits == 2
    assert counted.sites == 1
    assert counted.schedules == 1
    assert await db_session.get(Organization, org) is None
    left = (
        (await db_session.execute(select(Audit).where(Audit.organization_id == org)))
        .scalars().all()
    )
    assert left == []
    orphan_sites = (
        (await db_session.execute(select(Site).where(Site.organization_id == org)))
        .scalars().all()
    )
    assert orphan_sites == []
    orphan_schedules = (
        (
            await db_session.execute(
                select(AuditSchedule).where(AuditSchedule.organization_id == org)
            )
        )
        .scalars().all()
    )
    assert orphan_schedules == []


@pytest.mark.asyncio
async def test_a_mismatched_confirmation_refuses_to_close(db_session):
    """Захист від виклику з неправильним аргументом, а не від зловмисника."""
    org = await _org(db_session, "mismatch@example.com")
    await _audit(db_session, org)

    with pytest.raises(deletion.DeletionRefused):
        await deletion.delete_organization(
            db_session, organization_id=org, confirmation=uuid.uuid4(), reason="закриття"
        )
    assert await db_session.get(Organization, org) is not None


@pytest.mark.asyncio
async def test_the_database_itself_blocks_a_casual_organization_delete(db_session):
    """RESTRICT на audits.organization_id — останній бар'єр.

    Випадковий `DELETE FROM organizations` не може забрати історію з
    собою: базі байдуже, з якого коду прийшов запит.
    """
    org = await _org(db_session, "barrier@example.com")
    await _audit(db_session, org)

    # pytest.raises зовні, savepoint усередині: виняток має пролетіти
    # крізь savepoint, щоб той відкотився. Навпаки — savepoint пробує
    # RELEASE на перерваній транзакції й ламає решту тесту.
    with pytest.raises(IntegrityError):
        async with db_session.begin_nested():
            await db_session.execute(
                sa_delete(Organization).where(Organization.id == org)
            )


# ── шляхи не перетинаються ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_retention_and_deletion_are_different_paths(db_session):
    """Чистка не вміє того, що вміє видалення, — і це перевіряється діями.

    Аудит, який чистка вже обробила до кінця, для видалення досі існує;
    а скільки б чистка не проходила, рядок після неї на місці.
    """
    org = await _org(db_session, "paths@example.com")
    audit_id = await _audit(db_session, org)
    audit = await db_session.get(Audit, audit_id)
    audit.finished_at = datetime.now(UTC) - timedelta(days=5000)
    await db_session.flush()

    for _ in range(2):
        await retention.purge_expired(db_session)
    assert await db_session.get(Audit, audit_id) is not None, "чистка запис не чіпає"

    await deletion.delete_audit(
        db_session, audit_id=audit_id, organization_id=org, reason="а видалення — так"
    )
    assert await db_session.get(Audit, audit_id) is None
