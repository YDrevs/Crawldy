"""Класифікація невдач аудиту.

Від класу залежить, чи повертається квота, тож він мусить визначатися
типом винятку, а не розбором тексту. Зіставляти рядок мовою — рівно та
пастка, від якої проєкт уже відмовився в деградаціях: повідомлення
переписують, і правило тихо перестає діяти.
"""

from __future__ import annotations

import asyncio

import httpx

from app.audit.fetcher import SiteUnreachable, UnsafeUrlError
from app.core.run_enums import FailureClass

# Винятки, які означають «сайт клієнта не відповів». Квота за них не
# повертається: краул відбувся, відповідь чесна, робота зроблена.
_SITE_PROBLEMS: tuple[type[BaseException], ...] = (
    SiteUnreachable,
    UnsafeUrlError,
    httpx.TransportError,
    httpx.TooManyRedirects,
)


def classify(error: BaseException) -> FailureClass:
    """Чому аудит не дав результату.

    Усе, що не впізнано, — внутрішня помилка. Дефолт навмисно на нашу
    користь навпаки: невідомий виняток означає, що ми не розібралися, і
    платити за це має не клієнт.
    """
    if isinstance(error, asyncio.CancelledError):
        return FailureClass.CANCELLED
    if isinstance(error, _SITE_PROBLEMS):
        return FailureClass.SITE_UNREACHABLE
    if isinstance(error, TimeoutError):
        # Наш власний таймаут на весь аудит. Сайт тут ні до чого:
        # ми не встигли.
        return FailureClass.INTERNAL_ERROR
    return FailureClass.INTERNAL_ERROR


__all__ = ["FailureClass", "classify"]
