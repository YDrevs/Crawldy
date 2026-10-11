"""Звернення з контактної форми: прийняти, зберегти, спробувати доставити.

Порядок навмисний і незмінний:

1. перевірити поля (довжина, формат) — до будь-якої зовнішньої роботи;
2. перевірити антибот-токен на сервері;
3. **зберегти** звернення;
4. спробувати доставити.

Збереження стоїть перед доставкою, бо лист може не піти, а звернення
загубитися не має. Успіх людині показується після кроку 3 — після того,
як ми справді прийняли звернення й відповідаємо за нього, — а не після
того, як браузер намалював форму.

Приймання не торкається жодного комерційного права: контактна форма не
списує ані аудитів, ані підписки. Обмеження частоти тут — захист від
зловживання, і живе воно в лічильнику запитів, а не в квотах тарифу.
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.contact import antibot as antibot_module
from app.contact import delivery as delivery_module
from app.core.config import settings
from app.core.logging import log
from app.models.contact import ContactMessage

# Межі полів. Верхні — захист від сміття, нижні — від порожнього рядка з
# пробілів. Числа однакові для всіх мов: німецьке речення довше за
# англійське, але не в десять разів.
NAME_MAX = 120
EMAIL_MAX = 254
MESSAGE_MIN = 10
MESSAGE_MAX = 5000
SITE_MAX = 2048

EMAIL_SHAPE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
# Публічний домен: мітки з крапкою між ними. Те саме правило, що у формі
# запуску перевірки, — інакше та сама адреса приймалась би по-різному.
HOST_SHAPE = re.compile(
    r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$",
    re.IGNORECASE,
)

# Керівні символи, яким немає місця в тексті звернення. Переноси рядків
# і табуляція лишаються: людина форматує свій текст.
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class ContactError(Exception):
    """Звернення не прийнято. `reason` — стабільний код для клієнта."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# Стабільні коди. Клієнт мапить їх у свій локалізований текст; сирими на
# екран вони не потрапляють ніколи.
INVALID_NAME = "contact.invalid_name"
INVALID_EMAIL = "contact.invalid_email"
INVALID_MESSAGE = "contact.invalid_message"
INVALID_SITE = "contact.invalid_site"
ANTIBOT_REJECTED = "contact.antibot_rejected"
ANTIBOT_UNAVAILABLE = "contact.antibot_unavailable"
DELIVERY_UNAVAILABLE = "contact.delivery_unavailable"


@dataclass(frozen=True, slots=True)
class Submission:
    """Те, що прийшло з форми, ще не перевірене."""

    name: str
    email: str
    site_url: str
    message: str
    locale: str
    token: str
    honeypot: str
    ip: str


@dataclass(frozen=True, slots=True)
class Accepted:
    """Звернення прийнято. `reference` — короткий номер для людини."""

    id: uuid.UUID
    reference: str
    delivered: bool


def _clean(value: str) -> str:
    """Прибрати керівні символи й краї. Розмітку не інтерпретуємо ніде."""
    return _CONTROL.sub("", value or "").strip()


def normalize_site(raw: str) -> str:
    """Адреса сайту з того, як її пишуть люди. Порожнє — теж відповідь.

    Поле необовʼязкове, тож порожній рядок валідний. Схему дописуємо, як
    і у формі запуску перевірки: людина не зобовʼязана знати про http.
    """
    value = _clean(raw)
    if not value:
        return ""
    if len(value) > SITE_MAX:
        raise ContactError(INVALID_SITE)
    if not re.match(r"^https?://", value, re.IGNORECASE):
        value = f"https://{value}"
    host = re.sub(r"^https?://", "", value, flags=re.IGNORECASE).split("/")[0]
    if not HOST_SHAPE.match(host):
        raise ContactError(INVALID_SITE)
    return value


def validate(submission: Submission) -> Submission:
    """Серверна перевірка полів. Клієнтську не вважаємо доказом нічого."""
    name = _clean(submission.name)
    email = _clean(submission.email)
    message = _clean(submission.message)

    if not name or len(name) > NAME_MAX:
        raise ContactError(INVALID_NAME)
    if not email or len(email) > EMAIL_MAX or not EMAIL_SHAPE.match(email):
        raise ContactError(INVALID_EMAIL)
    if len(message) < MESSAGE_MIN or len(message) > MESSAGE_MAX:
        raise ContactError(INVALID_MESSAGE)

    return Submission(
        name=name,
        email=email,
        site_url=normalize_site(submission.site_url),
        message=message,
        locale=submission.locale,
        token=submission.token,
        honeypot=submission.honeypot,
        ip=submission.ip,
    )


def request_key(submission: Submission, *, window: datetime | None = None) -> str:
    """Ідентичність звернення: те саме за змістом і в тому самому вікні.

    Вікно — година. Людина, яка написала вдруге наступного дня, має
    право бути почутою; повтор тієї самої відправки за секунду — ні.
    """
    moment = (window or datetime.now(UTC)).strftime("%Y-%m-%dT%H")
    raw = "|".join(
        [submission.email.lower(), submission.message, submission.site_url, moment]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def hash_ip(ip: str) -> str:
    """Хеш адреси з сіллю. Самої адреси ми не зберігаємо."""
    if not ip:
        return ""
    return hashlib.sha256(f"{settings.ip_hash_salt}|{ip}".encode()).hexdigest()


def delivery_ready() -> bool:
    """Чи є куди доставляти. У проді без цього форму не показуємо."""
    return delivery_module.build_transport().available()


async def submit(
    db: AsyncSession,
    submission: Submission,
    *,
    antibot: antibot_module.AntiBotProvider | None = None,
    transport: delivery_module.Transport | None = None,
) -> Accepted:
    """Прийняти звернення. Виняток — відмова, і вона завжди пояснена кодом."""
    # 1. Приманка. Її заповнює лише автомат — людина цього поля не бачить.
    #    Відповідь назовні звичайна: бот не має дізнатися, на чому спіймався.
    if _clean(submission.honeypot):
        log.info("contact_honeypot")
        raise ContactError(ANTIBOT_REJECTED)

    # 2. Поля. Перевіряються до будь-якого зовнішнього виклику.
    clean = validate(submission)

    # 3. Антибот — на сервері. Токен браузера сам по собі не доказ.
    provider = antibot or antibot_module.build_provider()
    verification = await provider.verify(clean.token, remote_ip=clean.ip)
    if verification.verdict is antibot_module.Verdict.REJECTED:
        raise ContactError(ANTIBOT_REJECTED)
    if verification.verdict is antibot_module.Verdict.UNAVAILABLE:
        # Провайдер не відповів або не налаштований. У проді це відмова:
        # приймати звернення без перевірки означає лишити форму відкритою
        # для ботів. Поза продом перевірки може не бути взагалі, і форма
        # мусить лишатися придатною до роботи.
        if settings.app_env == "prod":
            raise ContactError(ANTIBOT_UNAVAILABLE)

    sender = transport or delivery_module.build_transport()
    if settings.app_env == "prod" and not sender.available():
        # Кнопка, яка нікуди не доставляє, — обман. У проді краще чесна
        # відмова, ніж мовчазна втрата звернення.
        raise ContactError(DELIVERY_UNAVAILABLE)

    # 4. Зберегти ДО доставки. Лист може не піти; звернення губитися не має.
    key = request_key(clean)
    row = ContactMessage(
        name=clean.name,
        email=clean.email,
        site_url=clean.site_url,
        message=clean.message,
        locale=clean.locale,
        ip_hash=hash_ip(clean.ip),
        request_key=key,
    )
    try:
        # SAVEPOINT, а не транзакція цілком: зіткнення з унікальним
        # індексом скасовує рівно цю вставку. `rollback()` тут відкотив
        # би все, що робилося в тому самому запиті, — включно з першим
        # зверненням, якого ми й шукаємо далі.
        async with db.begin_nested():
            db.add(row)
            await db.flush()
    except IntegrityError:
        # Той самий запит удруге: повтор мережею або друге натискання.
        # Ідемпотентність тримає індекс, а не сподівання на клієнта.
        existing = (
            await db.execute(
                select(ContactMessage).where(ContactMessage.request_key == key)
            )
        ).scalar_one()
        return Accepted(
            id=existing.id,
            reference=_reference(existing.id),
            delivered=existing.status == "delivered",
        )

    reference = _reference(row.id)

    # 5. Доставити. Невдача тут не скасовує прийняття: звернення в базі.
    delivered = False
    if sender.available():
        row.delivery_attempts += 1
        try:
            sender.send(
                delivery_module.Outgoing(
                    name=clean.name,
                    email=clean.email,
                    site_url=clean.site_url,
                    message=clean.message,
                    locale=clean.locale,
                    reference=reference,
                )
            )
            row.status = "delivered"
            row.delivered_at = datetime.now(UTC)
            delivered = True
        except Exception as exc:  # noqa: BLE001 — транспорт кидає що завгодно
            # Тип, а не текст: рядок винятку поштової бібліотеки може
            # нести адреси й службові подробиці.
            row.status = "failed"
            row.delivery_error = type(exc).__name__
            log.warning("contact_delivery_failed", error=type(exc).__name__)

    await db.flush()
    return Accepted(id=row.id, reference=reference, delivered=delivered)


def _reference(message_id: uuid.UUID) -> str:
    """Короткий номер звернення для листа й журналу."""
    return message_id.hex[:8].upper()
