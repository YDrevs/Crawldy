"""enrichment cache tokens

Revision ID: 0034
Revises: 0033

Кешовані токени окремими колонками. Провайдер віддає їх окремо від
`input_tokens` і тарифікує інакше — запис у кеш дорожчий за звичайний
вхід, читання вдесятеро дешевше. Без цих колонок вартість у журналі
була б занижена рівно на кешовану частину, тобто журнал витрат показував
би неправильне число там, де він існує саме заради правильного.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0034"
down_revision = "0033"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "enrichment_attempts", sa.Column("cache_write_tokens", sa.Integer(), nullable=True)
    )
    op.add_column(
        "enrichment_attempts", sa.Column("cache_read_tokens", sa.Integer(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("enrichment_attempts", "cache_read_tokens")
    op.drop_column("enrichment_attempts", "cache_write_tokens")
