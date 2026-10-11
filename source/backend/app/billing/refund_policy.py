"""Хто платить за невдалий аудит.

Це продуктова політика, а не властивість двигуна. `FailureClass` — факт
(«сайт не відповів», «зламалося в нас»); рішення, чи повертати за цей
факт гроші, ухвалює бізнес і має право змінити його, не чіпаючи ні
машину станів квоти, ні класифікатор невдач.

Тому політика живе тут, а не в `audit/enums.py`: двигун виробляє факти,
білінг вирішує, що вони означають для рахунку.
"""

from __future__ import annotations

from app.core.config import settings
from app.core.run_enums import FailureClass

# Політика за замовчуванням.
#
# Повертаємо за те, що зламалося в нас або в наших постачальників, і за
# скасування до виконання. Не повертаємо за недоступний чи заблокований
# сайт клієнта: краул відбувся, відповідь чесна, робота зроблена.
#
# Останнє — свідоме продуктове рішення, а не технічна необхідність. Якщо
# завтра виявиться, що клієнти сприймають його як несправедливе, зміна
# коштує рядка в налаштуваннях: ні машина станів, ні класифікатор про це
# не знають.
DEFAULT_REFUNDABLE: frozenset[FailureClass] = frozenset(
    {
        FailureClass.PROVIDER_FAILED,
        FailureClass.INTERNAL_ERROR,
        FailureClass.CANCELLED,
    }
)


def refundable() -> frozenset[FailureClass]:
    """Класи невдач, за які квота повертається просто зараз.

    Налаштування перекриває дефолт цілком, а не доповнює його: часткове
    накладання дає стан, у якому неможливо сказати, яка політика діє.
    Невідома назва класу ігнорується — помилка друку в змінній оточення
    не має мовчки розширювати або звужувати повернення.
    """
    configured = settings.billing_refundable_failures
    if configured is None:
        return DEFAULT_REFUNDABLE
    known = {f.value: f for f in FailureClass}
    return frozenset(known[name] for name in configured if name in known)


def is_refundable(failure: FailureClass | None) -> bool:
    """Успішний аудит (`None`) списується завжди: робота виконана."""
    return failure is not None and failure in refundable()
