"""Одноразові посилання на встановлення нового пароля.

Таблиця, а не колонка в `users`. Причина не в нормалізації: колонка
дозволила б рівно один токен і не лишила б сліду, коли людина замовила
лист двічі, а розслідування «хто і коли скидав пароль» саме з цього
сліду й починається.

У базі лежить ЛИШЕ хеш токена, як у `sessions` і `api_keys`. Дамп бази
не дає можливості скинути чужий пароль.

Одноразовість забезпечує часткова UNIQUE-умова, а не код: два одночасні
запити на відновлення інакше створили б два чинні посилання, і старий
лист лишався б ключем від акаунта. Перевірка в Python цієї гонки не
ловить — БД ловить.

Нічого наявного не змінюється: жодної колонки, жодного індексу, жодного
рядка в інших таблицях. Тому `downgrade` — просто видалення таблиці.

Revision ID: 0054
Revises: 0053
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0054"
down_revision = "0053"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_resets",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_password_resets_user_id", "password_resets", ["user_id"])
    op.create_index(
        "ix_password_resets_token_hash", "password_resets", ["token_hash"], unique=True
    )
    # Один ЖИВИЙ токен на людину. Умова часткова: використані й скасовані
    # рядки лишаються назавжди — вони і є той слід, заради якого таблиця.
    op.create_index(
        "ux_password_resets_active_user",
        "password_resets",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("used_at IS NULL AND superseded_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ux_password_resets_active_user", table_name="password_resets")
    op.drop_index("ix_password_resets_token_hash", table_name="password_resets")
    op.drop_index("ix_password_resets_user_id", table_name="password_resets")
    op.drop_table("password_resets")
