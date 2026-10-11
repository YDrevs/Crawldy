"""Черга краулу й правила допуску в неї — одні на всі джерела адрес.

## Навіщо окремий модуль

Адреси приходять із чотирьох місць: точка входу, посилання у відповіді
сервера, карта сайту й DOM після рендеру. Спокуса — дати останньому
власний обхід, бо він зʼявляється пізніше за решту. Це була б друга
реалізація тих самих правил, і розійшлася б вона на першій же дрібниці:
одне джерело фільтрувало б розширення, друге ні; одне зважало б на
`nofollow`, друге забуло.

Тому черга одна, і `offer()` — єдина двері. Хто б не приніс адресу, вона
проходить ті самі перевірки й той самий дедуплікат.

## Що робить пріоритет

Обхід у ширину, але всередині глибини сторінки впорядковані за тим,
наскільки ймовірно вони щось стверджують про компанію. Пояснення й
історія — у `crawler.py`, звідки ця логіка сюди й переїхала без змін.

## Чому robots саме тут

До цієї зміни robots.txt не застосовувався ніде: ані до статичних
посилань, ані до жодних. Правило, додане лише для відрендерених адрес,
було б рівно тією другою реалізацією, якої модуль і уникає, тож воно
стоїть у спільних дверях і діє на всіх однаково. Ціна виміряна на
вибірці з 56 знімків: 2 сторінки з 950 на 47 сайтах із непорожнім
robots.txt.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from app.audit.logical_pages import normalize
from app.audit.page_kinds import kind_of, path_depth
from app.audit.site_scope import CRAWLABLE_SCHEMES as _CRAWLABLE_SCHEMES
from app.audit.site_scope import SiteScope

# Розширення, за якими лежить не сторінка. Список був у `crawler.py` і
# переїхав сюди цілим: він частина правил допуску, а не обходу.
SKIP_EXTENSIONS = (
    ".pdf", ".zip", ".rar", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".avif", ".svg", ".ico",
    ".mp4", ".mp3", ".webm", ".css", ".js", ".json", ".xml", ".rss",
)

# Єдині схеми, які краулер уміє завантажити. `mailto:`, `tel:`,
# `javascript:` і `data:` відсіює вже екстрактор, але двері не мають
# спиратися на чужу сумлінність: у DOM після рендеру трапляється все.
# Реекспорт заради сумісності: єдине означення живе в `site_scope`.
CRAWLABLE_SCHEMES = _CRAWLABLE_SCHEMES


class Source(StrEnum):
    """Звідки ми дізналися про адресу. Для доказу, не для оцінки."""

    ENTRY = "entry"
    # Посилання в HTML, який віддав сервер.
    RESPONSE = "response"
    # Посилання, якого у відповіді не було, — воно зʼявилось після JS.
    RENDER = "render"
    SITEMAP = "sitemap"


@dataclass(slots=True)
class Frontier:
    """Що ще не прочитано, що вже прочитано і звідки про це відомо."""

    origin: str
    max_depth: int
    # Розібраний robots.txt (`app.audit.robots.RobotsFile`) або None.
    robots: Any = None
    user_agent: str = "*"

    _queue: list[tuple[int, int, int, int, str]] = field(default_factory=list)
    _seen: set[str] = field(default_factory=set)
    _fetched: set[str] = field(default_factory=set)
    # Нормалізована адреса → джерела, з яких вона нам відома. Множина, бо
    # та сама сторінка буває і в карті, і в меню, і дублювати рядок
    # заради збереження походження було б гірше за злиття.
    _sources: dict[str, set[Source]] = field(default_factory=dict)
    _order: int = 0
    # Межа сайту, виведена з `origin` один раз. Кешується, бо `eligible`
    # викликається на кожне посилання кожної сторінки.
    _scope: SiteScope | None = None
    # Адреси, для яких ланцюг перенаправлень не дійшов до кінця. Живуть
    # тут, бо це знання про сам краул, а не про сторінку: сторінки в
    # такому випадку не існує взагалі.
    redirect_limited: set[str] = field(default_factory=set)

    @property
    def scope(self) -> SiteScope:
        if self._scope is None:
            self._scope = SiteScope.from_url(self.origin)
        return self._scope

    # ── допуск ────────────────────────────────────────────────────────────

    def allowed_by_robots(self, url: str) -> bool:
        if self.robots is None or getattr(self.robots, "empty", True):
            return True
        path = urlparse(url).path or "/"
        decision = self.robots.evaluate(self.user_agent, path)
        return bool(decision.allowed)

    def eligible(self, url: str) -> tuple[bool, str]:
        """Чи можна ставити адресу в чергу, і якщо ні — то чому.

        Причина повертається текстом навмисно: вона йде в доказ, коли
        треба пояснити, чому відрендерене посилання нікуди не привело.
        """
        if not url:
            return False, "empty"
        parsed = urlparse(url)
        if parsed.scheme not in CRAWLABLE_SCHEMES:
            return False, "scheme"
        # Те саме правило, що й в екстракторі. Порівняння рядків
        # (`url.startswith(self.origin)`) відкидало ту саму сторінку на
        # іншій схемі: вхід `http://x`, посилання `https://x/page`.
        if not self.scope.contains(url):
            return False, "external"
        if (parsed.path or "").lower().endswith(SKIP_EXTENSIONS):
            return False, "not_a_page"
        if not self.allowed_by_robots(url):
            return False, "robots"
        return True, ""

    # ── черга ─────────────────────────────────────────────────────────────

    def offer(
        self,
        url: str,
        depth: int,
        *,
        source: Source,
        anchor: str = "",
        seeded: bool = False,
    ) -> bool:
        """Запропонувати адресу. `True` — стала в чергу вперше.

        Походження записується навіть тоді, коли адресу вже знали: одна
        сторінка може бути і в карті, і в меню, і після рендеру, і всі
        три факти правдиві.
        """
        key = normalize(url)
        self._sources.setdefault(key, set())

        if depth > self.max_depth:
            self._sources[key].add(source)
            return False
        ok, _reason = self.eligible(url)
        if not ok:
            return False

        self._sources[key].add(source)
        # Прочитане не повертається в чергу. Перевірка саме на
        # `_fetched`, а не лише на `_seen`: адресу, яку ми вже
        # завантажили наперед, теж треба вміти назвати без наслідків —
        # інакше запис походження мовчки замовляє другий запит.
        if key in self._seen or key in self._fetched:
            self._seen.add(key)
            return False
        self._seen.add(key)

        # Глибина шляху приборкує сотні карток товару, але для адреси з
        # карти вона нічого не означає: цю сторінку ми обрали свідомо.
        segments = 1 if seeded else path_depth(url)
        heapq.heappush(
            self._queue, (int(kind_of(url, anchor)), segments, depth, self._order, url)
        )
        self._order += 1
        return True

    def take(self, limit: int) -> list[tuple[str, int]]:
        """Наступні адреси в порядку пріоритету."""
        batch: list[tuple[str, int]] = []
        while self._queue and len(batch) < limit:
            _kind, _segments, depth, _order, url = heapq.heappop(self._queue)
            batch.append((url, depth))
        return batch

    def mark_fetched(self, url: str) -> None:
        self._fetched.add(normalize(url))

    def was_fetched(self, url: str) -> bool:
        return normalize(url) in self._fetched

    def knows(self, url: str) -> bool:
        return normalize(url) in self._seen

    def sources_of(self, url: str) -> tuple[str, ...]:
        return tuple(sorted(s.value for s in self._sources.get(normalize(url), set())))

    @property
    def pending(self) -> bool:
        return bool(self._queue)

    @property
    def queued(self) -> int:
        """Скільки адрес чекає в черзі просто зараз.

        Не «скільки сторінок на сайті»: черга росте, поки краул читає, і
        це нижня межа відомого, а не оцінка розміру сайту.
        """
        return len(self._queue)


__all__ = ["CRAWLABLE_SCHEMES", "SKIP_EXTENSIONS", "Frontier", "Source"]
