"""Скільки сайту ми справді прочитали — один канонічний факт на всіх.

Рівень покриття вже жив у `short.py` для безкоштовного результату. Коли
його знадобилось передавати ще й у шар збагачення, спокуса була написати
другий розрахунок поруч — і тоді два місця відповідали б на те саме
питання, розходячись на першій же правці.

Тому логіка тут, а `short.py` і збирачі входів збагачення її викликають.
Числа беруться з `summary.coverage`, який будує `builder._coverage`;
рівень — з наявності бала й прогалин даних. Нових джерел правди не
зʼявляється.
"""

from __future__ import annotations

from typing import Any

from app.report.types import ReportDocument

# Рівні свідомо крупні: це діагностика для читача, а не класифікація
# причин. `insufficient` означає, що впевненої оцінки немає взагалі.
FULL = "full"
PARTIAL = "partial"
INSUFFICIENT = "insufficient"


def coverage_level(document: ReportDocument) -> str:
    """`full` / `partial` / `insufficient` за наявним станом звіту."""
    if document.overall_score is None:
        return INSUFFICIENT
    if any(m.scope.split(".")[0] != "llm" for m in document.missing_data):
        # Прогалина в даних, крім свідомо вимкненого семантичного шару.
        return PARTIAL
    return FULL


def coverage_facts(document: ReportDocument) -> dict[str, Any]:
    """Покриття у вигляді, придатному для передавання далі.

    `pages_unread` рахується явно, а не лишається читачеві: різниця між
    «знаємо 10 адрес» і «прочитали 3» — це рівно те, про що твердження
    не можна робити, і вона має бути названа числом.
    """
    crawl = (document.summary or {}).get("coverage") or {}
    known = crawl.get("pages_known")
    read = crawl.get("pages_read")
    unread = None
    if isinstance(known, int) and isinstance(read, int):
        unread = max(known - read, 0)
    return {
        "level": coverage_level(document),
        "pages_read": read,
        "pages_known": known,
        "pages_failed": crawl.get("pages_failed"),
        "pages_unread": unread,
        "share": crawl.get("share"),
    }


__all__ = ["FULL", "INSUFFICIENT", "PARTIAL", "coverage_facts", "coverage_level"]
