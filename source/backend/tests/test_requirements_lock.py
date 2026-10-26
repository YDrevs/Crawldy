"""Lockfile покриває кожну залежність із pyproject.

Образ ставить пакети ЛИШЕ з `requirements.lock` (з `--require-hashes`).
Залежність, додана в pyproject без перегенерації lockfile, в образ би не
потрапила — і падіння було б аж на імпорті в контейнері.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def _name(requirement: str) -> str:
    return re.split(r"[\[<>=!~ ;]", requirement, maxsplit=1)[0].lower().replace("_", "-")


def test_every_dependency_is_locked_with_hashes() -> None:
    declared = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    lock = (BACKEND / "requirements.lock").read_text(encoding="utf-8")
    locked = {
        m.group(1).lower().replace("_", "-")
        for m in re.finditer(r"^([A-Za-z0-9_.-]+)==", lock, flags=re.MULTILINE)
    }
    missing = sorted(
        _name(r) for r in declared["project"]["dependencies"] if _name(r) not in locked
    )
    assert not missing, f"перегенеруйте requirements.lock: {missing}"
    assert "--hash=sha256:" in lock
