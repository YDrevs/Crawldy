from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=10,
    pool_pre_ping=True,
    echo=False,
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        # Робоча конфігурація (платіжний провайдер, ключі AI) читається
        # адаптерами синхронно з кешу процесу; кожен запит гарантує, що
        # кеш не старший за кілька секунд. Імпорт локальний: модуль
        # конфігурації тягне модель, а модель — `Base` звідси.
        from app.core import runtime_config as runtime

        await runtime.ensure_fresh(session)
        yield session
