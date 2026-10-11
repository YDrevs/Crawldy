"""Стан покинутої каси: місце під довше значення статусу.

`PurchaseStatus` отримав `ABANDONED` — каса, за яку не заплатили і яку
службовий екран гасить, щоб перелік незарахованих не заростав. Стан
оборотний: оплата, що прийде пізніше, оживляє покупку.

Колонка була `varchar(8)` — рівно під найдовше з наявних значень
(`REFUNDED`). Нове довше на символ, тож без цієї міграції гасіння падає
на рівні бази.

Revision ID: 0052
Revises: 0051
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0052"
down_revision = "0051"
branch_labels = None
depends_on = None


# Той самий тип, що оголошує модель: інакше автогенерація бачить
# розбіжність між `VARCHAR(n)` міграції та `Enum(...)` моделі, і тест
# «моделі не розійшлися з міграціями» падає на кожному прогоні.
_STATUS = sa.Enum(
    "PENDING", "PAID", "ABANDONED", "REFUNDED",
    name="purchase_status",
    native_enum=False,
)


def upgrade() -> None:
    op.alter_column(
        "one_off_purchases",
        "status",
        existing_type=sa.String(length=8),
        type_=_STATUS,
        existing_nullable=False,
    )


def downgrade() -> None:
    # Назад лише тоді, коли покинутих кас немає: інакше значення не влізе.
    op.execute(
        "UPDATE one_off_purchases SET status = 'PENDING' WHERE status = 'ABANDONED'"
    )
    op.alter_column(
        "one_off_purchases",
        "status",
        existing_type=_STATUS,
        type_=sa.String(length=8),
        existing_nullable=False,
    )
