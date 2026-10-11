"""Таблиці контексту ідентичності: хто це і від чийого імені діє.

Представлення персистентності, не бізнес-логіка. Правила — в
`app/identity/`; тут лише те, як воно лежить у базі.

Головне рішення схеми: **користувач не володіє нічим.** Усе, за що
платять і що можна передати, належить організації. На запуску майже
кожна організація матиме одного учасника, і спокуса прив'язати сайти
просто до `user_id` велика — але тоді поява другого учасника, передача
володіння чи агентський акаунт означають міграцію всіх бізнес-таблиць
одночасно. Один зайвий join сьогодні дешевший за це.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.audit.i18n import DEFAULT_LOCALE
from app.core.db import Base
from app.identity.enums import OrganizationKind, PlatformRole, Role, UserStatus


def _now() -> datetime:
    return datetime.now(UTC)


class User(Base):
    """Особа. Тільки ідентичність — ні тарифу, ні сайтів, ні аудитів."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Пошта зберігається вже нормалізованою (нижній регістр, без пробілів).
    # Унікальність — функціональним індексом по lower(email): нормалізація
    # в домені може мати помилку, база помилки мати не може.
    email: Mapped[str] = mapped_column(String(320))
    password_hash: Mapped[str] = mapped_column(Text)
    display_name: Mapped[str] = mapped_column(String(200), default="")
    # Належність до команди Crawldy. Порожньо — звичайний клієнт, і це
    # дефолт для всіх: щоб стати персоналом, потрібна явна дія, а не
    # відсутність заборони.
    #
    # Окремо від `Membership.role` навмисно: та роль про організацію
    # клієнта, ця — про платформу. В одному полі власник будь-якої
    # організації опинився б на один рядок від нашої адмінки.
    platform_role: Mapped[PlatformRole | None] = mapped_column(
        Enum(PlatformRole, name="platform_role", native_enum=False), nullable=True
    )

    # Мова інтерфейсу. Порожньо — успадковується від організації.
    #
    # Порожній рядок, а не NULL із дефолтом: різниця між «не обирав» і
    # «обрав англійську» реальна. Хто не обирав, поїде за організацією,
    # коли та змінить мову; хто обрав — ні.
    #
    # Рядок, а не enum у базі: перелік мов росте, і кожне додавання не
    # має бути міграцією типу. Значення валідує домен, а невідоме
    # прочитається як «не обрано» — див. `i18n.parse`.
    locale: Mapped[str] = mapped_column(String(16), default="", server_default="")
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status", native_enum=False),
        default=UserStatus.PENDING,
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Захист від підбору пароля. Лічильник на акаунті, а не на IP: змінити
    # адресу дешевше, ніж вгадати пароль, тож обмеження по IP зупиняє
    # випадкового перебірника й не зупиняє того, хто справді пробує.
    # Обмеження по IP теж потрібне, але як другий рубіж і в іншому шарі.
    failed_login_count: Mapped[int] = mapped_column(SmallInteger, default=0, server_default="0")
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), onupdate=_now
    )
    # М'яке видалення: жорстке забрало б із собою аудити чужої організації,
    # у якій людина була учасником. Запит на видалення даних — окремий
    # процес, а не каскад.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # `foreign_keys` обов'язковий: у memberships два ключі на users —
    # учасник і той, хто його запросив. Без явної вказівки SQLAlchemy не
    # може обрати, і падає на ініціалізації мапера, а не на запиті.
    memberships: Mapped[list[Membership]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        foreign_keys="Membership.user_id",
    )

    __table_args__ = (Index("ix_users_email_lower", func.lower(email), unique=True),)


class Organization(Base):
    """Власник бізнес-ресурсів: сайтів, аудитів, підписки, розкладів."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    # Людиночитаний ідентифікатор в адресах. Не використовується для
    # авторизації — вона завжди по id, бо slug може змінитися.
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Особистий простір, створений при реєстрації. Прапорець потрібен, щоб
    # не пропонувати видалити єдину організацію користувача й щоб
    # інтерфейс не показував перемикач там, де вибирати нема з чого.
    is_personal: Mapped[bool] = mapped_column(default=False)
    # Чим організація є для продукту: особистий простір, команда,
    # гостьова воронка або вже привласнена гостьова.
    #
    # Окремо від `is_personal` навмисно. Той прапорець відповідає на
    # питання «створена разом із людиною», і гостьова організація на
    # ньому виглядала б особистою для кожного, хто його читає, — зокрема
    # для правила «не пропонуй видалити єдину організацію».
    kind: Mapped[OrganizationKind] = mapped_column(
        Enum(OrganizationKind, name="organization_kind", native_enum=False),
        default=OrganizationKind.TEAM,
        server_default=OrganizationKind.TEAM.name,
        index=True,
    )
    # Мова організації: нею за замовчуванням складаються звіти, які
    # організація віддає далі — своєму керівництву або своїм клієнтам.
    #
    # Це не мова аудиту. Аудит мови не має взагалі: той самий запуск
    # віддається різними мовами різним читачам, і зміна цього поля не
    # змінює жодного виміряного факту.
    default_locale: Mapped[str] = mapped_column(
        String(16), default=DEFAULT_LOCALE.value, server_default=DEFAULT_LOCALE.value
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now(), onupdate=_now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    memberships: Mapped[list[Membership]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )


class Membership(Base):
    """Зв'язок особи з організацією та її роль у ній."""

    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[Role] = mapped_column(Enum(Role, name="membership_role", native_enum=False))

    invited_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    invited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Порожньо означає «запрошення не прийнято»: членство існує, доступу
    # ще немає. Без цього розділення запрошення довелося б тримати
    # окремою таблицею з тими самими полями.
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="memberships", foreign_keys=[user_id])
    organization: Mapped[Organization] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_membership_user_org"),
        # Рівно один власник на організацію. Перевірка в коді пережила б
        # рівно до першої гонки при передачі володіння.
        Index(
            "uq_membership_single_owner",
            "organization_id",
            unique=True,
            postgresql_where=role == Role.OWNER,
        ),
    )


class Session(Base):
    """Браузерна сесія.

    Непрозорий токен у httpOnly-cookie, а не JWT. Причина одна й
    практична: відкликання має спрацьовувати миттєво — при зміні пароля,
    при виході з усіх пристроїв, при підозрі на витік. JWT цього не вміє
    без списку відкликаних, тобто без тієї самої таблиці, тільки збоку.

    У базі лежить хеш токена. Витік дампа не дає можливості увійти.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    # Показується власнику в переліку активних сесій — це функція безпеки,
    # а не аналітика. Тому рядок, а не хеш: хеш нікому нічого не скаже.
    user_agent: Mapped[str] = mapped_column(String(200), default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship()


class ApiKey(Base):
    """Програмний доступ. Належить організації, а не людині.

    Ключ, виданий користувачеві, помирає разом із його звільненням —
    інтеграція падає в день, коли когось відключили від акаунта. Тому
    власник ключа — організація; хто його створив, лишається в
    `created_by_user_id` для розбору, а не для доступу.

    У базі хеш. Сам ключ показується один раз при створенні: якщо його
    можна подивитися пізніше, значить, він у нас у відкритому вигляді.
    """

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), default="")
    # Перші символи ключа. Показуються в переліку, щоб людина впізнала
    # свій ключ, не маючи можливості його відновити.
    prefix: Mapped[str] = mapped_column(String(16), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped[Organization] = relationship()


class PasswordReset(Base):
    """Одноразове посилання на встановлення нового пароля.

    Та сама доктрина, що в `Session` і `ApiKey`: у базі лежить лише хеш,
    тож дамп не дає можливості скинути чужий пароль. SHA-256 тут не
    економія на argon2, а правильний вибір — токен випадковий на 256
    бітів, і словникової атаки на нього не існує.

    Відмінність від усіх наявних токенів проєкту одна, і заради неї
    таблиця й існує: цей ОДНОРАЗОВИЙ. `used_at` — не `revoked_at`:
    перший каже «ним уже скористалися», другий — «його відкликали», і
    плутати їх не можна, бо перше настає саме тоді, коли все пройшло
    добре. Одноразовість тримає не код, а часткова UNIQUE-умова нижче:
    перевірка в Python програла б двом одночасним запитам.
    """

    __tablename__ = "password_resets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    # Момент використання. Поки NULL — токен живий.
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Момент скасування попереднього запиту новим. Окремо від `used_at`:
    # «замовили ще один лист» і «пароль змінено» — різні події, і в
    # розслідуванні їх треба розрізняти.
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship()

    __table_args__ = (
        # Один живий токен на людину. Часткова унікальність, а не перевірка
        # в коді: два одночасні запити на відновлення інакше створили б два
        # чинні посилання, і старий лист лишався б ключем.
        Index(
            "ux_password_resets_active_user",
            "user_id",
            unique=True,
            postgresql_where=text("used_at IS NULL AND superseded_at IS NULL"),
        ),
    )


__all__ = ["ApiKey", "Membership", "Organization", "PasswordReset", "Session", "User"]
