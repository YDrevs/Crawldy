"""Моделі, доступні для семантичного аналізу.

Єдине джерело правди для валідації запиту й для списку в інтерфейсі.
Два списки розʼїхалися б на першій же зміні, а наслідок був би тихий:
UI пропонує модель, яку API відбиває.

Опис кожної моделі — не маркетинг, а результат прогону по калібрувальній
вибірці (7 сайтів, 2026-08-07). Вибір моделі змінює бал: на 1csmart.com.ua
різниця між найдорожчою й найдешевшою — 13 балів, і всі 13 від знахідок,
яких дешевша не побачила. Тому користувач має бачити, чим платить за
економію.

Знахідок на всій вибірці: Opus 5 — три, Sonnet 5 — одна, Haiku 4.5 — одна.
Хибних спрацювань на добре зроблених сайтах — жодного в усіх трьох, тобто
економія коштує чутливості, а не точності.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LlmModelInfo:
    id: str
    label: str
    # Приблизна вартість семантичної частини одного аудиту, доларів.
    # Два виклики на аудит; порядок величини, не рахунок.
    cost_per_audit: float
    note: str
    default: bool = False


AVAILABLE_MODELS: tuple[LlmModelInfo, ...] = (
    LlmModelInfo(
        id="claude-opus-5",
        label="Claude Opus 5",
        cost_per_audit=0.085,
        note="найчутливіша: на калібрувальній вибірці знайшла втричі більше за решту",
        default=True,
    ),
    LlmModelInfo(
        id="claude-sonnet-5",
        label="Claude Sonnet 5",
        cost_per_audit=0.05,
        # Проміжною за ціною вона є, проміжною за результатом — ні. Писати
        # «середина» означало б продати користувачеві те, чого ми не міряли.
        note="втричі дорожча за Haiku, але на нашій вибірці знайшла рівно стільки ж",
    ),
    LlmModelInfo(
        id="claude-haiku-4-5",
        label="Claude Haiku 4.5",
        cost_per_audit=0.017,
        note=(
            "вп'ятеро дешевша за Opus, безпідставно не звинувачує, "
            "але дві знахідки з трьох пропускає"
        ),
    ),
)

MODEL_IDS: tuple[str, ...] = tuple(m.id for m in AVAILABLE_MODELS)
DEFAULT_MODEL: str = next(m.id for m in AVAILABLE_MODELS if m.default)


def is_known(model: str) -> bool:
    return model in MODEL_IDS


__all__ = ["AVAILABLE_MODELS", "DEFAULT_MODEL", "MODEL_IDS", "LlmModelInfo", "is_known"]
