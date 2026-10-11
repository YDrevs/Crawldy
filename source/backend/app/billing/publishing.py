"""Публікація прайсів у провайдера: одна ціна, задана в кабінеті.

Закладка «Ціни» — єдине місце, де людина задає суму. Провайдер каси не
має власної думки про неї: при кожному збереженні ціни ми створюємо або
оновлюємо його прайс тією самою сумою й валютою і запамʼятовуємо
ідентифікатор. У кабінеті провайдера ніхто нічого не вписує; при зміні
провайдера чи його оточення каталог публікується наново автоматично.

Контракт навмисно вужчий за `BillingProvider`: публікація — інша
відповідальність (каталог), і адаптер каси може її не мати взагалі.
Адаптер отримує опис прайса без слів провайдера й повертає те, що
справді опублікував: суму й валюту з його відповіді, а не з нашого
запиту. Розбіжність між ними — знахідка, а не припущення.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PriceSpec:
    """Що саме опублікувати. `interval` порожній — разова покупка."""

    code: str
    name: str
    amount_minor: int
    currency: str
    interval: str | None
    description: str


@dataclass(frozen=True)
class PublishedPrice:
    """Що провайдер справді має після публікації.

    Сума й валюта — з ВІДПОВІДІ провайдера. Каса стягує саме їх, і
    показувати клієнтові інше число означало б продавати за одну ціну, а
    брати іншу. Для підписок є властивість самого провайдера, яку ми не
    приховуємо: чинні підписки лишаються на сумі, з якою їх відкрили, і
    нову ціну бачать лише нові підписники.
    """

    provider: str
    product_ref: str
    price_ref: str
    amount_minor: int
    currency: str
    interval: str | None
    status: str


class PublishFailed(Exception):
    """Провайдер не прийняв прайс. Збереження ціни при цьому не відбувається:
    сайт не сміє показувати суму, за якою каса не візьме гроші."""

    def __init__(self, outcome: str, detail: str) -> None:
        super().__init__(f"{outcome}: {detail}")
        self.outcome = outcome
        self.detail = detail


class PricePublisher(Protocol):
    name: str

    async def publish(
        self, spec: PriceSpec, *, price_ref: str | None, product_ref: str | None
    ) -> PublishedPrice:
        """Створити або оновити прайс. `price_ref` і `product_ref` — те, що
        ми запамʼятали минулого разу; невідоме провайдерові ігнорується й
        замінюється новим."""
        ...

    async def read(self, price_ref: str) -> PublishedPrice | None:
        """Що провайдер має зараз під цим ідентифікатором; `None` — не має."""
        ...


__all__ = ["PricePublisher", "PriceSpec", "PublishFailed", "PublishedPrice"]
