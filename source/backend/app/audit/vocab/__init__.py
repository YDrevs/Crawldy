"""Словники, якими двигун упізнає, **що це за сторінка**.

## Це не локалізація

Найважливіше речення розділу: **мова продукту ≠ мова сайту**. Іспанський
сайт лишається іспанським, хоч би якою мовою користувач відкрив Crawldy, і
`/precios` має впізнаватися як сторінка цін для читача з Токіо так само,
як для читача з Мадрида.

Тому тут окремий тип, `ContentLanguage`, а не `i18n.Locale`. Не для
охайності: два різні поняття під одним типом одного дня передадуть одне
замість одного, і продукт почне впізнавати сторінки залежно від
налаштувань інтерфейсу. Помилка була б тихою — сторінка просто стала б
`UNKNOWN`, а з нею мовчки відпали б правила, що спираються на тип.

## Це покриття, а не текст

Словник — не переклад. Переклад можна відкласти: неперекладений рядок
видно. Непокрита мова не видно взагалі — аудит не помиляється, він
мовчить. Сайт іспанською просто не отримує частини правил, і в звіті це
нічим не відрізняється від сайту, у якого таких проблем немає.

Саме тому `coverage()` існує з першого дня, ще до самих словників: щоб
питання «які мови ми справді розуміємо» мало відповідь у коді, а не в
чиїйсь пам'яті.

## Стан сьогодні

Покриті англійська й українська — ті, на яких проєкт відкалібрований.
Решта оголошена й порожня. Додати мову = дописати словник у `words.py`,
не чіпаючи жодного чека: чек питає «чи це слово означає ціни», а не «чи
воно дорівнює pricing або ціни».
"""

from __future__ import annotations

from collections.abc import Iterable

from app.audit.vocab.enums import Concept, ContentLanguage
from app.audit.vocab.words import VOCABULARIES


# Мови, для яких словники справді заповнені.
#
# Рахується зі словників, а не оголошується списком: список розійшовся б
# із вмістом при першому ж додаванні, і `coverage()` брехала б саме тоді,
# коли на неї покладаються.
def covered(concept: Concept | None = None) -> frozenset[ContentLanguage]:
    """Мови, у яких є хоч одне слово для цього поняття (або для будь-якого)."""
    concepts = [concept] if concept is not None else list(Concept)
    return frozenset(
        language
        for language, words in VOCABULARIES.items()
        if any(words.get(c) for c in concepts)
    )


def coverage() -> dict[ContentLanguage, list[Concept]]:
    """Що саме ми вміємо впізнавати кожною мовою. Для звіту й для тесту."""
    return {
        language: [c for c in Concept if VOCABULARIES.get(language, {}).get(c)]
        for language in ContentLanguage
    }


def words_for(
    concept: Concept, languages: Iterable[ContentLanguage] | None = None
) -> frozenset[str]:
    """Усі слова поняття в заданих мовах; за замовчуванням — в усіх.

    Дефолт «в усіх» навмисно. Мова сайту заздалегідь невідома: заголовок
    `lang` бреше частіше, ніж каже правду, а адреса сторінки взагалі мови
    не має. Дешевше перевірити слово в кожній мові, ніж спершу вгадувати
    мову, а потім помилятися двічі.
    """
    chosen = list(languages) if languages is not None else list(ContentLanguage)
    return frozenset(
        word
        for language in chosen
        for word in VOCABULARIES.get(language, {}).get(concept, frozenset())
    )


def means(
    concept: Concept, word: str, *, languages: Iterable[ContentLanguage] | None = None
) -> bool:
    """Чи означає це слово задане поняття."""
    return word.lower() in words_for(concept, languages)


__all__ = [
    "VOCABULARIES",
    "Concept",
    "ContentLanguage",
    "coverage",
    "covered",
    "means",
    "words_for",
]
