"""тарифні рівні dev-сіда зникають із публічного каталогу

Free / Starter / Pro / Agency — вітринні рівні з раннього сіда (0014),
які продукт не продає: доступ — це Single / Pack / Monthly, кількість
того самого аналізу, а не рівні з відібраними можливостями. Рядки
лишаються — `free` є дефолтним тарифом резолвера прав, і жодна
підписка чи покупка не зачіпається; змінюється лише видимість у
`/v1/plans`.

Умова звужена до dev-сідових кодів навмисно: тариф, заведений пізніше
руками (наприклад, продуктовий Monthly), міграція не чіпає.

Revision ID: 0045
Revises: 0044
Create Date: 2026-09-02
"""
from alembic import op

revision = '0045'
down_revision = '0044'
branch_labels = None
depends_on = None

LEGACY_TIER_CODES = "('free', 'starter', 'pro', 'agency')"


def upgrade() -> None:
    op.execute(
        f"UPDATE plans SET is_public = false WHERE code IN {LEGACY_TIER_CODES}"
    )


def downgrade() -> None:
    op.execute(
        f"UPDATE plans SET is_public = true WHERE code IN {LEGACY_TIER_CODES}"
    )
