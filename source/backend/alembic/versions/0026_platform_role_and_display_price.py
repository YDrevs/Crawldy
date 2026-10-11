"""platform role and display price

Revision ID: 0026
Revises: 0025

`users.platform_role` — окрема вісь авторизації для команди Crawldy.

Не прапорець `is_staff` і не значення в `Membership.role`: та роль про
організацію клієнта, ця — про платформу. В одному полі власник будь-якої
організації опинився б на один рядок від нашої адмінки. Два рівні
одразу (staff дивиться, admin міняє), бо розділити їх пізніше означало б
розбиратися, хто що вже встиг.

Порожньо в усіх наявних рядків — це дефолт і він безпечний: щоб стати
персоналом, потрібна явна дія, а не відсутність заборони.

`plan_prices.display_amount_minor` — ціна для показу на сторінці тарифів.
Не джерело правди для списання: рахує провайдер за своїм прайсом.
Поле існує, бо публічна сторінка потребує числа, а тягнути його з
провайдера на кожен показ означало б класти сторінку разом із його
недоступністю.

`minor`, а не `cents`: у єни мінімальної одиниці немає взагалі, у динара
Бахрейну їх тисяча. Показник валюти не зберігається — він властивість
ISO 4217, а не окремої ціни, і рахується в `billing/money.py`.
"""
from alembic import op
import sqlalchemy as sa


revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('plan_prices', sa.Column('display_amount_minor', sa.Integer(), nullable=True))
    op.add_column('users', sa.Column('platform_role', sa.Enum('STAFF', 'ADMIN', name='platform_role', native_enum=False), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'platform_role')
    op.drop_column('plan_prices', 'display_amount_minor')
