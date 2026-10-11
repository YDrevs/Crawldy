"""Історія скорів: що змінилося на сайті, а що змінилося в нас.

Повторний аудит замовляють заради однієї цифри — «стало краще?». Дати
цю цифру просто; дати її чесно — ні. Між двома прогонами міняється не
лише сайт: додається чек, зсувається стеля, перерозподіляються ваги. У
цьому проєкті таке вже траплялося двічі, і обидва рази бали всієї
вибірки поїхали мовчки.

Тому тут дві відповіді замість однієї. Перша — чи взагалі можна
порівнювати: якщо версія детекторів або скорингу інша, різниця
пояснюється і сайтом, і нами, а розділити внески неможливо. Друга — що
робити, коли не можна: перерахувати старий знімок нинішніми правилами й
порівняти вже однакове. Саме заради цього знімок і зберігається.

Модуль чистий: ні FastAPI, ні ORM. На вході — точки, на виході —
порівняння.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
from typing import Any

# Складові версії, зміна яких робить бали непорівнянними. `config` і
# `model` сюди не входять навмисно: вони кажуть, *що* ми міряли (скільки
# сторінок, якою моделлю), а не *як* рахували. Різниця в них — теж
# причина обережності, але вона видима у звіті й без нас.
DECIDING_VERSIONS = ("detector", "scoring")


@dataclass(slots=True)
class ScorePoint:
    """Один аудит в історії сайту."""

    audit_id: str
    at: datetime
    overall: int | None
    scores: dict[str, int] = field(default_factory=dict)
    versions: dict[str, Any] = field(default_factory=dict)
    # Чи лежить у базі знімок, з якого цей аудит можна перерахувати.
    has_snapshot: bool = False

    def to_json(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "at": self.at.isoformat(),
            "overall": self.overall,
            "scores": self.scores,
            "versions": self.versions,
            "can_be_recomputed": self.has_snapshot,
        }


@dataclass(slots=True)
class Comparison:
    """Різниця між двома аудитами й межі, у яких їй можна вірити."""

    before: ScorePoint
    after: ScorePoint
    overall_delta: int | None
    by_module: dict[str, int]
    # Обидва пораховані однаково — різницю можна приписати сайту.
    comparable: bool
    # Що саме змінилося в нас: «detector», «scoring» або обидва.
    changed_in_us: list[str] = field(default_factory=list)
    # Порівняння зроблене після перерахунку старого знімка нинішніми
    # правилами, тож попри різні версії воно чесне.
    rebased: bool = False

    @property
    def days(self) -> int:
        return max((self.after.at - self.before.at).days, 0)

    def to_json(self) -> dict[str, Any]:
        return {
            "before": self.before.to_json(),
            "after": self.after.to_json(),
            "days_between": self.days,
            "overall_delta": self.overall_delta,
            "by_module": self.by_module,
            "comparable": self.comparable,
            "changed_in_us": self.changed_in_us,
            "rebased": self.rebased,
        }


def compare(before: ScorePoint, after: ScorePoint, *, rebased: bool = False) -> Comparison:
    """Різниця між двома точками з позначкою, чи їй можна вірити.

    Дельта рахується завжди — ховати число безглуздо, його однаково
    видно з двох звітів. Але поруч із ним стоїть відповідь на питання,
    якого клієнт не поставить сам: чи це сайт змінився.
    """
    changed = [
        name
        for name in DECIDING_VERSIONS
        if before.versions.get(name) != after.versions.get(name)
    ]
    # Порівняння після перерахунку однакове за побудовою: обидві точки
    # пораховані нинішнім кодом, навіть якщо стара збиралася торік.
    comparable = rebased or not changed
    modules = sorted(set(before.scores) | set(after.scores))
    return Comparison(
        before=before,
        after=after,
        overall_delta=_delta(before.overall, after.overall),
        by_module={
            name: after.scores[name] - before.scores[name]
            for name in modules
            if name in before.scores and name in after.scores
        },
        comparable=comparable,
        changed_in_us=[] if rebased else changed,
        rebased=rebased,
    )


def _delta(before: int | None, after: int | None) -> int | None:
    """Немає бала — немає дельти. Нуль тут означав би «не змінилося»."""
    return None if before is None or after is None else after - before


def timeline(points: list[ScorePoint]) -> list[Comparison]:
    """Порівняння кожної точки з попередньою, від старішої до новішої."""
    ordered = sorted(points, key=lambda p: p.at)
    return [compare(a, b) for a, b in pairwise(ordered)]


def needs_recompute(points: list[Comparison]) -> list[Comparison]:
    """Порівняння, які можна виправити перерахунком старого знімка.

    Саме вони й роблять історію придатною: без перерахунку кожна зміна
    правил лишає в графіку стрибок, який виглядає як подія на сайті.
    """
    return [c for c in points if not c.comparable and c.before.has_snapshot]


__all__ = [
    "DECIDING_VERSIONS",
    "Comparison",
    "ScorePoint",
    "compare",
    "needs_recompute",
    "timeline",
]
