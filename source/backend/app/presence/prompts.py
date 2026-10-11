"""Затверджений набір промптів: 12 небрендових + 3 брендові, версійовано.

Генерація детермінована — шаблони від фактів, без моделі. Це рішення,
а не спрощення: набір мусить бути відтворюваним, версійованим і
перевірним лінтом; згенерований моделлю набір не був би жодним із
трьох.

Лінт упередженості — жорсткий: небрендовий промпт, у якому трапився
бренд, аліас чи домен, не проходить. Промпти, підігнані під те, щоб
бренд знаходився, зробили б вимірювання виміром нас самих — той самий
клас дефекту, що й пошук підрядка в HTML.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.presence.contracts import (
    PresencePrompt,
    PromptCategory,
    PromptSet,
    Segment,
)

# Версія правил генерації. Зміна шаблонів чи складу — нова версія, і
# історія через цю межу непорівнянна (те саме правило, що detector_version).
PROMPT_SET_RULES = "p0-1"

# Версія інструкції явного режиму. Вона додається до тексту промпту при
# надсиланні (сам набір лишається p0-1) і записується в спостереження
# через точний надісланий текст.
MODE_RULES = "m1"

# Інструкція явного (заземленого) режиму: просить актуальну відповідь із
# джерелами, НЕ називає бренд і НЕ підказує бажану відповідь — лінт
# упередженості застосовується до підсумкового тексту так само.
_EXPLICIT_SUFFIX: dict[str, str] = {
    "en": (" Please search the web for current information and base your "
           "answer on up-to-date sources, citing where the information "
           "comes from."),
    "uk": (" Будь ласка, пошукай актуальну інформацію в інтернеті й "
           "спирайся на свіжі джерела, вказавши, звідки взято відповідь."),
}


def explicit_suffix(language: str) -> str:
    """Суфікс явного режиму мовою промпту; невідома мова — англійською."""
    return _EXPLICIT_SUFFIX.get(language, _EXPLICIT_SUFFIX["en"])


@dataclass(slots=True, frozen=True)
class PromptFacts:
    """Факти для генерації. Бренд — окремо: він потрібен лінту й
    брендовому сегменту, але не сміє потрапити в небрендові тексти."""

    brand: str
    brand_aliases: tuple[str, ...]
    domain: str
    category: str               # «стоматологічна клініка», «CRM software»
    services: tuple[str, ...]   # до 3 конкретних послуг/продуктів
    location: str | None        # місто/регіон, якщо бізнес локальний
    language: str               # мова промптів, напр. "uk" або "en"


class PromptBiasError(ValueError):
    """Небрендовий промпт містить бренд/аліас/домен."""


# Шаблони за мовами. Дві мови в P0 — українська й англійська; інша мова
# сайту падає на англійську (чесніше, ніж машинний шаблон невідомою нам
# мовою). Розширення — додавання словника, не зміна коду.
_TEMPLATES: dict[str, dict[str, list[str]]] = {
    "en": {
        "category": [
            "What are the best {category} options{loc_suffix}?",
            "Recommend a reliable {category}{loc_suffix}.",
            "Top {category} choices{loc_suffix} — what should I consider?",
            "Which {category} would you recommend and why?",
            "How do I pick a good {category}? Name a few worth looking at.",
        ],
        "need": [
            "I need help with {service}. What are my options?",
            "How do I choose a provider for {service}?",
            "What should I look for when buying {service}?",
        ],
        "comparison": [
            "Compare popular providers of {service}.",
            "What are the leading alternatives for {category}?",
        ],
        "informational": [
            "How does {service} usually work?",
            "What does {category} typically cost?",
        ],
        "local": [
            "Where can I find {category} in {location}?",
        ],
        "branded": [
            "What is {brand}?",
            "Is {brand} trustworthy? What do people say about it?",
            "Tell me about {brand} and what it offers.",
        ],
    },
    "uk": {
        "category": [
            "Які найкращі варіанти: {category}{loc_suffix}?",
            "Порадь надійну компанію: {category}{loc_suffix}.",
            "Топ пропозицій у ніші «{category}»{loc_suffix} — на що зважати?",
            "Кого б ти порадив у категорії «{category}» і чому?",
            "Як обрати хорошу компанію ({category})? Назви кілька вартих уваги.",
        ],
        "need": [
            "Мені потрібно: {service}. Які є варіанти?",
            "Як обрати виконавця для «{service}»?",
            "На що звертати увагу, замовляючи «{service}»?",
        ],
        "comparison": [
            "Порівняй відомих постачальників послуги «{service}».",
            "Які провідні альтернативи в ніші «{category}»?",
        ],
        "informational": [
            "Як зазвичай працює «{service}»?",
            "Скільки зазвичай коштує «{category}»?",
        ],
        "local": [
            "Де знайти «{category}» у місті {location}?",
        ],
        "branded": [
            "Що таке {brand}?",
            "Чи варто довіряти {brand}? Що про них кажуть?",
            "Розкажи про {brand} і що вони пропонують.",
        ],
    },
}

_CATEGORY_QUOTA: tuple[tuple[PromptCategory, int], ...] = (
    (PromptCategory.CATEGORY, 4),
    (PromptCategory.NEED, 3),
    (PromptCategory.COMPARISON, 2),
    (PromptCategory.INFORMATIONAL, 2),
    (PromptCategory.LOCAL, 1),
)


def _alias_patterns(facts: PromptFacts) -> list[re.Pattern[str]]:
    tokens = {facts.brand, *facts.brand_aliases, facts.domain}
    tokens |= {facts.domain.removeprefix("www.")}
    return [
        re.compile(rf"(?<!\w){re.escape(t)}(?!\w)", re.IGNORECASE)
        for t in tokens if t
    ]


def lint_unbranded(text: str, facts: PromptFacts) -> None:
    """Кидає PromptBiasError, якщо небрендовий текст згадує бренд."""
    for pattern in _alias_patterns(facts):
        if pattern.search(text):
            raise PromptBiasError(
                f"небрендовий промпт містить бренд/домен: {pattern.pattern}"
            )


def build_prompt_set(facts: PromptFacts) -> PromptSet:
    """12 небрендових + 3 брендові. Детерміновано за фактами."""
    lang = facts.language if facts.language in _TEMPLATES else "en"
    templates = _TEMPLATES[lang]
    loc_suffix = ""
    if facts.location:
        loc_suffix = (f" in {facts.location}" if lang == "en"
                      else f" у місті {facts.location}")

    services = list(facts.services) or [facts.category]

    def _fill(template: str, service_i: int) -> str:
        return template.format(
            category=facts.category,
            service=services[service_i % len(services)],
            location=facts.location or "",
            loc_suffix=loc_suffix,
            brand=facts.brand,
        ).strip()

    prompts: list[PresencePrompt] = []
    for category, quota in _CATEGORY_QUOTA:
        pool = templates[category.value]
        offset = 0
        if category is PromptCategory.LOCAL and not facts.location:
            # Без локації локальний промпт недоречний — квота йде
            # категорійному пулу (з відступом, щоб текст не дублювався),
            # і набір лишається з 12 небрендових.
            pool = templates[PromptCategory.CATEGORY.value]
            category = PromptCategory.CATEGORY
            offset = 4
        for i in range(quota):
            text = _fill(pool[(offset + i) % len(pool)], i)
            lint_unbranded(text, facts)
            ordinal = sum(1 for p in prompts if p.category is category) + 1
            prompts.append(PresencePrompt(
                prompt_id=f"{category.value}-{ordinal}",
                text=text,
                category=category,
                segment=Segment.UNBRANDED,
                language=lang,
            ))

    for i, template in enumerate(templates["branded"], start=1):
        prompts.append(PresencePrompt(
            prompt_id=f"branded-{i}",
            text=_fill(template, 0),
            category=PromptCategory.BRANDED,
            segment=Segment.BRANDED,
            language=lang,
        ))

    return PromptSet(version=f"{PROMPT_SET_RULES}:{lang}", prompts=tuple(prompts))
