"""комерційний текст шістьма мовами: name_i18n / description_i18n

Порожня мапа — універсальна назва (дефолтне поле для всіх мов), і саме
так читаються всі наявні записи: жодних вигаданих перекладів заднім
числом. Числа не локалізуються ніколи — тут лише написи.

Revision ID: 0044
Revises: 0043
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = '0044'
down_revision = '0043'
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ('plans', 'commercial_offers'):
        name_column = 'name_i18n' if table == 'plans' else 'display_name_i18n'
        op.add_column(table, sa.Column(
            name_column, postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default='{}',
        ))
        op.add_column(table, sa.Column(
            'description_i18n', postgresql.JSONB(astext_type=sa.Text()),
            nullable=False, server_default='{}',
        ))


def downgrade() -> None:
    op.drop_column('commercial_offers', 'description_i18n')
    op.drop_column('commercial_offers', 'display_name_i18n')
    op.drop_column('plans', 'description_i18n')
    op.drop_column('plans', 'name_i18n')
