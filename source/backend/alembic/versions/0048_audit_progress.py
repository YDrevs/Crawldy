"""Хід виконання аудиту: скільки сторінок уже прочитано.

Числа справжні — ті самі, що потім стануть покриттям у звіті. Поле
існує, щоб екран очікування показував рух, не вигадуючи відсотків.

Revision ID: 0048
Revises: 0047
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0048"
down_revision = "0047"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audits",
        sa.Column(
            "progress",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("audits", "progress")
