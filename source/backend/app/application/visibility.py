"""Що клієнт бачить — на відміну від того, що ми зберігаємо.

`history_retention_days` у правах тарифу — це вікно видимості історії, а
не строк життя даних. Різниця принципова, і на ній тримається безпечність
пониження тарифу: приховане повертається наступним апгрейдом, знищене —
ні. Скільки даних *існує*, вирішує `retention_policy`; скільки з них
*показати* — це право тарифу, і рахується воно тут.

Звідси й місце: це не запит до бази (шар сервісів) і не правило зберігання
(політика строків), а продуктова умова на читання. Обидва маршрути
історії питають одне й те саме, і відповідь мусить бути однією функцією —
інакше вікна двох маршрутів розійдуться при першій зміні.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.billing import service as billing


@dataclass(frozen=True, slots=True)
class HistoryWindow:
    """Вікно видимості історії для однієї організації.

    `days` лишається в відповіді API: інтерфейс мусить сказати «показано
    останні N днів», інакше обрізана крива читається як «раніше аудитів
    не було» — а це неправда, і неправда образлива, бо аудити є.
    """

    days: int | None
    since: datetime | None

    @property
    def unlimited(self) -> bool:
        return self.since is None


async def history_window(
    db: AsyncSession, *, organization_id: uuid.UUID, now: datetime | None = None
) -> HistoryWindow:
    """Вікно за правами тарифу. `None` у праві — показувати все."""
    resolved = await billing.for_organization(db, organization_id=organization_id)
    days = resolved.limit("history_retention_days")
    if days is None:
        return HistoryWindow(days=None, since=None)
    moment = now or datetime.now(UTC)
    return HistoryWindow(days=int(days), since=moment - timedelta(days=int(days)))


__all__ = ["HistoryWindow", "history_window"]
