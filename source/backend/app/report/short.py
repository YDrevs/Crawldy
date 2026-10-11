"""Безкоштовний вигляд звіту: масштаб проблеми, а не діагноз.

Проєкція над готовим `ReportDocument`, а не окремий аудит. Другого
краулу немає: безкоштовне й платне — два вигляди одного виконаного
виміру.

## Межа — продуктове рішення, і тримає її схема

Безкоштовний результат відповідає на «чи є проблема і наскільки вона
серйозна». Платний — на «що саме, де, чому і як виправити». Тому тут
**структурно немає** полів для шести вимірів, знахідок, доказів, адрес
сторінок, технічних причин і порад: маршрут не може віддати те, чого
не існує в DTO. Ховати поля на фронтенді було б не межею, а шторкою.

Прецедент уже в продукті: нетехнічна частина Word-звіту показує
власнику наслідок і серйозність — без жодної поради, бо «порада "що
зробити" — це і є те, що продається» (`docx_owner.py`).

## Три головні проблеми — рівнем наслідку

Текст береться з `consequence` — єдиного поля каталогу, яке за
побудовою не містить жаргону (окремий тест) і не обіцяє невиміряного
(ще один). Ні `issue_key`, ні модуль, ні сторінки, ні «знайдено/
очікували» назовні не виходять. Вибір — наявним порядком рекомендацій
продукту; нового ранжування тут немає.

## Чесність не за paywall

Порожній бал лишається порожнім, а покриття називається просто:
`full` / `partial` / `insufficient`. Технічні причини прогалин
(коди відповіді, таймаути провайдерів) — діагностика, і вона за межею;
сам факт прогалини — ні, і він показується завжди.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.audit.scoring import SEVERITY_MULTIPLIER
from app.report.coverage import coverage_level
from app.report.types import Recommendation, ReportDocument

#: Скільки головних проблем показує безкоштовний вигляд.
TOP_PROBLEMS = 3

#: Серйозність → бізнесова вага для розподілу. critical зливається з
#: high, info — з low: власнику важлива шкала «терміново / важливо /
#: дрібниці», а не пʼять внутрішніх градацій детектора.
_SEVERITY_FOLD = {
    "critical": "high",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "info": "low",
}

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True, slots=True)
class FreeProblem:
    """Одна з головних проблем — мовою наслідку, без діагнозу.

    `problem` і `why` — перше речення `consequence` і решта: каталог
    пише наслідок саме так — твердження, потім пояснення. Коли речення
    одне, `why` порожній, і картка складається з самого твердження.

    `impact_points` — справжня ізольована дельта з рушія скорингу, не
    оцінка й не сума. Її не можна додавати до сусідніх: кожна міряна
    окремо проти того самого базового бала, і стеля на `issue_key`
    робить ефект нелінійним.

    Мітки терміновості тут більше немає. Вона стояла бейджем на картці
    поруч із лічильниками серйозності — двома словниками про одне й те
    саме, — і читалась як суперечність: «Терміново» опинялося нижче за
    два «Важливо», бо порядок брався не зі смуги. Число, яке видно,
    пояснює порядок саме́.
    """

    problem: str
    why: str
    impact_points: int
    #: Приріст округлюється до нуля, або загального бала немає взагалі.
    #: Тоді число не показується — «+0» каже, що дія марна, а це неправда.
    floored: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "problem": self.problem,
            "why": self.why,
            "impact_points": self.impact_points,
            "floored": self.floored,
        }


@dataclass(frozen=True, slots=True)
class FreeCoverage:
    """Покриття крупним планом: чи вистачило прочитаного.

    Без переліку адрес, що не відповіли, і без технічних причин — це
    діагностика. Рівень чесно каже головне: `insufficient` означає, що
    впевненої оцінки немає і бал порожній.
    """

    pages_read: int | None
    pages_known: int | None
    level: str  # "full" | "partial" | "insufficient"
    #: Скільки знайдених адрес не відповіли. Окреме число, а не різниця
    #: `known - read`: у знаменнику є й ті, до яких краул не дійшов за
    #: бюджетом, і назвати їх невдачами означало б звинуватити сайт у
    #: нашій межі.
    pages_failed: int = 0

    def to_json(self) -> dict[str, Any]:
        return {
            "pages_read": self.pages_read,
            "pages_known": self.pages_known,
            "level": self.level,
            "pages_failed": self.pages_failed,
        }


@dataclass(frozen=True, slots=True)
class FreeAuditResult:
    """Безкоштовна проєкція. Окремий тип, а не повний звіт із дірками.

    Клієнт без оплати не отримує прихованих діагностичних полів у JSON
    просто тому, що їх тут нема. Межу тримає сервер, фронтенд — лише
    подача.
    """

    audit_id: str
    url: str
    origin: str
    status: str
    generated_at: datetime
    overall_score: int | None
    overall_band: str
    issues_total: int
    severity: dict[str, int]  # {"high": n, "medium": n, "low": n}
    coverage: FreeCoverage
    problems: list[FreeProblem] = field(default_factory=list)
    unlocked: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "url": self.url,
            "origin": self.origin,
            "status": self.status,
            "generated_at": self.generated_at.isoformat(),
            "overall_score": self.overall_score,
            "overall_band": self.overall_band,
            "issues_total": self.issues_total,
            "severity": dict(self.severity),
            "coverage": self.coverage.to_json(),
            "problems": [p.to_json() for p in self.problems],
            "unlocked": self.unlocked,
        }


def to_short(document: ReportDocument, *, audit_id: str, unlocked: bool = False) -> FreeAuditResult:
    """Безкоштовна проєкція готового документа.

    `unlocked` не змінює вміст: повний вигляд віддається іншим маршрутом
    і іншою схемою. Прапорець лише каже інтерфейсу, чи є що відкривати.
    """
    summary = document.summary or {}
    by_severity: dict[str, int] = dict(summary.get("by_severity") or {})
    folded = {"high": 0, "medium": 0, "low": 0}
    for severity, count in by_severity.items():
        folded[_SEVERITY_FOLD.get(severity, "low")] += int(count)

    return FreeAuditResult(
        audit_id=audit_id,
        url=str(document.target.get("url") or document.audit.get("url") or ""),
        origin=str(document.target.get("origin") or document.audit.get("origin") or ""),
        status=str(document.audit.get("status") or ""),
        generated_at=document.generated_at,
        overall_score=document.overall_score,
        overall_band=document.overall_band,
        issues_total=int(summary.get("issues_total") or len(document.issues)),
        severity=folded,
        coverage=_coverage(document),
        problems=_top_problems(document),
        unlocked=unlocked,
    )


def _coverage(document: ReportDocument) -> FreeCoverage:
    """Рівень береться зі спільного модуля: те саме питання — одна відповідь.

    Технічні причини прогалин сюди все одно не потрапляють — безкоштовний
    результат показує лише факт, а не діагностику.
    """
    crawl = (document.summary or {}).get("coverage") or {}
    return FreeCoverage(
        pages_read=crawl.get("pages_read"),
        pages_known=crawl.get("pages_known"),
        level=coverage_level(document),
        pages_failed=int(crawl.get("pages_failed") or 0),
    )


def top_recommendations(document: ReportDocument) -> list[Recommendation]:
    """Три найважливіші проблеми — вибір і порядок, без жодного тексту.

    Винесено окремо саме тому, що порядок треба перевіряти: він мусить
    бути однаковий усіма мовами, а порівнювати його можна лише за
    ідентифікаторами, яких у публічному контракті немає й не буде.

    ## Вибір

    Береться перша рекомендація кожного модуля, поки не набереться три:
    три знахідки однієї теми (наприклад, три метрики швидкості) сказали б
    власнику менше, ніж три різні. Модуль назовні не виходить — він лише
    розводить кандидатів. Замінити вибір чистим впливом не можна: той
    структурно виносить дешеву косметику над критичним, і ми це вже
    проходили з Twitter-карткою при Lighthouse 25.

    ## Порядок

    Ключ сортування не містить жодного локалізованого рядка. Раніше
    останнім кроком стояло перше речення `consequence`, тобто текст
    мовою сторінки, — і той самий аудит ka-dent.com.ua із двома
    знахідками по −3 показував їх у різному порядку: англійська й
    російська починали з телефонів, решта чотирьох мов — з опису
    сторінки. Одні дані, шість відповідей.

    Тепер ключ такий:

    1. ізольований вплив на бал — спадання;
    2. канонічна вага серйозності — та сама, що в скорингу;
    3. канонічний пріоритет бекенда (`rank`, який уже присвоїв білдер);
    4. `issue_key` як остаточний розвʼязувач.

    Четвертий крок робить порядок повністю визначеним: два різні
    `issue_key` ніколи не дають рівності, тож результат не залежить ані
    від мови, ані від порядку перебору.
    """
    ranked = [r for r in document.recommendations if r.consequence]
    picked = []
    seen_modules = set()
    for rec in ranked:
        if rec.module in seen_modules:
            continue
        seen_modules.add(rec.module)
        picked.append(rec)
        if len(picked) == TOP_PROBLEMS:
            break
    if len(picked) < TOP_PROBLEMS:
        chosen = {r.issue_key for r in picked}
        for rec in ranked:
            if rec.issue_key in chosen:
                continue
            picked.append(rec)
            chosen.add(rec.issue_key)
            if len(picked) == TOP_PROBLEMS:
                break

    picked.sort(key=_stable_order)
    return picked


def _stable_order(rec: Recommendation) -> tuple[int, int, int, str]:
    """Ключ порядку. Жодного локалізованого рядка тут бути не може."""
    return (
        -rec.impact_points,
        # Вага серйозності береться зі скорингу, а не переписується
        # числами поруч: два переліки того самого розійшлися б на першій
        # правці. Мінус — бо більша вага має стояти вище.
        -SEVERITY_MULTIPLIER.get(rec.severity, 0),
        rec.rank,
        rec.issue_key,
    )


def _top_problems(document: ReportDocument) -> list[FreeProblem]:
    """Подання трійки. Вибір і порядок уже зроблені вище."""
    problems = []
    for rec in top_recommendations(document):
        sentences = _SENTENCE_END.split(rec.consequence.strip(), maxsplit=1)
        problems.append(
            FreeProblem(
                problem=sentences[0],
                why=sentences[1] if len(sentences) > 1 else "",
                impact_points=rec.impact_points,
                floored=rec.floored,
            )
        )
    return problems
