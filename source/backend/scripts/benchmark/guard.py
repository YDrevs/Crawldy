"""Тверда заборона платних викликів під час прогону корпусу.

## Навіщо

Тисяча сайтів × платний виклик = рахунок, який ніхто не планував. Гірше
за самі гроші те, що збій тут тихий: шар моделі мовчки вмикається з
`.env`, прогін завершується, і дізнаєшся про це з виписки.

## Чому саме так

Гард не покладається на налаштування, бо налаштування й є ризиком. Він
підміняє **самі SDK**: `anthropic` і `openai` імпортуються ліниво
всередині функцій, тож заміна модуля в `sys.modules` перехоплює будь-який
шлях — і теперішній, і той, який хтось додасть завтра, не знаючи про цей
файл.

Падає закрито: якщо код усе ж спробує звернутися до провайдера, прогін
зупиниться з помилкою, а не витратить кредит.
"""

from __future__ import annotations

import sys
import types
from typing import Any


class PaidCallBlocked(RuntimeError):
    """Спроба платного виклику під час прогону корпусу."""


def _forbidden(name: str) -> Any:
    def factory(*_args: Any, **_kwargs: Any) -> Any:
        raise PaidCallBlocked(
            f"бенчмарк спробував створити клієнт {name}. Платні виклики під час "
            f"прогону корпусу заборонені: використайте фікстури або запустіть "
            f"окремий, окремо погоджений платний тест."
        )

    return factory


#: Що стояло до гарда. Порожньо — гард не встановлений.
_before: dict[str, Any] | None = None


def install() -> list[str]:
    """Заблокувати платні шляхи. Повертає, що саме заблоковано."""
    from app.core.config import settings

    global _before
    if _before is None:
        # Знімається один раз: повторний `install()` не має записати
        # підмінений модуль як «оригінал» — інакше відновлення поверне
        # заглушку й гард стане невіддільним від процесу назавжди.
        _before = {
            "anthropic": sys.modules.get("anthropic"),
            "openai": sys.modules.get("openai"),
            "llm_enabled": settings.llm_enabled,
            "enrich_enabled": settings.enrich_enabled,
        }

    blocked: list[str] = []

    # 1. Налаштування: шар, що впливає на бал, і шар збагачення.
    settings.llm_enabled = False
    settings.enrich_enabled = False
    blocked.append("settings.llm_enabled=False")
    blocked.append("settings.enrich_enabled=False")

    # 2. Самі SDK. Підміна модуля, а не функції: імпорт ліниво стоїть
    #    усередині методів провайдерів, тож перехоплювати треба те, що
    #    вони імпортують.
    for name, attributes in (
        ("anthropic", ("Anthropic", "AsyncAnthropic")),
        ("openai", ("OpenAI", "AsyncOpenAI")),
    ):
        module = types.ModuleType(name)
        for attribute in attributes:
            setattr(module, attribute, _forbidden(f"{name}.{attribute}"))
        # Винятки, на які провайдери посилаються при обробці помилок.
        module.APIError = PaidCallBlocked  # type: ignore[attr-defined]
        module.APIStatusError = PaidCallBlocked  # type: ignore[attr-defined]
        module.RateLimitError = PaidCallBlocked  # type: ignore[attr-defined]
        module.APITimeoutError = PaidCallBlocked  # type: ignore[attr-defined]
        sys.modules[name] = module
        blocked.append(f"sys.modules[{name!r}]")

    return blocked


def restore() -> None:
    """Зняти гард і повернути процес у стан до нього.

    Гард — глобальний стан процесу: він підміняє записи в `sys.modules`,
    тобто впливає на весь інтерпретатор, а не на свого викликача. Для
    прогону корпусу це саме те, що треба, і знімати його там ніколи не
    потрібно — процес існує рівно заради прогону.

    Потрібно це тестам. Поки шляху назад не було, тести бенчмарку тихо
    ламали 23 інші: усе, що після них імпортувало справжні `anthropic`
    чи `openai`, отримувало заглушку. Кожен окремий файл був зелений,
    падала лише повна вибірка — тобто дефект залежав від порядку.
    """
    global _before
    if _before is None:
        return
    from app.core.config import settings

    for name in ("anthropic", "openai"):
        original = _before[name]
        if original is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original
    settings.llm_enabled = _before["llm_enabled"]
    settings.enrich_enabled = _before["enrich_enabled"]
    _before = None


def is_installed() -> bool:
    """Чи стоїть гард. Використовується в перевірках перед прогоном."""
    module = sys.modules.get("anthropic")
    if module is None:
        return False
    client = getattr(module, "AsyncAnthropic", None)
    if client is None:
        return False
    try:
        client()
    except PaidCallBlocked:
        return True
    except Exception:  # noqa: BLE001 — будь-що інше означає справжній SDK
        return False
    return False


__all__ = ["PaidCallBlocked", "install", "is_installed", "restore"]
