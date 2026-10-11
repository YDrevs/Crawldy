"""Відновлення пароля й зміна відомого пароля.

Доменний шар: ані FastAPI, ані HTTP-кодів. Те саме правило, що в решті
`app/identity/`, і воно тут не формальність — ці ж функції має бути
можливо викликати з тесту без клієнта.

Три рішення, які варто знати, перш ніж щось міняти.

**Запит не каже, чи існує акаунт.** `request_reset` повертає токен для
відомої адреси й `None` для невідомої, але маршрут віддає ОДНАКОВУ
відповідь в обох випадках. Інакше форма «забули пароль» стає
безкоштовним перевіряльником, чи є в сервісі така людина.

**Одноразовість тримає база, не код.** `consume` оновлює рядок умовним
`UPDATE ... WHERE used_at IS NULL` і дивиться на кількість зачеплених
рядків. Перевірка «прочитали, побачили NULL, записали» програє двом
одночасним запитам: обидва прочитали б NULL.

**Новий запит скасовує попередній.** Людина, що натиснула «надішліть ще
раз», очікує, що старий лист більше не працює. Часткова UNIQUE-умова в
БД цього й вимагає — двох живих токенів на одну людину не буває.
"""

from __future__ import annotations

import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity import passwords, service
from app.models.identity import PasswordReset, User

# Той самий розмір, що в сесій, ключів API та гостьових токенів: 32 байти
# — 256 бітів ентропії. Префікса немає навмисно: токен їде в адресному
# рядку листа, і впізнаваний префікс у чужих логах ускладнив би життя
# власнику, нічого не давши нам.
TOKEN_BYTES = 32


@dataclass(frozen=True, slots=True)
class IssuedReset:
    """Створений запит. Сирий токен існує ЛИШЕ тут і в листі."""

    record: PasswordReset
    token: str
    user_locale: str
    """Мова ПРОФІЛЮ адресата. Тягнути `record.user` з маршруту не можна:
    лінива підвантажка в async-контексті — це помилка, а не запит."""


def _now() -> datetime:
    return datetime.now(UTC)


async def request_reset(
    db: AsyncSession, *, email: str, ttl_minutes: int
) -> IssuedReset | None:
    """Токен для відомої адреси, `None` для невідомої.

    `None` — не помилка й не виняток: невідома адреса це нормальний,
    очікуваний вхід. Маршрут мусить відповісти на нього так само, як на
    успіх.
    """
    user = await service.find_user_by_email(db, email)
    if user is None:
        return None
    if user.deleted_at is not None:
        return None
    if not user.status.can_sign_in:
        # Вимкненому акаунту пароль не відновлюють: новий пароль не дав
        # би входу, тож лист лише збив би людину з пантелику.
        return None

    await supersede_active(db, user_id=user.id)

    token = secrets.token_urlsafe(TOKEN_BYTES)
    record = PasswordReset(
        user_id=user.id,
        token_hash=service.hash_token(token),
        expires_at=_now() + timedelta(minutes=ttl_minutes),
    )
    db.add(record)
    await db.flush()
    return IssuedReset(record=record, token=token, user_locale=user.locale or "")


async def supersede_active(db: AsyncSession, *, user_id: uuid.UUID) -> int:
    """Скасувати всі живі токени людини. Скільки саме — повертаємо."""
    stmt = (
        update(PasswordReset)
        .where(
            PasswordReset.user_id == user_id,
            PasswordReset.used_at.is_(None),
            PasswordReset.superseded_at.is_(None),
        )
        .values(superseded_at=_now())
    )
    result: CursorResult[Any] = await db.execute(stmt)  # type: ignore[assignment]
    return int(result.rowcount or 0)


async def peek(db: AsyncSession, *, token: str) -> PasswordReset | None:
    """Чинний токен або `None`, БЕЗ споживання.

    Потрібен екрану: перш ніж показати форму нового пароля, варто
    сказати «посилання застаріло», а не приймати пароль і відмовити
    після. Прострочений, використаний, скасований і неіснуючий дають
    один і той самий `None` — розрізняти їх означало б підказувати, що
    токен колись існував.
    """
    if not token:
        return None
    stmt = select(PasswordReset).where(PasswordReset.token_hash == service.hash_token(token))
    record = (await db.execute(stmt)).scalar_one_or_none()
    if record is None:
        return None
    if record.used_at is not None or record.superseded_at is not None:
        return None
    if record.expires_at <= _now():
        return None
    return record


async def consume(db: AsyncSession, *, token: str, new_password: str) -> User | None:
    """Встановити новий пароль за токеном. `None` — токен не підійшов.

    Порядок навмисний: спершу політика пароля, потім атомарне
    споживання, і лише потім запис хеша. Якби токен гасився першим,
    слабкий пароль спалював би посилання й людина лишалася б замкненою.
    """
    record = await peek(db, token=token)
    if record is None:
        return None

    # Кидає `WeakPassword` ДО того, як щось змінилося.
    passwords.validate(new_password)

    # Умовний UPDATE: рядок дістається тому, хто перший. Другий
    # одночасний запит зачепить нуль рядків і отримає `None`.
    claimed: CursorResult[Any] = await db.execute(  # type: ignore[assignment]
        update(PasswordReset)
        .where(
            PasswordReset.id == record.id,
            PasswordReset.used_at.is_(None),
            PasswordReset.superseded_at.is_(None),
        )
        .values(used_at=_now())
    )
    if not claimed.rowcount:
        return None

    user = await db.get(User, record.user_id)
    if user is None:  # pragma: no cover — FK з ON DELETE CASCADE
        return None

    await _set_password(db, user=user, new_password=new_password)
    return user


async def change_password(
    db: AsyncSession, *, user_id: uuid.UUID, current_password: str, new_password: str
) -> bool:
    """Зміна відомого пароля. `False` — поточний пароль не підійшов.

    Приймає `user_id`, а не обʼєкт: маршрути не імпортують `app/models/`
    (межу стереже `tests/test_import_boundaries.py`), тож завантаження
    користувача належить сюди.

    Поточний пароль обовʼязковий навіть для вже автентифікованої людини:
    інакше вкрадена сесія перетворюється на вкрадений акаунт.
    """
    user = await db.get(User, user_id)
    if user is None:
        return False
    if not passwords.verify(user.password_hash, current_password):
        return False
    passwords.validate(new_password)
    await _set_password(db, user=user, new_password=new_password)
    return True


async def _set_password(db: AsyncSession, *, user: User, new_password: str) -> None:
    """Спільний хвіст обох шляхів.

    Три дії, і жодну не можна пропустити:

    1. хеш через `passwords.hash_password` — єдине місце з argon2;
    2. зняти блокування й лічильник невдач, як це робить успішний вхід:
       людина довела володіння поштою, тримати її замкненою безглуздо;
    3. відкликати ВСІ сесії. `revoke_all_sessions` існував у проєкті з
       коментарем «Викликається й при зміні пароля» і не мав жодного
       виклику — ось цей.
    """
    user.password_hash = passwords.hash_password(new_password)
    user.failed_login_count = 0
    user.locked_until = None
    await db.flush()
    await service.revoke_all_sessions(db, user_id=user.id)
    # Решта живих посилань більше не потрібна: пароль уже інший.
    await supersede_active(db, user_id=user.id)
