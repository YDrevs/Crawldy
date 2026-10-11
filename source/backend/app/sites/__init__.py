"""Контекст сайтів: що саме аудитуємо і кому воно належить."""

from app.sites.identity import InvalidSiteUrl, normalize_origin

__all__ = ["InvalidSiteUrl", "normalize_origin"]
