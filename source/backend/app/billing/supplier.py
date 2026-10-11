"""Хто постачає продукт, хто продає за законом і хто проводить платіж.

Три різні речі, які легко злити в одну й потім не розділити.

## Постачальник — це ми

`Supplier` — наша юридична особа: та, що володіє продуктом і надає
послугу. Сьогодні одна, після переходу в США інша. Це **не** обовʼязково
той, хто фігурує в чеку покупця.

## Продавець за законом залежить від моделі торгівлі

При `MERCHANT_OF_RECORD` продавцем для покупця виступає сам провайдер:
Paddle укладає угоду з клієнтом, виставляє податок і несе за це
відповідальність, а ми постачаємо йому продукт. У чеку стоїть Paddle.

При `DIRECT` провайдер — лише процесор платежу. Stripe нікому нічого не
продає; продавець — ми, і в чеку стоїть наша назва.

Тому «продавець» не можна виводити ані з постачальника, ані з
провайдера окремо. Він виводиться з моделі торгівлі, і саме її треба
зберігати в покупці: після переходу Paddle → Stripe стара покупка
мусить і далі означати те, що означала.

## Чому реєстр у коді, а не в базі

Юридичних осіб одиниці, вони не заводяться користувачем і не міняються
щотижня. Таблиця під них дала б адмінку, міграції й можливість
відредагувати особу заднім числом — саме те, чого не має статися з
історією продажів.

Незмінність історії тримає не цей файл, а знімок реквізитів у самій
покупці: реєстр колись відредагують, і без знімка стара покупка мовчки
змінила б постачальника.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any

from app.billing.enums import CommerceModel


class SellerOfRecord(StrEnum):
    """Кого покупець бачить продавцем. Виводиться, не зберігається."""

    PROVIDER = "provider"
    SUPPLIER = "supplier"


def seller_of_record(model: CommerceModel) -> SellerOfRecord:
    return (
        SellerOfRecord.PROVIDER
        if model is CommerceModel.MERCHANT_OF_RECORD
        else SellerOfRecord.SUPPLIER
    )


@dataclass(frozen=True, slots=True)
class Supplier:
    """Наша юридична особа.

    Порожні рядки тут не помилка: реквізити ще не визначені, і вигадані
    виглядали б справжніми в чеку. Порожнє поле видно одразу, вигадане —
    ніколи.
    """

    key: str
    legal_name: str
    display_name: str
    country: str
    address: str = ""
    tax_id: str = ""
    support_email: str = ""
    terms_url: str = ""
    privacy_url: str = ""

    def snapshot(self) -> dict[str, Any]:
        """Незмінний зліпок для запису в покупку."""
        return asdict(self)


SUPPORT_EMAIL = "support@crawldy.com"

# Реєстр. Ключ ніколи не перевикористовується під іншу особу: він і є
# тим, на що посилається історія.
SUPPLIERS: dict[str, Supplier] = {
    # Поточна юридична особа. Назву й реквізити впишуть, коли вони
    # будуть остаточними; ключ від цього не зміниться.
    "current": Supplier(
        key="current",
        legal_name="",
        display_name="Crawldy",
        country="UA",
        support_email=SUPPORT_EMAIL,
    ),
    # Майбутня. Заведена наперед навмисно: перехід має бути зміною
    # значення в налаштуваннях, а не появою нового поняття.
    "crawldy-us": Supplier(
        key="crawldy-us",
        legal_name="",
        display_name="Crawldy",
        country="US",
        support_email=SUPPORT_EMAIL,
    ),
}

# Чинна пара «хто постачає» + «як торгуємо». Змінюється разом із
# переходом на іншого провайдера і **не впливає на вже записані
# покупки**: ті несуть власний знімок і власну модель торгівлі.
CURRENT_SUPPLIER_KEY = "current"
CURRENT_COMMERCE_MODEL = CommerceModel.MERCHANT_OF_RECORD


def current_supplier() -> Supplier:
    return SUPPLIERS[CURRENT_SUPPLIER_KEY]


def supplier(key: str) -> Supplier | None:
    """Особа за ключем — або `None` для ключа, якого вже немає.

    Історична покупка не покладається на цю функцію: у неї є знімок.
    Вона потрібна там, де питають про **чинного** постачальника.
    """
    return SUPPLIERS.get(key)


__all__ = [
    "CURRENT_COMMERCE_MODEL",
    "CURRENT_SUPPLIER_KEY",
    "SUPPLIERS",
    "CommerceModel",
    "SellerOfRecord",
    "Supplier",
    "current_supplier",
    "seller_of_record",
    "supplier",
]
