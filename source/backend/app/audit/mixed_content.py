"""Незахищені підресурси на захищеній сторінці — і що з ними робить браузер.

## Дві різні речі, які не можна злити в одну

**Заявлене** — розмітка просить `http://…`. Це факт про сайт, і він
лишається фактом, хоч би що потім зробив браузер.

**Спостережене** — що сталося насправді: браузер підвищив схему до
https, заблокував запит, зробив його як є, або ми просто не бачили.
Спостережене є лише для сторінок, які ми відкривали в браузері, а їх
щонайбільше три на аудит.

Зливати їх не можна в жоден бік. Сказати «ресурс заблоковано», не
бачивши блокування, — вигадка. Сказати «все гаразд, бо браузер підвищить
схему» — теж: підвищення працює, лише поки https-версія ресурсу існує,
і в розмітці лишається адреса, яка одного дня перестане відповідати.

## Чому не ACTIVE/PASSIVE

Стара двійка не описує сучасну поведінку. Специфікація розрізняє
запити, які браузер блокує, і ті, які він мовчки підвищує; крім них є
завантаження з захищеної сторінки, і є випадки, яких ми чесно не знаємо.
Звідси пʼять станів, а не два.

## Чого тут немає

Навігації. `<a href="http://…">` із https-сторінки — це звичайне
посилання на незахищений сайт, а не змішаний вміст: браузер нічого не
підвантажує, він переходить. Плутати їх означало б лаяти сайт за те,
чого не сталося. Екстрактор такі посилання й не збирає.

Сканування вразливостей теж немає й не буде: тут рівно те, що видно з
розмітки сторінки й журналу запитів браузера.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from app.audit.logical_pages import normalize
from app.audit.types import PageSignals


class Handling(StrEnum):
    """Як сучасний браузер має повестися з цим запитом."""

    # Запит, який браузер не підвищує й не пропускає.
    BLOCKABLE = "blockable"
    # Зображення, аудіо, відео: схему браузер підвищує сам.
    UPGRADEABLE = "upgradeable"
    # Завантаження файлу з захищеної сторінки по http.
    MIXED_DOWNLOAD = "mixed_download"
    # Не підресурс: навігація й подібне.
    NOT_MIXED = "not_mixed"
    # Випадок, про який ми не беремося судити.
    UNKNOWN = "unknown"


class Observed(StrEnum):
    """Що ми справді бачили в журналі запитів браузера."""

    # Браузер пішов по https за тією самою адресою.
    UPGRADED = "upgraded"
    # Запит пішов саме по http — ми бачили це на власні очі.
    REQUESTED_INSECURELY = "requested_insecurely"
    # Сторінку відкривали, але цього запиту в журналі немає.
    NOT_OBSERVED = "not_observed"
    # Сторінку в браузері не відкривали — питання не ставилось.
    NO_RENDER = "no_render"


# Призначення запиту, які браузер підвищує сам.
_UPGRADEABLE_KINDS = frozenset({"img", "audio", "video", "source", "track", "icon"})
# Призначення, які він блокує.
_BLOCKABLE_KINDS = frozenset(
    {"script", "stylesheet", "preload", "iframe", "embed", "object", "xhr", "fetch"}
)


def _is_ip_host(host: str) -> bool:
    """Хост — це літерал IP, а не імʼя.

    Алгоритм підвищення схеми до таких не застосовується, тож зараховувати
    їх до «браузер полагодить сам» було б неправдою.
    """
    bare = host.split(":")[0].strip("[]")
    try:
        ipaddress.ip_address(bare)
    except ValueError:
        return False
    return True


def classify(kind: str, url: str) -> Handling:
    """Клас поведінки за призначенням запиту й адресою."""
    if kind == "download":
        return Handling.MIXED_DOWNLOAD
    if kind in _BLOCKABLE_KINDS:
        return Handling.BLOCKABLE
    if kind in _UPGRADEABLE_KINDS:
        # Підвищення не застосовується до IP-літерала, а що зроблять
        # різні браузери далі — ми не міряли. Чесна відповідь: не знаємо.
        if _is_ip_host(urlparse(url).netloc.lower()):
            return Handling.UNKNOWN
        return Handling.UPGRADEABLE
    return Handling.UNKNOWN


@dataclass(frozen=True, slots=True)
class Reference:
    """Один незахищений підресурс на захищеній сторінці."""

    page: str
    url: str
    kind: str
    handling: Handling
    observed: Observed
    # response | render | both — де саме ми побачили це в розмітці.
    seen_in: str = "response"
    third_party: bool = False
    in_srcset: bool = False

    def as_evidence(self) -> dict[str, Any]:
        return {
            "page": self.page,
            "url": self.url,
            "type": self.kind,
            "handling": self.handling.value,
            "observed": self.observed.value,
            "seen_in": self.seen_in,
            "third_party": self.third_party,
            "in_srcset": self.in_srcset,
        }


@dataclass(slots=True)
class Analysis:
    """Незахищені підресурси сайту разом із межами спостереження."""

    references: list[Reference] = field(default_factory=list)
    # Сторінки на https, які ми взагалі розглядали.
    secure_pages: int = 0
    # Сторінки, відкриті в браузері: лише про них є спостережене.
    rendered_pages: int = 0
    # Сторінки, чий CSP просить браузер підвищувати схему сам.
    pages_with_upgrade_directive: int = 0

    def by_handling(self) -> dict[Handling, list[Reference]]:
        out: dict[Handling, list[Reference]] = {}
        for ref in self.references:
            out.setdefault(ref.handling, []).append(ref)
        return out

    def coverage(self) -> dict[str, Any]:
        return {
            "secure_pages": self.secure_pages,
            "rendered_pages": self.rendered_pages,
            "pages_with_upgrade_insecure_requests": self.pages_with_upgrade_directive,
            # Скільки посилань ми могли підтвердити журналом браузера.
            "runtime_evidence_available": self.rendered_pages > 0,
        }


def _requests_of(ctx: Any, page: PageSignals) -> list[str] | None:
    """Адреси, які браузер справді запитав. None — сторінку не рендерили."""
    result = ctx.renders.get(page.url) if hasattr(ctx, "renders") else None
    if result is None or not getattr(result, "rendered", False):
        return None
    return list(result.requests)


def _observe(url: str, requests: list[str] | None) -> Observed:
    """Що журнал браузера каже про цю конкретну адресу."""
    if requests is None:
        return Observed.NO_RENDER
    if url in requests:
        return Observed.REQUESTED_INSECURELY
    upgraded = "https://" + url[len("http://"):]
    if upgraded in requests:
        return Observed.UPGRADED
    return Observed.NOT_OBSERVED


def _third_party(ctx: Any, url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return bool(host) and host != urlparse(ctx.origin).netloc.lower()


def _upgrade_directive(page: PageSignals) -> bool:
    policy = (page.header("content-security-policy") or "").lower()
    return "upgrade-insecure-requests" in policy


def analyse(ctx: Any) -> Analysis:
    """Незахищені підресурси всіх прочитаних захищених сторінок.

    Сторінки на http пропускаються цілком: змішаний вміст існує лише в
    захищеному контексті, а про незахищений документ говорить `seo.https`.
    Дублювати той самий корінь двома знахідками не можна.
    """
    result = Analysis()
    for page in ctx.ok_pages:
        if not page.url.lower().startswith("https://"):
            continue
        result.secure_pages += 1
        if _upgrade_directive(page):
            result.pages_with_upgrade_directive += 1

        requests = _requests_of(ctx, page)
        if requests is not None:
            result.rendered_pages += 1

        rendered = ctx.renders.get(page.url) if hasattr(ctx, "renders") else None
        after = getattr(rendered, "signals", None) if rendered is not None else None
        in_response = {(r.url, r.kind) for r in page.insecure_refs}
        in_render = {(r.url, r.kind) for r in (after.insecure_refs if after else [])}

        for url, kind in sorted(in_response | in_render):
            if (url, kind) in in_response and (url, kind) in in_render:
                seen = "both"
            elif (url, kind) in in_render:
                seen = "render"
            else:
                seen = "response"
            source = next(
                r for r in ([*page.insecure_refs, *(after.insecure_refs if after else [])])
                if (r.url, r.kind) == (url, kind)
            )
            result.references.append(
                Reference(
                    page=page.url,
                    url=url,
                    kind=kind,
                    handling=classify(kind, url),
                    observed=_observe(url, requests),
                    seen_in=seen,
                    third_party=_third_party(ctx, url),
                    in_srcset=source.in_srcset,
                )
            )

    # Запити, яких у розмітці не було: їх робить сам скрипт. Журнал
    # браузера — єдине місце, де це видно, і саме він тут доказ.
    result.references.extend(_from_network(ctx, result))
    return result


def _from_network(ctx: Any, analysis: Analysis) -> list[Reference]:
    """Незахищені запити з журналу браузера, яких немає в розмітці."""
    declared = {(r.page, r.url) for r in analysis.references}
    found: list[Reference] = []
    for url, render in (getattr(ctx, "renders", {}) or {}).items():
        if not getattr(render, "rendered", False):
            continue
        if not url.lower().startswith("https://"):
            continue
        for request in dict.fromkeys(render.requests):
            if not request.lower().startswith("http://"):
                continue
            if (url, request) in declared:
                continue
            found.append(
                Reference(
                    page=url,
                    url=request,
                    # Призначення запиту журнал не зберігає, і вгадувати
                    # його з адреси означало б вигадувати клас поведінки.
                    kind="request",
                    handling=Handling.UNKNOWN,
                    observed=Observed.REQUESTED_INSECURELY,
                    seen_in="network",
                    third_party=_third_party(ctx, request),
                )
            )
    return found


def pages_with(references: list[Reference]) -> int:
    return len({normalize(r.page) for r in references})


__all__ = [
    "Analysis",
    "Handling",
    "Observed",
    "Reference",
    "analyse",
    "classify",
    "pages_with",
]
