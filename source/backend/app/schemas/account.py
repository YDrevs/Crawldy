"""Контракт акаунта: тариф, підписка, права, використання.

Один ресурс замість чотирьох дрібних: будь-якому інтерфейсу — веб,
мобільному, CLI — на екрані акаунта потрібні саме ці речі разом, і
чотири запити замість одного не дали б нічого, крім чотирьох спінерів.

Це продуктовий ресурс, а не зліпок таблиць: `plan` тут — код і назва, а
не рядок `plans`; `subscription` — стан і межі, а не ORM-модель;
`entitlements` — уже розвʼязані значення після тарифу й індивідуальних
винятків, тобто те, що справді діє.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.billing.enums import BillingState, SubscriptionStatus


class AccountOrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_personal: bool
    default_locale: str

    model_config = {"from_attributes": True}


class PlanOut(BaseModel):
    code: str
    name: str


class SubscriptionOut(BaseModel):
    """Стан підписки. Відсутність (`null` в акаунті) — теж відповідь:
    організація живе на безкоштовному тарифі без підписки взагалі."""

    status: SubscriptionStatus
    cancel_at_period_end: bool
    current_period_start: datetime | None
    current_period_end: datetime | None
    trial_end: datetime | None
    grace_until: datetime | None

    model_config = {"from_attributes": True}


class UsageOut(BaseModel):
    """Скільки аудитів доступно — з двох різних джерел.

    **Два числа, а не одне.** Спокуса скласти їх у «доступно 29» велика
    й хибна: квота періоду згорає при поновленні, куплені кредити — ні.
    Клієнт, який побачив одну суму, не може вирішити, чи варто робити
    аудит сьогодні, і виявляє різницю аж тоді, коли частина числа зникає
    сама собою.

    Провайдера тут немає навмисно: інтерфейс не має знати, через кого
    пройшов платіж, і не має ламатися від того, що через рік це буде
    інший провайдер.
    """

    audits_used: int
    # None — без обмеження.
    audits_limit: int | None
    # Скільки лишилось. Рахує бекенд, а не інтерфейс: «ліміт мінус
    # використано» виглядає тривіальним рівно доти, доки не зʼявляється
    # безлімітний тариф, перевитрата після зміни плану або від'ємна
    # різниця. Три клієнти повторили б це правило тричі.
    audits_remaining: int | None
    period_start: datetime
    period_end: datetime
    # Коли квота поновиться — або `None`, якщо не поновиться взагалі.
    # Порожньо для скасованої підписки: показати дату означало б обіцяти
    # поновлення, якого не буде.
    renews_at: datetime | None = None
    # Окремо куплені аудити. Періоду не мають, при поновленні підписки не
    # змінюються, витрачаються лише коли квота періоду вичерпана.
    one_off_available: int = 0

    # Перевірки AI-присутності: місячна квота підписки і куплені одиниці
    # окремо — це різні права з різною долею при скасуванні підписки.
    # `presence_limit` без обмеження не буває; None тут означає лише
    # «підписки немає», і тоді залишок теж None.
    presence_used: int = 0
    presence_limit: int | None = 0
    presence_remaining: int | None = 0
    presence_credits_available: int = 0


class AccountOut(BaseModel):
    organization: AccountOrganizationOut
    role: str
    plan: PlanOut
    # Стан оплати одним словом, уже розвʼязаний із статусу підписки та
    # прапорця скасування. Інтерфейс не складає їх сам.
    billing_state: BillingState = BillingState.FREE
    subscription: SubscriptionOut | None = None
    # Розвʼязані права: дефолт → тариф → індивідуальні винятки.
    # Значення, які справді діють, а не сирий JSONB тарифу.
    entitlements: dict[str, Any] = Field(default_factory=dict)
    usage: UsageOut


__all__ = [
    "AccountOrganizationOut",
    "AccountOut",
    "PlanOut",
    "SubscriptionOut",
    "UsageOut",
]
