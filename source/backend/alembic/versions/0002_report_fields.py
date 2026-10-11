"""report fields: degraded, evidence, i18n keys on issues

Revision ID: 0002
Revises: 0001

Звіт фази 1 потребує даних, яких у схемі не було:
- degraded/skipped_modules — щоб зібрати missing_data (зараз деградації
  склеєні рядком в audits.error і структуру з них не відновити);
- evidence — site-level докази (robots, sitemap, llms.txt, performance);
  вони жили лише в SiteContext і після аудиту зникали;
- msg_key/msg_params на issue — без них збережений аудит не перекласти
  іншою мовою, бо в БД лежить уже відрендерений український текст.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audits",
        sa.Column("degraded", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "audits",
        sa.Column("skipped_modules", postgresql.JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "audits",
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "audit_issues",
        sa.Column("msg_key", sa.String(96), nullable=False, server_default=""),
    )
    op.add_column(
        "audit_issues",
        sa.Column("msg_params", postgresql.JSONB(), nullable=False, server_default="{}"),
    )

    # Старі issues не мають ключа каталогу. code — найкраще наближення:
    # для чеків з одним повідомленням він збігається з ключем, для решти
    # рендер відкотиться на сам ключ, а не збрехає перекладом.
    op.execute("UPDATE audit_issues SET msg_key = code WHERE msg_key = ''")


def downgrade() -> None:
    op.drop_column("audit_issues", "msg_params")
    op.drop_column("audit_issues", "msg_key")
    op.drop_column("audits", "evidence")
    op.drop_column("audits", "skipped_modules")
    op.drop_column("audits", "degraded")
