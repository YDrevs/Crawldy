"""Legacy-аналітик: сторінки — дані, а цитата мусить бути на сторінці.

Цей шар уміє створити знахідку (`llm.unstated_facts`), тож вплив тексту
сайту на модель — це вплив на бал. Цитата, якої немає в тексті вказаної
сторінки, — вигадка моделі або результат інʼєкції, і як доказ у звіт вона
не йде.
"""

from __future__ import annotations

from typing import Any

from app.audit.llm import anthropic_analyst as module
from app.core.untrusted import UNTRUSTED_NOTICE

PAGES = [
    ("https://a.example/", "Home", "We bake sourdough   bread in LVIV every morning."),
    ("https://a.example/prices", "Prices", "Loaf — 80 UAH."),
]


def _analyst(answer: dict[str, Any], seen: list[str]) -> module.AnthropicAnalyst:
    analyst = module.AnthropicAnalyst(model="test")

    async def fake_ask(system: str, prompt: str, schema: dict[str, Any]) -> dict[str, Any]:
        seen.extend([system, prompt])
        return answer

    analyst._ask = fake_ask  # type: ignore[method-assign]
    return analyst


async def test_a_quote_found_on_its_page_is_kept() -> None:
    answer = {
        "facts": [
            {"key": "offering", "stated": True, "quote": "we bake sourdough bread",
             "url": "https://a.example/"},
        ],
    }
    facts = await _analyst(answer, []).facts("https://a.example", PAGES)
    offering = next(f for f in facts.facts if f.key == "offering")
    assert offering.quote == "we bake sourdough bread"
    assert offering.page_url == "https://a.example/"


async def test_an_invented_quote_is_not_used_as_evidence() -> None:
    answer = {
        "facts": [
            {"key": "location", "stated": True, "quote": "Based in Kyiv",
             "url": "https://a.example/"},
            {"key": "pricing", "stated": True, "quote": "Loaf — 80 UAH.",
             "url": "https://elsewhere.example/"},
        ],
    }
    facts = await _analyst(answer, []).facts("https://a.example", PAGES)
    by_key = {f.key: f for f in facts.facts}
    # Мовчання моделі вважаємо «сказано» — тут так само: stated лишається,
    # але неперевірна цитата й чужа адреса доказом не стають.
    assert by_key["location"].stated is True
    assert by_key["location"].quote == ""
    assert by_key["pricing"].quote == ""
    assert by_key["pricing"].page_url == ""


async def test_pages_go_to_the_model_as_untrusted_data() -> None:
    seen: list[str] = []
    await _analyst({"facts": []}, seen).facts("https://a.example", PAGES)
    system, prompt = seen
    assert UNTRUSTED_NOTICE in system
    assert prompt.count("<untrusted ") == 2


async def test_every_page_prompt_is_marked() -> None:
    for system in (module.PAGE_SYSTEM, module.BRIEF_SYSTEM, module.FACTS_SYSTEM, module.OWNER_SYSTEM):
        assert UNTRUSTED_NOTICE in system
