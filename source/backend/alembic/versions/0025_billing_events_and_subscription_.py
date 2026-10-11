"""billing events and subscription transitions

Revision ID: 0025
Revises: 0024

Журнал білінгу: вхідні факти окремо від стану.

`billing_events` — нормалізовані події провайдера. Ідемпотентність
тримається унікальністю (provider, external_event_id) у базі, а не if-ом
у коді: та сама подія приходить двічі, п'ять разів, після таймауту нашої
відповіді й паралельно на два процеси — а рядок один і перехід один.
«Отримано» і «оброблено» — різні статуси: збій обробки лишає подію
видимою як failed, придатною до повтору й нездатною створити другий
перехід. Нормалізовані факти (періоди, trial, організація) — колонками:
з них подія відновлюється для повтору без участі провайдера.

`subscription_transitions` — історія переходів, якої не переписують.
Відповідь на «чому ця організація 14 березня мала права Pro» складається
саме звідси: стан, тариф, межі періоду, момент дії і посилання на подію.
organization_id денормалізовано навмисно — питання ставлять про
організацію, і відповідь не має залежати від того, чи жива підписка.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0025'
down_revision = '0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('billing_events',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('provider', sa.String(length=32), nullable=False),
    sa.Column('external_event_id', sa.String(length=128), nullable=False),
    sa.Column('kind', sa.String(length=48), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('received_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.Enum('RECEIVED', 'PROCESSING', 'PROCESSED', 'STALE', 'FAILED', name='billing_event_status', native_enum=False), nullable=False),
    sa.Column('error', sa.Text(), nullable=False),
    sa.Column('subscription_ref', sa.String(length=128), nullable=True),
    sa.Column('customer_ref', sa.String(length=128), nullable=True),
    sa.Column('price_ref', sa.String(length=128), nullable=True),
    sa.Column('organization_id', sa.UUID(), nullable=True),
    sa.Column('with_trial', sa.Boolean(), nullable=False),
    sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('trial_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancel_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider', 'external_event_id', name='uq_billing_event_provider_id')
    )
    op.create_index('ix_billing_events_status', 'billing_events', ['status'], unique=False)
    op.create_table('subscription_transitions',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('subscription_id', sa.UUID(), nullable=False),
    sa.Column('organization_id', sa.UUID(), nullable=False),
    sa.Column('from_status', sa.Enum('INACTIVE', 'TRIALING', 'ACTIVE', 'PAST_DUE', 'PAUSED', 'CANCELLED', name='subscription_status', native_enum=False), nullable=False),
    sa.Column('to_status', sa.Enum('INACTIVE', 'TRIALING', 'ACTIVE', 'PAST_DUE', 'PAUSED', 'CANCELLED', name='subscription_status', native_enum=False), nullable=False),
    sa.Column('from_plan_id', sa.UUID(), nullable=True),
    sa.Column('to_plan_id', sa.UUID(), nullable=False),
    sa.Column('effective_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('period_start', sa.DateTime(timezone=True), nullable=True),
    sa.Column('period_end', sa.DateTime(timezone=True), nullable=True),
    sa.Column('grace_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('cancel_at_period_end', sa.Boolean(), nullable=False),
    sa.Column('billing_event_id', sa.UUID(), nullable=True),
    sa.ForeignKeyConstraint(['billing_event_id'], ['billing_events.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscription_transitions_organization_id'), 'subscription_transitions', ['organization_id'], unique=False)
    op.create_index(op.f('ix_subscription_transitions_subscription_id'), 'subscription_transitions', ['subscription_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_subscription_transitions_subscription_id'), table_name='subscription_transitions')
    op.drop_index(op.f('ix_subscription_transitions_organization_id'), table_name='subscription_transitions')
    op.drop_table('subscription_transitions')
    op.drop_index('ix_billing_events_status', table_name='billing_events')
    op.drop_table('billing_events')
