"""Аудит належить організації, і чужий для тебе не існує.

До цього блоку жоден аудит не мав власника: `GET /v1/audits/{id}` віддавав
будь-який аудит будь-кому з ключем. Це не була помилка в перевірці — це
була відсутність поняття, за яким можна перевіряти.

Тести тут перевіряють не «чи є фільтр у коді», а те, що зовні видно:
чужий ідентифікатор дає 404, чужа історія — 404, чужий перелік порожній.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.audit.enums import AuditStatus, AuditTrigger
from app.identity.legacy import LEGACY_ORGANIZATION_ID
from app.models.audit import Audit, AuditTarget
from app.models.identity import Organization
from tests.integration.conftest import register, sign_in_as


async def _own_organization(client) -> uuid.UUID:
    body = (await client.get("/v1/auth/me")).json()
    return uuid.UUID(body["organization"]["id"])


async def _grant_credit(db, client) -> None:
    """Куплена одиниця аудиту: безкоштовних повних аудитів не існує.

    Тести нижче перевіряють обрізання опцій і створення сайту, а не
    квоту — але запуск мусить бути ЧИМОСЬ оплачений, і чесний спосіб
    один: записана покупка.
    """
    from datetime import UTC, datetime

    from app.application import purchases

    await purchases.record(
        db,
        organization_id=await _own_organization(client),
        provider="fake",
        external_id=f"pur-{uuid.uuid4()}",
        quantity=1,
        currency="USD",
        amount_minor=100,
        purchased_at=datetime.now(UTC),
    )
    await db.commit()


async def _make_audit(
    db, *, organization_id: uuid.UUID, origin: str = "https://example.com", score: int = 70
) -> Audit:
    """Готовий завершений аудит просто в базі.

    Через API його не створити: справжній запуск пішов би в чергу й у
    мережу, а перевіряємо ми доступ, а не краул.
    """
    audit = Audit(
        organization_id=organization_id,
        url=f"{origin}/",
        origin=origin,
        status=AuditStatus.COMPLETED,
        score_overall=score,
        options={},
        trigger=AuditTrigger.MANUAL,
    )
    db.add(audit)
    await db.flush()
    db.add(
        AuditTarget(
            audit_id=audit.id,
            position=0,
            url=f"{origin}/",
            origin=origin,
            status=AuditStatus.COMPLETED,
            score_overall=score,
            scores={"seo": score},
            versions={"detector": "d1", "scoring": "s1"},
        )
    )
    await db.flush()
    return audit


@pytest.mark.asyncio
async def test_an_audit_is_created_with_an_owner(client, db_session):
    """Створення через API прив'язує аудит до організації того, хто просив."""
    await register(client, "a@example.com")
    org_id = await _own_organization(client)
    await _grant_credit(db_session, client)

    response = await client.post(
        "/v1/audits", json={"url": "https://example.com", "options": {"max_pages": 5}}
    )

    assert response.status_code == 202
    audit_id = uuid.UUID(response.json()["id"])
    stored = await db_session.get(Audit, audit_id)
    assert stored.organization_id == org_id
    assert stored.created_by_user_id is not None
    assert stored.trigger is AuditTrigger.MANUAL


@pytest.mark.asyncio
async def test_an_audit_from_an_api_key_is_marked_as_such(client, db_session):
    """Запис має пам'ятати, звідки взявся запуск.

    «Чому цей аудит виконався» має відповідь у самому рядку, а не в
    кореляції часових міток із чимось іще.
    """
    await register(client, "a@example.com")
    await _grant_credit(db_session, client)
    token = (await client.post("/v1/auth/api-keys", json={})).json()["token"]
    await client.post("/v1/auth/logout")

    response = await client.post(
        "/v1/audits",
        json={"url": "https://example.com", "options": {"max_pages": 5}},
        headers={"X-API-Key": token},
    )

    assert response.status_code == 202
    stored = await db_session.get(Audit, uuid.UUID(response.json()["id"]))
    assert stored.trigger is AuditTrigger.API
    assert stored.created_by_user_id is None, "у ключа немає автора"


@pytest.mark.asyncio
async def test_an_audit_needs_authentication(client, db_session):
    audit = await _make_audit(db_session, organization_id=LEGACY_ORGANIZATION_ID)

    assert (await client.get(f"/v1/audits/{audit.id}")).status_code == 401
    assert (await client.get("/v1/audits")).status_code == 401


@pytest.mark.asyncio
async def test_a_foreign_audit_does_not_exist_for_the_asker(client, db_session):
    """Головна перевірка блоку.

    404, а не 403: «доступ заборонено» підтвердило б, що аудит існує, і
    дало б спосіб перебирати чужі ідентифікатори.
    """
    await register(client, "victim@example.com")
    victim_org = await _own_organization(client)
    audit = await _make_audit(db_session, organization_id=victim_org)

    await sign_in_as(client, "attacker@example.com")

    assert (await client.get(f"/v1/audits/{audit.id}")).status_code == 404
    assert (await client.get(f"/v1/audits/{audit.id}/report")).status_code == 404
    assert (await client.get(f"/v1/audits/{audit.id}/issues")).status_code == 404
    assert (await client.get(f"/v1/audits/{audit.id}/benchmark")).status_code == 404


@pytest.mark.asyncio
async def test_the_list_shows_only_your_own(client, db_session):
    await register(client, "victim@example.com")
    victim_org = await _own_organization(client)
    await _make_audit(db_session, organization_id=victim_org, origin="https://victim.example")

    await sign_in_as(client, "attacker@example.com")

    assert (await client.get("/v1/audits")).json() == []


@pytest.mark.asyncio
async def test_you_do_see_your_own(client, db_session):
    await register(client, "a@example.com")
    org = await _own_organization(client)
    await _make_audit(db_session, organization_id=org)

    listed = (await client.get("/v1/audits")).json()

    assert len(listed) == 1


@pytest.mark.asyncio
async def test_the_history_of_a_domain_is_not_public(client, db_session):
    """Найтихіший витік цього блоку.

    Історія ключувалася на origin і не питала про організацію: достатньо
    було знати чужий домен, щоб побачити чужу криву балів — тобто саме
    те, за що платять.
    """
    await register(client, "victim@example.com")
    victim_org = await _own_organization(client)
    await _make_audit(db_session, organization_id=victim_org, origin="https://secret.example")
    await _make_audit(db_session, organization_id=victim_org, origin="https://secret.example")

    await sign_in_as(client, "attacker@example.com")

    response = await client.get("/v1/audits/history/by-origin?origin=https://secret.example")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_you_do_see_the_history_of_your_own_domain(client, db_session):
    await register(client, "a@example.com")
    org = await _own_organization(client)
    await _make_audit(db_session, organization_id=org, origin="https://mine.example", score=60)
    await _make_audit(db_session, organization_id=org, origin="https://mine.example", score=70)

    response = await client.get("/v1/audits/history/by-origin?origin=https://mine.example")

    assert response.status_code == 200
    assert len(response.json()["points"]) == 2


@pytest.mark.asyncio
async def test_a_foreign_target_cannot_be_rescored(client, db_session):
    await register(client, "victim@example.com")
    victim_org = await _own_organization(client)
    audit = await _make_audit(db_session, organization_id=victim_org)
    target_id = (
        await db_session.scalars(select(AuditTarget.id).where(AuditTarget.audit_id == audit.id))
    ).one()

    await sign_in_as(client, "attacker@example.com")

    assert (await client.post(f"/v1/audits/targets/{target_id}/rescore")).status_code == 404


@pytest.mark.asyncio
async def test_the_legacy_service_key_has_an_organization_now(client, db_session, monkeypatch):
    """Глобальний ключ лишився живим, але вже не діє поза моделлю доступу.

    Він бачить службову організацію — ту саму, до якої міграція прив'язала
    аудити, що існували до появи власників.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "api_keys", ["service-key"])
    legacy = await db_session.get(Organization, LEGACY_ORGANIZATION_ID)
    assert legacy is not None, "міграція мала створити службову організацію"
    await _make_audit(db_session, organization_id=LEGACY_ORGANIZATION_ID)

    response = await client.get("/v1/audits", headers={"X-API-Key": "service-key"})

    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_the_legacy_key_does_not_see_customer_audits(client, db_session, monkeypatch):
    """Службовий ключ — не майстер-ключ.

    Він отримав організацію саме для того, щоб перестати бути всюдисущим.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "api_keys", ["service-key"])
    await register(client, "customer@example.com")
    org = await _own_organization(client)
    await _make_audit(db_session, organization_id=org)
    await client.post("/v1/auth/logout")

    response = await client.get("/v1/audits", headers={"X-API-Key": "service-key"})

    assert response.json() == []


# ── квота при створенні аудиту ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_free_state_allows_no_full_audit(client):
    """Безкоштовних повних аудитів не існує — і це видно через HTTP.

    Рішення власника 2026-09-03: безкоштовний стан акаунта дає нуль
    повних аудитів. Безкоштовним лишається превʼю — окремий шлях, який
    квоти не торкається (tests/integration/test_free_preview.py).
    """
    await register(client, "a@example.com")

    first = await client.post("/v1/audits", json={"url": "https://example.com"})

    assert first.status_code == 402
    # Нуль — це «не входить у стан», а не «вичерпано»: вичерпати нуль
    # неможливо, і причина чесно це каже.
    assert first.json()["detail"]["reason"] == "quota.not_included"
    assert first.json()["detail"]["limit"] == 0


@pytest.mark.asyncio
async def test_options_are_trimmed_to_the_plan_not_refused(client, db_session):
    """Клієнт просив 100 сторінок і отримає 10.

    Відмовити повністю означало б не зробити нічого через те, що не
    можемо зробити все. Скільки прочитано, у звіті видно окремо.
    """
    await register(client, "a@example.com")
    await _grant_credit(db_session, client)

    response = await client.post(
        "/v1/audits", json={"url": "https://example.com", "options": {"max_pages": 100}}
    )

    assert response.status_code == 202
    stored = await db_session.get(Audit, uuid.UUID(response.json()["id"]))
    assert stored.options["max_pages"] == 10, "обрізано до безкоштовного тарифу"


@pytest.mark.asyncio
async def test_the_semantic_layer_is_switched_off_when_the_plan_does_not_include_it(
    client, db_session
):
    await register(client, "a@example.com")
    await _grant_credit(db_session, client)

    response = await client.post(
        "/v1/audits", json={"url": "https://example.com", "options": {"llm": True}}
    )

    stored = await db_session.get(Audit, uuid.UUID(response.json()["id"]))
    assert stored.options["llm"] is False


@pytest.mark.asyncio
async def test_an_audit_creates_the_site_it_audits(client, db_session):
    """Історії потрібно, до чого прив'язатися.

    Сайт заводиться сам: людина просила перевірити адресу, а не
    оформити її, і змушувати її до зайвого кроку немає причини.
    """
    from app.models.sites import Site

    await register(client, "a@example.com")
    await _grant_credit(db_session, client)

    response = await client.post("/v1/audits", json={"url": "https://example.com/pricing"})

    stored = await db_session.get(Audit, uuid.UUID(response.json()["id"]))
    assert stored.site_id is not None
    site = await db_session.get(Site, stored.site_id)
    assert site.origin == "https://example.com"
