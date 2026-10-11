"""report_links: публічні посилання на звіт

Revision ID: 0004
Revises: 0003

Токен зберігаємо як SHA-256, а не відкритим текстом: дамп бази або
випадковий SELECT не має роздавати робочі посилання на чужі звіти.
Порівняння йде по хешу, тож індекс на ньому й унікальний.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "report_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_targets.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("lang", sa.String(8), nullable=False, server_default="uk"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("views", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_report_links_token_hash", "report_links", ["token_hash"], unique=True)
    op.create_index("ix_report_links_audit_id", "report_links", ["audit_id"])


def downgrade() -> None:
    op.drop_index("ix_report_links_audit_id", table_name="report_links")
    op.drop_index("ix_report_links_token_hash", table_name="report_links")
    op.drop_table("report_links")
