"""Реєстрація, вхід, вихід, «хто я», ключі API.

Тонкий шар: розбирає запит, викликає доменну операцію, віддає відповідь.
Рішень тут немає — вони в `app/identity/`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field, field_validator

from app.api.deps import (
    SESSION_COOKIE,
    ActorDep,
    AdminDep,
    SessionDep,
    auth_rate_limited,
    clear_session_cookie,
    client_ip,
    set_session_cookie,
)
from app.audit.i18n import parse as parse_locale
from app.core.config import settings
from app.core.ratelimit import RateLimiter
from app.identity import api_keys, recovery, service
from app.identity.dto import ApiKeyView, UserView
from app.identity.dto import OrganizationView as OrgView
from app.identity.passwords import WeakPassword
from app.worker.queue import enqueue_password_reset

log = structlog.get_logger()

router = APIRouter(prefix="/v1/auth", tags=["auth"])


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class RegisterIn(Credentials):
    display_name: str = Field(default="", max_length=200)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    status: str
    # Мова інтерфейсу. Порожньо — не обирав; тоді діє мова організації.
    locale: str = ""
    # Роль у команді Crawldy. `null` у переважної більшості; інтерфейс
    # питає її, щоб не малювати пункт меню, який усе одно дасть 403.
    platform_role: str | None = None


class PreferencesIn(BaseModel):
    """Що користувач може змінити про себе.

    Окремо від `/v1/account`: там тариф, підписка, права й квота —
    ресурс білінгу. Змішати їх означало б, що зміна мови концептуально
    належить до оплати.
    """

    display_name: str | None = Field(default=None, max_length=200)
    # Порожній рядок дозволений: він означає «не обирав».
    locale: str | None = Field(default=None, max_length=16)

    @field_validator("locale")
    @classmethod
    def _known_locale(cls, value: str | None) -> str | None:
        """Перевірка тут, а не в сервісі: перелік мов — словник двигуна,
        і залежність контексту ідентичності від нього ламає межі."""
        if value:
            if parse_locale(value) is None:
                raise ValueError(f"мова не підтримується: {value}")
            return parse_locale(value).value  # нормалізуємо «pt-BR» → «pt»
        return value


class OrganizationOut(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    is_personal: bool
    role: str


class MeOut(BaseModel):
    user: UserOut | None
    organization: OrganizationOut
    auth: str


class ApiKeyCreateIn(BaseModel):
    name: str = Field(default="", max_length=100)


class ApiKeyOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    created_at: str
    last_used_at: str | None


class ApiKeyCreatedOut(ApiKeyOut):
    # Єдиний раз, коли ключ видно. Далі в базі лише хеш.
    token: str


def _user_out(view: UserView) -> UserOut:
    return UserOut(
        id=view.id,
        email=view.email,
        display_name=view.display_name,
        status=view.status.value,
        locale=view.locale,
        platform_role=view.platform_role,
    )


def _org_out(view: OrgView) -> OrganizationOut:
    return OrganizationOut(
        id=view.id,
        name=view.name,
        slug=view.slug,
        is_personal=view.is_personal,
        role=view.role.value,
    )


@router.post("/register", response_model=MeOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: RegisterIn, request: Request, response: Response, db: SessionDep
) -> MeOut:
    """Новий користувач, його особиста організація і одразу вхід.

    Просити людину увійти відразу після реєстрації — зайвий крок, на
    якому губляться: вона щойно довела, що знає пароль.
    """
    await auth_rate_limited(request, "signup")
    try:
        registration = await service.register(
            db,
            email=payload.email,
            password=payload.password,
            display_name=payload.display_name,
        )
    except service.EmailTaken as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="ця пошта вже зареєстрована"
        ) from exc
    except WeakPassword as exc:
        # Той самий машинний код, що на скиданні й на зміні пароля.
        # Політика одна, тож і звітувати про її порушення три шляхи
        # мусять однаково: раніше тут їхав голий службовий рядок
        # українською, і клієнт не мав за чим відрізнити «закороткий
        # пароль» від будь-якої іншої 422.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"reason": "password.weak", "message": str(exc)},
        ) from exc

    issued = await service.create_session(
        db, user=registration.user, user_agent=request.headers.get("user-agent", "")
    )
    await db.commit()

    set_session_cookie(response, token=issued.token, expires_at=issued.session.expires_at)
    return MeOut(
        user=_user_out(UserView.of(registration.user)),
        organization=_org_out(
            OrgView.of_membership(registration.organization, registration.membership)
        ),
        auth="session",
    )


@router.post("/login", response_model=MeOut)
async def login(
    payload: Credentials, request: Request, response: Response, db: SessionDep
) -> MeOut:
    """Вхід. Причина відмови одна на всі випадки.

    Невідома пошта, невірний пароль, замкнений після підбору чи
    відключений акаунт — назовні однаково 401 з тим самим текстом.
    Розрізняти їх означало б безкоштовно розповідати сторонньому, що
    відбувається з чужим акаунтом.
    """
    await auth_rate_limited(request, "login")
    user = await service.authenticate(db, email=payload.email, password=payload.password)
    if user is None:
        # Коміт потрібен: невдала спроба збільшила лічильник, і без нього
        # захист від підбору не рахував би нічого.
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="невірна пошта або пароль"
        )

    organizations = await service.view_organizations_of(db, user_id=user.id)
    if not organizations:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="немає доступу")

    issued = await service.create_session(
        db, user=user, user_agent=request.headers.get("user-agent", "")
    )
    await db.commit()

    set_session_cookie(response, token=issued.token, expires_at=issued.session.expires_at)
    return MeOut(
        user=_user_out(UserView.of(user)),
        organization=_org_out(organizations[0]),
        auth="session",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, db: SessionDep) -> Response:
    """Вихід. Без cookie теж 204 — це не помилка, а бажаний стан."""
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await service.revoke_session(db, token)
        await db.commit()
    clear_session_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/me", response_model=MeOut)
async def me(actor: ActorDep, db: SessionDep) -> MeOut:
    """Хто я і в якій організації. Джерело правди для інтерфейсу.

    Фронтенд не обчислює це сам і не зберігає між сесіями: усе, що він
    показує про доступ, приходить звідси.
    """
    organization = await service.view_organization(
        db, organization_id=actor.organization_id, role=actor.role
    )
    if organization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="потрібен вхід")

    user = await service.view_user(db, actor.user_id) if actor.user_id else None

    return MeOut(
        user=_user_out(user) if user else None,
        organization=_org_out(organization),
        auth=actor.auth,
    )


# ── ключі API ──────────────────────────────────────────────────────────────


def _key_out(view: ApiKeyView) -> ApiKeyOut:
    return ApiKeyOut(
        id=view.id,
        name=view.name,
        prefix=view.prefix,
        created_at=view.created_at.isoformat(),
        last_used_at=view.last_used_at.isoformat() if view.last_used_at else None,
    )


@router.patch("/me", response_model=MeOut)
async def update_me(payload: PreferencesIn, actor: ActorDep, db: SessionDep) -> MeOut:
    """Налаштування користувача: імʼя та мова інтерфейсу.

    Ключ API сюди не ходить: у ключа немає людини, а це її налаштування.
    """
    if actor.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="потрібен вхід людиною"
        )
    user = await service.update_preferences(
        db,
        user_id=actor.user_id,
        display_name=payload.display_name,
        locale=payload.locale,
    )
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="потрібен вхід")

    organization = await service.view_organization(
        db, organization_id=actor.organization_id, role=actor.role
    )
    if organization is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="потрібен вхід")
    await db.commit()
    return MeOut(user=_user_out(user), organization=_org_out(organization), auth=actor.auth)


@router.post("/api-keys", response_model=ApiKeyCreatedOut, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    payload: ApiKeyCreateIn, actor: AdminDep, db: SessionDep
) -> ApiKeyCreatedOut:
    """Ключ організації. Створює людина, володіє організація."""
    user_id = actor.require_human()
    issued = await api_keys.issue(
        db,
        organization_id=actor.organization_id,
        created_by_user_id=user_id,
        name=payload.name,
    )
    await db.commit()
    base = _key_out(ApiKeyView.of(issued.record))
    return ApiKeyCreatedOut(**base.model_dump(), token=issued.token)


@router.get("/api-keys", response_model=list[ApiKeyOut])
async def list_api_keys(actor: AdminDep, db: SessionDep) -> list[ApiKeyOut]:
    records = await api_keys.list_for(db, organization_id=actor.organization_id)
    return [_key_out(ApiKeyView.of(r)) for r in records]


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: Annotated[uuid.UUID, ...], actor: AdminDep, db: SessionDep
) -> Response:
    """Відкликання. Чужий ключ дає 404, а не 403.

    Фільтр по організації стоїть у запиті, тож «не знайдено» тут — це
    правда з погляду того, хто питає.
    """
    revoked = await api_keys.revoke(db, key_id=key_id, organization_id=actor.organization_id)
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── відновлення пароля ────────────────────────────────────────────────
#
# Обмеження частоти: за зразком контактної форми, з власним вікном.
# Ділити лічильник із нею не можна — спам у форму не має закривати
# людині вхід до акаунта.


def _limiter(request: Request) -> RateLimiter:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:  # pragma: no cover — ставиться в lifespan
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="сервіс недоступний"
        )
    return limiter  # type: ignore[no-any-return]


async def _recovery_rate_limited(request: Request) -> None:
    """Два відра, не одне.

    За IP — щоб один клієнт не перебирав чужі адреси. За адресою — щоб
    зловмисник не завалив чужу скриньку листами, міняючи IP. Вистачить
    переповнення будь-якого, і відповідь та сама: 429 зі строком, коли
    можна повторити.
    """
    limiter = _limiter(request)
    keys = [f"recovery:ip:{client_ip(request)}"]
    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 — некоректне тіло тут не наша турбота
        body = {}
    if isinstance(body, dict):
        raw = body.get("email")
        if isinstance(raw, str) and raw.strip():
            # Адреса в ключі — у вигляді хеша: лічильник не має ставати
            # переліком адрес, які хтось намагався відновити.
            keys.append(f"recovery:email:{service.hash_token(raw.strip().lower())}")
    for key in keys:
        decision = await limiter.check(
            key,
            limit=settings.recovery_rate_limit,
            window=settings.recovery_rate_window_seconds,
        )
        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"reason": "recovery.too_many"},
                headers={"Retry-After": str(decision.reset_after)},
            )


class ForgotIn(BaseModel):
    email: EmailStr
    lang: str = Field(default="", max_length=16)


class ForgotOut(BaseModel):
    """Відповідь, однакова для відомої й невідомої адреси."""

    accepted: bool = True


class ResetIn(BaseModel):
    token: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=256)


class ChangeIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


@router.post("/password/forgot", response_model=ForgotOut, status_code=status.HTTP_202_ACCEPTED)
async def forgot_password(
    payload: ForgotIn,
    response: Response,
    _: Annotated[None, Depends(_recovery_rate_limited)],
) -> ForgotOut:
    """Запит на відновлення. Відповідь НЕ каже, чи є такий акаунт.

    Маршрут не ходить у базу й не надсилає листа: він лише ставить задачу
    в чергу — для БУДЬ-ЯКОЇ адреси, відомої чи ні. Пошук акаунта й
    доставку виконує воркер, і для невідомої адреси він мовчки спиняється.

    Саме тому тут немає `SessionDep`. Однакового ТІЛА відповіді замало:
    поки маршрут шукав користувача сам, невідома адреса поверталась
    одразу, а відома — після запиту в базу й зʼєднання з чужим SMTP.
    Різниця в часі відповіді і є той самий витік, від якого захищає
    однакове тіло. Тепер вимірювати нічого: обидва шляхи — це одна
    постановка в чергу.

    Черга недоступна — 503, і теж однаковий для обох адрес. Прикидатися,
    що лист прийнято, коли його нікому передати, означало б залишити
    людину чекати на те, чого не буде.
    """
    response.headers["Cache-Control"] = "no-store"
    try:
        await enqueue_password_reset(
            email=service.normalize_email(payload.email), lang=payload.lang
        )
    except Exception as exc:
        # У журнал іде тип винятку, і тільки він. Ані адреси, ані рядка
        # помилки клієнта Redis: перший — персональні дані, другий несе
        # адресу сервера й параметри підключення.
        log.warning("password_reset_enqueue_failed", error=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"reason": "recovery.unavailable"},
        ) from exc
    return ForgotOut()


@router.get("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def check_reset_token(token: str, response: Response, db: SessionDep) -> Response:
    """Чи чинне посилання. 204 — так, 404 — ні.

    Потрібне екрану: показати «посилання застаріло» до того, як людина
    введе новий пароль, а не після. Прострочений, використаний,
    скасований і неіснуючий дають однаковий 404.
    """
    record = await recovery.peek(db, token=token)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"reason": "recovery.invalid"}
        )
    response.headers["Cache-Control"] = "no-store"
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(payload: ResetIn, db: SessionDep) -> Response:
    """Встановити новий пароль за посиланням із листа.

    Сесій не видається: людина входить наново вже новим паролем. Так
    само не видається й підказки, чим саме токен не підійшов.
    """
    try:
        user = await recovery.consume(db, token=payload.token, new_password=payload.password)
    except WeakPassword as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "password.weak", "message": str(exc)},
        ) from exc
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail={"reason": "recovery.invalid"}
        )
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})


@router.post("/password/change", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: ChangeIn, actor: ActorDep, response: Response, db: SessionDep
) -> Response:
    """Зміна відомого пароля. Поточний обовʼязковий.

    Навіть для вже автентифікованої людини: інакше вкрадена сесія
    перетворюється на вкрадений акаунт. Після зміни всі сесії
    відкликаються — включно з тією, якою прийшов цей запит.
    """
    user_id = actor.require_human()
    try:
        changed = await recovery.change_password(
            db,
            user_id=user_id,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
    except WeakPassword as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"reason": "password.weak", "message": str(exc)},
        ) from exc
    if not changed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail={"reason": "password.wrong_current"}
        )
    await db.commit()
    clear_session_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})
