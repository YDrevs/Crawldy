"""Межа провайдера присутності: одне питання — одна відповідь.

Адаптер отримує текст промпту й ринок, повертає `ProviderAnswer` з
механічно витягнутими фактами (текст, циовані адреси, чи був пошук,
спожите). Тлумачення відповіді — НЕ робота адаптера: воно спільне для
всіх провайдерів і живе в `normalize`.

Контракт помилок: будь-який збій — `PresenceProviderError` зі статусом
із канонічної моделі. Провайдеро-специфічні винятки за межу не виходять.
"""

from __future__ import annotations

from typing import Protocol

from app.presence.contracts import ProviderAnswer


class PresenceProvider(Protocol):
    name: str
    model: str
    tool_version: str

    async def observe(
        self, prompt_text: str, *, country: str | None,
        require_search: bool = False,
    ) -> ProviderAnswer: ...
