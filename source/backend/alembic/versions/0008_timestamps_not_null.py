"""created_at/updated_at: привести базу у відповідність до моделі

Revision ID: 0008
Revises: 0007

`alembic check` на живій базі показав розбіжність: у моделях ці колонки
оголошені без `nullable=True`, тобто NOT NULL, а в таблицях вони
nullable. Розбіжність стара — тягнеться з міграції 0001, — і сама собою
нічого не ламала, бо `server_default=now()` однаково заповнює значення.

Але поки модель і схема розходяться, `alembic check` завжди червоний, а
отже, не може попередити про справжню розбіжність. Інструмент, який
завжди сигналить, не сигналить ні про що.

Рядок без часу створення не має сенсу; значення проставляє сервер, тож
NOT NULL — це те, що ми й мали на увазі. Порожні значення (яких бути не
може, але перевірити дешево) заповнюємо перед зміною.
"""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Таблиця → колонки, які мають бути NOT NULL.
COLUMNS = {
    "audits": ("created_at",),
    "report_links": ("created_at",),
    "issue_verdicts": ("created_at", "updated_at"),
}


def upgrade() -> None:
    for table, columns in COLUMNS.items():
        for column in columns:
            op.execute(
                f"UPDATE {table} SET {column} = now() WHERE {column} IS NULL"
            )
            op.alter_column(
                table, column, existing_type=sa.DateTime(timezone=True), nullable=False
            )


def downgrade() -> None:
    for table, columns in COLUMNS.items():
        for column in columns:
            op.alter_column(
                table, column, existing_type=sa.DateTime(timezone=True), nullable=True
            )
