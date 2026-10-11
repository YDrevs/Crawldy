"""one schedule per site

Revision ID: 0029
Revises: 0028

Один розклад на сайт — правило домену, а не обмеження інтерфейсу.

Продуктове питання звучить «коли перевіряти цей сайт», і два різні
розклади на нього не гнучкість, а два джерела правди: людина бачить
«щотижня», а запуски приходять щодня, бо десь лишився другий запис.

Заразом обмеження робить безпечним повторне надсилання форми. Створення
розкладу не було ідемпотентним: подвійний клік, повтор запиту після
таймауту або ретрай клієнта давали другий розклад, і клієнт помічав це
за подвоєним рахунком аудитів.

## Дублікати не видаляються мовчки

Якщо в базі вже є сайт із двома розкладами, міграція зупиняється з
переліком таких сайтів замість того, щоб вирішити за людину, який із них
зайвий. Розклад — це намір клієнта; стерти його автоматично дешевше, ніж
пояснити потім, чому аудити перестали приходити.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    duplicates = (
        op.get_bind()
        .execute(
            sa.text(
                """
                SELECT site_id, count(*) AS n
                  FROM audit_schedules
                 GROUP BY site_id
                HAVING count(*) > 1
                """
            )
        )
        .fetchall()
    )
    if duplicates:
        listed = ", ".join(f"{row.site_id} ({row.n})" for row in duplicates)
        raise RuntimeError(
            "у цих сайтів більше одного розкладу, і вибір зайвого — рішення "
            f"людини, а не міграції: {listed}"
        )

    op.create_unique_constraint("uq_schedule_site", "audit_schedules", ["site_id"])


def downgrade() -> None:
    op.drop_constraint("uq_schedule_site", "audit_schedules", type_="unique")
