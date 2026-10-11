"""ai enrichment ledger

Revision ID: 0033
Revises: 0032

Журнал AI-збагачення: логічні прогони з ідемпотентною ідентичністю та
кожна фактична спроба провайдера — включно з невдалими, щоб fallback
було видно, а не здогадувано. AI-похідне живе у власних таблицях: у
core-записах аудиту провайдерського стану немає й не зʼявиться.

Унікальний індекс по (audit, задача, версії, хеш входу) — це правило
«повторне відкриття звіту не породжує повторний платний виклик»,
виражене схемою, а не дисципліною коду.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None

# Ті самі типи, що в моделях, а не «схожі»: `test_migrations` порівнює
# схему з метаданими й ловить розбіжність. VARCHAR замість Enum лишив би
# таблицю без CHECK-обмеження — тобто без єдиної гарантії, що в колонці
# статусу лежить статус.
TASK_TYPE = sa.Enum(
    "SITE_UNDERSTANDING",
    "ROOT_CAUSE_GROUPING",
    "REMEDIATION_PLAN",
    name="enrichment_task_type",
    native_enum=False,
)
STATUS = sa.Enum(
    "PENDING",
    "RUNNING",
    "COMPLETED",
    "UNAVAILABLE",
    "FAILED",
    name="enrichment_status",
    native_enum=False,
)


def upgrade() -> None:
    op.create_table(
        "enrichment_runs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audit_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", TASK_TYPE, nullable=False),
        sa.Column("task_version", sa.String(16), nullable=False),
        sa.Column("prompt_version", sa.String(16), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("routing_version", sa.String(16), nullable=False, server_default=""),
        sa.Column("locale", sa.String(8), nullable=False, server_default="en"),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("status", STATUS, nullable=False, server_default="PENDING"),
        sa.Column("result", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "audit_id",
            "task_type",
            "task_version",
            "prompt_version",
            "schema_version",
            "input_hash",
            name="uq_enrichment_identity",
        ),
    )
    op.create_index("ix_enrichment_runs_audit_id", "enrichment_runs", ["audit_id"])
    op.create_index(
        "ix_enrichment_runs_audit_task", "enrichment_runs", ["audit_id", "task_type"]
    )

    op.create_table(
        "enrichment_attempts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("enrichment_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.SmallInteger(), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("request_id", sa.String(128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("error_category", sa.String(32), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=True),
        sa.Column("output_tokens", sa.Integer(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Float(), nullable=True),
        sa.Column("pricing_version", sa.String(16), nullable=True),
        sa.UniqueConstraint("run_id", "number", name="uq_enrichment_attempt_number"),
    )
    op.create_index("ix_enrichment_attempts_run_id", "enrichment_attempts", ["run_id"])


def downgrade() -> None:
    op.drop_table("enrichment_attempts")
    op.drop_table("enrichment_runs")
