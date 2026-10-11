"""Лист КОРИСТУВАЧЕВІ: найменший інтерфейс, який справді потрібен.

Чому не `app/contact/delivery.py`. Той транспорт уміє рівно одне —
надіслати звернення НАМ: одержувач зашитий у конструктор із
`settings.contact_recipient`, а `Outgoing` несе поля форми, не тему й не
тіло. Лист про відновлення пароля йде щоразу на іншу адресу, з власною
темою й двома частинами. Розширити `Outgoing` означало б зробити
доставку звернень залежною від конфігурації відновлення пароля — дві
різні можливості продукту з одним вимикачем.

Тому тут окремий, навмисно вузький інтерфейс. Домен каже «надіслати
лист», а не «SMTP»: провайдера можна замінити, не торкаючись жодного
рядка логіки відновлення.
"""

from __future__ import annotations

from app.mail.transport import (
    CaptureMailer,
    Mailer,
    Message,
    NullMailer,
    SmtpMailer,
    build_mailer,
    is_temporary,
)

__all__ = [
    "CaptureMailer",
    "Mailer",
    "Message",
    "NullMailer",
    "SmtpMailer",
    "build_mailer",
    "is_temporary",
]
