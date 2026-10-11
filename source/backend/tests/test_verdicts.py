"""Вердикти людини: чи відрізняє система «неправда» від «не робитимемо»."""

from __future__ import annotations

import uuid

import httpx
import pytest

from app.api.deps import current_actor
from app.audit.enums import Verdict
from app.core.db import get_session
from app.identity.authz import ActorContext
from app.identity.enums import PlatformRole, Role
from app.main import app
from app.services.verdict_service import MIN_VERDICTS_TO_JUDGE, CheckFeedback

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


def staff_actor() -> ActorContext:
    """Той самий актор, але з команди Crawldy.

    Окрема функція, а не прапорець у попередній: різниця між клієнтом і
    персоналом має бути видима в тесті так само явно, як у коді.
    """
    return ActorContext(
        organization_id=TEST_ORGANIZATION_ID,
        role=Role.OWNER,
        auth="session",
        user_id=uuid.UUID("00000000-0000-0000-0000-00000000beef"),
        platform_role=PlatformRole.STAFF,
    )


def _feedback(code: str, **counts: int) -> CheckFeedback:
    return CheckFeedback(code=code, total=sum(counts.values()), by_verdict=counts)


def test_wont_fix_does_not_count_against_the_check():
    """«Правда, але не робитимемо» — це про пріоритети, а не про помилку."""
    item = _feedback("seo.title", agreed=3, wont_fix=5, fixed=2)
    assert item.wrong_share == 0.0


def test_only_wrong_counts_against_the_check():
    item = _feedback("seo.orphan_pages", agreed=6, wrong=2)
    assert item.wrong_share == 0.25


def test_unclear_is_about_wording_not_detection():
    """«Незрозуміло, що робити» — сигнал про формулювання."""
    item = _feedback("llm.stale_content", agreed=4, unclear=4)
    assert item.wrong_share == 0.0
    assert item.by_verdict["unclear"] == 4


def test_a_couple_of_answers_do_not_make_a_verdict_about_the_check():
    """На двох відповідях 50% помилок — це одна незгода, а не властивість."""
    item = _feedback("seo.topic_islands", agreed=1, wrong=1)
    assert item.wrong_share == 0.5
    assert item.is_meaningful is False


def test_enough_answers_make_the_share_meaningful():
    item = _feedback("seo.topic_islands", agreed=MIN_VERDICTS_TO_JUDGE, wrong=1)
    assert item.is_meaningful is True


@pytest.fixture
async def client(monkeypatch):
    box: dict[str, object] = {"saved": None, "summary": []}

    async def fake_record(_session, issue_id, verdict, *, note="", author=""):
        if box["saved"] == "missing":
            return None

        class Saved:
            pass

        saved = Saved()
        saved.issue_id = issue_id
        saved.code = "seo.canonical"
        saved.verdict = verdict
        saved.note = note
        box["saved"] = saved
        return saved

    async def fake_summary(_session):
        return list(box["summary"])

    monkeypatch.setattr("app.services.verdict_service.record", fake_record)
    monkeypatch.setattr("app.services.verdict_service.feedback_by_check", fake_summary)
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[current_actor] = actor_for_tests

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http, box

    app.dependency_overrides.clear()


ISSUE = "/v1/audits/issues/00000000-0000-0000-0000-000000000001/verdict"


async def test_recording_a_verdict_returns_what_was_saved(client):
    http, _ = client
    response = await http.put(
        ISSUE, json={"verdict": "wrong", "note": "canonical там є, ми його не побачили"}
    )
    assert response.status_code == 200
    assert response.json()["verdict"] == "wrong"


async def test_a_verdict_for_an_unknown_issue_is_a_404(client):
    http, box = client
    box["saved"] = "missing"
    response = await http.put(ISSUE, json={"verdict": "agreed"})
    assert response.status_code == 404


async def test_an_invented_verdict_is_rejected(client):
    """Перелік закритий: «відхилено» без причини нам нічого не дає."""
    http, _ = client
    response = await http.put(ISSUE, json={"verdict": "відхилено"})
    assert response.status_code == 422


async def test_a_customer_cannot_read_the_feedback_of_all_organizations(client):
    """Регресія витоку.

    Зведення йде по **всіх** організаціях, і воно жило на клієнтському
    API: будь-який автентифікований клієнт бачив, скільки чужих людей і як
    відповіли на кожен чек. Перевірка тут не про наявність коду, а про те,
    що видно ззовні — клієнт із вгаданим URL отримує відмову.
    """
    http, _ = client
    assert (await http.get("/v1/admin/checks/feedback")).status_code == 403


async def test_feedback_says_how_many_answers_are_needed(client):
    """Зведення переїхало під права команди: воно по всіх організаціях."""
    http, box = client
    app.dependency_overrides[current_actor] = staff_actor
    box["summary"] = [_feedback("seo.orphan_pages", agreed=6, wrong=2)]
    body = (await http.get("/v1/admin/checks/feedback")).json()
    assert body["min_answers_to_judge"] == MIN_VERDICTS_TO_JUDGE
    assert body["checks"][0]["wrong_share"] == 0.25
    assert body["checks"][0]["enough_answers"] is True


def test_every_verdict_value_is_a_distinct_answer():
    """Пʼять відповідей, а не «так» і «ні»: інакше дані не інтерпретувати."""
    assert {v.value for v in Verdict} == {
        "agreed", "fixed", "wont_fix", "wrong", "unclear",
    }


def test_issue_out_carries_the_recorded_verdict_without_choking_on_it():
    """Регресія: поле схеми й звʼязок моделі не можуть зватися однаково.

    Поки звʼязок теж звався `verdict`, pydantic із `from_attributes` брав
    атрибут за іменем і отримував ORM-обʼєкт замість enum. Ендпойнт
    аудиту падав 500 — але лише після того, як зʼявився перший записаний
    вердикт, тобто на живому стеку й не одразу.
    """
    import uuid as _uuid
    from dataclasses import dataclass, field

    from app.audit.enums import Module, Severity
    from app.schemas.audit import IssueOut

    @dataclass
    class Recorded:
        verdict: Verdict = Verdict.WRONG
        note: str = "canonical там є"

    @dataclass
    class OrmIssue:
        id: _uuid.UUID = field(default_factory=_uuid.uuid4)
        module: Module = Module.SEO
        code: str = "seo.canonical"
        severity: Severity = Severity.MEDIUM
        title: str = "Немає canonical"
        description: str = ""
        recommendation: str = ""
        evidence: dict = field(default_factory=dict)
        page_url: str | None = None
        human_verdict: Recorded | None = None

    empty = IssueOut.from_issue(OrmIssue())
    assert empty.verdict is None and empty.verdict_note == ""

    answered = IssueOut.from_issue(OrmIssue(human_verdict=Recorded()))
    assert answered.verdict is Verdict.WRONG
    assert answered.verdict_note == "canonical там є"
