"""Ендпоінт звіту й адаптер ORM → ReportSource.

Тести бʼють по HTTP через ASGI-транспорт, але без БД: сесія підмінена
залежністю, бо перевіряємо шар звіту, а не SQLAlchemy.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from docx import Document

from app.api.deps import current_actor
from app.api.routes.audits import DOCX_MEDIA_TYPE
from app.audit.enums import AuditStatus, DegradationKind, Module, Severity
from app.core.db import get_session
from app.identity.authz import ActorContext
from app.identity.enums import Role
from app.main import app
from app.services.report_service import source_from_audit

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


@dataclass
class FakeIssue:
    code: str = "seo.canonical"
    module: str = "seo"
    severity: str = "medium"
    title: str = "Немає rel=canonical"
    description: str = ""
    recommendation: str = "Додайте canonical."
    evidence: dict[str, Any] = field(default_factory=dict)
    weight: int = 2
    issue_variant: str = "missing"
    msg_key: str = "seo.canonical.missing"
    msg_params: dict[str, Any] = field(default_factory=dict)


DEFAULT_EVIDENCE = {
    "http": {"entry_url": "https://example.com/", "origin": "https://example.com"},
    "robots_txt": {"exists": True},
}


@dataclass
class FakeTarget:
    """Ціль несе те, що до появи audit_targets лежало на аудиті."""

    id: uuid.UUID = field(default_factory=uuid.uuid4)
    position: int = 0
    url: str = "https://example.com"
    origin: str = "https://example.com"
    status: str = AuditStatus.COMPLETED.value
    score_overall: int = 62
    scores: dict[str, int] = field(
        default_factory=lambda: {"seo": 55, "ai_ready": 70, "llm_visibility": 65}
    )
    error: str | None = None
    degraded: list[dict[str, Any]] = field(default_factory=list)
    skipped_modules: list[str] = field(default_factory=lambda: ["performance"])
    evidence: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_EVIDENCE))
    # Підміна має мати ті самі поля, що й модель: інакше вона перевіряє
    # не той обʼєкт, який працює в бою.
    versions: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=lambda: datetime(2026, 8, 5, 12, tzinfo=UTC))
    finished_at: datetime = field(
        default_factory=lambda: datetime(2026, 8, 5, 12, 0, 30, tzinfo=UTC)
    )
    issues: list[Any] = field(default_factory=list)
    pages: list[Any] = field(default_factory=list)


@dataclass
class FakeAudit:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    url: str = "https://example.com"
    origin: str = "https://example.com"
    status: str = AuditStatus.COMPLETED.value
    score_overall: int = 62
    scores: dict[str, int] = field(
        default_factory=lambda: {"seo": 55, "ai_ready": 70, "llm_visibility": 65}
    )
    degraded: list[dict[str, Any]] = field(default_factory=list)
    skipped_modules: list[str] = field(default_factory=lambda: ["performance"])
    evidence: dict[str, Any] = field(default_factory=lambda: dict(DEFAULT_EVIDENCE))
    # Підміна має мати ті самі поля, що й модель: інакше вона перевіряє
    # не той обʼєкт, який працює в бою.
    versions: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime(2026, 8, 5, 12, tzinfo=UTC))
    started_at: datetime = field(default_factory=lambda: datetime(2026, 8, 5, 12, tzinfo=UTC))
    finished_at: datetime = field(
        default_factory=lambda: datetime(2026, 8, 5, 12, 0, 30, tzinfo=UTC)
    )
    targets: list[FakeTarget] = field(default_factory=list)
    issues: list[Any] = field(default_factory=list)
    pages: list[Any] = field(default_factory=list)


def default_issues() -> list[FakeIssue]:
    return [
        FakeIssue(evidence={"page_url": "https://example.com/a"}),
        FakeIssue(evidence={"page_url": "https://example.com/b"}),
        FakeIssue(
            code="seo.sitemap",
            msg_key="seo.sitemap.missing",
            severity="high",
            weight=2,
            title="sitemap.xml не знайдено",
        ),
    ]


def make_audit(**overrides: Any) -> FakeAudit:
    issues = overrides.pop("issues", None)
    audit = FakeAudit(**overrides)
    audit.issues = issues if issues is not None else default_issues()
    if not audit.targets:
        audit.targets = [
            FakeTarget(
                url=audit.url,
                status=audit.status,
                score_overall=audit.score_overall,
                scores=audit.scores,
                degraded=audit.degraded,
                skipped_modules=audit.skipped_modules,
                evidence=audit.evidence,
                issues=audit.issues,
            )
        ]
    return audit


@pytest.fixture
async def client(monkeypatch):
    """Підміняємо сесію й ключ: тест про звіт, а не про БД і не про auth."""
    audit_box: dict[str, Any] = {"audit": make_audit()}

    async def fake_get_audit(_session, audit_id, **_kwargs):
        audit = audit_box["audit"]
        return audit if audit is not None and audit.id == audit_id else None

    monkeypatch.setattr("app.services.audit_service.get_audit", fake_get_audit)

    # Перевірка «покупку повернено» ходить у БД, якої тут немає. Для
    # цих тестів платної історії не існує — стан «не повернено» і є
    # правдою про їхній аудит; сама перевірка покрита інтеграційно.
    async def no_refund(_db, _audit_id):
        return False

    monkeypatch.setattr("app.application.guest.paid_content_denied", no_refund)
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[current_actor] = actor_for_tests

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client, audit_box

    app.dependency_overrides.clear()


async def test_report_endpoint_returns_every_promised_field(client):
    http, box = client
    response = await http.get(f"/v1/audits/{box['audit'].id}/report")

    assert response.status_code == 200
    body = response.json()
    required = {
        "overall_score",
        "speed_score",
        "seo_score",
        "ai_ready_score",
        "llm_visibility_score",
        "issues",
        "recommendations",
        "evidence",
        "missing_data",
        "next_actions",
    }
    assert required <= set(body)
    assert body["overall_score"] == 62
    assert body["speed_score"] is None, "модуль пропущено — null, а не нуль"
    assert body["seo_score"] == 55


async def test_report_endpoint_switches_language(client):
    http, box = client
    audit_id = box["audit"].id

    uk = (await http.get(f"/v1/audits/{audit_id}/report", params={"lang": "uk"})).json()
    en = (await http.get(f"/v1/audits/{audit_id}/report", params={"lang": "en"})).json()

    assert uk["locale"] == "uk"
    assert en["locale"] == "en"
    assert uk["issues"][0]["title"] == "sitemap.xml не знайдено"
    assert en["issues"][0]["title"] == "sitemap.xml not found"
    assert uk["overall_score"] == en["overall_score"], "мова не має чіпати числа"


async def test_stored_audit_is_relocalised_from_msg_key_not_from_stored_text(client):
    """У БД лежить український текст; англійський збирається з ключа й params."""
    http, box = client
    box["audit"].targets[0].issues = [
        FakeIssue(
            code="seo.title",
            msg_key="seo.title.too_short",
            title="Title закороткий (21 симв.)",
            msg_params={"length": 21, "min": 30, "max": 60},
        )
    ]
    body = (await http.get(f"/v1/audits/{box['audit'].id}/report", params={"lang": "en"})).json()

    assert body["issues"][0]["title"] == "Title explains nothing (21 chars)"


async def test_unknown_language_is_rejected(client):
    """`de` тепер підтримується, тож перевіряємо справді невідоме."""
    http, box = client
    response = await http.get(f"/v1/audits/{box['audit'].id}/report", params={"lang": "xx"})
    assert response.status_code == 422


async def test_missing_audit_gives_404(client):
    http, _ = client
    response = await http.get(f"/v1/audits/{uuid.uuid4()}/report")
    assert response.status_code == 404


async def test_running_audit_has_no_report_yet(client):
    http, box = client
    box["audit"].status = AuditStatus.RUNNING.value
    response = await http.get(f"/v1/audits/{box['audit'].id}/report")

    assert response.status_code == 409
    assert "running" in response.json()["detail"]


async def test_partial_audit_still_gets_a_report(client):
    """Частковий аудит — це дані з прогалиною, а не відсутність даних."""
    http, box = client
    box["audit"].status = AuditStatus.PARTIAL.value
    box["audit"].targets[0].status = AuditStatus.PARTIAL.value
    box["audit"].targets[0].degraded = [
        {
            "scope": "performance",
            "kind": DegradationKind.PROVIDER_UNAVAILABLE.value,
            "reason": "429",
            "affected_modules": ["performance"],
        }
    ]
    body = (await http.get(f"/v1/audits/{box['audit'].id}/report")).json()

    assert body["audit"]["status"] == "partial"
    assert body["missing_data"][0]["affects"] == ["speed_score"]


async def test_docx_format_returns_a_word_attachment(client):
    http, box = client
    response = await http.get(
        f"/v1/audits/{box['audit'].id}/report", params={"format": "docx", "lang": "uk"}
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == DOCX_MEDIA_TYPE
    assert (
        'filename="audit-example.com-technical-uk.docx"'
        in response.headers["content-disposition"]
    )
    assert response.content[:2] == b"PK"
    Document(io.BytesIO(response.content))  # читається як справжній docx


async def test_docx_filename_follows_the_language(client):
    http, box = client
    response = await http.get(
        f"/v1/audits/{box['audit'].id}/report", params={"format": "docx", "lang": "en"}
    )
    assert (
        'filename="audit-example.com-technical-en.docx"'
        in response.headers["content-disposition"]
    )


async def test_json_stays_the_default_format(client):
    http, box = client
    response = await http.get(f"/v1/audits/{box['audit'].id}/report")

    assert response.headers["content-type"].startswith("application/json")
    # Без `lang` і без налаштувань профілю мова резолвиться в канонічну.
    assert response.json()["locale"] == "en"


async def test_unknown_format_is_rejected(client):
    http, box = client
    response = await http.get(
        f"/v1/audits/{box['audit'].id}/report", params={"format": "pdf"}
    )
    assert response.status_code == 422


async def test_docx_is_not_produced_for_an_unfinished_audit(client):
    http, box = client
    box["audit"].status = AuditStatus.QUEUED.value
    response = await http.get(
        f"/v1/audits/{box['audit'].id}/report", params={"format": "docx"}
    )
    assert response.status_code == 409


# ── адаптер ────────────────────────────────────────────────────────────────


def test_adapter_lifts_page_url_back_out_of_evidence():
    """page_url зберігається всередині evidence — без розпакування зникне групування."""
    audit = make_audit()
    source = source_from_audit(audit)

    canonical = [i for i in source.issues if i.code == "seo.canonical"]
    assert [i.page_url for i in canonical] == [
        "https://example.com/a",
        "https://example.com/b",
    ]
    assert all("page_url" not in i.evidence for i in canonical)


def test_adapter_restores_enums_and_skipped_modules():
    source = source_from_audit(make_audit())

    assert source.skipped_modules == {Module.PERFORMANCE}
    assert source.status is AuditStatus.COMPLETED
    assert all(isinstance(i.module, Module) for i in source.issues)
    assert all(isinstance(i.severity, Severity) for i in source.issues)


def test_adapter_falls_back_to_code_when_msg_key_is_empty():
    """Рядки з міграції 0002 мають msg_key = code — рендер має вижити."""
    audit = make_audit(issues=[FakeIssue(msg_key="")])
    source = source_from_audit(audit)

    assert source.issues[0].msg == "seo.canonical"


@pytest.mark.asyncio
async def test_llm_models_endpoint_feeds_the_interface():
    """Форма бере список звідси. Якщо він розійдеться з валідацією,
    користувач обере модель і отримає 422 на запуску аудиту."""
    from app.audit.llm.models import MODEL_IDS
    from app.schemas.audit import AuditOptionsIn

    app.dependency_overrides[current_actor] = actor_for_tests
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/v1/audits/llm-models")
    finally:
        app.dependency_overrides.pop(current_actor, None)

    assert response.status_code == 200
    models = response.json()
    assert [m["id"] for m in models] == list(MODEL_IDS)
    assert sum(1 for m in models if m["default"]) == 1
    for model in models:
        assert model["note"], f"{model['id']} без пояснення, чим платить користувач"
        assert AuditOptionsIn(llm_model=model["id"]).llm_model == model["id"]


def test_measured_modules_survive_a_missing_overall():
    """Загального бала немає чесно, але виміряне викидати не можна.

    Аудит сайту з простроченим хостингом показував порожньо там, де ми
    таки виміряли швидкість і захист: зведення пропускало ціль без
    загального бала цілком.
    """
    from app.services.audit_service import _average_module_scores

    @dataclass
    class Target:
        score_overall: int | None
        scores: dict[str, int]

    targets = [
        Target(None, {"performance": 100, "tech": 35}),
        Target(60, {"performance": 40, "tech": 55}),
    ]
    assert _average_module_scores(targets) == {"performance": 70, "tech": 45}
