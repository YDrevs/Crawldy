"""Структура звіту. Джерело для JSON і для docx — одне й те саме."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.audit.enums import AuditStatus, Confidence, Effort, Module, Severity
from app.audit.types import Degradation, Issue
from app.report.passed import PassedCheck

REPORT_VERSION = "1.0"

# Модуль performance у звіті називається speed: клієнтові зрозуміліше,
# а всередині лишається performance. Мапа тут — єдине місце перекладу.
MODULE_FIELD: dict[Module, str] = {
    Module.PERFORMANCE: "speed_score",
    Module.SEO: "seo_score",
    Module.AI_READY: "ai_ready_score",
    Module.LLM_VISIBILITY: "llm_visibility_score",
    Module.TECH: "tech_score",
    Module.ACCESSIBILITY: "accessibility_score",
}

# Модулі, які клієнт бачить не балом, а знімком. Доступність ми міряємо
# на ОДНІЙ сторінці одним зовнішнім інструментом, і бал 0..100 поруч із
# балами, порахованими по всьому сайту, читається як рівне з рівним. Це
# рішення про представлення: вклад модуля в загальний бал не змінюється.
SNAPSHOT_MODULES: frozenset[Module] = frozenset({Module.ACCESSIBILITY})

# Правило Lighthouse -> наш чек, який говорить про ТУ САМУ ваду. Мапа
# потрібна, щоб послатися, а не щоб приховати: посилання ставиться лише
# тоді, коли відповідна знахідка справді є в цьому аудиті. Стверджувати
# покриття «за мапою» не можна — на 150 сайтах відповідник спрацював на
# тій самій сторінці лише в 24.7% випадків для `heading-order`.
EQUIVALENT_CHECK: dict[str, str] = {
    "image-alt": "seo.image_alt",
    "html-has-lang": "ai.lang",
    "heading-order": "seo.heading_hierarchy",
}

EFFORT_COST: dict[Effort, float] = {Effort.LOW: 1.0, Effort.MEDIUM: 2.0, Effort.HIGH: 4.0}

NEXT_ACTIONS_LIMIT = 7


@dataclass(slots=True)
class ReportSource:
    """Вхід для білдера. Збирається або з AuditOutcome, або з рядків БД."""

    url: str
    entry_url: str
    origin: str
    overall: int | None
    scores: dict[str, int]
    issues: list[Issue]
    degraded: list[Degradation]
    skipped_modules: set[Module]
    evidence: dict[str, Any]
    # Чим порахований аудит. Порожньо для аудитів, збережених до того, як
    # ми почали це записувати: вигадувати версію заднім числом означало б
    # зробити їх порівнянними на вигляд, не будучи такими.
    versions: dict[str, Any] = field(default_factory=dict)
    partial_modules: set[Module] = field(default_factory=set)
    pages_crawled: int = 0
    audit_id: uuid.UUID | None = None
    status: AuditStatus = AuditStatus.COMPLETED
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(slots=True)
class ScoreEntry:
    module: Module
    field: str
    score: int
    band: str
    weight: float
    effective_weight: float
    issues_count: int
    excluded: bool
    # Оцінка є, але побудована не на всіх сигналах напряму.
    partial: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "module": self.module.value,
            "field": self.field,
            "score": self.score,
            "band": self.band,
            "weight": self.weight,
            "effective_weight": round(self.effective_weight, 4),
            "issues_count": self.issues_count,
            "excluded": self.excluded,
            "partial": self.partial,
        }


@dataclass(slots=True)
class IssueEntry:
    code: str
    issue_key: str
    msg: str
    module: Module
    severity: Severity
    title: str
    description: str
    recommendation: str
    evidence: dict[str, Any]
    page_url: str | None
    weight: int
    penalty: float

    def to_json(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "issue_key": self.issue_key,
            "msg": self.msg,
            "module": self.module.value,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "recommendation": self.recommendation,
            "evidence": self.evidence,
            "page_url": self.page_url,
            "weight": self.weight,
            "penalty": self.penalty,
        }


@dataclass(slots=True)
class Recommendation:
    """Одна проблема, а не одне входження: 5 сторінок без canonical = 1 пункт."""

    rank: int
    # Стабільний ідентифікатор проблеми — той самий, за яким рахується
    # стеля штрафу. Скоринг і звіт мусять групувати однаково, інакше
    # клієнт бачить два пункти там, де бал бачить один.
    issue_key: str
    msg: str
    code: str
    module: Module
    severity: Severity
    title: str
    problem: str
    action: str
    # Наслідок простою мовою — основа нетехнічної частини звіту.
    consequence: str
    scope: str  # "site" | "page"
    affected_pages: int
    affected_examples: list[str]
    evidence: dict[str, Any]
    impact_points: int
    impact_by_module: dict[str, int]
    effort: Effort
    priority_score: float
    floored: bool
    # Наскільки твердо це стверджується. Рекомендація тверда рівно
    # настільки, наскільки найслабший доказ під нею.
    confidence: Confidence = Confidence.HIGH
    # Наскільки важлива найважливіша зі сторінок, яких це стосується, за
    # версією самого сайту (0..1). Знахідка на головній і на забутій
    # сторінці третього рівня коштують клієнту різного. Порожньо для
    # знахідок про сайт загалом і для аудитів, збережених до графа.
    page_importance: float | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "issue_key": self.issue_key,
            "msg": self.msg,
            "code": self.code,
            "module": self.module.value,
            "severity": self.severity.value,
            "title": self.title,
            "problem": self.problem,
            "action": self.action,
            "consequence": self.consequence,
            "scope": self.scope,
            "affected_pages": self.affected_pages,
            "affected_examples": self.affected_examples,
            "evidence": self.evidence,
            "confidence": self.confidence.value,
            "impact_points": self.impact_points,
            "impact_by_module": self.impact_by_module,
            "effort": self.effort.value,
            "priority_score": round(self.priority_score, 3),
            "page_importance": self.page_importance,
            "floored": self.floored,
        }


@dataclass(slots=True)
class NextAction:
    rank: int
    issue_key: str
    msg: str
    module: Module
    action: str
    why: str
    expected_gain_points: int
    expected_gain: str
    effort: Effort
    affected_pages: int
    evidence_ref: str

    def to_json(self) -> dict[str, Any]:
        return {
            "rank": self.rank,
            "issue_key": self.issue_key,
            "msg": self.msg,
            "module": self.module.value,
            "action": self.action,
            "why": self.why,
            "expected_gain_points": self.expected_gain_points,
            "expected_gain": self.expected_gain,
            "effort": self.effort.value,
            "affected_pages": self.affected_pages,
            "evidence_ref": self.evidence_ref,
        }


@dataclass(slots=True)
class MissingData:
    scope: str
    kind: str
    reason: str
    affects: list[str]
    note: str

    def to_json(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "kind": self.kind,
            "reason": self.reason,
            "affects": self.affects,
            "note": self.note,
        }


@dataclass(slots=True)
class AccessibilityFinding:
    """Одна провалена перевірка Lighthouse у знімку доступності."""

    audit_id: str
    title: str
    impact: str = ""
    # Код нашого чека, який говорить про це саме — і лише якщо він
    # СПРАЦЮВАВ у цьому аудиті. None означає «більше ніде про це не
    # сказано», а не «мапи немає».
    also_reported_as: str | None = None
    also_reported_module: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "title": self.title,
            "impact": self.impact,
            "also_reported_as": self.also_reported_as,
            "also_reported_module": self.also_reported_module,
        }


@dataclass(slots=True)
class AccessibilitySnapshot:
    """Доступність однієї сторінки, а не оцінка сайту.

    Знаменника «з 76» тут немає навмисно: із 76 оголошених перевірок
    рівно 10 — `manual`, їх Lighthouse не виконує ніколи, а ще 0..4 —
    `informative`. Частка «N з 76» занижувала б покриття кожної сторінки
    приблизно на 15% з причини, що сторінки не стосується.
    """

    available: bool
    measured_url: str | None = None
    strategy: str = "mobile"
    applicable: int | None = None
    passed: int | None = None
    failed: int | None = None
    findings: list[AccessibilityFinding] = field(default_factory=list)
    # Бал Lighthouse для ЦІЄЇ сторінки — зовнішній орієнтир, не наш бал.
    lighthouse_score: float | None = None
    # Доступність більше не показується балом, але свою частку загального
    # бала поки зберігає: вклад лишили незмінним до калібрування. Без
    # цього поля видимі ваги сходяться до 90%, і клієнт має право
    # вирішити, що звіт зламаний — або, значно гірше, що цей знімок на
    # його бал не впливає взагалі.
    counts_toward_overall: bool = False
    overall_weight: float | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "counts_toward_overall": self.counts_toward_overall,
            "overall_weight": self.overall_weight,
            "measured_url": self.measured_url,
            "strategy": self.strategy,
            "applicable": self.applicable,
            "passed": self.passed,
            "failed": self.failed,
            "findings": [f.to_json() for f in self.findings],
            "lighthouse_score": self.lighthouse_score,
        }


@dataclass(slots=True)
class ReportDocument:
    locale: str
    generated_at: datetime
    audit: dict[str, Any]
    target: dict[str, Any]
    overall_score: int | None
    overall_band: str
    module_scores: dict[str, int | None]
    scores: list[ScoreEntry]
    summary: dict[str, Any]
    issues: list[IssueEntry]
    recommendations: list[Recommendation]
    next_actions: list[NextAction]
    evidence: dict[str, Any] = field(default_factory=dict)
    # Чим порахований аудит: версії краулера, детекторів, скорингу,
    # конфігурації й моделі. Порожньо для аудитів до того, як ми почали
    # це записувати.
    versions: dict[str, Any] = field(default_factory=dict)
    missing_data: list[MissingData] = field(default_factory=list)
    # Скор, який вийде, якщо виправити все з next_actions. Рахується
    # перерахунком без цих проблем одразу, а не сумою impact_points:
    # їх сумувати не можна, стеля на code і нелінійність шкали роблять
    # суму завищеною, і клієнту обіцяли б неіснуючий приріст.
    potential_score: int | None = None
    # Доступність подається знімком сторінки, а не балом модуля.
    accessibility: AccessibilitySnapshot | None = None
    # Пройдені перевірки: явний доказ успіху, ніколи не тиша чека.
    # Другорядні до проблем; на бали не впливають узагалі.
    passed_checks: list[PassedCheck] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "report_version": REPORT_VERSION,
            "engine_versions": self.versions,
            "locale": self.locale,
            "generated_at": self.generated_at.isoformat(),
            "audit": self.audit,
            "target": self.target,
            "overall_score": self.overall_score,
            "overall_band": self.overall_band,
            "potential_score": self.potential_score,
            **self.module_scores,
            "scores": [s.to_json() for s in self.scores],
            "summary": self.summary,
            "issues": [i.to_json() for i in self.issues],
            "recommendations": [r.to_json() for r in self.recommendations],
            "next_actions": [a.to_json() for a in self.next_actions],
            "accessibility_snapshot": (
                self.accessibility.to_json() if self.accessibility else None
            ),
            "passed_checks": [p.to_json() for p in self.passed_checks],
            "evidence": self.evidence,
            "missing_data": [m.to_json() for m in self.missing_data],
        }
