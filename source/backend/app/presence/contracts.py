"""Канонічні типи присутності: родини доказів, статуси, запис спостереження.

Одиниця виміру — одне спостереження: (промпт × провайдер × повтор).
Відповідь без виклику пошуку — теж спостереження (модель може знати
бренд із навчання), але цитувань у ній бути не може, і прапорець
`searched` тримає цю різницю видимою.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class EvidenceFamily(StrEnum):
    """Родина доказу. Змішувати знаменники різних родин заборонено."""

    SYNTHETIC = "synthetic"
    # first-party зʼявиться у P1; значення оголошене вже зараз, щоб
    # збережені рядки різних родин ніколи не зливались в один запит.
    FIRST_PARTY = "first_party"


class PromptCategory(StrEnum):
    CATEGORY = "category"          # «найкращі X у Y»
    NEED = "need"                  # «як вирішити проблему Z»
    COMPARISON = "comparison"      # «порівняйте варіанти X»
    INFORMATIONAL = "informational"
    LOCAL = "local"
    BRANDED = "branded"


# Категорії, відповіді на які за задумом — перелік варіантів: лише на
# них «бренд згадано» означає «бренд включено в рекомендацію».
LIST_CATEGORIES = frozenset({PromptCategory.CATEGORY, PromptCategory.COMPARISON})


class Segment(StrEnum):
    """Брендові й небрендові промпти живуть в окремих знаменниках."""

    UNBRANDED = "unbranded"
    BRANDED = "branded"


class Mode(StrEnum):
    """Режим вимірювання. Знаменники режимів не змішуються ніколи.

    NATURAL — модель сама вирішує, чи шукати: пошук доступний, відповідь
    без пошуку — повноцінне спостереження (модель може знати бренд із
    навчання), але цитат у ній бути не може.

    EXPLICIT — промпт явно просить актуальну, заземлену в вебі відповідь;
    там, де API вміє примусити інструмент (OpenAI tool_choice), пошук
    примушується, в інших — лишається проханням, і чи стався пошук
    насправді, каже прапорець `searched`, а не наша віра.
    """

    NATURAL = "natural"
    EXPLICIT = "explicit"


class ObservationStatus(StrEnum):
    OK = "ok"
    PROVIDER_ERROR = "provider_error"
    RATE_LIMITED = "rate_limited"
    REFUSED = "refused"                 # провайдер відмовився відповідати
    NOT_CONFIGURED = "not_configured"   # немає ключа/адаптера
    BUDGET_EXHAUSTED = "budget_exhausted"
    # Захисної межі вартості виклику немає в конфігурації — платний
    # виклик не стартує (fail closed). Це стан НАШОЇ конфігурації, а не
    # збій провайдера і не властивість сайту клієнта.
    BUDGET_COST_BOUND_UNAVAILABLE = "budget_cost_bound_unavailable"


# Статуси, що потрапляють у знаменники метрик. Решта — «не спостережено»:
# збійна клітинка ніколи не рахується як нульова присутність.
OBSERVED_STATUSES = frozenset({ObservationStatus.OK})

# Статуси, після яких повтор має сенс (володіє повторами раннер).
RETRYABLE_STATUSES = frozenset(
    {ObservationStatus.PROVIDER_ERROR, ObservationStatus.RATE_LIMITED}
)


@dataclass(slots=True, frozen=True)
class PresencePrompt:
    """Один промпт затвердженого набору."""

    prompt_id: str            # стабільний у межах версії набору
    text: str
    category: PromptCategory
    segment: Segment
    language: str             # BCP 47 primary tag, напр. "uk"


@dataclass(slots=True, frozen=True)
class PromptSet:
    """Версійований набір: зміна версії рве порівнянність історії."""

    version: str
    prompts: tuple[PresencePrompt, ...]

    @property
    def unbranded(self) -> tuple[PresencePrompt, ...]:
        return tuple(p for p in self.prompts if p.segment is Segment.UNBRANDED)

    @property
    def branded(self) -> tuple[PresencePrompt, ...]:
        return tuple(p for p in self.prompts if p.segment is Segment.BRANDED)


@dataclass(slots=True)
class ProviderUsage:
    """Спожите за один виклик — окремо від відповіді: збій теж коштує."""

    input_tokens: int = 0
    output_tokens: int = 0
    searches: int = 0


@dataclass(slots=True)
class ProviderAnswer:
    """Нормалізована відповідь провайдера ДО тлумачення.

    Адаптер витягує лише механічне: текст, циовані адреси, чи був пошук.
    Судження (бренд згадано, домен процитовано) — робота normalize, і
    вона однакова для всіх провайдерів.
    """

    text: str
    cited_urls: list[str] = field(default_factory=list)
    searched: bool = False
    # Пошукові запити, які модель справді виконала, — коли провайдер їх
    # віддає (OpenAI action.query, Gemini google_search_call.queries,
    # Anthropic server_tool_use.input.query). Немає — порожньо, не вигадка.
    search_queries: list[str] = field(default_factory=list)
    model: str = ""
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    # Фактична вартість, коли провайдер віддає її сам (Agent API): для
    # обліку авторитетніша за наш розрахунок, але стелі бюджету не
    # обходить — допуск вирішується до виклику.
    provider_cost_usd: float | None = None
    # Ідентифікатор запиту/відповіді провайдера, коли він його віддає
    # (responseId у generateContent, id в Interactions): лягає в рядок
    # спроби — суперечку про конкретне списання ведуть за ним.
    provider_request_id: str | None = None
    raw: dict[str, object] = field(default_factory=dict)


class PresenceProviderError(Exception):
    """Єдиний виняток межі провайдера з категорією зі статусної моделі.

    `incurred_usd` каже бюджету, що сталося з грошима: 0.0 — АВТОРИТЕТНО
    відомо, що провайдер не тарифікував (запит не покинув наш процес:
    немає ключа, немає SDK, скриптований провайдер); None — невідомо
    (таймаут, обрив, 429, будь-яка HTTP-помилка після відправлення) —
    тоді книга чесно утримує зарезервований максимум, а не нуль.
    Замовчування — None: помилка, що забула оголосити долю грошей,
    коштує резерв, а не тихо оголошує себе безкоштовною. Жодного
    глобального правила «429 не білиться» немає — нуль вимагає
    авторитетного підтвердження конкретного провайдера.
    """

    def __init__(
        self, status: ObservationStatus, detail: str,
        *, incurred_usd: float | None = None,
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.incurred_usd = incurred_usd


@dataclass(slots=True)
class ObservationRecord:
    """Повний запис спостереження — те, що зберігається назавжди."""

    provider: str
    model: str
    tool_version: str
    prompt: PresencePrompt
    prompt_set_version: str
    run_index: int
    country: str | None
    status: ObservationStatus
    mode: Mode = Mode.NATURAL
    # Точний надісланий текст: у explicit-режимі він відрізняється від
    # prompt.text доданою інструкцією заземлення.
    sent_text: str = ""
    searched: bool = False
    search_queries: list[str] = field(default_factory=list)
    answer_excerpt: str = ""
    cited_urls: list[str] = field(default_factory=list)
    cited_domains: list[str] = field(default_factory=list)
    brand_mentioned: bool = False
    matched_alias: str | None = None
    domain_cited: bool = False
    pages_cited: list[str] = field(default_factory=list)
    # Власна адреса, що стоїть у ТЕКСТІ відповіді (пряме посилання) —
    # окремо від цитати провайдера: це різні твердження.
    domain_linked: bool = False
    linked_urls: list[str] = field(default_factory=list)
    recommended: bool | None = None      # лише для LIST_CATEGORIES
    observed_domains: list[str] = field(default_factory=list)
    error: str | None = None
    usage: ProviderUsage = field(default_factory=ProviderUsage)
    cost_usd: float = 0.0
    retries: int = 0
    duration_ms: int = 0
    normalize_version: str = ""
    raw: dict[str, object] | None = None
