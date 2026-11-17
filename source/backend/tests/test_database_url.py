"""Адреса бази від хостингу приводиться до асинхронного драйвера."""

import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@db:5432/x", "postgresql+asyncpg://u:p@db:5432/x"),
        ("postgresql://u:p@db:5432/x", "postgresql+asyncpg://u:p@db:5432/x"),
        ("postgresql+asyncpg://u:p@db:5432/x", "postgresql+asyncpg://u:p@db:5432/x"),
    ],
)
def test_database_url_gets_async_driver(given: str, expected: str) -> None:
    assert Settings(database_url=given).database_url == expected
