"""enum defaults use member names

Revision ID: 0028
Revises: 0027

Двом колонкам `audits` дефолт було задано **значенням** перерахування,
тоді як SQLAlchemy кладе в колонку **імʼя** члена, і CHECK побудований
на іменах.

    trigger      DEFAULT 'manual'   CHECK IN ('MANUAL','SCHEDULED','API')
    quota_state  DEFAULT 'reserved' CHECK IN ('RESERVED','CONSUMED','RELEASED')

Тобто дефолт колонки порушував обмеження тієї самої колонки. Дефект був
тихий: ORM завжди пише ці поля сам, тож до дефолту справа не доходила
жодного разу. Він спрацював би на першому ж записі повз ORM — ручному
`INSERT`, міграції даних, відновленні з дампа без цих колонок, — і
впав би на порушенні CHECK у місці, де ніхто не шукав би причину.

Старі міграції не переписуються: вони описують те, що вже сталося.
Виправлення йде вперед, окремим кроком, і міняє лише DEFAULT — дані в
колонках коректні, бо їх завжди писав ORM.
"""

from __future__ import annotations

from alembic import op

revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None

# Колонка → (було, стало). «Стало» — імʼя члена, тобто те саме, що вже
# перелічено в CHECK цієї колонки.
FIXES = (
    ("audits", "trigger", "manual", "MANUAL"),
    ("audits", "quota_state", "reserved", "RESERVED"),
)


def upgrade() -> None:
    for table, column, _old, correct in FIXES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT '{correct}'")


def downgrade() -> None:
    # Повертаємо як було — разом із дефектом. Відкат має відновлювати
    # попередній стан, а не покращений: інакше «відкотили» перестає
    # означати «повернулися туди, де були».
    for table, column, old, _correct in FIXES:
        op.execute(f"ALTER TABLE {table} ALTER COLUMN {column} SET DEFAULT '{old}'")
