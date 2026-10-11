"""Anthropic як адаптер — перший реальний, але не особливий.

SDK імпортується ліниво всередині виклику (як Playwright і як у
legacy-шарі): відсутність пакета чи ключа не валить імпорт модулів.
Ретраї SDK вимкнено (`max_retries=0`) навмисно: повторами володіє
раннер, і кожна спроба лягає в журнал — прихованих викликів, за які
заплачено без сліду, тут бути не може.

Провайдеро-специфічні деталі, що лишаються за цією межею:
- переклад JSON Schema у `output_config.format` (зокрема зняття
  `minimum` для цілих, якого цей структурний вихід не приймає);
- виявлення обриву за `stop_reason == "max_tokens"`;
- кешовані токени окремими полями `usage`, на відміну від інших API;
- категоризація винятків SDK у спільні категорії `ProviderError`.
"""

from __future__ import annotations

import json
from typing import Any

from app.core import runtime_config as runtime
from app.enrich.contracts import (
    ProviderCall,
    ProviderError,
    ProviderReply,
    ProviderUsage,
)

# ── діалект схем Anthropic ────────────────────────────────────────────────
#
# Canonical-схема належить Crawldy; провайдер її не диктує. Структурний
# вихід Anthropic приймає лише підмножину JSON Schema, і переклад у цю
# підмножину — робота адаптера, а не привід послабити контракт.
#
# Перелік НАВМИСНО закритий: сюди потрапляє тільки те, що ми справді
# бачили відбитим, із текстом помилки поруч. Узагальнена функція «зняти
# все, чого провайдер може не знати» тихо вирізала б і ті обмеження, які
# провайдер приймає, — і ми б ніколи не дізналися, що втратили. Усе, чого
# в переліку немає, іде до провайдера як є: невідома несумісність має
# впасти голосно (400 із назвою поля), а не зникнути мовчки.
#
# minimum/integer — спостережено 2026-08-24 на claude-opus-5:
#   400 invalid_request_error: "output_config.format.schema:
#   For 'integer' type, property 'minimum' is not supported"
#
# Доведено ПІДТРИМУВАНІ живими викликами (не чіпати):
#   minItems для array, enum для string, additionalProperties: false.
_UNSUPPORTED_BY_TYPE: dict[str, frozenset[str]] = {
    "integer": frozenset({"minimum"}),
}


def to_provider_schema(schema: Any) -> Any:
    """Канонічна схема → діалект Anthropic. Знімає лише відоме несумісне.

    Чиста функція: канонічний обʼєкт не мутується, бо він спільний для
    всіх провайдерів і живе в модулі задачі.
    """
    if isinstance(schema, list):
        return [to_provider_schema(item) for item in schema]
    if not isinstance(schema, dict):
        return schema

    drop = _UNSUPPORTED_BY_TYPE.get(str(schema.get("type", "")), frozenset())
    return {
        key: to_provider_schema(value)
        for key, value in schema.items()
        if key not in drop
    }


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self._client: Any = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            if not runtime.get("anthropic_api_key"):
                raise ProviderError("not_configured", "не заданий ключ ANTHROPIC_API_KEY")
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=runtime.get("anthropic_api_key"), max_retries=0)
        return self._client

    async def generate_structured(self, call: ProviderCall) -> ProviderReply:
        # `output_config` несе рівно те, що описано в контракті провайдера:
        # формат і схему.
        #
        # Поля `effort` тут свідомо немає. Воно є в legacy-шарі
        # (`app/audit/llm/`) і на Opus 5 працювало — усі 15 живих викликів
        # пілота пройшли. Але в офіційній документації `output_config`
        # його немає, а проєкт уже знає, що воно модельозалежне: Haiku 4.5
        # відповідає на нього 400. Слати недокументований параметр моделі,
        # на якій його ніхто не перевіряв, означало б покласти порівняння
        # Sonnet 5 на випадковість.
        #
        # Друга причина — чесність самого порівняння: якби Opus отримував
        # `effort: low`, а Sonnet ні, ми порівнювали б різні конфігурації,
        # а не моделі.
        output_config: dict[str, Any] = {
            "format": {"type": "json_schema", "schema": to_provider_schema(call.schema)}
        }

        try:
            client = self._ensure_client()
            response = await client.messages.create(
                model=call.model,
                max_tokens=call.max_output_tokens,
                system=call.system,
                cache_control={"type": "ephemeral"},
                output_config=output_config,
                messages=[{"role": "user", "content": call.prompt}],
                timeout=call.timeout_s,
            )
        except ProviderError:
            raise
        except Exception as exc:  # межа адаптера: далі лише ProviderError
            raise ProviderError(_category_of(exc), f"{type(exc).__name__}: {exc}") from exc

        if response.stop_reason == "refusal":
            raise ProviderError(
                "refused", "модель відмовилася виконувати задачу", _usage_of(response)
            )

        # Обрив по стелі вихідних токенів дає валідний обʼєкт із неповним
        # JSON. Без цієї перевірки він падав у парсер і потрапляв у журнал
        # як «відповідь не JSON» — тобто з неправильною причиною, та ще й
        # без обліку спожитого. Живий прогін показав саме це: пʼять
        # обірваних спроб записали нуль токенів і нуль вартості, хоча
        # провайдер їх спожив.
        if response.stop_reason == "max_tokens":
            raise ProviderError(
                "output_limit",
                f"відповідь обірвана стелею виходу ({call.max_output_tokens} токенів)",
                _usage_of(response),
            )

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ProviderError("invalid_output", f"відповідь не JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise ProviderError("invalid_output", "очікували обʼєкт, отримали інший тип")

        usage = getattr(response, "usage", None)
        return ProviderReply(
            output=parsed,
            model=str(getattr(response, "model", call.model)),
            request_id=getattr(response, "_request_id", None),
            # `input_tokens` у відповіді — це НЕкешована частина входу.
            # Кешовані токени лежать окремо й тарифікуються інакше, тож
            # і в журнал ідуть окремо.
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
        )

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.close()
            self._client = None


def _usage_of(response: Any) -> ProviderUsage:
    """Спожите — навіть коли відповідь непридатна."""
    usage = getattr(response, "usage", None)
    return ProviderUsage(
        input_tokens=getattr(usage, "input_tokens", None),
        output_tokens=getattr(usage, "output_tokens", None),
        cache_write_tokens=getattr(usage, "cache_creation_input_tokens", None),
        cache_read_tokens=getattr(usage, "cache_read_input_tokens", None),
        model=str(getattr(response, "model", "")) or None,
    )


# Anthropic не дає окремого коду для платіжного стану: нестача коштів
# приходить як 400 `invalid_request_error` з поясненням у тексті. Отже
# текст тут — єдина доступна ознака, і перевірка навмисно вузька: два
# сталі формулювання, усередині адаптера, під тестом. У нейтральний
# раннер жодне слово провайдера не потрапляє.
_BILLING_MARKERS = ("credit balance is too low", "billing")


def _looks_like_billing(exc: Exception) -> bool:
    body = getattr(exc, "body", None)
    message = ""
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = str(error.get("message", ""))
    if not message:
        message = str(exc)
    lowered = message.lower()
    return any(marker in lowered for marker in _BILLING_MARKERS)


def _category_of(exc: Exception) -> str:
    """Виняток SDK → спільна категорія. Типи Anthropic за цю межу не виходять."""
    import anthropic

    if isinstance(exc, anthropic.AuthenticationError | anthropic.PermissionDeniedError):
        # Ключ заданий, але відхилений. Не `not_configured`: конфігурація
        # в нас є. Саме цю різницю ми вже одного разу читали в журналі.
        return "authentication_error"
    if isinstance(exc, anthropic.RateLimitError):
        return "billing_error" if _looks_like_billing(exc) else "rate_limit"
    if isinstance(exc, anthropic.BadRequestError):
        return "billing_error" if _looks_like_billing(exc) else "invalid_request"
    if isinstance(exc, anthropic.APITimeoutError):
        return "timeout"
    if isinstance(
        exc,
        anthropic.OverloadedError | anthropic.InternalServerError | anthropic.APIConnectionError,
    ):
        return "provider_error"
    return "provider_error"
