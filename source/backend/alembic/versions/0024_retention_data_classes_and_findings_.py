"""retention: data classes and findings summary

Revision ID: 0024
Revises: 0023

Дані аудиту отримують класи з різними строками життя.

`purged_at` замінюється двома мітками, бо «почищено» — не один стан:
сирі дані (сторінки, знімки) і знахідки (issues, журнал спроб) живуть
різні строки, і різниця видима клієнту. Аудит без знімка ще можна
перечитати, аудит без знахідок — уже ні. Колонка порожня в усіх наявних
рядках (чистки ще не існувало), тож заміна не втрачає даних.

`findings_summary` — зведення, яке лишиться, коли самих знахідок уже не
буде: скільки, якої серйозності, у яких модулях, топ проблем за issue_key.
Рахується при завершенні аудиту, а не при чистці: пораховане при чистці
залежало б від того, коли job дійшов до рядка, а для аудиту, видаленого
раніше строку, не існувало б узагалі.

Сам рядок audits не чиститься ніколи: на ньому тримається крива історії,
і діра в ній читається як «нічого не сталося».
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('audits', sa.Column('raw_purged_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('audits', sa.Column('findings_purged_at', sa.DateTime(timezone=True), nullable=True))
    # Порожній обʼєкт наявним рядкам, а не порахований підсумок: зведення
    # рахується при завершенні аудиту, і відтворювати його тут із
    # теперішніх знахідок означало б написати в стару строку сьогоднішнє
    # число. Порожньо чесно каже «не рахували», і чистка це поважає.
    op.add_column('audits', sa.Column('findings_summary', sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), 'postgresql'), nullable=True))
    op.execute("UPDATE audits SET findings_summary = '{}'::jsonb WHERE findings_summary IS NULL")
    op.alter_column('audits', 'findings_summary', nullable=False)
    op.drop_column('audits', 'purged_at')


def downgrade() -> None:
    op.add_column('audits', sa.Column('purged_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True))
    op.drop_column('audits', 'findings_summary')
    op.drop_column('audits', 'findings_purged_at')
    op.drop_column('audits', 'raw_purged_at')
