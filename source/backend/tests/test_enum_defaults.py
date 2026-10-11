"""Дефолт колонки не має порушувати обмеження тієї самої колонки.

SQLAlchemy зберігає в enum-колонці **імʼя** члена (`RESERVED`), а не його
значення (`reserved`), і CHECK будується на іменах. `server_default`,
записаний зі значення, тому недопустимий — але дефект тихий: ORM завжди
пише поле сам, і до дефолту справа не доходить. Він спрацьовує на першому
записі повз ORM: ручному `INSERT`, міграції даних, відновленні з дампа.

Тест обходить усі таблиці, а не перелічує відомі: клас помилки
повторюваний, і наступна така колонка зʼявиться в коді, який цього файлу
не читав.
"""

from __future__ import annotations

import sqlalchemy as sa

import app.models  # noqa: F401  — реєструє всі таблиці в metadata
from app.core.db import Base


def _enum_columns_with_defaults() -> list[tuple[str, str, str, tuple[str, ...]]]:
    found = []
    for table in Base.metadata.sorted_tables:
        for column in table.columns:
            if not isinstance(column.type, sa.Enum) or column.server_default is None:
                continue
            raw = column.server_default.arg
            text = raw.text if hasattr(raw, "text") else str(raw)
            found.append(
                (table.name, column.name, text.strip("'"), tuple(column.type.enums))
            )
    return found


def test_every_enum_default_is_a_value_the_column_accepts():
    broken = [
        f"{table}.{column}: DEFAULT {default!r} не входить у {list(allowed)}"
        for table, column, default, allowed in _enum_columns_with_defaults()
        if default not in allowed
    ]
    assert not broken, "дефолт порушує CHECK власної колонки:\n" + "\n".join(broken)


def test_the_scan_actually_finds_something():
    """Захист від тесту, який проходить, бо нічого не перевіряє.

    Якщо обхід метаданих зламається, попередній тест стане зеленим
    назавжди й мовчки.
    """
    assert _enum_columns_with_defaults(), "жодної enum-колонки з дефолтом не знайдено"
