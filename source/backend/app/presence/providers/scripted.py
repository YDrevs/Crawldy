"""Скриптований провайдер: детерміновані відповіді для тестів і пілоту.

У проді його НЕ існує — реєстр відмовляється його створювати (див.
registry.py), і це та сама структурна межа, що й у білінгу: фейковий
провайдер у проді — це вигадане вимірювання в продукті, який продає
чесність вимірювань.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.presence.contracts import (
    ObservationStatus,
    PresenceProviderError,
    ProviderAnswer,
    ProviderUsage,
)


@dataclass(slots=True)
class ScriptedReply:
    text: str
    cited_urls: list[str] = field(default_factory=list)
    searched: bool = True
    fail_with: ObservationStatus | None = None


class ScriptedPresenceProvider:
    """Відповіді за чергою; вичерпана черга повторює останню."""

    name = "scripted"
    tool_version = "scripted-1"

    def __init__(self, replies: list[ScriptedReply], model: str = "scripted-model") -> None:
        self.model = model
        self._replies = replies
        self.calls: list[str] = []
        self.required_search_calls: list[bool] = []

    async def observe(
        self, prompt_text: str, *, country: str | None,
        require_search: bool = False,
    ) -> ProviderAnswer:
        del country
        self.calls.append(prompt_text)
        self.required_search_calls.append(require_search)
        index = min(len(self.calls) - 1, len(self._replies) - 1)
        reply = self._replies[index]
        if reply.fail_with is not None:
            # Скриптований збій не покидає процесу — нуль авторитетний.
            raise PresenceProviderError(
                reply.fail_with, "scripted failure", incurred_usd=0.0)
        return ProviderAnswer(
            text=reply.text,
            cited_urls=list(reply.cited_urls),
            searched=reply.searched,
            model=self.model,
            usage=ProviderUsage(
                input_tokens=50, output_tokens=200,
                searches=1 if reply.searched else 0,
            ),
            raw={"scripted": True},
        )
