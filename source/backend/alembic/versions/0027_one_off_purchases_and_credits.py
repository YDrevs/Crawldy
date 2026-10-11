"""one-off purchases and audit credits

Revision ID: 0027
Revises: 0026

Разова покупка аудитів і кредити, які вона породжує.

## Дві таблиці, а не лічильник

Спокуслива модель — одна колонка `credits_balance` на організації. Вона
не відповідає на питання, які виникають першого ж місяця: повернути
кошти за конкретну покупку, відкликати саме її невитрачені одиниці,
повернути **той самий** кредит за аудит, що не відбувся, пояснити через
півроку, звідки взялися ці пʼять.

Тому одиниця обліку — рядок у `audit_credits`. «Кредит не можна
зарезервувати двічі» стає властивістю рядка, а не арифметикою над
лічильником, у якій гонка непомітна доти, доки хтось не поскаржиться.

## Постачальник фіксується знімком, а не посиланням

`supplier_entity_key` каже, ким ми були; `supplier_snapshot` каже, які
саме реквізити діяли на момент продажу. Одного ключа мало: реєстр
юридичних осіб колись відредагують, і вся історія продажів мовчки
перепишеться на нову особу.

`commerce_model` теж у рядку. Це не наш постачальник і не провайдер, а
третє: хто юридично продавав покупцю. При merchant of record продавцем
виступає сам провайдер; при direct — ми. Після переходу Paddle → Stripe
модель зміниться, і без цього поля стара покупка почала б означати
протилежне тому, чим була.

## `audits.quota_source`

З чого оплачено аудит. Записується, а не виводиться: висновок «повернення
кредиту не оновило рядків, отже платили квотою» однаково виглядає і тоді,
коли кредит просто загубився. Порожньо в наявних рядків — вони старші за
разові покупки, і це чесне «невідомо», а не «підписка».
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None

# Перерахування зберігаються іменами членів, а не значеннями: саме так
# SQLAlchemy кладе Python-enum у колонку. CHECK, побудований зі значень,
# відбивав би кожен запис ORM.
CREDIT_STATES = ("AVAILABLE", "RESERVED", "CONSUMED", "REVOKED")
PURCHASE_STATUSES = ("PENDING", "PAID", "REFUNDED")
COMMERCE_MODELS = ("MERCHANT_OF_RECORD", "DIRECT")
QUOTA_SOURCES = ("SUBSCRIPTION", "ONE_OFF")


def upgrade() -> None:
    op.create_table(
        "one_off_purchases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("supplier_entity_key", sa.String(48), nullable=False),
        sa.Column(
            "supplier_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "commerce_model",
            sa.Enum(*COMMERCE_MODELS, name="commerce_model", native_enum=False),
            nullable=False,
        ),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(*PURCHASE_STATUSES, name="purchase_status", native_enum=False),
            nullable=False,
            server_default="PAID",
        ),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # Ідемпотентність приймання платежу тримає база, а не код: повторна
    # доставка тієї самої події не створить другої покупки, а отже й
    # другої партії кредитів.
    op.create_unique_constraint(
        "uq_purchase_provider_external",
        "one_off_purchases",
        ["provider", "external_id"],
    )
    op.create_index(
        "ix_one_off_purchases_organization_id", "one_off_purchases", ["organization_id"]
    )
    op.create_index(
        "ix_purchases_org_created", "one_off_purchases", ["organization_id", "created_at"]
    )

    op.create_table(
        "audit_credits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "purchase_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("one_off_purchases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "state",
            sa.Enum(*CREDIT_STATES, name="audit_credit_state", native_enum=False),
            nullable=False,
            server_default="AVAILABLE",
        ),
        # SET NULL, а не CASCADE: аудит колись видалять за строком
        # зберігання, і кредит не має зникати разом із ним — він
        # фінансовий запис, а не похідні дані аудиту.
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reserved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_audit_credits_purchase_id", "audit_credits", ["purchase_id"])
    op.create_index("ix_audit_credits_audit_id", "audit_credits", ["audit_id"])
    # Найгарячіший запит таблиці — «вільний кредит цієї організації».
    op.create_index("ix_credits_org_state", "audit_credits", ["organization_id", "state"])

    op.add_column(
        "audits",
        sa.Column(
            "quota_source",
            sa.Enum(*QUOTA_SOURCES, name="audit_quota_source", native_enum=False),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("audits", "quota_source")
    op.drop_index("ix_credits_org_state", table_name="audit_credits")
    op.drop_index("ix_audit_credits_audit_id", table_name="audit_credits")
    op.drop_index("ix_audit_credits_purchase_id", table_name="audit_credits")
    op.drop_table("audit_credits")
    op.drop_index("ix_purchases_org_created", table_name="one_off_purchases")
    op.drop_index("ix_one_off_purchases_organization_id", table_name="one_off_purchases")
    op.drop_table("one_off_purchases")
