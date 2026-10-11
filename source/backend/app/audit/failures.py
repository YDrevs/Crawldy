"""Чому адреса не дала сторінки — і чи це взагалі про нас.

`ctx.failed_urls` довго був однією купою, і покриття питало в неї
«скільки адрес не вдалося». Питання неправильне. У купі лежать дві
різні речі:

* сервер **не дав** нам вмісту — DNS не резолвиться, зʼєднання відпало,
  таймаут, 403, 429, 503. Доказу немає, і судити сайт за рештою
  сторінок означає судити за вибіркою, якої ми не обирали;
* сервер **сказав** нам про ресурс — 404 або 410. Це доказ, і ми його
  отримали. Адреса мертва, ми це знаємо напевно, і саме це живить
  `seo.broken_links`.

Різниця не академічна. На вибірці night3 з 42 сайтів, яким через
`crawl.failures` не давали бала, **16 були гейтнуті майже цілком через
404**: scikit-learn.org прочитано 11 сторінок без єдиної помилки
доступу, знайдено 14 биті посилання — і за це в нього забрали оцінку
SEO, готовності до ШІ та придатності до цитування. Тобто чим більше на
сайті биті посилань, тим менше ми беремося його судити. Сайт тікає від
оцінки рівно за ту ваду, заради якої нас і кличуть.

Питання, яке тепер ставить покриття, звучить так: **чи не вдалося нам
дістати доказ, бо до цілі не достукатись** — а не «чи був статус не
2xx».

Кодування причини рядком лишається: воно вже лежить у знімках, і
перерахунок старого аудиту має читатися так само, як свіжого. Але
розбирає цей рядок одне місце — тут. Той самий урок, що й з `msg`:
рядок годиться як формат зберігання й не годиться як ідентифікатор,
розкиданий по коду.
"""

from __future__ import annotations

import re
from enum import StrEnum

# Сервер авторитетно сказав про сам ресурс. Ми отримали доказ, і він
# лишається знахідкою: 404 — «сторінки немає», 410 — «була й прибрана».
_OBSERVED_STATUSES = frozenset({404, 410})

# Нас не пустили або не змогли обслужити. Вміст ми не отримали.
#   401/403 — відмовили; 407 — проксі; 408 — сервер утомився чекати;
#   429 — притримали (часто саме нас); 5xx — не змогли віддати.
_ACCESS_STATUSES = frozenset({401, 403, 407, 408, 429})

# Помилки транспорту, у яких відповіді не було взагалі. Порівнюємо за
# іменем класу винятку httpx, бо саме воно стоїть на початку рядка.
_ACCESS_TRANSPORT = (
    "ConnectError", "ConnectTimeout", "ReadTimeout", "WriteTimeout", "PoolTimeout",
    "ReadError", "WriteError", "ProtocolError", "RemoteProtocolError", "LocalProtocolError",
    "ProxyError", "UnsupportedProtocol", "TooManyRedirects", "NetworkError",
    "DecodingError", "TimeoutException", "TransportError", "ConnectionError",
)

# Наші власні артефакти черги, а не властивість сайту: порожня адреса,
# схема, якої ми не ходимо, SSRF-гард. Сайт тут ні до чого, і рахувати
# їх як «до сайту не достукатись» означало б ту саму помилку, що й з
# 404 — приписати сайту наше рішення.
_OUR_SIDE = ("порожній URL", "URL без хоста", "схема ", "резолвиться у приватний IP")

_STATUS = re.compile(r"^HTTP (\d{3})$")


class FailureKind(StrEnum):
    """Чим саме була невдача — з погляду «чи є в нас доказ»."""

    # До цілі не достукатись: транспорт, доступність, відмова, обмеження.
    ACCESS = "access"
    # Ціль відповіла про себе: 404, 410. Доказ отриманий.
    OBSERVED = "observed"
    # Наш власний артефакт: адреса, якою ми й не мали ходити.
    OUR_SIDE = "our_side"
    # Значення, яке не можна чесно віднести ні туди, ні сюди.
    AMBIGUOUS = "ambiguous"


def status_of(reason: str) -> int | None:
    """HTTP-статус із причини, якщо відповідь узагалі була."""
    match = _STATUS.match(reason.strip())
    return int(match.group(1)) if match else None


def classify(reason: str) -> FailureKind:
    """Категорія однієї причини.

    Порядок перевірок відповідає порядку впевненості: спершу те, що
    розбирається однозначно (статус), потім відомі імена винятків, і
    лише наприкінці — здогади. Невідоме лишається `AMBIGUOUS`, а не
    вливається в найближчу категорію: мовчазне віднесення до `ACCESS`
    забирало б у сайту бал за наш власний недогляд.
    """
    text = (reason or "").strip()
    if not text:
        return FailureKind.AMBIGUOUS

    status = status_of(text)
    if status is not None:
        if status in _OBSERVED_STATUSES:
            return FailureKind.OBSERVED
        if status in _ACCESS_STATUSES or 500 <= status <= 599:
            return FailureKind.ACCESS
        # Решта 4xx — 400, 405, 406, 409, 415, 451… Кожен має свою
        # історію, і спільної відповіді в них немає. Не вигадуємо.
        return FailureKind.AMBIGUOUS

    if any(marker in text for marker in _OUR_SIDE):
        return FailureKind.OUR_SIDE
    # DNS не резолвиться — хоста немає. Це недоступність цілі, а не наш
    # артефакт: адреса цілком законна, за нею просто нічого немає.
    if text.startswith("DNS"):
        return FailureKind.ACCESS
    name = text.split(":", 1)[0].strip()
    if name in _ACCESS_TRANSPORT:
        return FailureKind.ACCESS
    return FailureKind.AMBIGUOUS


def blocks_evidence(reason: str) -> bool:
    """Чи означає ця причина, що доказу про сторінку ми не дістали.

    Єдине питання, яке має ставити логіка покриття. `OBSERVED` — доказ
    у нас є. `OUR_SIDE` — до сайту претензій немає, ми самі поставили в
    чергу те, чого не мали. `AMBIGUOUS` не гейтить свідомо: забрати бал
    через значення, якого ми не розібрали, — гірше, ніж його лишити,
    і на вибірці таких випадків троє на 958 аудитів.
    """
    return classify(reason) is FailureKind.ACCESS


def summarize(reasons: list[str]) -> dict[str, int]:
    """Скільки причин кожної категорії. Для доказів у звіті."""
    counts = dict.fromkeys((k.value for k in FailureKind), 0)
    for reason in reasons:
        counts[classify(reason).value] += 1
    return counts


__all__ = [
    "FailureKind",
    "blocks_evidence",
    "classify",
    "status_of",
    "summarize",
]
