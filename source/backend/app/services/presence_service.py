"""Сервіс присутності: створення прогону, виконання, метрики, утримання.

Оркеструє межі, не змішуючи їх: політика — з адмін-домену, промпти — з
версіонованого генератора, виклики — з раннера, гроші — з каталогу.
Виконання ідемпотентне: клітинки, що вже мають рядки, не повторюються
(UNIQUE в базі — останній рубіж, перевірка тут — перший).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import catalog as ai_catalog
from app.audit.fetcher import normalize_url, origin_of
from app.billing import credits as billing_credits
from app.billing import quota as billing_quota
from app.billing import service as billing_service
from app.models.ai_settings import AiDomainSettings
from app.models.presence import (
    PresenceAttempt,
    PresenceObservation,
    PresenceRun,
)
from app.presence import metrics as presence_metrics
from app.presence import policy as presence_policy
from app.presence.budget import (
    COMMITTED_AT_ACTUAL,
    AttemptCell,
    AttemptState,
    AttemptTicket,
)
from app.presence.contracts import (
    EvidenceFamily,
    ObservationRecord,
    PresencePrompt,
    PromptCategory,
    PromptSet,
    Segment,
)
from app.presence.prompts import PromptFacts, build_prompt_set
from app.presence.providers.base import PresenceProvider
from app.presence.runner import execute_run

log = structlog.get_logger(__name__)


class DurableAttemptLedger:
    """Книга платних спроб у базі: резервація переживає процес.

    Реалізує той самий протокол `AttemptLedger`, що й памʼятна книга
    раннера, але кожен перехід стану — це закомічений рядок
    `presence_attempts`. Допуск атомарний і міжпроцесний: агрегати
    рахуються під `SELECT ... FOR UPDATE` рядка прогону, тож дві
    паралельні спроби (навіть із різних процесів) не можуть спільно
    зарезервувати той самий номер спроби — друга чекає на замок першої
    і бачить її вже закомічений рядок.

    Номер спроби (`attempt_no`) призначається ТУТ, під замком, за
    максимумом уже записаних для клітинки: повтор задачі воркера після
    падіння не зіткнеться з UNIQUE — його спроба стане наступною, а
    рядок загиблого процесу лишиться в історії і в сумі.

    Сесія одна на прогін, і AsyncSession не є конкурентно-безпечною —
    внутрішній asyncio.Lock серіалізує звертання до неї. Мережеві
    виклики він не серіалізує: замок тримається лише на час операції з
    базою, сам виклик провайдера йде поза ним.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        run_id: uuid.UUID,
        pricing_version: str,
    ) -> None:
        self._session = session
        self._run_id = run_id
        self._pricing_version = pricing_version
        self._lock = asyncio.Lock()
        self._halted = False
        self._spent: dict[str, Decimal] = {}

    async def reconcile(self) -> None:
        """Прибирання після можливого падіння процесу — ДО нових спроб.

        RESERVED без диспетчеризації означає: процес загинув між
        резервацією і викликом — грошей той виклик не коштував, рядок
        звільняється (аудиторно, зі станом RELEASED, не видаленням).
        DISPATCHED лишається як є: виклик міг дійти до провайдера, тож
        рядок не чіпаємо — його доля невідома, і вигадувати її не можна.
        COST_BOUND_VIOLATED у минулому — конверт уже зламано: жодна
        нова платна спроба цього прогону не стартує.
        """
        async with self._lock:
            await self._session.execute(
                select(PresenceRun.id)
                .where(PresenceRun.id == self._run_id)
                .with_for_update()
            )
            rows = (await self._session.execute(
                select(PresenceAttempt)
                .where(PresenceAttempt.run_id == self._run_id)
            )).scalars().all()
            for row in rows:
                if row.state == AttemptState.RESERVED.value:
                    row.state = AttemptState.RELEASED.value
                    row.error = (
                        "звільнено при резюме: виклик так і не стартував"
                    )
                elif row.state == AttemptState.COST_BOUND_VIOLATED.value:
                    self._halted = True
                if (row.state in {s.value for s in COMMITTED_AT_ACTUAL}
                        and row.actual_cost_usd is not None):
                    self._spent[row.provider] = self._spent.get(
                        row.provider, Decimal("0")) + row.actual_cost_usd
                elif row.state == AttemptState.UNKNOWN_COST.value:
                    self._spent[row.provider] = self._spent.get(
                        row.provider, Decimal("0")) + row.reserved_max_usd
            await self._session.commit()

    async def reserve(
        self, cell: AttemptCell, bound: Decimal
    ) -> AttemptTicket | None:
        async with self._lock:
            if self._halted:
                return None
            # Міжпроцесний замок: нумерація спроби і вставка — одна
            # атомарна одиниця відносно іншого процесу цього прогону.
            await self._session.execute(
                select(PresenceRun.id)
                .where(PresenceRun.id == self._run_id)
                .with_for_update()
            )
            next_no = (await self._session.execute(
                select(func.coalesce(
                    func.max(PresenceAttempt.attempt_no), 0))
                .where(
                    PresenceAttempt.run_id == self._run_id,
                    PresenceAttempt.provider == cell.provider,
                    PresenceAttempt.prompt_id == cell.prompt_id,
                    PresenceAttempt.mode == cell.mode,
                    PresenceAttempt.run_index == cell.run_index,
                )
            )).scalar_one() + 1
            # id вручну: після commit атрибути можуть бути expired, а
            # квиток потребує ідентифікатора без повторного читання.
            attempt_id = uuid.uuid4()
            row = PresenceAttempt(
                id=attempt_id,
                run_id=self._run_id,
                provider=cell.provider,
                prompt_id=cell.prompt_id,
                mode=cell.mode,
                run_index=cell.run_index,
                attempt_no=int(next_no),
                state=AttemptState.RESERVED.value,
                reserved_max_usd=bound,
                # Стель більше немає: NULL чесно каже «резервувалось не
                # проти стелі». Історичні рядки свої значення зберігають.
                provider_cap_usd=None,
                total_cap_usd=None,
                pricing_version=self._pricing_version,
            )
            self._session.add(row)
            # Резервація стає довговічною ЩЕ ДО мережевого виклику:
            # падіння процесу після цього коміту грошей не звільняє.
            await self._session.commit()
            return AttemptTicket(
                attempt_id=attempt_id, cell=cell, reserved_max=bound)

    async def _set_state(
        self, ticket: AttemptTicket, state: AttemptState, *,
        actual: Decimal | None = None, error: str | None = None,
        provider_request_id: str | None = None,
    ) -> None:
        values: dict[str, Any] = {"state": state.value}
        if actual is not None:
            values["actual_cost_usd"] = actual
        if error is not None:
            values["error"] = error[:2000]
        if provider_request_id is not None:
            values["provider_request_id"] = provider_request_id[:128]
        await self._session.execute(
            update(PresenceAttempt)
            .where(PresenceAttempt.id == ticket.attempt_id)
            .values(**values)
        )
        await self._session.commit()

    async def dispatch(self, ticket: AttemptTicket) -> None:
        async with self._lock:
            await self._set_state(ticket, AttemptState.DISPATCHED)

    async def settle_actual(
        self, ticket: AttemptTicket, actual: Decimal,
        *, provider_request_id: str | None = None,
    ) -> bool:
        async with self._lock:
            if actual > ticket.reserved_max:
                await self._set_state(
                    ticket, AttemptState.COST_BOUND_VIOLATED,
                    actual=actual,
                    error=(f"факт {actual} > зарезервованого максимуму "
                           f"{ticket.reserved_max}"),
                    provider_request_id=provider_request_id,
                )
                self._halted = True
                self._spent[ticket.cell.provider] = self._spent.get(
                    ticket.cell.provider, Decimal("0")) + actual
                return True
            await self._set_state(
                ticket, AttemptState.SETTLED, actual=actual,
                provider_request_id=provider_request_id,
            )
            self._spent[ticket.cell.provider] = self._spent.get(
                ticket.cell.provider, Decimal("0")) + actual
            return False

    async def known_zero(self, ticket: AttemptTicket, detail: str) -> None:
        async with self._lock:
            await self._set_state(
                ticket, AttemptState.KNOWN_ZERO,
                actual=Decimal("0"), error=detail,
            )

    async def unknown(self, ticket: AttemptTicket, detail: str) -> None:
        async with self._lock:
            await self._set_state(
                ticket, AttemptState.UNKNOWN_COST, error=detail)
            self._spent[ticket.cell.provider] = self._spent.get(
                ticket.cell.provider, Decimal("0")) + ticket.reserved_max

    def halted(self) -> bool:
        return self._halted

    def spent_by_provider(self) -> dict[str, Decimal]:
        return dict(self._spent)


async def load_policy(session: AsyncSession) -> presence_policy.PresencePolicy:
    row = await session.get(AiDomainSettings, presence_policy.DOMAIN)
    return presence_policy.from_stored(row.policy if row else None)


async def save_policy(
    session: AsyncSession, policy_json: dict[str, Any]
) -> tuple[presence_policy.PresencePolicy, list[str]]:
    """Валідує і зберігає політику домену. Помилки — без запису."""
    policy = presence_policy.from_stored(policy_json)
    errors = presence_policy.validate(policy)
    if errors:
        return policy, errors
    row = await session.get(AiDomainSettings, presence_policy.DOMAIN)
    if row is None:
        row = AiDomainSettings(domain=presence_policy.DOMAIN)
        session.add(row)
    row.policy = presence_policy.to_stored(policy)
    await session.flush()
    return policy, []


async def create_run(
    session: AsyncSession,
    *,
    url: str,
    brand: str,
    brand_aliases: list[str],
    category: str,
    services: list[str],
    location: str | None,
    language: str,
    organization_id: uuid.UUID | None,
    site_id: uuid.UUID | None,
    idempotency_key: str | None = None,
    policy: presence_policy.PresencePolicy | None = None,
) -> PresenceRun:
    """Створює прогін у стані queued. Виконує воркер, не API-процес.

    `policy` — перекриття ефективної політики для ВНУТРІШНІХ прогонів
    (службовий тест одного провайдера). Клієнтський шлях його не
    передає й завжди бере чинну політику домену.

    Право на прогін вимагається ТУТ, до черги: автентифікації і
    ввімкненого прапорця замало — присутність коштує реальних
    провайдерських грошей. Джерела права, за порядком: місячна квота
    підписки, потім куплена/грантована одиниця. Немає ні того, ні
    того — прогону не існує.

    `idempotency_key` розрізняє випадковий повтор ОДНОГО запиту
    (подвійний клік, ретрай мережі — той самий ключ, той самий прогін,
    право не резервується вдруге) від свідомого нового запуску (новий
    ключ або без ключа). Дедуплікації за доменом немає навмисно:
    повторна перевірка того самого сайту — законна покупка.
    """
    if policy is None:
        policy = await load_policy(session)
    if idempotency_key and organization_id is not None:
        existing = (await session.execute(
            select(PresenceRun).where(
                PresenceRun.organization_id == organization_id,
                PresenceRun.idempotency_key == idempotency_key,
            )
        )).scalar_one_or_none()
        if existing is not None:
            return existing
    entry = normalize_url(url)
    origin = origin_of(entry)
    if language not in policy.languages:
        # Мова поза дозволеним політикою списком падає на першу
        # дозволену — чесніше за мовчазний шаблон невідомою мовою.
        language = policy.languages[0]
    facts = PromptFacts(
        brand=brand,
        brand_aliases=tuple(brand_aliases),
        domain=origin.split("//", 1)[-1],
        category=category,
        services=tuple(services[:3]),
        location=location,
        language=language,
    )
    prompt_set = build_prompt_set(facts)
    run = PresenceRun(
        organization_id=organization_id,
        site_id=site_id,
        url=entry,
        origin=origin,
        brand=brand,
        brand_aliases=[brand, *brand_aliases],
        prompt_set_version=prompt_set.version,
        prompts=[
            {
                "prompt_id": p.prompt_id,
                "text": p.text,
                "category": p.category.value,
                "segment": p.segment.value,
                "language": p.language,
            }
            for p in prompt_set.prompts
        ],
        policy_snapshot={
            **presence_policy.to_stored(policy),
            # Відбиток прейскуранта на момент замовлення: виконання з
            # іншою версією цін не стартує мовчки — конверт змінився.
            "pricing_version": ai_catalog.pricing_version(),
            # Провенанс виконання google без секретів: ідентифікатор
            # проєкту й локація — адреси, не облікові дані.
            **_vertex_snapshot(policy),
        },
        status="queued",
        idempotency_key=idempotency_key,
    )
    session.add(run)
    await session.flush()

    run.entitlement_source = await _acquire_entitlement(
        session, organization_id=organization_id, run_id=run.id
    )
    await session.flush()
    return run


class PresenceEntitlementRequired(Exception):
    """Права на перевірку присутності немає: ні квоти, ні одиниці."""


async def public_models(session: AsyncSession) -> list[dict[str, str]]:
    """Провайдери й моделі для публічної сторінки — те саме джерело.

    Читає ту саму політику, що й `plan_view` і сам прогін
    (`policy.providers[...].model`), тож окремого публічного переліку
    моделей не існує й розійтися немає з чим.

    Вимкнений провайдер не показується: ми його не питаємо, і назвати
    його моделлю означало б заявити вимірювання, якого немає.
    """
    policy = await load_policy(session)
    return [
        {"provider": name, "model": policy.providers[name].model}
        for name in sorted(policy.active_providers())
    ]


async def plan_view(
    session: AsyncSession, *, organization_id: uuid.UUID | None,
) -> dict[str, Any]:
    """Що саме буде виміряно й чи є право — ДО запуску, без резервування.

    Клієнт мусить бачити провайдерів, обсяг і те, що одиниця спишеться
    лише за придатний прогін, перш ніж натиснути кнопку.
    """
    policy = await load_policy(session)
    prompts_planned = min(policy.max_prompts, 15)
    per_provider = prompts_planned * len(policy.modes) * policy.runs_per_prompt
    providers = [
        {
            "provider": name,
            "model": policy.providers[name].model,
            # «Налаштовано» — про ВИКОНАННЯ, з урахуванням бекенда:
            # для google/vertex_ai це проєкт Vertex, не API-ключ.
            "configured": _execution_ok(name, policy.providers[name]),
        }
        for name in sorted(policy.active_providers())
    ]

    allowance_available = False
    credits_available = 0
    if organization_id is not None:
        ent = await billing_service.for_organization(
            session, organization_id=organization_id
        )
        limit = ent.limit("presence_per_period")
        if limit is not None and limit > 0:
            subscription = await billing_service.active_subscription(
                session, organization_id=organization_id
            )
            used = await billing_quota.used_in(
                session, organization_id=organization_id,
                period=billing_quota.period_for(subscription),
                metric="presence",
            )
            allowance_available = used < limit
        credits_available = await billing_credits.balance(
            session, organization_id=organization_id, credit_type="presence"
        )

    return {
        "enabled": policy.enabled,
        "providers": providers,
        "modes": list(policy.modes),
        "prompts_planned": prompts_planned,
        "runs_per_prompt": policy.runs_per_prompt,
        "observations_planned_per_provider": per_provider,
        "observations_planned_total": per_provider * len(providers),
        "allowance_available": allowance_available,
        "credits_available": credits_available,
        "can_start": allowance_available or credits_available > 0,
    }


def _vertex_snapshot(
    policy: presence_policy.PresencePolicy,
) -> dict[str, Any]:
    """Провенанс Vertex для знімка політики прогону. Без секретів."""
    google = policy.providers.get("google")
    if google is None or not google.enabled:
        return {}
    if presence_policy.effective_backend("google", google) != "vertex_ai":
        return {}
    from app.core import runtime_config as runtime

    return {"vertex": {
        "project": runtime.get("google_vertex_project"),
        "location": runtime.get("google_vertex_location") or "global",
    }}


def _execution_ok(
    provider: str, p: presence_policy.ProviderPolicy
) -> bool:
    from app.ai.catalog import execution_configured

    return execution_configured(
        provider, presence_policy.effective_backend(provider, p))


async def _acquire_entitlement(
    session: AsyncSession,
    *,
    organization_id: uuid.UUID | None,
    run_id: uuid.UUID,
) -> str:
    if organization_id is None:
        # Прогони без організації створює лише внутрішній інструментарій
        # (пілоти, валідація) — клієнтський API завжди має організацію.
        return "internal"
    ent = await billing_service.for_organization(
        session, organization_id=organization_id
    )
    limit = ent.limit("presence_per_period")
    if limit is not None and limit > 0:
        subscription = await billing_service.active_subscription(
            session, organization_id=organization_id
        )
        decision = await billing_quota.consume(
            session,
            organization_id=organization_id,
            period=billing_quota.period_for(subscription),
            limit=limit,
            metric="presence",
        )
        if decision.allowed:
            return "subscription"
    reserved = await billing_credits.reserve_presence(
        session, organization_id=organization_id, run_id=run_id
    )
    if reserved is not None:
        return "credit"
    raise PresenceEntitlementRequired(
        "немає доступних перевірок AI-присутності"
    )


def _deliverable(run: PresenceRun, policy: presence_policy.PresencePolicy,
                 records_ok_by_provider: dict[str, int],
                 planned_per_provider: int) -> bool:
    """Чи достатнє покриття, щоб чесно взяти оплату.

    Провайдер «метрично придатний», коли його успішних спостережень
    вистачає на канонічні метрики — той самий поріг, що вмикає частки
    (MIN_OBSERVATIONS_FOR_RATE), обрізаний розміром самого прогону:
    малий прогін міряється власною повнотою, а не недосяжною двадцяткою.
    Прогін придатний, коли придатна СУВОРА БІЛЬШІСТЬ увімкнених
    провайдерів: 1→1, 2→2, 3→2, 4→3.
    """
    enabled = policy.active_providers()
    if not enabled:
        return False
    threshold = min(policy.min_observations_for_rate, planned_per_provider)
    deliverable_providers = sum(
        1 for name in enabled
        if records_ok_by_provider.get(name, 0) >= threshold
    )
    return deliverable_providers >= len(enabled) // 2 + 1


async def _settle_entitlement(
    session: AsyncSession, run: PresenceRun, *, deliverable: bool
) -> None:
    """Розрахунок права — рівно один раз на прогін.

    Придатний прогін списує зарезервоване; непридатний — повертає
    клієнтові право, а вже витрачені провайдерські гроші поглинаємо ми.
    Повтор виконання застає settled і не робить нічого.
    """
    if run.entitlement_settled:
        return
    source = run.entitlement_source
    if source == "credit":
        if deliverable:
            await billing_credits.consume_presence(session, run_id=run.id)
        else:
            await billing_credits.release_presence(session, run_id=run.id)
    elif source == "subscription" and not deliverable:
        if run.organization_id is not None:
            subscription = await billing_service.active_subscription(
                session, organization_id=run.organization_id
            )
            await billing_quota.release(
                session,
                organization_id=run.organization_id,
                period=billing_quota.period_for(subscription),
                metric="presence",
            )
    run.entitlement_settled = True
    await session.flush()


async def execute(
    session: AsyncSession,
    run_id: uuid.UUID,
    *,
    providers_override: dict[str, PresenceProvider] | None = None,
) -> PresenceRun:
    """Виконує прогін: безпечно до перезапуску, під бюджетом політики."""
    run = await session.get(PresenceRun, run_id)
    if run is None:
        raise LookupError(f"прогін не знайдено: {run_id}")

    policy = presence_policy.from_stored(run.policy_snapshot)
    prompt_set = PromptSet(
        version=run.prompt_set_version,
        prompts=tuple(
            PresencePrompt(
                prompt_id=str(p["prompt_id"]),
                text=str(p["text"]),
                category=PromptCategory(p["category"]),
                segment=Segment(p["segment"]),
                language=str(p["language"]),
            )
            for p in run.prompts
        ),
    )
    if not prompt_set.prompts:
        run.status = "failed"
        run.error = "прогін без збереженого набору промптів"
        await session.flush()
        return run

    existing = await session.execute(
        select(
            PresenceObservation.provider,
            PresenceObservation.prompt_id,
            PresenceObservation.mode,
            PresenceObservation.run_index,
        ).where(PresenceObservation.run_id == run.id)
    )
    done = {(p, pid, mode, idx) for p, pid, mode, idx in existing.all()}

    # Конверт цін дійсний лише для прейскуранта, яким його рахували:
    # інша версія каталогу означає, що зарезервовані максимуми й стелі
    # більше не описують ті самі гроші. Виконання не стартує (fail
    # closed); прогін без штампа — створений до цієї перевірки — іде
    # далі, бо йому нема чого звіряти.
    stamped = run.policy_snapshot.get("pricing_version")
    current_pricing = ai_catalog.pricing_version()
    if stamped is not None and stamped != current_pricing:
        run.status = "failed"
        run.error = (
            f"pricing_version_mismatch: замовлено за {stamped}, "
            f"каталог зараз {current_pricing} — конверт цін недійсний"
        )
        run.deliverable = False
        run.finished_at = datetime.now(UTC)
        await _settle_entitlement(session, run, deliverable=False)
        await session.flush()
        return run

    run.status = "running"
    await session.flush()

    # Книга спроб — у базі: резервація комітиться до виклику, тож резюме
    # після падіння бачить і сплачене, і DISPATCHED-спроби, чия доля
    # невідома. Стель витрат немає — обмежує сітка прогону.
    ledger = DurableAttemptLedger(
        session,
        run_id=run.id,
        pricing_version=current_pricing,
    )
    await ledger.reconcile()

    records, totals = await execute_run(
        policy=policy,
        prompt_set=prompt_set,
        origin=run.origin,
        brand_aliases=tuple(run.brand_aliases),
        done_cells=done,
        providers_override=providers_override,
        ledger=ledger,
    )
    for record in records:
        session.add(_to_row(run.id, record))
    run.observations_total = len(done) + len(records)
    run.observations_ok += totals.ok
    run.cost_usd += totals.cost_usd
    run.status = "completed"
    run.finished_at = datetime.now(UTC)

    if totals.cost_bound_violation is not None:
        # Факт перевищив зарезервований максимум — конверт цін зламано.
        # Це операційний інцидент: докази збережено (спроба в стані
        # COST_BOUND_VIOLATED, спостереження записані), платні виклики
        # зупинено, межа НЕ підвищується мовчки ніколи.
        run.error = f"cost_bound_violated: {totals.cost_bound_violation}"
        log.error(
            "presence.cost_bound_violated",
            run_id=str(run.id),
            detail=totals.cost_bound_violation,
            pricing_version=current_pricing,
        )

    ok_by_provider: dict[str, int] = {}
    result = await session.execute(
        select(PresenceObservation.provider, func.count())
        .where(PresenceObservation.run_id == run.id,
               PresenceObservation.status == "ok")
        .group_by(PresenceObservation.provider)
    )
    for provider_name, count in result.all():
        ok_by_provider[provider_name] = int(count)
    from app.presence.runner import planned_cells

    planned = planned_cells(policy, len(prompt_set.prompts))
    deliverable = _deliverable(run, policy, ok_by_provider, planned)
    run.deliverable = deliverable
    await _settle_entitlement(session, run, deliverable=deliverable)
    await session.flush()

    await purge_expired_raw(session, retention_days=policy.raw_retention_days)
    return run


def _to_row(run_id: uuid.UUID, record: ObservationRecord) -> PresenceObservation:
    return PresenceObservation(
        run_id=run_id,
        evidence_family=EvidenceFamily.SYNTHETIC.value,
        provider=record.provider,
        model=record.model,
        tool_version=record.tool_version,
        prompt_id=record.prompt.prompt_id,
        prompt_text=record.prompt.text,
        category=record.prompt.category.value,
        segment=record.prompt.segment.value,
        language=record.prompt.language,
        country=record.country,
        run_index=record.run_index,
        mode=record.mode.value,
        status=record.status.value,
        searched=record.searched,
        sent_text=record.sent_text,
        search_queries=record.search_queries,
        answer_excerpt=record.answer_excerpt,
        cited_urls=record.cited_urls,
        cited_domains=record.cited_domains,
        brand_mentioned=record.brand_mentioned,
        matched_alias=record.matched_alias,
        domain_cited=record.domain_cited,
        pages_cited=record.pages_cited,
        domain_linked=record.domain_linked,
        linked_urls=record.linked_urls,
        recommended=record.recommended,
        observed_domains=record.observed_domains,
        error=record.error,
        input_tokens=record.usage.input_tokens,
        output_tokens=record.usage.output_tokens,
        searches=record.usage.searches,
        cost_usd=record.cost_usd,
        retries=record.retries,
        duration_ms=record.duration_ms,
        normalize_version=record.normalize_version,
        raw=record.raw,
    )


async def run_metrics(session: AsyncSession, run: PresenceRun) -> dict[str, Any]:
    rows_result = await session.execute(
        select(PresenceObservation).where(PresenceObservation.run_id == run.id)
    )
    rows = [
        {
            "provider": o.provider,
            "prompt_id": o.prompt_id,
            "category": o.category,
            "segment": o.segment,
            "mode": o.mode,
            "status": o.status,
            "searched": o.searched,
            "brand_mentioned": o.brand_mentioned,
            "domain_cited": o.domain_cited,
            "domain_linked": o.domain_linked,
            "recommended": o.recommended,
            "observed_domains": o.observed_domains,
        }
        for o in rows_result.scalars()
    ]
    policy = presence_policy.from_stored(run.policy_snapshot)
    return {
        "metrics": presence_metrics.build_metrics(
            rows, min_observations=policy.min_observations_for_rate,
        ),
        "coverage": presence_metrics.coverage(
            rows,
            providers_configured=len(policy.active_providers()),
            prompts_declared=min(policy.max_prompts, len(run.prompts)),
        ),
    }


async def purge_expired_raw(session: AsyncSession, *, retention_days: int) -> int:
    """Зануляє сирі відповіді, старші за політику утримання."""
    threshold = datetime.now(UTC) - timedelta(days=retention_days)
    result = await session.execute(
        update(PresenceObservation)
        .where(
            PresenceObservation.created_at < threshold,
            PresenceObservation.raw.is_not(None),
        )
        .values(raw=None)
    )
    return int(result.rowcount or 0)


async def find_by_idempotency(
    session: AsyncSession, *, organization_id: uuid.UUID | None,
    idempotency_key: str,
) -> PresenceRun | None:
    if organization_id is None or not idempotency_key:
        return None
    return (await session.execute(
        select(PresenceRun).where(
            PresenceRun.organization_id == organization_id,
            PresenceRun.idempotency_key == idempotency_key,
        )
    )).scalar_one_or_none()


async def owned_run(
    session: AsyncSession, organization_id: uuid.UUID | None, run_id: uuid.UUID
) -> PresenceRun | None:
    run = await session.get(PresenceRun, run_id)
    if run is None or run.organization_id != organization_id:
        return None
    return run


async def runs_for(
    session: AsyncSession, organization_id: uuid.UUID | None, *, limit: int = 50
) -> list[PresenceRun]:
    result = await session.execute(
        select(PresenceRun)
        .where(PresenceRun.organization_id == organization_id)
        .order_by(PresenceRun.created_at.desc())
        .limit(limit)
    )
    return list(result.scalars())


async def observations_for(
    session: AsyncSession, run_id: uuid.UUID
) -> list[PresenceObservation]:
    result = await session.execute(
        select(PresenceObservation)
        .where(PresenceObservation.run_id == run_id)
        .order_by(
            PresenceObservation.provider,
            PresenceObservation.prompt_id,
            PresenceObservation.run_index,
        )
    )
    return list(result.scalars())
