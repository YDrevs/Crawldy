"""Мова через HTTP: деталі аудиту й звіт мусять розуміти її однаково.

Поки деталі віддавалися зі збережених стовпців, той самий аудит через
`/report` читався німецькою, а через `/audits/{id}` — завжди однією мовою.
Механізм перекладу при цьому існував і працював — просто інтерфейс, який
читає саме деталі, до нього не був підключений.
"""

from __future__ import annotations

import uuid

import pytest

from app.audit.enums import AuditStatus, Module, Severity
from app.models.audit import Audit, AuditIssue, AuditTarget
from app.models.identity import Organization, User
from tests.integration.conftest import register


async def _an_audit_with_a_finding(db, organization_id: uuid.UUID) -> uuid.UUID:
    """Аудит, збережений структурою: ключ і параметри, а не готовий текст."""
    audit = Audit(
        organization_id=organization_id,
        url="https://example.com/",
        origin="https://example.com",
        status=AuditStatus.COMPLETED,
        score_overall=64,
        scores={"seo": 55},
        options={},
        versions={"detector": "d1", "scoring": "s1"},
    )
    db.add(audit)
    await db.flush()
    target = AuditTarget(
        audit_id=audit.id,
        position=0,
        url=audit.url,
        origin=audit.origin,
        status=AuditStatus.COMPLETED,
        score_overall=64,
        scores={"seo": 55},
    )
    db.add(target)
    await db.flush()
    db.add(
        AuditIssue(
            audit_id=audit.id,
            target_id=target.id,
            module=Module.SEO,
            code="seo.h1",
            severity=Severity.HIGH,
            # Кеш дефолтної мови. Жоден шлях не має його читати.
            title="СТАРИЙ КЕШ",
            description="СТАРИЙ КЕШ",
            recommendation="СТАРИЙ КЕШ",
            evidence={"found": 2, "expected": 1},
            weight=3,
            issue_variant="multiple",
            msg_key="seo.h1.multiple",
            msg_params={"count": 2},
        )
    )
    await db.flush()
    return audit.id


@pytest.mark.asyncio
async def test_the_same_audit_comes_back_in_two_languages(client, db_session):
    body = (await register(client, "two@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    audit_id = await _an_audit_with_a_finding(db_session, org)

    english = (await client.get(f"/v1/audits/{audit_id}", params={"lang": "en"})).json()
    ukrainian = (await client.get(f"/v1/audits/{audit_id}", params={"lang": "uk"})).json()

    assert english["issues"][0]["title"] != ukrainian["issues"][0]["title"]
    assert english["locale"] == "en"
    assert ukrainian["locale"] == "uk"


@pytest.mark.asyncio
async def test_the_stored_rendered_text_is_never_served(client, db_session):
    """У базі лежить «СТАРИЙ КЕШ» — до клієнта він потрапити не може."""
    body = (await register(client, "cache@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    audit_id = await _an_audit_with_a_finding(db_session, org)

    for lang in ("en", "uk", "ja"):
        seen = (await client.get(f"/v1/audits/{audit_id}", params={"lang": lang})).json()
        assert "СТАРИЙ КЕШ" not in str(seen["issues"])


@pytest.mark.asyncio
async def test_the_detail_and_the_report_agree_on_the_language(client, db_session):
    """Одна семантика на два маршрути — інакше UI і документ розходяться."""
    body = (await register(client, "same@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    audit_id = await _an_audit_with_a_finding(db_session, org)

    detail = (await client.get(f"/v1/audits/{audit_id}", params={"lang": "uk"})).json()
    report = (
        await client.get(f"/v1/audits/{audit_id}/report", params={"lang": "uk", "format": "json"})
    ).json()

    from_detail = detail["issues"][0]["title"]
    from_report = report["issues"][0]["title"]
    assert from_detail == from_report


@pytest.mark.asyncio
async def test_language_does_not_change_the_measured_facts(client, db_session):
    body = (await register(client, "facts@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    audit_id = await _an_audit_with_a_finding(db_session, org)

    english = (await client.get(f"/v1/audits/{audit_id}", params={"lang": "en"})).json()
    japanese = (await client.get(f"/v1/audits/{audit_id}", params={"lang": "ja"})).json()

    for field in ("score_overall", "scores", "status", "issues_count", "issues_by_severity"):
        assert english[field] == japanese[field], field
    assert english["issues"][0]["evidence"] == japanese["issues"][0]["evidence"]
    assert english["issues"][0]["msg"] == japanese["issues"][0]["msg"]


@pytest.mark.asyncio
async def test_a_partial_language_falls_back_to_english_not_to_ukrainian(client, db_session):
    body = (await register(client, "partial@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    audit_id = await _an_audit_with_a_finding(db_session, org)

    japanese = (await client.get(f"/v1/audits/{audit_id}", params={"lang": "ja"})).json()
    english = (await client.get(f"/v1/audits/{audit_id}", params={"lang": "en"})).json()
    ukrainian = (await client.get(f"/v1/audits/{audit_id}", params={"lang": "uk"})).json()

    assert japanese["issues"][0]["title"] == english["issues"][0]["title"]
    assert japanese["issues"][0]["title"] != ukrainian["issues"][0]["title"]
    assert japanese["issues"][0]["text_locale"] == "en", "факт фолбеку видно"


@pytest.mark.asyncio
async def test_the_user_preference_answers_when_the_request_is_silent(client, db_session):
    """Без `lang` мова береться з профілю, а не з дефолту продукту."""
    body = (await register(client, "pref@example.com")).json()
    org = uuid.UUID(body["organization"]["id"])
    audit_id = await _an_audit_with_a_finding(db_session, org)

    user = await db_session.get(User, uuid.UUID(body["user"]["id"]))
    user.locale = "uk"
    await db_session.flush()

    seen = (await client.get(f"/v1/audits/{audit_id}")).json()
    assert seen["locale"] == "uk"


@pytest.mark.asyncio
async def test_the_organization_answers_when_the_user_never_chose(client, db_session):
    body = (await register(client, "orgpref@example.com")).json()
    org_id = uuid.UUID(body["organization"]["id"])
    audit_id = await _an_audit_with_a_finding(db_session, org_id)

    organization = await db_session.get(Organization, org_id)
    organization.default_locale = "uk"
    await db_session.flush()

    seen = (await client.get(f"/v1/audits/{audit_id}")).json()
    assert seen["locale"] == "uk", "користувач не обирав — їде за організацією"


@pytest.mark.asyncio
async def test_an_explicit_request_beats_the_profile(client, db_session):
    body = (await register(client, "explicit@example.com")).json()
    org_id = uuid.UUID(body["organization"]["id"])
    audit_id = await _an_audit_with_a_finding(db_session, org_id)

    user = await db_session.get(User, uuid.UUID(body["user"]["id"]))
    user.locale = "uk"
    await db_session.flush()

    seen = (await client.get(f"/v1/audits/{audit_id}", params={"lang": "en"})).json()
    assert seen["locale"] == "en"


@pytest.mark.asyncio
async def test_a_fresh_organization_speaks_english(client):
    """Дефолт продукту — англійська, і це видно з першої ж реєстрації."""
    body = (await register(client, "fresh@example.com")).json()
    assert body["organization"].get("default_locale", "en") == "en"
