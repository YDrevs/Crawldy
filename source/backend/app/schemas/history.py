"""Контракт історії балів.

Досі обидва маршрути історії віддавали dict, зібраний руками в самому
маршруті, — тобто контракт існував, але ніде не був оголошений, і зміна
ключа в `to_json()` зламала б клієнтів мовчки. Тепер форма зафіксована
схемою: FastAPI перевіряє її на кожній відповіді, а контрактний тест — на
кожному прогоні.

Форми віддзеркалюють `report/history.py::to_json` навмисно точно: це вже
опублікований контракт, і формалізація не має права його зрушити.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ScorePointOut(BaseModel):
    """Один аудит в історії сайту."""

    audit_id: str
    at: str  # ISO 8601; рядок, бо так уже опубліковано в to_json()
    overall: int | None
    scores: dict[str, int] = Field(default_factory=dict)
    versions: dict[str, Any] = Field(default_factory=dict)
    can_be_recomputed: bool = False


class HistoryStepOut(BaseModel):
    """Крок між двома аудитами й межі, у яких різниці можна вірити."""

    before: ScorePointOut
    after: ScorePointOut
    days_between: int
    overall_delta: int | None
    by_module: dict[str, int] = Field(default_factory=dict)
    comparable: bool
    changed_in_us: list[str] = Field(default_factory=list)
    rebased: bool = False


class HistoryOut(BaseModel):
    """Історія балів за origin."""

    origin: str
    # Вікно видимості тарифу. None — показано все. Поле в контракті
    # навмисно: обрізана крива без пояснення читається як «раніше
    # аудитів не було».
    visible_days: int | None = None
    points: list[ScorePointOut] = Field(default_factory=list)
    steps: list[HistoryStepOut] = Field(default_factory=list)
    incomparable_steps: int = 0
    fixable_by_recompute: int = 0


class SiteRefOut(BaseModel):
    id: str
    origin: str
    name: str


class SiteHistoryOut(BaseModel):
    """Історія балів сайту як бізнес-ресурсу."""

    site: SiteRefOut
    visible_days: int | None = None
    points: list[ScorePointOut] = Field(default_factory=list)
    steps: list[HistoryStepOut] = Field(default_factory=list)
    incomparable_steps: int = 0
    fixable_by_recompute: int = 0


__all__ = [
    "HistoryOut",
    "HistoryStepOut",
    "ScorePointOut",
    "SiteHistoryOut",
    "SiteRefOut",
]
