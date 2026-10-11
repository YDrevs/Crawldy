"""Порівняння з конкурентами: чи відрізняє воно норму галузі від відставання."""

from __future__ import annotations

import uuid

from app.identity.authz import ActorContext
from app.identity.enums import Role
from app.report.benchmark import Contender, compare

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


RULES = {"detector": "aaa", "scoring": "bbb", "config": "ccc"}


def _site(label: str, overall: int | None, findings=(), versions=None, **scores) -> Contender:
    return Contender(
        label=label,
        origin=f"https://{label}.example",
        overall=overall,
        scores=scores or {"seo": 60, "tech": 60},
        versions=versions if versions is not None else dict(RULES),
        findings=set(findings),
    )


def test_a_problem_everyone_has_is_not_a_competitive_loss():
    """Норма галузі: виправляти варто, виграти над конкурентами — ні."""
    result = compare(
        _site("you", 62, {"seo.canonical.missing", "seo.h1.missing"}),
        [
            _site("a", 71, {"seo.canonical.missing"}),
            _site("b", 68, {"seo.canonical.missing"}),
        ],
    )
    assert result.everyone_has == ["seo.canonical.missing"]
    assert result.only_you_have == ["seo.h1.missing"]


def test_a_problem_none_of_the_rivals_has_is_where_you_lose():
    result = compare(
        _site("you", 50, {"seo.sitemap.missing"}),
        [_site("a", 70, {"seo.h1.missing"}), _site("b", 72, {"seo.h1.missing"})],
    )
    assert result.only_you_have == ["seo.sitemap.missing"]
    assert result.only_you_avoid == ["seo.h1.missing"]


def test_an_advantage_needs_every_rival_to_have_the_problem():
    """Один конкурент із вадою — це не ваша перевага, а його недогляд."""
    result = compare(
        _site("you", 62, set()),
        [_site("a", 71, {"seo.h1.missing"}), _site("b", 68, set())],
    )
    assert result.only_you_avoid == []


def test_module_gap_is_measured_against_the_median_not_the_average():
    """Один конкурент із заблокованим краулом не має перетягувати картину."""
    result = compare(
        _site("you", 60, seo=60),
        [_site("a", 70, seo=70), _site("b", 72, seo=72), _site("c", 10, seo=10)],
    )
    assert result.behind_on == {"seo": -10}


def test_being_ahead_is_reported_too():
    result = compare(
        _site("you", 80, seo=80, tech=40),
        [_site("a", 60, seo=60, tech=60)],
    )
    assert result.ahead_on == {"seo": 20}
    assert result.behind_on == {"tech": -20}


def test_a_module_the_rivals_do_not_have_is_skipped():
    """У конкурента заблокований модуль — порівнювати нема з чим."""
    result = compare(_site("you", 60, seo=60, tech=50), [_site("a", 70, seo=70)])
    assert "tech" not in result.behind_on
    assert "tech" not in result.ahead_on


def test_rank_counts_only_sites_that_have_a_score():
    result = compare(
        _site("you", 62), [_site("a", 71), _site("b", None), _site("c", 40)]
    )
    assert result.rank == 2
    assert result.to_json()["of"] == 3


def test_a_different_crawl_budget_makes_the_comparison_invalid():
    """25 сторінок проти 5 — це порівняння бюджетів, а не сайтів."""
    rival = _site("a", 71, versions={**RULES, "config": "інша"})
    result = compare(_site("you", 62), [rival])
    assert result.comparable is False
    assert result.incomparable_with[rival.origin] == ["config"]


def test_same_rules_make_the_comparison_valid():
    assert compare(_site("you", 62), [_site("a", 71)]).comparable is True


def test_a_single_target_audit_says_there_is_nobody_to_compare_with():
    result = compare(_site("you", 62, {"seo.h1.missing"}), [])
    assert result.everyone_has == []
    assert result.only_you_avoid == []
    assert result.rank == 1


# ── через HTTP, на цілях одного аудиту ─────────────────────────────────────


async def test_benchmark_endpoint_reads_targets_of_one_audit(monkeypatch):
    """Аудит на кілька URL — це вже ви й конкуренти; бракувало прочитання."""
    import uuid as _uuid
    from dataclasses import dataclass
    from dataclasses import field as dc_field

    import httpx

    from app.api.deps import current_actor
    from app.core.db import get_session
    from app.main import app

    @dataclass
    class FakeIssue:
        msg_key: str
        code: str = "seo.x"

    @dataclass
    class FakeTarget:
        id: _uuid.UUID
        url: str
        origin: str
        score_overall: int
        scores: dict
        versions: dict
        issues: list = dc_field(default_factory=list)

    @dataclass
    class FakeAudit:
        targets: list

    audit = FakeAudit(
        targets=[
            FakeTarget(
                id=_uuid.uuid4(),
                url="https://you.example/",
                origin="https://you.example",
                score_overall=62,
                scores={"seo": 60},
                versions=dict(RULES),
                issues=[FakeIssue("seo.canonical.missing"), FakeIssue("seo.h1.missing")],
            ),
            FakeTarget(
                id=_uuid.uuid4(),
                url="https://rival.example/",
                origin="https://rival.example",
                score_overall=71,
                scores={"seo": 70},
                versions=dict(RULES),
                issues=[FakeIssue("seo.canonical.missing")],
            ),
        ]
    )

    async def fake_get_audit(_session, _audit_id, **_kwargs):
        return audit

    monkeypatch.setattr("app.services.audit_service.get_audit", fake_get_audit)
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[current_actor] = actor_for_tests
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
            body = (await http.get(f"/v1/audits/{_uuid.uuid4()}/benchmark")).json()
    finally:
        app.dependency_overrides.clear()

    assert body["rank"] == 2
    assert body["everyone_has"] == ["seo.canonical.missing"]
    assert body["only_you_have"] == ["seo.h1.missing"]
    assert body["behind_on"] == {"seo": -10}
