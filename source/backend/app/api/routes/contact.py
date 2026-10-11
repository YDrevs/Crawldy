"""Публічна контактна форма: конфігурація віджета й приймання звернення.

Два маршрути й нічого більше.

`GET /v1/contact/config` віддає браузеру рівно те, що йому призначено:
site-key віджета (він публічний за побудовою) і чи працює доставка.
Секрет провайдера й адреса одержувача сюди не потрапляють ніколи — тест
`test_contact.py` стереже саме це.

`POST /v1/contact` приймає звернення. Порядок перевірок — у
`app/application/contact.py`; тут лише межа HTTP: лічильник частоти,
походження запиту й переклад кодів відмови в статуси.

## Лічильник тут не має стосунку до тарифів

Контактна форма нічого не списує: ані аудитів, ані підписки. Вікно в неї
власне, окреме від запуску аудитів, інакше зловживання формою глушило б
головну дію продукту.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.deps import SessionDep
from app.application import contact as contact_app
from app.audit.i18n import DEFAULT_LOCALE, parse
from app.contact import delivery as delivery_module
from app.core.config import settings
from app.core.ratelimit import RateLimiter

router = APIRouter(prefix="/v1/contact", tags=["contact"])


def _limiter(request: Request) -> RateLimiter:
    limiter = getattr(request.app.state, "rate_limiter", None)
    if limiter is None:  # pragma: no cover — ставиться в lifespan
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="сервіс недоступний"
        )
    return limiter  # type: ignore[no-any-return]


def client_ip(request: Request) -> str:
    """Адреса клієнта. За проксі — перший запис `X-Forwarded-For`.

    Те саме правило, що в анонімній воронці: заголовку можна вірити лише
    за нашим проксі, інакше лічильник обходиться одним рядком.
    """
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


async def _rate_limited(request: Request) -> None:
    limiter = _limiter(request)
    ip = client_ip(request)
    decision = await limiter.check(
        f"contact:{ip}",
        limit=settings.contact_rate_limit,
        window=settings.contact_rate_window_seconds,
    )
    if not decision.allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"reason": "contact.too_many"},
            headers={"Retry-After": str(decision.reset_after)},
        )


def _same_origin(request: Request) -> None:
    """Запит із чужої сторінки не приймається.

    Форма живе на нашому сайті, і `Origin` браузер підставляє сам.
    Дозволені джерела — ті самі, що в CORS: два переліки дозволених
    сайтів розійшлися б уже на першій правці.
    """
    origin = request.headers.get("origin")
    if origin is None:
        # Не браузер (curl, серверний виклик): CSRF там не існує, а
        # відмовляти інтеграціям через відсутній заголовок нема підстав.
        return
    if origin not in settings.cors_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail={"reason": "contact.origin"}
        )


class ContactConfigOut(BaseModel):
    """Те, що браузеру справді потрібно. Секретів тут немає за побудовою."""

    site_key: str = ""
    """Публічний ключ віджета. Порожній — челенджу немає."""
    antibot: str = "disabled"
    delivery_ready: bool = False


class ContactIn(BaseModel):
    name: str = Field(max_length=contact_app.NAME_MAX + 1)
    email: str = Field(max_length=contact_app.EMAIL_MAX + 1)
    site_url: str = Field(default="", max_length=contact_app.SITE_MAX + 1)
    message: str = Field(max_length=contact_app.MESSAGE_MAX + 1)
    lang: str = Field(default="", max_length=16)
    token: str = Field(default="", max_length=4096)
    # Приманка. Назва навмисно нейтральна: автомат заповнює все, що
    # схоже на поле, а людина цього поля не бачить.
    company: str = Field(default="", max_length=200)


class ContactOut(BaseModel):
    """Відповідь без жодних службових подробиць.

    Ані адреси одержувача, ані стану транспорту, ані кодів провайдера:
    людині потрібно знати, що звернення прийнято, і номер, на який можна
    послатися.
    """

    accepted: bool = True
    reference: str


@router.get("/config", response_model=ContactConfigOut)
async def contact_config() -> ContactConfigOut:
    """Конфігурація форми для браузера. Секрет сюди не потрапляє."""
    return ContactConfigOut(
        site_key=settings.turnstile_site_key or "",
        antibot="turnstile" if settings.turnstile_secret_key else "disabled",
        delivery_ready=delivery_module.build_transport().available(),
    )


# Коди відмови → статус HTTP. Тіло несе стабільний код, який клієнт
# перекладає сам: сирий рядок сервера на екран не потрапляє ніколи.
_STATUS = {
    contact_app.INVALID_NAME: status.HTTP_422_UNPROCESSABLE_ENTITY,
    contact_app.INVALID_EMAIL: status.HTTP_422_UNPROCESSABLE_ENTITY,
    contact_app.INVALID_MESSAGE: status.HTTP_422_UNPROCESSABLE_ENTITY,
    contact_app.INVALID_SITE: status.HTTP_422_UNPROCESSABLE_ENTITY,
    contact_app.ANTIBOT_REJECTED: status.HTTP_403_FORBIDDEN,
    contact_app.ANTIBOT_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
    contact_app.DELIVERY_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
}


@router.post(
    "",
    response_model=ContactOut,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(_rate_limited), Depends(_same_origin)],
)
async def submit_contact(
    payload: ContactIn,
    request: Request,
    session: SessionDep,
    user_agent: Annotated[str | None, Header()] = None,
) -> ContactOut:
    """Прийняти звернення. Успіх — тільки після того, як ми його зберегли."""
    locale = parse(payload.lang or "") or DEFAULT_LOCALE
    submission = contact_app.Submission(
        name=payload.name,
        email=payload.email,
        site_url=payload.site_url,
        message=payload.message,
        locale=locale.value,
        token=payload.token,
        honeypot=payload.company,
        ip=client_ip(request),
    )
    try:
        accepted = await contact_app.submit(session, submission)
    except contact_app.ContactError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=_STATUS.get(exc.reason, status.HTTP_400_BAD_REQUEST),
            detail={"reason": exc.reason},
        ) from exc
    await session.commit()
    return ContactOut(reference=accepted.reference)
