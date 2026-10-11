"""Внутрішні права → публічний каталог тарифів.

Живе в `application`, а не в `billing`, і це не дрібниця: переклад
потребує каталогу i18n, а білінгу заборонено сягати двигуна аудиту —
там лежать не лише чеки, а й словник мов. Тест меж це спіймав і мав
рацію: білінг, який знає про мови продукту, наступного разу знатиме й
про чеки.

Єдине місце, де внутрішній словник прав перекладається на те, що клієнт
купує. Мапа нижче і є межею: додати право — не означає змінити сторінку
цін, перейменувати рядок на сторінці — не означає торкнутися жодної
перевірки в коді.

Права, яких немає в мапі, на сторінку не потрапляють, і це навмисно.
Внутрішній ліміт на кшталт `schedule_min_interval_hours` клієнту нічого
не каже — він каже нам, як часто дозволено запускати; продавати його
рядком «мінімальний інтервал 24 години» означало б рекламувати обмеження
замість можливості.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.audit.i18n import COMPLETE_LOCALES, Locale, catalog
from app.billing import money
from app.models.billing import Plan, PlanPrice
from app.schemas.catalog import PlanFeatureOut, PlanPriceOut, PublicPlanOut

# Мови, якими написаний публічний сайт, — вони ж мови клієнтського
# комерційного тексту. Той самий набір, що COMPLETE_LOCALES звітів:
# сторінка цін існує рівно цими шістьма мовами.
PUBLIC_TEXT_LOCALES: tuple[str, ...] = tuple(
    sorted(locale.value for locale in COMPLETE_LOCALES)
)


def localized_text(
    default: str, i18n: dict[str, object] | None, locale: Locale
) -> str:
    """Клієнтський напис мовою запиту.

    Порожня мапа — універсальна назва: дефолтне поле і є написом для
    всіх мов (єдина поведінка старих записів, без вигаданих перекладів).
    Непорожня мапа публічного запису покриває всі шість мов — це
    гарантує валідація адмін-маршруту, тож фолбек тут лише страхує
    неактивні чернетки й ніколи не підмінює мову публічній вітрині.
    """
    if not i18n:
        return default
    value = i18n.get(locale.value)
    return value if isinstance(value, str) and value else default


def missing_text_locales(i18n: dict[str, object] | None) -> list[str]:
    """Яких мов бракує в НЕПОРОЖНІЙ мапі. Порожня мапа — не прогалина,
    а явний вибір універсальної назви, тому для неї відповідь порожня."""
    if not i18n:
        return []
    return [
        locale for locale in PUBLIC_TEXT_LOCALES
        if not (isinstance(i18n.get(locale), str) and i18n.get(locale))
    ]


# Тариф, який показуємо як рекомендований. Один на каталог або жодного.
# Порожньо: на запуску місячний тариф один, і рекомендувати нема з-поміж
# чого. Колишнє "pro" належало вітринним рівням dev-сіда, знятим 0045.
HIGHLIGHTED = ""

# Безкоштовний тариф не «підключають» — з нього починають.
FREE_CODE = "free"


@dataclass(frozen=True, slots=True)
class _Limit:
    """Числовий ліміт і як його назвати, зокрема коли він безмежний."""

    key: str
    unlimited_key: str | None = None


# Ліміти в порядку показу. Порядок тут, а не в сортуванні на клієнті:
# перелік мусить читатися однаково в усіх тарифах, щоб їх можна було
# порівняти рядок навпроти рядка.
_LIMITS: list[tuple[str, _Limit]] = [
    ("audits_per_period", _Limit("plan.limit.audits", "plan.limit.audits_unlimited")),
    ("max_pages_per_audit", _Limit("plan.limit.pages")),
    ("sites_limit", _Limit("plan.limit.sites", "plan.limit.sites_unlimited")),
    # `scheduled_audits` тут немає навмисно: запланованих аудитів немає
    # в затвердженому першому випуску, і публічний каталог тарифів не
    # сміє рекламувати незбудовану можливість — жодною з шести мов.
    # Право в entitlements лишається як є; це рішення про вітрину.
    ("team_members", _Limit("plan.limit.team")),
    ("history_retention_days", _Limit("plan.limit.history", "plan.limit.history_unlimited")),
]

# Булеві можливості в порядку показу.
_FEATURES: list[tuple[str, str]] = [
    ("semantic_analysis", "plan.feature.semantic"),
    ("report_download", "plan.feature.reports"),
    ("public_reports", "plan.feature.public_reports"),
    ("api_access", "plan.feature.api"),
    ("white_label", "plan.feature.white_label"),
]


def public_plan(plan: Plan, prices: list[PlanPrice], locale: Locale) -> PublicPlanOut:
    """Один тариф у публічному вигляді."""
    values = dict(plan.entitlements or {})
    # Структуровані величини для картки цін. `audits_per_period: null` у
    # правах означає безліміт; відсутній ключ — не сконфігуровано, і
    # картка чесно не покаже числа. Присутність безлімітною не буває.
    audits_value = values.get("audits_per_period")
    return PublicPlanOut(
        code=plan.code,
        name=localized_text(plan.name, plan.name_i18n, locale),
        description=localized_text(
            plan.description, plan.description_i18n, locale),
        analyses_per_month=(
            int(audits_value) if isinstance(audits_value, int) else None
        ),
        analyses_unlimited=(
            "audits_per_period" in values and audits_value is None
        ),
        presence_checks_per_month=int(
            values.get("presence_per_period") or 0
        ),
        sort_order=plan.sort_order,
        highlighted=plan.code == HIGHLIGHTED,
        prices=[
            PlanPriceOut(
                currency=price.currency,
                interval=price.interval,
                amount_minor=price.display_amount_minor,
                exponent=money.exponent(price.currency),
            )
            for price in sorted(prices, key=lambda p: (p.interval, p.currency))
        ],
        limits=[
            _limit_line(values.get(key), rule, locale)
            for key, rule in _LIMITS
            if key in values
        ],
        features=[
            PlanFeatureOut(
                label_key=label,
                label=catalog(label, locale=locale),
                included=bool(values.get(key)),
            )
            for key, label in _FEATURES
            if key in values
        ],
        cta_key=_cta_key(plan, prices),
        cta_label=catalog(_cta_key(plan, prices), locale=locale),
        available=plan.code == FREE_CODE or bool(prices),
    )


def _limit_line(value: object, rule: _Limit, locale: Locale) -> PlanFeatureOut:
    """`None` у ліміті означає «без обмеження», а не нуль.

    Плутанина тут коштувала б дорого в обидва боки: «0 аудитів» на
    найдорожчому тарифі або «необмежено» на безкоштовному.
    """
    if value is None and rule.unlimited_key:
        return PlanFeatureOut(
            label_key=rule.unlimited_key,
            label=catalog(rule.unlimited_key, locale=locale),
        )
    count = 0 if value is None else int(value)
    return PlanFeatureOut(
        label_key=rule.key,
        label=catalog(rule.key, {"count": count}, locale=locale),
        included=count > 0,
    )


def _cta_key(plan: Plan, prices: list[PlanPrice]) -> str:
    if plan.code == FREE_CODE:
        return "plan.cta.start_free"
    return "plan.cta.subscribe" if prices else "plan.cta.contact"


__all__ = ["FREE_CODE", "HIGHLIGHTED", "public_plan"]
