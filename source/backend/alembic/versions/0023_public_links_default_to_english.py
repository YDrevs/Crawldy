"""public links default to english

Revision ID: 0023
Revises: 0022

`report_links.lang` мав server_default 'uk' ще з 0004, коли українська була
дефолтною мовою продукту. Тепер вона нею не є, а серверний дефолт лишався —
і будь-яка вставка повз ORM створювала б українське посилання.

Наявні посилання не чіпаємо: мова публічного посилання фіксується при
створенні й переписувати її заднім числом означало б змінити документ,
який комусь уже надіслали.

Alembic цієї різниці не бачить: autogenerate не порівнює server_default,
поки йому це не ввімкнути. Тому міграція написана вручну.
"""
from alembic import op
import sqlalchemy as sa


revision = '0023'
down_revision = '0022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("report_links", "lang", server_default="en")


def downgrade() -> None:
    op.alter_column("report_links", "lang", server_default="uk")
