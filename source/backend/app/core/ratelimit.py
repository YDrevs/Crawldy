"""Обмеження частоти. Механізм, не політика.

Скільки саме дозволено — вирішує той, хто викликає, і числа лежать поруч
із його правилами. Тут лише лічильник, який уміє сказати «ще можна» або
«вже ні», однаково для процесу й для кластера.

## Вікно фіксоване, і це свідомо

Ковзне вікно точніше на межі: за фіксованого вікна можна зробити подвійну
норму, влучивши в кінець одного вікна й початок наступного. Для захисту
від зловживання це прийнятно — ми боронимося від тисяч запитів, а не від
подвоєння двох, — а коштує фіксоване вікно одного `INCR` замість
сортованої множини з прибиранням хвоста.

Якщо колись знадобиться точність на межі, змінюється реалізація, не
інтерфейс: `check()` вже повертає момент скидання.

## Чому дві реалізації

`RedisRateLimiter` — для продукту: лічильник спільний для всіх процесів
API, інакше три воркери означають потрійну норму.

`MemoryRateLimiter` — для тестів і локального запуску без Redis. Це не
заглушка «нічого не робить»: він рахує по-справжньому, просто в межах
процесу. Ліміт, який у тестах завжди дозволяє, не перевіряє нічого — а
саме перевірити поведінку на межі тут і потрібно.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class Decision:
    """Відповідь лічильника.

    `remaining` і `reset_after` існують, щоб їх віддати клієнту
    заголовками: відмова, яка не каже, коли можна повторити, змушує
    добросовісного клієнта поводитися як зловмисник.
    """

    allowed: bool
    limit: int
    remaining: int
    reset_after: int
    """Секунд до скидання вікна."""


class RateLimiter(Protocol):
    """Лічильник спроб за ключем."""

    async def check(self, key: str, *, limit: int, window: int) -> Decision:
        """Порахувати спробу й сказати, чи вона в межах.

        Спроба рахується **завжди**, зокрема й та, що отримала відмову:
        інакше той, хто впирається в межу, скидав би собі вікно частими
        запитами.
        """
        ...


class MemoryRateLimiter:
    """Лічильник у памʼяті процесу. Для тестів і запуску без Redis."""

    def __init__(self) -> None:
        self._hits: dict[str, tuple[int, float]] = {}

    async def check(self, key: str, *, limit: int, window: int) -> Decision:
        now = time.monotonic()
        count, started = self._hits.get(key, (0, now))
        if now - started >= window:
            count, started = 0, now
        count += 1
        self._hits[key] = (count, started)
        reset_after = max(0, int(window - (now - started)))
        return Decision(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            reset_after=reset_after,
        )

    def reset(self) -> None:
        """Для тестів: забути все, що порахували."""
        self._hits.clear()


class RedisRateLimiter:
    """Лічильник у Redis: спільний для всіх процесів API."""

    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def check(self, key: str, *, limit: int, window: int) -> Decision:
        # INCR і EXPIRE одним конвеєром: два окремі виклики лишають вікно
        # без строку, якщо процес помер між ними, і ключ живе вічно.
        # EXPIRE ставиться щоразу, а не лише на першій спробі — так
        # дешевше, ніж читати TTL, щоб вирішити, чи його ставити.
        pipe = self._redis.pipeline()
        pipe.incr(key)
        pipe.expire(key, window, nx=True)
        pipe.ttl(key)
        count, _, ttl = await pipe.execute()
        reset_after = int(ttl) if isinstance(ttl, int) and ttl > 0 else window
        return Decision(
            allowed=int(count) <= limit,
            limit=limit,
            remaining=max(0, limit - int(count)),
            reset_after=reset_after,
        )


def build_rate_limiter() -> RateLimiter:
    """Лічильник за конфігурацією застосунку.

    Redis — той самий, що вже тримає чергу. Окремий інстанс під
    лічильник не потрібен: навантаження мізерне, а друга залежність
    означала б другий спосіб зламати старт.
    """
    from app.core.config import settings

    if not settings.redis_url:
        return MemoryRateLimiter()
    return RedisRateLimiter(Redis.from_url(settings.redis_url))
