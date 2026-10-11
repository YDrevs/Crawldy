"""Видалення на запит: коли зникає сам запис.

Окремий модуль від `retention.py` навмисно, і це не питання охайності.
Три способи позбутися даних мають різні життєві цикли, різних
відповідальних і різні наслідки:

| | чистка за строком | видалення аудиту | закриття акаунта |
|---|---|---|---|
| хто вирішує | продукт, автоматично | клієнт | клієнт або ми |
| що зникає | сирі дані, потім знахідки | усе про один аудит | уся організація |
| запис `audits` | **лишається** | зникає | зникає |
| оборотність | історія читається далі | ні | ні |
| викликається з job'а | так | **ні** | **ні** |

Спільний модуль означав би, що одного дня хтось візьме з job'а не ту
функцію, і різниця між «почистили знімок» та «стерли рік історії»
зведеться до одного слова в назві. Тому чистка фізично не вміє видалити
рядок `audits` (`NeverExpires` у політиці), а ці дві функції вимагають
причини й підтвердження — їх неможливо викликати «за замовчуванням».

Чого видалення **не** робить у жодному з двох випадків: не чіпає лічильники
використання. Аудит був виконаний, квота була списана, місяць був
оплачений — видалення результату не скасовує роботи, яку ми зробили. Інакше
повернення грошей влаштовувалося б кнопкою «видалити».
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import log
from app.models.audit import Audit
from app.models.identity import Organization
from app.models.scheduling import AuditSchedule
from app.models.sites import Site


class DeletionRefused(Exception):
    """Видалення не відбулося, і це рішення, а не збій."""


@dataclass(frozen=True, slots=True)
class Deleted:
    """Що саме зникло. Для журналу й для відповіді клієнту."""

    audits: int = 0
    sites: int = 0
    schedules: int = 0


async def delete_audit(
    db: AsyncSession,
    *,
    audit_id: uuid.UUID,
    organization_id: uuid.UUID,
    reason: str,
    requested_by_user_id: uuid.UUID | None = None,
) -> bool:
    """Прибрати один аудит на запит клієнта. Разом із записом.

    `organization_id` обов'язковий і звужує запит, а не перевіряється
    після: чужий аудит для цієї функції не існує, і помилитися в
    порядку перевірок неможливо.

    `reason` теж обов'язковий. Не для формальності: через рік єдиним
    поясненням діри в історії буде рядок у журналі, і «видалено» без
    причини нічого не пояснює.
    """
    if not reason.strip():
        raise DeletionRefused("видалення без причини не робимо")

    audit = (
        await db.execute(
            select(Audit).where(Audit.id == audit_id, Audit.organization_id == organization_id)
        )
    ).scalar_one_or_none()
    if audit is None:
        return False

    log.info(
        "audit_deleted_by_request",
        audit_id=str(audit_id),
        organization_id=str(organization_id),
        by=str(requested_by_user_id) if requested_by_user_id else None,
        origin=audit.origin,
        finished_at=audit.finished_at.isoformat() if audit.finished_at else None,
        reason=reason[:500],
    )
    await db.delete(audit)
    await db.flush()
    return True


async def delete_organization(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    confirmation: uuid.UUID,
    reason: str,
) -> Deleted:
    """Закрити акаунт: організація і все, що їй належить.

    `confirmation` мусить дорівнювати `organization_id`. Це не захист від
    зловмисника — той підставить будь-що. Це захист від виклику з
    неправильним аргументом: змінна, яку передали помилково, збігом не
    дорівнює тій, яку треба.

    Аудити видаляються явно, а не каскадом: `audits.organization_id` має
    `ondelete=RESTRICT` саме для того, щоб закриття акаунта не могло
    статися випадковим `DELETE FROM organizations`. Знімати RESTRICT
    заради зручності цієї функції означало б зняти єдиний бар'єр, який у
    базі є.
    """
    if confirmation != organization_id:
        raise DeletionRefused("підтвердження не збігається з організацією")
    if not reason.strip():
        raise DeletionRefused("закриття акаунта без причини не робимо")

    organization = await db.get(Organization, organization_id)
    if organization is None:
        raise DeletionRefused("організації не існує")

    counted = Deleted(
        audits=await _count(db, Audit, organization_id),
        sites=await _count(db, Site, organization_id),
        schedules=await _count(db, AuditSchedule, organization_id),
    )
    log.warning(
        "organization_deleted",
        organization_id=str(organization_id),
        audits=counted.audits,
        sites=counted.sites,
        schedules=counted.schedules,
        reason=reason[:500],
    )

    # Порядок: спершу те, що тримає RESTRICT, потім сама організація.
    # Решта (сесії, ключі, підписки, лічильники, розклади, сайти) піде
    # каскадом — там ondelete=CASCADE стоїть свідомо.
    await db.execute(delete(Audit).where(Audit.organization_id == organization_id))
    await db.delete(organization)
    await db.flush()
    return counted


async def _count(db: AsyncSession, model: type, organization_id: uuid.UUID) -> int:
    stmt = select(func.count()).select_from(model).where(
        model.organization_id == organization_id  # type: ignore[attr-defined]
    )
    return int((await db.execute(stmt)).scalar_one())


__all__ = ["Deleted", "DeletionRefused", "delete_audit", "delete_organization"]
