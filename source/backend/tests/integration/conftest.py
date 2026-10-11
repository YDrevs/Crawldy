"""Тимчасова база PostgreSQL на прогін тестів.

Досі жоден із тестів проєкту не торкався БД: усі 498 перевіряли чисті
шари — чеки, скоринг, білдер звіту. Для фази 4 цього замало. `JSONB`,
`ON CONFLICT … WHERE`, `FOR UPDATE SKIP LOCKED`, часові зони й каскади
поводяться на SQLite інакше або не працюють узагалі, а саме на них
тримаються квота, ідемпотентність вебхуків і захист розкладу від
подвійного запуску.

База створюється окрема й одноразова. Робоча база з `.env` не чіпається
навіть на читання: стерти її прогоном тестів — помилка, яку роблять рівно
один раз, і краще, щоб цієї нагоди не було.

Якщо PostgreSQL недоступний, тести пропускаються з поясненням, а не
падають: розробник без піднятого docker-compose має бачити зелений
юніт-набір, а не червоний екран через інфраструктуру.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.ratelimit import MemoryRateLimiter

BACKEND = Path(__file__).resolve().parents[2]

# Адміністративна база, до якої підключаємось, щоб створити тестову.
ADMIN_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://seo:seo@localhost:5432/postgres"
)


def _with_database(url: str, name: str) -> str:
    base, _, _ = url.rpartition("/")
    return f"{base}/{name}"


async def _server_is_reachable() -> str | None:
    """None, якщо все гаразд; інакше причина пропуску — читана людиною."""
    try:
        engine = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
        async with engine.connect():
            pass
        await engine.dispose()
    except Exception as exc:  # noqa: BLE001 — причина йде в skip, не в трейс
        return f"{type(exc).__name__}: {str(exc)[:120]}"
    return None


@pytest_asyncio.fixture(scope="session")
async def postgres_url() -> AsyncIterator[str]:
    """Порожня база з накатаними міграціями, своя на прогін."""
    reason = await _server_is_reachable()
    if reason:
        pytest.skip(f"PostgreSQL недоступний ({reason}); підніміть docker compose up postgres")

    name = f"crawldy_test_{uuid.uuid4().hex[:12]}"
    admin = create_async_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.exec_driver_sql(f'CREATE DATABASE "{name}"')

    url = _with_database(ADMIN_URL, name)
    try:
        # env.py викликає asyncio.run() на рівні модуля, а ми вже
        # всередині циклу — тож міграції йдуть у власному потоці.
        await asyncio.to_thread(_upgrade_to_head, url)
        yield url
    finally:
        async with admin.connect() as conn:
            # Клієнти, що не встигли від'єднатися, інакше не дадуть дропнути.
            await conn.exec_driver_sql(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname = '{name}' AND pid <> pg_backend_pid()"
            )
            await conn.exec_driver_sql(f'DROP DATABASE IF EXISTS "{name}"')
        await admin.dispose()


def _upgrade_to_head(url: str) -> None:
    """`alembic upgrade head` на вказаній базі.

    Викликається програмно, а не через підпроцес: так помилка міграції
    приходить трейсом у тест, а не рядком у чужому stdout.
    """
    from alembic.config import Config

    from alembic import command

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")


@pytest_asyncio.fixture
async def db_session(postgres_url: str) -> AsyncIterator[AsyncSession]:
    """Сесія в транзакції, яка відкочується після тесту.

    Тести не прибирають за собою вручну: те, що вони записали, зникає з
    відкотом. Порядок тестів від цього перестає впливати на результат — а
    саме через нього інтеграційні набори зазвичай і починають «мерехтіти».
    """
    engine = create_async_engine(postgres_url)
    connection = await engine.connect()
    transaction = await connection.begin()
    factory = async_sessionmaker(bind=connection, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP-клієнт застосунку, підключений до тестової транзакції.

    `commit()` у маршрутах підмінюється на `flush()`: справжній коміт
    завершив би зовнішню транзакцію фікстури, і відкоту після тесту не
    було б що відкочувати. Записане при цьому видно всім запитам у межах
    тесту — саме те, що потрібно, щоб перевіряти послідовності «створив →
    прочитав → видалив».
    """
    from app.core.db import get_session
    from app.main import app

    original_commit = db_session.commit
    db_session.commit = db_session.flush  # type: ignore[method-assign]

    async def _session() -> AsyncIterator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_session] = _session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()
    db_session.commit = original_commit  # type: ignore[method-assign]


@pytest_asyncio.fixture
async def worker_session(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[AsyncSession]:
    """Воркер, підключений до тестової транзакції.

    Воркер бере сесії з `SessionLocal` сам — він окремий процес і не має
    від кого їх отримати. Тому фікстура підміняє саму фабрику: усі його
    `async with SessionLocal()` віддають одну сесію тесту, а `commit()`
    стає `flush()`, щоб зовнішня транзакція дожила до відкоту.

    Сесія навмисно не закривається на виході з блоку: воркер відкриває їх
    кілька за один запуск, і перший же вихід забрав би її в решти.
    """
    from app.worker import recovery_task, tasks

    original_commit = db_session.commit
    db_session.commit = db_session.flush  # type: ignore[method-assign]

    class _Borrowed:
        async def __aenter__(self) -> AsyncSession:
            return db_session

        async def __aexit__(self, *_: object) -> bool:
            return False

    monkeypatch.setattr(tasks, "SessionLocal", _Borrowed)
    # Відновлення пароля бере сесію так само й зі свого модуля: імпорт
    # `from … import SessionLocal` створює власне імʼя, і підміна в
    # `tasks` до нього не дотягується.
    monkeypatch.setattr(recovery_task, "SessionLocal", _Borrowed)
    yield db_session
    db_session.commit = original_commit  # type: ignore[method-assign]


# Пароль, який проходить перевірку довжини. Один на всі тести — щоб не
# з'ясовувати щоразу, чому реєстрація повернула 422.
PASSWORD = "correct-horse-battery"


@pytest_asyncio.fixture
async def single_offer(db_session: AsyncSession) -> None:
    """«Разова перевірка» в каталозі — те, що гість купує за повний звіт.

    Окремого «прайсу разової покупки» в конфігурації більше немає: ціна
    одна, задається на закладці «Ціни» й публікується у провайдера. Тому
    касі потрібен запис каталогу, а не налаштування, і тест, який
    відкриває касу, мусить його завести — як завела б людина в кабінеті.
    """
    from app.services import commerce_service

    await commerce_service.upsert_offer(db_session, code="single", values={
        "offer_type": "single", "active": True, "display_name": "Single check",
        "provider": "fake", "provider_price_ref": "fake_single",
        "currency": "USD", "display_amount_minor": 999,
        "audit_credits": 1, "presence_credits": 1,
    })
    await db_session.commit()


async def register(client: httpx.AsyncClient, email: str, **extra: object):
    return await client.post(
        "/v1/auth/register", json={"email": email, "password": PASSWORD, **extra}
    )


async def sign_in_as(client: httpx.AsyncClient, email: str):
    """Новий користувач у власній організації, попередню сесію покинуто."""
    await client.post("/v1/auth/logout")
    return await register(client, email)


async def grant_audit_credits(db, *, organization_id, quantity: int = 1) -> None:
    """Куплені одиниці аудиту для організації.

    Безкоштовних повних аудитів не існує (рішення власника 2026-09-03):
    тест, що запускає повний аудит, мусить його ЧИМОСЬ оплатити, і
    чесний спосіб один — записана покупка. Ідентифікатор випадковий,
    щоб виклик у кількох тестах не впирався в ідемпотентність запису.
    """
    from datetime import UTC, datetime

    from app.application import purchases

    await purchases.record(
        db,
        organization_id=organization_id,
        provider="fake",
        external_id=f"pur-{uuid.uuid4()}",
        quantity=quantity,
        currency="USD",
        amount_minor=100 * quantity,
        purchased_at=datetime.now(UTC),
    )
    await db.commit()


@pytest.fixture(autouse=True)
def queue_is_not_the_subject(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    """Постановка в чергу підмінюється списком.

    Інтеграційні тести HTTP перевіряють доступ і персистентність, а не
    Redis. Без підміни кожен тест створення аудиту чекав би п'ять
    ретраїв підключення й падав за таймаутом — і виглядало б це як
    поломка продукту, хоча зламана лише адреса черги в оточенні.

    Фікстура повертає список поставлених ідентифікаторів: тест, якому
    потрібен сам факт постановки, може його перевірити.
    """
    queued: list[uuid.UUID] = []

    async def _enqueue(audit_id: uuid.UUID) -> None:
        queued.append(audit_id)

    monkeypatch.setattr("app.api.routes.audits.enqueue_audit", _enqueue)
    monkeypatch.setattr("app.api.routes.public.enqueue_audit", _enqueue)
    monkeypatch.setattr("app.api.routes.presence.enqueue_presence", _enqueue)
    # Службові прогони ставляться в ту саму чергу з власного роутера:
    # без підміни тут кожен тест адмінки чекав би тих самих пʼяти
    # ретраїв Redis і падав би 503 замість перевірки прав.
    monkeypatch.setattr("app.api.routes.admin_ops.enqueue_audit", _enqueue)
    monkeypatch.setattr("app.api.routes.admin_ops.enqueue_presence", _enqueue)
    monkeypatch.setattr("app.api.routes.public.enqueue_presence", _enqueue)
    return queued


@pytest.fixture(autouse=True)
def recovery_queue(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Черга відновлення пароля — списком, як і решта черг.

    Окремий список, а не спільний із аудитами: тут значення не
    ідентифікатор, а пара «адреса, мова», і саме її перевіряє тест про
    однаковий шлях для відомої й невідомої адреси.
    """
    queued: list[tuple[str, str]] = []

    async def _enqueue(*, email: str, lang: str = "") -> None:
        queued.append((email, lang))

    monkeypatch.setattr("app.api.routes.auth.enqueue_password_reset", _enqueue)
    return queued


@pytest.fixture(autouse=True)
def rate_limiter() -> Iterator[MemoryRateLimiter]:
    """Справжній лічильник у памʼяті, а не заглушка.

    `lifespan` під ASGITransport не виконується, тож лічильник ставиться
    тут. Саме лічильник, а не «завжди дозволено»: тест на межу мусить
    цю межу мати, інакше він перевіряє лише те, що маршрут не впав.
    """
    from app.main import app

    limiter = MemoryRateLimiter()
    app.state.rate_limiter = limiter
    yield limiter
    app.state.rate_limiter = None
