"""Транспорт пошти: протокол і три втілення.

Три, а не два, і кожне має свою причину:

* `SmtpMailer` — справжня доставка;
* `NullMailer` — пошти немає й вона ПРО ЦЕ КАЖЕ. Мовчазного успіху не
  буває: інакше людина чекала б листа, якого ніхто не надсилав;
* `CaptureMailer` — лист нікуди не летить, але його видно. Потрібен
  тестам і локальній розробці, де SMTP немає й бути не мусить.

Жодне з них не пише в журнал ані посилання, ані токена. Лист про
відновлення — це ключ від акаунта в один рядок; рядок у логах
перетворює доступ до логів на доступ до акаунтів.
"""

from __future__ import annotations

import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

import structlog

from app.core.config import settings

log = structlog.get_logger()


@dataclass(frozen=True, slots=True)
class Message:
    """Один лист. Одержувач — у повідомленні, а не в транспорті.

    Саме це відрізняє цей інтерфейс від контактного: адреса змінюється
    щоразу, тож вона властивість листа, а не налаштування процесу.
    """

    to: str
    subject: str
    text: str
    """Обовʼязкова частина. Поштовий клієнт без HTML лишається робочим."""
    html: str = ""


class Mailer(Protocol):
    name: str

    def available(self) -> bool: ...

    def send(self, message: Message) -> None:
        """Надіслати або кинути виняток. Мовчазної невдачі не буває."""
        ...


class NullMailer:
    """Пошта не налаштована. Відмова, а не тиша."""

    name = "null"

    def available(self) -> bool:
        return False

    def send(self, message: Message) -> None:
        raise RuntimeError("поштовий транспорт не налаштовано")


@dataclass
class CaptureMailer:
    """Лист лишається тут. Для тестів і для локальної розробки.

    Не `NullMailer`: той відмовляє, а цей приймає — і саме тому ним
    можна пройти сценарій до кінця, не піднімаючи SMTP. Якщо задано
    `MAIL_CAPTURE_DIR`, лист додатково лягає файлом `.eml`, який
    відкривається будь-яким поштовим клієнтом.
    """

    name: str = "capture"
    sent: list[Message] = field(default_factory=list)
    directory: Path | None = None

    def available(self) -> bool:
        return True

    def send(self, message: Message) -> None:
        self.sent.append(message)
        if self.directory is not None:
            self.directory.mkdir(parents=True, exist_ok=True)
            path = self.directory / f"{len(self.sent):04d}-{_slug(message.to)}.eml"
            path.write_bytes(bytes(_compose(message, sender=_sender())))
        # Тема й одержувач — так; тіло, посилання й токен — ніколи.
        log.info("mail_captured", to_domain=_domain(message.to), subject=message.subject)


class SmtpMailer:
    """Найменша конфігурація SMTP, яка справді працює."""

    name = "smtp"

    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
        use_tls: bool,
        timeout: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._sender = sender
        self._use_tls = use_tls
        self._timeout = timeout

    def available(self) -> bool:
        return True

    def send(self, message: Message) -> None:
        with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(_compose(message, sender=self._sender))
        log.info("mail_sent", to_domain=_domain(message.to), subject=message.subject)


def _sender() -> str:
    """Адреса відправника. Запасної немає навмисно.

    `no-reply@crawldy.ai` за замовчуванням виглядав турботою, а був
    пасткою: з чужого SMTP така адреса не проходить SPF і лист тихо
    осідає в спамі. У проді відсутність `MAIL_SENDER` тепер валить старт
    (див. `Settings._production_mail_is_configured`), локально —
    перехоплюється, а не надсилається.
    """
    if settings.mail_sender:
        return settings.mail_sender
    if settings.app_env == "prod":  # pragma: no cover — старт уже впав би
        raise RuntimeError("MAIL_SENDER не налаштовано")
    return "crawldy-local@localhost"


def is_temporary(exc: BaseException) -> bool:
    """Чи має сенс повторювати спробу.

    Розрізняти обовʼязково: повторювати відмову «такої скриньки немає»
    означає ще тричі постукати в ті самі зачинені двері, а НЕ повторити
    обрив зʼєднання означає втратити лист через секундну мережеву
    неприємність.

    Класифікація йде за кодом відповіді, а не за текстом: 4xx у SMTP
    означає «спробуйте пізніше», 5xx — «ні». Виняток без коду (обрив,
    таймаут, відмова в зʼєднанні) — тимчасовий за означенням: сервер не
    встиг сказати нічого.
    """
    if isinstance(exc, smtplib.SMTPAuthenticationError):
        # Дані для входу не стануть правильними від повтору.
        return False
    if isinstance(exc, smtplib.SMTPResponseException):
        return 400 <= exc.smtp_code < 500
    if isinstance(exc, smtplib.SMTPRecipientsRefused):
        codes = [code for code, _ in exc.recipients.values()]
        return all(400 <= code < 500 for code in codes) if codes else False
    return isinstance(exc, (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError))


def _domain(address: str) -> str:
    """Лише домен. Повна адреса в журналі — це персональні дані."""
    _, _, domain = address.partition("@")
    return domain or "?"


def _slug(address: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in address)[:60]


def _compose(message: Message, *, sender: str) -> EmailMessage:
    out = EmailMessage()
    out["From"] = sender
    out["To"] = message.to
    if settings.mail_reply_to:
        out["Reply-To"] = settings.mail_reply_to
    out["Subject"] = message.subject
    out.set_content(message.text)
    if message.html:
        out.add_alternative(message.html, subtype="html")
    return out


def build_mailer() -> Mailer:
    """Транспорт за конфігурацією.

    Без хоста поведінка РІЗНА за оточенням, і це навмисно. Локально
    відсутність SMTP не має зупиняти роботу над продуктом, тож лист
    перехоплюється. У проді та сама відсутність — це поламане
    відновлення пароля, і воно мусить бути видно одразу, а не тоді,
    коли клієнт не дочекається листа.
    """
    if settings.mail_smtp_host:
        return SmtpMailer(
            host=settings.mail_smtp_host,
            port=settings.mail_smtp_port,
            username=settings.mail_smtp_username or "",
            password=settings.mail_smtp_password or "",
            sender=_sender(),
            use_tls=settings.mail_smtp_tls,
        )
    # Перехоплення — ЛИШЕ локально. У staging воно було б гіршим за
    # відмову: середовище вдавало б робочу пошту, і дефект конфігурації
    # знайшовся б аж у проді.
    if settings.app_env != "local":
        return NullMailer()
    directory = Path(settings.mail_capture_dir) if settings.mail_capture_dir else None
    return CaptureMailer(directory=directory)
