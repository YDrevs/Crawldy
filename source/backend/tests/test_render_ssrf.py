"""SSRF-межа браузера: кожен запит сторінки проходить ту саму перевірку адреси.

Раніше `page.route` відсікав лише тип ресурсу, тож навігація, редирект,
XHR чи iframe сторінки клієнта могли піти на `169.254.169.254`, а
`page.content()` повертав би відповідь у знімок.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.audit.fetcher import UnsafeUrlError
from app.audit.render.playwright import _RouteGuard


@dataclass
class _Request:
    url: str
    resource_type: str = "document"


@dataclass
class _Route:
    request: _Request
    outcome: list[str] = field(default_factory=list)

    async def abort(self, error_code: str | None = None) -> None:
        self.outcome.append(f"abort:{error_code}")

    async def continue_(self) -> None:
        self.outcome.append("continue")


def _guard() -> tuple[_RouteGuard, list[str]]:
    checked: list[str] = []

    async def check(url: str) -> None:
        checked.append(url)
        host = url.split("/")[2].split(":")[0]
        if host in {"169.254.169.254", "127.0.0.1", "db.internal"}:
            raise UnsafeUrlError("приватний")

    return _RouteGuard(check=check), checked


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://127.0.0.1:6379/",
        "https://db.internal/api",
        "file:///etc/passwd",
        "ftp://example.com/x",
        "chrome://settings",
    ],
)
async def test_private_or_foreign_scheme_requests_are_aborted(url: str) -> None:
    guard, _ = _guard()
    route = _Route(_Request(url, resource_type="xhr"))

    await guard(route)

    assert route.outcome == ["abort:blockedbyclient"]


async def test_public_request_continues() -> None:
    guard, _ = _guard()
    route = _Route(_Request("https://example.com/app.js", resource_type="script"))

    await guard(route)

    assert route.outcome == ["continue"]


async def test_heavy_resources_are_still_dropped() -> None:
    guard, checked = _guard()
    route = _Route(_Request("https://example.com/v.mp4", resource_type="media"))

    await guard(route)

    assert route.outcome == ["abort:None"]
    assert checked == []


async def test_host_is_checked_once_per_render() -> None:
    guard, checked = _guard()
    for path in ("/a", "/b", "/c"):
        await guard(_Route(_Request(f"https://example.com{path}")))
    for _ in range(2):
        await guard(_Route(_Request("http://169.254.169.254/x")))

    assert len(checked) == 2


async def test_failing_check_is_treated_as_forbidden() -> None:
    """Збій резолву — не дозвіл."""

    async def check(url: str) -> None:
        raise OSError("dns down")

    guard = _RouteGuard(check=check)
    route = _Route(_Request("https://example.com/"))

    await guard(route)

    assert route.outcome == ["abort:blockedbyclient"]


async def test_final_url_check() -> None:
    guard, _ = _guard()

    assert await guard.allows("https://example.com/landing")
    assert not await guard.allows("http://127.0.0.1/")
    assert not await guard.allows("file:///etc/passwd")
    # about:blank — сторінка, яку ще не завантажили; про мережу вона не каже.
    assert not await guard.allows("about:blank")
