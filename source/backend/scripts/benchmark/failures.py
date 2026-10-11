"""Класи збоїв: чия це проблема — сайту чи наша.

## Навіщо не один `error`

«Не вдалося» без причини — марні дані. Тисяча сайтів дасть кількасот
збоїв, і без розділення неможливо відповісти на єдине питання, яке тут
важить: це властивість сайтів чи дефект нашого прогону. DNS, який не
резолвиться, — світ; виняток усередині Crawldy — ми.

Той самий поділ, що вже стоїть у `Verdict` для знахідок і в
`Degradation.is_failure` для модулів: причина без розрізнення не читається.
"""

from __future__ import annotations

from enum import StrEnum


class Failure(StrEnum):
    """Чому сайт не пройшов."""

    # ── проблеми на боці світу ────────────────────────────────────────
    DNS = "dns"
    CONNECTION = "connection"
    TLS = "tls"
    TIMEOUT = "timeout"
    # Сайт відповів, але нас не пустили: 403, WAF, robots.
    ACCESS_DENIED = "access_denied"
    # Адреса заблокована нашою ж перевіркою SSRF — приватний IP тощо.
    UNSAFE_TARGET = "unsafe_target"
    # Краул відпрацював, але не приніс жодної сторінки.
    EMPTY_CRAWL = "empty_crawl"

    # ── проблеми на нашому боці ───────────────────────────────────────
    RENDERER = "renderer"
    # Сайт не вклався у відведений час — це наша межа, а не його вада.
    SITE_TIMEOUT = "site_timeout"
    INTERNAL = "internal"

    UNKNOWN = "unknown"


# Збої, які описують світ. Решта — наші, і саме їх треба дивитися перед
# тим, як робити висновки з корпусу.
SITE_SIDE = frozenset({
    Failure.DNS, Failure.CONNECTION, Failure.TLS, Failure.TIMEOUT,
    Failure.ACCESS_DENIED, Failure.UNSAFE_TARGET, Failure.EMPTY_CRAWL,
})


def ours(failure: Failure) -> bool:
    return failure not in SITE_SIDE


# Ознаки в тексті винятку. Розбір рядка тут прийнятний саме тому, що це
# внутрішній інструмент: помилка класифікації псує зріз статистики, а не
# твердження клієнтові. У продуктових шляхах проєкт цього не робить.
_MARKERS: tuple[tuple[str, Failure], ...] = (
    ("не резолвиться", Failure.DNS),
    ("gaierror", Failure.DNS),
    ("nodename nor servname", Failure.DNS),
    ("name or service not known", Failure.DNS),
    ("приватний ip", Failure.UNSAFE_TARGET),
    ("unsafeurlerror", Failure.UNSAFE_TARGET),
    ("certificate", Failure.TLS),
    ("sslerror", Failure.TLS),
    ("ssl:", Failure.TLS),
    ("tlsv1", Failure.TLS),
    ("timeout", Failure.TIMEOUT),
    ("timed out", Failure.TIMEOUT),
    ("connecterror", Failure.CONNECTION),
    ("connection refused", Failure.CONNECTION),
    ("connection reset", Failure.CONNECTION),
    ("remoteprotocolerror", Failure.CONNECTION),
    ("siteunreachable", Failure.CONNECTION),
    ("403", Failure.ACCESS_DENIED),
    ("forbidden", Failure.ACCESS_DENIED),
    ("playwright", Failure.RENDERER),
    ("browser", Failure.RENDERER),
)


def classify(exception: BaseException | None, *, detail: str = "") -> Failure:
    """Виняток → клас збою."""
    if exception is None and not detail:
        return Failure.UNKNOWN
    if isinstance(exception, TimeoutError):
        return Failure.SITE_TIMEOUT
    text = f"{type(exception).__name__ if exception else ''} {exception or ''} {detail}".lower()
    for marker, failure in _MARKERS:
        if marker in text:
            return failure
    # Виняток, який ми не впізнали, найімовірніше наш: чужі мережеві
    # помилки мають упізнавані підписи, а наші — ні.
    return Failure.INTERNAL if exception is not None else Failure.UNKNOWN


def retryable(failure: Failure) -> bool:
    """Чи має сенс повторювати.

    Повторюємо лише те, що буває тимчасовим. 403 і приватний IP другого
    разу не зміняться, а внутрішній виняток повторить сам себе — і
    ховати його повтором означало б ховати наш власний дефект.
    """
    return failure in {
        Failure.CONNECTION, Failure.TIMEOUT, Failure.SITE_TIMEOUT, Failure.DNS,
    }


__all__ = ["SITE_SIDE", "Failure", "classify", "ours", "retryable"]
