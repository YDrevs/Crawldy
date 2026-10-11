"""Скриптований провайдер: детермінований, без мережі, без грошей.

Два призначення:

1. Тести — довести, що зміна провайдера/моделі не вимагає жодної правки
   коду задач (маршрути вказують на нього замість Anthropic).
2. Бенчмарк у режимі dry-run — прогнати весь конвеєр (вхід → виклик →
   валідація → збереження) на фіксованому корпусі, не витративши
   жодного цента. Живий платний прогін — окреме явне рішення.

Це продуктивний код тестового подвійника, а не мок у тестовому файлі,
бо на нього посилається конфігурація маршрутів бенчмарку.
"""

from __future__ import annotations

from collections.abc import Callable

from app.enrich.contracts import ProviderCall, ProviderError, ProviderReply

Script = Callable[[ProviderCall], dict[str, object]]


class ScriptedProvider:
    """Відповідає заготовленим виходом; рахує звернення.

    `script` отримує канонічний виклик і повертає обʼєкт-відповідь.
    `fail_with` перетворює провайдера на завжди-збійного — для перевірки
    fallback і журналювання невдалих спроб.
    """

    def __init__(
        self,
        name: str = "scripted",
        script: Script | None = None,
        fail_with: ProviderError | None = None,
    ) -> None:
        self.name = name
        self._script = script
        self._fail_with = fail_with
        self.calls: list[ProviderCall] = []

    async def generate_structured(self, call: ProviderCall) -> ProviderReply:
        self.calls.append(call)
        if self._fail_with is not None:
            raise self._fail_with
        if self._script is None:
            raise ProviderError("not_configured", "скрипт не заданий")
        return ProviderReply(
            output=dict(self._script(call)),
            model=call.model,
            request_id=f"scripted-{len(self.calls)}",
            # Детерміновані «токени»: поля провенансу мають чим заповнитись
            # і в безкоштовному прогоні, а тест бачить, що вони записані.
            input_tokens=len(call.prompt) // 4,
            output_tokens=64,
        )
