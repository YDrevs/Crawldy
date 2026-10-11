from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import (
    account,
    admin,
    admin_config,
    admin_ops,
    audits,
    auth,
    contact,
    health,
    offers,
    plans,
    presence,
    public,
    schedules,
    share,
    sites,
    webhooks,
)
from app.core.config import settings
from app.core.logging import configure_logging, log
from app.core.ratelimit import build_rate_limiter
from app.identity.authz import Forbidden, NotAuthenticated
from app.worker.queue import close_pool


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    # Лічильник частоти живе в стані застосунку, а не глобально: тест
    # мусить мати змогу підставити свій, не чіпаючи Redis, і при цьому
    # перевіряти справжню поведінку на межі, а не заглушку.
    _app.state.rate_limiter = build_rate_limiter()
    log.info("api_started", env=settings.app_env, perf_provider=settings.perf_provider)
    yield
    await close_pool()


app = FastAPI(
    title="Crawldy",
    version="0.1.0",
    description="Аудит сайту: швидкість, SEO, AI-ready/LLMO, придатність до цитування.",
    lifespan=lifespan,
)

# Точні origin'и й `allow_credentials`: інтерфейс автентифікується
# cookie-сесією, а браузер відмовляється слати cookie на "*". Зірочка тут
# не «менш строго», а просто зламаний вхід — і зламаний тихо.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(NotAuthenticated)
async def _not_authenticated(_: Request, exc: NotAuthenticated) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": "потрібен вхід"}
    )


@app.exception_handler(Forbidden)
async def _forbidden(_: Request, exc: Forbidden) -> JSONResponse:
    """Доменна відмова — це 403, а не 500.

    Обробник стоїть тут, а не в кожному маршруті, бо інакше перший
    забутий try/except перетворює відмову в доступі на внутрішню помилку
    — і виглядає це як поломка продукту, а не як спрацювання правила.

    Відмову через **чужий ресурс** маршрути перетворюють на 404 самі: тут
    ми не знаємо, чи існування ресурсу є таємницею.
    """
    return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content={"detail": str(exc)})


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(sites.router)
app.include_router(schedules.router)
app.include_router(audits.router)
app.include_router(share.router)
app.include_router(account.router)
app.include_router(admin.router)
app.include_router(admin_config.router)
app.include_router(admin_ops.router)
app.include_router(public.router)
app.include_router(webhooks.router)
app.include_router(presence.router)
app.include_router(offers.router)
app.include_router(plans.router)
app.include_router(contact.router)
