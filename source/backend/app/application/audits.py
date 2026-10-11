"""Use case: запустити аудит.

Тут збирається все, що не є ні аудитом, ні білінгом, ні автентифікацією
окремо. Порядок кроків — це і є продукт:

1. хто це й чи його це організація (шар вище вже відповів);
2. чи дозволяє тариф;
3. чи лишилась квота — і списати її атомарно;
4. обрізати опції до дозволених;
5. створити запис;
6. поставити в чергу.

Двигун аудиту не бере участі в жодному з перших чотирьох кроків і не
знає, що вони існують. Він отримує вже валідний запит із уже дозволеними
опціями — «ось що можна зробити, зроби».
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.application import options as options_policy
from app.application.options import OptionAdjustment
from app.audit.enums import AuditTrigger
from app.billing import credits, quota, refund_policy
from app.billing import service as billing
from app.billing.entitlements import EntitlementSet
from app.core.run_enums import FailureClass, QuotaSource, QuotaState
from app.models.audit import Audit
from app.schemas.audit import AuditCreate
from app.services import audit_service
from app.sites import service as sites


class NotAllowed(Exception):
    """Дію не дозволяє тариф або вичерпана квота.

    `reason` — ключ для i18n, а не готовий текст: рішення про мову
    належить шару, який відповідає клієнту.
    """

    def __init__(self, reason: str, *, limit: int | None = None, used: int | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.limit = limit
        self.used = used


@dataclass(frozen=True, slots=True)
class StartedAudit:
    """Що сталося. `queued` False означає, що чергу не вдалося сповістити."""

    audit: Audit
    entitlements: EntitlementSet
    quota_used: int
    quota_limit: int | None
    # Що тариф змінив у запиті. Порожньо означає «нічого» — і це теж
    # відповідь: звіт може чесно сказати, що обмежень не було.
    adjustments: list[OptionAdjustment] = field(default_factory=list)


def _trim_options(
    payload: AuditCreate, ent: EntitlementSet
) -> tuple[AuditCreate, list[OptionAdjustment]]:
    """Опції, обрізані до дозволених, і перелік того, що змінилося.

    Саме так права потрапляють у двигун. Він не питає про тариф — він
    отримує `max_pages`, який уже не перевищує дозволеного, і `llm`,
    який уже вимкнено, якщо семантика не входить у тариф.

    Обрізання, а не відмова: клієнт просив 100 сторінок і отримає 25 —
    це робота, яку ми можемо зробити, а відмовити повністю означало б не
    зробити нічого через те, що не можемо зробити все.

    Але мовчазним воно лишається тільки для виконання. Що саме обрізав
    тариф, повертається окремо й зберігається поруч із аудитом: інакше
    через місяць ні клієнт, ні ми не пояснимо, чому звіт неповний.
    """
    # Беремо лише ті опції, які політика взагалі може змінити. Повний
    # dump тут був би помилкою: він перетворює enum'и на рядки, і
    # зворотний `model_copy` поклав би в модель уже не те, що там було.
    watched = options_policy.watched_keys()
    requested = {key: getattr(payload.options, key, None) for key in watched}
    effective, adjustments = options_policy.apply(requested, ent)
    changed = {key: value for key, value in effective.items() if value != requested.get(key)}
    trimmed = payload.model_copy(
        update={"options": payload.options.model_copy(update=changed)}
    )
    return trimmed, adjustments


async def start_audit(
    db: AsyncSession,
    payload: AuditCreate,
    *,
    organization_id: uuid.UUID,
    created_by_user_id: uuid.UUID | None,
    trigger: AuditTrigger = AuditTrigger.MANUAL,
    site_id: uuid.UUID | None = None,
    schedule_id: uuid.UUID | None = None,
    scheduled_for: datetime | None = None,
    free_preview: bool = False,
) -> StartedAudit:
    """Створити аудит, списавши квоту. Постановку в чергу робить викликач.

    Черга навмисно лишається зовні: запис у базі й повідомлення брокера —
    дві різні системи, і склеювати їх усередині однієї функції означає
    вирішувати, що робити, коли впала друга, у місці, яке про це нічого
    не знає.

    `free_preview` — безкоштовне превʼю: результат показується коротким
    виглядом, повний відкриває окрема покупка САМЕ цього аудиту. Такий
    запуск не торкається ані квоти періоду, ані куплених одиниць —
    превʼю необмежені за рішенням продукту, і від зловживання боронить
    технічний ліміт частоти на маршруті, а не комерційні права. Опції
    при цьому так само обрізаються тарифом організації: обсяг читання —
    поведінка продукту, а не наділ.
    """
    ent = await billing.for_organization(db, organization_id=organization_id)

    source = QuotaSource.FREE_PREVIEW
    quota_used = 0
    quota_limit: int | None = None
    if not free_preview:
        subscription = await billing.active_subscription(
            db, organization_id=organization_id
        )
        period = quota.period_for(subscription)

        decision = await quota.consume(
            db,
            organization_id=organization_id,
            period=period,
            limit=ent.limit("audits_per_period"),
        )
        # Порядок оплати: спершу те, що вже входить у тариф, і лише потім
        # куплене окремо. Зворотний порядок витрачав би кредити клієнта,
        # поки в нього ще лишається квота періоду.
        source = QuotaSource.SUBSCRIPTION
        if not decision.allowed:
            if await credits.balance(db, organization_id=organization_id) <= 0:
                raise NotAllowed(
                    decision.reason or "quota.exhausted",
                    limit=decision.limit,
                    used=decision.used,
                )
            source = QuotaSource.ONE_OFF
        quota_used = decision.used
        quota_limit = decision.limit

    trimmed, adjustments = _trim_options(payload, ent)
    audit = await audit_service.create_audit(
        db,
        trimmed,
        organization_id=organization_id,
        site_id=site_id,
        created_by_user_id=created_by_user_id,
        trigger=trigger,
        schedule_id=schedule_id,
        scheduled_for=scheduled_for,
        requested_options=payload.options.model_dump(mode="json"),
    )
    audit.quota_source = source

    if free_preview:
        # Резерву не було — і завершувати нічого: стан закривається
        # одразу, щоб `settle_quota` не мав що повертати. CONSUMED тут
        # означає «долю вирішено», а не «щось списано»: жоден лічильник
        # цим аудитом не рухався.
        audit.quota_state = QuotaState.CONSUMED

    if source is QuotaSource.ONE_OFF:
        # Резерв — тут, а не до створення: кредит належить конкретному
        # аудиту, і без його ідентифікатора повернути потім **той самий**
        # кредит було б неможливо. Якщо між перевіркою балансу й цим
        # рядком кредит забрав паралельний запит, транзакція
        # відкочується разом зі щойно створеним аудитом.
        if await credits.reserve(
            db, organization_id=organization_id, audit_id=audit.id
        ) is None:
            raise NotAllowed(
                "quota.exhausted", limit=quota_limit, used=quota_used
            )

    return StartedAudit(
        audit=audit,
        entitlements=ent,
        quota_used=quota_used,
        quota_limit=quota_limit,
        adjustments=adjustments,
    )


async def release_quota(db: AsyncSession, *, organization_id: uuid.UUID) -> None:
    """Повернути квоту за аудит, який так і не почався з нашої вини."""
    subscription = await billing.active_subscription(db, organization_id=organization_id)
    await quota.release(db, organization_id=organization_id, period=quota.period_for(subscription))


async def settle_quota(
    db: AsyncSession, audit: Audit, *, failure: FailureClass | None = None
) -> QuotaState:
    """Завершити резерв: списати остаточно або повернути.

    Викликається рівно один раз на аудит, у момент, коли він дійшов до
    кінцевого стану. Повторний виклик нічого не робить — інакше повтор
    задачі повертав би квоту вдруге.

    Рішення ухвалює `billing.refund_policy`, а не цей код: машина станів
    веде резерв до кінця, політика каже, до якого саме. Змінити політику
    можна налаштуванням, не чіпаючи нічого тут.
    """
    if audit.quota_state is not QuotaState.RESERVED:
        return audit.quota_state

    audit.failure_class = failure
    refundable = refund_policy.is_refundable(failure)
    one_off = audit.quota_source is QuotaSource.ONE_OFF

    if refundable:
        # Повертаємо в те саме відро, з якого брали. Кредит повертається
        # той самий — не абстрактна одиниця в баланс: він належить
        # конкретній покупці, і при поверненні коштів за неї має
        # відкликатися саме він.
        if one_off:
            await credits.release(db, audit_id=audit.id)
        else:
            await release_quota(db, organization_id=audit.organization_id)
        audit.quota_state = QuotaState.RELEASED
    else:
        if one_off:
            await credits.consume(db, audit_id=audit.id)
        audit.quota_state = QuotaState.CONSUMED
    return audit.quota_state


async def ensure_site(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    url: str,
    created_by_user_id: uuid.UUID | None,
    ent: EntitlementSet,
) -> uuid.UUID | None:
    """Сайт для цієї адреси: наявний або новий, якщо тариф дозволяє.

    Аудит без сайту лишається можливим — CLI й разові перевірки нікуди
    не діваються. Але коли сайт є, історія й розклад мають до чого
    прив'язатися.
    """
    try:
        origin = sites.normalize_origin(url)
    except ValueError:
        return None

    existing = await sites.find_by_origin(db, organization_id=organization_id, origin=origin)
    if existing is not None:
        return existing.id

    limit = ent.limit("sites_limit")
    if limit is not None:
        used = await sites.count_active(db, organization_id=organization_id)
        if used >= limit:
            # Ліміт сайтів не має блокувати сам аудит: людина просила
            # перевірити адресу, а не завести сайт. Аудит виконається
            # без прив'язки, і в історію він просто не потрапить.
            return None

    view = await sites.create(
        db,
        organization_id=organization_id,
        url=origin,
        created_by_user_id=created_by_user_id,
    )
    return view.id


async def ensure_site_for(
    db: AsyncSession,
    *,
    organization_id: uuid.UUID,
    url: str,
    created_by_user_id: uuid.UUID | None,
) -> uuid.UUID | None:
    """`ensure_site`, який сам дістає права.

    Викликачу не треба знати, що для створення сайту потрібен тариф:
    він знає адресу й організацію, решта — робота цього шару.
    """
    ent = await billing.for_organization(db, organization_id=organization_id)
    return await ensure_site(
        db,
        organization_id=organization_id,
        url=url,
        created_by_user_id=created_by_user_id,
        ent=ent,
    )
