"""guest merge journal

Revision ID: 0031
Revises: 0030

Журнал злиття гостьової організації в наявну — і перелік перенесених
аудитів окремою таблицею, бо на ньому стоїть доступ: гостьова
спроможність після злиття мусить досі відкривати рівно ті аудити, які
були її, і це питання має відповідатися індексом, а не розбором JSON.

`audit_id` у переліку навмисно без FK: журнал — історичний запис, який
переживає видалення аудиту, про який говорить. Організації натомість
під RESTRICT з обох боків — вони не мають зникати з-під пояснення.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0031"
down_revision = "0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guest_merges",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "guest_organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "destination_organization_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "performed_by_user_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("audits_moved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purchases_moved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credits_moved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("site_map", JSONB(), nullable=False, server_default="[]"),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_guest_merges_guest_organization_id", "guest_merges", ["guest_organization_id"]
    )
    op.create_index(
        "ix_guest_merges_destination_organization_id",
        "guest_merges",
        ["destination_organization_id"],
    )

    op.create_table(
        "guest_merge_audits",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "merge_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("guest_merges.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("audit_id", sa.UUID(as_uuid=True), nullable=False),
        sa.UniqueConstraint("merge_id", "audit_id", name="uq_guest_merge_audit"),
    )
    op.create_index("ix_guest_merge_audits_merge_id", "guest_merge_audits", ["merge_id"])
    op.create_index("ix_guest_merge_audits_audit_id", "guest_merge_audits", ["audit_id"])


def downgrade() -> None:
    op.drop_index("ix_guest_merge_audits_audit_id", table_name="guest_merge_audits")
    op.drop_index("ix_guest_merge_audits_merge_id", table_name="guest_merge_audits")
    op.drop_table("guest_merge_audits")
    op.drop_index("ix_guest_merges_destination_organization_id", table_name="guest_merges")
    op.drop_index("ix_guest_merges_guest_organization_id", table_name="guest_merges")
    op.drop_table("guest_merges")
