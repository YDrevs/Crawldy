"""Реєстр адаптерів присутності: імʼя → фабрика, з прод-гейтом.

Модель передається фабриці з політики — реєстр знає, ЯК створити
адаптер, а політика вирішує, З ЧИМ. Додати провайдера — рядок тут плюс
модуль поруч; раннер і продукт не змінюються.

`scripted` реєструється лише поза продом і лише явно з тестів: у
`app_env=prod` його не існує взагалі — гейт стоїть у реєстрі, а не в
маршруті (урок білінгового фейка).
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.config import settings
from app.presence.providers.base import PresenceProvider


def _anthropic(model: str, timeout_s: float) -> PresenceProvider:
    from app.presence.providers.anthropic import AnthropicPresenceProvider

    return AnthropicPresenceProvider(model, timeout_s=timeout_s)


def _openai(model: str, timeout_s: float) -> PresenceProvider:
    from app.presence.providers.openai import OpenAIPresenceProvider

    return OpenAIPresenceProvider(model, timeout_s=timeout_s)


def _perplexity(model: str, timeout_s: float) -> PresenceProvider:
    from app.presence.providers.perplexity import PerplexityPresenceProvider

    return PerplexityPresenceProvider(model, timeout_s=timeout_s)


def _google(model: str, timeout_s: float) -> PresenceProvider:
    from app.presence.providers.google import GooglePresenceProvider

    # Продуктовий бекенд за замовчуванням; get_provider передає бекенд
    # явним параметром, і цей шлях лишається лише як позначка в реєстрі.
    return GooglePresenceProvider(
        model, timeout_s=timeout_s, backend="vertex_ai")


_FACTORIES: dict[str, Callable[[str, float], PresenceProvider]] = {
    "anthropic": _anthropic,
    "openai": _openai,
    "perplexity": _perplexity,
    "google": _google,
}

_PRODUCTION_NAMES = ("anthropic", "openai", "perplexity", "google")


def get_provider(
    name: str, model: str, *, timeout_s: float = 90.0,
    backend: str | None = None,
) -> PresenceProvider:
    factory = _FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"невідомий провайдер присутності: {name}")
    if name == "google":
        # Бекенд — явний параметр виконання google; для решти
        # провайдерів його не існує, і фабрики його не бачать.
        from app.presence.providers.google import GooglePresenceProvider

        return GooglePresenceProvider(
            model, timeout_s=timeout_s, backend=backend or "vertex_ai")
    return factory(model, timeout_s)


def register_provider(name: str, factory: Callable[[str], PresenceProvider]) -> None:
    """Для тестів. У проді реєстрація нестандартних провайдерів заборонена."""
    if settings.app_env == "prod":
        raise RuntimeError(
            "реєстрація провайдера присутності в проді заборонена: "
            "продуктова конфігурація живе в _FACTORIES"
        )
    # Тестові фабрики однопараметричні; таймаут їм ні до чого.
    _FACTORIES[name] = lambda model, _timeout: factory(model)


def unregister_provider(name: str) -> None:
    """Прибирає тестову реєстрацію; продуктові фабрики не чіпає."""
    if name in _PRODUCTION_NAMES:
        return
    _FACTORIES.pop(name, None)
