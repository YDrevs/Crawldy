from __future__ import annotations

import importlib.util

from app.audit.llm.base import LlmAnalyst, NullAnalyst
from app.audit.llm.models import is_known
from app.core import runtime_config as runtime
from app.core.config import settings


def get_analyst(enabled: bool | None = None, model: str | None = None) -> LlmAnalyst:
    """Аналітик або чесна відмова з причиною.

    Чотири різні причини мовчання — вимкнено, немає пакета, немає ключа,
    невідома модель — і читач звіту має бачити, яка саме. «Семантичного
    аналізу не було» без пояснення виглядає як збій продукту.
    """
    if not (settings.llm_enabled if enabled is None else enabled):
        # Єдина з чотирьох причин, яка є вибором, а не поломкою. Решта —
        # помилки налаштування, і аудит має лишитися partial.
        return NullAnalyst("семантичний аналіз вимкнено в налаштуваннях", disabled=True)
    if importlib.util.find_spec("anthropic") is None:
        return NullAnalyst("пакет anthropic не встановлено")
    if not runtime.get("anthropic_api_key"):
        return NullAnalyst("не заданий ключ ANTHROPIC_API_KEY")

    chosen = model or settings.llm_model
    if not is_known(chosen):
        # Невідома модель — це помилка налаштування, і мовчати про неї
        # не можна: аудит пройде, а клієнт не знатиме, що семантики в
        # його звіті немає.
        return NullAnalyst(f"невідома модель: {chosen}")

    from app.audit.llm.anthropic_analyst import AnthropicAnalyst

    return AnthropicAnalyst(model=chosen)
