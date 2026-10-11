"""Імпорт модулів реєструє всі чеки в REGISTRY."""

from app.audit.checks import (  # noqa: F401
    accessibility,
    ai_ready,
    conversion,
    llm_visibility,
    performance,
    seo,
    tech,
)
from app.audit.checks.base import REGISTRY, Check, all_checks, register

__all__ = ["REGISTRY", "Check", "all_checks", "register"]
