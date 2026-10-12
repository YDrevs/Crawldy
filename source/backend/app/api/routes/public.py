"""Анонімна воронка: аудит без реєстрації, короткий вигляд, розблокування.

Третій роутер без `X-API-Key`. Право тут доводиться **спроможністю** —
токеном гостьової сесії, — а не особою: акаунта в гостя немає й не
вимагається.

## Номер в адресі нічого не відкриває

Ідентифікатор аудиту стоїть у шляху, бо він називає ресурс. Доступ дає
заголовок із токеном сесії, якого немає в базі у відкритому вигляді.
Перебір номерів не дає нічого — не через те, що вони випадкові, а через
те, що вони не є доказом права.

## Обмеження частоти йде перед усім

Залежність `_rate_limited` стоїть на створенні сесії й на запуску
аудиту. Це не оздоблення: краул коштує грошей і трафіку чужому серверу,
і анонімний запуск без лічильника — це наш ресурс, відданий кожному.

## Оплата не робиться тут

`checkout` створює намір і віддає адресу каси. Повний вигляд відкриває
**перевірена подія провайдера**, яка приходить у `/v1/webhooks/{provider}`
і більше нізвідки. Повернення браузера з каси показує сторінку, і лише.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.api.deps import SessionDep, auth_rate_limited, client_ip
from app.application import audits as audits_app
from app.application import guest as guest_app
from app.application import purchases as purchases_app
from app.audit.enums import AuditStatus, AuditTrigger
from app.audit.i18n import DEFAULT_LOCALE, parse
from app.billing import catalog as billing_catalog
from app.billing.enums import PurchaseStatus
from app.core import runtime_config as runtime
from app.core.config import settings
from app.core.ratelimit import RateLimiter
from app.identity.passwords import WeakPassword
from app.schemas.audit import AuditCreate
from app.schemas.presence import (
    GuestPresenceOut,
    GuestPresenceRunIn,
    PresenceRunOut,
    PresenceSuggestionOut,
)
from app.schemas.result import (
    GuestAuditStatusOut,
    GuestShortReportOut,
    InspectedPageOut,
    failure_fields,
)
from app.services import audit_service
from app.worker.queue import enqueue_audit, enqueue_presence

router = APIRouter(prefix="/v1/public", tags=["public"])

PRIVATE_HEADERS = {
    "X-Robots-Tag": "noindex, nofollow, noarchive",
    "Cache-Control": "no-store, private",
    "Referrer-Policy": "no-referrer",
}

CAPABILITY_HEADER = "X-Guest-Token"

REPORTABLE = {AuditStatus.COMPLETED, AuditStatus.PARTIAL}
# Термінальні стани, які звіту не дали. Обидва несуть `failure_class`:
# `FAILED` — прогін почався й не дійшов; `SKIPPED` ставить
# `application/scheduled.py::_record_skip`, і разом із ним
# `FailureClass.CANCELLED`, коли вичерпано квоту. Стани, що ще тривають,
# сюди не входять: поле про невдачу в аудиті, який виконується, було б
# твердженням про те, чого ще не сталося.
_TERMINAL_FAILURES = {AuditStatus.FAILED, AuditStatus.SKIPPED}
# Поля, яких у НЕтермінальній відповіді немає ВЗАГАЛІ — не `null`.
#
# Різниця не косметична. Фронт оголошує `failure_reason?: string`, тобто
# `string | undefined`; `null` там — інший тип, і `?.trim()` на ньому
# падає не там, де його ловлять. Ключ, якого немає, читається як
# «невідомо»; ключ зі значенням `null` читається як «відомо, що нічого»,
# а це різні твердження про аудит, який ще виконується.
#
# `exclude_none` тут НЕ годиться: він прибрав би будь-яке порожнє поле,
# тобто зробив би форму відповіді залежною від даних. Ці два — названі.
_FAILURE_FIELDS = frozenset({"failure_class", "failure_reason"})


# ── обмеження частоти ──────────────────────────────────────────────────────


def _limiter(request: Request) -> RateLimiter:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:  # pragma: no cover — ставиться в lifespan
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="сервіс недоступний"
        )
    return limiter  # type: ignore[no-any-return]


def _limit_for(path: str) -> int:
    """Скільки звернень на годину дозволено цьому маршруту.

    Один виняток, і він про повторне відкриття ВЛАСНОЇ каси: воно віддає
    ту саму покупку й ту саму транзакцію, тобто нічого не створює.
    Спільна десятка тут означала б, що людина, яка закрила вікно оплати
    кілька разів, не може заплатити ще годину.
    """
    if path.endswith("/orders"):
        return settings.checkout_rate_limit
    return settings.public_rate_limit


async def _rate_limited(request: Request) -> None:
    """Порахувати спробу за адресою клієнта й відмовити понад норму."""
    limiter = _limiter(request)
    ip = client_ip(request)
    decision = await limiter.check(
        f"public:{request.url.path}:{ip}",
        limit=_limit_for(request.url.path),
        window=settings.public_rate_window_seconds,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="забагато запитів",
            headers={"Retry-After": str(decision.reset_after)},
        )


RateLimited = Depends(_rate_limited)


# ── спроможність ───────────────────────────────────────────────────────────


async def _capability(
    session: SessionDep,
    x_guest_token: Annotated[str | None, Header()] = None,
) -> guest_app.GuestSession:
    """Гостьова сесія з заголовка. Будь-яка невдача — однаковий 404.

    Прострочення, відкликання й неіснуючий токен не розрізняються
    назовні: інакше сторонній перебором зʼясував би, які токени існували.
    """
    if not x_guest_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    try:
        return await guest_app.resolve(session, x_guest_token)
    except guest_app.GuestError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено") from exc


CapabilityDep = Annotated[guest_app.GuestSession, Depends(_capability)]


# ── схеми ──────────────────────────────────────────────────────────────────


class GuestSessionOut(BaseModel):
    """Відкритий токен віддається один раз — тут, і більше ніде."""

    token: str
    expires_at: str


class PublicAuditCreate(BaseModel):
    """Запуск гостем. Лише адреса — більше ми нічого не питали."""

    url: str = Field(min_length=4, max_length=2048)


class PublicAuditOut(BaseModel):
    audit_id: uuid.UUID
    status: str
    unlocked: bool


class CheckoutOut(BaseModel):
    """Намір оплати. Не доказ і не право."""

    purchase_intent: str
    checkout_url: str
    audit_id: uuid.UUID
    # Публічний за задумом провайдера токен для його ж скрипта в
    # браузері. Ключ API сюди не потрапляє ніколи — ним підписуються
    # серверні виклики, і він єдиний, хто вміє створювати транзакції.
    client_token: str = ""
    provider: str = ""
    # Транзакція провайдера. Накладна каса Paddle відкривається саме за
    # нею, тож браузер її знати мусить. Правом вона не є: повний звіт
    # відкриває перевірена подія, звірена з нашим записом покупки.
    transaction_ref: str = ""
    # sandbox | live — скрипт провайдера мусить знати, куди він ходить.
    environment: str = ""


class OrderOut(BaseModel):
    """Намір оплати без аудиту. Не доказ і не право.

    Те саме, що `CheckoutOut`, але без `audit_id`: у цій воронці аудиту
    ще не існує — його адресу ми питаємо ПІСЛЯ оплати.
    """

    purchase_id: uuid.UUID
    checkout_url: str
    client_token: str = ""
    provider: str = ""
    transaction_ref: str = ""
    environment: str = ""


class OrderStateOut(BaseModel):
    """Що сталося з цією покупкою — і що з неї вже витрачено.

    `state` — наші записи про гроші. `started_audit_id` — аудит, на який
    покупку витрачено; поки його немає, покупець ще не назвав сайту, і
    екран мусить показати форму, а не «готово».
    """

    purchase_id: uuid.UUID
    state: str
    charged: bool | None = None
    started_audit_id: uuid.UUID | None = None
    presence_available: int = 0


class PaidAuditCreate(BaseModel):
    """Сайт, названий уже після оплати."""

    url: str = Field(min_length=4, max_length=2048)


class CheckoutConfigOut(BaseModel):
    """Те, що браузеру потрібно знати про провайдера, — і рівно це.

    Обидва значення публічні за задумом Paddle: клієнтський токен він
    сам призначив для сторінки, а оточення видно з адрес, куди та
    сторінка ходить. Ключ API і секрет вебхука сюди не потрапляють
    ніколи — ними підписуються серверні виклики.

    Значення приходять із бекенда, а не з `NEXT_PUBLIC_*`, щоб
    конфігурація провайдера жила в одному місці. Дві копії розійшлися б
    рівно там, де це найдорожче: пісочниця проти бойового.
    """

    provider: str
    environment: str
    client_token: str


class PaymentStateOut(BaseModel):
    """Чесна відповідь сторінці повернення з каси.

    `state` — що ми знаємо про гроші; `unlocked` — чи можна читати
    повний звіт. Вони розходяться в реальному стані «оплачено, доступ
    ще не видано», і зливати їх в одне поле означало б або обіцяти
    звіт, якого ще немає, або назвати оплату неоплаченою.

    `charged` — чи списано кошти: `True`/`False` — відомо, `None` — ні.
    Окремо від `state`, бо «обробляємо» покриває і «заплатив, подія в
    дорозі», і «закрив касу, не заплативши», а екран мусить розвести
    їх: інакше він або обіцяє «не списано» тому, хто заплатив, або
    тримає в очікуванні того, хто передумав.
    """

    audit_id: uuid.UUID
    state: str
    unlocked: bool
    charged: bool | None = None


# ── маршрути ───────────────────────────────────────────────────────────────


@router.post(
    "/sessions",
    response_model=GuestSessionOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RateLimited],
)
async def open_session(request: Request, session: SessionDep) -> GuestSessionOut:
    """Відкрити гостьову сесію: організація без учасників плюс спроможність."""
    opened = await guest_app.open_session(
        session, ip=client_ip(request), ip_salt=settings.ip_hash_salt
    )
    await session.commit()
    return GuestSessionOut(
        token=opened.token, expires_at=opened.session.expires_at.isoformat()
    )


@router.post(
    "/audits",
    response_model=PublicAuditOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[RateLimited],
)
async def start_audit(
    payload: PublicAuditCreate,
    capability: CapabilityDep,
    session: SessionDep,
) -> PublicAuditOut:
    """Запустити безкоштовне превʼю від імені гостьової організації.

    Той самий `application.start_audit`, що й у кабінеті, але в режимі
    превʼю: комерційні лічильники не торкаються — превʼю необмежені за
    рішенням продукту, і та сама сесія може запускати їх скільки треба.
    Від зловживання боронить технічний ліміт частоти вище — окремий від
    прав шар, який каже «забагато запитів», а не «квоту вичерпано».

    Привласнена організація нового не створює: старий токен після
    створення акаунта чи злиття інакше лишався б чорним ходом — запускав
    би аудити від імені людини. Читання при цьому не обмежується.
    """
    try:
        await guest_app.ensure_active_guest(session, capability)
    except guest_app.AlreadyClaimed as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"reason": "already.claimed"}
        ) from exc
    try:
        started = await audits_app.start_audit(
            session,
            AuditCreate(url=payload.url),
            organization_id=capability.organization_id,
            created_by_user_id=None,
            trigger=AuditTrigger.MANUAL,
            # Сайт створюється й гостю: на ньому тримається історія після
            # привласнення, і саме його origin звіряється при злитті.
            site_id=await audits_app.ensure_site_for(
                session,
                organization_id=capability.organization_id,
                url=payload.url,
                created_by_user_id=None,
            ),
            free_preview=True,
        )
    except audits_app.NotAllowed as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"reason": exc.reason},
        ) from exc

    await session.commit()
    try:
        await enqueue_audit(started.audit.id)
    except Exception as exc:
        await audit_service.mark_failed(session, started.audit.id, f"черга недоступна: {exc}")
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="черга недоступна, спробуйте пізніше",
        ) from exc

    return PublicAuditOut(
        audit_id=started.audit.id, status=started.audit.status, unlocked=False
    )


@router.get(
    "/audits/{audit_id}",
    response_model=GuestAuditStatusOut | GuestShortReportOut,
)
async def read_audit(
    audit_id: uuid.UUID,
    capability: CapabilityDep,
    session: SessionDep,
    lang: str = "",
) -> Response:
    """Стан аудиту й короткий вигляд, коли він готовий.

    Поки аудит виконується — лише статус. Готовий — коротка проєкція:
    бали, покриття, причини відсутності даних і перелік «що робити
    першим». Повний вигляд ця відповідь не віддає ніколи, навіть після
    оплати: для нього окремий маршрут і окрема схема.

    `lang` обовʼязковий саме тут, а не в налаштуваннях: мову сторінки
    знає лише сторінка. Без нього документ складався мовою за
    замовчуванням, і український екран показував англійські знахідки —
    підписи наші, а текст проблем чужий.
    """
    if not await guest_app.owns_audit(session, session=capability, audit_id=audit_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")

    audit = await audit_service.get_audit(session, audit_id)
    if audit is None:  # pragma: no cover — власність уже перевірено
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")

    unlocked = await guest_app.is_unlocked(session, audit_id)
    if AuditStatus(audit.status) not in REPORTABLE:
        # Хід іде поруч зі статусом, а не замість нього: екран очікування
        # мусить лишитися чесним, коли чисел ще немає. Порожній словник —
        # звичайний стан, а не збій: до першої хвилі краулу писати нічого,
        # а при кількох цілях ми не пишемо взагалі.
        #
        # E-13: чому не вийшло — класом і безпечним реченням.
        #
        # Клас додається лише термінальній невдачі: аудит, який іще
        # виконується, не має поля про невдачу, бо вона ще не сталася, і
        # порожнє поле поруч із «виконується» читалося б як натяк.
        #
        # Сире `audit.error` не потрапляє сюди ніколи. Воно лишається там,
        # де вже було: у кабінеті, за автентифікацією. Гість отримує
        # наслідок, а не діагностику.
        state = AuditStatus(audit.status)
        terminal = state in _TERMINAL_FAILURES
        # Клас і речення беруться ОДНИМ рішенням. Порожня або нерозпізнана
        # колонка стає `internal_error` разом зі своїм реченням — раніше
        # нормалізувався лише текст, і аудит без класу віддавав
        # `failure_class: null` поруч із поясненням про внутрішню помилку.
        failure_class, reason = (
            failure_fields(audit.failure_class, parse(lang)) if terminal else (None, None)
        )
        return _json_response(
            GuestAuditStatusOut(
                audit_id=str(audit_id),
                status=state,
                unlocked=unlocked,
                progress=audit.progress or {},
                failure_class=failure_class,
                failure_reason=reason,
            ).model_dump(mode="json", exclude=None if terminal else set(_FAILURE_FIELDS))
        )

    # Друга гілка тієї самої відповіді, і вона теж мусить пройти через свою
    # модель. `_json_response` віддає готовий `Response`, а FastAPI при
    # цьому пропускає валідацію `response_model` — отже, оголошена схема
    # гарантує форму лише доти, доки її гарантує цей рядок. Нижче саме він:
    # словник валідується, і серіалізується вже перевірена модель.
    short = guest_app.short_view(audit, unlocked=unlocked, locale=parse(lang))
    return _json_response(GuestShortReportOut.model_validate(short).model_dump(mode="json"))


@router.get("/audits/{audit_id}/full")
async def read_full(
    audit_id: uuid.UUID,
    capability: CapabilityDep,
    session: SessionDep,
    lang: str = "",
) -> Response:
    """Повний звіт. Лише після розблокування.

    Мова та сама, що в короткому вигляді: один аудит не має говорити
    двома мовами залежно від того, заплатили за нього чи ні.

    Відсутність права — 402, а не 404: ресурс існує, і людина про нього
    знає, бо щойно бачила короткий вигляд. Ховати його тут було б
    не безпекою, а плутаниною.
    """
    if not await guest_app.owns_audit(session, session=capability, audit_id=audit_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    if not await guest_app.is_unlocked(session, audit_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="повний звіт не відкрито"
        )

    audit = await audit_service.get_audit(session, audit_id)
    if audit is None or AuditStatus(audit.status) not in REPORTABLE:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    payload = guest_app.full_view(audit, locale=parse(lang))
    # E-14: які саме сторінки ми відкривали — лише тут, за оплатою.
    #
    # Уся політика (межа, порядок, collation, розвʼязання нічиїх, повне
    # число) належить застосунковому шару; маршрут отримує готовий DTO і
    # лише вдягає його у схему відповіді. Ані моделі, ані шару звіту він
    # для цього не торкається.
    inspected = await guest_app.pages_for(session, audit_id)
    payload.update(
        {
            "inspected_pages": [
                InspectedPageOut(url=page.url, status=page.status, depth=page.depth,
                                 read=page.read).model_dump(mode="json")
                for page in inspected.pages
            ],
            "inspected_pages_total": inspected.total,
            "inspected_pages_truncated": inspected.truncated,
        }
    )
    return _json_response(payload)


@router.post("/audits/{audit_id}/checkout", response_model=CheckoutOut, dependencies=[RateLimited])
async def checkout(
    audit_id: uuid.UUID,
    capability: CapabilityDep,
    session: SessionDep,
) -> CheckoutOut:
    """Відкрити касу на повний вигляд цього аудиту.

    Покупка створюється ДО каси й лишається PENDING: саме її
    ідентифікатор ми віддаємо провайдеру, і саме з нашого запису
    береться аудит, коли приходить перевірена подія.

    Ціни тут немає й не буде: вона живе в прайсі провайдера. Назвати
    суму тут означало б мати два джерела правди про гроші.

    Повторний виклик віддає ту саму покупку — подвійний клік не плодить
    записів. Купівля того самого аудиту вдруге, після повернення коштів,
    лишається можливою: та покупка вже не PENDING.
    """
    try:
        await guest_app.ensure_active_guest(session, capability)
    except guest_app.AlreadyClaimed as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"reason": "already.claimed"}
        ) from exc
    if not await guest_app.owns_audit(session, session=capability, audit_id=audit_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    if await guest_app.is_unlocked(session, audit_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="звіт уже відкрито")

    audit = await audit_service.get_audit(session, audit_id)
    if audit is None or AuditStatus(audit.status) not in REPORTABLE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="аудит ще не завершено"
        )

    try:
        opened = await purchases_app.open_checkout(
            session, organization_id=capability.organization_id, audit_id=audit_id
        )
    except purchases_app.ProviderUnavailable as exc:
        # Каса не відкрилась — покупка лишається PENDING і чекає на
        # наступну спробу. Незакрита каса не є помилкою даних.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "checkout.unavailable"},
        ) from exc
    await session.commit()

    return CheckoutOut(
        purchase_intent=str(opened.purchase.id),
        checkout_url=opened.url,
        audit_id=audit_id,
        client_token=runtime.get("paddle_client_token") or "",
        provider=opened.purchase.provider,
        transaction_ref=opened.purchase.provider_ref or "",
        environment=runtime.get("paddle_env") or "sandbox",
    )


@router.post("/orders", response_model=OrderOut, dependencies=[RateLimited])
async def open_order(
    capability: CapabilityDep,
    session: SessionDep,
) -> OrderOut:
    """Купити разову перевірку ДО того, як існує аудит.

    Це друга дорога до того самого продукту, і вона починається з
    оплати. Кнопка «Разова перевірка» на сторінці цін веде сюди: людина
    ще не називала сайту, і питати його перед касою означало б робити
    роботу, за яку вона ще не заплатила.

    Акаунта тут немає й не буде — разова покупка анонімна за рішенням
    власника. Права тримає гостьова спроможність, покупка належить
    гостьовій організації, а видача (одна перевірка сайту й одна
    перевірка присутності) приходить зліпком умов пропозиції, як і в
    кабінеті.

    Що саме продається, вирішує каталог, а не адреса: анонімно можна
    купити лише «разову перевірку». Пакет і підписка живуть на акаунті,
    бо їх витрачають не за один раз.
    """
    try:
        await guest_app.ensure_active_guest(session, capability)
    except guest_app.AlreadyClaimed as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"reason": "already.claimed"}
        ) from exc

    from app.application import commerce as commerce_app

    provider_name = billing_catalog.current_provider()
    try:
        offer = await purchases_app.single_offer(session, provider=provider_name)
        opened = await commerce_app.open_offer_checkout(
            session,
            organization_id=capability.organization_id,
            offer_code=str(offer.code),
            # Друга спроба тієї самої людини віддає ту саму касу: інакше
            # кожне натискання «спробувати ще раз» лишало б у провайдера
            # ще одну незавершену транзакцію.
            reuse_pending=True,
        )
    except (purchases_app.ProviderUnavailable, commerce_app.OfferUnavailable) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "checkout.unavailable"},
        ) from exc
    await session.commit()

    return OrderOut(
        purchase_id=opened.purchase_id,
        checkout_url=opened.url,
        client_token=runtime.get("paddle_client_token") or "",
        provider=provider_name,
        transaction_ref=opened.provider_ref,
        environment=runtime.get("paddle_env") or "sandbox",
    )


@router.get("/orders/{purchase_id}", response_model=OrderStateOut)
async def read_order(
    purchase_id: uuid.UUID,
    capability: CapabilityDep,
    session: SessionDep,
    reconcile: bool = False,
) -> OrderStateOut:
    """Що з цією покупкою — за НАШИМИ записами.

    Сторінка повернення з каси питає саме тут і нічого не вирішує сама:
    адресу повернення приніс браузер із чужого сайту. Право дає лише
    перевірена подія провайдера.

    `started_audit_id` розводить два стани, які інакше злилися б: гроші
    прийшли, але сайт ще не названий — і сайт названий, перевірка вже
    йде. Перший показує форму, другий веде до результату.
    """
    purchase = await purchases_app.owned_purchase(
        session, organization_id=capability.organization_id, purchase_id=purchase_id
    )
    if purchase is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")

    from app.billing import credits as billing_credits

    return OrderStateOut(
        purchase_id=purchase_id,
        state=await purchases_app.state_of(session, purchase=purchase),
        charged=await purchases_app.charged_of(
            session, purchase=purchase, ask_provider=reconcile
        ),
        started_audit_id=purchase.audit_id,
        presence_available=await billing_credits.balance(
            session,
            organization_id=capability.organization_id,
            credit_type="presence",
        ),
    )


@router.post(
    "/orders/{purchase_id}/audit",
    response_model=PublicAuditOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[RateLimited],
)
async def start_paid_audit(
    purchase_id: uuid.UUID,
    payload: PaidAuditCreate,
    capability: CapabilityDep,
    session: SessionDep,
) -> PublicAuditOut:
    """Витратити оплачену покупку на сайт, названий після каси.

    Тут сходяться дві речі, які в решті продукту приходять разом:
    оплата (вже підтверджена подією провайдера) і вибір сайту (щойно
    зроблений людиною). Тому саме тут покупка звʼязується з аудитом і
    відкривається повний вигляд — не «на віру», а на підставі власного
    запису зі статусом PAID.

    Аудит запускається НЕ як превʼю: він списує куплену одиницю, як і
    будь-який платний аудит кабінету. Друга куплена одиниця —
    присутність — лишається на організації й витрачається окремо, коли
    людина запускає перевірку присутності.

    Невдалий аудит не спалює покупку: якщо звʼязаний аудит завершився
    помилкою, та сама покупка приймає нову адресу.
    """
    try:
        await guest_app.ensure_active_guest(session, capability)
    except guest_app.AlreadyClaimed as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"reason": "already.claimed"}
        ) from exc

    purchase = await purchases_app.owned_purchase(
        session, organization_id=capability.organization_id, purchase_id=purchase_id
    )
    if purchase is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    if purchase.status is not PurchaseStatus.PAID:
        # Не «помилка», а стан: подія провайдера ще в дорозі або оплати
        # не було. Екран чекає й питає знову.
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"reason": "not.paid"},
        )

    live = await purchases_app.spent_on_live_audit(session, purchase=purchase)
    if live is not None:
        # Покупку вже витрачено, і той аудит живий: повертаємо його
        # замість другого запуску за ті самі гроші.
        return PublicAuditOut(
            audit_id=live.id, status=live.status, unlocked=True
        )

    try:
        started = await audits_app.start_audit(
            session,
            AuditCreate(url=payload.url),
            organization_id=capability.organization_id,
            created_by_user_id=None,
            trigger=AuditTrigger.MANUAL,
            site_id=await audits_app.ensure_site_for(
                session,
                organization_id=capability.organization_id,
                url=payload.url,
                created_by_user_id=None,
            ),
        )
    except audits_app.NotAllowed as exc:
        # Куплена одиниця не знайшлась. Це стан обліку, а не відмова
        # оплати: подія могла ще не дійти.
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"reason": exc.reason},
        ) from exc

    purchase.audit_id = started.audit.id
    await guest_app.unlock_for_purchase(
        session, purchase=purchase, audit_id=started.audit.id
    )
    await session.commit()
    try:
        await enqueue_audit(started.audit.id)
    except Exception as exc:
        await audit_service.mark_failed(
            session, started.audit.id, f"черга недоступна: {exc}"
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="черга недоступна, спробуйте пізніше",
        ) from exc

    return PublicAuditOut(
        audit_id=started.audit.id, status=started.audit.status, unlocked=True
    )


@router.get("/checkout-config", response_model=CheckoutConfigOut)
async def read_checkout_config() -> CheckoutConfigOut:
    """Публічні налаштування каси для сторінки оплати.

    Без спроможності гостя навмисно: сторінку default payment link
    Paddle відкриває за посиланням `?_ptxn=…`, і людина може дійти до
    неї з листа, іншого браузера чи наступного дня — там гостьового
    токена немає й бути не мусить. Права ця відповідь не дає: обидва
    значення публічні, а оплату однаково доводить лише перевірена
    подія провайдера.

    Без обмеження частоти: відповідь — дві константи, ані бази, ані
    мережі за нею немає.
    """
    return CheckoutConfigOut(
        provider=billing_catalog.current_provider(),
        environment=runtime.get("paddle_env") or "sandbox",
        client_token=runtime.get("paddle_client_token") or "",
    )


@router.get("/audits/{audit_id}/payment", response_model=PaymentStateOut)
async def read_payment_state(
    audit_id: uuid.UUID,
    capability: CapabilityDep,
    session: SessionDep,
    reconcile: bool = False,
) -> PaymentStateOut:
    """Стан оплати за НАШИМИ записами.

    Сторінка повернення з каси питає саме тут. Вона не має ані права,
    ані способу вирішувати сама: адреса повернення — це те, що браузер
    приніс із чужого сайту, а транзакція, названа в її параметрах, не
    перевірена нічим. Право дає лише перевірена подія провайдера.

    `reconcile` просить звірити відкриту касу з провайдером. Потрібно
    рівно тоді, коли вікно каси закрилось без слова «оплачено»: події
    в такому разі не буде ніколи, і без звірки відповідь застрягла б
    на «обробляємо». Звірка нічого не змінює й доступу не дає — вона
    відповідає лише на питання «гроші взято?», і то лише коли провайдер
    відповів сам.
    """
    if not await guest_app.owns_audit(session, session=capability, audit_id=audit_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")

    state = await purchases_app.payment_state(
        session, organization_id=capability.organization_id, audit_id=audit_id
    )
    return PaymentStateOut(
        audit_id=audit_id,
        state=state,
        charged=await purchases_app.charged(
            session,
            organization_id=capability.organization_id,
            audit_id=audit_id,
            ask_provider=reconcile,
        ),
        unlocked=await guest_app.is_unlocked(session, audit_id),
    )


class ClaimIn(BaseModel):
    """Створення акаунта для вже отриманої цінності.

    Питаємо рівно те, без чого акаунта не буває: пошту й пароль. Ні
    імені компанії, ні ролі, ні мети — усе це можна спитати потім, у
    людини, яка вже щось від нас отримала.
    """

    email: str = Field(min_length=3, max_length=320)
    # Межа схеми лише структурна — така сама, як у реєстрації. Політику
    # довжини оголошує `app/identity/passwords.py` і ніхто більше:
    # власне `min_length=8` тут було третім числом того самого правила,
    # нижчим за обидва інші, і саме воно впускало пароль, на якому
    # домен потім падав.
    password: str = Field(min_length=1, max_length=256)
    display_name: str = Field(default="", max_length=200)


class ClaimOut(BaseModel):
    organization_id: uuid.UUID
    user_id: uuid.UUID


@router.post("/claim", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
async def claim(
    payload: ClaimIn,
    request: Request,
    capability: CapabilityDep,
    session: SessionDep,
) -> ClaimOut:
    """Привласнити гостьову організацію новій людині.

    Аудит не рухається й не переписується: у нього той самий власник,
    той самий ідентифікатор, та сама покупка. Змінюється лише те, що в
    організації тепер є учасник.

    Наявна пошта — 409, а не помилка входу. Це інший сценарій: у людини
    вже є організація, і гостьові ресурси треба зливати з нею. Злиття —
    окрема операція з журналом походження, і цей маршрут її не робить.
    """
    # Той самий лічильник, що й у реєстрації: це теж створення акаунта.
    await auth_rate_limited(request, "signup")
    try:
        claimed = await guest_app.create_user_and_claim(
            session,
            session=capability,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
    except guest_app.ExistingUser as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"reason": "account.exists", "needs": "merge"},
        ) from exc
    except guest_app.AlreadyClaimed as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"reason": "already.claimed"}
        ) from exc
    except WeakPassword as exc:
        # Без цього `WeakPassword` (а це ValueError) виходив із домену
        # назовні: глобального обробника для нього немає, тож клієнт
        # діставав 500 на власну одруківку в паролі. Код і форма — ті
        # самі, що на реєстрації, скиданні й зміні: політика одна, тож
        # і звіт про її порушення один.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"reason": "password.weak", "message": str(exc)},
        ) from exc
    except guest_app.GuestError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено") from exc

    await session.commit()
    return ClaimOut(
        organization_id=claimed.organization.id, user_id=claimed.membership.user_id
    )




class ReportLinkOut(BaseModel):
    """Постійне посилання на куплений звіт. Токен показується один раз."""

    token: str
    url: str


class ReportLinkMintIn(BaseModel):
    """Мова, якою заморожується куплений звіт.

    Гостьовий аудит мови не має — як і будь-який аудит: той самий
    запуск віддається різними мовами різним читачам. Тому мова
    купленого звіту — явний параметр запиту в момент видачі: фронтенд
    передає мову, якою людина щойно пройшла воронку й читала короткий
    результат. Це не здогад із браузера чи адреси — це те, що людина
    вже обрала, коли зайшла на /uk чи /en.

    Після видачі джерело правди одне — `ReportLink.lang`; змінити мову
    можна лише новим посиланням за живої сесії.
    """

    lang: str = Field(default="", max_length=16)


@router.post(
    "/audits/{audit_id}/report-link",
    response_model=ReportLinkOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[RateLimited],
)
async def issue_report_link(
    audit_id: uuid.UUID,
    capability: CapabilityDep,
    session: SessionDep,
    payload: ReportLinkMintIn | None = None,
) -> ReportLinkOut:
    """Видати постійне посилання на куплений звіт.

    Сесія гостя мине за сім днів, а куплений доступ — ні: посилання
    привʼязане до розблокування, не до сесії, і не має строку. Воно
    відкриває рівно один звіт: ні інших аудитів, ні запуску, ні каси,
    ні жодного ресурсу організації.

    Повторний виклик за живої сесії видає нове посилання — це і є
    відновлення загубленого токена, поки сесія жива. Після її смерті
    відновлення немає: слабких ознак на кшталт пошти чи адреси ми не
    приймаємо, а надійний шлях збереження — акаунт.
    """
    if not await guest_app.owns_audit(session, session=capability, audit_id=audit_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    # Невідома чи порожня мова — продуктовий дефолт: звіти сьогодні
    # існують двома мовами, і прохання французької чесніше виконати
    # англійською, ніж відмовити. Явно обрану підтримувану мову дефолт
    # не підмінює ніколи — це тримає окремий тест.
    requested = parse((payload.lang if payload else "") or "")
    lang = (requested or DEFAULT_LOCALE).value
    try:
        token, _ = await guest_app.issue_report_link(session, audit_id=audit_id, lang=lang)
    except guest_app.GuestError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="повний звіт не відкрито"
        ) from exc
    await session.commit()
    return ReportLinkOut(token=token, url=f"/r/{token}")


# ── допоміжне ──────────────────────────────────────────────────────────────


def _json_response(payload: dict[str, Any]) -> Response:
    import json

    return Response(
        content=json.dumps(payload, ensure_ascii=False, default=str),
        media_type="application/json",
        headers=PRIVATE_HEADERS,
    )


# ── присутність після оплати ─────────────────────────────────────────────
#
# Разова покупка дає одиницю присутності, але досі дороги від покупки до
# прогону не було: форма жила за входом і вимагала бренд та категорію,
# яких гість не вводив. Тепер факти виводяться з того самого аудиту,
# показуються гостю з можливістю змінити, і прогін іде тією самою
# одиницею тієї самої гостьової організації. Клієнт платить за дві речі
# й отримує дві.


def _presence_run_out(run: Any) -> PresenceRunOut:
    return PresenceRunOut(
        id=run.id,
        url=run.url,
        brand=run.brand,
        status=run.status,
        prompt_set_version=run.prompt_set_version,
        created_at=run.created_at,
        finished_at=run.finished_at,
        observations_total=run.observations_total,
        observations_ok=run.observations_ok,
        cost_usd=round(run.cost_usd, 4),
        error=run.error,
        entitlement_source=run.entitlement_source,
        entitlement_settled=run.entitlement_settled,
        deliverable=run.deliverable,
    )


async def _guest_presence_audit(
    session: SessionDep, capability: guest_app.GuestSession, audit_id: uuid.UUID
) -> Any:
    """Аудит гостя, за який заплачено. Чужий чи неоплачений — 404."""
    if not await guest_app.owns_audit(session, session=capability, audit_id=audit_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    if not await guest_app.is_unlocked(session, audit_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail={"reason": "not.unlocked"}
        )
    audit = await audit_service.get_audit(session, audit_id)
    if audit is None or AuditStatus(audit.status) not in (
        AuditStatus.COMPLETED, AuditStatus.PARTIAL
    ):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="аудит ще не завершено")
    return audit


@router.get(
    "/audits/{audit_id}/presence", response_model=GuestPresenceOut, dependencies=[RateLimited]
)
async def guest_presence(
    audit_id: uuid.UUID, capability: CapabilityDep, session: SessionDep
) -> GuestPresenceOut:
    """Присутність для оплаченого аудиту: підстановка, право, прогони."""
    from app.services import presence_facts_service, presence_service

    audit = await _guest_presence_audit(session, capability, audit_id)
    facts = await presence_facts_service.suggest_for_audit(session, audit)
    plan = await presence_service.plan_view(
        session, organization_id=capability.organization_id
    )
    runs = [
        r for r in await presence_service.runs_for(session, capability.organization_id)
        if r.origin == audit.origin
    ]
    return GuestPresenceOut(
        suggestion=PresenceSuggestionOut(audit_id=audit.id, url=audit.url, **facts.to_json()),
        can_start=bool(plan.get("can_start")),
        credits_available=int(plan.get("credits_available", 0)),
        providers=[str(p.get("provider")) for p in plan.get("providers", [])],
        runs=[_presence_run_out(r) for r in runs],
    )


@router.post(
    "/audits/{audit_id}/presence",
    response_model=PresenceRunOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[RateLimited],
)
async def guest_presence_start(
    audit_id: uuid.UUID,
    payload: GuestPresenceRunIn,
    capability: CapabilityDep,
    session: SessionDep,
) -> PresenceRunOut:
    """Запустити прогін оплаченою одиницею. Факти — підтверджені людиною."""
    from app.services import presence_service

    try:
        await guest_app.ensure_active_guest(session, capability)
    except guest_app.AlreadyClaimed as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail={"reason": "already.claimed"}
        ) from exc
    audit = await _guest_presence_audit(session, capability, audit_id)
    try:
        # Точка збереження, а не відкат сесії: запис прогону вже у
        # транзакції, і відмова в праві мусить прибрати САМЕ його — не
        # все, що транзакція встигла зробити до того.
        async with session.begin_nested():
            run = await presence_service.create_run(
                session,
                url=audit.url,
                brand=payload.brand,
                brand_aliases=list(payload.brand_aliases),
                category=payload.category,
                services=[],
                location=payload.location,
                language=payload.language,
                organization_id=capability.organization_id,
                site_id=None,
                idempotency_key=payload.idempotency_key,
            )
    except presence_service.PresenceEntitlementRequired as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={"reason": "presence.noEntitlement"},
        ) from exc
    await session.commit()
    await enqueue_presence(run.id)
    return _presence_run_out(run)


@router.get("/presence/{run_id}", response_model=PresenceRunOut, dependencies=[RateLimited])
async def guest_presence_run(
    run_id: uuid.UUID, capability: CapabilityDep, session: SessionDep
) -> PresenceRunOut:
    """Стан прогону гостя — той самий контракт, що бачить клієнт у кабінеті."""
    from app.services import presence_service

    run = await presence_service.owned_run(session, capability.organization_id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    return _presence_run_out(run)


@router.get("/presence/{run_id}/export.docx", dependencies=[RateLimited])
async def guest_presence_export(
    run_id: uuid.UUID, capability: CapabilityDep, session: SessionDep,
    lang: str = "en", kind: str = "general",
) -> Response:
    """Word-експорт присутності для гостя — обидва види, як у кабінеті.

    Разова покупка продається разом із присутністю, тож гість, який не
    заводив акаунта, мусить отримати ті самі документи. Дефолт — вид
    для власника: гість купує звіт про свій бізнес, а не діагностику.
    """
    from app.application import presence as presence_app
    from app.services import presence_service

    if kind not in presence_app.KINDS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    run = await presence_service.owned_run(session, capability.organization_id, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")

    payload = await presence_app.export_docx(session, run, lang=lang, kind=kind)
    return Response(
        content=payload,
        media_type=("application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"),
        headers={"Content-Disposition": 'attachment; filename="'
                 + presence_app.export_filename(run, lang, kind) + '"'},
    )

