"""Матеріал, якого базовий звіт для власника не має і мати не може.

Базовий звіт — чистий Python: смужки, наслідки з каталогу, жодного
виклику моделі. Він працює завжди, зокрема без ключа, і саме тому
лишається базовим, а не запасним варіантом.

Розширення додає рівно те, чого шаблон не вміє:

- як штучний інтелект описує цей бізнес сьогодні — не наш переказ, а
  те, що модель зрозуміла з самого сайту;
- переказ кожної знахідки словами про цей конкретний бізнес: каталог
  пише про проблему взагалі, бо пише її один раз на всіх.

Нових знахідок тут не зʼявляється. Модель отримує список того, що вже
доведено чеками, і переказує його — інакше у звіті був би факт без
доказу, а такий звіт перестає бути аудитом.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.audit.llm import get_analyst
from app.report.types import ReportDocument

# Стільки ж проблем, скільки показує базовий звіт: переказувати те, чого
# в документі немає, немає сенсу.
MAX_NOTES = 6

# Наказові форми, з яких починається порада. Промпт її забороняє, але
# промпт — не гарантія, а порада «що зробити» — це те, що продається:
# у звіті вона віддає товар безкоштовно.
#
# Перевіряємо лише початок речення: слово «додайте» всередині фрази може
# бути частиною опису проблеми. Помилка тут коштує одного курсивного
# рядка, протікання — усієї розмови з клієнтом, тож фільтр свідомо
# суворіший, ніж потрібно.
_IMPERATIVES = frozenset({
    "додайте", "поставте", "напишіть", "вкажіть", "виправте", "зробіть",
    "налаштуйте", "опублікуйте", "перевірте", "замініть", "видаліть",
    "увімкніть", "дозвольте", "скоротіть", "розмістіть", "оновіть",
    "add", "put", "write", "fix", "set", "make", "publish", "check",
    "replace", "remove", "enable", "allow", "use", "ensure", "create",
})

_SENTENCE_END = ".!?…"


def looks_like_advice(text: str) -> bool:
    """Чи починається бодай одне речення з наказу."""
    sentence_start = True
    for word in text.replace("\n", " ").split():
        if sentence_start and word.strip("«\"'(-").lower().strip(",:;") in _IMPERATIVES:
            return True
        sentence_start = word.endswith(tuple(_SENTENCE_END))
    return False


@dataclass(slots=True)
class OwnerExtras:
    """None замість цього обʼєкта означає базовий режим — не збій."""

    requested: bool = False
    analysed: bool = False
    error: str | None = None
    opening: str = ""
    ai_view: str = ""
    notes: dict[str, str] = field(default_factory=dict)

    def note_for(self, key: str) -> str:
        return self.notes.get(key, "")


def brief_from_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    raw = evidence.get("site_brief")
    return raw if isinstance(raw, dict) else {}


def _business_line(brief: dict[str, Any]) -> str:
    """Одним рядком: чим компанія займається, за версією самої моделі."""
    if not brief.get("analysed"):
        return ""
    parts = [str(brief.get(key, "")) for key in ("name", "tagline", "description")]
    return " — ".join(p for p in parts if p)


def ai_view_of(brief: dict[str, Any]) -> str:
    """Як модель описує цей бізнес. Береться зі збереженого знімка:
    за нього вже заплачено під час аудиту, другий виклик тут зайвий."""
    if not brief.get("analysed"):
        return ""
    description = str(brief.get("description", "")).strip()
    return description or str(brief.get("tagline", "")).strip()


async def build_owner_extras(
    report: ReportDocument,
    *,
    model: str | None = None,
    enabled: bool | None = None,
) -> OwnerExtras:
    """Один виклик моделі на документ. Помилка не валить звіт: розділ
    каже, чому його немає, і решта документа рендериться як завжди."""
    brief = brief_from_evidence(report.evidence)
    extras = OwnerExtras(requested=True, ai_view=ai_view_of(brief))

    problems = [
        (rec.msg, rec.consequence)
        for rec in report.recommendations
        if rec.consequence
    ][:MAX_NOTES]
    if not problems:
        extras.analysed = True
        return extras

    analyst = get_analyst(enabled, model)
    written = await analyst.owner_notes(
        _business_line(brief), report.overall_band, problems
    )
    close = getattr(analyst, "aclose", None)
    if close is not None:
        await close()

    extras.analysed = written.analysed
    extras.error = written.error
    extras.opening = written.opening
    # Ключі, яких ми не давали, відкидаємо тут, а не в провайдері: інваріант
    # «знахідка лише з доказом» має триматися незалежно від того, хто саме
    # відповів. Провайдер, який колись повернув би зайвий пункт, додав би у
    # звіт проблему, якої не знайшов жоден чек.
    known = {key for key, _ in problems}
    extras.notes = {
        k: v
        for k, v in written.notes.items()
        if k in known and v and not looks_like_advice(v)
    }
    if looks_like_advice(extras.opening):
        extras.opening = ""
    return extras


__all__ = [
    "MAX_NOTES",
    "OwnerExtras",
    "ai_view_of",
    "brief_from_evidence",
    "build_owner_extras",
    "looks_like_advice",
]
