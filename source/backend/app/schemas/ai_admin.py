"""Контракти адмін-розділів AI: два домени, дві окремі схеми.

Секретів тут немає за побудовою: стан ключа — булеве
`key_configured`, значення не існує в жодному полі.
"""

from __future__ import annotations

from pydantic import BaseModel


class RouteOut(BaseModel):
    provider: str
    model: str


class AnalysisProviderOut(BaseModel):
    provider: str
    key_configured: bool


class AnalysisOverrideOut(BaseModel):
    default_provider: str | None
    default_model: str | None


class AnalysisSettingsOut(BaseModel):
    domain: str
    enabled: bool
    default_routes: dict[str, list[RouteOut]]
    override: AnalysisOverrideOut
    max_attempts: int
    attempt_timeout_s: float
    max_output_tokens: int
    providers: list[AnalysisProviderOut]


class PresenceProviderPolicyOut(BaseModel):
    enabled: bool
    model: str
    default_country: str | None


class PresencePolicyOut(BaseModel):
    enabled: bool
    providers: dict[str, PresenceProviderPolicyOut]
    runs_per_prompt: int
    max_prompts: int
    retry_limit: int
    raw_retention_days: int
    concurrency: int


class PresenceAuditCostModelOut(BaseModel):
    """Ціна однієї моделі каталогу і вартість одного спостереження нею."""

    provider: str
    model: str
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    cached_input_usd_per_mtok: float | None = None
    search_usd_per_1k: float | None = None
    cost_per_observation: float


class PresenceAuditCostLastOut(BaseModel):
    """Останній справжній адмінський аудит — факт, а не оцінка."""

    at: str
    url: str
    total_usd: float
    observations_total: int
    per_provider: dict[str, float]


class PresenceAuditCostOut(BaseModel):
    """Собівартість одного повного аудиту присутності.

    `models` ключується рядком «провайдер/модель» — каталог росте, тож
    ключі динамічні, а форма значення фіксована.
    """

    modes: int
    prompts: int
    runs_per_prompt: int
    reference_source: str
    reference_date: str
    selected: dict[str, str]
    models: dict[str, PresenceAuditCostModelOut]
    last_audit: PresenceAuditCostLastOut | None = None


class PresenceProviderStatusOut(BaseModel):
    provider: str
    enabled: bool
    model: str
    key_configured: bool
    production_adapter: bool
    supports_web_search: bool
    supports_location: bool
    default_country: str | None


class PresenceSettingsOut(BaseModel):
    domain: str
    policy: PresencePolicyOut
    providers: list[PresenceProviderStatusOut]
