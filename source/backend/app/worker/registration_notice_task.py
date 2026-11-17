"""Сповіщення власника адреси про спробу реєстрації на неї — у воркері.

Маршрут реєстрації вже відповів 409 (рішення власника: зрозуміла
відповідь людині важливіша за прихованість адреси). Тут лише лист тому,
чия адреса: хтось перевірив, що вона зареєстрована. SMTP повільний і
чужий, тому не в запиті; доставка й повтори — ті самі, що в листа
відновлення.
"""

from __future__ import annotations

from typing import Any

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import log
from app.identity import service
from app.mail import transport as mail
from app.mail.registration_notice import registration_attempt_letter
from app.worker.recovery_task import _deliver, _locale_of


def _links(locale_code: str) -> tuple[str, str]:
    """Посилання лише з НАШОЇ налаштованої адреси: нічого із запиту."""
    base = settings.public_app_url.rstrip("/")
    suffix = "" if locale_code == "en" else f"?lang={locale_code}"
    return f"{base}/login{suffix}", f"{base}/forgot{suffix}"


async def send_registration_notice_task(
    _ctx: dict[str, Any], email: str, lang: str = ""
) -> dict[str, str]:
    """Лист власнику адреси. Мовчки — коли акаунта немає або він вимкнений.

    Адреси в журналі немає: «хтось перевіряв цю адресу» — рівно те, що
    ми не хочемо розносити далі, ніж до її власника.
    """
    try:
        async with SessionLocal() as session:
            user = await service.find_user_by_email(session, email)
            if user is None or not user.status.can_sign_in:
                log.info("registration_notice_no_account")
                return {"status": "no_account"}
            profile_locale = user.locale or ""
    except Exception as exc:  # noqa: BLE001 — тип, не текст
        log.warning("registration_notice_lookup_failed", error=type(exc).__name__)
        return {"status": "lookup_failed"}

    locale = _locale_of(profile_locale, lang)
    login, reset = _links(locale.value)
    letter = registration_attempt_letter(locale=locale, login=login, reset=reset)
    message = mail.Message(to=email, subject=letter.subject, text=letter.text, html=letter.html)
    return {"status": await _deliver(message)}
