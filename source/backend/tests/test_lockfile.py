"""Образ ставить залежності з requirements.lock — з точними версіями й хешами.

`pyproject.toml` має лише нижні межі (`>=`), і кожна збірка тягла
найсвіжіше: так selectolax 1.0 мовчки зламав імпорт усього аудиту. Lock
фіксує версію й хеш кожного пакета; цей тест не дає йому розійтися з
переліком залежностей.

Оновлення (у Linux-контейнері, як і образ) — команда в CLAUDE.md,
розділ «Команди».
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PIN = re.compile(r"^([A-Za-z0-9_.-]+)==\S+", re.MULTILINE)


def _name(requirement: str) -> str:
    return re.split(r"[\[<>=!~; ]", requirement, maxsplit=1)[0].lower().replace("_", "-")


def test_every_dependency_is_pinned_with_a_hash() -> None:
    declared = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    names = {_name(r) for r in declared["project"]["dependencies"]}
    lock = (BACKEND / "requirements.lock").read_text(encoding="utf-8")
    pinned = {m.group(1).lower().replace("_", "-") for m in PIN.finditer(lock)}
    assert names - pinned == set(), f"немає в requirements.lock: {sorted(names - pinned)}"
    assert lock.count("--hash=sha256:") >= len(pinned)


def test_the_image_installs_from_the_lock() -> None:
    dockerfile = (BACKEND / "Dockerfile").read_text(encoding="utf-8")
    assert "--require-hashes -r requirements.lock" in dockerfile
