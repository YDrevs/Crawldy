"""audit_targets: один аудит → N цілей

Revision ID: 0003
Revises: 0002

Аудит стає контейнером, ціль — тим, що раніше було аудитом: свій краул,
свої issues, свій скор. Поля url/origin/status/scores на audits лишаються
як «первинна ціль», щоб наявні клієнти API не зламалися; score_overall
там стає зведеним.

audit_id на pages/issues лишається денормалізованим: на ньому висять
індекси ix_audit_issues_filter і ix_audit_pages_audit_url, і всі наявні
запити ходять саме через нього.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

AUDIT_STATUS = sa.Enum(
    "queued", "running", "completed", "partial", "failed",
    name="audit_status", native_enum=False, create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "audit_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("origin", sa.Text(), nullable=False),
        sa.Column("status", AUDIT_STATUS, nullable=False),
        sa.Column("score_overall", sa.SmallInteger(), nullable=True),
        sa.Column("scores", postgresql.JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("degraded", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("skipped_modules", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("audit_id", "url", name="uq_audit_targets_audit_url"),
    )
    op.create_index("ix_audit_targets_audit_id", "audit_targets", ["audit_id"])

    # Кожен наявний аудит стає аудитом з однією ціллю. id цілі беремо рівним
    # id аудиту: так бекфіл pages/issues не потребує другого проходу.
    op.execute(
        """
        INSERT INTO audit_targets (
            id, audit_id, position, url, origin, status, score_overall, scores,
            error, degraded, skipped_modules, evidence, started_at, finished_at
        )
        SELECT id, id, 0, url, origin, status, score_overall, scores,
               error, degraded, skipped_modules, evidence, started_at, finished_at
        FROM audits
        """
    )

    for table in ("audit_pages", "audit_issues"):
        op.add_column(
            table, sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True)
        )
        op.execute(f"UPDATE {table} SET target_id = audit_id WHERE target_id IS NULL")
        op.alter_column(table, "target_id", nullable=False)
        op.create_foreign_key(
            f"{table}_target_id_fkey", table, "audit_targets",
            ["target_id"], ["id"], ondelete="CASCADE",
        )
        op.create_index(f"ix_{table}_target_id", table, ["target_id"])


def downgrade() -> None:
    for table in ("audit_pages", "audit_issues"):
        op.drop_index(f"ix_{table}_target_id", table_name=table)
        op.drop_constraint(f"{table}_target_id_fkey", table, type_="foreignkey")
        op.drop_column(table, "target_id")
    op.drop_index("ix_audit_targets_audit_id", table_name="audit_targets")
    op.drop_table("audit_targets")
