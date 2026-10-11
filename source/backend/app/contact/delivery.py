"""Доставка звернення команді. Провайдер за адаптером, домен без його слів.

Той самий контракт, що й у білінгу: домен знає «надіслати звернення», а
не «SMTP» чи «API поштового сервісу». Провайдер міняється налаштуванням,
а не правкою маршруту.

## Успіх ніколи не вигадується

`NullTransport` існує для локальної роботи й тестів і **чесно каже, що
нічого не надіслав**. Він не повертає успіх: рядок звернення лишається
`queued`, і це видно запитом. Прод із таким транспортом не стартує
контактної форми взагалі — гейт стоїть у `available()`, а не в маршруті,
щоб через нього проходили всі шляхи одразу.

## Адреса одержувача живе тут і ніде більше

Вона приходить із налаштувань сервера, не зберігається зі зверненням і
не потрапляє у відповідь API. Те, чого немає в клієнті, не збирають
поштові роботи.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from app.core.config import settings
from app.core.logging import log


@dataclass(frozen=True, slots=True)
class Outgoing:
    """Звернення у формі, придатній для надсилання."""

    name: str
    email: str
    site_url: str
    message: str
    locale: str
    reference: str
    """Ідентифікатор звернення в нашій базі — для відповіді людині."""


class Transport(Protocol):
    name: str

    def available(self) -> bool: ...

    def send(self, outgoing: Outgoing) -> None:
        """Надіслати або кинути виняток. Мовчазної невдачі не буває."""
        ...


class NullTransport:
    """Пошти немає. Звернення зберігається, лист не йде — і так і сказано."""

    name = "null"

    def available(self) -> bool:
        return False

    def send(self, outgoing: Outgoing) -> None:
        raise RuntimeError("поштовий транспорт не налаштовано")


class SmtpTransport:
    """Надсилання через SMTP. Найменша конфігурація, яка справді працює."""

    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        recipient: str,
        use_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._recipient = recipient
        self._use_tls = use_tls
        self._timeout = timeout

    def available(self) -> bool:
        return bool(self._host and self._sender and self._recipient)

    def _compose(self, outgoing: Outgoing) -> EmailMessage:
        message = EmailMessage()
        message["Subject"] = f"Crawldy contact — {outgoing.reference}"
        message["From"] = self._sender
        message["To"] = self._recipient
        # Відповідати треба людині, а не собі: `Reply-To` несе її адресу,
        # `From` лишається нашим — інакше поштова служба відкине лист як
        # підробку чужого домену.
        message["Reply-To"] = outgoing.email
        body = (
            f"Name: {outgoing.name}\n"
            f"Email: {outgoing.email}\n"
            f"Site: {outgoing.site_url or '—'}\n"
            f"Locale: {outgoing.locale}\n"
            f"Reference: {outgoing.reference}\n\n"
            f"{outgoing.message}\n"
        )
        message.set_content(body)
        return message

    def send(self, outgoing: Outgoing) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(self._compose(outgoing))
        log.info("contact_delivered", reference=outgoing.reference, transport=self.name)


def build_transport() -> Transport:
    """Транспорт за конфігурацією. Без хоста або адрес — його немає."""
    if not settings.contact_smtp_host or not settings.contact_recipient:
        return NullTransport()
    return SmtpTransport(
        host=settings.contact_smtp_host,
        port=settings.contact_smtp_port,
        username=settings.contact_smtp_username or "",
        password=settings.contact_smtp_password or "",
        sender=settings.contact_sender or settings.contact_recipient,
        recipient=settings.contact_recipient,
        use_tls=settings.contact_smtp_tls,
    )
