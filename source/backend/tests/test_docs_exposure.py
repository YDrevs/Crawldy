"""Схема API й інтерактивна документація — не для проду.

`/docs` і `/openapi.json` перелічують кожен маршрут, включно зі
службовими, разом із тілами запитів: готова карта для перебору.
Локально й на staging вони лишаються — там ними користуються.
"""

from __future__ import annotations

import pytest

from app.main import docs_settings


def test_production_publishes_no_schema_or_docs() -> None:
    assert docs_settings("prod") == {"docs_url": None, "redoc_url": None, "openapi_url": None}


@pytest.mark.parametrize("env", ["local", "staging"])
def test_other_environments_keep_the_docs(env: str) -> None:
    assert docs_settings(env) == {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }
