"""Залежності запиту: сесія БД і контекст актора.

Два способи входу — cookie браузера й ключ API організації — зводяться
до одного `ActorContext`. Далі маршрути не знають, як саме прийшов
запит: перевірка власності однакова для людини й для інтеграції.
"""

from __future__ import annotations

import hmac
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.identity import api_keys, service
from app.identity.authz import ActorContext, Forbidden, NotAuthenticated
from app.identity.enums import PlatformRole, Role
from app.identity.legacy import LEGACY_ORGANIZATION_ID

SessionDep = Annotated[AsyncSession, Depends(get_session)]

# Ім'я cookie сесії. Префікс `__Host-` змушує браузер вимагати Secure,
# шлях "/" і відсутність Domain — тобто робить неможливим підсунути
# cookie з сусіднього піддомену.
#
# Локально його немає навмисно: браузер відкидає такі cookie без HTTPS, і
# вхід у розробці просто не працював би. Це та рідкісна різниця між
# середовищами, яку краще мати явною, ніж не мати захисту в проді.
SESSION_COOKIE = "crawldy_session" if settings.app_env == "local" else "__Host-crawldy_session"

# Заголовок ключа API лишається той самий, що був у глобального ключа:
# інтеграції, написані до фази 4, не мають ламатися через перейменування.
API_KEY_HEADER = "X-API-Key"


def client_ip(request: Request) -> str:
    """Адреса клієнта для лічильників частоти.

    `X-Forwarded-For` читається лише за нашим проксі (`trust_proxy_headers`)
    і СПРАВА: проксі дописують адресу в кінець, а перший запис — те, що
    клієнт прислав сам. Брати його означало обходити будь-який ліміт
    одним заголовком.
    """
    peer = request.client.host if request.client else ""
    if not settings.trust_proxy_headers:
        return peer
    chain = [
        part.strip()
        for part in request.headers.get("x-forwarded-for", "").split(",")
        if part.strip()
    ]
    if len(chain) < settings.trusted_proxy_hops:
        return peer
    return chain[-settings.trusted_proxy_hops]


async def auth_rate_limited(request: Request, action: str) -> None:
    """Ліміт спроб входу або створення акаунта з однієї адреси."""
    limit, window = {
        "login": (settings.login_rate_limit, settings.login_rate_window_seconds),
        "signup": (settings.signup_rate_limit, settings.signup_rate_window_seconds),
    }[action]
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:  # pragma: no cover — ставиться в lifespan
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="сервіс недоступний"
        )
    decision = await limiter.check(
        f"auth:{action}:ip:{client_ip(request)}", limit=limit, window=window
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"reason": "auth.too_many"},
            headers={"Retry-After": str(decision.reset_after)},
        )


def _is_service_key(token: str | None) -> bool:
    """Чи це один зі службових ключів. Порівняння за сталий час.

    Порожній перелік — ключа немає, а не «пускаємо всіх».
    """
    if not token:
        return False
    given = token.encode()
    return any(hmac.compare_digest(given, key.encode()) for key in settings.api_keys)


async def require_api_key(x_api_key: Annotated[str | None, Header()] = None) -> str:
    """Історичний глобальний ключ. Лишається для службових викликів.

    Не видається клієнтам, не належить організації, не відкликається
    поштучно — саме тому його замінюють ключі організації. Тут він
    доживає рівно доти, доки маршрути аудиту не перейдуть на
    `current_actor`, і його зняття — окремий крок, а не побічний ефект.
    """
    if x_api_key is None or not _is_service_key(x_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="невалідний або відсутній X-API-Key"
        )
    return x_api_key


ApiKeyDep = Annotated[str, Depends(require_api_key)]


async def _actor_from_session(db: AsyncSession, token: str) -> ActorContext | None:
    record = await service.resolve_session(db, token)
    if record is None:
        return None

    organizations = await service.organizations_of(db, user_id=record.user_id)
    if not organizations:
        # Користувач без жодної організації не може діяти: усе, з чим
        # працює продукт, належить організації. Особисту створюють при
        # реєстрації, тож сюди потрапляє лише той, кого звідусіль видалили.
        return None

    # Поки перемикача організацій немає, беремо першу за створенням —
    # особисту. Коли з'явиться, вибір житиме в сесії, а не в запиті.
    organization = organizations[0]
    membership = await service.membership_of(
        db, user_id=record.user_id, organization_id=organization.id
    )
    if membership is None:
        return None

    record.last_seen_at = datetime.now(UTC)
    return ActorContext(
        organization_id=organization.id,
        role=membership.role,
        auth="session",
        user_id=record.user_id,
        session_id=record.id,
        user_locale=await service.locale_of_user(db, user_id=record.user_id),
        organization_locale=organization.default_locale,
        platform_role=await service.platform_role_of(db, user_id=record.user_id),
    )


async def _actor_from_api_key(db: AsyncSession, token: str) -> ActorContext | None:
    key = await api_keys.resolve(db, token)
    if key is None:
        return None
    key.last_used_at = datetime.now(UTC)
    # Ключ діє від імені організації з правами адміністратора: він може
    # запускати аудити й керувати сайтами, але не білінгом і не складом
    # команди — для цього потрібна людина.
    return ActorContext(
        organization_id=key.organization_id,
        role=Role.ADMIN,
        auth="api_key",
        api_key_id=key.id,
        organization_locale=await service.locale_of_organization(
            db, organization_id=key.organization_id
        ),
    )


def _actor_from_legacy_key(token: str) -> ActorContext | None:
    """Історичний глобальний ключ, прив'язаний до службової організації.

    Він лишається живим, щоб наявні виклики — CLI, скрипти калібрування —
    не зламалися в день, коли з'явилася модель доступу. Але діє він уже не
    поза нею: у нього є організація, і перевірка власності для нього така
    сама, як для всіх.

    Ключі організації перевіряються **перед** ним: якщо той самий рядок
    виявиться і тим, і тим, виграє той, у якого є власник.
    """
    if not _is_service_key(token):
        return None
    return ActorContext(
        organization_id=LEGACY_ORGANIZATION_ID,
        role=Role.OWNER,
        auth="api_key",
    )


async def current_actor(request: Request, db: SessionDep) -> ActorContext:
    """Хто робить цей запит. 401, якщо невідомо.

    Cookie перевіряється першим: для браузера це основний шлях, і
    заголовок ключа там узагалі не має з'являтися.
    """
    cookie = request.cookies.get(SESSION_COOKIE)
    if cookie:
        actor = await _actor_from_session(db, cookie)
        if actor is not None:
            return actor

    header = request.headers.get(API_KEY_HEADER)
    if header:
        actor = await _actor_from_api_key(db, header)
        if actor is not None:
            return actor
        legacy = _actor_from_legacy_key(header)
        if legacy is not None:
            return legacy

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail="потрібен вхід або ключ API"
    )


ActorDep = Annotated[ActorContext, Depends(current_actor)]


def require_role(role: Role) -> Callable[[ActorContext], Awaitable[ActorContext]]:
    """Залежність, що вимагає роль не нижчу за задану."""

    async def dependency(actor: ActorDep) -> ActorContext:
        try:
            actor.require(role)
        except Forbidden as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        return actor

    return dependency


OwnerDep = Annotated[ActorContext, Depends(require_role(Role.OWNER))]
AdminDep = Annotated[ActorContext, Depends(require_role(Role.ADMIN))]


def require_platform(role: PlatformRole) -> Callable[[ActorContext], Awaitable[ActorContext]]:
    """Залежність для службових ендпойнтів.

    Перевірка в application-шарі, а не в тому, що адмінки не видно в
    інтерфейсі: клієнт із вгаданим URL має отримати 403 так само, як
    клієнт без URL — нічого.
    """

    async def dependency(actor: ActorDep) -> ActorContext:
        try:
            actor.require_platform(role)
        except Forbidden as exc:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
        return actor

    return dependency


StaffDep = Annotated[ActorContext, Depends(require_platform(PlatformRole.STAFF))]
PlatformAdminDep = Annotated[ActorContext, Depends(require_platform(PlatformRole.ADMIN))]


def not_found_instead_of_forbidden(_: Forbidden) -> HTTPException:
    """Чужий ресурс не існує — з погляду того, хто питає.

    403 підтверджує, що ресурс є, і дає спосіб перевіряти чужі
    ідентифікатори перебором. Тому назовні — 404.
    """
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="не знайдено")


def unauthenticated(_: NotAuthenticated) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="потрібен вхід")


def set_session_cookie(response: Response, *, token: str, expires_at: datetime) -> None:
    """Виставляє cookie сесії. Усі її властивості — в одному місці.

    `httponly` — щоб скрипт на сторінці не міг прочитати токен;
    `samesite=lax` — щоб чужий сайт не міг зробити запит від імені
    користувача, не ламаючи при цьому переходи за посиланням;
    `secure` — крім локальної розробки, де немає HTTPS.

    Функція, а не словник параметрів: словник типізується як
    `dict[str, object]`, і перевірка типів перестає бачити, що саме
    передається у `set_cookie`. Для налаштування безпеки це погана угода.
    """
    response.set_cookie(
        key=SESSION_COOKIE,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.app_env != "local",
        path="/",
        expires=expires_at,
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE, path="/")


__all__ = [
    "SESSION_COOKIE",
    "ActorDep",
    "AdminDep",
    "ApiKeyDep",
    "OwnerDep",
    "PlatformAdminDep",
    "SessionDep",
    "StaffDep",
    "clear_session_cookie",
    "current_actor",
    "not_found_instead_of_forbidden",
    "require_api_key",
    "require_role",
    "set_session_cookie",
    "unauthenticated",
]
