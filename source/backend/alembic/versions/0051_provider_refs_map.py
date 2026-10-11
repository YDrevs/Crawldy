"""Памʼять прайсів по провайдерах.

Чинну привʼязку описують `provider` / `provider_price_ref`; ця мапа
памʼятає, що запис мав у КОЖНОГО провайдера, у якого публікувався. Без
неї повернення до попереднього провайдера створювало б у нього нові
продукти замість наявних.

Наявні записи переносяться: чинна привʼязка стає першим рядком мапи.

Revision ID: 0051
Revises: 0050
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0051"
down_revision = "0050"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for table in ("commercial_offers", "plan_prices"):
        op.add_column(
            table,
            sa.Column(
                "provider_refs", JSONB(), nullable=False, server_default="{}"
            ),
        )
    op.execute(
        """
        UPDATE commercial_offers
           SET provider_refs = jsonb_build_object(
                 provider,
                 jsonb_build_object(
                   'price', provider_price_ref,
                   'product', coalesce(provider_product_ref, '')
                 )
               )
         WHERE provider_price_ref <> ''
        """
    )
    op.execute(
        """
        UPDATE plan_prices
           SET provider_refs = jsonb_build_object(
                 provider,
                 jsonb_build_object(
                   'price', provider_price_id,
                   'product', coalesce(provider_product_ref, '')
                 )
               )
         WHERE provider_price_id <> ''
        """
    )


def downgrade() -> None:
    for table in ("plan_prices", "commercial_offers"):
        op.drop_column(table, "provider_refs")
