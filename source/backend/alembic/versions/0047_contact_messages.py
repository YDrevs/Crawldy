"""Звернення з публічної контактної форми.

Таблиця зберігає звернення ДО спроби доставки: лист може не піти, а
повідомлення людини губитися не має. `request_key` унікальний — саме він
робить повтор натискання чи мережевий ретрай ідемпотентним, і вирішує це
база, а не сподівання на обробник.

Revision ID: 0047
Revises: 0046
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0047"
down_revision = "0046"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contact_messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("site_url", sa.String(length=2048), nullable=False, server_default=""),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("locale", sa.String(length=5), nullable=False, server_default="en"),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
        sa.Column("delivery_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("delivery_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.String(length=64), nullable=False, server_default=""),
        sa.Column("request_key", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("request_key", name="uq_contact_message_request"),
    )
    op.create_index("ix_contact_messages_email", "contact_messages", ["email"])
    op.create_index("ix_contact_messages_status", "contact_messages", ["status"])
    op.create_index("ix_contact_messages_created", "contact_messages", ["created_at"])
    op.create_index(
        "ix_contact_messages_request_key", "contact_messages", ["request_key"], unique=True
    )


def downgrade() -> None:
    op.drop_index("ix_contact_messages_request_key", table_name="contact_messages")
    op.drop_index("ix_contact_messages_created", table_name="contact_messages")
    op.drop_index("ix_contact_messages_status", table_name="contact_messages")
    op.drop_index("ix_contact_messages_email", table_name="contact_messages")
    op.drop_table("contact_messages")
