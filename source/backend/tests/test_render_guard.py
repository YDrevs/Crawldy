"""SSRF-перевірка браузера аудиту: без справжнього Chromium.

Обробник маршрутів отримує підробні `route`/`request` — перевіряється
рішення, а не Playwright. Живий прогін із редиректом на 127.0.0.1
показав, що за 3xx, відданим через `route.fulfill`, браузер іде сам,
повз `page.route`; звідси окремий тест на головний фрейм.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass, field
from typing import Any

import pytest

from app.audit.fetcher import UnsafeUrlError, is_forbidden_ip
from app.audit.render import playwright as pw

DNS = {"site.test": "93.184.216.34", "cdn.test": "8.8.8.8", "metadata.test": "169.254.169.254"}


@pytest.fixture(autouse=True)
def fake_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    async def resolve(host: str) -> list[str]:
        address = DNS.get(host, host)
        if is_forbidden_ip(ipaddress.ip_address(address)):
            raise UnsafeUrlError("приватний IP")
        return [address]

    monkeypatch.setattr(pw, "resolve_public", resolve)


@dataclass
class _Frame:
    parent_frame: Any = None


@dataclass
class _Response:
    status: int
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class _Request:
    url: str
    resource_type: str = "document"
    navigation: bool = True
    frame: _Frame = field(default_factory=_Frame)

    def is_navigation_request(self) -> bool:
        return self.navigation


@dataclass
class _Route:
    request: _Request
    reply: _Response | None = None
    outcome: str = ""

    async def abort(self, reason: str = "failed") -> None:
        self.outcome = f"abort:{reason}"

    async def continue_(self) -> None:
        self.outcome = "continue"

    async def fetch(self, **_: Any) -> _Response:
        assert self.reply is not None
        return self.reply

    async def fulfill(self, response: _Response) -> None:
        self.outcome = f"fulfill:{response.status}"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1/",
        "http://metadata.test/latest/",
        "http://[::ffff:7f00:1]/",
        "file:///etc/passwd",
        "ftp://site.test/",
    ],
)
async def test_internal_or_non_web_addresses_are_aborted(url: str) -> None:
    route = _Route(_Request(url, resource_type="fetch", navigation=False))
    await pw._Guard().route(route)
    assert route.outcome == "abort:blockedbyclient"


async def test_public_subresource_goes_through() -> None:
    route = _Route(_Request("https://cdn.test/app.js", resource_type="script", navigation=False))
    await pw._Guard().route(route)
    assert route.outcome == "continue"


async def test_main_frame_redirect_is_not_handed_to_the_browser() -> None:
    """Інакше наступний крок браузер зробить сам, і перевірки не буде."""
    guard = pw._Guard()
    route = _Route(
        _Request("https://site.test/"), reply=_Response(302, {"location": "/next"})
    )
    await guard.route(route)
    assert route.outcome == "abort:aborted"
    assert guard.redirect_to == "https://site.test/next"


async def test_redirect_to_internal_host_is_blocked_before_any_request() -> None:
    guard = pw._Guard()
    route = _Route(
        _Request("https://site.test/"),
        reply=_Response(302, {"location": "http://metadata.test/latest/"}),
    )
    await guard.route(route)
    assert route.outcome == "abort:blockedbyclient"
    assert guard.redirect_to is None


async def test_ordinary_navigation_is_fulfilled() -> None:
    route = _Route(_Request("https://site.test/"), reply=_Response(200))
    await pw._Guard().route(route)
    assert route.outcome == "fulfill:200"


async def test_guard_goto_follows_checked_redirects() -> None:
    guard = pw._Guard()
    visited: list[str] = []

    class _Page:
        async def goto(self, url: str, **_: Any) -> None:
            visited.append(url)
            if url.endswith("/a"):
                guard.redirect_to = "https://site.test/b"
                raise RuntimeError("net::ERR_ABORTED")

    await guard.goto(_Page(), "https://site.test/a")
    assert visited == ["https://site.test/a", "https://site.test/b"]


async def test_guard_goto_gives_up_on_endless_redirects() -> None:
    guard = pw._Guard()

    class _Page:
        async def goto(self, url: str, **_: Any) -> None:
            guard.redirect_to = url + "x"
            raise RuntimeError("net::ERR_ABORTED")

    with pytest.raises(RuntimeError, match="перенаправлень"):
        await guard.goto(_Page(), "https://site.test/")
