"""Прохід рендерингу: бюджет, деградації, відсутність браузера.

Playwright тут не запускається жодного разу. Оркестратор знає лише
протокол Renderer, і це головна властивість, яку перевіряє цей файл:
без неї кожен тест тягнув би за собою браузер.
"""

from __future__ import annotations

from unittest import mock

import pytest

from app.audit.enums import DegradationKind, Module
from app.audit.orchestrator import AuditOptions, _render_pages
from app.audit.render import NullRenderer, get_renderer
from app.audit.types import Degradation, PageSignals, RenderResult, SiteContext


class FakeRenderer:
    """Рахує звернення: бюджет перевіряється кількістю, а не наміром."""

    name = "fake"

    def __init__(self, error: str | None = None) -> None:
        self.error = error
        self.rendered_urls: list[str] = []
        self.closed = False

    async def render(self, url: str) -> RenderResult:
        self.rendered_urls.append(url)
        if self.error:
            return RenderResult(url=url, rendered=False, error=self.error)
        return RenderResult(url=url, rendered=True, html=f"<html>{url}</html>", elapsed_ms=42)

    async def aclose(self) -> None:
        self.closed = True


def ctx_with(count: int) -> SiteContext:
    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.pages = [
        PageSignals(url=f"https://example.com/p{n}", status_code=200) for n in range(count)
    ]
    return site


@pytest.fixture
def fake(monkeypatch):
    renderer = FakeRenderer()
    monkeypatch.setattr("app.audit.orchestrator.get_renderer", lambda _: renderer)
    return renderer


@pytest.mark.asyncio
async def test_render_respects_the_page_budget(fake):
    """Браузер на два порядки дорожчий за запит — бюджет не декоративний."""
    ctx = ctx_with(10)
    degraded: list[Degradation] = []

    await _render_pages(ctx, AuditOptions(render_max_pages=3), degraded)

    assert len(fake.rendered_urls) == 3
    assert len(ctx.renders) == 3
    assert degraded == []


@pytest.mark.asyncio
async def test_renders_are_keyed_by_the_same_url_as_pages(fake):
    """Чек має вміти взяти обидві версії однієї сторінки й порівняти."""
    ctx = ctx_with(2)
    await _render_pages(ctx, AuditOptions(render_max_pages=2), [])

    assert set(ctx.renders) == {page.url for page in ctx.ok_pages}


@pytest.mark.asyncio
async def test_browser_is_closed_even_when_rendering_fails(monkeypatch):
    renderer = FakeRenderer(error="browser crashed")
    monkeypatch.setattr("app.audit.orchestrator.get_renderer", lambda _: renderer)

    await _render_pages(ctx_with(3), AuditOptions(), [])

    assert renderer.closed, "процес браузера лишився б висіти до кінця воркера"


@pytest.mark.asyncio
async def test_missing_browser_degrades_once_not_per_page(monkeypatch):
    """Якщо браузера немає, він не з'явиться на другій сторінці."""
    renderer = FakeRenderer(error="playwright не встановлено")
    monkeypatch.setattr("app.audit.orchestrator.get_renderer", lambda _: renderer)
    degraded: list[Degradation] = []

    await _render_pages(ctx_with(5), AuditOptions(render_max_pages=5), degraded)

    assert len(renderer.rendered_urls) == 1, "решту сторінок не пробуємо"
    assert len(degraded) == 1
    assert degraded[0].kind is DegradationKind.PROVIDER_UNAVAILABLE
    assert "playwright не встановлено" in degraded[0].reason


@pytest.mark.asyncio
async def test_render_failure_marks_the_audit_partial_like_a_missing_psi_key(monkeypatch):
    """Недоступний браузер — те саме, що недоступний провайдер метрик:
    аудит проходить, але звіт зобовʼязаний сказати, чого в ньому немає."""
    renderer = FakeRenderer(error="timeout")
    monkeypatch.setattr("app.audit.orchestrator.get_renderer", lambda _: renderer)
    degraded: list[Degradation] = []

    await _render_pages(ctx_with(2), AuditOptions(), degraded)

    assert degraded[0].is_failure, "мовчазна відсутність JS-сигналів — це прихована дірка"
    assert degraded[0].affected_modules == [Module.LLM_VISIBILITY]


@pytest.mark.asyncio
async def test_site_without_content_pages_is_not_rendered(fake):
    """Сайт віддав 403: рендерити нічого, браузер піднімати не треба."""
    ctx = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    ctx.pages = [PageSignals(url="https://example.com/", status_code=403)]

    await _render_pages(ctx, AuditOptions(), [])

    assert fake.rendered_urls == []


@pytest.mark.asyncio
async def test_null_renderer_states_the_reason_instead_of_raising():
    result = await NullRenderer("playwright не встановлено").render("https://example.com/")

    assert result.rendered is False
    assert result.error == "playwright не встановлено"
    assert result.html == "", "порожній HTML не можна сплутати з відрендереним"


def test_disabled_rendering_returns_null_renderer():
    renderer = get_renderer(enabled=False)

    assert renderer.name == "null"


@pytest.mark.asyncio
async def test_a_hanging_render_gives_up_instead_of_blocking_the_audit():
    """Таймаути на goto й на очікування мережі не покривають решти: запуск
    браузера, page.content() і закриття контексту не обмежені нічим. На
    docs.stripe.com калібрувальний прогін через це зависав назавжди — не
    падав, а саме стояв."""
    import asyncio

    from app.audit.render.playwright import PlaywrightRenderer

    renderer = PlaywrightRenderer()

    async def never_returns(url: str, started: float):
        await asyncio.sleep(3600)

    renderer._render = never_returns  # type: ignore[method-assign]
    with mock.patch("app.audit.render.playwright.settings.render_timeout_s", 0.05):
        result = await renderer.render("https://slow.example/")

    assert not result.rendered
    assert "не вклався" in (result.error or "")


@pytest.mark.asyncio
async def test_the_browser_is_dropped_after_a_hang():
    """Зависла сторінка лишає браузер у невизначеному стані: наступна на
    ньому теж має шанс зависнути, і бюджет рендеру згорає весь."""
    import asyncio

    from app.audit.render.playwright import PlaywrightRenderer

    closed: list[bool] = []

    class FakeBrowser:
        async def close(self) -> None:
            closed.append(True)

    renderer = PlaywrightRenderer()
    renderer._browser = FakeBrowser()

    async def never_returns(url: str, started: float):
        await asyncio.sleep(3600)

    renderer._render = never_returns  # type: ignore[method-assign]
    with mock.patch("app.audit.render.playwright.settings.render_timeout_s", 0.05):
        await renderer.render("https://slow.example/")

    assert closed == [True]
    assert renderer._browser is None
