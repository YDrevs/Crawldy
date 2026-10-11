"""Таблиці. Представлення персистентності, не бізнес-логіка.

Розкладка по файлах відповідає обмеженим контекстам (`audit`, `identity`,
далі `billing`, `sites`, `scheduling`), а спільний `Base` лишається один:
Alembic має бачити всі таблиці в одному metadata, і три конвенції
розкладки замість однієї коштували б дорожче, ніж дають.

Контекст імпортує лише свій файл. Перевіряється `test_import_boundaries`.
"""

from app.models.ai_settings import AiDomainSettings
from app.models.audit import (
    Audit,
    AuditIssue,
    AuditPage,
    AuditTarget,
    IssueVerdict,
    ReportLink,
)
from app.models.billing import (
    BillingCustomer,
    EntitlementOverride,
    Plan,
    PlanPrice,
    Subscription,
)
from app.models.commerce import CommercialOffer, PromoCampaign, PromoRedemption
from app.models.contact import ContactMessage
from app.models.enrich import EnrichmentAttempt, EnrichmentRun
from app.models.guest import AuditUnlock, GuestMerge, GuestMergeAudit, GuestSession
from app.models.identity import (
    ApiKey,
    Membership,
    Organization,
    PasswordReset,
    Session,
    User,
)
from app.models.presence import PresenceObservation, PresenceRun
from app.models.purchase import AuditCredit, OneOffPurchase
from app.models.runtime_settings import RuntimeSetting
from app.models.scheduling import AuditSchedule
from app.models.sites import Site, SiteMerge
from app.models.usage import Usage

__all__ = [
    "AiDomainSettings",
    "ApiKey",
    "Audit",
    "AuditCredit",
    "AuditIssue",
    "AuditPage",
    "AuditSchedule",
    "AuditTarget",
    "AuditUnlock",
    "BillingCustomer",
    "CommercialOffer",
    "ContactMessage",
    "EnrichmentAttempt",
    "EnrichmentRun",
    "EntitlementOverride",
    "GuestMerge",
    "GuestMergeAudit",
    "GuestSession",
    "IssueVerdict",
    "Membership",
    "OneOffPurchase",
    "Organization",
    "PasswordReset",
    "Plan",
    "PlanPrice",
    "PresenceObservation",
    "PresenceRun",
    "PromoCampaign",
    "PromoRedemption",
    "ReportLink",
    "RuntimeSetting",
    "Session",
    "Site",
    "SiteMerge",
    "Subscription",
    "Usage",
    "User",
]
