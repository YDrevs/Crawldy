"""Частина імені файлу, яку можна покласти в `Content-Disposition`.

Хост приходить від клієнта (адреса, яку він дав на аудит). Лапка
закриває `filename="..."`, а будь-що поза ASCII-латиницею, цифрами й
`-._` у заголовку — або ламає його, або дає браузеру вигадати імʼя
самостійно. Тому лишається лише безпечна множина; решта стає `-`.
"""

from __future__ import annotations

_ALLOWED = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._")


def safe_part(text: str, fallback: str) -> str:
    cleaned = "".join(c if c in _ALLOWED else "-" for c in text).strip("-.")
    return cleaned[:120] or fallback


def host_part(url_or_origin: str, fallback: str = "site") -> str:
    """Хост із адреси чи origin — без схеми, шляху й небезпечних символів."""
    host = url_or_origin.split("://", 1)[-1].split("/", 1)[0]
    return safe_part(host, fallback)
