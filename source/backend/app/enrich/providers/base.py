"""Межа провайдера: один метод, канонічні типи, спільні категорії збоїв.

Anthropic тут — перший адаптер, а не архітектура. Додавання OpenAI чи
Google означає новий модуль поруч і рядок у реєстрі — код задач,
раннера і застосунку не змінюється (це закріплено тестами на фейкових
провайдерах).
"""

from __future__ import annotations

from typing import Protocol

from app.enrich.contracts import ProviderCall, ProviderReply


class AIProvider(Protocol):
    """Породжує структурний вихід за канонічним запитом.

    Контракт помилок: будь-який збій — це `ProviderError` з категорією.
    Провайдеро-специфічні винятки за цю межу не виходять.
    """

    name: str

    async def generate_structured(self, call: ProviderCall) -> ProviderReply: ...
