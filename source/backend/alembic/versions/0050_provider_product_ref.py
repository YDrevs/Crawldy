"""Продукт провайдера при прайсі каталогу.

Публікація прайсів створює у провайдера продукт і ціну при ньому; щоб
наступна зміна ціни оновлювала ту саму ціну, а не плодила продукти,
ідентифікатор продукту запамʼятовується поруч із прайсом. Порожньо
для записів, що існували до публікації: перша публікація заповнить.

Revision ID: 0050
Revises: 0049
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0050"
down_revision = "0049"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "commercial_offers",
        sa.Column("provider_product_ref", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "plan_prices",
        sa.Column("provider_product_ref", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("plan_prices", "provider_product_ref")
    op.drop_column("commercial_offers", "provider_product_ref")
