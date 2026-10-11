"""enrichment pricing identity

Revision ID: 0035
Revises: 0034

Три імені моделі замість одного. Провайдер може відпрацювати датованим
знімком запитаної моделі: ми просимо `gpt-5.4-mini`, відповідає
`gpt-5.4-mini-2026-03-17`. Провенанс мусить зберегти фактичне імʼя, але
цінник такого ключа не має — і перший живий виклик OpenAI записав
вартість NULL при цілком відомій ціні.

Тепер окремо: `model` (що відпрацювало), `requested_model` (що просили),
`pricing_key` (за чим шукали ціну). Обрізати суфікс регуляркою було б
гірше: вона так само радо зробила б із `gpt-5.4-mini` модель `gpt-5.4`.
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0035"
down_revision = "0034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "enrichment_attempts", sa.Column("requested_model", sa.String(64), nullable=True)
    )
    op.add_column(
        "enrichment_attempts", sa.Column("pricing_key", sa.String(64), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("enrichment_attempts", "pricing_key")
    op.drop_column("enrichment_attempts", "requested_model")
