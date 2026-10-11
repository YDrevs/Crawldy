"""Політика виконання Presence: адмін-конфігурація над каталогом.

Затверджені P0-значення — ДЕФОЛТИ конфігурації, а не константи продукту:
адміністратор змінює їх без релізу через `ai_domain_settings` (домен
«presence»). Раннер розвʼязує ефективну політику в момент запуску й
знімкує її в записі прогону — історія знає, чим саме міряли.

Секретів тут немає: політика знає лише «ключ налаштовано / ні», і це
читається з оточення в момент перевірки.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.ai.catalog import (
    capability,
    execution_configured,
    is_native_model,
    key_configured,
    max_attempt_cost_usd,
)
from app.presence.budget import REQUEST_CEILINGS

DOMAIN = "presence"

# Провайдери, для яких існує продуктовий адаптер. Реєстрація scripted у
# проді неможлива структурно (див. providers/registry.py) — тому його
# немає й у цьому переліку.
PRODUCTION_ADAPTERS = ("anthropic", "openai", "perplexity", "google")

# Режими вимірювання, які політика може вмикати. Порожній список
# недійсний: прогін без режимів не міряє нічого.
KNOWN_MODES = ("natural", "explicit")

# Бекенди виконання google-провайдера. Це ЯВНИЙ вибір без мовчазного
# фолбека: vertex_ai — продуктовий твердо-бюджетний шлях (ADC/workload
# identity, глобальний ендпойнт), developer_api — сумісність і
# внутрішня діагностика там, де налаштована модель реально доступна
# ключеві. Провайдер один — google; бекенд лише каже, ЯК виконувати.
GOOGLE_BACKENDS = ("vertex_ai", "developer_api")


@dataclass(slots=True, frozen=True)
class ProviderPolicy:
    enabled: bool
    model: str
    # Дефолт ринку для провайдерів із підтримкою локації; None — не
    # передавати локацію взагалі.
    default_country: str | None = None
    # ЗАСТАРІЛЕ й у допуску НЕ бере участі: спостережене число, хай і з
    # запасом, не є захисною межею. Захисний максимум спроби рахується з
    # ДОКУМЕНТОВАНИХ меж (контекстне вікно, стеля виходу, ліміт
    # пошуків) у ai.catalog.max_attempt_cost_usd. Поле збережене лише
    # щоб старі збережені політики читалися без сюрпризів.
    max_call_cost_usd: float | None = None
    # Бекенд виконання; має сенс лише для google (див. GOOGLE_BACKENDS).
    # None — дефолт провайдера (google → vertex_ai). Інші провайдери
    # бекендів не мають, і валідатор відхиляє спробу його задати.
    backend: str | None = None


def effective_backend(name: str, p: ProviderPolicy) -> str | None:
    """Чинний бекенд виконання провайдера. Дефолт google — vertex_ai."""
    if name != "google":
        return None
    return p.backend or "vertex_ai"


@dataclass(slots=True, frozen=True)
class PresencePolicy:
    enabled: bool
    providers: dict[str, ProviderPolicy]
    runs_per_prompt: int
    max_prompts: int
    retry_limit: int
    raw_retention_days: int
    concurrency: int
    # Режими вимірювання прогону. Знаменники режимів не змішуються.
    modes: tuple[str, ...] = ("natural", "explicit")
    # Поріг «достатньо спостережень для частки» — він же поріг метричної
    # придатності провайдера (обрізаний розміром прогону).
    min_observations_for_rate: int = 20
    # Таймаут одного виклику провайдера, секунд.
    provider_timeout_s: float = 90.0
    # Мови, якими генеруються набори промптів. Мова запиту поза списком
    # падає на першу — чесніше за машинний шаблон невідомою нам мовою.
    languages: tuple[str, ...] = ("en", "uk")

    def active_providers(self) -> list[str]:
        return [name for name, p in self.providers.items() if p.enabled]


# Дефолти повного продукту (чотири провайдери, два режими). P0-значення
# промптів/повторів/бюджетів збережені; свідомі зміни проти P0 (НЕ
# мовчазні — задокументовані в пакеті): доданий провайдер google і другий
# режим вимірювання. Продукт лишається за головним вимикачем enabled.
DEFAULT_POLICY = PresencePolicy(
    enabled=False,  # beta: вимкнено, поки адміністратор не увімкне
    providers={
        "anthropic": ProviderPolicy(enabled=True, model="claude-sonnet-4-6"),
        "openai": ProviderPolicy(enabled=True, model="gpt-5.1"),
        # Живу валідацію Agent API пройдено 2026-08-31: 3/3 спостереження,
        # $0.017, фактична вартість провайдера збіглася з обліком.
        "perplexity": ProviderPolicy(enabled=True, model="perplexity/sonar"),
        # Продуктовий шлях google — Vertex AI: gemini-2.5-flash із
        # заземленням, білиться ЗА ЗАЗЕМЛЕНИЙ ПРОМПТ ($35/1k, платний
        # тариф), максимум спроби рахований, автентифікація — ADC/
        # workload identity (жодних ключів у політиці). Без
        # налаштованого проєкту Vertex клітинки чесно стають
        # NOT_CONFIGURED ще ДО резервації — нуль витрат і нуль
        # забруднення стель. Ряд 2.5 у Developer API закритий для
        # нових користувачів (живий 404, 2026-09-01) — тому
        # developer_api лишається тільки сумісністю. УВАГА: карта
        # моделі Vertex ставить gemini-2.5-flash дату виведення
        # 2026-10-20 — watchlist 3.x (білиться за кожен запит без
        # стелі кількості) мусить розвʼязатися до неї. Локацію
        # google_search не приймає — default_country завжди None.
        "google": ProviderPolicy(enabled=True, model="gemini-2.5-flash",
                                 backend="vertex_ai"),
    },
    runs_per_prompt=2,
    max_prompts=15,
    retry_limit=1,
    raw_retention_days=30,
    concurrency=3,
    modes=("natural", "explicit"),
    min_observations_for_rate=20,
    provider_timeout_s=90.0,
    languages=("en", "uk"),
)


def from_stored(policy_json: dict[str, Any] | None) -> PresencePolicy:
    """Ефективна політика: дефолти, перекриті збереженим JSON.

    Невідомі ключі ігноруються мовчки навмисно: старий рядок політики не
    сміє валити новий код, а новий ключ зі старим кодом просто ще не
    діє.
    """
    if not policy_json:
        return DEFAULT_POLICY
    stored_providers = policy_json.get("providers")
    if stored_providers is None:
        providers = dict(DEFAULT_POLICY.providers)
    else:
        # Явна мапа провайдерів — АВТОРИТЕТНА: неназвані вимикаються.
        # Накладання на дефолти вже коштувало реальних грошей: політика
        # «лише scripted» мовчки лишала три типові провайдери ввімкненими,
        # і прогін зробив 60 живих платних викликів замість нуля.
        providers = {
            name: ProviderPolicy(enabled=False, model=base.model,
                                 default_country=base.default_country,
                                 backend=base.backend)
            for name, base in DEFAULT_POLICY.providers.items()
        }
        for name, raw in stored_providers.items():
            base = providers.get(name, ProviderPolicy(enabled=False, model=""))
            stored_cap = raw.get("max_call_cost_usd", base.max_call_cost_usd)
            stored_backend = raw.get("backend", base.backend)
            providers[name] = ProviderPolicy(
                enabled=bool(raw.get("enabled", False)),
                model=str(raw.get("model", base.model)),
                default_country=raw.get("default_country", base.default_country),
                max_call_cost_usd=(
                    float(stored_cap) if isinstance(stored_cap, int | float)
                    else None
                ),
                backend=(str(stored_backend)
                         if isinstance(stored_backend, str) else None),
            )

    def _num(key: str, default: float) -> float:
        value = policy_json.get(key, default)
        return float(value) if isinstance(value, int | float) else default

    stored_modes = policy_json.get("modes")
    if isinstance(stored_modes, list) and stored_modes:
        modes = tuple(str(m) for m in stored_modes)
    else:
        # Старий рядок політики (P0) режимів не знав і міряв natural.
        # Відсутність ключа означає стару поведінку, а не новий дефолт:
        # збережена конфігурація не сміє подорожчати сама собою.
        modes = ("natural",) if policy_json else DEFAULT_POLICY.modes

    stored_langs = policy_json.get("languages")
    languages = (
        tuple(str(lang) for lang in stored_langs)
        if isinstance(stored_langs, list) and stored_langs
        else DEFAULT_POLICY.languages
    )

    return PresencePolicy(
        enabled=bool(policy_json.get("enabled", DEFAULT_POLICY.enabled)),
        providers=providers,
        runs_per_prompt=int(_num("runs_per_prompt", DEFAULT_POLICY.runs_per_prompt)),
        max_prompts=int(_num("max_prompts", DEFAULT_POLICY.max_prompts)),
        retry_limit=int(_num("retry_limit", DEFAULT_POLICY.retry_limit)),
        raw_retention_days=int(
            _num("raw_retention_days", DEFAULT_POLICY.raw_retention_days)
        ),
        concurrency=int(_num("concurrency", DEFAULT_POLICY.concurrency)),
        modes=modes,
        min_observations_for_rate=int(_num(
            "min_observations_for_rate", DEFAULT_POLICY.min_observations_for_rate
        )),
        provider_timeout_s=_num(
            "provider_timeout_s", DEFAULT_POLICY.provider_timeout_s
        ),
        languages=languages,
    )


def to_stored(policy: PresencePolicy) -> dict[str, Any]:
    return {
        "enabled": policy.enabled,
        "providers": {
            name: {
                "enabled": p.enabled,
                "model": p.model,
                "default_country": p.default_country,
                "max_call_cost_usd": p.max_call_cost_usd,
                # Знімок несе ЧИННИЙ бекенд (для google — розвʼязаний
                # дефолт): провенанс спроби мусить читатися без коду.
                "backend": effective_backend(name, p),
            }
            for name, p in policy.providers.items()
        },
        "runs_per_prompt": policy.runs_per_prompt,
        "max_prompts": policy.max_prompts,
        "retry_limit": policy.retry_limit,
        "raw_retention_days": policy.raw_retention_days,
        "concurrency": policy.concurrency,
        "modes": list(policy.modes),
        "min_observations_for_rate": policy.min_observations_for_rate,
        "provider_timeout_s": policy.provider_timeout_s,
        "languages": list(policy.languages),
    }


def validate(policy: PresencePolicy) -> list[str]:
    """Помилки конфігурації. Порожньо — політику можна зберігати.

    Відсутність ключа НЕ блокує збереження (ключі приходять з оточення
    й можуть зʼявитися після політики) — але блокує сам запуск, і це
    рішення раннера.
    """
    errors: list[str] = []
    for name, p in policy.providers.items():
        if not p.enabled:
            continue
        if name not in PRODUCTION_ADAPTERS:
            errors.append(f"провайдер без продуктового адаптера: {name}")
            continue
        if not is_native_model(name, p.model):
            errors.append(
                f"чужа модель під вивіскою провайдера: {name}/{p.model} — "
                "провенанс спостереження вимагає власної моделі"
            )
        cap = capability(name, p.model)
        if cap is None:
            errors.append(f"невідома модель у каталозі: {name}/{p.model}")
        elif not cap.supports_web_search:
            errors.append(
                f"модель без веб-пошуку не придатна для присутності: {name}/{p.model}"
            )
        if p.default_country and cap is not None and not cap.supports_location:
            errors.append(
                f"провайдер не підтримує локацію, а дефолтний ринок задано: {name}"
            )
        # Бекенд — явний вибір, не мовчазний фолбек: невідоме значення
        # чи бекенд у провайдера, який бекендів не має, — помилка
        # конфігурації, а не «якось виконається».
        if name == "google":
            backend = effective_backend(name, p)
            if backend not in GOOGLE_BACKENDS:
                errors.append(f"невідомий бекенд google: {backend}")
            elif backend == "vertex_ai" and cap is not None and not (
                cap.context_window_tokens is not None
                and cap.max_searches_boundable
            ):
                errors.append(
                    f"vertex_ai вимагає моделі з рахованим максимумом "
                    f"спроби, а {p.model} його не має — платний шлях "
                    "не відкриється"
                )
        elif p.backend is not None:
            errors.append(f"бекенд не має сенсу для провайдера: {name}")
    if policy.enabled and not policy.active_providers():
        errors.append("жодного увімкненого провайдера для продуктового запуску")
    if not 1 <= policy.runs_per_prompt <= 5:
        errors.append("runs_per_prompt поза межами 1..5")
    if not 1 <= policy.max_prompts <= 50:
        errors.append("max_prompts поза межами 1..50")
    if not 0 <= policy.retry_limit <= 3:
        errors.append("retry_limit поза межами 0..3")
    if not 1 <= policy.raw_retention_days <= 365:
        errors.append("raw_retention_days поза межами 1..365")
    if not 1 <= policy.concurrency <= 10:
        errors.append("concurrency поза межами 1..10")
    if not policy.modes:
        errors.append("жодного режиму вимірювання")
    for mode in policy.modes:
        if mode not in KNOWN_MODES:
            errors.append(f"невідомий режим вимірювання: {mode}")
    if len(set(policy.modes)) != len(policy.modes):
        errors.append("режими повторюються")
    if not 1 <= policy.min_observations_for_rate <= 200:
        errors.append("min_observations_for_rate поза межами 1..200")
    if not 10 <= policy.provider_timeout_s <= 600:
        errors.append("provider_timeout_s поза межами 10..600")
    if not policy.languages:
        errors.append("жодної мови промптів")
    return errors


def provider_status(policy: PresencePolicy) -> list[dict[str, Any]]:
    """Безпечний стан провайдерів для адмінки: без жодного секрету."""
    rows = []
    for name, p in sorted(policy.providers.items()):
        cap = capability(name, p.model)
        ceilings = REQUEST_CEILINGS.get(name)
        bound = (
            max_attempt_cost_usd(
                cap,
                max_output_tokens=ceilings.max_output_tokens,
                max_searches=ceilings.max_searches,
            )
            if cap is not None and ceilings is not None else None
        )
        row: dict[str, Any] = {
            "provider": name,
            "enabled": p.enabled,
            "model": p.model,
            "key_configured": key_configured(name),
            "execution_configured": execution_configured(
                name, effective_backend(name, p)),
            "production_adapter": name in PRODUCTION_ADAPTERS,
            "supports_web_search": bool(cap and cap.supports_web_search),
            "supports_location": bool(cap and cap.supports_location),
            "default_country": p.default_country,
            # Захисний максимум ОДНІЄЇ спроби з документованих меж.
            # None — максимум нерахований, і платний виклик не стартує
            # (fail closed): адміністратор бачить це тут, а не в
            # загадковому збої.
            "max_attempt_cost_usd": (
                float(bound) if bound is not None else None
            ),
        }
        if name == "google":
            row["backend"] = effective_backend(name, p)
            row["vertex"] = _vertex_status()
        rows.append(row)
    return rows


def _vertex_status() -> dict[str, Any]:
    """Статика готовності Vertex — без секретів і без мережі.

    Тут лише те, що видно з оточення: чи задано проєкт і чи ЗНАЙДЕНО
    джерело облікових даних. Динамічні стани (API вимкнено, бракує
    ролі, модель недоступна) видно тільки з живого виклику — вони
    приходять читабельним текстом у записі спостереження, а не тут.
    """
    import os
    from pathlib import Path

    from app.core import runtime_config as runtime

    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        credentials = "service_account_env"
    else:
        adc = (Path(os.environ.get("APPDATA", ""))
               / "gcloud" / "application_default_credentials.json")
        adc_posix = (Path.home() / ".config" / "gcloud"
                     / "application_default_credentials.json")
        if adc.is_file() or adc_posix.is_file():
            credentials = "adc_file"
        else:
            # У деплої облікові дані може дати workload identity /
            # метадата-сервер — локальна відсутність файлу не вирок.
            credentials = "not_detected_locally"
    return {
        "project_configured": runtime.configured("google_vertex_project"),
        "location": runtime.get("google_vertex_location") or "global",
        "credentials": credentials,
    }

