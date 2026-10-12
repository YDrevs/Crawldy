"""Реєстрація, вхід, сесії, членство.

Доменні операції контексту ідентичності. Вони працюють із сесією
SQLAlchemy, але не знають ні про HTTP, ні про тарифи, ні про аудити:
питання «хто це» відповідається без жодного з них.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity import passwords
from app.identity.dto import OrganizationView, UserView
from app.identity.enums import PlatformRole, Role, UserStatus
from app.models.identity import Membership, Organization, Session, User

# Скільки живе сесія без поновлення. Тридцять днів — компроміс між
# «щотижня вводити пароль» і «вкрадений ноутбук лишається входом назавжди».
SESSION_TTL = timedelta(days=30)

# Довжина токена сесії в байтах до кодування.
TOKEN_BYTES = 32

# Після скількох невдалих спроб акаунт замикається і на скільки.
#
# Замикання акаунта — вимушений компроміс: воно ж дає стороннім спосіб
# зробити людині відмову в обслуговуванні, знаючи лише її пошту. Тому
# пауза коротка й скидається після успішного входу: мета — зробити
# перебір непрактичним, а не покарати власника.
MAX_FAILED_LOGINS = 10
LOCKOUT = timedelta(minutes=15)

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


class EmailTaken(ValueError):
    """Пошта вже зареєстрована."""


class NotAMember(PermissionError):
    """Користувач не належить до організації."""


def _now() -> datetime:
    return datetime.now(UTC)


def normalize_email(email: str) -> str:
    """Нижній регістр і без пробілів по краях.

    Крапки й `+теги` в Gmail навмисно не чіпаємо: «нормалізувати» їх
    означає вирішити за поштовий сервер, які адреси в нього однакові, і
    помилитися на кожному, крім Gmail.
    """
    return unicodedata.normalize("NFKC", email).strip().lower()


def slugify(value: str) -> str:
    ascii_only = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = _SLUG_STRIP.sub("-", ascii_only.lower()).strip("-")
    return slug[:48] or "org"


def hash_token(raw: str) -> str:
    """SHA-256 достатньо: токен випадковий, словникова атака неможлива.

    Argon2 тут був би не обережністю, а витратою: він захищає від підбору
    пароля з малою ентропією, а не випадкових 32 байтів.
    """
    return hashlib.sha256(raw.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Registration:
    """Що з'явилося при реєстрації. Особистий простір — одразу."""

    user: User
    organization: Organization
    membership: Membership


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(
        func.lower(User.email) == normalize_email(email), User.deleted_at.is_(None)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def unique_slug(session: AsyncSession, base: str) -> str:
    """Вільний slug: базовий, інакше з коротким суфіксом.

    Лічильник `-2`, `-3` не беремо навмисно: він розкриває, скільки
    організацій із такою назвою вже є.
    """
    candidate = slugify(base)
    for _ in range(5):
        exists = await session.scalar(select(Organization.id).where(Organization.slug == candidate))
        if exists is None:
            return candidate
        candidate = f"{slugify(base)}-{secrets.token_hex(3)}"
    return f"{slugify(base)}-{uuid.uuid4().hex[:8]}"


async def register(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str = "",
    organization_name: str | None = None,
) -> Registration:
    """Новий користувач і його особиста організація — однією транзакцією.

    Організація створюється одразу, а не «коли знадобиться команда».
    Інакше перший сайт довелося б прив'язати до користувача, а потім
    переносити — тобто зробити рівно те, чого архітектура уникає.
    """
    normalized = normalize_email(email)
    if await find_user_by_email(session, normalized) is not None:
        raise EmailTaken(normalized)

    user = User(
        email=normalized,
        password_hash=passwords.hash_password(password),
        display_name=display_name.strip()[:200],
        status=UserStatus.PENDING,
    )
    session.add(user)
    await session.flush()

    name = (organization_name or display_name or normalized.split("@")[0]).strip()[:200]
    organization = Organization(
        name=name or normalized.split("@")[0],
        slug=await unique_slug(session, name or normalized.split("@")[0]),
        is_personal=organization_name is None,
    )
    session.add(organization)
    await session.flush()

    membership = Membership(
        user_id=user.id,
        organization_id=organization.id,
        role=Role.OWNER,
        accepted_at=_now(),
    )
    session.add(membership)
    await session.flush()

    return Registration(user=user, organization=organization, membership=membership)


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User | None:
    """Користувач або None. Причину не розрізняємо назовні.

    «Такої пошти немає» проти «пароль невірний» — це безкоштовна
    перевірка існування акаунта для стороннього. Перевірку хеша робимо
    навіть тоді, коли користувача немає: інакше час відповіді сам скаже
    те, що ми відмовилися сказати словами.
    """
    user = await find_user_by_email(session, email)
    if user is None:
        passwords.verify(_DUMMY_HASH, password)
        return None
    if not user.status.can_sign_in:
        return None
    if user.locked_until is not None and user.locked_until > _now():
        # Хеш усе одно перевіряємо: без цього замкнений акаунт відповідав
        # би помітно швидше, і час відповіді сам сказав би, що адреса
        # існує й перебір уже йде.
        passwords.verify(user.password_hash, password)
        return None

    if not passwords.verify(user.password_hash, password):
        # Інкремент у базі, а не в Python: паралельні спроби читали те
        # саме значення й записували те саме «+1», тож десять одночасних
        # невдач рахувались як одна, і межа підбору не спрацьовувала.
        failed = await session.scalar(
            update(User)
            .where(User.id == user.id)
            .values(failed_login_count=User.failed_login_count + 1)
            .returning(User.failed_login_count)
        )
        if failed is not None and failed >= MAX_FAILED_LOGINS:
            user.locked_until = _now() + LOCKOUT
            user.failed_login_count = 0
        return None

    if passwords.needs_rehash(user.password_hash):
        # `rehash_existing`, а не `hash_password`: пароль уже прийнятий
        # колись і зараз доведений — перевіряти його на СЬОГОДНІШНЮ
        # межу довжини означало б замкнути людину за те, що ми підняли
        # вимогу після того, як вона зареєструвалась.
        user.password_hash = passwords.rehash_existing(password)
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = _now()
    return user


# Хеш неіснуючого пароля для вирівнювання часу відповіді.
_DUMMY_HASH = passwords.hash_password("x" * passwords.MIN_LENGTH)


@dataclass(frozen=True, slots=True)
class IssuedSession:
    """Сесія і її сирий токен. Токен існує лише тут і в cookie."""

    session: Session
    token: str


async def create_session(
    db: AsyncSession, *, user: User, user_agent: str = "", ttl: timedelta = SESSION_TTL
) -> IssuedSession:
    token = secrets.token_urlsafe(TOKEN_BYTES)
    record = Session(
        user_id=user.id,
        token_hash=hash_token(token),
        user_agent=user_agent[:200],
        expires_at=_now() + ttl,
        last_seen_at=_now(),
    )
    db.add(record)
    await db.flush()
    return IssuedSession(session=record, token=token)


async def resolve_session(db: AsyncSession, token: str) -> Session | None:
    """Чинна сесія або None. Прострочена й відкликана — однаково None.

    Так само None, коли власник більше не може входити (вимкнений чи
    видалений): вхід йому вже заборонено, а видана раніше сесія інакше
    жила б ще тридцять днів.
    """
    stmt = (
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(Session.token_hash == hash_token(token))
    )
    row = (await db.execute(stmt)).one_or_none()
    if row is None:
        return None
    record, user = row
    if record.revoked_at is not None or record.expires_at <= _now():
        return None
    if user.deleted_at is not None or not user.status.can_sign_in:
        return None
    return record


async def revoke_session(db: AsyncSession, token: str) -> bool:
    record = await resolve_session(db, token)
    if record is None:
        return False
    record.revoked_at = _now()
    return True


async def revoke_all_sessions(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    """Вихід з усіх пристроїв. Викликається й при зміні пароля."""
    stmt = select(Session).where(Session.user_id == user_id, Session.revoked_at.is_(None))
    records = (await db.execute(stmt)).scalars().all()
    for record in records:
        record.revoked_at = _now()
    return len(records)


async def membership_of(
    db: AsyncSession, *, user_id: uuid.UUID, organization_id: uuid.UUID
) -> Membership | None:
    """Прийняте членство. Запрошення без відповіді доступу не дає."""
    stmt = select(Membership).where(
        Membership.user_id == user_id,
        Membership.organization_id == organization_id,
        Membership.accepted_at.is_not(None),
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def organizations_of(db: AsyncSession, *, user_id: uuid.UUID) -> list[Organization]:
    stmt = (
        select(Organization)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(
            Membership.user_id == user_id,
            Membership.accepted_at.is_not(None),
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.created_at)
    )
    return list((await db.execute(stmt)).scalars().all())


async def transfer_ownership(
    db: AsyncSession, *, organization_id: uuid.UUID, to_user_id: uuid.UUID
) -> None:
    """Передача володіння — одна транзакція, без проміжку з двома власниками.

    Часткове виконання тут гірше за помилку: організація з двома
    власниками порушує обмеження бази, з нулем — лишається без того, хто
    може керувати білінгом.
    """
    new_owner = await membership_of(db, user_id=to_user_id, organization_id=organization_id)
    if new_owner is None:
        raise NotAMember(str(to_user_id))

    stmt = select(Membership).where(
        Membership.organization_id == organization_id, Membership.role == Role.OWNER
    )
    for current in (await db.execute(stmt)).scalars().all():
        current.role = Role.ADMIN
    await db.flush()

    new_owner.role = Role.OWNER
    await db.flush()


# ── перегляди для шарів вище ───────────────────────────────────────────────
#
# Назовні контекст віддає DTO, а не ORM-об'єкти: маршрут, який прийняв
# модель, починає залежати від схеми таблиці, і зміна колонки стає зміною
# контракту API.


async def view_user(db: AsyncSession, user_id: uuid.UUID) -> UserView | None:
    record = await db.get(User, user_id)
    return UserView.of(record) if record is not None else None


async def view_organization(
    db: AsyncSession, *, organization_id: uuid.UUID, role: Role
) -> OrganizationView | None:
    record = await db.get(Organization, organization_id)
    return OrganizationView.of(record, role) if record is not None else None


async def view_organizations_of(db: AsyncSession, *, user_id: uuid.UUID) -> list[OrganizationView]:
    """Організації користувача разом із його роллю в кожній."""
    stmt = (
        select(Organization, Membership.role)
        .join(Membership, Membership.organization_id == Organization.id)
        .where(
            Membership.user_id == user_id,
            Membership.accepted_at.is_not(None),
            Organization.deleted_at.is_(None),
        )
        .order_by(Organization.created_at)
    )
    rows = (await db.execute(stmt)).all()
    return [OrganizationView.of(org, role) for org, role in rows]


async def locale_of_user(db: AsyncSession, *, user_id: uuid.UUID) -> str:
    """Мова, яку користувач обрав. Порожньо — не обирав.

    Окрема функція, а не поле в контексті сесії: `api` не має права
    імпортувати моделі, і без неї маршрут діставав би налаштування через
    ORM в обхід цієї межі.
    """
    stmt = select(User.locale).where(User.id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none() or ""


async def locale_of_organization(db: AsyncSession, *, organization_id: uuid.UUID) -> str:
    """Мова організації: нею за замовчуванням складаються звіти."""
    stmt = select(Organization.default_locale).where(Organization.id == organization_id)
    return (await db.execute(stmt)).scalar_one_or_none() or ""


async def get_organization(db: AsyncSession, *, organization_id: uuid.UUID) -> Organization | None:
    """Організація за ідентифікатором. Для складання відповіді акаунта:
    `api` не має права ходити в моделі напряму."""
    return await db.get(Organization, organization_id)


async def update_preferences(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    display_name: str | None = None,
    locale: str | None = None,
) -> UserView | None:
    """Налаштування самого користувача. Не тариф і не організація.

    Код мови сюди приходить уже перевіреним схемою запиту: `identity` не
    має права знати перелік мов продукту — це словник двигуна, і залежність
    ідентичності від нього тест меж не пропускає. Порожній рядок дозволений
    і означає «не обирав»: така людина знову їде за мовою організації.
    """
    record = await db.get(User, user_id)
    if record is None:
        return None
    if display_name is not None:
        record.display_name = display_name.strip()[:200]
    if locale is not None:
        record.locale = locale
    await db.flush()
    return UserView.of(record)


async def platform_role_of(db: AsyncSession, *, user_id: uuid.UUID) -> PlatformRole | None:
    """Чи ця людина з команди Crawldy. Порожньо — звичайний клієнт."""
    stmt = select(User.platform_role).where(User.id == user_id)
    return (await db.execute(stmt)).scalar_one_or_none()
