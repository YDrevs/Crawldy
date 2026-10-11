"""audits belong to an organization

Revision ID: 0013
Revises: 0012

Найважливіша міграція фази 4 з погляду безпеки. До неї жоден аудит не мав
власника: `GET /v1/audits/{id}` віддавав будь-який аудит будь-кому з
ключем. Це не недогляд у перевірці — це відсутність самого поняття, за
яким можна перевіряти.

Порядок кроків не косметичний. Колонка додається nullable, потім
заповнюється, і лише потім стає NOT NULL: додати її одразу обов'язковою
означає впасти на першому ж рядку, який уже є в базі.

Наявні аудити прив'язуються до службової організації з фіксованим
ідентифікатором. Вони не належать жодному клієнту й не мають вигляду в
інтерфейсі; вони лишаються, бо на них тримається калібрування, і
видалити їх заради чистоти схеми означало б втратити те, чим міряється
якість продукту. До цієї ж організації прив'язаний глобальний
`settings.api_keys` — так наявні виклики працюють далі, але вже мають
власника, а не діють поза моделлю доступу.

`organization_id` іде з ondelete=RESTRICT: аудити — це історія, за яку
заплатили, і видалення організації не має тихо забирати її з собою.
"""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

# Фіксований ідентифікатор службової організації. Він захардкожений
# навмисно: код автентифікації мусить знати його, не роблячи запиту, а
# згенерований при міграції UUID довелося б звідкись читати.
LEGACY_ORG_ID = "00000000-0000-0000-0000-0000000000c1"


def upgrade() -> None:
    op.add_column("audits", sa.Column("organization_id", sa.UUID(), nullable=True))
    op.add_column("audits", sa.Column("site_id", sa.UUID(), nullable=True))
    op.add_column("audits", sa.Column("created_by_user_id", sa.UUID(), nullable=True))
    op.add_column(
        "audits",
        sa.Column(
            "trigger",
            sa.Enum("MANUAL", "SCHEDULED", "API", name="audit_trigger", native_enum=False),
            server_default="manual",
            nullable=False,
        ),
    )
    op.add_column("audits", sa.Column("purged_at", sa.DateTime(timezone=True), nullable=True))

    # Службова організація. ON CONFLICT — щоб повторний прогін міграції на
    # частково накатаній базі не падав.
    # Параметр приводиться до uuid явно: asyncpg не робить неявного
    # приведення varchar → uuid і падає з DatatypeMismatchError.
    op.execute(
        sa.text(
            """
            INSERT INTO organizations (id, name, slug, is_personal, created_at, updated_at)
            VALUES (CAST(:id AS uuid), 'Службовий простір', 'legacy', false, now(), now())
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(id=LEGACY_ORG_ID)
    )
    op.execute(
        sa.text(
            "UPDATE audits SET organization_id = CAST(:id AS uuid) "
            "WHERE organization_id IS NULL"
        ).bindparams(id=LEGACY_ORG_ID)
    )

    op.alter_column("audits", "organization_id", nullable=False)

    op.create_index("ix_audits_organization_id", "audits", ["organization_id"])
    op.create_index("ix_audits_site_id", "audits", ["site_id"])
    # Складений індекс під головний запит історії: аудити організації в
    # зворотному хронологічному порядку.
    op.create_index("ix_audits_org_created", "audits", ["organization_id", "created_at"])
    op.create_index("ix_audits_site_created", "audits", ["site_id", "created_at"])

    op.create_foreign_key(
        "fk_audits_organization",
        "audits",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_audits_site", "audits", "sites", ["site_id"], ["id"], ondelete="SET NULL"
    )
    op.create_foreign_key(
        "fk_audits_created_by", "audits", "users", ["created_by_user_id"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    op.drop_constraint("fk_audits_created_by", "audits", type_="foreignkey")
    op.drop_constraint("fk_audits_site", "audits", type_="foreignkey")
    op.drop_constraint("fk_audits_organization", "audits", type_="foreignkey")
    op.drop_index("ix_audits_site_created", table_name="audits")
    op.drop_index("ix_audits_org_created", table_name="audits")
    op.drop_index("ix_audits_site_id", table_name="audits")
    op.drop_index("ix_audits_organization_id", table_name="audits")
    op.drop_column("audits", "purged_at")
    op.drop_column("audits", "trigger")
    op.drop_column("audits", "created_by_user_id")
    op.drop_column("audits", "site_id")
    op.drop_column("audits", "organization_id")
    # Службову організацію не видаляємо: до неї можуть бути прив'язані
    # інші записи, а порожня організація нікому не шкодить.
