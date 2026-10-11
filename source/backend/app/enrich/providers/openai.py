"""OpenAI як другий адаптер — і перевірка, що архітектура справді тримає.

Anthropic був першим адаптером, але доки він лишався єдиним, твердження
«провайдер — деталь» не було нічим доведене. Цей файл — доказ: задачі,
канонічні схеми, валідатори й раннер не змінилися жодним рядком, щоб
сюди прийшла інша компанія з іншим API.

## Що тут провайдеро-специфічне

- **Ендпойнт**: Responses API (`client.responses.create`), а не
  Messages. Структурний вихід задається `text.format` з
  `type: "json_schema"`, іменем схеми і `strict: true`.
- **`strict: true` обовʼязковий** — без нього схема необовʼязкова.
- **Витяг тексту**: `response.output_text`.
- **Кешовані токени** лежать у `usage.input_tokens_details.cached_tokens`,
  а не окремим полем, і — на відміну від Anthropic — вже ВКЛЮЧЕНІ в
  `input_tokens`. Це тарифікується інакше, і облік мусить це знати.
- **Класифікація помилок**: типізовані винятки SDK перекладаються в
  спільні категорії `ProviderError`.

## Діалект схеми

Перекладу **не потрібно**. OpenAI приймає `minimum`, `minItems`, `enum`,
`additionalProperties: false` і вимагає, щоб усі властивості були в
`required` — усе це наші канонічні схеми вже мають. Тому тут немає
трансформації, а є контрактний тест, який це доводить: писати
порожній перетворювач «про всяк випадок» означало б додати місце, де
щось колись тихо зникне.

Порівняння з Anthropic показове: там `minimum` для цілих відбивається
400, і адаптер його знімає. Одна канонічна схема, два діалекти, нуль
змін у задачі.
"""

from __future__ import annotations

from typing import Any

from app.core import runtime_config as runtime
from app.enrich.contracts import (
    ProviderCall,
    ProviderError,
    ProviderReply,
    ProviderUsage,
)

# Ім'я схеми в запиті. OpenAI вимагає його як ідентифікатор формату; на
# зміст воно не впливає, тому одне на всі задачі.
SCHEMA_NAME = "crawldy_task_result"

# Ключові слова JSON Schema, яких OpenAI не приймає. Порожньо: наші
# канонічні схеми користуються лише підтримуваними. Перелік лишається
# явним, щоб наступна несумісність додавалася сюди з доказом, а не
# «прибиралася» узагальненою функцією.
#
# Підтверджено документацією (developers.openai.com, structured outputs,
# звірено 2026-08-24): підтримуються pattern, format, multipleOf,
# maximum/minimum, minItems/maxItems, enum, anyOf, required,
# additionalProperties: false. НЕ підтримуються: необовʼязкові поля,
# minLength/maxLength, anyOf у корені.
_UNSUPPORTED_BY_TYPE: dict[str, frozenset[str]] = {}


def to_provider_schema(schema: Any) -> Any:
    """Канонічна схема → діалект OpenAI.

    Сьогодні це тотожність, і так і має бути: перетворення зʼявиться
    лише разом із доведеною несумісністю. Функція існує, щоб місце для
    неї було одне й відоме.
    """
    if not _UNSUPPORTED_BY_TYPE:
        return schema
    if isinstance(schema, list):
        return [to_provider_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema
    drop = _UNSUPPORTED_BY_TYPE.get(str(schema.get("type", "")), frozenset())
    return {k: to_provider_schema(v) for k, v in schema.items() if k not in drop}


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            if not runtime.get("openai_api_key"):
                raise ProviderError("not_configured", "не заданий ключ OPENAI_API_KEY")
            from openai import AsyncOpenAI

            # Ретраї вимкнено: повторами володіє раннер, і кожна спроба
            # мусить лягти в журнал. Прихованих оплачених викликів бути
            # не може — та сама вимога, що й до адаптера Anthropic.
            self._client = AsyncOpenAI(api_key=runtime.get("openai_api_key"), max_retries=0)
        return self._client

    async def generate_structured(self, call: ProviderCall) -> ProviderReply:
        try:
            client = self._ensure_client()
            response = await client.responses.create(
                model=call.model,
                instructions=call.system,
                input=call.prompt,
                max_output_tokens=call.max_output_tokens,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": SCHEMA_NAME,
                        "schema": to_provider_schema(call.schema),
                        "strict": True,
                    }
                },
                timeout=call.timeout_s,
            )
        except ProviderError:
            raise
        except Exception as exc:  # межа адаптера: далі лише ProviderError
            raise ProviderError(_category_of(exc), f"{type(exc).__name__}: {exc}") from exc

        # Відмова приходить окремим типом елемента, а не винятком.
        refusal = _refusal_of(response)
        if refusal:
            # Відмова теж спалює токени, і рахунок за них виставлять. Той
            # самий клас дефекту, що вже спіймано на обриві по стелі
            # виходу: категорія була правильна, а облік губився.
            raise ProviderError(
                "refused", f"модель відмовилася: {refusal}", _usage_of(response)
            )

        # Обрив через ліміт вихідних токенів дає валідний обʼєкт із
        # неповним JSON. Без цієї перевірки він падав би як «не JSON», і
        # причина в журналі була б неправильною.
        if getattr(response, "status", None) == "incomplete":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", "")
            # Та сама провайдеро-нейтральна категорія, що й у Anthropic:
            # обрив по стелі — межа виконання, а не зіпсована відповідь.
            raise ProviderError(
                "output_limit", f"відповідь обірвана: {reason}", _usage_of(response)
            )

        import json

        text = getattr(response, "output_text", "") or ""
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError("invalid_output", f"відповідь не JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ProviderError("invalid_output", "очікували обʼєкт, отримали інший тип")

        usage = getattr(response, "usage", None)
        cached = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None)
        total_input = getattr(usage, "input_tokens", None)
        # OpenAI включає кешовані токени в `input_tokens`, Anthropic — ні.
        # Журнал зберігає їх роздільно, тож тут кешовану частину треба
        # відняти, інакше вона порахувалася б двічі й за вищою ставкою.
        uncached = total_input
        if isinstance(total_input, int) and isinstance(cached, int):
            uncached = max(total_input - cached, 0)

        return ProviderReply(
            output=parsed,
            model=str(getattr(response, "model", call.model)),
            request_id=getattr(response, "id", None),
            input_tokens=uncached,
            output_tokens=getattr(usage, "output_tokens", None),
            # Кеш OpenAI лише читається — записи як окремої платної
            # операції немає, тому cache_write лишається порожнім.
            cache_write_tokens=None,
            cache_read_tokens=cached,
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


def _refusal_of(response: Any) -> str:
    """Текст відмови, якщо модель відмовилась, інакше порожньо."""
    for item in getattr(response, "output", None) or []:
        for block in getattr(item, "content", None) or []:
            if getattr(block, "type", "") == "refusal":
                return str(getattr(block, "refusal", "")) or "без пояснення"
    return ""


def _usage_of(response: Any) -> ProviderUsage:
    """Спожите — навіть коли відповідь непридатна.

    Кешовані токени в OpenAI уже входять до `input_tokens`, тож тут та
    сама поправка, що й на успішному шляху: інакше кешована частина
    порахувалася б двічі.
    """
    usage = getattr(response, "usage", None)
    cached = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", None)
    total_input = getattr(usage, "input_tokens", None)
    uncached = total_input
    if isinstance(total_input, int) and isinstance(cached, int):
        uncached = max(total_input - cached, 0)
    return ProviderUsage(
        input_tokens=uncached,
        output_tokens=getattr(usage, "output_tokens", None),
        cache_write_tokens=None,
        cache_read_tokens=cached,
        model=str(getattr(response, "model", "")) or None,
    )


# Структурні коди помилок OpenAI → наші категорії. Код надійніший за
# текст: повідомлення переписують, коди — ні.
_CODE_TO_CATEGORY: dict[str, str] = {
    "insufficient_quota": "insufficient_quota",
    "billing_hard_limit_reached": "billing_error",
    "billing_not_active": "billing_error",
    "account_deactivated": "billing_error",
}


def _error_code(exc: Exception) -> str:
    """Код помилки з тіла відповіді, якщо провайдер його дав."""
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        return code
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            for field in ("code", "type"):
                value = error.get(field)
                if isinstance(value, str) and value:
                    return value
    return ""


def _category_of(exc: Exception) -> str:
    """Виняток SDK → спільна категорія. Типи OpenAI за цю межу не виходять.

    HTTP 429 у OpenAI означає три різні речі: вичерпану квоту, платіжну
    проблему й звичайне обмеження частоти. Чекати варто лише на третьому,
    тож статусу замало — дивимось структурний код.
    """
    import openai

    code = _error_code(exc)
    mapped = _CODE_TO_CATEGORY.get(code)

    if isinstance(exc, openai.AuthenticationError | openai.PermissionDeniedError):
        # Ключ заданий, але провайдер його не прийняв. Це НЕ
        # `not_configured`: конфігурація в нас є, її відхилив провайдер.
        return "authentication_error"
    if isinstance(exc, openai.RateLimitError):
        return mapped or "rate_limit"
    if isinstance(exc, openai.BadRequestError):
        # Платіжний стан інколи приходить і як 400 — код важить більше
        # за статус.
        return mapped or "invalid_request"
    if isinstance(exc, openai.APITimeoutError):
        return "timeout"
    if isinstance(exc, openai.InternalServerError | openai.APIConnectionError):
        return "provider_error"
    return mapped or "provider_error"
