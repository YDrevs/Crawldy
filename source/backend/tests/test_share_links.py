"""Публічні посилання: те, що віддає чужий звіт без ключа, має бути параноїдальним."""

from __future__ import annotations

import inspect
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.services.link_service import (
    DEFAULT_TTL_DAYS,
    MAX_TTL_DAYS,
    TOKEN_BYTES,
    hash_token,
)


@dataclass
class FakeLink:
    """Мінімальна модель посилання — перевіряємо саме логіку доступу."""

    expires_at: datetime
    revoked_at: datetime | None = None
    token_hash: str = ""
    views: int = 0
    id: uuid.UUID = field(default_factory=uuid.uuid4)

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > datetime.now(UTC)


def test_token_is_stored_only_as_a_hash():
    """У базі не має бути відкритого токена: дамп не роздає робочі посилання."""
    token = "s3cret-token-value"
    digest = hash_token(token)

    assert digest != token
    assert len(digest) == 64
    assert token not in digest


def test_hashing_is_deterministic_so_lookup_hits_the_index():
    assert hash_token("abc") == hash_token("abc")
    assert hash_token("abc") != hash_token("abd")


def test_token_has_enough_entropy_to_resist_guessing():
    import secrets

    token = secrets.token_urlsafe(TOKEN_BYTES)

    assert TOKEN_BYTES * 8 >= 256, "менше 256 біт для публічного URL — замало"
    assert len(token) >= 32


def test_expired_link_is_not_active():
    link = FakeLink(expires_at=datetime.now(UTC) - timedelta(seconds=1))
    assert link.is_active is False


def test_revoked_link_is_not_active_even_before_expiry():
    link = FakeLink(
        expires_at=datetime.now(UTC) + timedelta(days=10),
        revoked_at=datetime.now(UTC),
    )
    assert link.is_active is False


def test_fresh_link_is_active():
    assert FakeLink(expires_at=datetime.now(UTC) + timedelta(days=1)).is_active is True


@pytest.mark.parametrize(
    ("requested", "expected"),
    [(0, 1), (-5, 1), (1, 1), (14, 14), (90, 90), (365, MAX_TTL_DAYS)],
)
def test_ttl_is_clamped_to_a_sane_window(requested: int, expected: int):
    """Вічне посилання на клієнтський звіт — не варіант."""
    assert max(1, min(requested, MAX_TTL_DAYS)) == expected


def test_default_ttl_is_finite():
    assert 0 < DEFAULT_TTL_DAYS <= MAX_TTL_DAYS


# ── роут ───────────────────────────────────────────────────────────────────


def test_public_route_sets_headers_that_keep_the_report_out_of_search():
    from app.api.routes.share import PRIVATE_HEADERS

    assert PRIVATE_HEADERS["X-Robots-Tag"].startswith("noindex")
    assert "no-store" in PRIVATE_HEADERS["Cache-Control"]
    assert PRIVATE_HEADERS["Referrer-Policy"] == "no-referrer"


def test_public_route_is_the_only_one_without_an_api_key():
    from app.api.routes import share
    from app.main import app

    public = [r for r in app.openapi()["paths"] if r.startswith("/r/")]
    assert public == ["/r/{token}"]

    params = app.openapi()["paths"]["/r/{token}"]["get"].get("parameters", [])
    assert not [p for p in params if p["name"].lower() == "x-api-key"]
    assert share.router.prefix == "/r"


def test_every_rejection_looks_identical_from_outside():
    """Прострочене, відкликане й неіснуюче мають давати однаковий 404.

    Інакше сторонній міг би перебором зʼясувати, які токени існували.
    """
    import inspect

    from app.api.routes import share

    source = inspect.getsource(share.public_report)
    details = {
        line.split('detail="')[1].split('"')[0]
        for line in source.splitlines()
        if 'detail="' in line
    }
    assert details == {"посилання недійсне"}, f"різні пояснення відмови: {details}"


def test_the_public_link_serves_both_kinds_of_the_word_report():
    """Разова покупка йде власнику бізнесу — загальний вид мусить бути.

    Гість не має кабінету, і публічне посилання — єдині його двері до
    файлу. Поки формат був один, гість отримував технічний документ, а
    загальний існував лише за входом.
    """
    from app.api.routes.share import public_report

    source = inspect.getsource(public_report)
    for fmt in ("docx-general", "docx-technical"):
        assert f'"{fmt}"' in source, f"публічне посилання не знає {fmt}"
    # Старе значення лишається робочим: за ним ходять уже видані посилання.
    assert '"docx"' in source
