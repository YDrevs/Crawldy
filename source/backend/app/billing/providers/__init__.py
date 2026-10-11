"""Адаптери платіжних провайдерів.

Домен знає лише контракт із `base.py`. Paddle живе тут окремим
модулем і не додає жодного імпорту за межами цього пакета.
"""

from app.billing.providers.base import (
    BillingProvider,
    CheckoutRequest,
    CheckoutSession,
    InvalidWebhook,
    ProviderRef,
    ProviderUnavailable,
    Settlement,
    SettlementReport,
    UnhandledEvent,
    VerifiedBillingEvent,
)

__all__ = [
    "BillingProvider",
    "CheckoutRequest",
    "CheckoutSession",
    "InvalidWebhook",
    "ProviderRef",
    "ProviderUnavailable",
    "Settlement",
    "SettlementReport",
    "UnhandledEvent",
    "VerifiedBillingEvent",
]
