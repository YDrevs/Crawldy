"""Контракт задачі збагачення: провайдеро-нейтральний за побудовою.

Задача володіє: версією, промптом, схемою виходу (контракт Crawldy, не
провайдера), правилами валідації й детермінованим dry-run виходом.
Задача НЕ знає: імен провайдерів, імен моделей, форматів їхніх API.
Тест архітектури сканує цю течку на провайдерські імена й імпорти.

`validate` повертає очищений вихід або кидає `TaskValidationError`.
Семантичне правило спільне для всіх трьох задач: модель може посилатися
ЛИШЕ на те, що є у вході. Невідоме посилання — не «додаткова знахідка»,
а провал валідації: фаза 1 міркує над відомими проблемами, а не шукає
довільні нові.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.enrich.contracts import TaskRequest, TaskType
from app.enrich.identity import input_hash


@dataclass(frozen=True, slots=True)
class TaskSpec:
    type: TaskType
    version: str
    prompt_version: str
    schema_version: str
    system: str
    schema: dict[str, Any]
    render_prompt: Callable[[dict[str, Any]], str]
    validate: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
    # Схемо-валідний вихід із самого входу, без мережі: тести й бенчмарк
    # у режимі dry-run проходять весь конвеєр, не витративши ні цента.
    dry_output: Callable[[dict[str, Any]], dict[str, Any]]


def build_request(spec: TaskSpec, payload: dict[str, Any], locale: str = "en") -> TaskRequest:
    """Канонічний запит з ідемпотентною ідентичністю.

    Локаль — частина канонічного входу, а отже й хешу: результат іншою
    мовою — це ІНШИЙ збережений артефакт, а не привід перегенерувати цей.
    Фаза 1 працює канонічною англійською; звітної локалізації тут немає.
    """
    canonical = {"locale": locale, **payload}
    return TaskRequest(
        task_type=spec.type,
        task_version=spec.version,
        prompt_version=spec.prompt_version,
        schema_version=spec.schema_version,
        locale=locale,
        input=canonical,
        input_hash=input_hash(canonical),
    )


def require_keys(output: dict[str, Any], keys: tuple[str, ...]) -> None:
    from app.enrich.contracts import TaskValidationError

    missing = [key for key in keys if key not in output]
    if missing:
        raise TaskValidationError(f"у відповіді бракує полів: {', '.join(missing)}")
