"""Хід аудиту: що саме показує екран очікування, поки він триває.

Правило проєкту тут те саме, що й скрізь: числа справжні або їх немає.
Смужка, яка повзе до 90% і чекає, — вигадане число з анімацією, і на неї
ці тести не пускають.
"""

from __future__ import annotations

import pytest

from app.audit.crawler import crawl
from app.audit.fetcher import FetchResult
from app.audit.orchestrator import (
    STAGE_ANALYSIS,
    STAGE_CRAWL,
    STAGE_DISCOVERY,
    STAGE_MEASURING,
    STAGE_RENDER,
    STAGE_SCORING,
)

ORIGIN = "https://example.com"


class FakeFetcher:
    def __init__(self, links: dict[str, list[str]]) -> None:
        self._links = links

    async def get(self, url: str) -> FetchResult:
        anchors = "".join(f'<a href="{href}">посилання</a>' for href in self._links.get(url, []))
        html = f"<html><head><title>С</title></head><body><h1>Ц</h1>{anchors}</body></html>"
        return FetchResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            text=html,
            body_bytes=len(html.encode()),
            elapsed_ms=10,
            headers={},
        )


def _site(*paths: str) -> FakeFetcher:
    return FakeFetcher({f"{ORIGIN}/": [f"{ORIGIN}{path}" for path in paths]})


@pytest.mark.asyncio
async def test_the_crawler_reports_pages_it_has_actually_read():
    seen: list[tuple[int, int]] = []

    async def record(read: int, known: int) -> None:
        seen.append((read, known))

    pages, _ = await crawl(
        _site("/a", "/b", "/c"),
        f"{ORIGIN}/",
        ORIGIN,
        max_pages=4,
        max_depth=1,
        on_progress=record,
    )

    assert seen, "хід не повідомлявся жодного разу"
    # Останнє повідомлення описує саме те, що краул повернув.
    assert seen[-1][0] == len(pages)


@pytest.mark.asyncio
async def test_the_counter_never_walks_backwards():
    """Лічильник на очах у клієнта не має зменшуватись.

    Черга росте, поки краул читає, тож знаменник рухається — але
    прочитане лише додається.
    """
    seen: list[tuple[int, int]] = []

    async def record(read: int, known: int) -> None:
        seen.append((read, known))

    await crawl(
        _site("/a", "/b", "/c", "/d", "/e"),
        f"{ORIGIN}/",
        ORIGIN,
        max_pages=6,
        max_depth=1,
        on_progress=record,
    )

    reads = [read for read, _ in seen]
    assert reads == sorted(reads)


@pytest.mark.asyncio
async def test_the_denominator_never_promises_more_than_the_budget():
    """Обіцяти знаменник, до якого краул не дійде, — та сама вигадка.

    Сайт може мати сотні адрес у черзі, але бюджет читання скінченний:
    смужка, яка за побудовою ніколи не дійде до кінця, гірша за її
    відсутність.
    """
    seen: list[tuple[int, int]] = []

    async def record(read: int, known: int) -> None:
        seen.append((read, known))

    await crawl(
        _site(*[f"/p{i}" for i in range(30)]),
        f"{ORIGIN}/",
        ORIGIN,
        max_pages=3,
        max_depth=1,
        on_progress=record,
    )

    assert seen
    for read, known in seen:
        assert known <= 3
        assert known >= read


@pytest.mark.asyncio
async def test_a_crawl_without_a_listener_behaves_the_same():
    """Показник ходу — додаток, а не умова роботи."""
    pages, failed = await crawl(
        _site("/a", "/b"), f"{ORIGIN}/", ORIGIN, max_pages=3, max_depth=1
    )
    assert len(pages) == 3
    assert not failed


def test_the_stages_are_distinct_and_named():
    """Кожна стадія — окремий рядок: два стани під одним іменем ми вже
    проходили на `scope` деградації."""
    stages = {
        STAGE_DISCOVERY,
        STAGE_CRAWL,
        STAGE_MEASURING,
        STAGE_RENDER,
        STAGE_ANALYSIS,
        STAGE_SCORING,
    }
    assert len(stages) == 6
    assert all(stage.isidentifier() for stage in stages)
