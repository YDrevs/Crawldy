"""Видимі ознаки захисту форм від автоматизованого спаму.

## Що саме тут доводиться

Пасивне спостереження й нічого більше: ми читаємо розмітку, яку сайт
віддав сам, і кажемо, які клієнтські маркери анти-абюзу в ній видно.
Форму ми не надсилаємо, CAPTCHA не обходимо, rate limit не перевіряємо —
жодної дії, яка створила б звернення на чужому сайті.

Звідси й межа тверджень. Побачений віджет доводить, що провайдер
підключений **на клієнті**; він не доводить, що сервер перевіряє токен
(Google і Cloudflare прямо вимагають серверної перевірки, і віджет без
неї не захищає нічого). Відсутність маркера не доводить нічого взагалі:
захист може жити на сервері, у WAF або в невидимій reCAPTCHA v3.

## Чому не підрядок у HTML форми

Раніше ознаки шукались у `node.html` цілком — разом із видимим текстом.
Абзац «ми використовуємо reCAPTCHA» усередині форми зараховувався за
встановлений захист, а слово `trap` у тексті — за honeypot. Це той самий
клас помилки, що й «Пошук підрядка в HTML бреше» в CLAUDE.md.

Тому маркери шукаються лише в **атрибутах** елементів форми: клас, id,
name, `src`, `data-sitekey`. Текст сторінки не свідчить ні про що.

## Дві сили сигналу, і вони не рівні

* `form` — маркер усередині самої форми (віджет, iframe провайдера,
  поле відповіді). Це сигнал про **цю** форму.
* `page` — бібліотека провайдера підключена скриптом сторінки. Вона не
  доводить, що конкретна форма нею користується, але робить твердження
  «видимого захисту не виявлено» недоведеним: саме так виглядає
  невидима reCAPTCHA v3, де у формі до виконання JS немає нічого.

Тому сигнал рівня сторінки не оголошує форму захищеною, але й не дає
сказати про неї протилежне. Мовчання дешевше за хибне звинувачення.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse

# Провайдери, чиї маркери однозначні. Ключ — слаг у доказах і в каталозі
# повідомлень; він не перекладається й не змінюється разом із текстом.
#
# Джерела маркерів — публічна документація провайдерів на 2026-09:
# Cloudflare Turnstile (клас `cf-turnstile`, `challenges.cloudflare.com`),
# Google reCAPTCHA (`g-recaptcha`, `www.google.com/recaptcha`,
# `recaptcha.net`, поле `g-recaptcha-response`), hCaptcha (`h-captcha`,
# `hcaptcha.com`, поле `h-captcha-response`), Friendly Captcha
# (`frc-captcha`), ALTCHA (`altcha`).
PROVIDER_MARKERS: dict[str, tuple[str, ...]] = {
    "turnstile": ("cf-turnstile", "challenges.cloudflare.com"),
    "recaptcha": ("g-recaptcha", "recaptcha.net", "google.com/recaptcha"),
    "hcaptcha": ("h-captcha", "hcaptcha.com"),
    "friendly_captcha": ("frc-captcha", "friendly-challenge"),
    "altcha": ("altcha",),
}

# Атрибути, у яких маркер щось означає. Видимий текст сюди не входить
# навмисно: згадка провайдера в реченні не є його підключенням.
SIGNAL_ATTRIBUTES = (
    "class",
    "id",
    "name",
    "src",
    "data-sitekey",
    "data-callback",
    "data-action",
)

# Назви полів-приманок. Поле рахується honeypot'ом лише тоді, коли воно
# ще й приховане від людини: назва `trap` у видимому полі — не приманка.
HONEYPOT_NAMES = (
    "honeypot",
    "honey_pot",
    "hp_field",
    "_gotcha",
    "bot-field",
    "botfield",
    "trap",
    "nospam",
)

# Ознаки того, що поле сховане від людини. `type=hidden` сюди не входить:
# так само виглядає CSRF-токен, і плутати їх не можна.
HIDDEN_MARKERS = ("display:none", "display: none", "visibility:hidden", "opacity:0")


@dataclass(frozen=True, slots=True)
class Signal:
    """Один побачений маркер: хто, за чим і в якому представленні."""

    provider: str
    """Слаг провайдера або `honeypot`."""
    scope: str
    """`form` — усередині форми; `page` — бібліотека сторінки."""
    marker: str
    """Що саме збіглося: клас, хост скрипта, назва поля."""
    source: str
    """`static` — відповідь сервера; `rendered` — після виконання JS."""

    def to_json(self) -> dict[str, str]:
        return {
            "provider": self.provider,
            "scope": self.scope,
            "marker": self.marker,
            "source": self.source,
        }


@dataclass(slots=True)
class FormObservation:
    """Одна форма і все, що ми про її захист побачили."""

    identity: str
    """Безпечний селектор форми: `form#id`, `form[name=…]` або порядковий."""
    method: str
    action_scope: str
    signals: list[Signal] = field(default_factory=list)

    @property
    def providers(self) -> list[str]:
        """Провайдери, підключені в самій формі. Порядок стабільний."""
        seen: list[str] = []
        for signal in self.signals:
            if signal.scope == "form" and signal.provider not in seen:
                seen.append(signal.provider)
        return seen

    @property
    def protected(self) -> bool:
        """Чи є сигнал про ЦЮ форму. Бібліотека сторінки сюди не входить."""
        return bool(self.providers)

    @property
    def page_libraries(self) -> list[str]:
        """Провайдери, підключені сторінкою, але не видні в самій формі."""
        seen: list[str] = []
        for signal in self.signals:
            if signal.scope == "page" and signal.provider not in seen:
                seen.append(signal.provider)
        return seen

    @property
    def undetermined(self) -> bool:
        """Сказати «видимого захисту немає» не можна: бібліотека є.

        Саме так виглядає невидима reCAPTCHA v3 у статичній відповіді.
        """
        return not self.protected and bool(self.page_libraries)

    def to_json(self) -> dict[str, object]:
        return {
            "form": self.identity,
            "method": self.method,
            "action_scope": self.action_scope,
            "providers": self.providers,
            "page_libraries": self.page_libraries,
            "signals": [signal.to_json() for signal in self.signals],
        }


def markers_in(values: dict[str, str]) -> list[tuple[str, str]]:
    """Провайдери, чиї маркери є в атрибутах елемента.

    На вхід — лише значення атрибутів. Текст вузла сюди не потрапляє: це
    і є межа, яка відрізняє підключений віджет від згадки в реченні.
    """
    found: list[tuple[str, str]] = []
    for attribute in SIGNAL_ATTRIBUTES:
        raw = (values.get(attribute) or "").lower()
        if not raw:
            continue
        # Для `src` порівнюється хост і шлях: домен провайдера в адресі
        # скрипта однозначний, а от у query-рядку — вже ні.
        haystack = raw
        if attribute == "src":
            parsed = urlparse(raw)
            haystack = f"{parsed.netloc}{parsed.path}" or raw
        for provider, markers in PROVIDER_MARKERS.items():
            for marker in markers:
                if marker in haystack and (provider, marker) not in found:
                    found.append((provider, marker))
    return found


def is_honeypot(values: dict[str, str]) -> str | None:
    """Назва поля-приманки, якщо поле і зветься так, і сховане.

    Обидві умови обовʼязкові. Приманка, яку видно людині, приманкою не
    є; сховане поле зі звичайною назвою — це, найімовірніше, токен.
    """
    name = (values.get("name") or values.get("id") or "").lower()
    if not any(marker in name for marker in HONEYPOT_NAMES):
        return None
    style = (values.get("style") or "").replace(" ", "").lower()
    classes = (values.get("class") or "").lower()
    hidden = (
        (values.get("type") or "").lower() == "hidden"
        or any(marker.replace(" ", "") in style for marker in HIDDEN_MARKERS)
        or "hidden" in classes
        or "sr-only" in classes
        or "aria-hidden" in values
        or values.get("tabindex") == "-1"
    )
    return name if hidden else None
