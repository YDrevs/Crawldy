"""Провайдер на базі власного Lighthouse-сайдкара.

Сайдкар — Node-сервіс із headless Chrome, який приймає POST /run
{url, strategy} і повертає сирий Lighthouse-звіт (той самий формат, що й
lighthouseResult у PSI), тому парсери перевикористовуємо повністю: і
швидкість, і доступність читає той самий код, що й на шляху PSI.

Поля CrUX (`loadingExperience`) сайдкар не віддає — це польові дані
Google, а не результат локального прогону. Тому `_parse_field` тут немає
й бути не може: вигадати їх нізвідки.
"""

from __future__ import annotations

import httpx

from app.audit.performance.psi import _parse_accessibility, _parse_lab
from app.audit.types import PerformanceResult, Strategy
from app.core.config import settings
from app.core.logging import log


class LighthouseProvider:
    name = "lighthouse"

    def __init__(self, base_url: str | None = None, timeout: float = 180.0) -> None:
        self._base_url = (base_url or settings.lighthouse_url).rstrip("/")
        self._timeout = timeout

    async def measure(self, url: str, strategy: Strategy) -> PerformanceResult:
        result = PerformanceResult(provider=self.name, strategy=strategy, url=url)
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(
                    f"{self._base_url}/run",
                    json={"url": url, "strategy": strategy.value},
                )
            if response.status_code != 200:
                result.error = f"lighthouse HTTP {response.status_code}: {response.text[:200]}"
                return result
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            log.warning("lighthouse_failed", url=url, error=result.error)
            return result

        result.fetched = True
        # Сайдкар може віддати звіт як є або загорнутим — приймаємо обидва варіанти.
        report = payload if "lighthouseResult" in payload else {"lighthouseResult": payload}
        _parse_lab(report, result)
        # Сайдкар повертає і `accessibility` — той самий axe-core, що й
        # усередині PSI. До цього рядка движок її мовчки викидав: на
        # цьому провайдері напрям доступності не існував узагалі, і
        # модуль виключався зі скора при повністю придатних даних у
        # відповіді (E-08). Парсер той самий, що й у PSI, тож придатна
        # категорія дає ті самі поля, а відсутня чи зіпсована лишає їх
        # невиміряними — нуля чи ста з нічого не зʼявляється.
        _parse_accessibility(report, result)
        return result
