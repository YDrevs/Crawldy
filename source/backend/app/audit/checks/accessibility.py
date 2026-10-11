"""Доступність: чи може користуватися сайтом той, хто бачить чи рухається інакше.

Дані приходять із Lighthouse тим самим запитом, що й швидкість —
всередині нього axe-core. Своїх правил контрасту ми не пишемо: п'ять
власних перевірок дали б рівно те, від чого застерігає власний досвід
цього проєкту — більше чеків без більшої вартості.

Чеки тут лише перекладають результат у мову клієнта й вирішують, що
серйозне, а що ні. Перевірки, які ми вже робимо самі (alt зображень,
ієрархія заголовків, мова сторінки), відсіяні в провайдері: сказати про
одну ваду двічі означає подвоїти штраф за неї.

Модуль виключається зі скора, коли даних немає, — так само як швидкість
без ключа PSI. Мовчання не означає, що проблем немає.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.audit.checks.base import Check, register
from app.audit.types import Effort, Issue, Module, Severity, SiteContext

# Перевірки, які ламають користування сайтом, а не ускладнюють його.
# Заблокований зум і кнопка без назви — це не «недоліки оформлення»:
# людина просто не може зробити те, по що прийшла.
#
# `color-contrast` сюди навмисно не входить, хоч і виглядає доречно.
# На калібрувальній вибірці він провалювався на 17 сайтах із 31, а на
# шести був єдиною причиною «блокуючої» знахідки — тобто заявою про
# зламане користування там, де десь на сторінці сірий підпис на світлому
# тлі. Причина не в тому, що контраст не важливий, а в тому, що наші
# дані не відрізняють суцільно нечитабельну сторінку від одного дрібного
# напису: Lighthouse віддає сам факт, без частки ураженого тексту.
# Стверджуємо те, що можемо довести, тож контраст лишається у звичайних.
BLOCKING = frozenset({
    "meta-viewport",
    "button-name",
    "link-name",
    "label",
    "frame-title",
    "input-image-alt",
    "aria-required-attr",
    "aria-valid-attr-value",
})

# Скільки провалених перевірок показуємо переліком у доказах.
MAX_LISTED = 8


def _failures(ctx: SiteContext, *, blocking: bool) -> tuple[list[dict[str, str]], Any]:
    """Провалені перевірки потрібної половини разом із вимірюванням."""
    measured = ctx.primary_performance()
    if measured is None or measured.accessibility_score is None:
        return [], None
    picked = [f for f in measured.accessibility_failures if (f["id"] in BLOCKING) is blocking]
    return picked, measured


def _evidence(failures: list[dict[str, str]], measured: Any) -> dict[str, Any]:
    return {
        "audits": [f["id"] for f in failures][:MAX_LISTED],
        "titles": [f["title"] for f in failures][:MAX_LISTED],
        "lighthouse_score": measured.accessibility_score,
        "strategy": measured.strategy.value,
    }


# Два коди, а не один із двома повідомленнями. Друга стеля скорингу
# працює на `code`: під спільним кодом «не можу натиснути кнопку» і
# «незручно читати» вважалися повтореннями однієї проблеми, і модуль
# видавав рівно три різні бали на всю калібрувальну вибірку.
@register
class BlockingAccessibilityCheck(Check):
    """Людина не може зробити те, по що прийшла."""

    code = "a11y.blocking"
    module = Module.ACCESSIBILITY
    severity = Severity.HIGH
    weight = 3
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        failures, measured = _failures(ctx, blocking=True)
        if failures:
            yield self.issue(
                params={"count": len(failures)},
                evidence=_evidence(failures, measured),
            )


@register
class AccessibilityCheck(Check):
    """Користуватися можна, але важче, ніж мало б бути."""

    code = "a11y.failures"
    module = Module.ACCESSIBILITY
    severity = Severity.MEDIUM
    weight = 3
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        failures, measured = _failures(ctx, blocking=False)
        if failures:
            yield self.issue(
                params={"count": len(failures)},
                evidence=_evidence(failures, measured),
            )
