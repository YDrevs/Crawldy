"""Редиректи у `Fetcher.get`: SSRF-перевірка ДО кожного наступного запиту.

Раніше httpx проходив увесь ланцюг сам, а `response.history` перевірявся
вже після того, як фінальна відповідь прочитана, — і `history` не містить
самого `response.url`. `302 → http://169.254.169.254/` читався й
зберігався. Тепер кожен крок проходить перевірку до того, як ми туди
підемо, і запит на заборонену адресу не відбувається взагалі.
"""

from __future__ import annotations

import httpx
import pytest

from app.audit import fetcher as fetcher_mod
from app.audit.fetcher import Fetcher, UnsafeUrlError


@pytest.fixture(autouse=True)
def _fake_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Публічні імена проходять без DNS, IP-літерали судить справжня перевірка."""

    real = fetcher_mod.assert_public_host

    async def guard(url: str) -> None:
        host = httpx.URL(url).host
        if host.replace(".", "").isdigit() or ":" in host:
            await real(url)
        elif host.endswith(".internal"):
            raise UnsafeUrlError("приватний хост")

    monkeypatch.setattr(fetcher_mod, "assert_public_host", guard)


def _fetcher(handler: object, seen: list[str]) -> Fetcher:
    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return handler(request)  # type: ignore[operator, no-any-return]

    return Fetcher(transport=httpx.MockTransport(wrapped))


async def test_redirect_to_metadata_ip_is_never_requested() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})

    async with _fetcher(handler, seen) as f:
        result = await f.get("https://example.com/")

    assert seen == ["https://example.com/"]
    assert result.error is not None
    assert result.text == ""
    assert result.status_code is None


async def test_redirect_to_private_hostname_is_a_failed_result_not_an_exception() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "example.com":
            return httpx.Response(301, headers={"location": "https://db.internal/"})
        return httpx.Response(200, text="secret")

    async with _fetcher(handler, seen) as f:
        result = await f.get("https://example.com/")

    assert "db.internal" not in "".join(seen)
    assert not result.ok


async def test_redirect_to_non_http_scheme_is_refused() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "file:///etc/passwd"})

    async with _fetcher(handler, seen) as f:
        result = await f.get("https://example.com/")

    assert seen == ["https://example.com/"]
    assert not result.ok


async def test_public_chain_keeps_hops_and_final_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/":
            return httpx.Response(301, headers={"location": "/a"})
        if path == "/a":
            return httpx.Response(302, headers={"location": "https://www.example.com/b"})
        return httpx.Response(200, text="<html>ok</html>", headers={"content-type": "text/html"})

    async with _fetcher(handler, seen) as f:
        result = await f.get("https://example.com/")

    assert result.ok
    assert result.final_url == "https://www.example.com/b"
    assert result.text == "<html>ok</html>"
    # Семантика кроку не змінилась: код і значення Location як є.
    assert [(h.status_code, h.url) for h in result.redirects] == [
        (301, "/a"),
        (302, "https://www.example.com/b"),
    ]
    assert seen == [
        "https://example.com/",
        "https://example.com/a",
        "https://www.example.com/b",
    ]


async def test_endless_chain_stops_at_limit() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        n = int(request.url.params.get("n", "0"))
        return httpx.Response(302, headers={"location": f"/?n={n + 1}"})

    async with _fetcher(handler, seen) as f:
        result = await f.get("https://example.com/")

    assert result.redirect_limit_exceeded
    assert not result.ok
    # Як і в httpx із max_redirects=5: початковий запит і пʼять переходів.
    assert len(seen) == 6
