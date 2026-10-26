"""Частина імені файлу з адреси сайту — безпечна для заголовка відповіді.

Імʼя йде в `Content-Disposition: attachment; filename="…"`. Адреса сайту
приходить від клієнта: лапка в ній ламала б заголовок, а кирилиця
(`сайт.укр`) не кодується в Latin-1, і відповідь падала з 500. Тому
домен переводиться в punycode, а все, що лишилось поза `[A-Za-z0-9-._]`,
стає дефісом.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def host_part(url_or_host: str, *, fallback: str = "site") -> str:
    raw = url_or_host.strip()
    host = urlparse(raw).hostname if "://" in raw else raw.split("/")[0]
    host = (host or "").strip(".").lower()
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError:
        pass
    safe = _UNSAFE.sub("-", host).strip("-.")
    return safe[:120] or fallback
