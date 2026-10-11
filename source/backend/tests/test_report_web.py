"""Контракт результату для інтерфейсу: `ReportDocument` → `AuditResultResponse`.

Шар тонкий і саме тому був непокритий: він «нічого не робить». Але
переклад між внутрішнім представленням і публічним контрактом — це
рівно те місце, де службові значення просочуються назовні як дані.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest

from app.audit.enums import AuditStatus, DegradationKind, Module, Severity
from app.audit.i18n import Locale
from app.audit.types import Degradation, Issue
from app.report.builder import build_report
from app.report.types import ReportSource
from app.report.web import to_web

AUDIT_ID = uuid.UUID("9c2e1b40-0000-4000-8000-00000000a001")
SITE_ID = uuid.UUID("5b1f0a3e-0000-4000-8000-000000000001")


def issue(*, module=Module.SEO, severity=Severity.MEDIUM) -> Issue:
    return Issue(
        code="seo.canonical",
        module=module,
        severity=severity,
        title="t",
        evidence={},
        weight=2,
        page_url="https://example.com/",
        msg="seo.canonical.missing",
        params={},
        key="missing",
    )


def source(*, skipped=None, scores=None, degraded=None, partial=None) -> ReportSource:
    return ReportSource(
        url="https://example.com",
        entry_url="https://example.com/",
        origin="https://example.com",
        overall=50,
        scores=scores if scores is not None else {m.value: 50 for m in Module},
        issues=[issue()],
        degraded=list(degraded or []),
        skipped_modules=set(skipped or ()),
        partial_modules=set(partial or ()),
        evidence={},
        pages_crawled=3,
        status=AuditStatus.COMPLETED,
    )


def web(src: ReportSource, locale: Locale = Locale.EN):
    return to_web(
        build_report(src, locale),
        audit_id=AUDIT_ID,
        site_id=SITE_ID,
        status="completed",
        finished_at=datetime(2026, 8, 21, 9, 14, tzinfo=UTC),
        fallback_locale="en",
    )


def test_excluded_module_reports_no_score_rather_than_zero():
    """Невиміряний напрям не має віддавати нуль.

    Усередині `ScoreEntry.score` — `int`, і модуль без даних тримає там
    0 як службове значення; docx обходить його перевіркою `excluded`.
    У контракті поле оголошене `int | None` саме тому, що нуль читається
    як «модуль провалено», тобто як вимірювання, якого не було.
    """
    scores = {m.value: 50 for m in Module}
    scores.pop(Module.PERFORMANCE.value)
    result = web(source(skipped={Module.PERFORMANCE}, scores=scores))

    speed = next(m for m in result.modules if m.module is Module.PERFORMANCE)
    assert speed.excluded is True
    assert speed.score is None, "виключений модуль віддав число замість порожнечі"
    assert speed.band == "unknown"

    measured = next(m for m in result.modules if m.module is Module.SEO)
    assert measured.score == 50


def test_measured_zero_survives_the_trip():
    """Нуль виміряного модуля — справжній нуль, і його не можна ховати.

    Зворотний бік попереднього тесту: якщо викидати нулі як службові,
    зникне сайт, який справді провалив напрям.
    """
    scores = {m.value: 50 for m in Module}
    scores[Module.SEO.value] = 0
    result = web(source(scores=scores))

    seo = next(m for m in result.modules if m.module is Module.SEO)
    assert seo.excluded is False
    assert seo.score == 0


def test_missing_data_note_follows_the_report_language():
    """Приписка до прогалини — теж текст для клієнта.

    Рядки жили в білдері жорстко українською, і англійський звіт віддавав
    «модуль виключено з overall» посеред англійського тексту. Тест на
    `reason` цього не бачив: той локалізується поруч і окремо.
    """
    degraded = [
        Degradation(
            scope="performance",
            kind=DegradationKind.PROVIDER_UNAVAILABLE,
            reason="429 Too Many Requests",
            affected_modules=[Module.PERFORMANCE],
        )
    ]
    src = source(skipped={Module.PERFORMANCE}, degraded=degraded)

    english = web(src, Locale.EN).missing_data[0]
    ukrainian = web(src, Locale.UK).missing_data[0]

    assert english.note and ukrainian.note
    assert english.note != ukrainian.note
    assert "виключено" not in english.note
    assert "excluded" in english.note.lower()
    assert "виключено" in ukrainian.note


def test_module_weights_are_the_effective_ones():
    """Вага в контракті — та, з якою модуль справді увійшов у бал.

    Коли напрям виключено, його вага розходиться між рештою. Віддати
    номінальну вагу означає, що сума на екрані не збіжиться зі 100%.
    """
    scores = {m.value: 50 for m in Module}
    scores.pop(Module.PERFORMANCE.value)
    result = web(source(skipped={Module.PERFORMANCE}, scores=scores))

    active = [m for m in result.modules if not m.excluded]
    # Доступність пішла з переліку модулів у власний знімок, але свою
    # частку загального бала поки зберігає — тому видимі ваги сходяться
    # до 1.0 без неї. Явна перевірка, а не послаблений допуск: різницю
    # має бути видно, поки вона існує.
    from app.audit.scoring import active_weights

    hidden = active_weights({Module.PERFORMANCE}).get(Module.ACCESSIBILITY, 0.0)
    assert abs(sum(m.weight for m in active) - (1.0 - hidden)) < 0.001
    assert all(m.module is not Module.ACCESSIBILITY for m in result.modules)
    assert next(m for m in result.modules if m.excluded).weight == 0.0


# ── чому модуля немає в балі (E-01) і чесний `partial` (E-09) ─────────────
#
# `excluded` лишається тим, чим був: «бала немає». Причину несе окреме поле,
# і в контракті вона малими літерами, як решта станів. Доступність у
# `modules` не входить, тож її причина — у знімку `accessibility`.

EXCLUDED = "excluded_by_request"
NOT_MEASURED = "withheld_not_measured"

SPEED_OFF = Degradation(
    "performance",
    DegradationKind.MODULE_EXCLUDED,
    "модуль вимкнено в опціях аудиту",
    [Module.PERFORMANCE],
)


def _without(*modules: Module) -> dict[str, int]:
    return {m.value: 50 for m in Module if m not in modules}


def _module(payload: dict[str, Any], module: Module) -> dict[str, Any]:
    return next(m for m in payload["modules"] if m["module"] == module.value)


def test_accessibility_excluded_by_the_client_is_named_as_such():
    off = Degradation(
        "accessibility",
        DegradationKind.MODULE_EXCLUDED,
        "модуль вимкнено в опціях аудиту",
        [Module.ACCESSIBILITY],
    )
    result = web(
        source(
            skipped={Module.ACCESSIBILITY},
            scores=_without(Module.ACCESSIBILITY),
            degraded=[off],
        )
    )
    payload = result.model_dump(mode="json")

    assert payload["accessibility"]["withheld_reason"] == EXCLUDED
    assert payload["accessibility"]["counts_toward_overall"] is False


@pytest.mark.parametrize(
    ("degraded", "speed_reason"),
    [
        (
            [
                SPEED_OFF,
                Degradation(
                    "accessibility",
                    DegradationKind.PARTIAL_DATA,
                    "доступність не виміряно",
                    [Module.ACCESSIBILITY],
                ),
            ],
            EXCLUDED,
        ),
        (
            [
                Degradation(
                    "accessibility",
                    DegradationKind.PROVIDER_UNAVAILABLE,
                    "провайдер не повернув цю категорію",
                    [Module.ACCESSIBILITY],
                )
            ],
            None,
        ),
        (
            # Провайдер не відповів зовсім: прогалину пояснює лише деградація
            # швидкості, а доступність виключено мовчки.
            [
                Degradation(
                    "performance",
                    DegradationKind.PROVIDER_UNAVAILABLE,
                    "429",
                    [Module.PERFORMANCE],
                )
            ],
            NOT_MEASURED,
        ),
    ],
    ids=["performance_excluded", "no_category", "provider_silent"],
)
def test_requested_but_unmeasured_accessibility_is_never_called_excluded(degraded, speed_reason):
    skipped = {Module.ACCESSIBILITY} | {m for d in degraded for m in d.affected_modules}
    payload = web(
        source(skipped=skipped, scores=_without(*skipped), degraded=degraded)
    ).model_dump(mode="json")

    assert payload["accessibility"]["withheld_reason"] == NOT_MEASURED
    assert payload["accessibility"]["counts_toward_overall"] is False
    speed = _module(payload, Module.PERFORMANCE)
    assert speed["withheld_reason"] == speed_reason
    assert speed["excluded"] is (speed_reason is not None)


def test_measured_accessibility_and_scored_modules_carry_no_reason():
    payload = web(source()).model_dump(mode="json")

    assert payload["accessibility"]["withheld_reason"] is None
    assert payload["accessibility"]["counts_toward_overall"] is True
    assert all(m["withheld_reason"] is None for m in payload["modules"])


def test_a_partially_measured_llm_visibility_keeps_its_score_and_says_partial():
    from app.report.i18n import t

    disabled = Degradation(
        "llm", DegradationKind.LAYER_DISABLED, "вимкнено", [Module.LLM_VISIBILITY]
    )
    result = web(source(degraded=[disabled], partial={Module.LLM_VISIBILITY}))
    llm = _module(result.model_dump(mode="json"), Module.LLM_VISIBILITY)

    assert (llm["score"], llm["excluded"], llm["partial"], llm["withheld_reason"]) == (
        50,
        False,
        True,
        None,
    )
    (gap,) = [g for g in result.missing_data if g.scope == "llm"]
    assert gap.note == t("missing_note_partial", Locale.EN), "прапорець і примітка згодні"


def test_withheld_reason_is_an_additive_nullable_enum():
    """Старі відповіді й старі споживачі читаються так само, як до поля."""
    from app.schemas.result import (
        RESULT_CONTRACT_VERSION,
        AccessibilitySnapshotOut,
        ModuleScoreOut,
    )

    assert RESULT_CONTRACT_VERSION == 2, "адитивне поле версії контракту не змінює"
    for model in (ModuleScoreOut, AccessibilitySnapshotOut):
        schema = model.model_json_schema()
        options = schema["properties"]["withheld_reason"]["anyOf"]
        assert {v for option in options for v in option.get("enum", [])} == {
            EXCLUDED,
            NOT_MEASURED,
        }
        assert {"type": "null"} in options
        assert "withheld_reason" not in schema.get("required", [])

    old = ModuleScoreOut.model_validate(
        {
            "module": "seo",
            "score": 50,
            "band": "poor",
            "weight": 0.26,
            "issues_count": 1,
            "excluded": False,
            "partial": False,
        }
    )
    assert old.withheld_reason is None


# ── збережений звіт: правда виводиться при показі, рядок не змінюється ────


@dataclass
class StoredTarget:
    """Рядок `audit_targets` рівно з тими полями, які читає `report_service`."""

    url: str = "https://example.com"
    origin: str = "https://example.com"
    position: int = 0
    status: str = AuditStatus.COMPLETED.value
    score_overall: int | None = 66
    scores: dict[str, int] = field(
        default_factory=lambda: {
            "performance": 88,
            "seo": 42,
            "ai_ready": 73,
            "llm_visibility": 58,
            "tech": 69,
            "accessibility": 92,
        }
    )
    degraded: list[dict[str, Any]] = field(default_factory=list)
    skipped_modules: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
    versions: dict[str, Any] = field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    issues: list[Any] = field(default_factory=list)
    pages: list[Any] = field(default_factory=list)


@dataclass
class StoredAudit:
    targets: list[StoredTarget]
    id: uuid.UUID = AUDIT_ID
    created_at: datetime = datetime(2026, 8, 21, 9, 0, tzinfo=UTC)
    started_at: datetime | None = None
    finished_at: datetime | None = None


def _persisted(target: StoredTarget) -> bytes:
    stored = {
        "status": target.status,
        "score_overall": target.score_overall,
        "scores": target.scores,
        "degraded": target.degraded,
        "skipped_modules": target.skipped_modules,
    }
    return json.dumps(stored, sort_keys=True, ensure_ascii=False).encode("utf-8")


def _stored_web(target: StoredTarget):
    from app.services.report_service import source_from_audit

    document = build_report(source_from_audit(StoredAudit(targets=[target])), Locale.EN)
    return to_web(
        document,
        audit_id=AUDIT_ID,
        site_id=SITE_ID,
        status=target.status,
        finished_at=None,
        fallback_locale="en",
    )


def test_e09_f6_a_stored_report_derives_partial_from_its_degradation():
    """Збережений аудит із вимкненим шаром казав `partial: false` поруч із
    приміткою про неповні дані. Прапорець виводиться при показі з тієї самої
    деградації: рядок не мігрується, бали не перераховуються.
    """
    from app.report.i18n import t

    target = StoredTarget(
        degraded=[
            {
                "scope": "llm",
                "kind": "layer_disabled",
                "reason": "семантичного аналізу не було: семантичний аналіз вимкнено",
                "affected_modules": ["llm_visibility"],
            }
        ]
    )
    before = _persisted(target)
    # Старе правило бачило лише `partial_data` — у цьому рядку йому нема з чого.
    assert all(row["kind"] != DegradationKind.PARTIAL_DATA.value for row in target.degraded)

    result = _stored_web(target)

    llm = next(m for m in result.modules if m.module is Module.LLM_VISIBILITY)
    assert (llm.score, llm.excluded, llm.partial, llm.withheld_reason) == (58, False, True, None)
    (gap,) = [g for g in result.missing_data if g.scope == "llm"]
    assert gap.note == t("missing_note_partial", Locale.EN)
    assert result.status is AuditStatus.COMPLETED
    assert result.overall_score == 66
    assert {m.module.value: m.score for m in result.modules} == {
        k: v for k, v in target.scores.items() if k != Module.ACCESSIBILITY.value
    }
    assert _persisted(target) == before, "збережений рядок не змінився"


def test_a_stored_filtered_report_tells_excluded_from_not_measured():
    """Збережений аудит без швидкості: причини відновлюються з рядка.

    `reason_key` у збережених деградаціях немає — лише вид, scope і модулі, —
    і цього досить, щоб розрізнити «вимкнено клієнтом» і «не виміряно».
    """
    target = StoredTarget(
        score_overall=58,
        scores={"seo": 42, "ai_ready": 73, "llm_visibility": 58, "tech": 69},
        skipped_modules=["accessibility", "performance"],
        degraded=[
            {
                "scope": "performance",
                "kind": "module_excluded",
                "reason": "модуль вимкнено в опціях аудиту",
                "affected_modules": ["performance"],
            },
            {
                "scope": "accessibility",
                "kind": "partial_data",
                "reason": "доступність не виміряно: вимірювання швидкості виключено",
                "affected_modules": ["accessibility"],
            },
        ],
    )
    before = _persisted(target)

    payload = _stored_web(target).model_dump(mode="json")

    assert _module(payload, Module.PERFORMANCE)["withheld_reason"] == EXCLUDED
    assert payload["accessibility"]["withheld_reason"] == NOT_MEASURED
    assert payload["accessibility"]["counts_toward_overall"] is False
    assert payload["status"] == AuditStatus.COMPLETED.value
    assert _persisted(target) == before


def test_an_old_exclusion_row_without_modules_still_reads_as_excluded():
    """Виключення завжди називає модуль у `scope`; рядок без модулів — теж виключення."""
    target = StoredTarget(
        scores={"seo": 42, "ai_ready": 73, "llm_visibility": 58, "tech": 69, "accessibility": 92},
        skipped_modules=["performance"],
        degraded=[
            {"scope": "performance", "kind": "module_excluded", "reason": "вимкнено"}
        ],
    )

    payload = _stored_web(target).model_dump(mode="json")

    assert _module(payload, Module.PERFORMANCE)["withheld_reason"] == EXCLUDED


# ── G2.1: швидкість, яку просили під фільтром, але не виміряли ────────────


def test_a_stored_filtered_report_names_unmeasured_performance_as_not_measured():
    """Фільтр лишив швидкість, провайдер не відповів, власних вимірів немає.

    Швидкість просили, тож «вимкнено клієнтом» тут неправда: причина — не
    виміряно, і прогалину пояснює одна деградація швидкості. Рядок
    збереженого аудиту не змінюється.
    """
    target = StoredTarget(
        status=AuditStatus.PARTIAL.value,
        score_overall=None,
        scores={"ai_ready": 73, "llm_visibility": 58, "tech": 69},
        skipped_modules=["accessibility", "performance", "seo"],
        degraded=[
            {
                "scope": "seo",
                "kind": "module_excluded",
                "reason": "модуль вимкнено в опціях аудиту",
                "affected_modules": ["seo"],
            },
            {
                "scope": "performance",
                "kind": "provider_unavailable",
                "reason": "провайдер не повернув метрики: HTTP 429",
                "affected_modules": ["performance"],
            },
        ],
    )
    before = _persisted(target)

    payload = _stored_web(target).model_dump(mode="json")

    speed = _module(payload, Module.PERFORMANCE)
    assert (speed["score"], speed["excluded"], speed["withheld_reason"]) == (
        None,
        True,
        NOT_MEASURED,
    )
    assert speed["weight"] == 0.0
    assert _module(payload, Module.SEO)["withheld_reason"] == EXCLUDED
    assert payload["accessibility"]["withheld_reason"] == NOT_MEASURED
    assert [g["scope"] for g in payload["missing_data"]] == ["seo", "performance"]
    assert payload["overall_score"] is None
    assert _persisted(target) == before


def test_a_filtered_report_keeps_a_partially_measured_performance_score():
    """Без Core Web Vitals, але з часом відповіді сервера: бал є й позначений неповним."""
    from app.report.i18n import t

    result = web(
        source(
            skipped={Module.SEO},
            scores=_without(Module.SEO),
            partial={Module.PERFORMANCE},
            degraded=[
                Degradation(
                    "seo",
                    DegradationKind.MODULE_EXCLUDED,
                    "модуль вимкнено в опціях аудиту",
                    [Module.SEO],
                ),
                Degradation(
                    "performance",
                    DegradationKind.PARTIAL_DATA,
                    "Core Web Vitals не виміряно (HTTP 429)",
                    [Module.PERFORMANCE],
                ),
            ],
        )
    )

    speed = next(m for m in result.modules if m.module is Module.PERFORMANCE)
    assert (speed.score, speed.excluded, speed.partial, speed.withheld_reason) == (
        50,
        False,
        True,
        None,
    )
    (gap,) = [g for g in result.missing_data if g.scope == "performance"]
    assert gap.note == t("missing_note_partial", Locale.EN)
