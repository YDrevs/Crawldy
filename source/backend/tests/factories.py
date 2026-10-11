"""Хелпери для побудови тестових контекстів без мережі."""

from __future__ import annotations

from app.audit.extractor import extract
from app.audit.fetcher import FetchResult
from app.audit.types import PageSignals, SiteContext


def page_from_html(html: str, url: str = "https://example.com/", depth: int = 0) -> PageSignals:
    result = FetchResult(
        url=url,
        final_url=url,
        status_code=200,
        content_type="text/html",
        text=html,
        body_bytes=len(html.encode()),
        elapsed_ms=120,
        headers={},
    )
    return extract(result, origin="https://example.com", depth=depth)


def context(*pages: PageSignals, **overrides) -> SiteContext:
    ctx = SiteContext(
        entry_url=pages[0].url if pages else "https://example.com/",
        origin="https://example.com",
        is_https=True,
        hsts=True,
    )
    ctx.pages = list(pages)
    for key, value in overrides.items():
        setattr(ctx, key, value)
    return ctx
