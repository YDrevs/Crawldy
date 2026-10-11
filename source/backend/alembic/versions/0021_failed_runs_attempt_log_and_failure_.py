"""failed runs: attempt log and failure class

Revision ID: 0021
Revises: 0020

Невдалий запуск лишається записом, і тепер він каже, **чому**.

`audit_attempts` — журнал спроб під одним запуском. Лічильника
`audits.attempts` вистачало, щоб знати, скільки разів бралися, але не чому
кожна не вийшла — а це і є питання, яке ставлять до розкладу, що падає
щоночі. Перша спроба на провайдері й друга на нашому коді — інша історія,
ніж дві однакові. Таблиця не належить до важких даних: чистка за строком
утримання прибирає сторінки й докази, а журнал спроб лишається, бо саме
він пояснює діри в кривій.

`audit_targets.failure_class` — клас невдачі там, де його ще видно.
Виняток ловиться на рівні цілі, і до зведення від нього лишався тільки
текст. Наслідок був відчутний: аудит, у якого всі цілі впали через наш
власний код, ішов «успішним» шляхом — клієнту списувалась квота, повтору
не було, а в записі стояло FAILED без жодної причини.
"""
from alembic import op
import sqlalchemy as sa


revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('audit_attempts',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('audit_id', sa.UUID(), nullable=False),
    sa.Column('number', sa.SmallInteger(), nullable=False),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('status', sa.Enum('QUEUED', 'RUNNING', 'COMPLETED', 'PARTIAL', 'FAILED', 'SKIPPED', name='audit_status', native_enum=False), nullable=False),
    sa.Column('failure_class', sa.Enum('SITE_UNREACHABLE', 'SITE_BLOCKED', 'PROVIDER_FAILED', 'INTERNAL_ERROR', 'CANCELLED', name='audit_failure_class', native_enum=False), nullable=True),
    sa.Column('error', sa.Text(), nullable=False),
    sa.Column('retry_decision', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['audit_id'], ['audits.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('audit_id', 'number', name='uq_attempt_number')
    )
    op.create_index(op.f('ix_audit_attempts_audit_id'), 'audit_attempts', ['audit_id'], unique=False)
    op.add_column('audit_targets', sa.Column('failure_class', sa.Enum('SITE_UNREACHABLE', 'SITE_BLOCKED', 'PROVIDER_FAILED', 'INTERNAL_ERROR', 'CANCELLED', name='audit_failure_class', native_enum=False), nullable=True))


def downgrade() -> None:
    op.drop_column('audit_targets', 'failure_class')
    op.drop_index(op.f('ix_audit_attempts_audit_id'), table_name='audit_attempts')
    op.drop_table('audit_attempts')
