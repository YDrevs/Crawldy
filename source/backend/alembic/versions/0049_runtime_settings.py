"""Робочі налаштування адміністратора: ключ → значення, секрети шифровані.

Таблиця для сторінок «Платіжний провайдер» і «AI-моделі» службового
кабінету. Значення з оточення НЕ переносяться: вони лишаються фолбеком,
тож установлення, яке працювало на змінних оточення, після міграції
працює так само, а таблиця порожня доти, доки адміністратор не збереже
щось сам.

Revision ID: 0049
Revises: 0048
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0049"
down_revision = "0048"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column(
            "is_secret", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_by", UUID(as_uuid=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("runtime_settings")
