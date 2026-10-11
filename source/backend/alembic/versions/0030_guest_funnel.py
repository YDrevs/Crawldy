"""guest funnel: guest sessions, audit unlocks, organization kind

Revision ID: 0030
Revises: 0029

Анонімна воронка не робить власника необовʼязковим. Власником лишається
організація — просто без учасників, поки людини немає. Тому в цій
міграції немає жодного `nullable=True` на `organization_id`: усі чотири
зміни адитивні, і жоден наявний запит не отримує другої гілки.

## `organizations.kind`

Дефолт `TEAM`, і одразу після створення колонки — заповнення наявних
рядків із `is_personal`. Прапорець лишається: він відповідає на інше
питання («створена разом із людиною»), і гостьова організація на ньому
виглядала б особистою.

Значення пишуться **іменами** членів, не значеннями: колонка оголошена
як `Enum(..., native_enum=False)`, тобто SQLAlchemy кладе туди
`PERSONAL`, а CHECK перевіряє саме імена. Це вже коштувало двох
міграцій у білінгу — `server_default` зі значенням не проходив CHECK,
який оголошує та сама колонка.

## Строк спроможності коротший за строк аудиту

`guest_sessions.expires_at` не має нічого спільного зі зберіганням
аудиту. Прострочена сесія перестає бути ключем, але не знищує куплене:
той, хто заплатив, отримує власне посилання на звіт.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None

KINDS = ("PERSONAL", "TEAM", "GUEST", "CLAIMED")


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "kind",
            sa.Enum(*KINDS, name="organization_kind", native_enum=False),
            nullable=False,
            server_default="TEAM",
        ),
    )
    # Наявні рядки: особистий простір лишається особистим, решта — команда.
    op.execute("UPDATE organizations SET kind = 'PERSONAL' WHERE is_personal = true")
    op.create_index("ix_organizations_kind", "organizations", ["kind"])

    op.create_table(
        "guest_sessions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip_hash", sa.String(64), nullable=False, server_default=""),
    )
    op.create_index("ix_guest_sessions_organization_id", "guest_sessions", ["organization_id"])
    op.create_index("ix_guest_sessions_token_hash", "guest_sessions", ["token_hash"], unique=True)
    op.create_index("ix_guest_sessions_expires", "guest_sessions", ["expires_at"])

    op.create_table(
        "audit_unlocks",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audit_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "purchase_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("one_off_purchases.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "granted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("audit_id", name="uq_audit_unlock_audit"),
    )
    op.create_index("ix_audit_unlocks_audit_id", "audit_unlocks", ["audit_id"], unique=True)
    op.create_index("ix_audit_unlocks_purchase_id", "audit_unlocks", ["purchase_id"])

    op.add_column(
        "one_off_purchases",
        sa.Column(
            "audit_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_one_off_purchases_audit_id", "one_off_purchases", ["audit_id"])


def downgrade() -> None:
    op.drop_index("ix_one_off_purchases_audit_id", table_name="one_off_purchases")
    op.drop_column("one_off_purchases", "audit_id")
    op.drop_index("ix_audit_unlocks_purchase_id", table_name="audit_unlocks")
    op.drop_index("ix_audit_unlocks_audit_id", table_name="audit_unlocks")
    op.drop_table("audit_unlocks")
    op.drop_index("ix_guest_sessions_expires", table_name="guest_sessions")
    op.drop_index("ix_guest_sessions_token_hash", table_name="guest_sessions")
    op.drop_index("ix_guest_sessions_organization_id", table_name="guest_sessions")
    op.drop_table("guest_sessions")
    op.drop_index("ix_organizations_kind", table_name="organizations")
    op.drop_column("organizations", "kind")
