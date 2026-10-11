from __future__ import annotations

from app.audit.performance.base import PerformanceProvider
from app.audit.performance.lighthouse import LighthouseProvider
from app.audit.performance.psi import PsiProvider
from app.audit.types import PerformanceResult, Strategy
from app.core.config import settings
from app.core.logging import log


class AutoProvider:
    """PSI за замовчуванням, фолбек на власний Lighthouse при помилці."""

    name = "auto"

    def __init__(self) -> None:
        self._primary = PsiProvider()
        self._fallback = LighthouseProvider()

    async def measure(self, url: str, strategy: Strategy) -> PerformanceResult:
        result = await self._primary.measure(url, strategy)
        if result.fetched:
            return result
        log.info("perf_fallback", url=url, reason=result.error)
        return await self._fallback.measure(url, strategy)


def get_provider(name: str | None = None) -> PerformanceProvider:
    match (name or settings.perf_provider):
        case "psi":
            return PsiProvider()
        case "lighthouse":
            return LighthouseProvider()
        case _:
            return AutoProvider()
