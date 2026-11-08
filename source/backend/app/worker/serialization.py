"""Серіалізація черги arq: JSON замість pickle.

arq за замовчуванням читає завдання з Redis через `pickle.loads`, тобто
будь-хто, хто може писати в Redis, виконує код на воркері. Аргументи
наших задач — рядки й числа, результати — словники, тож JSON покриває
все. Те, що JSON не знає (UUID, дати, виняток у результаті невдалої
задачі), стає рядком: результат ми з черги не читаємо, він лише для
журналу arq.
"""

from __future__ import annotations

import json
from typing import Any


def serialize(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, default=str, ensure_ascii=False).encode()


def deserialize(raw: bytes) -> dict[str, Any]:
    try:
        data = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("завдання в черзі не є JSON") from exc
    if not isinstance(data, dict):
        raise ValueError("завдання в черзі не є обʼєктом")
    return data
