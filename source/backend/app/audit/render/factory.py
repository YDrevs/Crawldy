from __future__ import annotations

import importlib.util

from app.audit.render.base import NullRenderer, Renderer
from app.core.config import settings


def get_renderer(enabled: bool | None = None) -> Renderer:
    """Playwright, якщо він є і його не вимкнули; інакше — чесний NullRenderer.

    Перевіряємо саме наявність модуля, а не ловимо ImportError пізніше:
    причина «пакет не встановлено» має потрапити у звіт як текст, а не
    як стектрейс у логах воркера.
    """
    if not (settings.render_enabled if enabled is None else enabled):
        return NullRenderer("рендеринг вимкнено в налаштуваннях", disabled=True)
    if importlib.util.find_spec("playwright") is None:
        return NullRenderer("playwright не встановлено")

    from app.audit.render.playwright import PlaywrightRenderer

    return PlaywrightRenderer()
