"""Як відповідь доїхала: стиснення й версія протоколу.

## Два твердження, які легко переплутати

**Про відповідь** — «цю відповідь віддано без стиснення», «для цього
запиту погоджено HTTP/2». Це ми бачили.

**Про сервер** — «сервер не вміє стискати», «сервер не підтримує
HTTP/2». Цього ми не бачили й побачити не можемо. Погоджений протокол
залежить від ALPN, від CDN на шляху і від того, що вміє наша власна
бібліотека; стиснення — від того, що ми попросили в `Accept-Encoding`.

Модуль існує рівно для того, щоб друге ніколи не виводилося з першого.

## Що ми просимо і чого не просимо

httpx надсилає `Accept-Encoding: gzip, deflate`. Brotli й Zstandard у
списку немає, бо відповідних пакетів в оточенні немає. Отже, сервер,
який вміє лише Brotli, віддасть нам identity — і назвати це «не стискає»
було б неправдою про сервер, зате правдою про нашу вимірювальну
установку. Тому `advertised` зберігається поруч із результатом, а
висновок звучить як «ця відповідь прийшла без стиснення».

## Розміри

httpx розпаковує тіло сам, тож довжина тіла — це РОЗПАКОВАНИЙ розмір.
`Content-Length` при цьому описує те, що справді їхало мережею. Це різні
величини, і ділити одну на одну можна лише тоді, коли обидві є і немає
`Transfer-Encoding: chunked` — інакше `Content-Length` відсутній або
означає інше. Коли впевненості немає, розмір лишається `None`, а не
вигаданим числом.

## Чого тут немає

Порівняння CDN, замірів затримки, тюнінгу QUIC і бенчмарків. Тільки те,
що видно з однієї відповіді.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.audit.types import PageSignals


class Coding(StrEnum):
    """Що сказано в `Content-Encoding` цієї відповіді."""

    GZIP = "gzip"
    BROTLI = "br"
    ZSTD = "zstd"
    DEFLATE = "deflate"
    # Заголовка немає або він `identity`: представлення не кодоване.
    IDENTITY = "identity"
    # Кодування є, але не з тих, які ми впізнаємо.
    OTHER = "other"


# Кодування, зареєстровані для HTTP. `zstd` — RFC 8878 і RFC 9659,
# `br` — RFC 7932, решта — RFC 9110. Перелік короткий і майже не
# змінюється, тож окремого реєстру з провенансом він не потребує.
_KNOWN = {
    "gzip": Coding.GZIP,
    "x-gzip": Coding.GZIP,
    "br": Coding.BROTLI,
    "zstd": Coding.ZSTD,
    "deflate": Coding.DEFLATE,
    "identity": Coding.IDENTITY,
}


class Compressibility(StrEnum):
    """Чи має стиснення сенс для цього типу вмісту."""

    # Текстове представлення: стиснення зазвичай зменшує обсяг помітно.
    TEXTUAL = "textual"
    # Уже стиснений або погано стисний формат: зображення, шрифти, відео.
    ALREADY_COMPRESSED = "already_compressed"
    # Типу немає або він нам невідомий — не судимо.
    UNKNOWN = "unknown"


# Типи, які стискаються з користю. Беремо саме `Content-Type`, а не
# розширення: розширення бреше, і це в цьому проєкті вже коштувало
# помилок.
_TEXTUAL_EXACT = frozenset({
    "application/json", "application/ld+json", "application/xml",
    "application/xhtml+xml", "application/javascript", "application/x-javascript",
    "application/rss+xml", "application/atom+xml", "image/svg+xml",
    "application/manifest+json", "application/wasm",
})
_TEXTUAL_PREFIX = ("text/",)

# Формати, у яких транспортне стиснення майже нічого не дає: дані вже
# стиснені власним алгоритмом.
_COMPRESSED_EXACT = frozenset({
    "font/woff", "font/woff2", "application/font-woff", "application/font-woff2",
    "application/zip", "application/gzip", "application/x-gzip",
    "application/x-7z-compressed", "application/x-rar-compressed",
    "application/pdf", "application/octet-stream",
})
_COMPRESSED_PREFIX = ("image/", "audio/", "video/")


class Source(StrEnum):
    """Хто саме спостерігав цей транспорт."""

    CRAWLER = "crawler"
    BROWSER = "browser"


def client_offers_http2() -> bool:
    """Чи вміє НАШ клієнт погодити HTTP/2 у цьому середовищі.

    Це твердження про вимірювальну установку, і без нього спостереження
    «HTTP/1.1» не означає нічого: клієнт, який не вміє інакше, отримає
    HTTP/1.1 від будь-кого. `httpx` вмикає HTTP/2 лише за наявності
    пакета `h2`, тож перевіряємо саме його.
    """
    import importlib.util

    return importlib.util.find_spec("h2") is not None


def coding_of(header: str | None) -> Coding:
    """`Content-Encoding` → впізнане кодування.

    Береться перше кодування списку: воно й описує представлення, яке
    ми отримали.
    """
    value = (header or "").strip().lower()
    if not value:
        return Coding.IDENTITY
    first = value.split(",")[0].strip()
    return _KNOWN.get(first, Coding.OTHER)


def compressibility_of(content_type: str | None) -> Compressibility:
    """Тип вмісту → чи варто його стискати в транспорті."""
    value = (content_type or "").split(";")[0].strip().lower()
    if not value:
        return Compressibility.UNKNOWN
    if value in _TEXTUAL_EXACT or value.startswith(_TEXTUAL_PREFIX):
        return Compressibility.TEXTUAL
    if value in _COMPRESSED_EXACT or value.startswith(_COMPRESSED_PREFIX):
        return Compressibility.ALREADY_COMPRESSED
    # Невідомий тип лишається невідомим: обережність тут дешевша за
    # пораду стискати те, що стискати не треба.
    return Compressibility.UNKNOWN


def offers(advertised: str, coding: Coding) -> bool:
    """Чи просили ми саме це кодування.

    Без цього «сервер не стиснув» не є твердженням: сервер, який уміє
    лише Brotli, віддасть identity клієнту, який Brotli не просив.
    """
    wanted = {part.split(";")[0].strip().lower() for part in (advertised or "").split(",")}
    return coding.value in wanted or "*" in wanted


@dataclass(frozen=True, slots=True)
class Observation:
    """Транспорт однієї відповіді так, як його видно."""

    url: str
    source: Source
    protocol: str | None
    coding: Coding
    compressibility: Compressibility
    content_type: str | None
    advertised: str
    # Скільки байтів справді їхало. `None` — довіряти нема чому.
    encoded_bytes: int | None
    # Розмір після розпакування. Його ми знаємо завжди.
    decoded_bytes: int

    @property
    def unencoded_text(self) -> bool:
        """Текстова відповідь, віддана без кодування, коли ми його просили."""
        return (
            self.compressibility is Compressibility.TEXTUAL
            and self.coding is Coding.IDENTITY
            and offers(self.advertised, Coding.GZIP)
        )

    def as_evidence(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "observed_by": self.source.value,
            "protocol": self.protocol or "unknown",
            "content_encoding": self.coding.value,
            "content_type": self.content_type,
            "requested_encodings": self.advertised or "unknown",
            "bytes_over_the_wire": self.encoded_bytes,
            "bytes_after_decoding": self.decoded_bytes,
        }


@dataclass(slots=True)
class Analysis:
    """Транспорт усього прочитаного разом із межами спостереження."""

    observations: list[Observation] = field(default_factory=list)
    # Скільки відповідей узагалі несли транспортні дані.
    known: int = 0
    # Скільки не несли: знімок старший за поля, або запит не вдався.
    unknown: int = 0

    @property
    def unencoded(self) -> list[Observation]:
        return [o for o in self.observations if o.unencoded_text]

    def protocols(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for observation in self.observations:
            found[observation.protocol or "unknown"] = (
                found.get(observation.protocol or "unknown", 0) + 1
            )
        return dict(sorted(found.items()))

    def codings(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for observation in self.observations:
            if observation.compressibility is not Compressibility.TEXTUAL:
                continue
            found[observation.coding.value] = found.get(observation.coding.value, 0) + 1
        return dict(sorted(found.items()))

    def coverage(self) -> dict[str, Any]:
        return {
            "responses_with_transport_data": self.known,
            "responses_without_transport_data": self.unknown,
            "protocols": self.protocols(),
            "text_content_encodings": self.codings(),
            # Твердження про нас, а не про сайт — але без нього
            # спостереження про протокол не має сенсу.
            "client_offers_http2": client_offers_http2(),
            # HTTP/3 наш стек не погоджує, тож його відсутність —
            # невідомість, а не факт про сайт.
            "client_offers_http3": False,
        }


def _encoded_bytes(page: PageSignals) -> int | None:
    """Скільки байтів їхало мережею — або None, якщо це не доводиться.

    `Content-Length` описує кодоване представлення. При `chunked` його
    немає або воно означає інше, тож ділити на нього не можна.
    """
    if (page.header("transfer-encoding") or "").lower().find("chunked") >= 0:
        return None
    raw = page.header("content-length")
    if raw is None:
        return None
    try:
        value = int(raw.strip())
    except (TypeError, ValueError):
        return None
    return value if value >= 0 else None


def observe(page: PageSignals) -> Observation | None:
    """Транспорт однієї сторінки, як його бачив краулер."""
    if not page.http_version and not page.headers:
        return None
    return Observation(
        url=page.url,
        source=Source.CRAWLER,
        protocol=page.http_version or None,
        coding=coding_of(page.header("content-encoding")),
        compressibility=compressibility_of(page.content_type),
        content_type=page.content_type,
        advertised=page.accept_encoding,
        encoded_bytes=_encoded_bytes(page),
        decoded_bytes=page.html_bytes,
    )


def analyse(ctx: Any) -> Analysis:
    """Транспорт усіх прочитаних сторінок."""
    result = Analysis()
    for page in ctx.ok_pages:
        observation = observe(page)
        if observation is None or observation.protocol is None:
            # Поле зʼявилося пізніше за цей знімок. Це «не знаємо», а не
            # «HTTP/1.1» і не «без стиснення».
            result.unknown += 1
            if observation is None:
                continue
        else:
            result.known += 1
        result.observations.append(observation)
    return result


__all__ = [
    "Analysis",
    "Coding",
    "Compressibility",
    "Observation",
    "Source",
    "analyse",
    "coding_of",
    "compressibility_of",
    "observe",
    "offers",
]
