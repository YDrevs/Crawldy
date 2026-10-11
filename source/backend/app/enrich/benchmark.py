"""Оцінка збагачення: маніфест, прогін, поля для розбору.

Готове до роботи, але жодного платного батча не запускає саме: живий
прогін — окреме явне рішення людини (`--live` у `scripts/bench_enrich.py`).
За замовчуванням харнес іде в скриптований провайдер: конвеєр той самий,
рахунок нульовий.

## Що саме тут міряється

Якість письма — найменш цікаве. Вихід, який гарно звучить і вводить
непідтверджену проблему, — це ПРОВАЛ, і саме тому автоматична частина
рахує заземленість, а не стиль:

- `unknown_refs` / `hallucinated_findings` — посилання поза входом;
- `coverage` — яку частку знахідок узагалі охоплено;
- `duplicate_reduction` — скільки симптомів згорнулось у причини;
- `unsupported_claims` — обіцянки, яких ми не міряли (години, гроші,
  гарантії трафіку й позицій), знайдені за словником;
- `stability` — той самий вхід двічі: чи однаковий результат.

Людські поля (`plausibility`, `usefulness`, `ordering_usefulness`)
лишаються порожніми до перегляду очима — вигадувати їх автоматично
означало б рахувати власну думку за вимірювання.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from app.enrich.contracts import TaskType

# Слова, якими вихід обіцяє те, чого ми не міряли. Промпти це прямо
# забороняють, але промпт — не гарантія, і бенчмарк мусить рахувати
# порушення, а не вірити на слово.
_MONEY_PATTERN = r"[$€£]\s*\d[\d.,]*"
_DURATION_PATTERN = r"\b\d+\s*(?:hours?|hrs?|days?|man-?hours?)\b"
_GUARANTEE_PATTERN = r"\bguarantee(?:d|s)?\b"
# Величини, які модель могла ПЕРЕКАЗАТИ з поданого сайту: сума, строк
# чи гарантія, яка вже є у вході, — це цитата, а не вигадка.
_SOURCE_GROUNDABLE = (_MONEY_PATTERN, _DURATION_PATTERN, _GUARANTEE_PATTERN)

# Обіцянки про наслідки НАШОЇ роботи. Джерелом не виправдовуються
# ніколи: що б сайт не гарантував собі, зростання трафіку чи позицій
# наш звіт не міряв, і сказати такого не можна навіть цитуючи.
_NEVER_GROUNDED = (
    r"\b\d+\s*%\s*(?:more|increase|growth|uplift|traffic)\b",
    r"\bwill rank\b",
    r"\bwill increase\b",
    r"\bguarantee(?:d|s)?\s+(?:rankings?|traffic|results?|growth|visibility)\b",
)

_UNSUPPORTED_PATTERNS = (*_SOURCE_GROUNDABLE, *_NEVER_GROUNDED)


@dataclass(slots=True)
class CaseResult:
    """Один сайт × одна задача: що виміряно машиною і що лишається людині."""

    case: str
    task: TaskType
    status: str
    provider: str = ""
    model: str = ""
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None

    # ── заземленість: рахується автоматично ───────────────────────────
    input_findings: int = 0
    referenced_findings: int = 0
    unknown_refs: list[str] = field(default_factory=list)
    coverage: float = 0.0
    groups: int = 0
    duplicate_reduction: float = 0.0
    cause_confidence: dict[str, int] = field(default_factory=dict)
    lowered_causal_basis: int = 0
    unsupported_claims: list[str] = field(default_factory=list)
    validation_error: str | None = None
    stable: bool | None = None

    # ── судження: заповнює людина під час перегляду ───────────────────
    #
    # Порівнюючи моделі, ці поля важать більше за машинні: довша чи
    # впевненіша проза не є кращою відповіддю, і автоматично це не
    # виміряти. Дешева модель, яка правильно каже «причина невідома»,
    # краща за сильну, що вигадала причину.
    plausibility: int | None = None
    usefulness: int | None = None
    ordering_usefulness: int | None = None
    # Специфічні для порівняння моделей (v2):
    cluster_quality: str = ""  # strong | useful | weak | incorrect
    cause_discipline: str = ""  # disciplined | overreaching | over-hedged
    coverage_respect: str = ""  # respected | overreached | n/a
    generic_restatement: str = ""  # none | some | mostly
    reviewer_note: str = ""

    def to_json(self) -> dict[str, Any]:
        data = asdict(self)
        data["task"] = self.task.value
        return data


def unsupported_claims(text: str, source: str = "") -> list[str]:
    """Обіцянки, яких ми не міряли. Ціни самого клієнта — не обіцянка.

    Пілот позначив `$0` і `$1` у розумінні linear.app як безпідставні
    твердження. Це були тарифи Linear, процитовані з їхньої ж сторінки
    цін, яка лежала у вході задачі. Переказ прайсу клієнта — заземлена
    цитата, а не вигаданий кошторис.

    Той самий клас повторився на живому порівнянні: Sonnet написав, що
    головна сторінка представляє «its guarantees», і детектор позначив
    слово. Але rightpricerooter.com справді дає 25-річну гарантію на
    великі роботи — переказ чужої гарантії є прямим обовʼязком задачі
    про розуміння сайту.

    Тому величини, які можна процитувати з входу (суми, строки,
    гарантії), звіряються з поданим текстом: є в джерелі — заземлені,
    немає — вигадані. Правило проти вигаданих сум від цього не слабшає.

    Окремо стоять обіцянки про наслідки НАШОЇ роботи — трафік, позиції,
    «гарантований результат». Їх джерело не виправдовує ніколи.
    """
    found: list[str] = []
    for pattern in _UNSUPPORTED_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            hit = match.group(0)
            if pattern in _SOURCE_GROUNDABLE and _grounded_in(hit, source, pattern):
                continue
            found.append(hit)
    return found


def _grounded_in(hit: str, source: str, pattern: str = "") -> bool:
    """Чи трапляється ця величина в поданому вхідному тексті.

    Числа звіряються ТОЧНО: «12 hours» і «24 hours» — різні твердження,
    і послаблення тут пропустило б вигаданий кошторис поруч зі згадкою
    цілодобової роботи. Пробіли ігноруються, бо «$ 10» і «$10» — те саме
    число.

    Слово звіряється за основою: сайт пише «we guarantee to be honest»,
    модель переказує це як «its guarantees». Вимагати збігу словоформи
    означало б назвати вигадкою звичайний переказ — саме це й сталося з
    Sonnet на живому порівнянні.
    """
    if not source:
        return False
    if pattern == _GUARANTEE_PATTERN:
        return "guarantee" in source.lower()
    squeeze = re.sub(r"\s+", "", hit)
    return squeeze in re.sub(r"\s+", "", source)


def score_case(
    case: str,
    task: TaskType,
    payload: dict[str, Any],
    result: dict[str, Any] | None,
    status: str,
) -> CaseResult:
    """Автоматична частина оцінки. Судження лишаються None."""
    known = {f["ref"] for f in payload.get("findings", [])}
    out = CaseResult(case=case, task=task, status=status, input_findings=len(known))
    if not result:
        return out

    refs: list[str] = []
    if task is TaskType.ROOT_CAUSE_GROUPING:
        groups = result.get("groups", [])
        out.groups = len(groups)
        for group in groups:
            refs += list(group.get("finding_refs", []))
        refs += list(result.get("ungrouped_refs", []))
        grouped = sum(len(g.get("finding_refs", [])) for g in groups)
        # Скільки симптомів згорнулось: 17 знахідок у 2 групах — це 15
        # рядків, яких клієнт не читатиме поодинці.
        out.duplicate_reduction = (
            (grouped - len(groups)) / grouped if grouped else 0.0
        )
        # Розподіл впевненості в причині — головна метрика v2. Чесне
        # «unknown» тут не провал, а правильна відповідь, тож рахуємо
        # його поруч із рештою, а не як дефект.
        out.cause_confidence = {
            level: sum(1 for g in groups if g.get("cause_confidence") == level)
            for level in ("supported", "likely", "possible", "unknown")
        }
    elif task is TaskType.REMEDIATION_PLAN:
        for step in result.get("steps", []):
            refs += list(step.get("finding_refs", []))
        # Скільки разів валідація мусила знизити причинну заявку кроку.
        out.lowered_causal_basis = int(result.get("lowered_causal_basis") or 0)
    elif task is TaskType.SITE_UNDERSTANDING:
        out.coverage = 1.0 if result.get("source_urls") else 0.0

    if known:
        out.referenced_findings = len(set(refs) & known)
        out.coverage = out.referenced_findings / len(known)
    out.unknown_refs = sorted({r for r in refs if r not in known})

    import json

    out.unsupported_claims = unsupported_claims(
        json.dumps(result, ensure_ascii=False),
        # Джерело — поданий моделі вхід: сума, що вже була в ньому,
        # процитована, а не вигадана.
        json.dumps(payload, ensure_ascii=False),
    )
    return out


# Корпус бенчмарку описується маніфестом (JSON), а не типом у коді:
# знімки фіксовані навмисно. Два прогони по мережі — це два різні сайти,
# і різницю не можна приписати моделі; та сама пастка, що вже спіймана в
# калібруванні детекторів.
DEFAULT_TASKS: tuple[TaskType, ...] = (
    TaskType.SITE_UNDERSTANDING,
    TaskType.ROOT_CAUSE_GROUPING,
    TaskType.REMEDIATION_PLAN,
)
