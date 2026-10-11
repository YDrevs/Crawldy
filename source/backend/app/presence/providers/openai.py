"""OpenAI: Responses API + інструмент web_search.

Відповідь несе `output_text` і анотації `url_citation` (url, title) у
message-блоках; кількість пошуків — це кількість `web_search_call`
елементів у виході. Локація — `user_location` типу approximate.
Ретраї вимкнено: ними володіє раннер.
"""

from __future__ import annotations

from typing import Any, cast

from app.core import runtime_config as runtime
from app.presence.budget import REQUEST_CEILINGS
from app.presence.contracts import (
    ObservationStatus,
    PresenceProviderError,
    ProviderAnswer,
    ProviderUsage,
)

TOOL_VERSION = "web_search"
_TIMEOUT_S = 90.0


class OpenAIPresenceProvider:
    name = "openai"
    tool_version = TOOL_VERSION

    def __init__(self, model: str, *, timeout_s: float = _TIMEOUT_S) -> None:
        self.model = model
        self.timeout_s = timeout_s

    async def observe(
        self, prompt_text: str, *, country: str | None,
        require_search: bool = False,
    ) -> ProviderAnswer:
        if not runtime.get("openai_api_key"):
            raise PresenceProviderError(
                ObservationStatus.NOT_CONFIGURED, "OPENAI_API_KEY відсутній",
                incurred_usd=0.0,  # запит не покидав процесу
            )
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - оточення без SDK
            raise PresenceProviderError(
                ObservationStatus.NOT_CONFIGURED, f"SDK openai відсутній: {exc}",
                incurred_usd=0.0,  # запит не покидав процесу
            ) from exc

        tool: dict[str, Any] = {"type": TOOL_VERSION}
        if country:
            tool["user_location"] = {"type": "approximate", "country": country}

        client = openai.AsyncOpenAI(
            api_key=runtime.get("openai_api_key"), max_retries=0, timeout=self.timeout_s
        )
        try:
            # Explicit-режим: Responses API вміє ПРИМУСИТИ інструмент —
            # tool_choice="required" (офіційна документація web_search).
            # Це єдиний з чотирьох провайдерів із API-важелем примусу.
            ceilings = REQUEST_CEILINGS["openai"]
            # Обидві стелі — документовані параметри Responses API:
            # max_output_tokens (включно з reasoning-токенами) і
            # max_tool_calls (обмежує кількість викликів інструментів).
            # Саме з них рахується захисний максимум спроби.
            response = await client.responses.create(
                model=self.model,
                input=prompt_text,
                tools=cast(Any, [tool]),
                tool_choice=cast(Any, "required") if require_search else "auto",
                max_output_tokens=ceilings.max_output_tokens,
                max_tool_calls=ceilings.max_searches,
            )
        except openai.RateLimitError as exc:
            # OpenAI не публікує авторитетного «429 не білиться» —
            # доля грошей НЕВІДОМА, і книга утримує резерв, а не нуль.
            raise PresenceProviderError(
                ObservationStatus.RATE_LIMITED, str(exc)[:300],
                incurred_usd=None,
            ) from exc
        except openai.APIStatusError as exc:
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, f"HTTP {exc.status_code}",
                incurred_usd=None,
            ) from exc
        except (openai.APITimeoutError, openai.APIConnectionError) as exc:
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, str(exc)[:300],
                # Таймаут/обрив: чи стягнув провайдер — невідомо.
                incurred_usd=None,
            ) from exc
        except openai.APIError as exc:
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, str(exc)[:300],
                incurred_usd=None,
            ) from exc
        finally:
            await client.close()

        cited: list[str] = []
        queries: list[str] = []
        searches = 0
        for item in response.output or []:
            kind = getattr(item, "type", "")
            if kind == "web_search_call":
                searches += 1
                # Виконаний запит — коли API його віддає (action.query);
                # «зазвичай, але не завжди» за документацією.
                action = getattr(item, "action", None)
                q = getattr(action, "query", None)
                if isinstance(q, str) and q and q not in queries:
                    queries.append(q)
            elif kind == "message":
                for part in getattr(item, "content", None) or []:
                    for note in getattr(part, "annotations", None) or []:
                        if getattr(note, "type", "") == "url_citation":
                            url = getattr(note, "url", None)
                            if url:
                                cited.append(url)

        usage = response.usage
        return ProviderAnswer(
            text=response.output_text or "",
            cited_urls=cited,
            searched=searches > 0,
            search_queries=queries,
            model=getattr(response, "model", self.model),
            usage=ProviderUsage(
                input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
                output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
                searches=searches,
            ),
            raw=response.model_dump(),
        )
