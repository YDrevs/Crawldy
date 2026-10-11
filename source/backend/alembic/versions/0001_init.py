"""init audit tables

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

AUDIT_STATUS = sa.Enum(
    "queued", "running", "completed", "partial", "failed",
    name="audit_status", native_enum=False,
)
MODULE = sa.Enum(
    "performance", "seo", "ai_ready", "llm_visibility", name="issue_module", native_enum=False
)
SEVERITY = sa.Enum(
    "critical", "high", "medium", "low", "info", name="issue_severity", native_enum=False
)


def upgrade() -> None:
    op.create_table(
        "audits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("status", AUDIT_STATUS, nullable=False),
        sa.Column("options", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("score_overall", sa.SmallInteger(), nullable=True),
        sa.Column("scores", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_audits_status", "audits", ["status"])
    op.create_index("ix_audits_created_at", "audits", ["created_at"])

    op.create_table(
        "audit_pages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("content_type", sa.String(128), nullable=True),
        sa.Column("html_bytes", sa.Integer(), nullable=True),
        sa.Column("response_ms", sa.Integer(), nullable=True),
        sa.Column("depth", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("raw", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_audit_pages_audit_id", "audit_pages", ["audit_id"])
    op.create_index("ix_audit_pages_audit_url", "audit_pages", ["audit_id", "url"])

    op.create_table(
        "audit_issues",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "page_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_pages.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("module", MODULE, nullable=False),
        sa.Column("code", sa.String(96), nullable=False),
        sa.Column("severity", SEVERITY, nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("recommendation", sa.Text(), nullable=False, server_default=""),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("weight", sa.SmallInteger(), nullable=False, server_default="1"),
    )
    op.create_index("ix_audit_issues_audit_id", "audit_issues", ["audit_id"])
    op.create_index("ix_audit_issues_filter", "audit_issues", ["audit_id", "module", "severity"])


def downgrade() -> None:
    op.drop_table("audit_issues")
    op.drop_table("audit_pages")
    op.drop_table("audits")
