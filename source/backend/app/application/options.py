"""Опції: що просили, що дозволено, і чим вони відрізняються.

Обрізання правами тарифу лишається мовчазним для *виконання* — аудит
робиться, а не відхиляється, — але перестає бути мовчазним для
*відповіді*. Це різні речі, і плутати їх дорого: клієнт просив 100
сторінок, отримав 10, і через місяць ні він, ні ми не можемо пояснити,
чому звіт неповний.

Різниця не зберігається третім полем. Вона обчислюється з пари
«requested / effective», бо саме пара і є фактом: третє поле може
розійтися з першими двома, а похідне — не може.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.billing.entitlements import EntitlementSet

# Які опції яким правом обмежуються. Один словник замість розсипаних
# перевірок: додати ліміт означає дописати рядок, а не знайти всі місця.
LIMITED_BY: dict[str, str] = {
    "max_pages": "max_pages_per_audit",
}

# Опції-вимикачі: право `False` вимикає їх незалежно від значення.
GATED_BY: dict[str, str] = {
    "llm": "semantic_analysis",
}


def watched_keys() -> tuple[str, ...]:
    """Опції, які політика прав узагалі може змінити."""
    return (*LIMITED_BY, *GATED_BY)


@dataclass(frozen=True, slots=True)
class OptionAdjustment:
    """Одна опція, яку тариф змінив.

    `reason` — ключ права, а не готовий текст: рішення про мову належить
    тому шару, який відповідає клієнту.
    """

    option: str
    requested: Any
    effective: Any
    limited_by: str

    def to_json(self) -> dict[str, Any]:
        return {
            "option": self.option,
            "requested": self.requested,
            "effective": self.effective,
            "limited_by": self.limited_by,
        }


def apply(
    requested: dict[str, Any], ent: EntitlementSet
) -> tuple[dict[str, Any], list[OptionAdjustment]]:
    """Дозволені опції та перелік того, що змінилося.

    Порожній перелік означає, що тариф ні на що не вплинув — і це теж
    інформація: звіт може чесно сказати «обмежень не було».
    """
    effective = dict(requested)
    adjustments: list[OptionAdjustment] = []

    for option, right in LIMITED_BY.items():
        asked = requested.get(option)
        allowed = ent.limit(right)
        if asked is None:
            # Клієнт не назвав значення — беремо стелю тарифу. Це не
            # обмеження його вибору, тож і в перелік не потрапляє.
            effective[option] = allowed
            continue
        if allowed is not None and asked > allowed:
            effective[option] = allowed
            adjustments.append(
                OptionAdjustment(
                    option=option, requested=asked, effective=allowed, limited_by=right
                )
            )

    for option, right in GATED_BY.items():
        asked = requested.get(option)
        if asked and not ent.can(right):
            effective[option] = False
            adjustments.append(
                OptionAdjustment(
                    option=option, requested=True, effective=False, limited_by=right
                )
            )

    return effective, adjustments


def describe(requested: dict[str, Any], effective: dict[str, Any]) -> list[dict[str, Any]]:
    """Що змінилося, обчислене з пари. Для читання збереженого аудиту.

    Використовується там, де правил уже немає під рукою — у звіті через
    місяць, у переліку історії. Причину (`limited_by`) відновлюємо з тієї
    самої таблиці правил: вона описує, чому опція взагалі може бути
    обмежена, і не залежить від того, який тариф діяв тоді.
    """
    out = []
    for option in (*LIMITED_BY, *GATED_BY):
        if option not in requested:
            continue
        asked, got = requested.get(option), effective.get(option)
        if asked == got or asked is None:
            continue
        out.append(
            {
                "option": option,
                "requested": asked,
                "effective": got,
                "limited_by": LIMITED_BY.get(option) or GATED_BY[option],
            }
        )
    return out
