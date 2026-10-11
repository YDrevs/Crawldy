"""Actual AI Presence наскрізь: політика, прогін, ідемпотентність, адмінка.

Живе на PostgreSQL, як решта інтеграційних. Мережі немає: виконання йде
скриптованим провайдером через інʼєкцію сервісу.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select, update
from sqlalchemy import update as sa_update

from app.identity.enums import PlatformRole
from app.models.identity import User
from app.models.presence import PresenceObservation
from app.presence.policy import DEFAULT_POLICY, to_stored
from app.presence.providers.scripted import ScriptedPresenceProvider, ScriptedReply
from app.services import presence_service
from tests.integration.conftest import register


async def _grant_presence(db_session, n: int = 1):
    """Право на прогін: промо-грант перевірок присутності поточній орг."""
    from sqlalchemy import select as sa_select

    from app.billing import credits as billing_credits
    from app.models.identity import Organization

    org_id = (await db_session.execute(
        sa_select(Organization.id)
        .order_by(Organization.created_at.desc()).limit(1)
    )).scalar_one()
    await billing_credits.grant(
        db_session, organization_id=org_id, credit_type="presence",
        quantity=n, source="promo", reason="інтеграційний тест",
    )
    await db_session.commit()
    return org_id


@pytest_asyncio.fixture
async def staff(client, db_session):
    """Клієнт зі службовою роллю: реєстрація + підняття platform_role."""
    body = (await register(client, f"staff-{uuid.uuid4().hex[:8]}@example.com")).json()
    await db_session.execute(
        sa_update(User)
        .where(User.id == uuid.UUID(body["user"]["id"]))
        .values(platform_role=PlatformRole.STAFF)
    )
    await db_session.commit()
    return client


def _enabled_policy_json() -> dict:
    policy = to_stored(DEFAULT_POLICY)
    policy["enabled"] = True
    policy["providers"] = {
        "scripted": {"enabled": True, "model": "scripted-model",
                     "default_country": None},
        "anthropic": {"enabled": False, "model": "claude-sonnet-4-6"},
        "openai": {"enabled": False, "model": "gpt-5.1"},
        "perplexity": {"enabled": False, "model": "perplexity/sonar"},
    }
    return policy


async def _enable_with_scripted(db_session) -> None:
    """Пишемо політику напряму: адмін-шлях валідує PRODUCTION_ADAPTERS і
    скриптованого не пропустить — тест обходить це свідомо, бо виконує
    без мережі."""
    from app.models.ai_settings import AiDomainSettings

    row = await db_session.get(AiDomainSettings, "presence")
    if row is None:
        row = AiDomainSettings(domain="presence")
        db_session.add(row)
    row.policy = _enabled_policy_json()
    await db_session.commit()


@pytest.mark.asyncio
async def test_the_feature_flag_hides_the_endpoint_by_default(client):
    await register(client, "presence-flag@example.com")
    response = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic",
    })
    assert response.status_code == 404, "бета вимкнена — функції не існує"


@pytest.mark.asyncio
async def test_a_run_travels_from_creation_to_metrics(client, db_session):
    await register(client, "presence-run@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)

    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme Dental",
        "brand_aliases": ["Acme"], "category": "dental clinic",
        "services": ["implants"], "language": "en",
    })
    assert created.status_code == 202, created.text
    run_id = uuid.UUID(created.json()["id"])
    assert created.json()["provenance"] == "controlled_provider_api_checks"

    provider = ScriptedPresenceProvider(
        [ScriptedReply("Acme Dental is solid.",
                       cited_urls=["https://example.com/about"])])
    run = await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()
    assert run.status == "completed"
    assert run.observations_total == 60  # 15 промптів × 2 режими × 2 повтори
    assert run.cost_usd > 0

    detail = (await client.get(f"/v1/presence/runs/{run_id}")).json()
    assert detail["metrics"]["evidence_family"] == "synthetic"
    combined = detail["metrics"]["combined"]
    assert combined["mention_presence"]["denominator"] == 24  # 12 небрендових × 2
    assert combined["mention_presence"]["numerator"] == 24
    assert detail["coverage"]["observations_ok"] == 60
    assert len(detail["observations"]) == 60


@pytest.mark.asyncio
async def test_rerun_pays_nothing_twice_and_duplicates_are_impossible(
    client, db_session
):
    await register(client, "presence-idem@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)
    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic",
    })
    run_id = uuid.UUID(created.json()["id"])

    provider = ScriptedPresenceProvider([ScriptedReply("ok")])
    first = await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()
    calls_after_first = len(provider.calls)

    again = await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()
    assert len(provider.calls) == calls_after_first, "повтор не платить"
    assert again.observations_total == first.observations_total


@pytest.mark.asyncio
async def test_raw_evidence_expires_but_the_observation_stays(client, db_session):
    await register(client, "presence-retention@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)
    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic",
    })
    run_id = uuid.UUID(created.json()["id"])
    provider = ScriptedPresenceProvider([ScriptedReply("ok")])
    await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()

    stale = datetime.now(UTC) - timedelta(days=45)
    await db_session.execute(
        update(PresenceObservation)
        .where(PresenceObservation.run_id == run_id)
        .values(created_at=stale)
    )
    purged = await presence_service.purge_expired_raw(db_session, retention_days=30)
    await db_session.commit()
    assert purged == 60

    rows = (await db_session.execute(
        select(PresenceObservation).where(PresenceObservation.run_id == run_id)
    )).scalars().all()
    assert all(o.raw is None for o in rows)
    assert all(o.status == "ok" for o in rows), "нормалізований рядок вічний"


@pytest.mark.asyncio
async def test_admin_domains_are_separate_and_validated(client, db_session, staff):
    """Твердий інваріант: зміна аналізу не рухає присутність, і навпаки."""
    presence_before = (await staff.get("/v1/admin/ai/presence")).json()
    assert presence_before["policy"]["enabled"] is False

    saved = await staff.put("/v1/admin/ai/analysis", json={
        "default_provider": "anthropic", "default_model": "claude-opus-5"})
    assert saved.status_code == 200

    presence_after = (await staff.get("/v1/admin/ai/presence")).json()
    assert presence_after["policy"] == presence_before["policy"], (
        "політика аналізу не сміє зачепити присутність")

    analysis_before = (await staff.get("/v1/admin/ai/analysis")).json()
    saved = await staff.put("/v1/admin/ai/presence", json={
        **_enabled_policy_json(),
        "providers": {"anthropic": {"enabled": True,
                                    "model": "claude-sonnet-4-6"}},
    })
    assert saved.status_code == 200
    analysis_after = (await staff.get("/v1/admin/ai/analysis")).json()
    assert analysis_after["override"] == analysis_before["override"], (
        "політика присутності не сміє зачепити аналіз")

    rejected = await staff.put("/v1/admin/ai/presence", json={
        "enabled": True,
        "providers": {"scripted": {"enabled": True, "model": "scripted-model"}},
    })
    assert rejected.status_code == 422, "скриптований не має прод-адаптера"
    rejected = await staff.put("/v1/admin/ai/analysis", json={
        "default_provider": "anthropic", "default_model": "no-such-model"})
    assert rejected.status_code == 422

    for payload in (
        (await staff.get("/v1/admin/ai/presence")).json(),
        (await staff.get("/v1/admin/ai/analysis")).json(),
    ):
        blob = str(payload)
        assert "sk-" not in blob and "api_key" not in blob.replace(
            "key_configured", ""), "секрети не виходять в адмінку"


# ── ідемпотентність подання, план, експорт ───────────────────────────


async def test_same_idempotency_key_creates_one_run_and_reserves_once(
    client, db_session
):
    """Подвійний клік — один прогін, одна резервація, одна задача."""
    await register(client, "presence-idem@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session, n=2)

    payload = {
        "url": "https://example.com", "brand": "Acme Dental",
        "brand_aliases": ["Acme"], "category": "dental clinic",
        "services": ["implants"], "language": "en",
        "idempotency_key": "click-abc123",
    }
    first = await client.post("/v1/presence/runs", json=payload)
    second = await client.post("/v1/presence/runs", json=payload)
    assert first.status_code == 202 and second.status_code == 202
    assert first.json()["id"] == second.json()["id"], "той самий прогін"

    from sqlalchemy import func as sa_func
    from sqlalchemy import select as sa_select

    from app.models.presence import PresenceRun
    from app.models.purchase import AuditCredit

    runs = (await db_session.execute(
        sa_select(sa_func.count()).select_from(PresenceRun)
    )).scalar_one()
    assert runs == 1
    reserved = (await db_session.execute(
        sa_select(sa_func.count()).select_from(AuditCredit).where(
            AuditCredit.state == "RESERVED")
    )).scalar_one()
    assert reserved == 1, "право зарезервовано рівно раз"


async def test_a_new_key_is_a_deliberate_new_run(client, db_session):
    """Свідомий повтор перевірки того самого домену — законна покупка."""
    await register(client, "presence-rerun@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session, n=2)
    payload = {
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic",
    }
    first = await client.post("/v1/presence/runs", json={
        **payload, "idempotency_key": "run-1"})
    second = await client.post("/v1/presence/runs", json={
        **payload, "idempotency_key": "run-2"})
    assert first.json()["id"] != second.json()["id"]


async def test_plan_shows_scope_and_entitlement_before_start(client, db_session):
    await register(client, "presence-plan@example.com")
    await _enable_with_scripted(db_session)
    plan = (await client.get("/v1/presence/plan")).json()
    assert plan["providers"], "перелік провайдерів видно до запуску"
    assert plan["observations_planned_per_provider"] == (
        plan["prompts_planned"] * len(plan["modes"]) * plan["runs_per_prompt"]
    )
    assert plan["can_start"] is False, "без права стартувати не можна"
    await _grant_presence(db_session)
    plan2 = (await client.get("/v1/presence/plan")).json()
    assert plan2["credits_available"] == 1
    assert plan2["can_start"] is True


async def test_docx_export_serves_the_persisted_run(client, db_session):
    await register(client, "presence-docx@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)
    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme Dental",
        "brand_aliases": ["Acme"], "category": "dental clinic",
    })
    run_id = uuid.UUID(created.json()["id"])
    provider = ScriptedPresenceProvider(
        [ScriptedReply("Acme Dental works", cited_urls=["https://example.com/a"])])
    await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()

    exported = await client.get(f"/v1/presence/runs/{run_id}/export.docx",
                                params={"lang": "uk"})
    assert exported.status_code == 200
    assert exported.content[:2] == b"PK", "справжній docx-архів"
    assert len(exported.content) > 10_000


async def test_run_detail_carries_entitlement_outcome_and_modes(client, db_session):
    await register(client, "presence-outcome@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)
    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic"})
    run_id = uuid.UUID(created.json()["id"])
    provider = ScriptedPresenceProvider([ScriptedReply("ok")])
    await presence_service.execute(
        db_session, run_id, providers_override={"scripted": provider})
    await db_session.commit()

    detail = (await client.get(f"/v1/presence/runs/{run_id}")).json()
    assert detail["entitlement_source"] == "credit"
    assert detail["entitlement_settled"] is True
    assert detail["deliverable"] is True
    assert set(detail["metrics"]["modes"].keys()) == {"natural", "explicit"}
    assert {o["mode"] for o in detail["observations"]} == {
        "natural", "explicit"}


@pytest.mark.asyncio
async def test_run_snapshot_carries_google_backend_provenance(
    client, db_session,
):
    """Знімок політики прогону несе чинний бекенд google і версію цін —
    провенанс спроби читається без коду й без жодного секрету."""
    import json as _json

    from app.models.presence import PresenceRun

    await register(client, "presence-provenance@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)
    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic"})
    run_id = uuid.UUID(created.json()["id"])
    run = await db_session.get(PresenceRun, run_id)
    assert run is not None

    snapshot = run.policy_snapshot
    assert snapshot["providers"]["google"]["backend"] == "vertex_ai"
    assert len(snapshot["pricing_version"]) == 12
    dumped = _json.dumps(snapshot)
    for needle in ("Bearer", "api_key", "credentials", "token"):
        assert needle not in dumped, needle


@pytest.mark.asyncio
async def test_a_run_declares_its_site_and_a_foreign_one_is_not_found(
    client, db_session,
):
    """`site_id` приходить від клієнта, тож він мусить бути перевірений.

    Чужий сайт віддає 404, а не 403: відповідь «доступ заборонено»
    підтвердила б, що ресурс існує. Свій — доходить до прогону й назад
    у відповідь, бо саме на ньому тримається «остання присутність
    цього сайту»: порівнювати адреси для цього не можна.
    """
    await register(client, "presence-site@example.com")
    await _enable_with_scripted(db_session)
    await _grant_presence(db_session)

    mine = (await client.post(
        "/v1/sites", json={"url": "https://example.com"})).json()["id"]

    created = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic", "site_id": mine,
    })
    assert created.status_code == 202, created.text
    assert created.json()["site_id"] == mine, "сайт лишається у відповіді"

    listed = (await client.get("/v1/presence/runs")).json()
    assert [r["site_id"] for r in listed] == [mine]

    foreign = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic", "site_id": str(uuid.uuid4()),
    })
    assert foreign.status_code == 404, foreign.text

    # Прогін поза контекстом сайту дозволений і лишається без звʼязку.
    await _grant_presence(db_session)
    loose = await client.post("/v1/presence/runs", json={
        "url": "https://example.com", "brand": "Acme",
        "category": "dental clinic",
    })
    assert loose.status_code == 202, loose.text
    assert loose.json()["site_id"] is None


@pytest.mark.asyncio
async def test_public_models_come_from_the_policy_and_need_no_login(
    client, db_session
):
    """Публічна вітрина називає ті моделі, що виконують прогін.

    Ендпойнт без входу — як `/v1/offers` для цін: покупець мусить бачити,
    чим саме ми міряємо, ще до акаунта. Джерело те саме, що в раннера,
    тож сторінка не може розійтися з продуктом. Вимкнений провайдер не
    показується: ми його не питаємо, і назвати його моделлю означало б
    заявити вимірювання, якого немає.
    """
    from app.models.ai_settings import AiDomainSettings

    await _enable_with_scripted(db_session)

    res = await client.get("/v1/presence/models")
    assert res.status_code == 200, "вітрина мусить відкриватися без входу"
    assert res.json() == [{"provider": "scripted", "model": "scripted-model"}]

    # Зміна моделі в конфігурації змінює відповідь — без правок коду.
    row = await db_session.get(AiDomainSettings, "presence")
    policy = dict(row.policy)
    providers = dict(policy["providers"])
    providers["scripted"] = {**providers["scripted"], "model": "scripted-next"}
    policy["providers"] = providers
    row.policy = policy
    await db_session.commit()

    again = await client.get("/v1/presence/models")
    assert again.json() == [{"provider": "scripted", "model": "scripted-next"}]
