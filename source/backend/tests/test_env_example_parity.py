"""Every setting the app reads must be documented in `.env.example`.

A setting that exists only in Python is invisible at deployment time.
`IP_HASH_SALT` was exactly that: an empty default makes the "anonymous"
guest IP hash reproducible, and nothing told a deployer it existed.

The file carries placeholders only — never real values.
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings

EXAMPLE = Path(__file__).resolve().parents[1] / ".env.example"


def _declared() -> set[str]:
    names: set[str] = set()
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            names.add(stripped.split("=", 1)[0].strip().lower())
    return names


def test_every_setting_is_documented():
    missing = sorted(set(Settings.model_fields) - _declared())
    assert not missing, f"settings absent from .env.example: {missing}"


def test_the_example_declares_nothing_the_app_ignores():
    """A variable nobody reads is worse than none: it looks configured."""
    stale = sorted(_declared() - set(Settings.model_fields))
    assert not stale, f".env.example declares unread variables: {stale}"


def test_the_example_carries_no_real_secrets():
    """Placeholders only. A key here would be a key in git."""
    text = EXAMPLE.read_text(encoding="utf-8")
    for marker in ("sk-ant-", "sk-proj-", "sk-live", "AIza"):
        assert marker not in text, f".env.example contains a real key ({marker}…)"
