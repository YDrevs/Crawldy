"""Чистка за строком: важке зникає, запис лишається.

Це **єдиний** із трьох способів позбутися даних, який працює сам, за
розкладом, без людини. Тому він найобережніший, і тому він фізично не
вміє видалити рядок `audits` — див. `NeverExpires` у політиці.

Два інші способи живуть у `deletion.py` навмисно окремо. Різниця не в
акуратності коду, а в тому, чиє це рішення:

| Спосіб | Хто вирішив | Що зникає | Запис аудиту |
|---|---|---|---|
| чистка за строком | продукт, автоматично | сирі дані, потім знахідки | **лишається** |
| видалення на запит | клієнт | усе про цей аудит | зникає |
| закриття акаунта | клієнт або ми | вся організація | зникає |

Класти їх в один модуль означало б, що одного дня хтось викличе не ту
функцію з job'а — і різниця між «почистили знімок» та «стерли рік
історії» звелася б до одного слова в назві.

Властивості, які тут навмисні:

**Ідемпотентність.** Повторний прохід по вже почищеному аудиту не робить
нічого: мітки `raw_purged_at` / `findings_purged_at` — умова відбору, а
не наслідок.

**Безпека при паралельних job'ах.** Кандидати беруться
`FOR UPDATE SKIP LOCKED`, як і розклади. Другий екземпляр не чекає на
першому й не бере тих самих рядків.

**Порційність.** Один прохід обмежений `batch`: чистка не має тримати
довгу транзакцію й блокувати запис нових аудитів.

**Спостережуваність.** Прохід повертає, що саме зробив, а не лише «ок».
Чистка, яка мовчки не працює, виявляється через рахунок за диск.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import retention_policy as policy
from app.billing import service as billing
from app.core.logging import log
from app.models.audit import Audit, AuditAttempt, AuditIssue, AuditPage, AuditTarget

# Скільки аудитів розглядати за один прохід.
#
# Обмеження не через продуктивність запиту, а через довжину транзакції:
# рядки, взяті `FOR UPDATE`, тримаються до коміту, і великий batch
# блокував би запис результатів аудитів, що виконуються просто зараз.
BATCH = 200


@dataclass(slots=True)
class PurgeReport:
    """Що зробив один прохід. Порожній звіт — теж відповідь."""

    considered: int = 0
    raw_purged: int = 0
    findings_purged: int = 0
    pages_deleted: int = 0
    issues_deleted: int = 0
    attempts_deleted: int = 0
    snapshots_cleared: int = 0
    organizations: set[uuid.UUID] = field(default_factory=set)
    # Найпізніший finished_at серед розглянутих — курсор для наступної
    # порції. Без нього прохід голодує: якщо голову черги (за
    # finished_at) займають старі аудити організації з подовженим
    # строком, кожна порція розглядала б ті самі рядки, нічого не робила
    # й зупиняла прохід — а придатні рядки позаду не дочекалися б ніколи.
    last_seen: datetime | None = None

    @property
    def did_anything(self) -> bool:
        return bool(self.raw_purged or self.findings_purged)

    def as_log(self) -> dict[str, int]:
        return {
            "considered": self.considered,
            "raw_purged": self.raw_purged,
            "findings_purged": self.findings_purged,
            "pages_deleted": self.pages_deleted,
            "issues_deleted": self.issues_deleted,
            "attempts_deleted": self.attempts_deleted,
            "organizations": len(self.organizations),
        }


# Кандидати: завершені аудити, старіші за найкоротший можливий строк, у
# яких почищено ще не все.
#
# Найкоротший продуктовий строк, а не строк організації: політика в
# кожної своя, і рахувати її треба після відбору. Порядок — від
# найстаріших, щоб ті, які справді підпадають, стояли на початку й
# порція не витрачалася на молодші.
_CANDIDATES = text(
    """
    SELECT id, finished_at FROM audits
     WHERE finished_at IS NOT NULL
       AND finished_at < :floor
       AND finished_at > :after
       AND (raw_purged_at IS NULL OR findings_purged_at IS NULL)
     ORDER BY finished_at
     FOR UPDATE SKIP LOCKED
     LIMIT :batch
    """
)

# Початок часу для першої порції: раніше за будь-який аудит.
_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _now() -> datetime:
    return datetime.now(UTC)


async def purge_expired(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    batch: int = BATCH,
    after: datetime | None = None,
) -> PurgeReport:
    """Одна порція чистки. Рядок `audits` не зникає ніколи.

    `after` — курсор із попередньої порції (`report.last_seen`): порція
    починається за ним, а не з голови черги. Розглянутий і непридатний
    рядок (подовжений строк організації) інакше розглядався б щопорції.
    """
    moment = now or _now()
    report = PurgeReport()

    floor = moment - timedelta(days=policy.RAW_FLOOR_DAYS)
    rows = await db.execute(
        _CANDIDATES, {"floor": floor, "after": after or _EPOCH, "batch": batch}
    )
    fetched = rows.fetchall()
    ids = [row[0] for row in fetched]
    if not ids:
        return report
    report.last_seen = max(row[1] for row in fetched)

    policies: dict[uuid.UUID, policy.RetentionPolicy] = {}
    for audit_id in ids:
        audit = await db.get(Audit, audit_id)
        if audit is None:
            continue
        report.considered += 1
        rules = policies.get(audit.organization_id)
        if rules is None:
            rules = await _policy_for(db, audit.organization_id)
            policies[audit.organization_id] = rules
        await _apply(db, audit, rules, moment, report)

    await db.flush()
    if report.did_anything:
        log.info("retention_purged", **report.as_log())
    return report


async def _policy_for(db: AsyncSession, organization_id: uuid.UUID) -> policy.RetentionPolicy:
    resolved = await billing.for_organization(db, organization_id=organization_id)
    return policy.resolve(dict(resolved.values))


async def _apply(
    db: AsyncSession,
    audit: Audit,
    rules: policy.RetentionPolicy,
    now: datetime,
    report: PurgeReport,
) -> None:
    finished = audit.finished_at
    if finished is None:
        return

    before = (report.raw_purged, report.findings_purged)

    raw_cutoff = rules.cutoff(policy.DataClass.RAW, now=now)
    if audit.raw_purged_at is None and raw_cutoff is not None and finished < raw_cutoff:
        await _purge_raw(db, audit, now, report)

    found_cutoff = rules.cutoff(policy.DataClass.FINDINGS, now=now)
    if audit.findings_purged_at is None and found_cutoff is not None and finished < found_cutoff:
        await _purge_findings(db, audit, now, report)

    if (report.raw_purged, report.findings_purged) != before:
        report.organizations.add(audit.organization_id)


async def _purge_raw(
    db: AsyncSession, audit: Audit, now: datetime, report: PurgeReport
) -> None:
    """Сторінки й знімки. Після цього аудит не перерахувати, але прочитати — так.

    Спершу знахідки відчіплюються від сторінок. `audit_issues.page_id`
    має `ondelete=CASCADE` — правильний для видалення *аудиту*, але тут
    він означав би, що чистка сирого шару мовчки зносить знахідки: рівно
    той каскад з дешевого класу даних в історичний, якого цей модуль
    існує щоб не допустити. Адреса сторінки при цьому не губиться — вона
    від початку лежить у `evidence.page_url` кожної знахідки.
    """
    await db.execute(
        update(AuditIssue).where(AuditIssue.audit_id == audit.id).values(page_id=None)
    )
    pages = await db.execute(delete(AuditPage).where(AuditPage.audit_id == audit.id))
    report.pages_deleted += pages.rowcount or 0

    targets = (
        (await db.execute(select(AuditTarget).where(AuditTarget.audit_id == audit.id)))
        .scalars()
        .all()
    )
    for target in targets:
        if target.snapshot:
            target.snapshot = {}
            report.snapshots_cleared += 1

    audit.raw_purged_at = now
    report.raw_purged += 1


async def _purge_findings(
    db: AsyncSession, audit: Audit, now: datetime, report: PurgeReport
) -> None:
    """Знахідки й журнал спроб. Зведення в записі лишається.

    Порядок важливий: `audit_issues` посилається на `audit_pages`, тож
    сторінки мусять піти першими або разом. У чистці за строком це
    гарантовано — сирі дані мають коротший строк, — але аудит із
    подовженим строком сирих даних міг би прийти сюди зі сторінками на
    місці. Тому видаляємо явно, а не покладаємось на порядок класів.
    """
    if audit.raw_purged_at is None:
        await _purge_raw(db, audit, now, report)

    issues = await db.execute(delete(AuditIssue).where(AuditIssue.audit_id == audit.id))
    report.issues_deleted += issues.rowcount or 0
    attempts = await db.execute(delete(AuditAttempt).where(AuditAttempt.audit_id == audit.id))
    report.attempts_deleted += attempts.rowcount or 0

    audit.findings_purged_at = now
    report.findings_purged += 1


__all__ = ["BATCH", "PurgeReport", "purge_expired"]
