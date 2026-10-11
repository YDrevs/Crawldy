"""Межа сайту: одне правило для екстрактора й фронтира.

Ці тести існують через конкретний дефект. На нічному прогоні 278 сайтів
із 959 мали посилання на самих себе, які краул вважав чужими:
екстрактор порівнював `netloc` буквально (`www.kernel.org` ≠
`kernel.org`), а фронтир робив `url.startswith(origin)` — тобто
порівнював рядок разом зі схемою, і `https://x/page` не проходив, коли
вхід був `http://x`.

Найважливіше тут — не окремі випадки, а те, що **обидва шляхи
перевіряються на одному переліку**. Дві реалізації одного правила вже
розійшлися одного разу; тест, який дивиться лише на один бік, дозволив
би їм розійтися знову.
"""

from __future__ import annotations

import pytest

from app.audit.extractor import extract
from app.audit.fetcher import FetchResult
from app.audit.frontier import Frontier
from app.audit.site_scope import SiteScope, same_site


def _links_for(origin: str, href: str) -> list:
    """Сигнали сторінки з єдиним посиланням — щоб питати екстрактор прямо."""
    html = f'<html><body><a href="{href}">посилання</a></body></html>'
    result = FetchResult(
        url=f"{origin}/", final_url=f"{origin}/", status_code=200,
        content_type="text/html", text=html, body_bytes=len(html),
        elapsed_ms=1, headers={"content-type": "text/html"},
    )
    return list(extract(result, origin=origin).links)


# (origin, url, той самий сайт?, чому)
CASES: tuple[tuple[str, str, bool, str], ...] = (
    # ── схема: сайт, що переїхав на https, лишається собою ────────────
    ("http://example.com", "https://example.com/page", True, "http → https"),
    ("https://example.com", "http://example.com/page", True, "https → http"),
    # ── корінь і www — псевдоніми ─────────────────────────────────────
    ("https://example.com", "https://www.example.com/page", True, "корінь → www"),
    ("https://www.example.com", "https://example.com/page", True, "www → корінь"),
    ("http://example.com", "https://www.example.com/p", True, "схема і www разом"),
    ("https://www.shop.example.com", "https://shop.example.com/x", True,
     "www піддомену — теж псевдонім свого хоста"),
    # ── довільний піддомен внутрішнім НЕ стає ─────────────────────────
    ("https://example.com", "https://shop.example.com/p", False, "магазин на піддомені"),
    ("https://example.com", "https://docs.example.com/p", False, "довідка на піддомені"),
    ("https://example.com", "https://blog.example.com/p", False, "блог на піддомені"),
    ("https://shop.example.com", "https://example.com/x", False, "піддомен → корінь"),
    # ── чужі й схожі назви ────────────────────────────────────────────
    ("https://example.com", "https://other.org/page", False, "інший домен"),
    ("https://example.com", "https://example.com.evil.org/", False,
     "назва закінчується не там, де здається"),
    ("https://example.com", "https://evilexample.com/", False, "підрядок без межі мітки"),
    ("https://example.com", "https://notexample.com/", False, "підрядок без межі мітки"),
    # ── порти ─────────────────────────────────────────────────────────
    ("https://example.com", "https://example.com:443/p", True, "типовий порт https"),
    ("http://example.com", "http://example.com:80/p", True, "типовий порт http"),
    ("https://example.com", "https://example.com:8080/p", False, "інший порт"),
    ("https://example.com:8080", "https://example.com:8080/x", True, "той самий порт"),
    ("https://example.com:8080", "https://example.com/x", False, "порт проти типового"),
    # ── дрібниці написання ────────────────────────────────────────────
    ("https://example.com", "https://EXAMPLE.COM/Page", True, "регістр хоста"),
    ("https://example.com", "https://example.com./page", True, "кінцева крапка"),
    ("https://example.com", "https://example.com/p?a=1", True, "запит не впливає"),
    ("https://example.com", "https://example.com/p#frag", True, "фрагмент не впливає"),
    # ── не адреси сторінок ────────────────────────────────────────────
    ("https://example.com", "mailto:hello@example.com", False, "mailto"),
    ("https://example.com", "javascript:void(0)", False, "javascript"),
    ("https://example.com", "", False, "порожньо"),
)


@pytest.mark.parametrize(("origin", "url", "expected", "why"), CASES)
def test_site_scope_rule(origin: str, url: str, expected: bool, why: str) -> None:
    """1. Саме правило."""
    assert same_site(url, origin) is expected, why


@pytest.mark.parametrize(("origin", "url", "expected", "why"), CASES)
def test_frontier_admits_exactly_what_the_rule_calls_the_same_site(
    origin: str, url: str, expected: bool, why: str
) -> None:
    """2. Фронтир не має власної думки про межу сайту.

    Саме розбіжність між ним і екстрактором давала найгірший випадок:
    екстрактор називав посилання внутрішнім, фронтир відкидав його як
    зовнішнє, і сайт виглядав односторінковим при `failed_urls: 0`.
    """
    frontier = Frontier(origin=origin, max_depth=2)
    allowed, reason = frontier.eligible(url)
    if expected:
        assert allowed, f"{why}: фронтир відкинув свій же сайт ({reason})"
    else:
        assert not allowed, f"{why}: фронтир пустив чужу адресу"


@pytest.mark.parametrize(("origin", "url", "expected", "why"), CASES)
def test_extractor_marks_internal_exactly_like_the_rule(
    origin: str, url: str, expected: bool, why: str
) -> None:
    """3. Екстрактор теж не має власної думки.

    `is_internal` живить граф посилань, сироти, тексти підписів і
    пріоритет краулу — розходження тут отруює одразу кілька чеків.
    """
    if not url.startswith(("http://", "https://")):
        pytest.skip("екстрактор такі схеми відсіює раніше")
    found = _links_for(origin, url)
    links = [x for x in found if x.url.startswith(("http://", "https://"))]
    assert links, "посилання мало потрапити в сигнали"
    assert links[0].is_internal is expected, why


def test_the_two_paths_cannot_drift_apart() -> None:
    """4. Головне: обидва шляхи згодні між собою на всьому переліку.

    Тести вище перевіряють кожен бік окремо. Цей стверджує саме те, чого
    бракувало: що вони дають ОДНАКОВУ відповідь.
    """
    for origin, url, _, why in CASES:
        if not url.startswith(("http://", "https://")):
            continue
        rule = same_site(url, origin)
        frontier_says = Frontier(origin=origin, max_depth=2).eligible(url)[0]
        links = _links_for(origin, url)
        extractor_says = links[0].is_internal if links else False
        assert rule == frontier_says == extractor_says, (
            f"{why}: правило={rule} фронтир={frontier_says} екстрактор={extractor_says}"
        )


def test_the_real_defect_cases_from_night1() -> None:
    """5. Три випадки з нічного прогону, дослівно.

    `hospitalsancarlos.cl` віддав 20 внутрішніх посилань і прочитав одну
    сторінку. `kernel.org` — 91 посилання, усі на `www.kernel.org`.
    """
    # вхід на http, сайт лінкує себе через https
    f = Frontier(origin="http://hospitalsancarlos.cl", max_depth=2)
    assert f.eligible("https://hospitalsancarlos.cl/portal/quienes-somos/")[0]

    # вхід без www, навігація на www
    f = Frontier(origin="https://kernel.org", max_depth=2)
    assert f.eligible("https://www.kernel.org/category/releases.html")[0]

    # і навпаки
    f = Frontier(origin="http://fernandes.co.jp", max_depth=2)
    assert f.eligible("https://fernandes.co.jp/gakki/")[0]


def test_entry_redirect_establishes_the_scope() -> None:
    """6. Межу задає адреса, на якій краул СПРАВДІ опинився.

    Вхід `http://x`, що веде на `https://www.x`, лишає обидві початкові
    адреси всередині межі: інакше сайт після перенаправлення переставав
    би бути собою.
    """
    scope = SiteScope.from_url("https://www.example.com/")
    assert scope.contains("http://example.com/page")
    assert scope.contains("https://www.example.com/page")
    assert not scope.contains("https://cdn.example.com/asset")


def test_a_broken_origin_admits_nothing() -> None:
    """7. Невідома межа не означає «пускати все»."""
    for bad in ("", "not-a-url", "ftp://example.com", "https://"):
        scope = SiteScope.from_url(bad)
        assert not scope.is_valid
        assert not scope.contains("https://example.com/page")
