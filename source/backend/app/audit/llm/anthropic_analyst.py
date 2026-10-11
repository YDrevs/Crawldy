"""Семантичний аналіз через Anthropic API.

Пакет `anthropic` імпортується ліниво, всередині функції — як і Playwright.
Відсутність ключа або самого пакета не має валити імпорт модуля чеків.

Схеми відповіді задані явно (`output_config.format`), а не вивідні з
Pydantic: `app/audit/` не залежить від Pydantic ніде більше, і тягнути
його сюди заради двох структур означало б розмити межу чистого ядра.
"""

from __future__ import annotations

import json
from typing import Any

from app.audit.llm.base import Fact, OwnerNotes, PageInsight, SiteBrief, SiteFacts
from app.core import runtime_config as runtime
from app.core.config import settings
from app.core.logging import log

# Скільки тексту сторінки віддаємо моделі. Довші сторінки коштують більше,
# а відповідь на питання «про що ця сторінка» дає вже перша частина.
MAX_PAGE_CHARS = 6000

# Скільки тексту з кожної сторінки йде у запит про факти. Тут сторінок
# кілька, і платить за них один виклик, тож ліміт на сторінку менший.
MAX_FACT_CHARS = 2500

# Факти, без яких компанію не можна порекомендувати. Список закритий і
# однаковий для всіх сайтів — саме тому відповіді можна порівнювати між
# сайтами. Вільний перелік «чого бракує» цю властивість втрачає: на
# stripe.com він так само довгий, як на сайті без контактів.
#
# Контактів тут навмисно немає. `tel:` і `mailto:` витягуються розміткою,
# а «немає як звʼязатися» вже питає llm.contact_page. Факт, на який
# відповідає правило, не має ні коштувати грошей, ні мати змоги
# помилитися: на живому прогоні модель не побачила телефон crustula,
# який лежить у розмітці явним посиланням.
FACT_KEYS: tuple[tuple[str, str], ...] = (
    ("offering", "what the company concretely sells or does"),
    ("location", "the city, region or country it is based in or serves"),
    ("pricing", "prices, a price list, or an explicit way to get a quote"),
)

PAGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "How you would describe this page to someone asking about this company."
            ),
        },
        "main_query": {
            "type": "string",
            "description": "The single question a person would type into search to land here.",
        },
        "answers_query": {
            "type": "boolean",
            "description": "Whether the page actually answers that question.",
        },
        "missing": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Facts a reader would expect on this page and cannot find.",
        },
        "entities": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Named products, services, places or organisations stated on the page.",
        },
    },
    "required": ["summary", "main_query", "answers_query", "missing", "entities"],
    "additionalProperties": False,
}

BRIEF_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "tagline": {"type": "string", "description": "One line: what this company does."},
        "description": {"type": "string", "description": "Two or three sentences."},
        "offerings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete products or services, as the site names them.",
        },
        "audience": {"type": "string", "description": "Who this is for."},
    },
    "required": ["name", "tagline", "description", "offerings", "audience"],
    "additionalProperties": False,
}

FACTS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "facts": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "enum": [k for k, _ in FACT_KEYS]},
                    "stated": {"type": "boolean"},
                    "quote": {
                        "type": "string",
                        "description": "Short exact quote from the text, or empty if not stated.",
                    },
                    "url": {
                        "type": "string",
                        "description": "URL of the page the quote is on, or empty.",
                    },
                },
                "required": ["key", "stated", "quote", "url"],
                "additionalProperties": False,
            },
        },
        "serves_an_area": {
            "type": "boolean",
            "description": (
                "True if this business serves customers in a specific city, region or "
                "country. False if it is global or online-only, where a street address "
                "would not help a customer."
            ),
        },
        "sells_listed_items": {
            "type": "boolean",
            "description": (
                "True if the site offers individual products or services a visitor would "
                "compare on price. False for free or open-source projects and for "
                "enterprise deals negotiated case by case."
            ),
        },
    },
    "required": ["facts", "serves_an_area", "sells_listed_items"],
    "additionalProperties": False,
}

OWNER_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "opening": {
            "type": "string",
            "description": (
                "Two or three sentences addressed to the owner: what their site is for "
                "and what state it is in. Plain words only."
            ),
        },
        "notes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "The problem key, copied back."},
                    "text": {
                        "type": "string",
                        "description": "One sentence: this problem, in terms of this business.",
                    },
                },
                "required": ["key", "text"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["opening", "notes"],
    "additionalProperties": False,
}

OWNER_SYSTEM = (
    "You write for the owner of a small business who does not work in technology. "
    "You are given what their website sells and a list of problems already found on it. "
    "Restate each problem in terms of this particular business and what it costs them "
    "in customers. Never add a finding that is not in the list, never soften one that "
    "is, and never explain how to fix anything — that is not what this document is for. "
    "No technical terms at all: no SEO, no indexing, no markup, no language models. "
    "Write in the language of the problem descriptions you are given."
)

FACTS_SYSTEM = (
    "You are given the text of several pages from one website — everything a visitor "
    "or an AI assistant can read on it. For each listed fact, say whether the site "
    "states it anywhere in this text. Judge only what is written: if it is not there, "
    "it is not stated, no matter how obvious it seems for a company like this. "
    "When it is stated, quote the exact words and give the page URL."
)

PAGE_SYSTEM = (
    "You read a web page the way a search engine or an AI assistant does, and report "
    "what you actually found — never what a page like this usually contains. "
    "If the page does not state something, it is missing; do not infer it from the "
    "company name, the URL, or your own knowledge of the industry. "
    "Answer in the language the page is written in."
)

BRIEF_SYSTEM = (
    "You are given several pages from one website. Describe the company exactly as "
    "these pages present it, using their own terms for products and services. "
    "Invent nothing: if the pages never say who the audience is, say so plainly. "
    "Answer in the language the pages are written in."
)


class AnthropicAnalyst:
    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        self._model = model or settings.llm_model
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=runtime.get("anthropic_api_key"))
        return self._client

    async def read_page(self, url: str, title: str, text: str) -> PageInsight:
        prompt = (
            f"URL: {url}\nTitle: {title or '(no title)'}\n\n"
            f"Page text:\n{text[:MAX_PAGE_CHARS]}"
        )
        data = await self._ask(PAGE_SYSTEM, prompt, PAGE_SCHEMA)
        if isinstance(data, str):
            return PageInsight(url=url, analysed=False, error=data)
        return PageInsight(
            url=url,
            analysed=True,
            summary=str(data.get("summary", "")),
            main_query=str(data.get("main_query", "")),
            answers_query=bool(data.get("answers_query", True)),
            missing=[str(x) for x in data.get("missing", [])],
            entities=[str(x) for x in data.get("entities", [])],
        )

    async def brief(self, origin: str, pages: list[tuple[str, str]]) -> SiteBrief:
        joined = "\n\n---\n\n".join(
            f"{title or '(no title)'}\n{body[:2000]}" for title, body in pages[:5]
        )
        data = await self._ask(BRIEF_SYSTEM, f"Site: {origin}\n\n{joined}", BRIEF_SCHEMA)
        if isinstance(data, str):
            return SiteBrief(analysed=False, error=data)
        return SiteBrief(
            analysed=True,
            name=str(data.get("name", "")),
            tagline=str(data.get("tagline", "")),
            description=str(data.get("description", "")),
            offerings=[str(x) for x in data.get("offerings", [])],
            audience=str(data.get("audience", "")),
        )

    async def facts(self, origin: str, pages: list[tuple[str, str, str]]) -> SiteFacts:
        """`pages` — трійки (url, title, text). URL потрібен моделі, щоб
        показати, на якій саме сторінці вона знайшла факт."""
        body = "\n\n".join(
            f"=== {url}\n{title or '(no title)'}\n{text[:MAX_FACT_CHARS]}"
            for url, title, text in pages
        )
        asked = "\n".join(f"- {key}: {description}" for key, description in FACT_KEYS)
        data = await self._ask(
            FACTS_SYSTEM, f"Facts to check:\n{asked}\n\nSite pages:\n{body}", FACTS_SCHEMA
        )
        if isinstance(data, str):
            return SiteFacts(analysed=False, error=data)

        seen = {str(item.get("key", "")): item for item in data.get("facts", [])}
        return SiteFacts(
            analysed=True,
            facts=[
                Fact(
                    key=key,
                    # Факт, про який модель промовчала, вважаємо названим:
                    # мовчання — не доказ відсутності, а звинувачувати сайт
                    # у тому, чого ми не питали, гірше за пропуск.
                    stated=bool(seen.get(key, {}).get("stated", True)),
                    quote=str(seen.get(key, {}).get("quote", "")),
                    page_url=str(seen.get(key, {}).get("url", "")),
                )
                for key, _ in FACT_KEYS
            ],
            serves_an_area=bool(data.get("serves_an_area", False)),
            sells_listed_items=bool(data.get("sells_listed_items", False)),
            read_pages=[url for url, _, _ in pages],
        )

    async def owner_notes(
        self, business: str, band: str, problems: list[tuple[str, str]]
    ) -> OwnerNotes:
        """`problems` — пари (ключ, наслідок простою мовою) з каталогу."""
        listed = "\n".join(f"- {key}: {text}" for key, text in problems)
        prompt = (
            f"The business, as its own site describes it:\n{business or '(unknown)'}\n\n"
            f"Overall state of the site: {band}\n\n"
            f"Problems found:\n{listed}"
        )
        data = await self._ask(OWNER_SYSTEM, prompt, OWNER_SCHEMA)
        if isinstance(data, str):
            return OwnerNotes(analysed=False, error=data)

        known = {key for key, _ in problems}
        return OwnerNotes(
            analysed=True,
            opening=str(data.get("opening", "")),
            # Ключі, яких ми не давали, відкидаємо: у звіт має потрапити
            # переказ наших знахідок, а не нова, яку ніхто не доводив.
            notes={
                str(item.get("key", "")): str(item.get("text", ""))
                for item in data.get("notes", [])
                if str(item.get("key", "")) in known and str(item.get("text", ""))
            },
        )

    async def _ask(
        self, system: str, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any] | str:
        """Повертає розібрану відповідь або рядок із причиною невдачі."""
        output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": schema}}
        if _supports_effort(self._model):
            # Задача вузька й описова: читаємо текст, повертаємо факти.
            # Глибше міркування тут не покращує відповідь, лише коштує.
            output_config["effort"] = settings.llm_effort

        try:
            client = self._ensure_client()
            response = await client.messages.create(
                model=self._model,
                max_tokens=settings.llm_max_tokens,
                system=system,
                # Системна частина однакова для всіх сторінок одного аудиту,
                # тож кешування економить на кожній наступній сторінці.
                cache_control={"type": "ephemeral"},
                output_config=output_config,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:  # noqa: BLE001 — збій API не валить аудит
            log.warning("llm_failed", error=str(exc))
            return f"{type(exc).__name__}: {exc}"

        # Перевірка до читання content: при відмові модель повертає HTTP 200
        # з порожнім або частковим списком, і звернення до content[0] падає.
        if response.stop_reason == "refusal":
            return "модель відмовилася аналізувати цю сторінку"

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return f"відповідь не розібралась як JSON: {exc}"
        return parsed if isinstance(parsed, dict) else "очікували обʼєкт, отримали список"

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


def _supports_effort(model: str) -> bool:
    """Чи приймає модель output_config.effort.

    Haiku 4.5 відповідає на нього 400, і оскільки збій API аудиту не валить,
    вимкнення шару виглядало як «модель нічого не знайшла»: на дешевій
    моделі чек мовчав на всіх сайтах, включно з тими, де проблеми справжні.
    Мовчання через несумісний параметр не має виглядати як чиста перевірка.
    """
    return "haiku" not in model.lower()
