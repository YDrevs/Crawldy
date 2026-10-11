from __future__ import annotations

from typing import Protocol

from app.audit.types import RenderResult


class Renderer(Protocol):
    """Виконує JS на сторінці й повертає підсумковий HTML.

    Протокол, а не базовий клас, з тієї ж причини, що й у
    PerformanceProvider: чеки й оркестратор нічого не знають про те,
    хто саме рендерить, і тести підставляють свою реалізацію без
    браузера.
    """

    name: str

    async def render(self, url: str) -> RenderResult: ...

    async def aclose(self) -> None: ...


class NullRenderer:
    """Рендерер, який чесно каже, що не рендерив.

    Потрібен не для тестів, а для продакшену: Playwright може бути не
    встановлений, браузер не завантажений, пам'яті в контейнері
    забракнути. У всіх цих випадках аудит має пройти без JS-сигналів,
    а не впасти — те саме правило, що й з відсутнім ключем PSI.
    """

    name = "null"

    def __init__(self, reason: str, *, disabled: bool = False) -> None:
        self.reason = reason
        self.disabled = disabled

    async def render(self, url: str) -> RenderResult:
        return RenderResult(url=url, rendered=False, error=self.reason, disabled=self.disabled)

    async def aclose(self) -> None:
        return None
