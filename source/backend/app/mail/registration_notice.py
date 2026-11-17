"""Лист «хтось пробував зареєструватися на вашу пошту» — шістьма мовами.

Реєстрація на зайняту адресу відповідає 409, і це рішення власника:
людина одразу бачить «акаунт уже є — увійдіть». Ціна цього рішення —
адресу можна перевірити, чи вона зареєстрована. Лист каже власникові
адреси, що таку перевірку хтось зробив, і дає два шляхи: увійти або
відновити пароль, якщо це був він сам, але пароль забув.

Ні пароля, ні токена, ні адреси того, хто пробував, лист не містить:
ми не знаємо, хто це, а IP у листі — витік чужих даних, а не захист.
"""

from __future__ import annotations

from app.audit.i18n import Locale
from app.mail.copy import Letter, _escape

_SUBJECT: dict[Locale, str] = {
    Locale.UK: "Спроба реєстрації в Crawldy з вашою поштою",
    Locale.EN: "Someone tried to sign up to Crawldy with your email",
    Locale.DE: "Registrierungsversuch bei Crawldy mit Ihrer E-Mail",
    Locale.ES: "Intento de registro en Crawldy con tu correo",
    Locale.FR: "Tentative d'inscription à Crawldy avec votre e-mail",
    Locale.RU: "Попытка регистрации в Crawldy с вашей почтой",
}

_BODY: dict[Locale, str] = {
    Locale.UK: (
        "Хтось щойно спробував створити акаунт Crawldy з цією адресою.\n\n"
        "Акаунт на неї вже є, тож нового не створено і нічого не змінено.\n\n"
        "Якщо це були ви — просто увійдіть: {login}\n"
        "Забули пароль? Відновіть його тут: {reset}\n\n"
        "Якщо це були не ви, нічого робити не треба: ваш акаунт і пароль\n"
        "лишаються як були."
    ),
    Locale.EN: (
        "Someone just tried to create a Crawldy account with this address.\n\n"
        "An account already exists for it, so nothing was created or changed.\n\n"
        "If this was you, simply sign in: {login}\n"
        "Forgot your password? Reset it here: {reset}\n\n"
        "If this was not you, no action is needed: your account and password\n"
        "stay as they are."
    ),
    Locale.DE: (
        "Gerade hat jemand versucht, mit dieser Adresse ein Crawldy-Konto anzulegen.\n\n"
        "Für sie gibt es bereits ein Konto, daher wurde nichts angelegt oder geändert.\n\n"
        "Falls Sie das waren, melden Sie sich einfach an: {login}\n"
        "Passwort vergessen? Hier zurücksetzen: {reset}\n\n"
        "Falls Sie das nicht waren, ist nichts zu tun: Ihr Konto und Ihr\n"
        "Passwort bleiben unverändert."
    ),
    Locale.ES: (
        "Alguien acaba de intentar crear una cuenta de Crawldy con esta dirección.\n\n"
        "Ya existe una cuenta con ella, así que no se creó ni cambió nada.\n\n"
        "Si fuiste tú, simplemente inicia sesión: {login}\n"
        "¿Olvidaste la contraseña? Restablécela aquí: {reset}\n\n"
        "Si no fuiste tú, no tienes que hacer nada: tu cuenta y tu contraseña\n"
        "siguen igual."
    ),
    Locale.FR: (
        "Quelqu'un vient d'essayer de créer un compte Crawldy avec cette adresse.\n\n"
        "Un compte existe déjà pour elle : rien n'a été créé ni modifié.\n\n"
        "Si c'était vous, connectez-vous simplement : {login}\n"
        "Mot de passe oublié ? Réinitialisez-le ici : {reset}\n\n"
        "Si ce n'était pas vous, vous n'avez rien à faire : votre compte et votre\n"
        "mot de passe restent inchangés."
    ),
    Locale.RU: (
        "Кто-то только что попытался создать аккаунт Crawldy с этим адресом.\n\n"
        "Аккаунт на него уже есть, поэтому ничего не создано и не изменено.\n\n"
        "Если это были вы — просто войдите: {login}\n"
        "Забыли пароль? Восстановите его здесь: {reset}\n\n"
        "Если это были не вы, ничего делать не нужно: ваш аккаунт и пароль\n"
        "остаются прежними."
    ),
}

LOCALES: tuple[Locale, ...] = tuple(_SUBJECT)


def registration_attempt_letter(*, locale: Locale, login: str, reset: str) -> Letter:
    chosen = locale if locale in _SUBJECT else Locale.EN
    text = _BODY[chosen].format(login=login, reset=reset)
    html = (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;'
        'font-size:15px;line-height:1.6;color:#1b1b1b">'
        + "".join(f"<p>{_escape(part)}</p>" for part in text.split("\n\n") if part.strip())
        + "</div>"
    )
    return Letter(subject=_SUBJECT[chosen], text=text, html=html)
