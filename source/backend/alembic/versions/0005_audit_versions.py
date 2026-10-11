"""audits/audit_targets: чим саме порахований аудит

Revision ID: 0005
Revises: 0004

Без цих полів два аудити того самого сайту не можна порівняти: різниця
в балах однаково пояснюється змінами на сайті й змінами в нас. Це не
теоретична загроза — друга стеля в скорингу зсунула бали всієї вибірки,
і всі попередні аудити стали непорівнянними мовчки.

Одна JSON-колонка, а не пʼять окремих: набір полів ще змінюватиметься,
і кожна зміна не має коштувати міграції. Всередині лежить `schema`, яка
й каже, який це набір.

Старим рядкам дістається порожній обʼєкт. Це чесно: ми справді не знаємо,
чим їх рахували, і вигадувати версію заднім числом означало б зробити їх
порівнянними на вигляд, не будучи такими.
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_JSON = postgresql.JSONB(astext_type=sa.Text())


def upgrade() -> None:
    for table in ("audits", "audit_targets"):
        op.add_column(
            table,
            sa.Column("versions", _JSON, nullable=False, server_default=sa.text("'{}'::jsonb")),
        )


def downgrade() -> None:
    for table in ("audits", "audit_targets"):
        op.drop_column(table, "versions")
