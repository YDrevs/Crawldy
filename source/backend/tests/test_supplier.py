"""Постачальник, модель торгівлі й продавець за законом — три різні речі.

Тести без бази: це словник домену, і саме тут найлегше злити поняття,
які потім не розділити.
"""

from __future__ import annotations

from app.billing import supplier as suppliers
from app.billing.enums import CommerceModel
from app.billing.supplier import SellerOfRecord, seller_of_record


def test_merchant_of_record_makes_the_provider_the_seller():
    """При Paddle продавцем для покупця є сам Paddle, а не ми.

    Він укладає угоду з клієнтом, рахує податок і стоїть у чеку; ми
    постачаємо йому продукт. Назвати нашу особу продавцем тут означало б
    описати юридичну реальність неправильно.
    """
    assert (
        seller_of_record(CommerceModel.MERCHANT_OF_RECORD) is SellerOfRecord.PROVIDER
    )


def test_direct_makes_the_supplier_the_seller():
    """При Stripe провайдер — лише процесор. Продавець — ми."""
    assert seller_of_record(CommerceModel.DIRECT) is SellerOfRecord.SUPPLIER


def test_the_future_entity_is_already_in_the_registry():
    """Перехід має бути зміною значення, а не появою поняття."""
    assert "crawldy-us" in suppliers.SUPPLIERS
    assert suppliers.SUPPLIERS["crawldy-us"].country == "US"


def test_snapshot_carries_everything_needed_to_explain_a_sale():
    entity = suppliers.current_supplier()
    snapshot = entity.snapshot()

    assert snapshot["key"] == entity.key
    for field in ("legal_name", "display_name", "country", "support_email"):
        assert field in snapshot


def test_legal_details_are_empty_rather_than_invented():
    """Порожнє поле видно одразу, вигадане — ніколи.

    Юридичні реквізити ще не визначені. Правдоподібна назва в чеку
    виглядала б справжньою й стала б джерелом хибних фактів про нас.
    """
    for entity in suppliers.SUPPLIERS.values():
        assert entity.legal_name == "", "вигадані реквізити потрапили в реєстр"


def test_an_unknown_key_does_not_raise():
    """Ключ особи, якої вже немає в реєстрі, не має валити читання історії.

    Історична покупка не покладається на реєстр — у неї є знімок.
    """
    assert suppliers.supplier("entity-that-was-retired") is None
