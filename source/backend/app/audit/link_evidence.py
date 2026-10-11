"""Хто на кого посилається — поіменно, з текстом і походженням.

## Що тут з'явилося нового

Нічого зі збору. `LinkRef` несе адресу, текст, `rel` і `in_chrome` давно;
відрендерені посилання лежать у `RenderResult.signals.links`; граф рахує
входження. Бракувало з'єднання: граф знає, що на сторінку веде вісім
посилань, і не знає, з яких саме сторінок і якими словами. Через це
знахідка про зламані адреси вміла сказати «404», але не вміла сказати,
де це полагодити.

## Чому окремий модуль, а не поле в чеку

Наступний пункт дорожньої карти — якість тексту посилань, і йому
потрібні рівно ці самі спостереження. Масив, дописаний у чек про зламані
посилання, довелося б переписувати; тут же він з самого початку про
посилання взагалі, а не про їхню поламаність.

Судження тут немає жодного: ані про якість тексту, ані про серйозність.
Модуль відповідає на питання «що ми бачили», а не «що з цим не так».

## Межа, яку легко перейти

«Не перевіряли» — не те саме, що «зламано». Адреса, до якої не дійшов
бюджет краулу або яку закрив robots.txt, лишається невідомою, і
`TargetState` розводить ці випадки замість того, щоб згортати їх у
«битий». Підтвердженим вважається лише те, на що сервер відповів сам.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from app.audit.logical_pages import normalize
from app.audit.types import PageSignals


class Seen(StrEnum):
    """Де саме ми бачили це посилання."""

    RESPONSE = "response"
    RENDER = "render"
    BOTH = "both"


class TargetState(StrEnum):
    """Що ми знаємо про адресу, на яку ведуть посилання."""

    OK = "ok"
    CLIENT_ERROR = "client_error"
    SERVER_ERROR = "server_error"
    # Перенаправлення спрацювало, а те, куди воно привело, — ні.
    REDIRECT_TO_ERROR = "redirect_to_error"
    # Запит не вдався на рівні транспорту. Це може бути й наш бік, тож
    # підтвердженою поламкою сайту воно не рахується.
    FETCH_FAILED = "fetch_failed"
    # Не відкривали: не вистачило бюджету краулу.
    NOT_CHECKED = "not_checked"
    # Закрито robots.txt — ми свідомо не пішли, а не «не змогли».
    BLOCKED = "blocked"


# Стани, у яких сервер сам сказав, що сторінки немає. Лише вони мають
# право потрапити у твердження «посилання веде в помилку».
CONFIRMED_BROKEN = frozenset(
    {TargetState.CLIENT_ERROR, TargetState.SERVER_ERROR, TargetState.REDIRECT_TO_ERROR}
)


@dataclass(frozen=True, slots=True)
class Observation:
    """Одне посилання так, як ми його побачили."""

    source: str
    source_key: str
    target: str
    target_key: str
    anchor: str
    seen_in: Seen
    rel: str = ""
    in_chrome: bool = False

    def as_evidence(self) -> dict[str, Any]:
        return {
            "from": self.source,
            "anchor": self.anchor,
            "seen_in": self.seen_in.value,
            "in_chrome": self.in_chrome,
        }


@dataclass(frozen=True, slots=True)
class Destination:
    """Одна ціль і всі посилання, які на неї ведуть."""

    key: str
    url: str
    state: TargetState = TargetState.NOT_CHECKED
    status: int | None = None
    observations: tuple[Observation, ...] = ()
    detail: dict[str, Any] = field(default_factory=dict)

    @property
    def sources(self) -> tuple[str, ...]:
        """Різні сторінки, з яких ведуть посилання."""
        return tuple(dict.fromkeys(o.source for o in self.observations))

    @property
    def links(self) -> int:
        """Скільки посилань спостережено. Одна сторінка може мати кілька."""
        return len(self.observations)

    @property
    def broken(self) -> bool:
        return self.state in CONFIRMED_BROKEN

    def as_evidence(self, limit: int = 5) -> dict[str, Any]:
        """Показуємо обмежено, рахуємо повністю.

        Урізаний перелік не має вдавати повний: поруч завжди стоять
        справжні числа, а порядок сталий, щоб два прогони давали той
        самий доказ.
        """
        shown = sorted(
            self.observations, key=lambda o: (o.source_key, o.anchor)
        )[:limit]
        evidence: dict[str, Any] = {
            "url": self.url,
            "state": self.state.value,
            "status": self.status,
            "source_pages": len(self.sources),
            "links": self.links,
            "examples": [o.as_evidence() for o in shown],
            "examples_shown": len(shown),
            **self.detail,
        }
        if len(shown) < self.links:
            evidence["examples_truncated"] = True
        return evidence


def _internal_links(page: PageSignals) -> dict[str, tuple[str, str, bool]]:
    """Нормалізована ціль → (як написано, текст, чи це меню)."""
    found: dict[str, tuple[str, str, bool]] = {}
    for link in page.links:
        if not link.is_internal or not link.url:
            continue
        found.setdefault(normalize(link.url), (link.url, link.anchor, link.in_chrome))
    return found


def _observations(ctx: Any, page: PageSignals) -> list[Observation]:
    """Посилання однієї сторінки з позначкою, де саме їх видно.

    Обидва переліки вже розібрані: відповідь сервера — краулом,
    відрендерений DOM — тим самим `extract` під час рендеру. Другого
    порівняння DOM тут немає й не потрібно.
    """
    response = _internal_links(page)
    rendered: dict[str, tuple[str, str, bool]] = {}
    render = ctx.renders.get(page.url) if hasattr(ctx, "renders") else None
    if render is not None and getattr(render, "signals", None) is not None:
        rendered = _internal_links(render.signals)

    source_key = normalize(page.url)
    out: list[Observation] = []
    for key in dict.fromkeys((*response, *rendered)):
        written, anchor, in_chrome = response.get(key) or rendered[key]
        if key in response and key in rendered:
            seen = Seen.BOTH
        elif key in rendered:
            seen = Seen.RENDER
        else:
            # Рендеру не було — тоді все, що ми маємо, це відповідь, і
            # називати її «лише відповіддю» коректно: іншого джерела
            # для цієї сторінки не існує.
            seen = Seen.RESPONSE
        out.append(
            Observation(
                source=page.url,
                source_key=source_key,
                target=written,
                target_key=key,
                anchor=anchor,
                seen_in=seen,
                in_chrome=in_chrome,
            )
        )
    return out


def _state_of(ctx: Any, key: str, known: dict[str, PageSignals]) -> Destination:
    """Що сервер відповів за цією адресою — або чому ми не знаємо."""
    page = known.get(key)
    if page is not None:
        status = page.status_code
        redirected = bool(page.redirect_chain) and normalize(page.url) != key
        if status is not None and 400 <= status < 500:
            state = TargetState.REDIRECT_TO_ERROR if redirected else TargetState.CLIENT_ERROR
        elif status is not None and status >= 500:
            state = TargetState.REDIRECT_TO_ERROR if redirected else TargetState.SERVER_ERROR
        else:
            state = TargetState.OK
        detail: dict[str, Any] = {}
        if redirected:
            detail["final_url"] = page.url
            detail["redirects"] = len(page.redirect_chain)
        return Destination(key=key, url=page.url if not redirected else key,
                           state=state, status=status, detail=detail)

    failure = ctx.failed_urls.get(key) or _failure_for(ctx, key)
    if failure:
        # Краул записує свої відмови рядком `HTTP <код>`; усе інше —
        # транспорт. Це наш власний формат, а не чужої бібліотеки.
        if failure.startswith("HTTP 4"):
            return Destination(key=key, url=key, state=TargetState.CLIENT_ERROR,
                               status=_code(failure))
        if failure.startswith("HTTP 5"):
            return Destination(key=key, url=key, state=TargetState.SERVER_ERROR,
                               status=_code(failure))
        return Destination(key=key, url=key, state=TargetState.FETCH_FAILED,
                           detail={"error": failure})

    if _blocked(ctx, key):
        return Destination(key=key, url=key, state=TargetState.BLOCKED)
    return Destination(key=key, url=key, state=TargetState.NOT_CHECKED)


def _failure_for(ctx: Any, key: str) -> str:
    for url, reason in ctx.failed_urls.items():
        if normalize(url) == key:
            return str(reason)
    return ""


def _code(reason: str) -> int | None:
    tail = reason.split()[-1]
    return int(tail) if tail.isdigit() else None


def _blocked(ctx: Any, url: str) -> bool:
    parsed = getattr(ctx.robots, "parsed", None)
    if parsed is None or getattr(parsed, "empty", True):
        return False
    from app.core.config import settings

    path = urlparse(url).path or "/"
    return not bool(parsed.evaluate(settings.user_agent, path).allowed)


def collect(ctx: Any) -> dict[str, Destination]:
    """Усі внутрішні посилання сайту, згруповані за ціллю."""
    known: dict[str, PageSignals] = {}
    for page in ctx.pages:
        known.setdefault(normalize(page.url), page)
        for variant in page.url_variants:
            known.setdefault(normalize(variant), page)
        if page.redirected_from:
            known.setdefault(normalize(page.redirected_from), page)

    grouped: dict[str, list[Observation]] = {}
    for page in ctx.ok_pages:
        for observation in _observations(ctx, page):
            grouped.setdefault(observation.target_key, []).append(observation)

    out: dict[str, Destination] = {}
    for key, observations in grouped.items():
        base = _state_of(ctx, key, known)
        out[key] = Destination(
            key=key,
            url=base.url,
            state=base.state,
            status=base.status,
            observations=tuple(observations),
            detail=base.detail,
        )
    return out


def broken(ctx: Any) -> list[Destination]:
    """Цілі, про поламаність яких сказав сам сервер. Порядок сталий."""
    found = [d for d in collect(ctx).values() if d.broken]
    return sorted(found, key=lambda d: (-d.links, d.key))


__all__ = [
    "CONFIRMED_BROKEN",
    "Destination",
    "Observation",
    "Seen",
    "TargetState",
    "broken",
    "collect",
]
