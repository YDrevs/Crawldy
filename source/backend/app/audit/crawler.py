"""Краул у межах origin із лімітами глибини й кількості сторінок.

Обхід — у ширину, але черга не проста: сторінки з однаковою глибиною
беруться за тим, наскільки ймовірно вони щось стверджують про компанію.
Чистий BFS брав що трапиться, і на ka-dent.com.ua бюджет у 14 сторінок
з'їдали одинадцять статей блогу, а сторінка послуг лишалася непрочитаною.
Це не дрібниця порядку: чек, який питає «чи є десь ціни», через таку
вибірку мовчить на сайті, де цін справді немає.

Сама черга й правила допуску живуть у `frontier.py`. Це не косметичний
поділ: краул став викликатися хвилями — після рендеру зʼявляються
адреси, яких у відповіді сервера не було, — і черга мусить пережити межу
виклику. Поки вона була локальною змінною, друга хвиля означала б другий
набір правил.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from app.audit.extractor import extract
from app.audit.fetcher import Fetcher, FetchResult
from app.audit.frontier import Frontier, Source
from app.audit.types import PageSignals
from app.core.config import settings
from app.core.logging import log

# Хід краулу назовні: (прочитано, відомо). Проста функція, і саме тому
# інваріант «app/audit не знає про базу» лишається цілим — писати кудись
# число буде той, хто цю функцію передав.
ProgressHook = Callable[[int, int], Awaitable[None]]


async def crawl(
    fetcher: Fetcher,
    entry_url: str,
    origin: str,
    *,
    max_pages: int | None = None,
    max_depth: int | None = None,
    seed_urls: list[str] | None = None,
    prefetched: FetchResult | None = None,
    frontier: Frontier | None = None,
    on_progress: ProgressHook | None = None,
) -> tuple[list[PageSignals], dict[str, str]]:
    """Повертає (сторінки, {url: причина_невдачі}).

    `prefetched` — уже завантажена точка входу: оркестратор тягне її першою,
    щоб визначити origin, і передає сюди, аби не робити другий запит.

    `frontier` — спільна черга. Її передають, щоб продовжити той самий
    краул новою хвилею: усе, що вже прочитано, лишається прочитаним, а
    ліміт сторінок цієї хвилі приходить у `max_pages`.
    """
    max_pages = max_pages or settings.crawl_max_pages
    max_depth = max_depth if max_depth is not None else settings.crawl_max_depth

    if frontier is None:
        frontier = Frontier(origin=origin, max_depth=max_depth)

    # Умова — «чи вже читали точку входу», а не «чи передали чергу».
    # Спершу тут стояло друге, і воно ламало кожен реальний аудит: черга
    # передається завжди, тож завантажена наперед головна сторінка
    # мовчки не потрапляла в результат. Тести на фікстурах цього не
    # бачили, бо передавали `prefetched=None`; побачив живий прогін.
    fresh_entry = not frontier.was_fetched(entry_url)

    if fresh_entry and prefetched is None:
        frontier.offer(entry_url, 0, source=Source.ENTRY)

    pages: list[PageSignals] = []
    failed: dict[str, str] = {}

    # Спершу те, на що посилається головна: сайт сам показує, що вважає
    # головним. Карта сайту йде після — вона повний перелік, а не вибір
    # власника, і при рівному пріоритеті має поступатися.
    if fresh_entry and prefetched is not None and prefetched.is_html:
        entry_page = extract(prefetched, origin, depth=0)
        # Позначаємо прочитаною ДО запису походження: інакше `offer`
        # поставить у чергу сторінку, яка вже в руках, і ми завантажимо
        # головну вдруге.
        frontier.mark_fetched(entry_url)
        frontier.offer(entry_url, 0, source=Source.ENTRY)
        entry_page.discovered_via = list(frontier.sources_of(entry_url))
        pages.append(entry_page)
        _offer_links(frontier, entry_page, depth=1)

    for seed in (seed_urls or [])[: max_pages * 2]:
        if seed != entry_url:
            frontier.offer(seed, 1, source=Source.SITEMAP, seeded=True)

    while frontier.pending and len(pages) < max_pages:
        room = min(settings.crawl_concurrency, max_pages - len(pages))
        batch = frontier.take(room)
        if not batch:
            break

        results = await asyncio.gather(*(fetcher.get(url) for url, _ in batch))

        for (url, depth), result in zip(batch, results, strict=True):
            frontier.mark_fetched(url)
            if result.error:
                failed[url] = result.error
                if result.redirect_limit_exceeded:
                    frontier.redirect_limited.add(url)
                continue
            if not result.is_html:
                continue
            page = extract(result, origin, depth=depth)
            page.discovered_via = list(frontier.sources_of(url))
            pages.append(page)
            if result.status_code and result.status_code >= 400:
                failed[url] = f"HTTP {result.status_code}"
                continue
            _offer_links(frontier, page, depth=depth + 1)

        if on_progress is not None:
            # Після хвилі, а не після кожного документа: запис коштує
            # окремого звернення до сховища, а людина однаково не бачить
            # різниці між оновленням раз на сторінку й раз на десять.
            #
            # «Відомо» — це те, що вже прочитано плюс те, що чекає в
            # черзі, але не більше за бюджет: обіцяти знаменник, до
            # якого краул не дійде за побудовою, означало б показати
            # смужку, яка ніколи не дійде до кінця.
            known = min(len(pages) + frontier.queued, max_pages)
            await on_progress(len(pages), max(known, len(pages)))

    log.info("crawl_done", entry=entry_url, pages=len(pages), failed=len(failed))
    return pages, failed


def _offer_links(frontier: Frontier, page: PageSignals, *, depth: int) -> None:
    """Внутрішні посилання сторінки — у спільну чергу.

    `nofollow` лишається тут, а не в дверях: це властивість посилання,
    а не адреси. Та сама сторінка, названа деінде без `nofollow`, має
    потрапити в чергу.
    """
    for link in page.links:
        if link.is_internal and "nofollow" not in link.rel:
            frontier.offer(link.url, depth, source=Source.RESPONSE, anchor=link.anchor)


__all__ = ["ProgressHook", "crawl"]
