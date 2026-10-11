"""Perplexity: Agent API (/v1/agent) з інструментом web_search.

Міграція з legacy Sonar Chat Completions свідома: старий API офіційно
підтримується лише до 2026-09-27, а Agent API — канонічний інтерфейс для
нових інтеграцій. Бонус міграції: web_search приймає
`user_location.country`, якого legacy не мав.

Провенанс: спостереження з provider=perplexity МУСИТЬ іти власною
моделлю Perplexity (`perplexity/...`). Agent API вміє маршрутизувати й
у чужі моделі — але тоді це було б спостереження OpenAI під вивіскою
Perplexity, тобто неправда про походження. Межу тримає валідація
політики (`is_native_model`), адаптер її не перевіряє повторно.

Форма відповіді — офіційна документація Agent API: відповідь у
`output[].content[].text` message-елемента, джерела в елементі
`search_results` (`results[].url` — source of truth для цитат), спожите
в `usage` разом із лічильником викликів пошуку
(`tool_calls_details.search_web.invocation`).

httpx навмисно: один POST не вартий SDK-залежності.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core import runtime_config as runtime
from app.presence.budget import REQUEST_CEILINGS
from app.presence.contracts import (
    ObservationStatus,
    PresenceProviderError,
    ProviderAnswer,
    ProviderUsage,
)

TOOL_VERSION = "agent-web_search"
_ENDPOINT = "https://api.perplexity.ai/v1/agent"
_TIMEOUT_S = 120.0


class PerplexityPresenceProvider:
    name = "perplexity"
    tool_version = TOOL_VERSION

    def __init__(self, model: str, *, timeout_s: float = _TIMEOUT_S) -> None:
        self.model = model
        self.timeout_s = timeout_s

    async def observe(
        self, prompt_text: str, *, country: str | None,
        require_search: bool = False,
    ) -> ProviderAnswer:
        # `require_search` без API-важеля: Agent API не має примусу
        # інструмента — явний режим для Perplexity живе в тексті промпту.
        if not runtime.get("perplexity_api_key"):
            raise PresenceProviderError(
                ObservationStatus.NOT_CONFIGURED, "PERPLEXITY_API_KEY відсутній",
                incurred_usd=0.0,  # запит не покидав процесу
            )
        tool: dict[str, Any] = {"type": "web_search"}
        if country:
            tool["user_location"] = {"country": country}
        ceilings = REQUEST_CEILINGS["perplexity"]
        # Обидві стелі — документовані параметри Agent API; з них
        # рахується захисний максимум спроби.
        payload = {
            "model": self.model,
            "input": prompt_text,
            "tools": [tool],
            "max_output_tokens": ceilings.max_output_tokens,
            "max_tool_calls": ceilings.max_searches,
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout_s) as client:
                response = await client.post(
                    _ENDPOINT,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {runtime.get('perplexity_api_key')}"
                    },
                )
        except httpx.HTTPError as exc:
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, f"мережа: {exc!r}"[:300],
                # Таймаут/обрив: чи стягнув провайдер — невідомо.
                incurred_usd=None,
            ) from exc

        if response.status_code == 429:
            # Авторитетного «429 не білиться» немає — доля невідома.
            raise PresenceProviderError(
                ObservationStatus.RATE_LIMITED, "HTTP 429",
                incurred_usd=None,
            )
        if response.status_code >= 400:
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR,
                f"HTTP {response.status_code}: {response.text[:200]}",
                incurred_usd=None,
            )

        body: dict[str, Any] = response.json()
        return parse_agent_response(body, fallback_model=self.model)


def parse_agent_response(
    body: dict[str, Any], *, fallback_model: str
) -> ProviderAnswer:
    """Офіційна форма Agent API → канонічна відповідь. Окремо від I/O,
    щоб фіксчури тестів проходили рівно цим кодом."""
    texts: list[str] = []
    cited: list[str] = []
    for item in body.get("output") or []:
        kind = item.get("type") if isinstance(item, dict) else None
        if kind == "message":
            for part in item.get("content") or []:
                if isinstance(part, dict) and part.get("type") == "output_text":
                    texts.append(str(part.get("text") or ""))
        elif kind == "search_results":
            for row in item.get("results") or []:
                url = row.get("url") if isinstance(row, dict) else None
                if isinstance(url, str) and url and url not in cited:
                    cited.append(url)

    usage = body.get("usage") or {}
    tool_calls = usage.get("tool_calls_details") or {}
    search_calls = 0
    search_web = tool_calls.get("search_web")
    if isinstance(search_web, dict):
        search_calls = int(search_web.get("invocation") or 0)
    searched = search_calls > 0 or bool(cited)

    # Фактична вартість від провайдера, коли він її віддає: авторитетна
    # для обліку, але стелі бюджету вона НЕ обходить — допуск до виклику
    # раннер вирішує ДО запиту, за вже витраченим.
    provider_cost: float | None = None
    cost_field = usage.get("cost")
    if isinstance(cost_field, dict):
        total = cost_field.get("total_cost")
        if isinstance(total, int | float):
            provider_cost = float(total)

    return ProviderAnswer(
        text="".join(texts),
        cited_urls=cited,
        searched=searched,
        model=str(body.get("model") or fallback_model),
        usage=ProviderUsage(
            input_tokens=int(usage.get("input_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or 0),
            searches=max(search_calls, 1 if searched else 0),
        ),
        provider_cost_usd=provider_cost,
        raw=body,
    )
