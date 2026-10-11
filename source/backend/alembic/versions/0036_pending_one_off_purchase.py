"""pending one-off purchase

Revision ID: 0036
Revises: 0035

Разова покупка тепер починається до каси, а не після оплати.

Два наслідки для схеми, обидва додавальні:

- `provider_ref` — посилання провайдера на транзакцію. Подія про
  повернення коштів посилається саме на неї, а не на нашу покупку, тож
  без цього поля повернення нічого б не знайшло. Окремо від
  `external_id`, де лежить НАШ ідентифікатор кореляції: змішати їх
  означало б не мати чим звірити одне з одним.

- `purchased_at` стає nullable. Покупка в стані PENDING ще не оплачена,
  і підставляти туди час створення означало б назвати часом оплати
  момент, коли ніхто не заплатив. Наявні рядки не змінюються: усі вони
  оплачені й час мають.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0036"
down_revision = "0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "one_off_purchases", sa.Column("provider_ref", sa.String(128), nullable=True)
    )
    op.create_index(
        "ix_one_off_purchases_provider_ref", "one_off_purchases", ["provider_ref"]
    )
    op.alter_column(
        "one_off_purchases",
        "purchased_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
    )


def downgrade() -> None:
    # Назад — лише для порожньої від PENDING таблиці: рядок без часу
    # оплати в NOT NULL не влізе, і мовчки вигадувати йому час не можна.
    op.alter_column(
        "one_off_purchases",
        "purchased_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
    )
    op.drop_index("ix_one_off_purchases_provider_ref", table_name="one_off_purchases")
    op.drop_column("one_off_purchases", "provider_ref")
