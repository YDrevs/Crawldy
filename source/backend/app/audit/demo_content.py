"""Чужий шаблонний вміст, який лишився на сайті клієнта.

Сайт на конструкторі приходить із демо-даними: вигаданою командою,
телефоном виду +8(123)985789, поштою на домені теми, службовими
частинами шаблону, виставленими як окремі сторінки. Частину з них
власник міняє, частину не помічає роками.

Для клієнта це дорожче за більшість технічних знахідок. Відвідувач
бачить вісім облич із чужими іменами й розуміє, що сайт зроблений
абияк, — а пошук і мовні моделі беруть ці сторінки за факти про
компанію. На smartkp.com.ua наш власний генератор llms.txt вносив
Mark Liuw і Angela Kwang у файл, який клієнт мав покласти на сайт для
ШІ: ми не просто не помічали чужий шаблон, ми складали з нього карту.

Кожен сигнал окремо помиляється. Українська компанія може мати
іноземних працівників; пошта на чужому домені буває справжньою. Тому
знахідка зʼявляється лише там, де сходяться щонайменше два незалежні
сигнали, а severity росте з їхньою кількістю.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.audit.page_kinds import PageType, path_words, type_of
from app.audit.types import PageSignals, SiteContext

# Назви тем, конструкторів і майданчиків. Зустрічаються в пошті, у тексті
# й у назвах сторінок, які власник ніколи не створював свідомо.
VENDOR_NAMES = frozenset({
    "seofy", "envato", "themeforest", "elementor", "wpbakery", "avada",
    "divi", "astra", "bricks", "themify", "woodmart", "flatsome", "betheme",
})

# Заглушки, які пишуть у демо-дані.
PLACEHOLDER_WORDS = frozenset({
    "lorem", "ipsum", "dolor", "yourdomain", "yoursite", "yourcompany",
    "johndoe", "janedoe", "yourname", "demo", "placeholder",
})

PLACEHOLDER_EMAIL_DOMAINS = frozenset({
    "example.com", "example.org", "mail.com", "domain.com", "yourdomain.com",
    "email.com", "test.com", "demo.com",
})

# Службові частини шаблону, які конструктор іноді лишає доступними.
TEMPLATE_PATH_WORDS = frozenset({
    "footer", "header", "elementor", "template-parts", "templatera",
    "sidebar", "popup", "megamenu",
})

# Телефон-заглушка: підряд зростаючі або однакові цифри.
_SEQUENTIAL = re.compile(r"(0123456|1234567|2345678|9876543)")
_REPEATED = re.compile(r"(\d)\1{5,}")
_LATIN_NAME = re.compile(r"^[A-Z][a-z]+(?:\s+[A-Z][a-z'’-]+)+$")


@dataclass(slots=True)
class DemoSignals:
    """Що саме виглядає чужим. Порожньо — сайт свій."""

    placeholder_contacts: list[str] = field(default_factory=list)
    vendor_mentions: list[str] = field(default_factory=list)
    template_pages: list[str] = field(default_factory=list)
    foreign_person_pages: list[str] = field(default_factory=list)

    @property
    def buckets(self) -> dict[str, list[str]]:
        return {
            "placeholder_contacts": self.placeholder_contacts,
            "vendor_mentions": self.vendor_mentions,
            "template_pages": self.template_pages,
            "foreign_person_pages": self.foreign_person_pages,
        }

    @property
    def kinds(self) -> int:
        """Скільки НЕЗАЛЕЖНИХ сигналів зійшлося.

        Незалежність — це різні докази, а не різні назви категорій. Поки
        рахувалися просто непорожні відра, одна адреса потрапляла у два
        з них і давала «два незалежні сигнали» сама з себе: на
        sparkracingtechnology.com це був власний запис блогу, у слузі
        якого трапилось слово конструктора. Умова MIN_SIGNALS при цьому
        формально виконувалась, а насправді доказ був один.

        Рахуємо найбільшу кількість категорій, яким можна роздати
        РІЗНІ докази. Категорій щонайбільше чотири, тож повний перебір
        тут дешевший за будь-яку евристику й не залежить від порядку.
        """
        buckets = [(name, set(items)) for name, items in self.buckets.items() if items]
        best = 0

        def walk(index: int, used: frozenset[str], taken: int) -> None:
            nonlocal best
            if taken + (len(buckets) - index) <= best:
                return          # решта не поліпшить результат
            if index == len(buckets):
                best = max(best, taken)
                return
            _, items = buckets[index]
            for item in sorted(items - used):
                walk(index + 1, used | {item}, taken + 1)
            # категорію можна й пропустити: її доказ уже зарахований іншій
            walk(index + 1, used, taken)

        walk(0, frozenset(), 0)
        return best

    def to_json(self) -> dict[str, Any]:
        # `independent_signals` поруч із самими доказами: читач має
        # бачити не лише що знайдено, а й скільки з цього незалежного.
        return {**self.buckets, "independent_signals": self.kinds}


def detect(ctx: SiteContext) -> DemoSignals:
    found = DemoSignals()
    known = ctx.known

    for email in getattr(known, "emails", []):
        domain = email.rsplit("@", 1)[-1].lower()
        local = email.split("@", 1)[0].lower()
        # Одна адреса дає рівно один сигнал. seofy@mail.com підпадає і під
        # домен-заглушку, і під назву теми, і якби вона рахувалась двічі,
        # правило про збіг незалежних сигналів не означало б нічого:
        # одного факту вистачало б на знахідку.
        if any(vendor in local or vendor in domain for vendor in VENDOR_NAMES):
            found.vendor_mentions.append(email)
        elif domain in PLACEHOLDER_EMAIL_DOMAINS or local in PLACEHOLDER_WORDS:
            found.placeholder_contacts.append(email)

    for phone in getattr(known, "phones", []):
        if _looks_fake(phone):
            found.placeholder_contacts.append(phone)

    site_is_latin = _mostly_latin(ctx)
    for page in ctx.ok_pages:
        words = path_words(page.url)
        if words & TEMPLATE_PATH_WORDS:
            found.template_pages.append(page.url)
        if words & VENDOR_NAMES:
            found.vendor_mentions.append(page.url)
        if not site_is_latin and _is_foreign_person_page(page):
            found.foreign_person_pages.append(page.url)

    return found


def _looks_fake(phone: str) -> bool:
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 7:
        return False
    return bool(_SEQUENTIAL.search(digits) or _REPEATED.search(digits))


def _mostly_latin(ctx: SiteContext) -> bool:
    """Якою абеткою написаний сам сайт.

    Для сайту латинкою іноземне імʼя нічого не означає. Сигнал працює
    лише там, де сторінки команди різко випадають з мови решти сайту.
    """
    home = ctx.home
    sample = (home.text[:2000] if home else "") or ""
    cyrillic = sum(1 for c in sample if "а" <= c.lower() <= "я" or c in "іїєґІЇЄҐ")
    return cyrillic < len(sample) * 0.1


def _is_foreign_person_page(page: PageSignals) -> bool:
    if type_of(page.url, page.title or "") is not PageType.PERSON:
        return False
    name = (page.title or "").split("-")[0].split("|")[0].strip()
    return bool(_LATIN_NAME.match(name))


__all__ = [
    "PLACEHOLDER_EMAIL_DOMAINS",
    "PLACEHOLDER_WORDS",
    "TEMPLATE_PATH_WORDS",
    "VENDOR_NAMES",
    "DemoSignals",
    "detect",
]
