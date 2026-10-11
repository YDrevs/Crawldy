"""Маршрутизація: яка задача → який провайдер і модель.

ЄДИНЕ місце в шарі збагачення, де дозволені конкретні імена провайдерів
і моделей. Задача каже, ЩО їй потрібно; тут вирішується, ХТО виконає.
Порівняння моделей чи додавання fallback — зміна цієї таблиці, а не
коду задач (закріплено тестами: два фейкові провайдери переключаються
самими маршрутами).

Клієнтського вибору моделі для цього шару немає навмисно: клієнт купує
аналіз Crawldy, а не конкретну foundation-модель. Legacy-параметр
`llm_model` належить вимкненому семантичному шару й сюди не проникає.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.enrich.contracts import TaskType

# Піднімати при зміні таблиці маршрутів чи політики fallback: провенанс
# прогону має казати, за якими правилами обирався виконавець.
ROUTING_VERSION = "1"


@dataclass(frozen=True, slots=True)
class RouteCandidate:
    provider: str
    model: str


# Впорядковані кандидати: перший — основний, далі — fallback. Сьогодні
# реальний провайдер один; архітектурно другим рядком може стояти інший
# провайдер без жодної зміни коду задач.
DEFAULT_ROUTES: dict[TaskType, tuple[RouteCandidate, ...]] = {
    TaskType.SITE_UNDERSTANDING: (RouteCandidate("anthropic", "claude-opus-5"),),
    TaskType.ROOT_CAUSE_GROUPING: (RouteCandidate("anthropic", "claude-opus-5"),),
    TaskType.REMEDIATION_PLAN: (RouteCandidate("anthropic", "claude-opus-5"),),
}

Routes = dict[TaskType, tuple[RouteCandidate, ...]]

# ── маршрути порівняння моделей ───────────────────────────────────────────
#
# Конфігурація бенчмарку, а НЕ продуктова маршрутизація: `DEFAULT_ROUTES`
# вище не змінюється. Кандидат тут один на модель навмисно — fallback
# перекривав би те, що ми міряємо: якби Sonnet упав і роботу мовчки
# доробив Opus, у порівнянні виявився б чужий результат.
BENCHMARK_MODELS: dict[str, RouteCandidate] = {
    "opus-5": RouteCandidate("anthropic", "claude-opus-5"),
    "sonnet-5": RouteCandidate("anthropic", "claude-sonnet-5"),
    "gpt-5.4-mini": RouteCandidate("openai", "gpt-5.4-mini"),
}


def benchmark_routes(model_key: str, tasks: tuple[TaskType, ...]) -> Routes:
    """Один і той самий кандидат на всі задачі порівняння."""
    candidate = BENCHMARK_MODELS[model_key]
    return {task: (candidate,) for task in tasks}


def route_for(task: TaskType, routes: Routes | None = None) -> tuple[RouteCandidate, ...]:
    table = DEFAULT_ROUTES if routes is None else routes
    return table.get(task, ())


@dataclass(frozen=True, slots=True)
class ModelPrice:
    """USD за мільйон токенів, окремо для кожного класу.

    Класи роздільні, бо провайдер їх роздільно і тарифікує: запис у кеш
    дорожчий за звичайний вхід, читання з кешу — вдесятеро дешевше.
    Порахувати їх за однією ставкою означає записати в журнал витрат
    неправильне число, а на нього спираються рішення.
    """

    input_: float
    output: float
    cache_write: float
    cache_read: float


# Цінова база. Порожній словник означає «ціни немає» — і тоді вартість
# лишається NULL, бо вигадана вартість у журналі гірша за її відсутність.
#
# Anthropic — platform.claude.com/docs/en/about-claude/pricing, звірено
# 2026-08-24: перший party API, global routing, без Batch і без fast
# mode. Запис у кеш узятий 5-хвилинний (`cache_control: ephemeral`).
#
# OpenAI — developers.openai.com/api/docs/pricing, звірено 2026-08-24:
# стандартний рівень, без Batch і без регіональної надбавки. Окремої
# платної операції запису в кеш там немає — лише дешевше читання, тож
# `cache_write` дорівнює звичайному входу й на рахунок не впливає.
PRICING: dict[str, ModelPrice] = {
    "claude-opus-5": ModelPrice(
        input_=5.00, output=25.00, cache_write=6.25, cache_read=0.50
    ),
    "claude-sonnet-5": ModelPrice(
        input_=2.00, output=10.00, cache_write=2.50, cache_read=0.20
    ),
    "gpt-5.4-mini": ModelPrice(
        input_=0.75, output=4.50, cache_write=0.75, cache_read=0.075
    ),
}
CURRENCY = "USD"
# Піднімати разом зі ставками: збережений рядок мусить лишатися читаним
# після наступної зміни цін.
PRICING_VERSION = "2026-08-24-anthropic-first-party+openai-standard"


def estimate_upper_bound(
    model_key: str, calls: int, max_input_tokens: int, max_output_tokens: int
) -> float | None:
    """Стеля витрат на заплановану партію викликів.

    Свідомо песимістична: увесь вхід рахується некешованим і за повною
    ставкою, увесь вихід — по стелі `max_output_tokens`. Занижена
    оцінка перед платним прогоном гірша за відсутню, бо на неї спираються,
    коли вирішують натиснути «так».
    """
    candidate = BENCHMARK_MODELS.get(model_key)
    if candidate is None:
        return None
    price = PRICING.get(candidate.model)
    if price is None:
        return None
    per_call = (max_input_tokens * price.input_ + max_output_tokens * price.output) / 1_000_000
    return per_call * calls


def pricing_key_for(requested_model: str, actual_model: str | None) -> str | None:
    """Під яким імʼям шукати ціну. None — шукати не можна, вартість NULL.

    Провайдер може відпрацювати датованим знімком: ми просимо
    `gpt-5.4-mini`, а відповідає `gpt-5.4-mini-2026-03-17`. Провенанс
    мусить зберегти фактичне імʼя, але цінник такого ключа не має — і
    перший живий виклик OpenAI записав вартість `None`.

    Ключем стає ЗАПИТАНА модель: саме її ми обрали маршрутом, і саме
    вона є в ціннику. Обрізати суфікс регуляркою було б гірше — вона так
    само радо перетворила б `gpt-5.4-mini` на `gpt-5.4`, тобто на іншу
    модель за іншою ціною.

    Захист від підміни: фактична модель мусить бути або тією самою, або
    її знімком (`<requested>-<щось>`). Якщо провайдер відпрацював чимось
    іншим, ціну не вгадуємо — повертаємо None, і вартість чесно лишається
    порожньою.
    """
    if requested_model not in PRICING:
        return None
    if not actual_model or actual_model == requested_model:
        return requested_model
    if actual_model.startswith(f"{requested_model}-"):
        return requested_model
    # Відповіла інша модель — ціна невідома, і вигадувати її не можна.
    return None


def cost_estimate(
    model: str,
    input_tokens: int | None,
    output_tokens: int | None,
    cache_write_tokens: int | None = None,
    cache_read_tokens: int | None = None,
) -> tuple[float | None, str | None]:
    """(вартість, версія цінника) або (None, None), якщо бази немає.

    `model` — це ЦІНОВИЙ КЛЮЧ (див. `pricing_key_for`), а не обовʼязково
    те імʼя, яке повернув провайдер.
    """
    price = PRICING.get(model)
    if price is None or input_tokens is None or output_tokens is None:
        return None, None
    total = (
        input_tokens * price.input_
        + output_tokens * price.output
        + (cache_write_tokens or 0) * price.cache_write
        + (cache_read_tokens or 0) * price.cache_read
    )
    return total / 1_000_000, PRICING_VERSION
