"""Машина станів підписки. Чиста: жодного вводу-виводу.

Стани — в `SubscriptionStatus`; тут — переходи між ними й правило, що
недозволений перехід є **відмовою**, а не мовчазним прийняттям. Подія,
яка вимагає неможливого («активувати скасовану»), означає, що ми й
провайдер розійшлися в уявленні про підписку, — і це треба побачити,
а не затерти.

## Семантика станів

| Стан | Що означає | Права |
|---|---|---|
| `INACTIVE` | створена, оплати ще не було | ні |
| `TRIALING` | пробний період | так |
| `ACTIVE` | оплачено, період триває | так |
| `PAST_DUE` | списання не пройшло; грація до `grace_until` | так, до кінця грації |
| `PAUSED` | призупинена за згодою обох сторін | ні |
| `CANCELLED` | завершена; назад дороги немає | ні |

«Скасується наприкінці періоду» — не стан, а прапорець
`cancel_at_period_end`: він ортогональний до активності, і стан-гібрид
подвоїв би таблицю переходів.

`CANCELLED` — поглинальний. Повернення клієнта — це **нова** підписка
з новим рядком, а не воскресіння старої: інакше історія переходів
однієї підписки описувала б два різні життя.
"""

from __future__ import annotations

from app.billing.enums import BillingEventKind, SubscriptionStatus

_S = SubscriptionStatus
_K = BillingEventKind


class InvalidTransition(Exception):
    """Подія вимагає переходу, якого в машині станів немає.

    Це не «зайва подія», а розбіжність між нами й провайдером у питанні,
    у якому стані підписка. Викликач записує подію як невдалу — з текстом
    саме цього винятку, — і хтось живий дивиться, хто з двох помиляється.
    """

    def __init__(self, current: SubscriptionStatus, kind: BillingEventKind) -> None:
        self.current = current
        self.kind = kind
        super().__init__(f"подія «{kind.value}» не застосовна до стану «{current.value}»")


# Що до чого веде: (поточний стан, вид події) → новий стан.
#
# Таблиця, а не if-и: повноту таблиці можна перевірити тестом, повноту
# if-ів — лише оком. Відсутність пари означає InvalidTransition.
TRANSITIONS: dict[tuple[SubscriptionStatus, BillingEventKind], SubscriptionStatus] = {
    # Початок життя. INACTIVE — єдиний вхід; звідки взявся trial,
    # вирішує подія (`with_trial`), а не окремий вид.
    (_S.INACTIVE, _K.SUBSCRIPTION_STARTED): _S.ACTIVE,
    # Пробний період скінчився добре або погано.
    (_S.TRIALING, _K.SUBSCRIPTION_RENEWED): _S.ACTIVE,
    (_S.TRIALING, _K.PAYMENT_FAILED): _S.PAST_DUE,
    (_S.TRIALING, _K.CANCELLATION_SCHEDULED): _S.TRIALING,
    (_S.TRIALING, _K.SUBSCRIPTION_CANCELLED): _S.CANCELLED,
    (_S.TRIALING, _K.PLAN_CHANGED): _S.TRIALING,
    # Оплачене життя.
    (_S.ACTIVE, _K.SUBSCRIPTION_RENEWED): _S.ACTIVE,
    (_S.ACTIVE, _K.PAYMENT_FAILED): _S.PAST_DUE,
    (_S.ACTIVE, _K.CANCELLATION_SCHEDULED): _S.ACTIVE,
    (_S.ACTIVE, _K.SUBSCRIPTION_CANCELLED): _S.CANCELLED,
    (_S.ACTIVE, _K.SUBSCRIPTION_PAUSED): _S.PAUSED,
    (_S.ACTIVE, _K.PLAN_CHANGED): _S.ACTIVE,
    # Грація. Відновлення платежу повертає в ACTIVE; нове невдале
    # списання лишає в PAST_DUE (грація при цьому не подовжується — див.
    # apply: строк ставиться лише при вході в стан).
    (_S.PAST_DUE, _K.PAYMENT_RECOVERED): _S.ACTIVE,
    # Після відновлення частина провайдерів шле renewed, а не recovered:
    # для них успішне списання і є подовженням. Семантично це те саме.
    (_S.PAST_DUE, _K.SUBSCRIPTION_RENEWED): _S.ACTIVE,
    (_S.PAST_DUE, _K.PAYMENT_FAILED): _S.PAST_DUE,
    (_S.PAST_DUE, _K.SUBSCRIPTION_CANCELLED): _S.CANCELLED,
    (_S.PAST_DUE, _K.CANCELLATION_SCHEDULED): _S.PAST_DUE,
    # Пауза.
    (_S.PAUSED, _K.SUBSCRIPTION_RESUMED): _S.ACTIVE,
    (_S.PAUSED, _K.SUBSCRIPTION_CANCELLED): _S.CANCELLED,
    # CANCELLED — поглинальний: жодного рядка з нього немає навмисно.
}

# Види, які твердять «підписка існує», — для них перехід із INACTIVE
# також дозволений: перша ж подія, що дійшла, будує стан. Провайдери не
# гарантують, що started прийде першим, а підписка, яка чекає на
# «правильний порядок», — це клієнт, який заплатив і не отримав.
_ESTABLISHING: frozenset[BillingEventKind] = frozenset(
    {_K.SUBSCRIPTION_RENEWED, _K.PAYMENT_RECOVERED, _K.SUBSCRIPTION_RESUMED}
)


def next_status(
    current: SubscriptionStatus, kind: BillingEventKind, *, with_trial: bool = False
) -> SubscriptionStatus:
    """Куди веде подія. Недозволена — виняток, не мовчання."""
    if kind is _K.SUBSCRIPTION_STARTED and current is _S.INACTIVE and with_trial:
        return _S.TRIALING
    target = TRANSITIONS.get((current, kind))
    if target is None and current is _S.INACTIVE and kind in _ESTABLISHING:
        return _S.ACTIVE
    if target is None:
        raise InvalidTransition(current, kind)
    return target


def is_terminal(status: SubscriptionStatus) -> bool:
    return status is _S.CANCELLED


__all__ = ["TRANSITIONS", "InvalidTransition", "is_terminal", "next_status"]
