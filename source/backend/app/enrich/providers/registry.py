"""Реєстр провайдерів: імʼя → фабрика.

Нові провайдери додаються рядком тут (або реєстрацією в тестах) — без
жодної зміни в задачах, раннері чи застосунку. Фабрики ліниві: сам факт
наявності запису нічого не імпортує й не викликає.
"""

from __future__ import annotations

from collections.abc import Callable

from app.enrich.providers.base import AIProvider


def _anthropic() -> AIProvider:
    from app.enrich.providers.anthropic import AnthropicProvider

    return AnthropicProvider()


def _openai() -> AIProvider:
    from app.enrich.providers.openai import OpenAIProvider

    return OpenAIProvider()


_FACTORIES: dict[str, Callable[[], AIProvider]] = {
    "anthropic": _anthropic,
    "openai": _openai,
}


def get_provider(name: str) -> AIProvider:
    factory = _FACTORIES.get(name)
    if factory is None:
        raise KeyError(f"невідомий провайдер: {name}")
    return factory()


def register_provider(name: str, factory: Callable[[], AIProvider]) -> None:
    """Для тестів і бенчмарку. Продуктова конфігурація живе в _FACTORIES."""
    _FACTORIES[name] = factory

