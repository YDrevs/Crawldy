"""presence: довговічна книга платних спроб (резервації бюджету)

Revision ID: 0043
Revises: 0042
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '0043'
down_revision = '0042'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'presence_attempts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('run_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('presence_runs.id', ondelete='CASCADE'),
                  nullable=False, index=True),
        sa.Column('provider', sa.String(32), nullable=False),
        sa.Column('prompt_id', sa.String(64), nullable=False),
        sa.Column('mode', sa.String(16), nullable=False),
        sa.Column('run_index', sa.SmallInteger(), nullable=False),
        sa.Column('attempt_no', sa.SmallInteger(), nullable=False),
        sa.Column('state', sa.String(24), nullable=False),
        sa.Column('reserved_max_usd', sa.Numeric(12, 6), nullable=False),
        sa.Column('actual_cost_usd', sa.Numeric(12, 6), nullable=True),
        sa.Column('provider_cap_usd', sa.Numeric(12, 6), nullable=False),
        sa.Column('total_cap_usd', sa.Numeric(12, 6), nullable=False),
        sa.Column('pricing_version', sa.String(16), nullable=False),
        sa.Column('provider_request_id', sa.String(128), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint(
            'run_id', 'provider', 'prompt_id', 'mode', 'run_index',
            'attempt_no', name='uq_presence_attempt_identity'),
    )


def downgrade() -> None:
    op.drop_table('presence_attempts')
