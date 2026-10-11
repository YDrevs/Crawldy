"""commercial snapshots: purchase offer terms, subscription period allocation

Revision ID: 0040
Revises: 0039
Create Date: 2026-08-31
"""
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = '0040'
down_revision = '0039'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Зліпок комерційних умов пропозиції на момент відкриття каси:
    # редагування каталогу не переписує того, що людина вже купила.
    op.add_column(
        'one_off_purchases',
        sa.Column('offer_snapshot', JSONB(), nullable=True),
    )
    # Наділ поточного періоду підписки: зміна тарифу посеред періоду не
    # чіпає вже виданого; наступний період знімкується наново.
    op.add_column(
        'subscriptions',
        sa.Column('period_allocation', JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('subscriptions', 'period_allocation')
    op.drop_column('one_off_purchases', 'offer_snapshot')
