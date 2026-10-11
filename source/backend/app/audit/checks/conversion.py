"""Чи видно на сторінці, що робити далі.

Аудит, який знаходить усе, крім причини, з якої сайт існує, лишається
технічним звітом. Комерційна сторінка має вести до дії: зателефонувати,
залишити заявку, покласти в кошик. Коли жодного способу немає, сторінка
може бути бездоганною за розміткою і при цьому не приносити нічого.

Тут два питання, на які відповідають зібрані дані, і жодного, на яке
довелося б здогадуватись. Оцінювати переконливість тексту чи розміщення
кнопки ми не беремось: це судження, а не вимірювання.

Модуль — tech. Він і без того найширший: захист форм, лічильники,
узгодженість контактів. Зробити «Конверсію» окремим напрямом було б
чесніше за назвою, але це перерозподіл ваг усіх шести й ще одна межа, за
якою бали непорівнянні. Перенести чек пізніше — один рядок у класі.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from app.audit import applicability, vocab
from app.audit.checks.base import Check, register
from app.audit.page_kinds import SELLS_SOMETHING, path_words
from app.audit.types import (
    Confidence,
    Effort,
    FormSignals,
    Issue,
    Module,
    PageSignals,
    Severity,
    SiteContext,
)
from app.audit.vocab.enums import Concept

# Слова адрес, які самі собою є наступним кроком.
# Словник живе у `vocab`: додати мову має бути правкою рядків, а не коду.
ACTION_PATHS = vocab.words_for(Concept.CALL_TO_ACTION)

# Заклики до дії в тексті посилання. Порівнюємо з початком рядка, бо
# «зателефонувати» і «зателефонуйте» — те саме, а «як ми телефонували
# клієнтам» — ні.
#
# Перелік живе у `vocab`, як і слова адрес, а не кортежем тут. Поки він був
# кортежем, він знав англійську й українсько-російські корені й не знав
# більше нічого, тож вирок про ОДНАКОВУ сторінку залежав від мови підпису:
# «Buy the pack» і «Купить пакет» були дією, а «Придбати пакет», «Paket
# kaufen», «Comprar el paquete» і «Acheter le pack» — ні. Другий словник
# поруч із `vocab` і був тим місцем, де мови розходились.
#
# `sorted` тут не косметика: `words_for` віддає `frozenset`, а порядок
# обходу множини рядків залежить від `PYTHONHASHSEED`. Відповідь `any`
# від порядку не залежить, але відтворюваність доказу — залежить.
ACTION_ANCHORS = tuple(sorted(vocab.words_for(Concept.CALL_TO_ACTION_TEXT)))

# Телефон у тексті: щонайменше девʼять цифр поспіль, можливо з пробілами,
# дужками й дефісами всередині.
PHONE_IN_TEXT = re.compile(r"(?<![\d/.,-])\+?\d[\d\s()\-]{7,}\d(?![\d/.,-])")

# Суцільний ряд цифр без плюса й розділювачів — не номер, а артикул чи
# рахунок. Тест `test_a_long_number_without_separators_is_not_a_phone`
# ловив саме це: «Артикул 900123456789» проходив як телефон компанії.
PHONE_SEPARATORS = " ()-"

# Скільки сторінок мають показати номер, щоб це був номер сайту, а не
# число, яке випадково склалося в текст статті.
MIN_PAGES_WITH_PHONE = 2

# Скільки тексту має бути на сторінці, щоб вважати, що ми її прочитали.
MIN_WORDS_TO_JUDGE = 80

MAX_LISTED = 5


@register
class NoWayToActCheck(Check):
    """Комерційна сторінка, з якої нікуди натиснути.

    Дивимось на сторінку після виконання скриптів: кнопку, домальовану
    браузером, людина бачить, і робити вигляд, що її немає, безглуздо.
    Це той рідкісний випадок, коли читач сторінки — не пошук і не
    асистент, а людина з мишею.
    """

    code = "cro.no_action"
    module = Module.TECH
    severity = Severity.HIGH
    weight = 3
    effort = Effort.MEDIUM
    confidence = Confidence.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            if ctx.type_of(page) not in SELLS_SOMETHING:
                continue
            # Лише сторінки, які ми справді відкрили в браузері. На
            # moz.com/products/pro у статичному HTML 53 внутрішні
            # посилання, і всі до одного в меню й підвалі: заклик там
            # домальовує скрипт. Сказати такій сторінці «звідси нікуди
            # натиснути» означало б описати наш краул, а не сайт.
            seen = ctx.rendered(page.url)
            if seen is None or not _we_actually_read_the_body(seen):
                continue
            if _offers_an_action(seen):
                continue
            yield self.issue(
                evidence={
                    "forms": 0,
                    "contacts_in_page_body": 0,
                    "action_links_in_page_body": 0,
                    "contacts_in_menu_or_footer": len(seen.tel_links)
                    + len(seen.mailto_addresses),
                    "internal_links": sum(1 for link in seen.links if link.is_internal),
                    "page_type": str(ctx.type_of(page)),
                },
                page_url=page.url,
            )


def _we_actually_read_the_body(page: PageSignals) -> bool:
    """Чи є в нас тіло сторінки, чи лише обвʼязка навколо порожнечі.

    Дві різні картини виглядають однаково: сторінка без кнопки й
    сторінка, тіло якої домальовує скрипт. На /pricing/sales у hubspot
    не було нічого взагалі, а на moz.com/products/pro — шістдесят
    посилань, і всі до одного в меню й підвалі. В обох випадках сказати
    «звідси нікуди натиснути» означало б описати наш краул.
    """
    if page.is_content_shell or page.word_count < MIN_WORDS_TO_JUDGE:
        return False
    return True


def _offers_an_action(page: PageSignals) -> bool:
    """Чи є дія в самій сторінці, а не в обвʼязці, спільній для сайту.

    Межа тут головна. Поки рахувалися посилання будь-де, чек не спрацював
    на жодній із сорока однієї комерційної сторінки восьми сайтів — і не
    міг: меню з «Контактами» має кожен сайт, тож відповідь була «дія є»
    завжди, а отже нічого не означала.
    """
    if any(_is_a_lead_form(form) for form in page.forms) or page.body_contacts:
        return True
    if any(_is_an_action("", label) for label in page.body_buttons):
        return True
    return any(
        _is_an_action(link.url, link.anchor)
        for link in page.links
        if link.is_internal and not link.in_chrome
    )


# Пошук по сайту — теж `<form>`, але звертанням він не є. Без цієї межі
# будь-яка сторінка з полем пошуку в шапці вважалася б такою, що дає
# людині спосіб зв'язатися.
SEARCH_ACTIONS = ("search", "/?s=", "znajti", "poshuk")


def _is_a_lead_form(form: FormSignals) -> bool:
    action = form.action.lower()
    if any(word in action for word in SEARCH_ACTIONS):
        return False
    # Одне поле, метод GET і жодної адреси призначення — це пошук у
    # шапці. Ознака тут саме адреса: форма на `/lead` лишається заявкою,
    # навіть якщо в ній одне поле.
    return not (not action and form.method.lower() == "get" and form.field_count <= 1)


def _is_an_action(url: str, anchor: str) -> bool:
    if path_words(url) & ACTION_PATHS:
        return True
    text = anchor.strip().lower()
    return any(text.startswith(phrase) or phrase in text for phrase in ACTION_ANCHORS)


@register
class PhoneNotTappableCheck(Check):
    """Номер надруковано, але подзвонити з телефону не можна.

    На екрані завширшки з долоню номер без `tel:` треба запамʼятати,
    перемкнутися в дзвінки й набрати вручну. Частина людей цього не
    робить, і втрачений дзвінок нічим не відрізняється від ненайденого
    сайту.

    Твердження стосується всього сайту, а не сторінки: посилання `tel:`
    ми не бачили ніде, а номер бачили на кількох.
    """

    code = "cro.phone_not_tappable"
    module = Module.TECH
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.LOW
    confidence = Confidence.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Клієнт натискає номер на публічній сторінці; номер у кабінеті
        # чи в адмінці до цього твердження не належить ані як доказ
        # проблеми, ані як доказ того, що її немає.
        relevant = {p.url for p in applicability.pages_for(ctx, self.code)}
        if any(page.tel_links for page in ctx.ok_pages if page.url in relevant):
            return
        found = [pair for pair in _phones_in_text(ctx) if pair[0] in relevant]
        if len(found) < MIN_PAGES_WITH_PHONE:
            return
        yield self.issue(
            params={"count": len(found)},
            evidence={
                "phones": [phone for _, phone in found][:MAX_LISTED],
                "pages": [url for url, _ in found][:MAX_LISTED],
                "tel_links": 0,
            },
        )


def _phones_in_text(ctx: SiteContext) -> list[tuple[str, str]]:
    """Сторінки, на яких надруковано щось схоже на номер телефону."""
    found: list[tuple[str, str]] = []
    for page in ctx.ok_pages:
        for match in PHONE_IN_TEXT.finditer(page.text):
            raw = match.group().strip()
            digits = sum(char.isdigit() for char in raw)
            if not 9 <= digits <= 15:
                continue
            if not raw.startswith("+") and not any(c in PHONE_SEPARATORS for c in raw):
                continue
            found.append((page.url, raw))
            break
    return found
