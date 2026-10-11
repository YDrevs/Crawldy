"""Пошук адаптера провайдера за іменем.

Мінімальний навмисно: словник і функція. Плагінів, точок розширення й
автозавантаження тут не буде — провайдерів у нас один, буде два, і
абстракція, що чекає на третього, коштує дорожче за словник.

Реєстр існує рівно заради маршруту вебхука: він отримує ім'я провайдера
з адреси й мусить перетворити його на адаптер, не знаючи, які взагалі
бувають. Невідоме ім'я повертає `None`, а маршрут відповідає так само,
як на невірний підпис: перебором адрес не має з'ясовуватися, кого ми
підключили.
"""

from __future__ import annotations

from app.billing.providers import BillingProvider, InvalidWebhook, UnhandledEvent
from app.billing.providers.fake import NAME as FAKE_NAME
from app.billing.providers.fake import FakeBillingProvider, FakePricePublisher
from app.billing.providers.paddle import NAME as PADDLE_NAME
from app.billing.providers.paddle import PaddleProvider
from app.billing.providers.paddle_prices import PaddlePricePublisher
from app.billing.publishing import PricePublisher
from app.core.config import settings

# Один екземпляр на процес. Фейк тримає сценарний стан (клієнти,
# підписки), і два екземпляри означали б, що подія, зроблена одним,
# невідома другому.
_FAKE = FakeBillingProvider()

# Paddle не тримає стану — новий екземпляр коштує нічого, але один
# на процес рівно з тієї ж причини, що й фейк: передбачуваність.
_PADDLE = PaddleProvider()

_PROVIDERS: dict[str, BillingProvider] = {PADDLE_NAME: _PADDLE}
if settings.app_env != "prod":
    _PROVIDERS[FAKE_NAME] = _FAKE


# Публікатори прайсів — окремий реєстр із тим самим гейтом: фейк у
# проді не публікує нічого, як і не продає.
_FAKE_PRICES = FakePricePublisher()
_PADDLE_PRICES = PaddlePricePublisher()
_PUBLISHERS: dict[str, PricePublisher] = {PADDLE_NAME: _PADDLE_PRICES}
if settings.app_env != "prod":
    _PUBLISHERS[FAKE_NAME] = _FAKE_PRICES


def publisher_for(name: str) -> PricePublisher | None:
    """Публікатор прайсів за іменем провайдера, або `None` для невідомого."""
    return _PUBLISHERS.get(name.strip().lower())


def register_publisher(name: str, publisher: PricePublisher) -> None:
    """Замінити або додати публікатор. Для тестів."""
    _PUBLISHERS[name.strip().lower()] = publisher


def fake_prices() -> FakePricePublisher:
    """Той самий екземпляр фейкового публікатора, який бачать маршрути."""
    return _FAKE_PRICES


def provider_for(name: str) -> BillingProvider | None:
    """Адаптер за іменем, або `None` для невідомого."""
    return _PROVIDERS.get(name.strip().lower())


def register(name: str, provider: BillingProvider) -> None:
    """Замінити або додати адаптер. Для тестів і для появи справжнього."""
    _PROVIDERS[name.strip().lower()] = provider


def fake() -> FakeBillingProvider:
    """Той самий екземпляр фейка, який бачить маршрут вебхука."""
    return _FAKE


__all__ = [
    "InvalidWebhook",
    "UnhandledEvent",
    "fake",
    "fake_prices",
    "provider_for",
    "publisher_for",
    "register",
    "register_publisher",
]
