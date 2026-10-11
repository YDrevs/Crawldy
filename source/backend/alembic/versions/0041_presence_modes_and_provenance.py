"""presence: режими вимірювання, провенанс спостереження, ідемпотентність

Revision ID: 0041
Revises: 0040
Create Date: 2026-09-01
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

JSONB = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql')

revision = '0041'
down_revision = '0040'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Спостереження: режим (старі P0-рядки — natural: інших тоді не
    # існувало), точний надісланий текст, виконані пошукові запити,
    # пряме посилання, лічильники повторів/тривалості, версія тлумачення.
    op.add_column('presence_observations', sa.Column(
        'mode', sa.String(16), nullable=False, server_default='natural'))
    op.add_column('presence_observations', sa.Column(
        'sent_text', sa.Text(), nullable=False, server_default=''))
    op.add_column('presence_observations', sa.Column(
        'search_queries', JSONB, nullable=False, server_default='[]'))
    op.add_column('presence_observations', sa.Column(
        'domain_linked', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('presence_observations', sa.Column(
        'linked_urls', JSONB, nullable=False, server_default='[]'))
    op.add_column('presence_observations', sa.Column(
        'retries', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('presence_observations', sa.Column(
        'duration_ms', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('presence_observations', sa.Column(
        'normalize_version', sa.String(8), nullable=False, server_default=''))

    # Ідентичність клітинки тепер включає режим.
    op.drop_constraint(
        'uq_presence_observation_identity', 'presence_observations',
        type_='unique')
    op.create_unique_constraint(
        'uq_presence_observation_identity', 'presence_observations',
        ['run_id', 'provider', 'prompt_id', 'mode', 'run_index'])

    # Прогін: підсумок придатності та ключ ідемпотентності подання.
    op.add_column('presence_runs', sa.Column(
        'deliverable', sa.Boolean(), nullable=True))
    op.add_column('presence_runs', sa.Column(
        'idempotency_key', sa.String(64), nullable=True))
    op.create_unique_constraint(
        'uq_presence_run_idempotency', 'presence_runs',
        ['organization_id', 'idempotency_key'])


def downgrade() -> None:
    op.drop_constraint('uq_presence_run_idempotency', 'presence_runs', type_='unique')
    op.drop_column('presence_runs', 'idempotency_key')
    op.drop_column('presence_runs', 'deliverable')
    op.drop_constraint(
        'uq_presence_observation_identity', 'presence_observations',
        type_='unique')
    op.create_unique_constraint(
        'uq_presence_observation_identity', 'presence_observations',
        ['run_id', 'provider', 'prompt_id', 'run_index'])
    for column in ('normalize_version', 'duration_ms', 'retries', 'linked_urls',
                   'domain_linked', 'search_queries', 'sent_text', 'mode'):
        op.drop_column('presence_observations', column)
