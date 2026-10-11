"""issue_verdicts: що сказала людина про знахідку

Revision ID: 0007
Revises: 0006

Калібрування цього проєкту досі спиралося на гіпотезу про рівень сайту —
і тому розділення в середині діапазону нічим перевірити: немає з чим
звіряти. Вердикти дають те, з чим.

Головне тут — не сам факт відхилення, а його причина. «Не робитимемо» і
«такого немає» в інтерфейсах зазвичай зливаються в одну кнопку, і саме
через це відхилення нічого не варті як дані: незрозуміло, чек помилився
чи клієнт не хоче витрачатись. Проти чека свідчить лише `wrong`.

`code` і `msg` дублюються з issue навмисно: зведення по чеках має
пережити видалення аудиту, інакше дані про якість чека живуть рівно
стільки, скільки аудит, у якому їх зібрано.
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "issue_verdicts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "issue_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audit_issues.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "audit_id",
            UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(96), nullable=False),
        sa.Column("msg", sa.String(96), nullable=False, server_default=""),
        sa.Column(
            "verdict",
            sa.Enum(
                "agreed", "fixed", "wont_fix", "wrong", "unclear",
                name="issue_verdict", native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("author", sa.String(120), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("issue_id", name="uq_issue_verdicts_issue"),
    )
    op.create_index("ix_issue_verdicts_issue_id", "issue_verdicts", ["issue_id"])
    op.create_index("ix_issue_verdicts_audit_id", "issue_verdicts", ["audit_id"])
    op.create_index("ix_issue_verdicts_code", "issue_verdicts", ["code"])


def downgrade() -> None:
    op.drop_table("issue_verdicts")
