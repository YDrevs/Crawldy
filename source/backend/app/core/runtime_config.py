"""Робоча конфігурація: збережене адміністратором → оточення → дефолт коду.

## Навіщо

Досі кожне значення платіжного провайдера й кожен ключ AI-провайдера
читалися з оточення в момент виклику (`settings.paddle_api_key`,
`settings.anthropic_api_key`, …). Службовий кабінет мусить уміти їх
змінювати без релізу — але не сміє зробити робоче встановлення
«ненастроєним» лише тому, що зʼявився. Звідси порядок розвʼязання:

    1. значення, збережене адміністратором (`runtime_settings`);
    2. змінна оточення / `.env` — те, на чому встановлення працює зараз;
    3. дефолт коду, якщо він у поля взагалі є.

Перенесення з оточення не робиться: оточення лишається фолбеком, і
адміністратор бачить на сторінці «налаштовано з оточення», а не порожнє
поле. Збережене значення перекриває оточення; «прибрати» повертає до
оточення, а не до порожнечі.

## Секрети

Секрети зберігаються лише зашифрованими (Fernet). Ключ шифрування —
`SECRETS_KEY` в оточенні; без нього збереження секрету відхиляється з
явною причиною, а секрети з оточення працюють як і раніше. Назовні
секрет не повертається ніколи — лише «налаштовано / ні» і джерело.

## Кеш і свіжість

Читання синхронне й береться з кешу процесу: адаптери не мають сесії
бази й не повинні її мати. Кеш оновлюється `ensure_fresh(session)` —
залежність кожного HTTP-запиту (`get_session`) і початок задач воркера
викликають його; всередині стоїть TTL, щоб не читати таблицю частіше,
ніж раз на кілька секунд на процес. Процес, що жодного разу не оновив
кеш, читає оточення — тобто поводиться рівно як до появи таблиці.
"""

from __future__ import annotations

import base64
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.runtime_settings import RuntimeSetting

Kind = Literal["str", "float", "int", "choice"]
Source = Literal["admin", "env", "default", "none"]


@dataclass(frozen=True, slots=True)
class Spec:
    """Що це за ключ: секрет чи ні, звідки фолбек, якого типу значення."""

    key: str
    domain: Literal["payment", "ai"]
    secret: bool = False
    kind: Kind = "str"
    choices: tuple[str, ...] = ()
    # Атрибут `settings`, з якого береться фолбек. None — фолбеку немає.
    env: str | None = None
    # Дефолт коду для полів, у яких він є (не для секретів).
    default: str | None = None
    # Не секрет, але й не показується у відповіді як є: лише
    # «налаштовано» + останні символи. Токен Paddle для браузера
    # публічний за задумом Paddle, проте на службовій сторінці цілком
    # він не потрібен.
    masked: bool = False
    # Провайдер, до якого належить ключ (для групування на сторінці).
    provider: str = ""
    # Очікуваний початок значення — підказка формату для валідації.
    prefix: tuple[str, ...] = field(default_factory=tuple)


SPECS: dict[str, Spec] = {
    # ── платіжний провайдер ────────────────────────────────────────────
    "billing_provider": Spec(
        "billing_provider", "payment", kind="choice", choices=("paddle", "fake"),
        env="billing_provider", default="fake", provider="payment",
    ),
    "paddle_env": Spec(
        "paddle_env", "payment", kind="choice", choices=("sandbox", "live"),
        env="paddle_env", default="sandbox", provider="paddle",
    ),
    "paddle_api_key": Spec(
        "paddle_api_key", "payment", secret=True, env="paddle_api_key",
        provider="paddle", prefix=("pdl_live_apikey_", "pdl_sdbx_apikey_"),
    ),
    "paddle_client_token": Spec(
        "paddle_client_token", "payment", env="paddle_client_token",
        provider="paddle", masked=True, prefix=("live_", "test_"),
    ),
    "paddle_webhook_secret": Spec(
        "paddle_webhook_secret", "payment", secret=True, env="paddle_webhook_secret",
        provider="paddle", prefix=("pdl_ntfset_",),
    ),
    "paddle_timeout_s": Spec(
        "paddle_timeout_s", "payment", kind="float", env="paddle_timeout_s",
        default="20.0", provider="paddle",
    ),
    "paddle_signature_tolerance_s": Spec(
        "paddle_signature_tolerance_s", "payment", kind="int",
        env="paddle_signature_tolerance_s", default="300", provider="paddle",
    ),
    # ── AI Presence: ключі й адреси виконання ──────────────────────────
    "anthropic_api_key": Spec(
        "anthropic_api_key", "ai", secret=True, env="anthropic_api_key",
        provider="anthropic", prefix=("sk-ant-",),
    ),
    "openai_api_key": Spec(
        "openai_api_key", "ai", secret=True, env="openai_api_key",
        provider="openai", prefix=("sk-",),
    ),
    "perplexity_api_key": Spec(
        "perplexity_api_key", "ai", secret=True, env="perplexity_api_key",
        provider="perplexity", prefix=("pplx-",),
    ),
    "google_api_key": Spec(
        "google_api_key", "ai", secret=True, env="google_api_key", provider="google",
    ),
    "google_vertex_project": Spec(
        "google_vertex_project", "ai", env="google_vertex_project", provider="google",
    ),
    "google_vertex_location": Spec(
        "google_vertex_location", "ai", env="google_vertex_location",
        default="global", provider="google",
    ),
}

# Скільки секунд кеш процесу вважається свіжим. Кожен HTTP-запит і
# кожна задача воркера викликають ensure_fresh; таблиця мала, тож
# читання раз на кілька секунд на процес — непомітна ціна.
_TTL_S = 5.0


class SecretsUnavailable(RuntimeError):
    """Немає ключа шифрування — секрет зберегти неможливо."""


class UnknownSetting(KeyError):
    """Ключа немає в переліку відомих."""


@dataclass(slots=True)
class _Cache:
    rows: dict[str, str | None] = field(default_factory=dict)  # key → розшифроване
    undecryptable: set[str] = field(default_factory=set)
    loaded_at: float | None = None


_cache = _Cache()


# ── шифрування ──────────────────────────────────────────────────────────


def _fernet() -> Fernet | None:
    raw = settings.secrets_key
    if not raw:
        return None
    # Будь-який рядок → 32 байти → url-safe base64: адміністратор не
    # зобовʼязаний генерувати ключ саме у форматі Fernet.
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def secrets_storage_available() -> bool:
    return _fernet() is not None


def _encrypt(value: str) -> str:
    fernet = _fernet()
    if fernet is None:
        raise SecretsUnavailable("SECRETS_KEY не задано: секрет зберегти неможливо")
    return fernet.encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt(token: str) -> str | None:
    fernet = _fernet()
    if fernet is None:
        return None
    try:
        return fernet.decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


# ── читання ─────────────────────────────────────────────────────────────


def spec_of(key: str) -> Spec:
    try:
        return SPECS[key]
    except KeyError as exc:
        raise UnknownSetting(key) from exc


def _env_value(spec: Spec) -> str | None:
    if spec.env is None:
        return None
    raw = getattr(settings, spec.env, None)
    if raw is None or raw == "":
        return None
    return str(raw)


def get(key: str) -> str | None:
    """Чинне значення: адмін → оточення → None. Для коду, не для показу."""
    spec = spec_of(key)
    stored = _cache.rows.get(key)
    if stored:
        return stored
    return _env_value(spec)


def get_float(key: str) -> float:
    spec = spec_of(key)
    value = get(key)
    try:
        return float(value if value is not None else (spec.default or "0"))
    except ValueError:
        return float(spec.default or "0")


def get_int(key: str) -> int:
    spec = spec_of(key)
    value = get(key)
    try:
        return int(float(value if value is not None else (spec.default or "0")))
    except ValueError:
        return int(spec.default or "0")


def source(key: str) -> Source:
    spec = spec_of(key)
    if _cache.rows.get(key):
        return "admin"
    if _env_value(spec):
        return "env"
    if spec.default is not None:
        return "default"
    return "none"


def configured(key: str) -> bool:
    return bool(get(key))


def _tail(value: str) -> str:
    return value[-4:] if len(value) > 8 else ""


def describe(key: str) -> dict[str, Any]:
    """Безпечний опис для адмінки: секрет ніколи не потрапляє у відповідь."""
    spec = spec_of(key)
    value = get(key)
    row: dict[str, Any] = {
        "key": key,
        "domain": spec.domain,
        "provider": spec.provider,
        "secret": spec.secret,
        "masked": spec.masked,
        "kind": spec.kind,
        "choices": list(spec.choices),
        "configured": bool(value),
        "source": source(key),
        "storage_available": secrets_storage_available() if spec.secret else True,
        "undecryptable": key in _cache.undecryptable,
        "default": spec.default,
    }
    if spec.secret or spec.masked:
        row["value"] = None
        row["hint"] = _tail(value) if value else ""
    else:
        row["value"] = value
        row["hint"] = ""
    return row


def format_problem(key: str, value: str) -> str | None:
    """Чому значення не схоже на очікуване. None — заперечень немає."""
    spec = spec_of(key)
    if spec.kind == "choice" and value not in spec.choices:
        return f"дозволені значення: {', '.join(spec.choices)}"
    if spec.kind == "float":
        try:
            if float(value) <= 0:
                return "має бути додатним числом"
        except ValueError:
            return "має бути числом"
    if spec.kind == "int":
        try:
            if int(value) <= 0:
                return "має бути додатним цілим числом"
        except ValueError:
            return "має бути цілим числом"
    if spec.prefix and not any(value.startswith(p) for p in spec.prefix):
        return f"очікується початок {' або '.join(spec.prefix)}"
    return None


# ── свіжість кешу ───────────────────────────────────────────────────────


def apply_rows(rows: list[tuple[str, str | None, bool]]) -> None:
    """Заповнити кеш рядками таблиці. Публічна заради тестів без бази."""
    fresh: dict[str, str | None] = {}
    broken: set[str] = set()
    for key, value, is_secret in rows:
        if key not in SPECS:
            continue
        if value is None:
            fresh[key] = None
            continue
        if is_secret:
            plain = _decrypt(value)
            if plain is None:
                broken.add(key)
                continue
            fresh[key] = plain
        else:
            fresh[key] = value
    _cache.rows = fresh
    _cache.undecryptable = broken
    _cache.loaded_at = time.monotonic()


async def refresh(session: AsyncSession) -> None:
    """Перечитати таблицю зараз — після збереження або на старті задачі."""
    result = await session.execute(
        select(RuntimeSetting.key, RuntimeSetting.value, RuntimeSetting.is_secret)
    )
    apply_rows([(k, v, bool(s)) for k, v, s in result.all()])


async def ensure_fresh(session: AsyncSession) -> None:
    """Оновити кеш, якщо він старший за TTL. Дешево на гарячому шляху."""
    if _cache.loaded_at is not None and time.monotonic() - _cache.loaded_at < _TTL_S:
        return
    await refresh(session)


def reset_cache() -> None:
    """Для тестів: процес поводиться, ніби таблиці ще не читав."""
    _cache.rows = {}
    _cache.undecryptable = set()
    _cache.loaded_at = None


# ── запис ───────────────────────────────────────────────────────────────


async def save(
    session: AsyncSession,
    values: dict[str, str | None],
    *,
    updated_by: uuid.UUID | None,
) -> dict[str, str]:
    """Зберегти значення (None — прибрати збережене, повернутися до оточення).

    Повертає помилки формату по ключах; за наявності хоч однієї нічого
    не записується. Секрет без ключа шифрування — теж помилка, а не
    мовчазний запис відкритим текстом.
    """
    errors: dict[str, str] = {}
    prepared: dict[str, tuple[str | None, bool]] = {}
    for key, raw in values.items():
        try:
            spec = spec_of(key)
        except UnknownSetting:
            errors[key] = "невідомий ключ"
            continue
        if raw is None or raw == "":
            prepared[key] = (None, spec.secret)
            continue
        value = raw.strip()
        problem = format_problem(key, value)
        if problem is not None:
            errors[key] = problem
            continue
        if spec.secret:
            if not secrets_storage_available():
                errors[key] = "SECRETS_KEY не задано: секрет зберегти неможливо"
                continue
            prepared[key] = (_encrypt(value), True)
        else:
            prepared[key] = (value, False)
    if errors:
        return errors

    for key, (stored, is_secret) in prepared.items():
        if stored is None:
            await session.execute(delete(RuntimeSetting).where(RuntimeSetting.key == key))
            continue
        stmt = insert(RuntimeSetting).values(
            key=key, value=stored, is_secret=is_secret, updated_by=updated_by
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[RuntimeSetting.key],
            set_={"value": stored, "is_secret": is_secret, "updated_by": updated_by},
        )
        await session.execute(stmt)
    await session.flush()
    await refresh(session)
    return {}


def keys_for(domain: str) -> list[str]:
    return [key for key, spec in SPECS.items() if spec.domain == domain]


__all__ = [
    "SPECS",
    "SecretsUnavailable",
    "Spec",
    "UnknownSetting",
    "apply_rows",
    "configured",
    "describe",
    "ensure_fresh",
    "format_problem",
    "get",
    "get_float",
    "get_int",
    "keys_for",
    "refresh",
    "reset_cache",
    "save",
    "secrets_storage_available",
    "source",
    "spec_of",
]
