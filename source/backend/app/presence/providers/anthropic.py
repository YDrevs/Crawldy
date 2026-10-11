"""Anthropic: Messages API + серверний web_search.

Базова версія інструмента (`web_search_20250305`) навмисно: їй не
потрібен code-execution-канал, вона доступна всюди, і її відповідь
містить рівно те, що нам треба, — текст із цитатами
`web_search_result_location` та лічильник пошуків в usage.

`encrypted_content` НЕ зберігається: він потрібен лише багатоходовим
розмовам, а спостереження — один хід. Ретраями володіє раннер;
`max_retries=0` — прихованих оплачених викликів не існує.
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

TOOL_VERSION = "web_search_20250305"
_TIMEOUT_S = 90.0


class AnthropicPresenceProvider:
    name = "anthropic"
    tool_version = TOOL_VERSION

    def __init__(self, model: str, *, timeout_s: float = _TIMEOUT_S) -> None:
        self.model = model
        self.timeout_s = timeout_s

    async def observe(
        self, prompt_text: str, *, country: str | None,
        require_search: bool = False,
    ) -> ProviderAnswer:
        # `require_search` не має API-важеля: серверний web_search
        # Anthropic примусити не можна (тригер керується лише промптом,
        # офіційна документація). Явний режим для цього провайдера —
        # інструкція в тексті; чи стався пошук, каже usage, не наша віра.
        if not runtime.get("anthropic_api_key"):
            raise PresenceProviderError(
                ObservationStatus.NOT_CONFIGURED, "ANTHROPIC_API_KEY відсутній",
                incurred_usd=0.0,  # запит не покидав процесу
            )
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - оточення без SDK
            raise PresenceProviderError(
                ObservationStatus.NOT_CONFIGURED, f"SDK anthropic відсутній: {exc}",
                incurred_usd=0.0,  # запит не покидав процесу
            ) from exc

        ceilings = REQUEST_CEILINGS["anthropic"]
        tool: dict[str, Any] = {
            "type": TOOL_VERSION,
            "name": "web_search",
            # Документований max_uses — реальна стеля кількості пошуків:
            # перевищення дає max_uses_exceeded, а не тихий виклик.
            "max_uses": ceilings.max_searches,
        }
        if country:
            tool["user_location"] = {"type": "approximate", "country": country}

        client = anthropic.AsyncAnthropic(
            api_key=runtime.get("anthropic_api_key"), max_retries=0, timeout=self.timeout_s
        )
        try:
            message = await client.messages.create(
                model=self.model,
                max_tokens=ceilings.max_output_tokens,
                messages=[{"role": "user", "content": prompt_text}],
                tools=cast(Any, [tool]),
            )
        except anthropic.RateLimitError as exc:
            # Авторитетного «429 не білиться» в документації немає —
            # доля грошей невідома, книга утримує резерв.
            raise PresenceProviderError(
                ObservationStatus.RATE_LIMITED, str(exc)[:300],
                incurred_usd=None,
            ) from exc
        except anthropic.APIStatusError as exc:
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, f"HTTP {exc.status_code}",
                incurred_usd=None,
            ) from exc
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, str(exc)[:300],
                # Таймаут/обрив: чи стягнув провайдер — невідомо.
                incurred_usd=None,
            ) from exc
        except anthropic.APIError as exc:
            raise PresenceProviderError(
                ObservationStatus.PROVIDER_ERROR, str(exc)[:300],
                incurred_usd=None,
            ) from exc
        finally:
            await client.close()

        texts: list[str] = []
        cited: list[str] = []
        queries: list[str] = []
        for block in message.content:
            if block.type == "text":
                texts.append(block.text)
                for citation in block.citations or []:
                    url = getattr(citation, "url", None)
                    if isinstance(url, str) and url:
                        cited.append(url)
            elif (getattr(block, "type", "") == "server_tool_use"
                  and getattr(block, "name", "") == "web_search"):
                q = (getattr(block, "input", None) or {}).get("query")
                if isinstance(q, str) and q and q not in queries:
                    queries.append(q)

        server_use = getattr(message.usage, "server_tool_use", None)
        searches = int(getattr(server_use, "web_search_requests", 0) or 0)
        return ProviderAnswer(
            text="".join(texts),
            cited_urls=cited,
            searched=searches > 0,
            search_queries=queries,
            model=message.model,
            usage=ProviderUsage(
                input_tokens=message.usage.input_tokens,
                output_tokens=message.usage.output_tokens,
                searches=searches,
            ),
            raw=_strip_encrypted(message.model_dump()),
        )


def _strip_encrypted(obj: Any) -> Any:
    """Прибирає транзитні шифровані поля з сирого доказу рекурсивно.

    Вони потрібні лише для повернення в багатоходову розмову — зберігати
    їх означало б тримати дані, які нам не належить читати й не треба.
    """
    if isinstance(obj, dict):
        return {
            k: _strip_encrypted(v)
            for k, v in obj.items()
            if k not in ("encrypted_content", "encrypted_index")
        }
    if isinstance(obj, list):
        return [_strip_encrypted(v) for v in obj]
    return obj
