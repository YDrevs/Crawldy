"""Службова конфігурація: платіжний провайдер і AI-моделі присутності.

Дві сторінки кабінету команди над двома вже наявними механізмами:

- значення й секрети — `app.core.runtime_config` (адмін → оточення);
- політика присутності (увімкнено, модель, бюджети, повтори) —
  `app.presence.policy` через `presence_service.load/save_policy`, тобто
  той самий рядок `ai_domain_settings`, який продукт читає при запуску.

Тут немає власної моделі даних: сервіс лише збирає обидва джерела в
одну безпечну відповідь і розводить збереження по них. Секрет не
проходить через жодне поле відповіді — навіть у тексті помилки
перевірки зʼєднання його значення затирається.

Перевірка зʼєднання — це виклик, який НЕ коштує грошей і не робить
покупки: метадані моделі, перелік типів подій, перелік асинхронних
задач. Він доводить, що ключ прийнято й що оточення те, яким його
назвали; він не доводить, що вистачить квоти на живий прогін.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import catalog as ai_catalog
from app.application import catalogue_publishing as publishing
from app.billing.providers.paddle import (
    LIVE_BASE_URL,
    SANDBOX_BASE_URL,
    SANDBOX_KEY_MARKER,
)
from app.core import runtime_config as runtime
from app.core.config import settings
from app.presence import policy as presence_policy
from app.services import presence_service

PAYMENT_PROVIDERS = ("paddle",)
PRESENCE_PROVIDERS = presence_policy.PRODUCTION_ADAPTERS


def _redact(text: str, *secrets: str | None) -> str:
    """Секрет у тексті помилки затирається — незалежно від того, хто його туди вставив."""
    for value in secrets:
        if value and len(value) >= 8:
            text = text.replace(value, "•••")
    return text[:300]


# ── платіжний провайдер ────────────────────────────────────────────────


def _paddle_consistency() -> list[str]:
    """Проблеми, які видно без мережі: ключ не з того оточення."""
    problems: list[str] = []
    key = runtime.get("paddle_api_key") or ""
    env = runtime.get("paddle_env") or "sandbox"
    if key and env == "sandbox" and SANDBOX_KEY_MARKER not in key:
        problems.append("key_looks_live_in_sandbox")
    if key and env == "live" and SANDBOX_KEY_MARKER in key:
        problems.append("key_looks_sandbox_in_live")
    token = runtime.get("paddle_client_token") or ""
    if token and env == "sandbox" and not token.startswith("test_"):
        problems.append("client_token_looks_live_in_sandbox")
    if token and env == "live" and token.startswith("test_"):
        problems.append("client_token_looks_sandbox_in_live")
    return problems


def _payment_status(provider: str) -> str:
    if provider == "fake":
        return "fake"
    required = ("paddle_api_key", "paddle_webhook_secret", "paddle_client_token")
    if not all(runtime.configured(k) for k in required):
        return "not_configured"
    if _paddle_consistency():
        return "inconsistent"
    return "configured"


async def payment_view(session: AsyncSession, *, webhook_base: str) -> dict[str, Any]:
    await runtime.refresh(session)
    provider = (runtime.get("billing_provider") or "fake").strip().lower()
    fields = [runtime.describe(key) for key in runtime.keys_for("payment")]
    return {
        "active_provider": provider,
        "environment": runtime.get("paddle_env") or "sandbox",
        "status": _payment_status(provider),
        "problems": _paddle_consistency(),
        # Адреса, яку треба вписати в Paddle → Developer tools → Notifications.
        "webhook_url": f"{webhook_base.rstrip('/')}/v1/webhooks/paddle",
        # Що продається і чи опубліковано в чинного провайдера — без мережі.
        "catalogue": await publishing.catalogue_status(session),
        "fake_available": settings.app_env != "prod",
        "secrets_storage_available": runtime.secrets_storage_available(),
        "fields": fields,
    }


async def save_payment(
    session: AsyncSession, values: dict[str, str | None], *, updated_by: uuid.UUID | None
) -> dict[str, str]:
    allowed = set(runtime.keys_for("payment"))
    errors = {k: "невідомий ключ" for k in values if k not in allowed}
    if errors:
        return errors
    if values.get("billing_provider") == "fake" and settings.app_env == "prod":
        return {"billing_provider": "фейковий провайдер у проді не реєструється"}
    return await runtime.save(session, values, updated_by=updated_by)


# Ключі, від яких залежить, КУДИ публікуються прайси. Зміна будь-якого з них
# означає, що каталог у провайдера треба опублікувати наново.
PUBLISHING_KEYS = ("billing_provider", "paddle_env", "paddle_api_key")


async def republish_after_save(
    session: AsyncSession, values: dict[str, str | None]
) -> list[dict[str, Any]] | None:
    """Після зміни провайдера, оточення чи ключа — увесь каталог наново.

    Налаштування вже збережені й НЕ відкочуються: людина мусить мати
    змогу виправити ключ і зберегти ще раз. Що не опублікувалось —
    видно у відповіді, а запис лишається з попереднім провайдером.
    `None` — публікація не потрібна (змінили, скажімо, тайм-аут).
    """
    if not any(key in values for key in PUBLISHING_KEYS):
        return None
    await runtime.refresh(session)
    return await publishing.republish_catalogue(session)


async def test_payment(session: AsyncSession) -> dict[str, Any]:
    """Живий виклик Paddle без грошей: перелік типів подій під ключем."""
    await runtime.refresh(session)
    provider = (runtime.get("billing_provider") or "fake").strip().lower()
    if provider != "paddle":
        return {"ok": False, "outcome": "not_paddle", "detail": provider}
    key = runtime.get("paddle_api_key")
    if not key:
        return {"ok": False, "outcome": "no_api_key", "detail": ""}
    problems = _paddle_consistency()
    if problems:
        return {"ok": False, "outcome": "inconsistent", "detail": ", ".join(problems)}
    env = runtime.get("paddle_env") or "sandbox"
    base = SANDBOX_BASE_URL if env == "sandbox" else LIVE_BASE_URL
    started = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=runtime.get_float("paddle_timeout_s")) as client:
            response = await client.get(
                f"{base}/event-types", headers={"Authorization": f"Bearer {key}"}
            )
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "outcome": "network_error",
            "detail": _redact(f"{type(exc).__name__}: {exc}", key),
        }
    elapsed = int((time.monotonic() - started) * 1000)
    if response.status_code == 200:
        try:
            count = len(response.json().get("data", []))
        except ValueError:
            count = 0
        return {"ok": True, "outcome": "ok", "environment": env,
                "detail": f"event types: {count}", "latency_ms": elapsed,
                # Жива звірка каталогу: що Paddle має під нашими прайсами.
                "catalogue": await publishing.verify_catalogue(session)}
    if response.status_code in (401, 403):
        return {"ok": False, "outcome": "unauthorized", "environment": env,
                "detail": _redact(response.text, key), "latency_ms": elapsed}
    return {"ok": False, "outcome": "http_error", "environment": env,
            "detail": _redact(f"HTTP {response.status_code}: {response.text}", key),
            "latency_ms": elapsed}


# ── AI-моделі присутності ──────────────────────────────────────────────


def _models(provider: str) -> list[dict[str, Any]]:
    rows = []
    for cap in ai_catalog.models_for(provider):
        if not cap.supports_web_search:
            continue
        rows.append({
            "model": cap.model,
            "supports_location": cap.supports_location,
            "input_usd_per_mtok": cap.input_usd_per_mtok,
            "output_usd_per_mtok": cap.output_usd_per_mtok,
            "search_usd_per_1k": cap.search_usd_per_1k,
        })
    return rows


async def ai_view(session: AsyncSession) -> dict[str, Any]:
    await runtime.refresh(session)
    policy = await presence_service.load_policy(session)
    status_rows = {row["provider"]: row for row in presence_policy.provider_status(policy)}
    providers = []
    for name in PRESENCE_PROVIDERS:
        keys = [k for k in runtime.keys_for("ai") if runtime.spec_of(k).provider == name]
        providers.append({
            **status_rows.get(name, {"provider": name, "enabled": False, "model": ""}),
            "settings": [runtime.describe(k) for k in keys],
            "models": _models(name),
            "backends": list(presence_policy.GOOGLE_BACKENDS) if name == "google" else [],
        })
    return {
        "domain": presence_policy.DOMAIN,
        "policy": presence_policy.to_stored(policy),
        "providers": providers,
        "secrets_storage_available": runtime.secrets_storage_available(),
        "pricing_version": ai_catalog.pricing_version(),
    }


async def save_ai(
    session: AsyncSession,
    *,
    policy: dict[str, Any] | None,
    values: dict[str, str | None] | None,
    updated_by: uuid.UUID | None,
) -> dict[str, Any]:
    """Секрети й політика — двома різними механізмами, одна відповідь про помилки."""
    errors: dict[str, Any] = {}
    if values:
        allowed = set(runtime.keys_for("ai"))
        unknown = {k: "невідомий ключ" for k in values if k not in allowed}
        if unknown:
            errors["settings"] = unknown
        else:
            problems = await runtime.save(session, values, updated_by=updated_by)
            if problems:
                errors["settings"] = problems
    if policy is not None:
        _, policy_errors = await presence_service.save_policy(session, policy)
        if policy_errors:
            errors["policy"] = policy_errors
    return errors


async def test_ai_provider(session: AsyncSession, provider: str) -> dict[str, Any]:
    """Безкоштовний виклик, який доводить, що ключ прийнято, а модель відома."""
    await runtime.refresh(session)
    policy = await presence_service.load_policy(session)
    p = policy.providers.get(provider)
    if p is None or provider not in PRESENCE_PROVIDERS:
        return {"ok": False, "outcome": "unknown_provider", "detail": provider}
    model = p.model
    started = time.monotonic()
    try:
        outcome = await asyncio.wait_for(_probe(provider, model, p), timeout=30)
    except TimeoutError:
        outcome = {"ok": False, "outcome": "timeout", "detail": "30 s"}
    except Exception as exc:  # noqa: BLE001 — причина йде адміністратору, не в трейс
        outcome = {
            "ok": False,
            "outcome": "error",
            "detail": _redact(
                f"{type(exc).__name__}: {exc}",
                runtime.get(f"{provider}_api_key"),
            ),
        }
    outcome.setdefault("model", model)
    outcome["latency_ms"] = int((time.monotonic() - started) * 1000)
    return outcome


async def _probe(provider: str, model: str, p: presence_policy.ProviderPolicy) -> dict[str, Any]:
    key = runtime.get(f"{provider}_api_key")
    if provider == "anthropic":
        if not key:
            return {"ok": False, "outcome": "no_api_key", "detail": ""}
        import anthropic

        client = anthropic.AsyncAnthropic(api_key=key, max_retries=0, timeout=20)
        try:
            info = await client.models.retrieve(model)
        except anthropic.AuthenticationError as exc:
            return {"ok": False, "outcome": "unauthorized", "detail": _redact(str(exc), key)}
        except anthropic.NotFoundError as exc:
            return {"ok": False, "outcome": "model_not_found", "detail": _redact(str(exc), key)}
        return {"ok": True, "outcome": "ok", "detail": getattr(info, "display_name", "") or model}

    if provider == "openai":
        if not key:
            return {"ok": False, "outcome": "no_api_key", "detail": ""}
        import openai

        client = openai.AsyncOpenAI(api_key=key, max_retries=0, timeout=20)
        try:
            info = await client.models.retrieve(model)
        except openai.AuthenticationError as exc:
            return {"ok": False, "outcome": "unauthorized", "detail": _redact(str(exc), key)}
        except openai.NotFoundError as exc:
            return {"ok": False, "outcome": "model_not_found", "detail": _redact(str(exc), key)}
        return {"ok": True, "outcome": "ok", "detail": getattr(info, "id", "") or model}

    if provider == "perplexity":
        if not key:
            return {"ok": False, "outcome": "no_api_key", "detail": ""}
        # Перелік асинхронних задач — автентифікований GET без тарифу:
        # ключ або приймається (200), або ні (401). Виклик моделі тут не
        # робиться навмисно — у Perplexity кожен запит платний.
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                "https://api.perplexity.ai/async/chat/completions",
                headers={"Authorization": f"Bearer {key}"},
            )
        if response.status_code == 200:
            return {"ok": True, "outcome": "ok", "detail": "key accepted"}
        if response.status_code in (401, 403):
            return {"ok": False, "outcome": "unauthorized", "detail": _redact(response.text, key)}
        return {"ok": False, "outcome": "http_error",
                "detail": _redact(f"HTTP {response.status_code}: {response.text}", key)}

    if provider == "google":
        backend = presence_policy.effective_backend(provider, p)
        if backend == "vertex_ai":
            project = runtime.get("google_vertex_project")
            if not project:
                return {"ok": False, "outcome": "no_project", "detail": "google_vertex_project"}
            from app.presence.providers.google import _refresh_vertex_token, _vertex_host

            location = runtime.get("google_vertex_location") or "global"
            token = await asyncio.to_thread(_refresh_vertex_token)
            # countTokens: документований безкоштовний виклик. Він
            # доводить рівно те, що треба, — облікові дані прийнято,
            # проєкт має доступ, модель існує в цій локації, — і не
            # витрачає ані токенів, ані пошуків. GET метаданих моделі
            # тут не годиться: публікаторський ресурс віддає HTML-404
            # на цьому шляху, і це виглядало б як «моделі немає».
            url = (
                f"https://{_vertex_host(location)}/v1/projects/{project}"
                f"/locations/{location}/publishers/google/models/{model}:countTokens"
            )
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(
                    url,
                    headers={"Authorization": f"Bearer {token}"},
                    json={"contents": [{"role": "user", "parts": [{"text": "ping"}]}]},
                )
            if response.status_code == 200:
                return {"ok": True, "outcome": "ok",
                        "detail": f"vertex_ai · {project} · {location}"}
            if response.status_code in (401, 403):
                return {"ok": False, "outcome": "unauthorized",
                        "detail": _redact(response.text, token)}
            if response.status_code == 404:
                return {"ok": False, "outcome": "model_not_found",
                        "detail": _redact(response.text, token)}
            return {"ok": False, "outcome": "http_error",
                    "detail": _redact(f"HTTP {response.status_code}: {response.text}", token)}
        if not key:
            return {"ok": False, "outcome": "no_api_key", "detail": ""}
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}",
                headers={"x-goog-api-key": key},
            )
        if response.status_code == 200:
            return {"ok": True, "outcome": "ok", "detail": "developer_api"}
        if response.status_code in (400, 401, 403):
            return {"ok": False, "outcome": "unauthorized", "detail": _redact(response.text, key)}
        if response.status_code == 404:
            return {"ok": False, "outcome": "model_not_found",
                    "detail": _redact(response.text, key)}
        return {"ok": False, "outcome": "http_error",
                "detail": _redact(f"HTTP {response.status_code}: {response.text}", key)}

    return {"ok": False, "outcome": "unknown_provider", "detail": provider}
