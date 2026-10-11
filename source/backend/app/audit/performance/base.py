from __future__ import annotations

from typing import Protocol

from app.audit.types import PerformanceResult, Strategy

# Пороги Core Web Vitals (good / needs-improvement межа).
THRESHOLDS: dict[str, tuple[float, float]] = {
    "LCP": (2500, 4000),
    "INP": (200, 500),
    "CLS": (0.1, 0.25),
    "FCP": (1800, 3000),
    "TTFB": (800, 1800),
    "TBT": (200, 600),
}


def rate(metric: str, value: float | None) -> str | None:
    if value is None or metric not in THRESHOLDS:
        return None
    good, poor = THRESHOLDS[metric]
    if value <= good:
        return "good"
    return "needs-improvement" if value <= poor else "poor"


class PerformanceProvider(Protocol):
    name: str

    async def measure(self, url: str, strategy: Strategy) -> PerformanceResult: ...
