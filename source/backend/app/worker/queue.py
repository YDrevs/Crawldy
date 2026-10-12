import json
import uuid
from functools import lru_cache
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

_pool: ArqRedis | None = None


@lru_cache
def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


def serialize_job(obj: Any) -> bytes:
    """JSON замість типового pickle arq.

    Воркер розпаковує все, що лежить у Redis. З pickle це означало, що
    будь-хто з доступом до Redis виконує свій код у воркері — а Redis у
    compose був відкритий назовні без пароля. Аргументи задач — рядки й
    числа, тож JSON нічого не втрачає; `default=str` — для результатів.
    """
    return json.dumps(obj, default=str).encode()


def deserialize_job(data: bytes) -> Any:
    return json.loads(data)


async def get_pool() -> ArqRedis:
    global _pool
    if _pool is None:
        _pool = await create_pool(
            redis_settings(), job_serializer=serialize_job, job_deserializer=deserialize_job
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def enqueue_audit(audit_id: uuid.UUID, *, attempt: int = 1, delay_s: int = 0) -> None:
    """Поставити спробу виконати аудит.

    Номер спроби входить в ідентифікатор завдання навмисно. Черга не
    приймає двох завдань з однаковим id, і саме це захищає від подвійної
    постановки — але захищає й від повтору: без номера друга спроба того
    самого аудиту мовчки не потрапляла б у чергу взагалі. Помилка була б
    невидимою: повтори просто ніколи не відбувалися б.
    """
    pool = await get_pool()
    await pool.enqueue_job(
        "run_audit_task",
        str(audit_id),
        attempt,
        _job_id=f"audit:{audit_id}:{attempt}",
        _defer_by=delay_s or None,
    )


async def enqueue_enrichment(audit_id: uuid.UUID, task_type: str) -> None:
    """Поставити задачу збагачення. Викликає лише внутрішній тригер.

    Ідентифікатор завдання без номера спроби — навмисно, на відміну від
    аудиту: повторна постановка тієї самої задачі для того самого аудиту
    має бути НЕ-подією. Другий рівень захисту — ідемпотентність самого
    прогону: навіть якщо черга виконає завдання двічі, платний виклик
    станеться один раз.
    """
    pool = await get_pool()
    await pool.enqueue_job(
        "run_enrichment_task",
        str(audit_id),
        task_type,
        _job_id=f"enrich:{audit_id}:{task_type}",
    )


async def enqueue_presence(run_id: uuid.UUID) -> None:
    """Поставити прогін присутності. Без номера спроби — навмисно:
    повторна постановка того самого прогону мусить бути не-подією, а
    ідемпотентність виконання тримає UNIQUE ідентичності спостережень."""
    pool = await get_pool()
    await pool.enqueue_job(
        "run_presence_task",
        str(run_id),
        _job_id=f"presence:{run_id}",
    )


async def enqueue_password_reset(*, email: str, lang: str = "") -> None:
    """Поставити доставку листа про відновлення пароля.

    Ідентифікатора завдання НЕМАЄ навмисно, і це протилежність рішенню
    для збагачення. Там повторна постановка мусить бути не-подією; тут
    друге натискання «надішліть ще раз» — це свідомий намір людини, і
    мовчазне поглинання другого запиту виглядало б як зламана кнопка.
    Від напливу боронить обмежувач частоти на маршруті, а не черга.

    Адреса їде в чергу як є: Redis — наша інфраструктура, а без адреси
    воркер не мав би кому писати. У журнали вона не потрапляє ніде.
    """
    pool = await get_pool()
    await pool.enqueue_job("send_password_reset_task", email, lang)
