"""Публічний каталог тарифів — контракт сторінки цін.

Окремий від внутрішніх прав навмисно. `Plan.entitlements` — це ключі, за
якими код ухвалює рішення: `max_pages_per_audit`, `schedule_min_interval_hours`,
`semantic_analysis`. Віддати їх сторінці цін означало б зробити контрактом
маркетингового сайту наш внутрішній словник — і будь-яке перейменування
ключа чи поява нового ліміту ставали б зміною публічної сторінки.

Тут інше: перелік того, що клієнт **купує**, людськими словами. Ключ
права може змінитися, не зачепивши жодного рядка нижче; рядок нижче може
змінитися, не зачепивши жодної перевірки в коді.

Ціни живуть у провайдера — тут лише показове значення (`PlanPrice`
пояснює, чому воно взагалі є). Порожня ціна — не нуль, а «зв'яжіться з
нами»: намалювати нуль означало б назвати платний тариф безкоштовним.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PlanPriceOut(BaseModel):
    """Ціна тарифу в одній валюті за один період — лише для показу.

    Сума в **мінімальних одиницях** валюти, а показник каже, скільки їх
    у одиниці: 4900 при показнику 2 — це 49.00, при показнику 0 — це
    4900. Без показника клієнт ділив би на сто, і 4900 єн ставали б
    сорока девʼятьма.

    `amount_minor` порожній — ціни ще не завели. Сторінка має показати
    заклик звʼязатися, а не нуль: нуль назвав би платний тариф
    безкоштовним.

    Списання цим числом не робиться ніколи: суму визначає прайс
    провайдера.
    """

    currency: str
    interval: str  # month | year
    amount_minor: int | None = None
    # Знаків після коми в цій валюті (ISO 4217).
    exponent: int = 2


class PlanFeatureOut(BaseModel):
    """Рядок переліку можливостей.

    `label_key` — ключ каталогу i18n, `label` — уже відрендерений текст
    мовою запиту. Обидва навмисно: сторінка малює `label`, а майбутній
    статичний генератор або інший клієнт може перекласти сам за ключем,
    не чекаючи на нашу мову.

    `included` розводить «є в тарифі» й «немає»: перелік з обома видами
    рядків продає краще за перелік лише з наявним, бо показує різницю
    між тарифами.
    """

    label_key: str
    label: str
    included: bool = True


class PublicPlanOut(BaseModel):
    """Тариф очима того, хто ще не клієнт."""

    code: str
    name: str
    description: str = ""
    # Що клієнт КУПУЄ, у структурованому вигляді для картки цін:
    # кількість перевірок на місяць (None + unlimited=True — безліміт;
    # None + False — не сконфігуровано) і скільки перевірок Actual AI
    # Presence ВКЛЮЧЕНО. Це показ, не права: резолвер прав читає
    # entitlements, а не ці поля.
    analyses_per_month: int | None = None
    analyses_unlimited: bool = False
    presence_checks_per_month: int = 0
    # Порядок показу. Іде з бекенда, щоб сторінка не сортувала за ціною й
    # не переставляла тарифи місцями при першій же зміні.
    sort_order: int = 0
    # Тариф, який ми рекомендуємо. Один на каталог або жодного.
    highlighted: bool = False

    prices: list[PlanPriceOut] = Field(default_factory=list)
    # Обмеження людськими словами: «до 100 сторінок на аудит», а не
    # `max_pages_per_audit: 100`.
    limits: list[PlanFeatureOut] = Field(default_factory=list)
    features: list[PlanFeatureOut] = Field(default_factory=list)

    # Що робить кнопка. `available=False` — тариф показуємо, але купити
    # зараз не можна (наприклад, тільки за домовленістю).
    cta_key: str
    cta_label: str
    available: bool = True


class PlanCatalogOut(BaseModel):
    """Каталог цілком. Мова відповіді — поруч, а не здогадкою клієнта."""

    locale: str
    plans: list[PublicPlanOut] = Field(default_factory=list)


__all__ = ["PlanCatalogOut", "PlanFeatureOut", "PlanPriceOut", "PublicPlanOut"]
