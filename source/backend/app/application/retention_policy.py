"""Скільки живуть дані аудиту — і які саме дані.

Політика, а не механізм: чисті функції без вводу-виводу, як і
`retries.py`. Замінити її можна, не чіпаючи ні job чистки, ні жодну
таблицю.

Головний інваріант розділу: **чистка не має робити історичний аудит
незрозумілим**. Після неї ми досі мусимо знати, що аудитували, коли, з
якими опціями, якими версіями, з яким результатом і чому не вийшло, якщо
не вийшло. Тому дані діляться на чотири класи з різними строками, а не
чистяться одним `DELETE ... WHERE created_at <`.

## Чотири класи

`RECORD` — рядок `audits`. Власник, сайт, адреса, статус, час, опції
(просив і зробили), версії, бали, покриття, деградації, клас невдачі,
стан квоти, зведення знахідок. **Строку не має взагалі.** Це не «дуже
довго» — це «ніколи»: на ньому тримається крива історії, і діра в ній
читається як «нічого не сталося».

`FINDINGS` — `audit_issues` і `audit_attempts`. Окремі знахідки з
доказами й журнал спроб. Живуть довго, але не вічно: на аудиті з
двадцяти п'яти сторінок це сотні рядків, і вони накопичуються. Коли їх
чистять, зведення в `RECORD` лишається — саме заради цього воно
рахується при завершенні, а не при чистці.

`DERIVED` — те, що будується на льоту: JSON-звіт, Word-документ,
порівняння з конкурентами. У базі не лежить, чистити нічого. Але
залежність варта згадки: після чистки `RAW` звіт будується з `FINDINGS`,
а після чистки `FINDINGS` — лише зі зведення.

`RAW` — `audit_targets.snapshot` і `audit_pages`. Найдорожче: знімок
чотиристорінкового сайту важить 52 КБ, тобто близько п'яти на сторінку, і
на продуктовому бюджеті в 25 сторінок це сотні кілобайтів на ціль. Строк
найкоротший.

## Чому тариф не вкорочує зберігання

`history_retention_days` у правах тарифу означає **що клієнт бачить**, а
не що ми зберігаємо. Різниця не формальна: якби тариф керував видаленням,
пониження тарифу на один місяць знищувало б рік історії безповоротно, і
жодна підтримка не змогла б допомогти. Приховане повертається, знищене —
ні.

Тариф може строк **подовжити** (агенції потрібні знімки, щоб
перераховувати старі аудити за новими правилами), але не вкоротити нижче
продуктової межі. Тому пониження тарифу нічого не руйнує тієї ж ночі.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any


class DataClass(StrEnum):
    """Клас даних аудиту. Строк життя визначається тільки ним."""

    RECORD = "record"
    FINDINGS = "findings"
    DERIVED = "derived"
    RAW = "raw"


class NeverExpires(Exception):
    """Для цього класу даних строку не існує.

    Виняток, а не `None`, навмисно: `None` означав би «немає обмеження» і
    мовчки прослизнув би в порівняння як «чистити все». Постійний запис
    має бути неможливо почистити помилкою в одному рядку.
    """


# Продуктові межі. Нижче них не опускає жоден тариф.
#
# Тридцять днів для сирих даних — не з міркувань місця, а тому, що знімок
# єдине, з чого аудит перераховується за новими правилами без краулу. Без
# цього вікна зміну скорингу неможливо оцінити на живих даних.
RAW_FLOOR_DAYS = 30
# Знахідки переживають сирі дані на порядок: із них будується детальний
# звіт, і саме їх відкривають, коли питають «а що там було торік».
FINDINGS_FLOOR_DAYS = 365

# Дефолти продукту, якщо права нічого не кажуть.
DEFAULT_RAW_DAYS = 90
DEFAULT_FINDINGS_DAYS = 730


@dataclass(frozen=True, slots=True)
class RetentionPolicy:
    """Строки для однієї організації.

    `None` у `findings_days` — «зберігати завжди». Для `raw_days` такого
    варіанту немає навмисно: вічні знімки означають, що вартість
    зберігання росте лінійно з віком акаунта й ніколи не спадає.

    Інваріант: `findings_days` (якщо скінченний) ≥ `raw_days`. Тримає
    його `resolve`, і саме тому політику будують через нього, а не
    конструктором.
    """

    raw_days: int
    findings_days: int | None

    def cutoff(self, data_class: DataClass, *, now: datetime | None = None) -> datetime | None:
        """Межа, старіше за яку дані цього класу підлягають чистці.

        `None` — клас має строк, але цей акаунт зберігає його завжди.
        Виняток — клас, у якого строку не буває.
        """
        if data_class in (DataClass.RECORD, DataClass.DERIVED):
            raise NeverExpires(f"{data_class.value} не чиститься за строком")
        moment = now or datetime.now(UTC)
        days = self.raw_days if data_class is DataClass.RAW else self.findings_days
        if days is None:
            return None
        return moment - timedelta(days=days)

    @property
    def shortest_days(self) -> int:
        """Найкоротший строк політики. Ним відбирають кандидатів на чистку."""
        return self.raw_days


def resolve(entitlements: dict[str, Any] | None) -> RetentionPolicy:
    """Політика організації з її прав.

    Права можуть строк подовжити й не можуть укоротити: продуктова межа —
    підлога, а не значення за замовчуванням.
    """
    values = entitlements or {}
    raw_days = max(_days(values, "raw_retention_days", DEFAULT_RAW_DAYS), RAW_FLOOR_DAYS)
    findings_days = _findings_days(values)
    if findings_days is not None:
        # Знахідки живуть щонайменше стільки ж, скільки сирі дані. Інакше
        # подовження лише сирих перевертає строки: аудит стає
        # «перераховуваним, але нечитаним» — знімок є, а знахідок уже
        # немає. Хто подовжив знімки, подовжив і те, що з них рахують.
        findings_days = max(findings_days, raw_days)
    return RetentionPolicy(raw_days=raw_days, findings_days=findings_days)


def _days(values: dict[str, Any], key: str, fallback: int) -> int:
    raw = values.get(key)
    return raw if isinstance(raw, int) and raw > 0 else fallback


def _findings_days(values: dict[str, Any]) -> int | None:
    raw = values.get("findings_retention_days", DEFAULT_FINDINGS_DAYS)
    if raw is None:
        return None  # зберігати завжди
    days = raw if isinstance(raw, int) and raw > 0 else DEFAULT_FINDINGS_DAYS
    return max(days, FINDINGS_FLOOR_DAYS)


# Продуктова політика за замовчуванням — для організації без прав.
DEFAULT = RetentionPolicy(raw_days=DEFAULT_RAW_DAYS, findings_days=DEFAULT_FINDINGS_DAYS)


__all__ = [
    "DEFAULT",
    "DEFAULT_FINDINGS_DAYS",
    "DEFAULT_RAW_DAYS",
    "FINDINGS_FLOOR_DAYS",
    "RAW_FLOOR_DAYS",
    "DataClass",
    "NeverExpires",
    "RetentionPolicy",
    "resolve",
]
