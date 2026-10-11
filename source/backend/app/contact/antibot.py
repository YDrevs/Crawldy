"""Перевірка антибот-токена на СЕРВЕРІ.

Віджет у браузері не захищає нічого: він лише видає токен, і поки цей
токен не перевірено на сервері запитом до провайдера, будь-хто надішле
форму напряму в API. Cloudflare і Google кажуть це прямо у власній
документації, і саме тому перевірка живе тут, а не на клієнті.

## Три стани, а не два

`ok` — провайдер підтвердив токен. `rejected` — провайдер сказав «ні»:
це відмова, і звернення не приймається. `unavailable` — провайдер не
відповів або не налаштований: наша інфраструктура, а не вина людини.

Розрізняти друге й третє обовʼязково. Мовчазне перетворення «провайдер
лежить» на «ви бот» відрізало б живих людей від єдиного каналу звʼязку;
зворотне — «не змогли перевірити, тож пропустимо» — робить перевірку
декоративною. Політику вибору для кожного стану ухвалює маршрут, а не
цей модуль: тут лише чесна відповідь про те, що сталося.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.logging import log

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Офіційні тестові ключі Cloudflare. Вони існують саме для розробки й
# приймають будь-який токен; це НЕ production-облікові дані, і саме тому
# їх видно в коді.
TURNSTILE_TEST_SECRET = "1x0000000000000000000000000000000AA"


class Verdict(StrEnum):
    OK = "ok"
    REJECTED = "rejected"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class Verification:
    verdict: Verdict
    # Коди провайдера — для журналу й діагностики. Клієнтові вони не
    # показуються ніколи: це службові рядки, а не текст для людини.
    codes: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return self.verdict is Verdict.OK


class AntiBotProvider(Protocol):
    """Провайдер челенджу. Три методи не потрібні — вистачає одного."""

    name: str

    async def verify(self, token: str, *, remote_ip: str) -> Verification: ...


class DisabledProvider:
    """Провайдера не налаштовано.

    Він не вдає успіх: віддає `unavailable`, і рішення, що з цим робити,
    ухвалює маршрут за оточенням. Вдавана перевірка гірша за відсутню —
    вона ще й приховує, що захисту немає.
    """

    name = "disabled"

    async def verify(self, token: str, *, remote_ip: str) -> Verification:
        return Verification(verdict=Verdict.UNAVAILABLE, codes=("not-configured",))


class TurnstileProvider:
    """Cloudflare Turnstile: перевірка токена запитом до провайдера."""

    name = "turnstile"

    def __init__(self, secret: str, *, timeout: float = 5.0) -> None:
        self._secret = secret
        self._timeout = timeout

    async def verify(self, token: str, *, remote_ip: str) -> Verification:
        if not token:
            # Порожній токен — це відмова, а не збій: браузер із живим
            # віджетом завжди щось надсилає.
            return Verification(verdict=Verdict.REJECTED, codes=("missing-input-response",))
        payload = {"secret": self._secret, "response": token}
        if remote_ip:
            payload["remoteip"] = remote_ip
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(TURNSTILE_VERIFY_URL, data=payload)
            response.raise_for_status()
            body = response.json()
        except Exception as exc:  # noqa: BLE001 — мережа, таймаут, нерозбірлива відповідь
            # Токен у журнал не потрапляє: він одноразовий, але це
            # секрет запиту, і місце йому не в логах.
            log.warning("turnstile_unavailable", error=type(exc).__name__)
            return Verification(verdict=Verdict.UNAVAILABLE, codes=("provider-error",))
        codes = tuple(str(code) for code in (body.get("error-codes") or []))
        if body.get("success") is True:
            return Verification(verdict=Verdict.OK, codes=codes)
        return Verification(verdict=Verdict.REJECTED, codes=codes)


def build_provider() -> AntiBotProvider:
    """Провайдер за конфігурацією. Ключа немає — перевірки немає, і це видно."""
    secret = settings.turnstile_secret_key
    if not secret:
        return DisabledProvider()
    return TurnstileProvider(secret)
