"""Разові кредити: резерв, списання, повернення, відкликання.

## Кожен перехід — один умовний UPDATE

Не «прочитати, вирішити, записати». Читання з подальшим записом дає
вікно, у яке проходить другий запит, і два аудити витрачають один
кредит. Тому стан перевіряється в тому самому операторі, який його
міняє: другий запит не знайде рядка в очікуваному стані й отримає
порожній результат.

## Імена, а не значення

У колонці лежить **імʼя** члена перерахування (`AVAILABLE`), бо саме так
SQLAlchemy зберігає Python-enum, і CHECK побудований на іменах. Сирий
SQL, написаний зі значень (`'available'`), не збігся б ніколи — і мовчки:
запит просто не оновлював би рядків, що виглядало б як «кредитів немає».
Ця пастка вже коштувала проєкту одного дефекту в ідемпотентності подій.

## Найстаріший кредит витрачається першим

`ORDER BY created_at` не косметика: кредити можуть бути відкликані при
поверненні коштів за покупку, і витрачати спершу найновіші означало б
залишати під відкликання саме те, що клієнт устиг оплатити давніше.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.enums import CreditState

# `FOR UPDATE SKIP LOCKED` у підзапиті: паралельні резерви беруть різні
# рядки замість того, щоб чекати один одного. Обхід межі рядка вгору
# неможливий — зовнішній UPDATE ще раз перевіряє стан.
_RESERVE = text(
    """
    UPDATE audit_credits
       SET state = 'RESERVED', audit_id = :audit, reserved_at = :now
     WHERE id = (
             SELECT id FROM audit_credits
              WHERE organization_id = :org AND state = 'AVAILABLE'
                AND credit_type = :ctype
              ORDER BY created_at
                FOR UPDATE SKIP LOCKED
              LIMIT 1
           )
       AND state = 'AVAILABLE'
    RETURNING id
    """
)

_CONSUME = text(
    """
    UPDATE audit_credits
       SET state = 'CONSUMED', consumed_at = :now
     WHERE audit_id = :audit AND state = 'RESERVED'
    RETURNING id
    """
)

# Повернення дивиться на покупку, з якої кредит походить. Якщо за неї
# вже повернули кошти, кредит не має воскреснути доступним: клієнт за
# нього більше не платить. Він завершує життя відкликаним, зберігаючи
# `audit_id` — щоб лишалося видно, під який аудит його займали.
_RELEASE = text(
    """
    UPDATE audit_credits AS c
       SET state = CASE WHEN p.status = 'REFUNDED' THEN 'REVOKED' ELSE 'AVAILABLE' END,
           audit_id = CASE WHEN p.status = 'REFUNDED' THEN c.audit_id ELSE NULL END,
           reserved_at = NULL,
           -- Явне приведення: у гілці ELSE стоїть NULL, і без нього
           -- PostgreSQL виводить тип параметра як text.
           revoked_at = CASE WHEN p.status = 'REFUNDED'
                             THEN CAST(:now AS timestamptz) ELSE NULL END
      FROM one_off_purchases AS p
     WHERE c.purchase_id = p.id
       AND c.audit_id = :audit
       AND c.state = 'RESERVED'
    RETURNING c.state
    """
)

_REVOKE_UNUSED = text(
    """
    UPDATE audit_credits
       SET state = 'REVOKED', revoked_at = :now
     WHERE purchase_id = :purchase AND state = 'AVAILABLE'
    RETURNING id
    """
)

_BALANCE = text(
    """
    SELECT count(*) FROM audit_credits
     WHERE organization_id = :org AND state = 'AVAILABLE'
       AND credit_type = :ctype
    """
)

_RESERVE_PRESENCE = text(
    """
    UPDATE audit_credits
       SET state = 'RESERVED', presence_run_id = :run, reserved_at = :now
     WHERE id = (
             SELECT id FROM audit_credits
              WHERE organization_id = :org AND state = 'AVAILABLE'
                AND credit_type = 'presence'
              ORDER BY created_at
                FOR UPDATE SKIP LOCKED
              LIMIT 1
           )
       AND state = 'AVAILABLE'
    RETURNING id
    """
)

_CONSUME_PRESENCE = text(
    """
    UPDATE audit_credits
       SET state = 'CONSUMED', consumed_at = :now
     WHERE presence_run_id = :run AND state = 'RESERVED'
    RETURNING id
    """
)

# Той самий закон, що й для аудитів: кредит повертається доступним, але
# якщо покупку тим часом повернули — стає відкликаним. Промо-гранти без
# покупки (purchase_id IS NULL) повертаються доступними завжди.
_RELEASE_PRESENCE = text(
    """
    UPDATE audit_credits AS c
       SET state = CASE WHEN p.status = 'REFUNDED' THEN 'REVOKED' ELSE 'AVAILABLE' END,
           presence_run_id = CASE WHEN p.status = 'REFUNDED'
                                  THEN c.presence_run_id ELSE NULL END,
           reserved_at = NULL,
           revoked_at = CASE WHEN p.status = 'REFUNDED'
                             THEN CAST(:now AS timestamptz) ELSE NULL END
      FROM one_off_purchases AS p
     WHERE c.purchase_id = p.id
       AND c.presence_run_id = :run
       AND c.state = 'RESERVED'
    RETURNING c.state
    """
)

_RELEASE_PRESENCE_GRANT = text(
    """
    UPDATE audit_credits
       SET state = 'AVAILABLE', presence_run_id = NULL, reserved_at = NULL
     WHERE presence_run_id = :run AND state = 'RESERVED' AND purchase_id IS NULL
    RETURNING id
    """
)

_RESERVED_FOR = text(
    """
    SELECT id FROM audit_credits
     WHERE audit_id = :audit AND state IN ('RESERVED', 'CONSUMED')
     LIMIT 1
    """
)


def _now() -> datetime:
    return datetime.now(UTC)


async def balance(
    db: AsyncSession, *, organization_id: uuid.UUID, credit_type: str = "audit"
) -> int:
    """Скільки одиниць цього типу доступно. Не рахує зарезервовані."""
    row = await db.execute(
        _BALANCE, {"org": organization_id, "ctype": credit_type}
    )
    return int(row.scalar_one())


async def reserve(
    db: AsyncSession, *, organization_id: uuid.UUID, audit_id: uuid.UUID
) -> uuid.UUID | None:
    """Зайняти один кредит під аудит. `None` — вільних немає.

    Атомарно: два одночасні аудити однієї організації візьмуть різні
    кредити або другий не отримає жодного, але ніколи — один і той самий.
    """
    row = await db.execute(
        _RESERVE,
        {"org": organization_id, "audit": audit_id, "now": _now(),
         "ctype": "audit"},
    )
    return row.scalar_one_or_none()


async def consume(db: AsyncSession, *, audit_id: uuid.UUID) -> bool:
    """Списати остаточно. Повторний виклик нічого не робить."""
    row = await db.execute(_CONSUME, {"audit": audit_id, "now": _now()})
    return row.scalar_one_or_none() is not None


async def release(db: AsyncSession, *, audit_id: uuid.UUID) -> CreditState | None:
    """Завершити резерв, повернувши **той самий** кредит.

    Не «додати одиницю до балансу»: кредит належить конкретній покупці,
    і саме тому повернення може закінчитися двома різними станами.

    Звичайний випадок — назад у доступні. Але якщо за покупку тим часом
    повернули кошти, кредит стає відкликаним: інакше аудит, що не вдався,
    воскрешав би оплату, якої вже немає. Проміжок між резервом і
    поверненням коштів невеликий, але існує, і на ньому клієнт отримав би
    безкоштовний аудит.

    Повертає новий стан або `None`, якщо повертати не було чого —
    резерву не існувало, або він уже завершений. Повтор задачі на цьому
    зупиняється сам.
    """
    row = await db.execute(_RELEASE, {"audit": audit_id, "now": _now()})
    state = row.scalar_one_or_none()
    # `CreditState[...]`, а не `CreditState(...)`: у колонці лежить **імʼя**
    # члена, і пошук за значенням тут не спрацював би. Та сама межа між
    # іменем і значенням, що й у сирому SQL вище, лише на рівень вище.
    return CreditState[state] if state is not None else None


async def revoke_unused(db: AsyncSession, *, purchase_id: uuid.UUID) -> int:
    """Відкликати невитрачені кредити покупки. Для повернення коштів.

    Витрачені не чіпаються: послугу було надано, і забирати її заднім
    числом означало б стерти аудит, за який клієнт уже отримав звіт.
    Зарезервовані теж не чіпаються — вони зараз виконуються, і їхню долю
    вирішить розрахунок аудиту: успіх спише кредит остаточно, невдача
    відкличе його, побачивши, що покупка вже повернена. Забирати їх тут
    означало б обірвати аудит, який клієнт уже запустив.
    """
    rows = await db.execute(_REVOKE_UNUSED, {"purchase": purchase_id, "now": _now()})
    return len(rows.fetchall())


async def reserve_presence(
    db: AsyncSession, *, organization_id: uuid.UUID, run_id: uuid.UUID
) -> uuid.UUID | None:
    """Зайняти одну перевірку присутності під прогін. `None` — немає."""
    row = await db.execute(
        _RESERVE_PRESENCE,
        {"org": organization_id, "run": run_id, "now": _now()},
    )
    return row.scalar_one_or_none()


async def consume_presence(db: AsyncSession, *, run_id: uuid.UUID) -> bool:
    """Списати перевірку присутності остаточно. Повтор — тиха но-оп."""
    row = await db.execute(_CONSUME_PRESENCE, {"run": run_id, "now": _now()})
    return row.scalar_one_or_none() is not None


async def release_presence(db: AsyncSession, *, run_id: uuid.UUID) -> bool:
    """Повернути зарезервовану перевірку присутності.

    Куплена — за законом покупки (повернена покупка відкликає);
    промо-грант повертається доступним завжди.
    """
    row = await db.execute(_RELEASE_PRESENCE, {"run": run_id, "now": _now()})
    if row.scalar_one_or_none() is not None:
        return True
    grant = await db.execute(_RELEASE_PRESENCE_GRANT, {"run": run_id})
    return grant.scalar_one_or_none() is not None


async def grant(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    credit_type: str,
    quantity: int,
    source: str,
    reason: str | None = None,
    granted_by: uuid.UUID | None = None,
    purchase_id: uuid.UUID | None = None,
) -> int:
    """Видати одиниці: покупка, промо чи адмінське рішення.

    Кожна одиниця — рядок зі своїм походженням; історія пояснює себе
    сама. Викликати ДЛЯ покупки можна лише зсередини переходу
    PENDING→PAID — ідемпотентність тримає сам перехід.
    """
    from app.models.purchase import AuditCredit

    for _ in range(quantity):
        db.add(AuditCredit(
            id=uuid.uuid4(),
            purchase_id=purchase_id,
            organization_id=organization_id,
            credit_type=credit_type,
            source=source,
            reason=reason,
            granted_by=granted_by,
        ))
    await db.flush()
    return quantity


async def credit_for(db: AsyncSession, *, audit_id: uuid.UUID) -> uuid.UUID | None:
    """Який саме кредит оплатив цей аудит. Для пояснення історії."""
    row = await db.execute(_RESERVED_FOR, {"audit": audit_id})
    return row.scalar_one_or_none()


__all__ = [
    "CreditState",
    "balance",
    "consume",
    "consume_presence",
    "credit_for",
    "grant",
    "release",
    "release_presence",
    "reserve",
    "reserve_presence",
    "revoke_unused",
]
