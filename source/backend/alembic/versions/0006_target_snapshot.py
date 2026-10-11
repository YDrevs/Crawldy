"""audit_targets: знімок зібраного для перерахунку без краулу

Revision ID: 0006
Revises: 0005

Версії з міграції 0005 назвали проблему: після зміни скорингу старі бали
стають непорівнянними. Але назвати мало — треба мати з чого перерахувати,
а в базі лежали самі висновки. Єдиним способом оновити число був
повторний краул, тобто вимірювання вже іншого сайту.

Знімок — це `SiteContext` без втрат: сторінки з посиланнями, розміткою й
текстом, robots, карта сайту, llms.txt, вимірювання швидкості й
відрендерені сигнали. HTML не зберігається — чеки читають сигнали, а не
розмітку, — і висновки моделі теж: вони належать конкретному прогону.

Колонка на `audit_targets`, а не на `audits`: знімок належить одній
адресі, а в аудиті їх може бути кілька.

Старим рядкам дістається порожній обʼєкт. Перерахувати їх не вийде, і це
чесніше, ніж вдавати, що вийде.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

_JSON = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    op.add_column(
        "audit_targets",
        sa.Column("snapshot", _JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )


def downgrade() -> None:
    op.drop_column("audit_targets", "snapshot")
