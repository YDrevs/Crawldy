"""language preferences

Revision ID: 0022
Revises: 0021

Мова стає налаштуванням, а не константою.

`users.locale` порожній за замовчуванням, і це не те саме, що «англійська».
Порожньо означає «не обирав»: така людина поїде за мовою організації, коли
та її змінить, а той, хто обрав, — ні. NULL із дефолтом цієї різниці не
передав би.

`organizations.default_locale` — мова звітів, які організація віддає далі:
своєму керівництву або своїм клієнтам. Наявним організаціям ставиться `en`,
бо саме англійська стала канонічною мовою продукту.

Обидві колонки — рядки, а не enum у базі: перелік мов росте, і кожне
додавання не має бути міграцією типу. Невідоме значення домен читає як
«не обрано», тож зіпсований код не робить акаунт непридатним.

Мови аудиту тут немає й не буде: той самий запуск віддається різними
мовами різним читачам, і зміна цих полів не змінює жодного виміряного
факту.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('default_locale', sa.String(length=16), server_default='en', nullable=False))
    op.add_column('users', sa.Column('locale', sa.String(length=16), server_default='', nullable=False))
    # Рішення про повтор перестає бути готовим реченням однією мовою.
    op.add_column(
        'audit_attempts',
        sa.Column('retry_decision_key', sa.String(length=64), server_default='', nullable=False),
    )
    op.add_column(
        'audit_attempts',
        sa.Column(
            'retry_decision_params',
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'),
            server_default='{}',
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column('audit_attempts', 'retry_decision_params')
    op.drop_column('audit_attempts', 'retry_decision_key')
    op.drop_column('users', 'locale')
    op.drop_column('organizations', 'default_locale')
