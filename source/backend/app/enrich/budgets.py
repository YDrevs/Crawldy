"""Бюджет виконання задачі: скільки виходу й скільки часу їй треба.

Це **потужність**, а не семантика. Промпт, схема й вхід від цих чисел не
залежать, тож версії задач вони не піднімають: той самий контракт можна
виконати з різною стелею виходу, і результат лишиться тим самим
контрактом.

## Чому не одне число на всіх

Спроба виконати всі три задачі під спільною межею 3000 токенів і 45
секунд провалилась на живому порівнянні: `site_understanding` вкладався
(1441 / 1182 / 607 токенів), а `root_cause_grouping` і
`remediation_plan` обривалися на середині JSON або не встигали. Причина
структурна: у схемі v2 кожна група несе сім полів, зокрема два окремі
переліки доказів, і на сайті з 33 знахідками вихід просто більший.

Однакова стеля для різних за обсягом робіт — це не однакові умови, а
однакове число. Умови однакові тоді, коли кожна задача має досить місця
виконати саме себе.

## Що мусить лишатися однаковим

Усі моделі порівняння отримують **той самий** бюджет на **ту саму**
задачу. Бюджет прив'язаний до задачі, ніколи до провайдера чи моделі:
інакше порівняння міряло б налаштування, а не моделі.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.enrich.contracts import TaskType


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    max_output_tokens: int
    timeout_s: float


# Значення підібрані за фактичними виходами живого прогону, а не навмання:
# `site_understanding` лишається як був, бо в межу вкладався з великим
# запасом; двом більшим задачам дано стелю, за якої обірваний вихід
# перестає бути межею інструмента.
EXECUTION_BUDGETS: dict[TaskType, ExecutionBudget] = {
    TaskType.SITE_UNDERSTANDING: ExecutionBudget(max_output_tokens=3000, timeout_s=45.0),
    TaskType.ROOT_CAUSE_GROUPING: ExecutionBudget(max_output_tokens=8000, timeout_s=120.0),
    TaskType.REMEDIATION_PLAN: ExecutionBudget(max_output_tokens=8000, timeout_s=120.0),
}


def budget_for(task: TaskType) -> ExecutionBudget:
    """Бюджет задачі. Провайдер і модель на нього не впливають ніколи."""
    return EXECUTION_BUDGETS[task]


def budgets_provenance() -> dict[str, dict[str, float | int]]:
    """Бюджети у вигляді, придатному для запису в артефакт прогону.

    Порівняння без цього непрочитне: два прогони однієї задачі під
    різними стелями — різні умови, і памʼятати про це напамʼять не можна.
    """
    return {
        task.value: {
            "max_output_tokens": budget.max_output_tokens,
            "timeout_s": budget.timeout_s,
        }
        for task, budget in EXECUTION_BUDGETS.items()
    }


__all__ = ["EXECUTION_BUDGETS", "ExecutionBudget", "budget_for", "budgets_provenance"]
