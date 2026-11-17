"""Адреса клієнта для лічильників частоти й хешів звернень.

Одне правило на весь API. `X-Forwarded-For` пише кожен учасник ланцюга,
дописуючи праворуч адресу, ВІД якої отримав запит. Ліві записи дає сам
клієнт і підробляє як завгодно; довіряти можна лише тим, що дописали наші
проксі. Тож при `trusted_proxy_count = N` справжній клієнт — N-й запис
справа: його дописав найзовнішній із наших проксі.

0 — проксі немає, заголовок ігнорується повністю. Ланцюг, коротший за N,
означає, що запит обійшов зовнішній проксі: тоді беремо адресу
зʼєднання — суворіше (одне відро на всіх), але не слабше.
"""

from __future__ import annotations

import ipaddress

from starlette.requests import Request

from app.core.config import settings


def client_ip(request: Request) -> str:
    peer = request.client.host if request.client else ""
    count = settings.trusted_proxy_count
    if count <= 0:
        return peer
    header = request.headers.get("x-forwarded-for", "")
    chain = [part.strip() for part in header.split(",") if part.strip()]
    if len(chain) < count:
        return peer
    candidate = chain[-count]
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return peer
    return candidate
