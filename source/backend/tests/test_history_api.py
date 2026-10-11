"""Ендпоінти історії й перерахунку. Через HTTP, але без БД."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest

from app.api.deps import current_actor
from app.application.visibility import HistoryWindow
from app.core.db import get_session
from app.identity.authz import ActorContext
from app.identity.enums import Role
from app.main import app
from app.report.history import ScorePoint

# Актор для тестів шару API без бази. Маршрути тепер вимагають контекст
# організації, а не глобальний ключ: перевірка власності — не деталь
# реалізації, і підмінити її «якимось ключем» більше не можна.
TEST_ORGANIZATION_ID = uuid.UUID("00000000-0000-0000-0000-00000000f00d")


def actor_for_tests() -> ActorContext:
    return ActorContext(
        organization_id=TEST_ORGANIZATION_ID,
        role=Role.OWNER,
        auth="session",
        user_id=uuid.UUID("00000000-0000-0000-0000-00000000beef"),
    )

WHEN = datetime(2026, 1, 1, tzinfo=UTC)
RULES = {"detector": "aaa", "scoring": "bbb"}


def _point(day: int, overall: int, versions=None, *, snapshot=False) -> ScorePoint:
    return ScorePoint(
        audit_id=f"00000000-0000-0000-0000-00000000000{day}",
        at=WHEN + timedelta(days=day),
        overall=overall,
        scores={"seo": overall, "tech": overall},
        versions=versions if versions is not None else dict(RULES),
        has_snapshot=snapshot,
    )


@pytest.fixture
async def client(monkeypatch):
    box: dict[str, object] = {"points": [], "rescore": None}

    async def fake_history(_session, origin, **_kwargs):
        return list(box["points"])

    async def fake_rescore(_session, target_id, **_kwargs):
        return box["rescore"]

    async def unlimited_window(_session, **_kwargs):
        return HistoryWindow(days=None, since=None)

    monkeypatch.setattr("app.services.audit_service.score_history", fake_history)
    monkeypatch.setattr("app.services.audit_service.rescore_target", fake_rescore)
    # Ці тести перевіряють криву, а не тариф: вікно видимості безмежне,
    # інакше маршрут пішов би по права в базу, якої тут немає.
    monkeypatch.setattr("app.api.routes.audits.history_window", unlimited_window)
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[current_actor] = actor_for_tests

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http, box

    app.dependency_overrides.clear()


async def test_history_marks_the_step_where_our_rules_changed(client):
    http, box = client
    box["points"] = [
        _point(0, 50, snapshot=True),
        _point(30, 62, {**RULES, "scoring": "інша"}),
    ]
    response = await http.get(
        "/v1/audits/history/by-origin", params={"origin": "https://example.com"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["incomparable_steps"] == 1
    assert body["fixable_by_recompute"] == 1
    assert body["steps"][0]["changed_in_us"] == ["scoring"]
    assert body["steps"][0]["overall_delta"] == 12


async def test_history_of_a_site_with_stable_rules_is_comparable(client):
    http, box = client
    box["points"] = [_point(0, 50), _point(30, 62), _point(60, 70)]
    body = (
        await http.get(
            "/v1/audits/history/by-origin", params={"origin": "https://example.com/"}
        )
    ).json()
    assert body["incomparable_steps"] == 0
    assert [s["overall_delta"] for s in body["steps"]] == [12, 8]


async def test_history_without_audits_is_a_404_not_an_empty_curve(client):
    http, box = client
    box["points"] = []
    response = await http.get(
        "/v1/audits/history/by-origin", params={"origin": "https://nobody.example"}
    )
    assert response.status_code == 404


async def test_rescore_returns_both_numbers_and_does_not_replace_the_old_one(client):
    http, box = client
    stored = _point(0, 50, snapshot=True)
    recomputed = _point(0, 44, {**RULES, "scoring": "нинішня"}, snapshot=True)
    box["rescore"] = (stored, recomputed)
    body = (
        await http.post(
            "/v1/audits/targets/00000000-0000-0000-0000-000000000001/rescore"
        )
    ).json()
    assert body["stored"]["overall"] == 50
    assert body["recomputed"]["overall"] == 44
    assert body["difference"]["comparable"] is True
    assert body["difference"]["rebased"] is True


async def test_rescore_without_a_snapshot_is_a_404(client):
    http, box = client
    box["rescore"] = None
    response = await http.post(
        "/v1/audits/targets/00000000-0000-0000-0000-000000000001/rescore"
    )
    assert response.status_code == 404
