"""durable paid report link

Revision ID: 0032
Revises: 0031

Куплений звіт не має зникати разом із семиденною сесією гостя. Право
лежить у audit_unlocks; посилання — лише предʼявлення цього права, і
воно стає безстроковим: NULL в expires_at означає «закінчується
відкликанням, а не календарем». Вигаданий довгий строк був би тим самим
правдоподібним числом, якого проєкт уникає всюди.

unlock_id відрізняє платні посилання від поділених з кабінету:
повернення коштів відкликає перші, не зачіпаючи других.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("report_links", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=True)
    op.add_column(
        "report_links",
        sa.Column(
            "unlock_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("audit_unlocks.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_report_links_unlock_id", "report_links", ["unlock_id"])


def downgrade() -> None:
    op.drop_index("ix_report_links_unlock_id", table_name="report_links")
    op.drop_column("report_links", "unlock_id")
    # Безстрокові рядки при відкаті отримали б NOT NULL — ставимо їм
    # далекий строк не можна: вигаданого числа тут не буде. Відкат
    # можливий лише на порожніх безстрокових.
    op.alter_column("report_links", "expires_at", existing_type=sa.DateTime(timezone=True), nullable=False)
