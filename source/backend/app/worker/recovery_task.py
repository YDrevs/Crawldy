"""Доставка листа про відновлення пароля — у воркері, не в запиті.

Чому не в HTTP-запиті, хоч там було коротше. Три причини, і жодна не
косметична.

**Пошук акаунта — це вимірна робота.** Поки маршрут сам шукав
користувача й сам надсилав лист, невідома адреса поверталась одразу, а
відома — після зʼєднання з чужим SMTP-сервером. Відповідь у тілі була
ідентична, а час відповіді — ні, і саме за ним форма «забули пароль»
перетворювалась на перевіряльник, чи зареєстрована людина в сервісі.
Тепер маршрут не ходить у базу взагалі: він ставить задачу для БУДЬ-ЯКОЇ
адреси й нічого про неї не знає.

**SMTP синхронний і чужий.** Зʼєднання з поштовим сервером триває
секунди, а буває, що й таймаут. Тримати на ньому цикл подій анонімного
маршруту означає віддати зовнішньому сервісу право підвісити наш API.

**Повтор мусить бути керований.** Тимчасовий збій пошти має право на
другу спробу, але друга спроба НЕ МАЄ створювати другий токен: у
людини на руках уже перший, і скасування його новим зробило б робоче
посилання з листа мертвим. Тому токен створюється один раз, ДО циклу
повторів, а сама задача ніколи не кидає винятку — інакше повторив би її
ARQ, з нової сесії й з новим токеном.
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.audit.i18n import Locale
from app.audit.i18n import parse as parse_locale
from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import log
from app.identity import recovery
from app.mail import transport as mail
from app.mail.copy import reset_letter

# Скільки разів пробувати надіслати. Три — це перша спроба й дві
# повторні; більше не додає надійності, бо поштові сервери, які не
# відповіли за пів хвилини, зазвичай не відповідають і за п'ять, зате
# додає час, протягом якого задача тримає слот воркера.
MAX_SEND_ATTEMPTS = 3

# Пауза перед повтором подвоюється: 2 с, потім 4 с. Рівні паузи били б
# у перевантажений сервер із тією самою частотою, що й спричинила збій.
RETRY_BASE_DELAY_S = 2.0


def _reset_link(token: str, locale_code: str) -> str:
    """Посилання з НАШОЇ налаштованої адреси.

    Нічого із запиту сюди не потрапляє, крім коду мови зі скінченного
    переліку. Саме тому відкритого перенаправлення тут бути не може:
    щоб його влаштувати, треба змінити конфігурацію сервера.
    """
    base = settings.public_app_url.rstrip("/")
    suffix = "" if locale_code == "en" else f"&lang={locale_code}"
    return f"{base}/reset?token={token}{suffix}"


async def send_password_reset_task(
    _ctx: dict[str, Any], email: str, lang: str = ""
) -> dict[str, str]:
    """Знайти акаунт, видати токен, надіслати лист. Мовчки — коли нема кого.

    Повертає статус словом, і це єдине, що про цю задачу можна дізнатися
    ззовні. Ані адреси, ані токена, ані посилання в журналі немає: лист
    про відновлення — це ключ від акаунта в один рядок, і рядок у логах
    перетворив би доступ до логів на доступ до акаунтів.
    """
    try:
        issued = await _issue(email)
    except Exception as exc:  # noqa: BLE001 — тип, не текст
        # Виняток НЕ пробрасується: ARQ повторив би задачу й видав другий
        # токен. Збій бази тут означає, що листа не буде, і це краще за
        # два живі посилання, одне з яких людина ніколи не бачила.
        log.warning("password_reset_issue_failed", error=type(exc).__name__)
        return {"status": "issue_failed"}

    if issued is None:
        # Невідома, видалена або вимкнена адреса. Нормальний вхід, а не
        # помилка: маршрут ставить задачу, не знаючи, чи є такий акаунт.
        log.info("password_reset_no_account")
        return {"status": "no_account"}

    token, locale_code = issued
    locale = _locale_of(locale_code, lang)
    letter = reset_letter(
        locale=locale,
        link=_reset_link(token, locale.value),
        hours=max(1, settings.password_reset_ttl_minutes // 60),
    )
    message = mail.Message(
        to=email, subject=letter.subject, text=letter.text, html=letter.html
    )
    return {"status": await _deliver(message)}


def _locale_of(profile: str, requested: str) -> Locale:
    """Мова профілю, інакше мова сторінки запиту, інакше англійська.

    `parse` віддає `None` на невідомий код, і саме тому тут явний
    фолбек: у профілі може лежати мова, якої каталог листів не має, а
    `lang` приходить із запиту й довіряти йому не можна взагалі. Лист
    англійською — прийнятний результат; лист із `None` замість мови —
    падіння задачі й відсутній лист.
    """
    for code in (profile, requested):
        if code:
            parsed = parse_locale(code)
            if parsed is not None:
                return parsed
    return Locale.EN


async def _issue(email: str) -> tuple[str, str] | None:
    """Токен і мова профілю, або `None` для невідомої адреси.

    Сирий токен виходить звідси РІВНО раз і живе далі тільки в памʼяті
    цієї задачі та в листі. У базі лежить його SHA-256.
    """
    async with SessionLocal() as session:
        result = await recovery.request_reset(
            session,
            email=email,
            ttl_minutes=settings.password_reset_ttl_minutes,
        )
        if result is None:
            return None
        token = result.token
        locale_code = result.user_locale
        await session.commit()
    return token, locale_code


async def _deliver(message: mail.Message) -> str:
    """Надіслати з обмеженим повтором. Той самий лист, той самий токен.

    Токен сюди приходить готовим і всередині не змінюється — саме це й
    робить повтор безпечним. Провалений останній раз НЕ скасовує токена:
    таймаут SMTP не доводить, що лист не пішов, і скасування зробило б
    мертвим посилання, яке людина, можливо, вже тримає в пошті. Токен
    просто застаріє сам.
    """
    mailer = mail.build_mailer()
    if not mailer.available():
        # Сюди потрапляє staging чи прод без налаштованого SMTP. Прод без
        # нього взагалі не стартує, тож це передусім сигнал про staging.
        log.error("password_reset_mail_unconfigured", transport=mailer.name)
        return "unconfigured"

    for attempt in range(1, MAX_SEND_ATTEMPTS + 1):
        try:
            await asyncio.to_thread(mailer.send, message)
        except Exception as exc:  # noqa: BLE001 — тип, не текст
            # Тип винятку, не його текст: повідомлення поштових бібліотек
            # несуть адреси, імена скриньок і нутрощі сервера.
            temporary = mail.is_temporary(exc)
            log.warning(
                "password_reset_delivery_failed",
                error=type(exc).__name__,
                attempt=attempt,
                temporary=temporary,
            )
            if not temporary or attempt == MAX_SEND_ATTEMPTS:
                return "failed"
            await asyncio.sleep(RETRY_BASE_DELAY_S * 2 ** (attempt - 1))
        else:
            if attempt > 1:
                log.info("password_reset_delivered_after_retry", attempt=attempt)
            return "sent"
    return "failed"  # pragma: no cover — цикл завжди виходить раніше


__all__ = ["send_password_reset_task"]
