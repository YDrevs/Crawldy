"""Текст листа про відновлення пароля — шістьма мовами.

Чому окремий каталог, а не наявні. `app/audit/i18n` тримає знахідки
аудиту (чотири поля на ключ, і тести перевіряють саме їх форму),
`app/report/i18n` — каркас документа. Тема й тіло листа не лягають у
жодну з цих форм, а вкласти їх силоміць означало б зіпсувати перевірки,
які там уже працюють.

Мова листа береться з ПРОФІЛЮ адресата, а не із запиту. Запит міг піти
з чужого пристрою чи з іншої мовної версії сайту; людина ж читатиме
лист у своїй пошті. Коли профіль мови не має, лишається мова сторінки,
з якої прийшов запит, — це краще за англійську за замовчуванням.

Посилання підставляється рівно один раз, у `{link}`. Жоден рядок тут не
містить ані токена, ані адреси — тільки шаблон.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.audit.i18n import Locale

# Скільки годин живе посилання, підставляється в `{hours}`. Рядок про
# строк обовʼязковий: лист, який не каже, доки він чинний, змушує
# людину гадати, чому посилання «раптом» перестало працювати.


@dataclass(frozen=True, slots=True)
class Letter:
    subject: str
    text: str
    html: str


_SUBJECT: dict[Locale, str] = {
    Locale.UK: "Відновлення пароля Crawldy",
    Locale.EN: "Reset your Crawldy password",
    Locale.DE: "Crawldy-Passwort zurücksetzen",
    Locale.ES: "Restablecer tu contraseña de Crawldy",
    Locale.FR: "Réinitialiser votre mot de passe Crawldy",
    Locale.RU: "Восстановление пароля Crawldy",
}

_BODY: dict[Locale, str] = {
    Locale.UK: (
        "Ви (або хтось) попросили відновити пароль до Crawldy.\n\n"
        "Щоб установити новий пароль, перейдіть за посиланням:\n"
        "{link}\n\n"
        "Посилання діє {hours} год. і спрацює лише один раз.\n\n"
        "Якщо ви цього не просили, нічого робити не треба: пароль\n"
        "лишається чинним, а посилання просто застаріє."
    ),
    Locale.EN: (
        "Someone asked to reset the password for your Crawldy account.\n\n"
        "To set a new password, open this link:\n"
        "{link}\n\n"
        "The link is valid for {hours} h and works only once.\n\n"
        "If this was not you, no action is needed: your password stays\n"
        "as it is and the link will simply expire."
    ),
    Locale.DE: (
        "Jemand hat angefragt, das Passwort für Ihr Crawldy-Konto\n"
        "zurückzusetzen.\n\n"
        "Um ein neues Passwort zu setzen, öffnen Sie diesen Link:\n"
        "{link}\n\n"
        "Der Link gilt {hours} Std. und funktioniert nur einmal.\n\n"
        "Falls Sie das nicht waren, müssen Sie nichts tun: Ihr Passwort\n"
        "bleibt unverändert und der Link läuft einfach ab."
    ),
    Locale.ES: (
        "Alguien ha solicitado restablecer la contraseña de tu cuenta\n"
        "de Crawldy.\n\n"
        "Para establecer una contraseña nueva, abre este enlace:\n"
        "{link}\n\n"
        "El enlace es válido {hours} h y funciona una sola vez.\n\n"
        "Si no has sido tú, no hace falta hacer nada: tu contraseña\n"
        "sigue igual y el enlace caducará por sí solo."
    ),
    Locale.FR: (
        "Quelqu'un a demandé la réinitialisation du mot de passe de\n"
        "votre compte Crawldy.\n\n"
        "Pour définir un nouveau mot de passe, ouvrez ce lien :\n"
        "{link}\n\n"
        "Le lien est valable {hours} h et ne fonctionne qu'une fois.\n\n"
        "Si vous n'êtes pas à l'origine de cette demande, il n'y a rien\n"
        "à faire : votre mot de passe reste inchangé et le lien expirera."
    ),
    Locale.RU: (
        "Кто-то запросил восстановление пароля к аккаунту Crawldy.\n\n"
        "Чтобы задать новый пароль, откройте ссылку:\n"
        "{link}\n\n"
        "Ссылка действует {hours} ч. и сработает только один раз.\n\n"
        "Если это были не вы, делать ничего не нужно: пароль остаётся\n"
        "прежним, а ссылка просто устареет."
    ),
}

_BUTTON: dict[Locale, str] = {
    Locale.UK: "Установити новий пароль",
    Locale.EN: "Set a new password",
    Locale.DE: "Neues Passwort setzen",
    Locale.ES: "Establecer nueva contraseña",
    Locale.FR: "Définir un nouveau mot de passe",
    Locale.RU: "Задать новый пароль",
}

LOCALES: tuple[Locale, ...] = (Locale.UK, Locale.EN, Locale.DE, Locale.ES, Locale.FR, Locale.RU)


def _escape(value: str) -> str:
    """Мінімальне екранування для HTML-частини.

    Посилання будуємо ми самі з налаштованої адреси й власного токена,
    тож чужого тексту тут не буває. Екранування стоїть на випадок, коли
    наступна правка підставить сюди щось із запиту.
    """
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def reset_letter(*, locale: Locale, link: str, hours: int) -> Letter:
    """Тема, текстова й HTML-частини одного листа.

    Текстова частина не «запасна»: поштові клієнти без HTML і
    корпоративні шлюзи, що вирізають розмітку, лишаються робочими.
    """
    chosen = locale if locale in _SUBJECT else Locale.EN
    text = _BODY[chosen].format(link=link, hours=hours)
    safe = _escape(link)
    html = (
        '<div style="font-family:system-ui,-apple-system,Segoe UI,sans-serif;'
        'font-size:15px;line-height:1.6;color:#1b1b1b">'
        + "".join(f"<p>{_escape(part)}</p>" for part in text.split("\n\n") if part.strip())
        + f'<p><a href="{safe}" '
        'style="display:inline-block;padding:10px 18px;border-radius:8px;'
        'background:#007c82;color:#fff;text-decoration:none">'
        + _escape(_BUTTON[chosen])
        + "</a></p></div>"
    )
    return Letter(subject=_SUBJECT[chosen], text=text, html=html)
