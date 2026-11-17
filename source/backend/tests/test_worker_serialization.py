"""Черга не знає pickle: що лежить у Redis, не виконується при читанні.

arq за замовчуванням серіалізує завдання й результати pickle. Хто може
писати в Redis — а він стояв без пароля й з опублікованим портом, —
той кладе в чергу обʼєкт, чий `__reduce__` виконується на воркері.
JSON такого механізму не має.
"""

from __future__ import annotations

import pickle
import uuid

import pytest

from app.worker import queue
from app.worker.main import WorkerSettings
from app.worker.serialization import deserialize, serialize


def test_job_payload_round_trips() -> None:
    job = {"t": 1, "f": "run_audit_task", "a": ("abc", 2), "k": {}, "et": 1700000000000}
    restored = deserialize(serialize(job))
    assert restored["f"] == "run_audit_task"
    assert list(restored["a"]) == ["abc", 2]


def test_non_json_results_degrade_to_text_instead_of_failing() -> None:
    audit = uuid.uuid4()
    data = deserialize(serialize({"r": {"audit": audit, "error": ValueError("boom")}}))
    assert data["r"]["audit"] == str(audit)
    assert "boom" in data["r"]["error"]


def test_a_pickle_payload_is_rejected() -> None:
    class Evil:
        def __reduce__(self) -> tuple[object, tuple[str]]:
            return (print, ("pwned",))

    with pytest.raises(ValueError):
        deserialize(pickle.dumps({"f": Evil()}))


async def test_worker_and_producer_use_the_json_serializer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert WorkerSettings.job_serializer is serialize
    assert WorkerSettings.job_deserializer is deserialize

    captured: dict[str, object] = {}

    async def fake_create_pool(_settings: object, **kwargs: object) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(queue, "create_pool", fake_create_pool)
    monkeypatch.setattr(queue, "_pool", None)
    await queue.get_pool()
    monkeypatch.setattr(queue, "_pool", None)

    assert captured == {"job_serializer": serialize, "job_deserializer": deserialize}
