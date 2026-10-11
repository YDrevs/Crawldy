"""Публічний контракт Actual AI Presence.

Кожна відповідь несе `evidence_family`: клієнт завжди бачить, що перед
ним — контрольовані API-спостереження, а не телеметрія платформ і не
вимір споживчого продукту.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PresenceRunCreate(BaseModel):
    url: str = Field(min_length=4, max_length=2048)
    brand: str = Field(min_length=1, max_length=255)
    brand_aliases: list[str] = Field(default_factory=list, max_length=10)
    category: str = Field(min_length=2, max_length=120)
    services: list[str] = Field(default_factory=list, max_length=3)
    location: str | None = Field(default=None, max_length=120)
    language: str = Field(default="en", max_length=8)
    site_id: uuid.UUID | None = None
    # Ключ ідемпотентності подання: подвійний клік з тим самим ключем
    # знаходить той самий прогін і не резервує право вдруге. Свідомий
    # новий запуск — новий ключ.
    idempotency_key: str | None = Field(default=None, max_length=64)


class PresenceSuggestionOut(BaseModel):
    """Факти для форми прогону, виведені з аудиту. Кожне поле можна змінити."""

    audit_id: uuid.UUID
    url: str
    brand: str
    brand_aliases: list[str]
    category: str
    location: str | None
    language: str
    # Звідки взято кожен непорожній факт: schema | title | domain | site.
    sources: dict[str, str]


class GuestPresenceRunIn(BaseModel):
    """Запуск присутності гостем після оплати: підтверджені або змінені факти."""

    brand: str = Field(min_length=1, max_length=255)
    brand_aliases: list[str] = Field(default_factory=list, max_length=10)
    category: str = Field(min_length=2, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    language: str = Field(default="en", max_length=8)
    idempotency_key: str | None = Field(default=None, max_length=64)


class GuestPresenceOut(BaseModel):
    """Стан присутності для гостьового екрана: що пропонуємо й що вже є."""

    suggestion: PresenceSuggestionOut
    # Право на прогін: куплена одиниця ще не витрачена.
    can_start: bool
    credits_available: int
    providers: list[str]
    runs: list[PresenceRunOut]


class PresenceObservationOut(BaseModel):
    provider: str
    model: str
    prompt_id: str
    prompt_text: str
    category: str
    segment: str
    run_index: int
    mode: str = "natural"
    status: str
    searched: bool
    search_queries: list[str] = Field(default_factory=list)
    brand_mentioned: bool
    domain_cited: bool
    domain_linked: bool = False
    pages_cited: list[str]
    cited_domains: list[str]
    recommended: bool | None
    answer_excerpt: str
    error: str | None


class PresenceRunOut(BaseModel):
    id: uuid.UUID
    url: str
    brand: str
    status: str
    # Сайт кабінету, для якого замовлено прогін. Порожньо, коли прогін
    # запущено поза контекстом сайту: звʼязок оголошується явно й
    # ніколи не виводиться зі схожості адрес.
    site_id: uuid.UUID | None = None
    evidence_family: str = "synthetic"
    prompt_set_version: str
    created_at: datetime
    finished_at: datetime | None
    observations_total: int
    observations_ok: int
    cost_usd: float
    error: str | None
    # Підсумок права: чим оплачено, чи розраховано, чи придатний прогін.
    entitlement_source: str | None = None
    entitlement_settled: bool = False
    deliverable: bool | None = None
    # Формулювання походження — незмінна частина контракту: спостереження
    # через API провайдерів, не вимір споживчих продуктів.
    provenance: str = "controlled_provider_api_checks"


GuestPresenceOut.model_rebuild()


class PresenceRunDetailOut(PresenceRunOut):
    metrics: dict[str, Any]
    coverage: dict[str, Any]
    observations: list[PresenceObservationOut]


class PresenceProviderPlanOut(BaseModel):
    provider: str
    model: str
    configured: bool


class PresenceModelOut(BaseModel):
    """Провайдер і модель, якою він зараз міряє присутність.

    Публічна вітрина: сторінка «Видимість у ШІ» називає моделі, і назвати
    їх треба тими самими, що виконують прогін, — інакше сторінка обіцяє
    одне вимірювання, а продукт робить інше.
    """

    provider: str
    model: str


class PresencePlanOut(BaseModel):
    """Обсяг майбутнього прогону — ДО запуску, без резервування права."""

    enabled: bool
    providers: list[PresenceProviderPlanOut]
    modes: list[str]
    prompts_planned: int
    runs_per_prompt: int
    observations_planned_per_provider: int
    observations_planned_total: int
    allowance_available: bool
    credits_available: int
    can_start: bool
    evidence_family: str = "synthetic"
    provenance: str = "controlled_provider_api_checks"
