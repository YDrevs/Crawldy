"""Канонічний каталог AI-моделей: можливості, ціни, стан ключів.

ЄДИНЕ місце, де імена моделей зустрічаються з їхніми можливостями й
цінами. Політики доменів (аналіз, присутність) посилаються сюди, але
самі рішення про використання лежать у політиках — не тут.

Ціни — офіційні прейскуранти провайдерів, звірені 2026-09-01:
* Anthropic: web search $10/1k пошуків + токени
  (platform.claude.com/docs .../web-search-tool);
* OpenAI: web search $10/1k викликів на reasoning-моделях + токени
  (developers.openai.com/api/docs/pricing); gpt-5.1 досі в прейскуранті,
  сімʼя gpt-5.6 (sol/terra/luna) — новіші профілі;
* Perplexity: Agent API — perplexity/sonar $0.25/$2.50 за 1M токенів +
  web_search $2.50/1k викликів (docs.perplexity.ai, Agent API pricing).
  Legacy-збір за запит ($5–12/1k) НЕ переноситься: він належав Sonar
  Chat Completions, який підтримується лише до 2026-09-27 (дату звірено
  повторно 2026-09-01 на docs.perplexity.ai);
* Google: Gemini Interactions API, інструмент google_search — токени
  gemini-3.7-flash $0.75/$3.75 за 1M (до 2026-12-31, далі $1.50/$7.50),
  пошук $14/1k запитів після 5k безкоштовних на місяць
  (ai.google.dev/gemini-api/docs/pricing). У бюджеті рахуємо ПЛАТНИЙ
  тариф — безкоштовна квота лише зменшує фактичний рахунок.

Зміна ціни тут — оновлення довідки, а не зміна поведінки: бюджети
рахуються від цих чисел у момент виклику.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ModelCapability:
    provider: str
    model: str
    supports_web_search: bool
    supports_citations: bool
    supports_location: bool
    input_usd_per_mtok: float
    output_usd_per_mtok: float
    # Ціна пошуку/запиту за 1000 викликів; 0 — пошук не тарифікується
    # окремо (або модель без пошуку).
    search_usd_per_1k: float
    # Документована стеля ВХОДУ за один запит (модельне контекстне вікно
    # або явний вхідний ліміт API) — провайдер сам відхиляє більше, тож
    # це enforceable-межа для розрахунку максимуму спроби. None — межі
    # в документації немає, і твердий бюджет не може її вигадати.
    context_window_tokens: int | None = None
    # Чи вміє ЗАПИТ обмежити кількість тарифікованих пошуків
    # (документований параметр: max_uses / max_tool_calls). False —
    # пошуковий вимір необмежений, і максимум спроби нерахований.
    max_searches_boundable: bool = False
    # Ціна кешованого входу, якщо провайдер тарифікує його окремо. Лише
    # довідкова (для показу в адмінці): облік вартості спостереження
    # кешовані токени не розрізняє — провайдер не віддає їх у наш
    # конвеєр окремим полем.
    cached_input_usd_per_mtok: float | None = None


# Ключ — (provider, model). Продуктові адаптери відмовляються працювати
# з моделлю, якої тут немає: невідома модель = невідома ціна = некерований
# бюджет.
CATALOG: dict[tuple[str, str], ModelCapability] = {
    ("anthropic", "claude-sonnet-4-6"): ModelCapability(
        "anthropic", "claude-sonnet-4-6",
        supports_web_search=True, supports_citations=True,
        supports_location=True,
        input_usd_per_mtok=3.0, output_usd_per_mtok=15.0,
        search_usd_per_1k=10.0,
        # Контекстне вікно 1M (platform.claude.com, models, 2026-09-01);
        # пошуки обмежує документований max_uses інструмента.
        context_window_tokens=1_000_000,
        max_searches_boundable=True,
    ),
    ("anthropic", "claude-opus-5"): ModelCapability(
        "anthropic", "claude-opus-5",
        supports_web_search=True, supports_citations=True,
        supports_location=True,
        input_usd_per_mtok=5.0, output_usd_per_mtok=25.0,
        search_usd_per_1k=10.0,
        context_window_tokens=1_000_000,
        max_searches_boundable=True,
    ),
    # Додано для benchmark-порівняння моделей (власник, 2026-09-07).
    # Ціни підтверджені власником у консолі акаунта; той самий адаптер
    # і web_search_20250305, що в Sonnet 4.6.
    ("anthropic", "claude-sonnet-5"): ModelCapability(
        "anthropic", "claude-sonnet-5",
        supports_web_search=True, supports_citations=True,
        supports_location=True,
        input_usd_per_mtok=2.0, output_usd_per_mtok=10.0,
        search_usd_per_1k=10.0,
        context_window_tokens=1_000_000,
        max_searches_boundable=True,
    ),
    ("anthropic", "claude-haiku-4-5"): ModelCapability(
        "anthropic", "claude-haiku-4-5",
        supports_web_search=True, supports_citations=True,
        supports_location=True,
        input_usd_per_mtok=1.0, output_usd_per_mtok=5.0,
        search_usd_per_1k=10.0,
        context_window_tokens=200_000,
        max_searches_boundable=True,
    ),
    ("openai", "gpt-5.1"): ModelCapability(
        "openai", "gpt-5.1",
        supports_web_search=True, supports_citations=True,
        supports_location=True,
        input_usd_per_mtok=1.25, output_usd_per_mtok=10.0,
        search_usd_per_1k=10.0,
        # Документований вхідний ліміт сімʼї gpt-5: 272k (400k вікно
        # мінус 128k зарезервованого виходу) — API відхиляє більше;
        # пошуки обмежує документований max_tool_calls Responses API.
        context_window_tokens=272_000,
        max_searches_boundable=True,
    ),
    ("openai", "gpt-5.6-luna"): ModelCapability(
        "openai", "gpt-5.6-luna",
        supports_web_search=True, supports_citations=True,
        supports_location=True,
        input_usd_per_mtok=0.20, output_usd_per_mtok=1.20,
        search_usd_per_1k=10.0,
        context_window_tokens=272_000,
        max_searches_boundable=True,
    ),
    # Додано для benchmark-порівняння моделей (власник, 2026-09-07).
    # Ціни підтверджені власником; той самий адаптер Responses API, що
    # в gpt-5.1 і luna.
    ("openai", "gpt-5.6-terra"): ModelCapability(
        "openai", "gpt-5.6-terra",
        supports_web_search=True, supports_citations=True,
        supports_location=True,
        input_usd_per_mtok=2.0, output_usd_per_mtok=12.0,
        search_usd_per_1k=10.0,
        context_window_tokens=272_000,
        max_searches_boundable=True,
    ),
    ("openai", "gpt-5.6-sol"): ModelCapability(
        "openai", "gpt-5.6-sol",
        supports_web_search=True, supports_citations=True,
        supports_location=True,
        input_usd_per_mtok=4.0, output_usd_per_mtok=20.0,
        search_usd_per_1k=10.0,
        context_window_tokens=272_000,
        max_searches_boundable=True,
        cached_input_usd_per_mtok=0.40,
    ),
    ("google", "gemini-3.7-flash"): ModelCapability(
        "google", "gemini-3.7-flash",
        supports_web_search=True, supports_citations=True,
        # Interactions API не приймає локацію користувача для
        # google_search — ринок локалізується формулюванням промпту.
        supports_location=False,
        input_usd_per_mtok=0.75, output_usd_per_mtok=3.75,
        search_usd_per_1k=14.0,
        context_window_tokens=1_000_000,
        # Gemini 3.x білиться ЗА КОЖЕН пошуковий запит, а Interactions
        # API не документує жодного параметра, що обмежує їх кількість
        # (ai.google.dev/api/interactions-api, звірено 2026-09-01) —
        # пошуковий вимір необмежений, максимум спроби нерахований,
        # твердий бюджет закривається (fail closed).
        max_searches_boundable=False,
    ),
    # Продуктова модель Google для присутності; виконується бекендом
    # vertex_ai. Ціни ІДЕНТИЧНІ на обох платформах і звірені 2026-09-01:
    # Vertex (продуктове джерело): вхід $0.30/M (text), вихід $2.50/M
    # «response and reasoning» — cloud.google.com/vertex-ai/
    # generative-ai/pricing; Developer API (сумісність):
    # ai.google.dev/gemini-api/docs/pricing — ті самі числа. Межі:
    # контекст 1 048 576, вихід 65 536 — карта моделі Vertex
    # (docs.cloud.google.com/vertex-ai/generative-ai/docs/models/
    # gemini/2-5-flash; статус GA, ДАТА ВИВЕДЕННЯ 2026-10-20 — див.
    # watchlist 3.x у пакеті).
    ("google", "gemini-2.5-flash"): ModelCapability(
        "google", "gemini-2.5-flash",
        supports_web_search=True, supports_citations=True,
        supports_location=False,
        input_usd_per_mtok=0.30, output_usd_per_mtok=2.50,
        # Заземлення 2.5 тарифікується за ЗАЗЕМЛЕНИЙ ПРОМПТ, не за
        # окремий запит. Vertex-прайс (2026-09-01): «$35 per 1,000
        # Grounding Prompts… Even if multiple Grounding Queries are
        # sent, there is only one charge for a Grounding Prompt»;
        # білиться лише промпт, що успішно повернув джерела. Безкоштовні
        # 1 500 промптів/добу в захисну межу НЕ закладаються. Число
        # лежить у лічильнику пошуків: одиниця виміру — заземлений
        # промпт.
        search_usd_per_1k=35.0,
        context_window_tokens=1_048_576,
        # Одиниць білення на один запит рівно одна за означенням
        # одиниці (промпт = запит), тож пошуковий вимір обмежений
        # структурно — на відміну від 3.x, де білиться кожен запит.
        max_searches_boundable=True,
    ),
    ("perplexity", "perplexity/sonar"): ModelCapability(
        "perplexity", "perplexity/sonar",
        supports_web_search=True, supports_citations=True,
        # web_search в Agent API приймає user_location.country.
        supports_location=True,
        input_usd_per_mtok=0.25, output_usd_per_mtok=2.50,
        search_usd_per_1k=2.50,
        # Контекст sonar 128k (docs.perplexity.ai, models); Agent API
        # документує max_output_tokens і max_tool_calls.
        context_window_tokens=128_000,
        max_searches_boundable=True,
    ),
    # Тестовий цінник скриптованого провайдера. У продуктовій політиці
    # він неможливий (PRODUCTION_ADAPTERS його не містить), а без запису
    # тут раннер не зміг би рахувати бюджет у тестах тим самим кодом.
    ("scripted", "scripted-model"): ModelCapability(
        "scripted", "scripted-model",
        supports_web_search=True, supports_citations=True,
        supports_location=False,
        input_usd_per_mtok=1.0, output_usd_per_mtok=1.0,
        search_usd_per_1k=8.0,
        context_window_tokens=1_000_000,
        max_searches_boundable=True,
    ),
    # Тестова модель БЕЗ захисних меж: для пінів «нерахований максимум
    # закривається» тим самим кодом, що й google.
    ("scripted", "scripted-unbounded"): ModelCapability(
        "scripted", "scripted-unbounded",
        supports_web_search=True, supports_citations=True,
        supports_location=False,
        input_usd_per_mtok=1.0, output_usd_per_mtok=1.0,
        search_usd_per_1k=8.0,
        context_window_tokens=None,
        max_searches_boundable=False,
    ),
}


# Провенанс: спостереження провайдера мусить іти його ВЛАСНОЮ моделлю.
# Agent API Perplexity вміє маршрутизувати в чужі моделі — але тоді
# «perplexity» у записі було б неправдою про походження відповіді.
PROVIDER_NATIVE_MODEL_PREFIXES: dict[str, tuple[str, ...]] = {
    "anthropic": ("claude-",),
    "openai": ("gpt-", "o"),
    "perplexity": ("perplexity/",),
    "google": ("gemini-",),
    "scripted": ("scripted-",),
}


def is_native_model(provider: str, model: str) -> bool:
    prefixes = PROVIDER_NATIVE_MODEL_PREFIXES.get(provider)
    if prefixes is None:
        return False
    return model.startswith(prefixes)


def capability(provider: str, model: str) -> ModelCapability | None:
    return CATALOG.get((provider, model))


def models_for(provider: str) -> list[ModelCapability]:
    return [c for (p, _), c in CATALOG.items() if p == provider]


def key_configured(provider: str) -> bool:
    """Чи є секрет для провайдера. Значення секрету звідси не виходить."""
    # Через robочу конфігурацію: збережене адміністратором → оточення.
    from app.core import runtime_config as runtime

    if provider in ("anthropic", "openai", "perplexity", "google"):
        return runtime.configured(f"{provider}_api_key")
    return False


def execution_configured(provider: str, backend: str | None = None) -> bool:
    """Чи налаштовано ВИКОНАННЯ провайдера в цьому оточенні.

    Для google це залежить від бекенда: vertex_ai потребує проєкту
    Google Cloud (автентифікація — ADC/workload identity, її наявність
    перевіряється в момент виклику), developer_api — API-ключа. Бекенди
    не підмінюють один одного мовчки: незконфігурований — це чесний
    NOT_CONFIGURED ДО резервації, а не спроба іншого шляху.
    """
    if provider == "google" and (backend or "vertex_ai") == "vertex_ai":
        from app.core import runtime_config as runtime

        return runtime.configured("google_vertex_project")
    return key_configured(provider)


def call_cost_usd(cap: ModelCapability, *, input_tokens: int,
                  output_tokens: int, searches: int) -> float:
    """Вартість одного виклику за офіційним прейскурантом."""
    return (
        input_tokens / 1_000_000 * cap.input_usd_per_mtok
        + output_tokens / 1_000_000 * cap.output_usd_per_mtok
        + searches / 1000 * cap.search_usd_per_1k
    )


# Еталонні обсяги одного спостереження, ВИМІРЯНІ на прогоні ka-dent.com.ua
# (2026-09-01, 60 спостережень на провайдера). Обсяг входу визначає не
# модель, а те, скільки сторінок провайдер вкладає в контекст після
# пошуку, тож він спільний для всіх моделей одного провайдера. Це база
# ОЦІНКИ вартості аудиту в адмінці — не факт, а прогноз за виміряними
# обсягами й чинними цінами. Один бренд, тож на важчій видачі число
# попливе; в адмінці воно й підписане як оцінне.
REFERENCE_VOLUMES: dict[str, tuple[int, int, float]] = {
    # provider: (input_tokens, output_tokens, searches) на спостереження
    "anthropic": (19_763, 1_521, 2.1),
    "openai": (7_807, 1_191, 1.0),
    "google": (217, 1_242, 1.0),
    "perplexity": (4_898, 1_408, 1.0),
}

#: Спостережень у повному аудиті присутності (15 промптів × 2 режими × 2).
OBSERVATIONS_PER_AUDIT = 60


def estimated_audit_usd(cap: ModelCapability,
                        observations: int = OBSERVATIONS_PER_AUDIT) -> float | None:
    """Оцінка вартості одного аудиту цією моделлю за виміряними обсягами.

    None — для провайдера немає еталонного виміру, і вигадувати обсяг
    ми не будемо: краще порожнє поле, ніж оцінка з повітря.
    """
    volumes = REFERENCE_VOLUMES.get(cap.provider)
    if volumes is None:
        return None
    in_tok, out_tok, searches = volumes
    # Пошук дробовий у середньому (2.1), тож рахуємо напряму, а не через
    # call_cost_usd з цілим лічильником пошуків.
    per_obs = (
        in_tok / 1_000_000 * cap.input_usd_per_mtok
        + out_tok / 1_000_000 * cap.output_usd_per_mtok
        + searches / 1000 * cap.search_usd_per_1k
    )
    return per_obs * observations


def max_attempt_cost_usd(
    cap: ModelCapability, *, max_output_tokens: int,
    max_searches: int | None,
) -> Decimal | None:
    """Захисний максимум ОДНІЄЇ спроби з документованих меж, у Decimal.

    Формула: стеля входу (документоване контекстне вікно / вхідний ліміт
    API — провайдер сам відхиляє більше) × вхідна ціна + наша стеля
    виходу × вихідна ціна + стеля пошуків × збір. Жодних спостережених
    середніх і множників «про запас»: кожен доданок — enforceable-межа.

    None — максимум НЕРАХОВАНИЙ: немає документованої стелі входу, або
    запит не вміє обмежити кількість тарифікованих пошуків. Твердий
    бюджет тоді закривається, а не вгадує.
    """
    if cap.context_window_tokens is None:
        return None
    if max_searches is None or not cap.max_searches_boundable:
        return None
    million = Decimal("1000000")
    thousand = Decimal("1000")
    return (
        Decimal(cap.context_window_tokens) / million
        * Decimal(str(cap.input_usd_per_mtok))
        + Decimal(max_output_tokens) / million
        * Decimal(str(cap.output_usd_per_mtok))
        + Decimal(max_searches) / thousand
        * Decimal(str(cap.search_usd_per_1k))
    )


def pricing_version() -> str:
    """Відбиток чинного прейскуранта: рядки каталогу → стабільний хеш.

    Записується в кожну резервацію і в знімок політики прогону: спроба
    з іншою версією цін не сміє стартувати мовчки — конверт змінився.
    """
    blob = "|".join(
        f"{p}:{m}:{c.input_usd_per_mtok}:{c.output_usd_per_mtok}:"
        f"{c.search_usd_per_1k}:{c.context_window_tokens}:"
        f"{c.max_searches_boundable}"
        for (p, m), c in sorted(CATALOG.items())
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]
