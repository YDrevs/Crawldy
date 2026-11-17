"""DNS rebinding: перевірка адреси й зʼєднання — одна операція.

`assert_public_host` резолвить імʼя, а httpx потім резолвить його вдруге
сам. Сервер DNS із TTL 0 відповідає публічною адресою першому запиту й
`127.0.0.1` — другому. Тепер зʼєднання відкриває `_GuardedBackend`: він
резолвить один раз, перевіряє кожну адресу й конектиться саме до
перевіреної, тож другого резолву, який можна підмінити, немає.
"""

from __future__ import annotations

from typing import Any

import httpx
import pytest

from app.audit import fetcher as fetcher_mod
from app.audit.fetcher import Fetcher, UnsafeUrlError, _GuardedBackend


class _RecordingBackend:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []

    async def connect_tcp(self, host: str, port: int, **_: Any) -> object:
        self.calls.append((host, port))
        return object()


def _resolver(*ips: str) -> Any:
    async def resolve(host: str, port: int) -> list[str]:
        return list(ips)

    return resolve


async def test_rebinding_to_loopback_is_refused_without_connecting() -> None:
    inner = _RecordingBackend()
    backend = _GuardedBackend(inner=inner, resolve=_resolver("127.0.0.1"))  # type: ignore[arg-type]

    with pytest.raises(UnsafeUrlError):
        await backend.connect_tcp("rebind.example.com", 443)

    assert inner.calls == []


async def test_any_private_address_in_the_answer_refuses_the_host() -> None:
    inner = _RecordingBackend()
    backend = _GuardedBackend(
        inner=inner,  # type: ignore[arg-type]
        resolve=_resolver("93.184.215.14", "169.254.169.254"),
    )

    with pytest.raises(UnsafeUrlError):
        await backend.connect_tcp("mixed.example.com", 443)

    assert inner.calls == []


async def test_connects_to_the_checked_ip_not_the_name() -> None:
    inner = _RecordingBackend()
    backend = _GuardedBackend(inner=inner, resolve=_resolver("93.184.215.14"))  # type: ignore[arg-type]

    await backend.connect_tcp("example.com", 443)

    assert inner.calls == [("93.184.215.14", 443)]


async def test_private_hosts_allowed_by_config_skip_the_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fetcher_mod.settings, "allow_private_hosts", True)
    inner = _RecordingBackend()
    backend = _GuardedBackend(inner=inner, resolve=_resolver("127.0.0.1"))  # type: ignore[arg-type]

    await backend.connect_tcp("localhost", 8000)

    assert inner.calls == [("127.0.0.1", 8000)]


async def test_default_fetcher_routes_connections_through_the_guard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Обхід попередньої перевірки не має значення: транспорт сам не пустить.

    Якщо оновлення httpx перейменує внутрішнє поле пулу, підміна мовчки
    перестане діяти — цей тест це й ловить.
    """

    async def no_precheck(url: str) -> None:
        return None

    monkeypatch.setattr(fetcher_mod, "assert_public_host", no_precheck)

    async with Fetcher() as f:
        result = await f.get("http://127.0.0.1:9/")

    assert not result.ok
    assert result.error is not None
    assert "UnsafeUrl" in result.error or "приватн" in result.error


async def test_guarded_transport_raises_unsafe_url_directly() -> None:
    async with httpx.AsyncClient(transport=fetcher_mod.guarded_transport()) as client:
        with pytest.raises(UnsafeUrlError):
            await client.get("http://127.0.0.1:9/")
