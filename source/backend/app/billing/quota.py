"""Квота: скільки ще можна, і атомарне списання.

Один інваріант, названий вголос: **квота списується при створенні
аудиту.** Не при старті й не при завершенні.

Списання на старті лишає вікно між постановкою в чергу й підняттям
воркера, у яке пролазить довільна кількість запитів. Списання на
завершенні дозволяє запустити тисячу аудитів одночасно й розібратися
потім. Обидва варіанти виглядають справедливішими до клієнта й обидва
ламаються під навантаженням.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Subscription

AUDITS = "audits"


@dataclass(frozen=True, slots=True)
class Period:
    """Період, у якому рахується споживання.

    Прив'язаний до періоду підписки, а не до календарного місяця:
    клієнт, який оплатив 15-го, очікує свій ліміт з 15-го. Для
    безкоштовного тарифу підписки немає, і тоді період календарний —
    це найлегша річ переплутати, тому вона написана тут явно.
    """

    start: datetime
    end: datetime
    source: str  # "subscription" | "calendar"


@dataclass(frozen=True, slots=True)
class QuotaDecision:
    """Відповідь на «чи можна ще».

    `reason` — ключ для i18n, а не готовий текст: шар API не має
    вирішувати, якою мовою розмовляє клієнт.
    """

    allowed: bool
    used: int
    limit: int | None
    reason: str | None = None

    @property
    def remaining(self) -> int | None:
        return None if self.limit is None else max(0, self.limit - self.used)


def _now() -> datetime:
    return datetime.now(UTC)


def _calendar_month(moment: datetime) -> Period:
    start = moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = (
        start.replace(year=start.year + 1, month=1)
        if start.month == 12
        else start.replace(month=start.month + 1)
    )
    return Period(start=start, end=end, source="calendar")


def period_for(subscription: Subscription | None, *, at: datetime | None = None) -> Period:
    moment = at or _now()
    if (
        subscription is not None
        and subscription.current_period_start is not None
        and subscription.current_period_end is not None
        and subscription.current_period_start <= moment < subscription.current_period_end
    ):
        return Period(
            start=subscription.current_period_start,
            end=subscription.current_period_end,
            source="subscription",
        )
    return _calendar_month(moment)


# Одне речення, у якому живе весь захист від гонки.
#
# Читання перед записом тут неможливе за побудовою: умова `used < :limit`
# перевіряється тим самим оператором, який збільшує лічильник. Два
# паралельні запити при одному залишку дають рівно одне списання —
# другий не побачить рядка в RETURNING.
_CONSUME = text(
    """
    INSERT INTO usage_counters
        (id, organization_id, metric, period_start, period_end, used, created_at, updated_at)
    VALUES (gen_random_uuid(), :org, :metric, :start, :end, 1, now(), now())
    ON CONFLICT (organization_id, period_start, metric)
    DO UPDATE SET used = usage_counters.used + 1, updated_at = now()
    WHERE usage_counters.used < :limit
    RETURNING used
    """
)

# Те саме без ліміту: тариф без обмеження все одно рахує споживання —
# інакше «скільки аудитів було в травні» немає з чого відповісти.
_CONSUME_UNLIMITED = text(
    """
    INSERT INTO usage_counters
        (id, organization_id, metric, period_start, period_end, used, created_at, updated_at)
    VALUES (gen_random_uuid(), :org, :metric, :start, :end, 1, now(), now())
    ON CONFLICT (organization_id, period_start, metric)
    DO UPDATE SET used = usage_counters.used + 1, updated_at = now()
    RETURNING used
    """
)

_PEEK = text(
    """
    SELECT used FROM usage_counters
     WHERE organization_id = :org AND metric = :metric AND period_start = :start
    """
)

_RELEASE = text(
    """
    UPDATE usage_counters SET used = GREATEST(used - 1, 0), updated_at = now()
     WHERE organization_id = :org AND metric = :metric AND period_start = :start
    RETURNING used
    """
)


async def used_in(
    db: AsyncSession, *, organization_id: uuid.UUID, period: Period, metric: str = AUDITS
) -> int:
    row = await db.execute(
        _PEEK, {"org": organization_id, "metric": metric, "start": period.start}
    )
    return int(row.scalar_one_or_none() or 0)


async def consume(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    period: Period,
    limit: int | None,
    metric: str = AUDITS,
) -> QuotaDecision:
    """Списати одиницю або відмовити. Атомарно, одним запитом.

    Порожній результат означає «ліміт вичерпано»: рядок не оновився, бо
    умова `used < limit` не виконалась.
    """
    if limit is not None and limit <= 0:
        return QuotaDecision(allowed=False, used=0, limit=limit, reason="quota.not_included")

    statement = _CONSUME_UNLIMITED if limit is None else _CONSUME
    params: dict[str, object] = {
        "org": organization_id,
        "metric": metric,
        "start": period.start,
        "end": period.end,
    }
    if limit is not None:
        params["limit"] = limit

    row = await db.execute(statement, params)
    used = row.scalar_one_or_none()
    if used is None:
        current = await used_in(db, organization_id=organization_id, period=period, metric=metric)
        return QuotaDecision(
            allowed=False, used=current, limit=limit, reason="quota.exhausted"
        )
    return QuotaDecision(allowed=True, used=int(used), limit=limit)


async def release(
    db: AsyncSession, *, organization_id: uuid.UUID, period: Period, metric: str = AUDITS
) -> None:
    """Повернути списану одиницю.

    Викликається лише тоді, коли аудит не виконався з **нашої** причини:
    не вдалося поставити в чергу, внутрішня помилка, скасування до
    старту.

    Не повертається, якщо причина зовнішня — сайт не відповів, віддав
    403, зламаний сертифікат. Ми виконали роботу й відповіли чесно;
    повертати за це означає платити за чужу поломку.
    """
    await db.execute(_RELEASE, {"org": organization_id, "metric": metric, "start": period.start})
