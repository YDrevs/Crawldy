"""presence: ширший статус спостереження під budget_cost_bound_unavailable

Revision ID: 0042
Revises: 0041
Create Date: 2026-09-01
"""
import sqlalchemy as sa

from alembic import op

revision = '0042'
down_revision = '0041'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        'presence_observations', 'status',
        existing_type=sa.String(24), type_=sa.String(40),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'presence_observations', 'status',
        existing_type=sa.String(40), type_=sa.String(24),
        existing_nullable=False,
    )
