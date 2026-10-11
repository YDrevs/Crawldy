"""Провайдеро-нейтральні контракти шару збагачення.

Задача описує, ЩО їй потрібно (структурний вихід, бюджети, схема);
маршрутизація вирішує, ХТО це виконає. Імена провайдерів і моделей у
цих типах не зʼявляються ніде, крім полів провенансу, куди записується
те, що фактично відбулося.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskType(StrEnum):
    SITE_UNDERSTANDING = "site_understanding"
    ROOT_CAUSE_GROUPING = "root_cause_grouping"
    REMEDIATION_PLAN = "remediation_plan"


class EnrichmentStatus(StrEnum):
    """Стан логічного прогону. Збій тут ніколи не є збоєм аудиту."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    # Провайдер недоступний / нема здорового кандидата: результату немає
    # з зовнішніх причин, і повторити пізніше має сенс.
    UNAVAILABLE = "unavailable"
    # Провайдер відповів, але відповідь не пройшла валідацію: повтор без
    # зміни задачі навряд чи допоможе, це наша межа, а не його погода.
    FAILED = "failed"


class AttemptOutcome(StrEnum):
    """Операційні категорії збою — провайдеро-нейтральні за побудовою.

    Розділені не за красою, а за тим, що з ними робити далі. Три пари,
    які легко злити в одну й потім не зрозуміти журнал:

    - `NOT_CONFIGURED` проти `AUTHENTICATION_ERROR`: ключа немає взагалі
      проти «ключ є, але провайдер його відхилив». Перше лагодить
      конфігурація, друге — власник акаунта. Ми вже одного разу
      втратили прогін на мертвому ключі, і журнал мусить називати це
      своїм імʼям.
    - `INSUFFICIENT_QUOTA` / `BILLING_ERROR` проти `RATE_LIMIT`: у OpenAI
      всі троє можуть прийти під HTTP 429. Чекати варто лише на
      третьому; на перших двох чекання — марна трата часу.
    - `INVALID_REQUEST` проти `PROVIDER_ERROR`: наш запит проти чужої
      погоди.
    """

    OK = "ok"
    TIMEOUT = "timeout"
    PROVIDER_ERROR = "provider_error"
    REFUSED = "refused"
    INVALID_OUTPUT = "invalid_output"
    # Crawldy не має придатної конфігурації: ключа немає, налаштування
    # відсутнє. Відхилений провайдером ключ сюди НЕ належить.
    NOT_CONFIGURED = "not_configured"
    # Ключ заданий, але провайдер його не прийняв: недійсний, відкликаний,
    # прострочений, без прав.
    AUTHENTICATION_ERROR = "authentication_error"
    # Квота акаунта вичерпана. Повтор тим самим запитом не допоможе.
    INSUFFICIENT_QUOTA = "insufficient_quota"
    # Платіжний стан не дає користуватися API.
    BILLING_ERROR = "billing_error"
    # Тимчасове обмеження частоти — єдиний клас, де чекати справді варто.
    RATE_LIMIT = "rate_limit"
    # Провайдер відбив сам запит — найчастіше схему, яку його діалект не
    # приймає. Повтор тим самим запитом не допоможе.
    INVALID_REQUEST = "invalid_request"
    # Модель уперлася в стелю вихідних токенів: відповідь обірвана на
    # середині. Окремо від `INVALID_OUTPUT`, бо це наша межа виконання,
    # а не зіпсована відповідь — і лікується вона бюджетом, а не задачею.
    OUTPUT_LIMIT = "output_limit"


@dataclass(slots=True)
class ProviderUsage:
    """Спожите провайдером — окремо від відповіді.

    Потрібне саме тому, що збійна спроба теж коштує грошей: обрив по
    стелі виходу спалює токени сповна.
    """

    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_write_tokens: int | None = None
    cache_read_tokens: int | None = None
    model: str | None = None


class ProviderError(Exception):
    """Збій на боці провайдера, у категоріях, спільних для всіх адаптерів.

    Провайдеро-специфічні винятки (anthropic.*, openai.*) не мають
    перетинати межу адаптера: код задач і раннера ловить лише цей тип.
    """

    def __init__(
        self, category: str, detail: str, usage: ProviderUsage | None = None
    ) -> None:
        super().__init__(detail)
        self.category = category
        self.detail = detail
        # Провайдер міг спожити токени й до збою — найяскравіше при
        # обриві по стелі виходу. Втрачати оплачене лише тому, що
        # логічна задача не вдалася, не можна: рахунок виставлять усе одно.
        self.usage = usage


class TaskValidationError(Exception):
    """Вихід моделі не пройшов перевірку контракту задачі."""


@dataclass(slots=True)
class ProviderCall:
    """Один канонічний запит: усе, що адаптеру треба знати.

    `schema` — контракт Crawldy (JSON Schema). Як саме він перетвориться
    на параметри конкретного API — справа адаптера.
    """

    system: str
    prompt: str
    schema: dict[str, Any]
    model: str
    max_output_tokens: int
    timeout_s: float


@dataclass(slots=True)
class ProviderReply:
    """Відповідь адаптера: розібраний обʼєкт плюс метадані провенансу.

    Кешовані токени лежать окремо від `input_tokens` навмисно — так їх
    віддає провайдер і так їх тарифікують. Скласти все в одне число
    означало б порахувати запис у кеш за ціною звичайного входу, а
    читання з кешу — вдесятеро дорожче, ніж воно коштує.
    """

    output: dict[str, Any]
    model: str
    request_id: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_write_tokens: int | None = None
    cache_read_tokens: int | None = None


@dataclass(slots=True)
class TaskRequest:
    """Логічна одиниця роботи: зібраний вхід однієї задачі для одного аудиту.

    `input` — канонічний вхід, з якого рахується input_hash. Він містить
    ЛИШЕ детерміністичний матеріал аудиту й публічний вміст сайту —
    жодних облікових даних, токенів чи внутрішніх ідентифікаторів.
    """

    task_type: TaskType
    task_version: str
    prompt_version: str
    schema_version: str
    locale: str
    input: dict[str, Any]
    input_hash: str


@dataclass(slots=True)
class AttemptRecord:
    """Провенанс однієї спроби: що реально викликалось і чим скінчилось.

    `cost_usd` лишається None, коли надійної цінової бази немає —
    вигаданої вартості в журналі бути не може. Токени при цьому
    записуються завжди, коли провайдер їх віддав.
    """

    number: int
    provider: str
    # Фактична модель, якою провайдер відпрацював. Може бути датованим
    # знімком запитаної (`gpt-5.4-mini-2026-03-17`), і саме її зберігає
    # провенанс: вдавати, що знімка не було, означало б збрехати про те,
    # чим порахований результат.
    model: str
    outcome: AttemptOutcome
    started_at: str
    finished_at: str
    # Що ми просили маршрутом. Дорівнює `model`, коли провайдер не
    # підставив знімок.
    requested_model: str = ""
    # Під яким імʼям шукалася ціна. None — ціни не знайшли, і вартість
    # чесно лишилась порожньою.
    pricing_key: str | None = None
    latency_ms: int | None = None
    request_id: str | None = None
    error_category: str | None = None
    error: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_write_tokens: int | None = None
    cache_read_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None
    pricing_version: str | None = None


@dataclass(slots=True)
class RunOutcome:
    """Підсумок логічного прогону: статус, результат і всі спроби.

    Спроби — включно з невдалими: fallback не ховається, кожна спроба
    з фактичним провайдером і моделлю лягає в журнал.
    """

    status: EnrichmentStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    attempts: list[AttemptRecord] = field(default_factory=list)
