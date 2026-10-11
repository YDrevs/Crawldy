"""Порівняння з конкурентами: що з ваших проблем справді ваші.

Таблиця балів — найменш корисне, що можна зробити з кількох аудитів.
«У вас 62, у них 71» не каже, що робити, і навіть не каже, чи це погано:
різниця в девʼять балів може складатися з десятка дрібниць, які є в усіх.

Тому головне тут — не рейтинг, а поділ проблем на три купи. Ті, що є в
усіх, — норма галузі: виправляти їх варто, але виграшу над конкурентами
вони не дадуть, бо ніхто нічого й не виграє. Ті, що є лише у вас, — і є
відставання, за яке платять. Ті, яких немає лише у вас, — ваша перевага,
і про неї теж треба знати, щоб випадково не втратити.

Порівнювати можна тільки однаково пораховане. На відміну від історії,
сюди входить і `config`: краул на 25 сторінок проти краулу на 5 — це не
порівняння сайтів, а порівняння бюджетів.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median
from typing import Any

# Складові версії, зміна яких робить порівняння недійсним. `config` тут
# є, а в історії немає: там ідеться про той самий сайт у різний час, і
# бюджет краулу впливає слабше, ніж різниця в правилах. Тут же різний
# бюджет означає, що конкурента ми прочитали інакше, ніж вас.
DECIDING_VERSIONS = ("detector", "scoring", "config")


@dataclass(slots=True)
class Contender:
    """Один сайт у порівнянні."""

    label: str
    origin: str
    overall: int | None
    scores: dict[str, int] = field(default_factory=dict)
    versions: dict[str, Any] = field(default_factory=dict)
    # Ключі знахідок (`Issue.msg`), а не коди: клієнту різні проблеми під
    # одним кодом — різні дії, і в порівнянні так само.
    findings: set[str] = field(default_factory=set)

    def to_json(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "origin": self.origin,
            "overall": self.overall,
            "scores": self.scores,
        }


@dataclass(slots=True)
class Benchmark:
    """Ви на тлі конкурентів."""

    subject: Contender
    rivals: list[Contender]
    # Модулі, де ви нижчі за медіану конкурентів, і на скільки.
    behind_on: dict[str, int]
    ahead_on: dict[str, int]
    # Проблеми, які є у вас і в усіх конкурентів: норма галузі.
    everyone_has: list[str]
    # Проблеми, які є лише у вас: те, чим ви програєте.
    only_you_have: list[str]
    # Проблеми, яких немає лише у вас: ваша перевага.
    only_you_avoid: list[str]
    comparable: bool
    # З ким саме порівняння недійсне і чому.
    incomparable_with: dict[str, list[str]] = field(default_factory=dict)

    @property
    def rank(self) -> int | None:
        """Місце за загальним балом, 1 — найкраще. None, якщо бала немає."""
        if self.subject.overall is None:
            return None
        scored = [c.overall for c in [self.subject, *self.rivals] if c.overall is not None]
        return sorted(scored, reverse=True).index(self.subject.overall) + 1

    def to_json(self) -> dict[str, Any]:
        return {
            "subject": self.subject.to_json(),
            "rivals": [r.to_json() for r in self.rivals],
            "rank": self.rank,
            "of": len([c for c in [self.subject, *self.rivals] if c.overall is not None]),
            "behind_on": self.behind_on,
            "ahead_on": self.ahead_on,
            "everyone_has": self.everyone_has,
            "only_you_have": self.only_you_have,
            "only_you_avoid": self.only_you_avoid,
            "comparable": self.comparable,
            "incomparable_with": self.incomparable_with,
        }


def compare(subject: Contender, rivals: list[Contender]) -> Benchmark:
    """Порівняння одного сайту з рештою.

    Порожній список конкурентів — не помилка: буває аудит на одну ціль,
    і тоді все, що можна чесно сказати, — що порівнювати нема з чим.
    """
    incomparable = {
        rival.origin: changed
        for rival in rivals
        if (changed := _differs(subject.versions, rival.versions))
    }
    behind, ahead = _module_gaps(subject, rivals)
    return Benchmark(
        subject=subject,
        rivals=rivals,
        behind_on=behind,
        ahead_on=ahead,
        everyone_has=_everyone_has(subject, rivals),
        only_you_have=_only_you_have(subject, rivals),
        only_you_avoid=_only_you_avoid(subject, rivals),
        comparable=not incomparable,
        incomparable_with=incomparable,
    )


def _differs(ours: dict[str, Any], theirs: dict[str, Any]) -> list[str]:
    return [name for name in DECIDING_VERSIONS if ours.get(name) != theirs.get(name)]


def _module_gaps(
    subject: Contender, rivals: list[Contender]
) -> tuple[dict[str, int], dict[str, int]]:
    """Відставання й перевага по модулях проти медіани конкурентів.

    Медіана, а не середнє: один конкурент із заблокованим краулом і
    порожнім балом інакше перетягував би картину на себе.
    """
    behind: dict[str, int] = {}
    ahead: dict[str, int] = {}
    for module, ours in subject.scores.items():
        theirs = [r.scores[module] for r in rivals if module in r.scores]
        if not theirs:
            continue
        gap = ours - round(median(theirs))
        if gap < 0:
            behind[module] = gap
        elif gap > 0:
            ahead[module] = gap
    return behind, ahead


def _everyone_has(subject: Contender, rivals: list[Contender]) -> list[str]:
    """Проблеми, спільні для всіх. Виправляти варто, виграти — ні."""
    if not rivals:
        return []
    common = set(subject.findings)
    for rival in rivals:
        common &= rival.findings
    return sorted(common)


def _only_you_have(subject: Contender, rivals: list[Contender]) -> list[str]:
    """Те, чим ви програєте: проблема ваша й більше нічия."""
    theirs: set[str] = set()
    for rival in rivals:
        theirs |= rival.findings
    return sorted(subject.findings - theirs)


def _only_you_avoid(subject: Contender, rivals: list[Contender]) -> list[str]:
    """Ваша перевага: проблема є в кожного конкурента, а у вас немає.

    Це не привід нічого робити — це привід не зламати випадково.
    """
    if not rivals:
        return []
    common = set(rivals[0].findings)
    for rival in rivals[1:]:
        common &= rival.findings
    return sorted(common - subject.findings)


__all__ = ["DECIDING_VERSIONS", "Benchmark", "Contender", "compare"]
