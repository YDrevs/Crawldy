"""Службові прогони: справжній конвеєр без комерційних обмежень.

## Що саме обходиться

Рівно продуктові права: квота періоду, куплені одиниці, ліміти тарифу,
запис продажу. Технічні межі — таймаути, стелі краулу, бюджети
провайдерів, захист від приватних адрес — лишаються на місці: тест
мусить виконати ТУ САМУ логіку, інакше він нічого не доводить.

## Як тест відрізняється від клієнтського прогону в даних

- аудит: `quota_source = admin_test`, `quota_state = consumed` одразу
  (резерву не було, тож і повертати нічого), організація — та, від імені
  якої працює адміністратор;
- присутність: `organization_id = None` — це вже наявний внутрішній
  шлях (`entitlement_source = "internal"`), який не торкається ані
  квоти, ані кредитів.

Аналітика виключає обидва (див. `admin_analytics_service`), тож
службовий прогін не може виглядати ані продажем, ані використанням
клієнта.

## Звіт

Окремого генератора немає й не буде: `report_for` викликає той самий
`build_report` і ті самі рендери, що й клієнтський маршрут. Різниця
лише в перевірці прав — тобто в тому, хто має право попросити.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import catalog as ai_catalog
from app.audit.enums import AuditStatus, AuditTrigger
from app.core.run_enums import QuotaSource, QuotaState
from app.models.audit import Audit
from app.models.presence import PresenceObservation, PresenceRun
from app.presence import policy as presence_policy
from app.schemas.audit import AuditCreate
from app.services import audit_service, presence_service

# Ті самі стани, у яких клієнтові доступні результат і звіт.
REPORTABLE = (AuditStatus.COMPLETED, AuditStatus.PARTIAL)


async def start_audit(
    session: AsyncSession,
    payload: AuditCreate,
    *,
    organization_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
) -> Audit:
    """Аудит без квоти й без кредитів, позначений як службовий тест.

    `application.start_audit` не використовується навмисно: уся його
    робота — саме резервування прав, яких тут не має бути. Створення
    запису й цілей іде через той самий `audit_service.create_audit`, тож
    сам аудит нічим не відрізняється від клієнтського — виконає його той
    самий воркер тим самим конвеєром.
    """
    audit = await audit_service.create_audit(
        session,
        payload,
        organization_id=organization_id,
        site_id=None,
        created_by_user_id=created_by_user_id,
        trigger=AuditTrigger.MANUAL,
        requested_options=payload.options.model_dump(mode="json"),
    )
    audit.quota_source = QuotaSource.ADMIN_TEST
    # Резерву не було — доля одиниці вирішена одразу, і `settle_quota`
    # не має чого повертати. Те саме рішення, що й для безкоштовного
    # превʼю, і з тієї самої причини.
    audit.quota_state = QuotaState.CONSUMED
    await session.flush()
    return audit


async def start_presence(
    session: AsyncSession,
    *,
    url: str,
    brand: str,
    brand_aliases: list[str],
    category: str,
    services: list[str],
    location: str | None,
    language: str,
    only_provider: str | None = None,
    model_override: str | None = None,
) -> PresenceRun:
    """Прогін присутності без організації — тобто без прав і без списань.

    `only_provider` звужує ефективну політику до одного провайдера: це
    калібрувальний шлях, і він мусить бути точним — інші провайдери не
    просто ігноруються у звіті, а не викликаються взагалі (вимкнені у
    знімку політики, з якого читає раннер).

    `model_override` міняє модель ЦЬОГО провайдера лише для цього
    прогону — benchmark-шлях порівняння моделей (власник, 2026-09-07).
    Продуктова політика не змінюється: правка живе у знімку прогону, а
    не в збереженій політиці домену. Вимагає `only_provider`, бо міняти
    модель одного провайдера в мультипровайдерному прогоні
    двозначно. Модель мусить бути в каталозі — інакше вартість і межі
    невідомі, і резервація впаде ще до виклику.
    """
    policy = await presence_service.load_policy(session)
    if model_override is not None and only_provider is None:
        raise LookupError("model_override потребує only_provider")
    if only_provider is not None:
        if only_provider not in policy.providers:
            raise LookupError(f"невідомий провайдер: {only_provider}")
        policy = _only(policy, only_provider)
        if model_override is not None:
            if (only_provider, model_override) not in ai_catalog.CATALOG:
                raise LookupError(
                    f"моделі немає в каталозі: {only_provider}/{model_override}"
                )
            policy = _with_model(policy, only_provider, model_override)
    elif not policy.active_providers():
        raise LookupError("жодного увімкненого провайдера")
    return await presence_service.create_run(
        session,
        url=url,
        brand=brand,
        brand_aliases=brand_aliases,
        category=category,
        services=services,
        location=location,
        language=language,
        organization_id=None,
        site_id=None,
        policy=policy,
    )


def _only(
    policy: presence_policy.PresencePolicy, provider: str
) -> presence_policy.PresencePolicy:
    """Копія політики, у якій увімкнено рівно одного провайдера."""
    from dataclasses import replace

    providers = {
        name: replace(p, enabled=(name == provider))
        for name, p in policy.providers.items()
    }
    # Головний вимикач домену тут піднімається свідомо: службовий тест
    # існує саме щоб перевірити провайдера до відкриття продукту.
    return replace(policy, providers=providers, enabled=True)


def _with_model(
    policy: presence_policy.PresencePolicy, provider: str, model: str
) -> presence_policy.PresencePolicy:
    """Копія політики з іншою моделлю одного провайдера. Benchmark-шлях."""
    from dataclasses import replace

    providers = {
        name: (replace(p, model=model) if name == provider else p)
        for name, p in policy.providers.items()
    }
    return replace(policy, providers=providers)


async def recent_audits(session: AsyncSession, *, limit: int = 20) -> list[Audit]:
    rows = await session.scalars(
        select(Audit)
        .where(Audit.quota_source == QuotaSource.ADMIN_TEST)
        .order_by(Audit.created_at.desc())
        .limit(limit)
    )
    return list(rows)


async def recent_presence(session: AsyncSession, *, limit: int = 20) -> list[PresenceRun]:
    rows = await session.scalars(
        select(PresenceRun)
        .where(PresenceRun.organization_id.is_(None))
        .order_by(PresenceRun.created_at.desc())
        .limit(limit)
    )
    return list(rows)


async def audit_cost(session: AsyncSession) -> dict[str, Any]:
    """Собівартість ОДНОГО повного аудиту присутності — для ціноутворення.

    Реальний аудит проганяє сітку через КОЖНОГО ввімкненого провайдера,
    тож його вартість — сума по всіх обраних моделях, а не окрема
    вартість кожної. Це і є число, від якого власник рахує продажну
    ціну (вимога власника 2026-09-07).

    Оцінка реагує на параметри, задані на сторінці (повтори, промпти):
    спостережень на провайдера = промпти × режими × повтори. Ціни й
    еталонні обсяги — з каталогу; клієнт множить `cost_per_observation`
    на живу кількість спостережень, тож правка полів оновлює число ще
    до збереження. Тому тут вартість спостереження, а не готова сума.

    «Остання фактична» — найсвіжіший СПРАВЖНІЙ адмінський аудит: прогін
    без організації, у якому ввімкнено більше одного провайдера. Смоки й
    однопровайдерні бенчмарк-прогони сюди не входять — вони про інше
    (порівняння моделей), а не про собівартість продажу.
    """
    policy = await presence_service.load_policy(session)

    # Вартість одного спостереження кожної каталожної моделі, у якої є
    # виміряний еталонний обсяг для її провайдера. Клієнт бере звідси
    # обрані моделі й множить на живу кількість спостережень.
    per_obs: dict[str, dict[str, Any]] = {}
    for (provider, model), cap in ai_catalog.CATALOG.items():
        volumes = ai_catalog.REFERENCE_VOLUMES.get(provider)
        if volumes is None:
            continue
        in_tok, out_tok, searches = volumes
        cost = (
            in_tok / 1_000_000 * cap.input_usd_per_mtok
            + out_tok / 1_000_000 * cap.output_usd_per_mtok
            + searches / 1000 * cap.search_usd_per_1k
        )
        per_obs[f"{provider}/{model}"] = {
            "provider": provider,
            "model": model,
            "input_usd_per_mtok": cap.input_usd_per_mtok,
            "output_usd_per_mtok": cap.output_usd_per_mtok,
            "cached_input_usd_per_mtok": cap.cached_input_usd_per_mtok,
            "search_usd_per_1k": cap.search_usd_per_1k,
            "cost_per_observation": round(cost, 6),
        }

    # Останній справжній аудит: багатопровайдерний адмінський прогін.
    rows = await session.scalars(
        select(PresenceRun)
        .where(PresenceRun.organization_id.is_(None))
        .order_by(PresenceRun.created_at.desc())
    )
    last_audit: dict[str, Any] | None = None
    for run in rows:
        enabled = [
            name for name, p in run.policy_snapshot.get("providers", {}).items()
            if p.get("enabled")
        ]
        if len(enabled) <= 1:
            continue  # смок або однопровайдерний бенчмарк — не аудит
        obs = await session.execute(
            select(PresenceObservation.provider, PresenceObservation.cost_usd)
            .where(PresenceObservation.run_id == run.id)
        )
        by_provider: dict[str, float] = {}
        for prov, cost in obs.all():
            by_provider[prov] = by_provider.get(prov, 0.0) + (cost or 0.0)
        last_audit = {
            "at": run.created_at.isoformat(),
            "url": run.url,
            "total_usd": round(run.cost_usd, 4),
            "observations_total": run.observations_total,
            "per_provider": {p: round(v, 4) for p, v in by_provider.items()},
        }
        break

    return {
        "modes": len(policy.modes),
        "prompts": policy.max_prompts,
        "runs_per_prompt": policy.runs_per_prompt,
        "reference_source": "ka-dent.com.ua",
        "reference_date": "2026-09-01",
        # Обрана модель кожного провайдера — з чинної політики. Клієнт
        # може показати іншу вибірку з незбереженої форми; ключі тут
        # покривають увесь каталог, тож будь-яка обрана модель знайдеться.
        "selected": {
            name: p.model for name, p in policy.providers.items()
        },
        "models": per_obs,
        "last_audit": last_audit,
    }


async def owned_test_audit(session: AsyncSession, audit_id: uuid.UUID) -> Audit | None:
    """Аудит, створений службовим тестом. Клієнтський сюди не потрапляє."""
    audit = await session.get(Audit, audit_id)
    if audit is None or audit.quota_source is not QuotaSource.ADMIN_TEST:
        return None
    return audit


async def owned_test_run(session: AsyncSession, run_id: uuid.UUID) -> PresenceRun | None:
    run = await session.get(PresenceRun, run_id)
    if run is None or run.organization_id is not None:
        return None
    return run


def diagnostics(audit: Audit) -> dict[str, Any]:
    """Технічний зріз прогону: те, що клієнтові у звіт не йде.

    Нічого не обчислює й не тлумачить — лише те, що конвеєр уже записав.
    """
    return {
        "id": str(audit.id),
        "url": audit.url,
        "origin": audit.origin,
        "status": audit.status.value,
        "trigger": audit.trigger.value,
        "quota_source": audit.quota_source.value if audit.quota_source else None,
        "quota_state": audit.quota_state.value,
        "failure_class": audit.failure_class.value if audit.failure_class else None,
        "error": audit.error,
        "created_at": audit.created_at.isoformat() if audit.created_at else None,
        "started_at": audit.started_at.isoformat() if audit.started_at else None,
        "finished_at": audit.finished_at.isoformat() if audit.finished_at else None,
        "attempts": audit.attempts,
        "score_overall": audit.score_overall,
        "scores": audit.scores or {},
        "skipped_modules": list(audit.skipped_modules or []),
        "degraded": list(audit.degraded or []),
        "evidence": audit.evidence or {},
        "versions": audit.versions or {},
        "options": audit.options or {},
        "requested_options": audit.requested_options or {},
        "option_adjustments": list(getattr(audit, "option_adjustments", []) or []),
        "progress": audit.progress or {},
        "targets": [
            {
                "id": str(t.id),
                "position": t.position,
                "url": t.url,
                "origin": t.origin,
                "status": t.status.value,
                "score_overall": t.score_overall,
                "scores": t.scores or {},
                "error": t.error,
                "failure_class": t.failure_class.value if t.failure_class else None,
            }
            for t in sorted(audit.targets, key=lambda t: t.position)
        ],
        "pages": [
            {
                "url": page.url,
                "status_code": page.status_code,
                "response_ms": page.response_ms,
                "depth": page.depth,
            }
            for page in audit.pages
        ],
        "attempt_log": [
            {
                "number": a.number,
                "status": a.status.value,
                "failure_class": a.failure_class.value if a.failure_class else None,
                "error": a.error,
                "retry_decision": a.retry_decision,
                "started_at": a.started_at.isoformat() if a.started_at else None,
                "finished_at": a.finished_at.isoformat() if a.finished_at else None,
            }
            for a in sorted(audit.attempt_log, key=lambda a: a.number)
        ],
    }
