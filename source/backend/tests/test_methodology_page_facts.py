"""Сторінка методології показує числа реального скорингу, а не переказ.

Публічна таблиця «Точні правила розрахунку» рендериться зі знімка
`frontend/app/content/methodology/scoring-facts.json`. Цей тест — межа,
яка не дає знімку розійтися з реалізацією: зміна ваги, множника чи
стелі без оновлення сторінки валить збірку бекенда, а не тихо бреше
клієнтові з шести мов одразу.
"""

from __future__ import annotations

import json
from pathlib import Path

from app.audit.enums import Module, Severity
from app.audit.orchestrator import MIN_WORDS_FOR_A_SITE
from app.audit.scoring import (
    MAX_PENALTY_PER_KEY,
    MAX_PENALTY_SHARE_OF_HALF,
    MODULE_WEIGHT,
    SEVERITY_MULTIPLIER,
)

FACTS_PATH = (
    Path(__file__).resolve().parents[2]
    / "frontend"
    / "app"
    / "content"
    / "methodology"
    / "scoring-facts.json"
)


def _facts() -> dict:
    # Відсутній файл — теж розходження: сторінка тоді рендерить порожнечу.
    return json.loads(FACTS_PATH.read_text(encoding="utf-8"))


def test_the_published_weights_are_the_real_weights() -> None:
    facts = _facts()
    expected = {module.value: weight for module, weight in MODULE_WEIGHT.items()}
    assert facts["weights"] == expected


def test_the_published_severity_multipliers_are_real() -> None:
    facts = _facts()
    expected = {
        severity.value: multiplier
        for severity, multiplier in SEVERITY_MULTIPLIER.items()
    }
    assert facts["severity_multipliers"] == expected


def test_the_published_limits_are_real() -> None:
    facts = _facts()
    assert facts["repetition"]["max_penalty_per_key"] == MAX_PENALTY_PER_KEY
    assert (
        facts["repetition"]["max_penalty_share_of_half"]
        == MAX_PENALTY_SHARE_OF_HALF
    )
    assert facts["coverage"]["min_words_for_a_site"] == MIN_WORDS_FOR_A_SITE


def test_the_snapshot_covers_every_module_and_severity() -> None:
    """Новий модуль чи рівень серйозності мусить зʼявитися й на сторінці."""
    facts = _facts()
    assert set(facts["weights"]) == {module.value for module in Module}
    assert set(facts["severity_multipliers"]) == {
        severity.value for severity in Severity
    }
