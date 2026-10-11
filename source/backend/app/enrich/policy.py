"""Адмін-політика домену AI-аналізу: окрема від присутності.

Мінімальне розширення наявної архітектури, не редизайн: збагачення вже
приймає інʼєкцію маршрутів (`execute_run(..., routes=...)`), тож
політика лише будує цю інʼєкцію з адмін-конфігурації. Порожня політика
означає «як було» — DEFAULT_ROUTES без жодної зміни поведінки.

Твердий інваріант доменів: цей модуль не читає і не пише політику
присутності, а зміна будь-якого поля тут не впливає на спостереження
присутності — у них власний рядок `ai_domain_settings` і власний код.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.catalog import capability
from app.enrich.contracts import TaskType
from app.enrich.routing import DEFAULT_ROUTES, RouteCandidate, Routes

DOMAIN = "analysis"

ANALYSIS_PROVIDERS = ("anthropic", "openai")


@dataclass(slots=True, frozen=True)
class AnalysisPolicy:
    """Перекриття маршруту аналізу. None — DEFAULT_ROUTES без змін."""

    default_provider: str | None = None
    default_model: str | None = None


DEFAULT_ANALYSIS_POLICY = AnalysisPolicy()


def from_stored(policy_json: dict[str, Any] | None) -> AnalysisPolicy:
    if not policy_json:
        return DEFAULT_ANALYSIS_POLICY
    provider = policy_json.get("default_provider")
    model = policy_json.get("default_model")
    return AnalysisPolicy(
        default_provider=str(provider) if provider else None,
        default_model=str(model) if model else None,
    )


def to_stored(policy: AnalysisPolicy) -> dict[str, Any]:
    return {
        "default_provider": policy.default_provider,
        "default_model": policy.default_model,
    }


def validate(policy: AnalysisPolicy) -> list[str]:
    errors: list[str] = []
    if bool(policy.default_provider) != bool(policy.default_model):
        errors.append("default_provider і default_model задаються разом")
    if policy.default_provider and policy.default_provider not in ANALYSIS_PROVIDERS:
        errors.append(f"провайдер без адаптера аналізу: {policy.default_provider}")
    if (policy.default_provider and policy.default_model
            and capability(policy.default_provider, policy.default_model) is None):
        errors.append(
            "модель відсутня в каталозі: "
            f"{policy.default_provider}/{policy.default_model}"
        )
    return errors


def routes_for(policy: AnalysisPolicy) -> Routes | None:
    """Маршрути для збагачення. None — жодного перекриття."""
    if not (policy.default_provider and policy.default_model):
        return None
    override = RouteCandidate(policy.default_provider, policy.default_model)
    # Перекриття ставить обраного кандидата ПЕРШИМ, лишаючи типовий
    # маршрут як fallback, — політика змінює вибір, не ламаючи стійкість.
    return {
        task: (override, *[c for c in candidates if c != override])
        for task, candidates in DEFAULT_ROUTES.items()
    }


def status_view(policy: AnalysisPolicy) -> dict[str, Any]:
    """Безпечний огляд домену аналізу для адмінки: без секретів."""
    from app.ai.catalog import key_configured
    from app.core.config import settings

    return {
        "domain": DOMAIN,
        "enabled": settings.enrich_enabled,
        "default_routes": {
            task.value: [
                {"provider": c.provider, "model": c.model} for c in candidates
            ]
            for task, candidates in DEFAULT_ROUTES.items()
        },
        "override": to_stored(policy),
        "max_attempts": settings.enrich_max_attempts,
        "attempt_timeout_s": settings.enrich_attempt_timeout_s,
        "max_output_tokens": settings.enrich_max_output_tokens,
        "providers": [
            {"provider": name, "key_configured": key_configured(name)}
            for name in ANALYSIS_PROVIDERS
        ],
    }


__all__ = [
    "ANALYSIS_PROVIDERS",
    "DOMAIN",
    "AnalysisPolicy",
    "TaskType",
    "from_stored",
    "routes_for",
    "status_view",
    "to_stored",
    "validate",
]
