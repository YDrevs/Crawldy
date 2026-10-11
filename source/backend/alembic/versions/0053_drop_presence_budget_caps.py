"""Стелі бюджету присутності скасовано: знімок стелі спроби — nullable.

Стелі ($10 на прогін, $5 на провайдера) були нижчі за виміряну вартість
повного аудиту ($10.81, сама Anthropic $6.21) і обрізали б перший же
справжній клієнтський прогін. Колонки не видаляються: історичні рядки
документують, проти чого резервувалась спроба тоді, коли стелі були.
Нові рядки пишуть NULL — «резервувалось не проти стелі».

Revision ID: 0053
Revises: 0052
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0053"
down_revision = "0052"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "presence_attempts", "provider_cap_usd",
        existing_type=sa.Numeric(12, 6), nullable=True,
    )
    op.alter_column(
        "presence_attempts", "total_cap_usd",
        existing_type=sa.Numeric(12, 6), nullable=True,
    )


def downgrade() -> None:
    # Назад колонки стають обовʼязковими, тож рядки без стелі треба чимось
    # заповнити. Нуль тут був би брехнею («стеля нульова»), тож беремо
    # зарезервований максимум самої спроби: проти нього її і допускали.
    op.execute(
        "UPDATE presence_attempts SET provider_cap_usd = reserved_max_usd "
        "WHERE provider_cap_usd IS NULL"
    )
    op.execute(
        "UPDATE presence_attempts SET total_cap_usd = reserved_max_usd "
        "WHERE total_cap_usd IS NULL"
    )
    op.alter_column(
        "presence_attempts", "total_cap_usd",
        existing_type=sa.Numeric(12, 6), nullable=False,
    )
    op.alter_column(
        "presence_attempts", "provider_cap_usd",
        existing_type=sa.Numeric(12, 6), nullable=False,
    )
