"""безкоштовний стан акаунта не дарує повних аудитів

Рішення власника 2026-09-03: безкоштовних ПОВНИХ аудитів не існує.
Безкоштовне превʼю (обмежений результат) необмежене і не проходить
через квоту взагалі — його боронить технічний ліміт частоти. Тариф
`free` лишається дефолтним станом акаунта без покупки, але «1 повний
аудит на період» був хибним продуктовим правилом: він і створював
неправдиве «1 of 1 audits» у кабінеті, і слугував воротами «один
безкоштовний аудит на гостьову сесію».

Умова звужена до dev-сідового коду навмисно: тарифи, заведені руками,
міграція не переписує.

Revision ID: 0046
Revises: 0045
Create Date: 2026-09-03
"""
from alembic import op

revision = '0046'
down_revision = '0045'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE plans
           SET entitlements = jsonb_set(entitlements, '{audits_per_period}', '0')
         WHERE code = 'free'
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE plans
           SET entitlements = jsonb_set(entitlements, '{audits_per_period}', '1')
         WHERE code = 'free'
        """
    )
