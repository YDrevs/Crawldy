"""Адреси, які видно лише після виконання JS, у спільній черзі краулу.

## Що тут стоїть замість справжнього, а що ні

Підмінено рівно два шари: транспорт HTTP і браузер. Усе між ними —
справжнє: `Frontier` із його правилами допуску, `crawl()`, `extract()`,
`render_diff.compare()` і хвильовий цикл оркестратора. Інакше тест
перевіряв би власні заглушки: питання ж саме в тому, чи проходять
відрендеровані адреси ті самі двері, що й статичні.

Сайт описується словником «адреса → HTML» у двох версіях — тій, що
віддає сервер, і тій, що лишається після JS. Різницю між ними знаходить
той самий компаратор, що працює в продукті.
"""

from __future__ import annotations

import pytest

from app.audit.fetcher import FetchResult
from app.audit.frontier import Frontier, Source
from app.audit.orchestrator import AuditOptions, _render_and_discover
from app.audit.types import RenderResult, SiteContext

ORIGIN = "https://spa.test"
HOME = f"{ORIGIN}/"


def html(body: str = "", *, title: str = "Page") -> str:
    return (
        f"<html lang='en'><head><title>{title}</title></head>"
        f"<body><h1>{title}</h1>{body}<p>Some words on the page.</p></body></html>"
    )


def links(*urls: str) -> str:
    return "".join(f'<a href="{u}">link</a>' for u in urls)


class FakeFetcher:
    """Транспорт, і більше нічого. Рахує кожен запит поіменно."""

    def __init__(self, pages: dict[str, str], *, missing: int = 404) -> None:
        self.pages = pages
        self.missing = missing
        self.requested: list[str] = []

    async def get(self, url: str) -> FetchResult:
        self.requested.append(url)
        body = self.pages.get(url)
        if body is None:
            return FetchResult(
                url=url, final_url=url, status_code=self.missing, content_type="text/html",
                text="", body_bytes=0, elapsed_ms=5, headers={},
            )
        return FetchResult(
            url=url, final_url=url, status_code=200, content_type="text/html",
            text=body, body_bytes=len(body), elapsed_ms=5, headers={},
        )

    async def aclose(self) -> None:
        return None


class FakeRenderer:
    """Браузер, який віддає заздалегідь відомий DOM."""

    name = "fake"

    def __init__(self, dom: dict[str, str], *, fails: bool = False, disabled: bool = False):
        self.dom = dom
        self.fails = fails
        self.disabled = disabled
        self.rendered: list[str] = []

    async def render(self, url: str) -> RenderResult:
        self.rendered.append(url)
        if self.fails or self.disabled:
            return RenderResult(
                url=url, rendered=False, disabled=self.disabled,
                error="вимкнено" if self.disabled else "браузер не піднявся",
            )
        return RenderResult(url=url, rendered=True, html=self.dom.get(url, html()))

    async def aclose(self) -> None:
        return None


async def run_site(
    monkeypatch,
    response: dict[str, str],
    dom: dict[str, str] | None = None,
    *,
    max_pages: int = 25,
    max_depth: int = 2,
    render_budget: int = 3,
    renderer: FakeRenderer | None = None,
    robots: object | None = None,
) -> tuple[SiteContext, FakeFetcher, FakeRenderer]:
    """Проганяє справжній краул і справжній хвильовий цикл по фікстурі."""
    from app.audit import orchestrator
    from app.audit.crawler import crawl

    fetcher = FakeFetcher(response)
    browser = renderer if renderer is not None else FakeRenderer(dom or {})
    monkeypatch.setattr(orchestrator, "get_renderer", lambda _enabled: browser)

    ctx = SiteContext(entry_url=HOME, origin=ORIGIN, is_https=True)
    frontier = Frontier(origin=ORIGIN, max_depth=max_depth, robots=robots)
    frontier.offer(HOME, 0, source=Source.ENTRY)

    pages, failed = await crawl(
        fetcher, HOME, ORIGIN, max_pages=max_pages, max_depth=max_depth, frontier=frontier
    )
    orchestrator._absorb(ctx, HOME, pages, failed)

    await _render_and_discover(
        ctx,
        AuditOptions(render_max_pages=render_budget),
        [],
        fetcher=fetcher,
        frontier=frontier,
        entry_url=HOME,
        max_pages=max_pages,
        max_depth=max_depth,
    )
    return ctx, fetcher, browser


def urls(ctx: SiteContext) -> set[str]:
    return {p.url for p in ctx.ok_pages}


# ── 1–3. Основна поведінка ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_ordinary_static_site_behaves_exactly_as_before(monkeypatch):
    """1. Сайт без JS-навігації нічого не має помітити."""
    site = {HOME: html(links("/a", "/b")), f"{ORIGIN}/a": html(), f"{ORIGIN}/b": html()}
    ctx, fetcher, _ = await run_site(monkeypatch, site, dom=site)
    assert urls(ctx) == {HOME, f"{ORIGIN}/a", f"{ORIGIN}/b"}
    assert sorted(fetcher.requested) == sorted(site)


@pytest.mark.asyncio
async def test_a_link_that_exists_only_after_rendering_is_crawled(monkeypatch):
    """2. Оболонка без жодного посилання; `/a` домальовує JS.

    Саме це раніше давало краул на одну сторінку: у відповіді сервера
    посилань немає, а те, що їх домальовує скрипт, ніде не читалося.
    """
    response = {HOME: html(), f"{ORIGIN}/a": html(title="A")}
    dom = {HOME: html(links("/a"))}
    ctx, _, _ = await run_site(monkeypatch, response, dom)
    assert f"{ORIGIN}/a" in urls(ctx)


@pytest.mark.asyncio
async def test_discovery_continues_to_a_second_level(monkeypatch):
    """3. `оболонка → A → B`: один шар відкриття недостатньо.

    Вимога явна: реалізація, яка ставить знайдене в чергу один раз і
    спиняється, лишає глибшу JS-навігацію невидимою.
    """
    response = {HOME: html(), f"{ORIGIN}/a": html(title="A"), f"{ORIGIN}/b": html(title="B")}
    dom = {HOME: html(links("/a")), f"{ORIGIN}/a": html(links("/b"), title="A")}
    ctx, _, browser = await run_site(monkeypatch, response, dom)
    assert {f"{ORIGIN}/a", f"{ORIGIN}/b"} <= urls(ctx)
    assert browser.rendered[:2] == [HOME, f"{ORIGIN}/a"]


# ── 4–10. Правила допуску — ті самі, що для статичних адрес ───────────────


@pytest.mark.asyncio
async def test_a_url_present_both_statically_and_after_render_is_fetched_once(monkeypatch):
    """4. Рендер не є приводом прочитати сторінку вдруге."""
    response = {HOME: html(links("/a")), f"{ORIGIN}/a": html(title="A")}
    dom = {HOME: html(links("/a"))}
    _, fetcher, _ = await run_site(monkeypatch, response, dom)
    assert fetcher.requested.count(f"{ORIGIN}/a") == 1


@pytest.mark.asyncio
async def test_a_rendered_link_that_normalizes_onto_a_static_one_is_fetched_once(monkeypatch):
    """5. `/a` і `/a/` — одна сторінка, хто б їх не приніс."""
    response = {HOME: html(links("/a")), f"{ORIGIN}/a": html(title="A")}
    dom = {HOME: html(links("/a/", "/a?utm_source=x"))}
    _, fetcher, _ = await run_site(monkeypatch, response, dom)
    assert len([u for u in fetcher.requested if u.rstrip("/").endswith("/a")]) == 1


@pytest.mark.asyncio
async def test_an_external_rendered_link_is_not_crawled(monkeypatch):
    """6. Чужий домен лишається чужим і після рендеру."""
    response = {HOME: html()}
    dom = {HOME: html(links("https://elsewhere.test/a"))}
    _, fetcher, _ = await run_site(monkeypatch, response, dom)
    assert not any("elsewhere.test" in u for u in fetcher.requested)


@pytest.mark.asyncio
async def test_a_fragment_only_difference_does_not_add_a_page(monkeypatch):
    """7. `#section` — це та сама сторінка."""
    response = {HOME: html(links("/a")), f"{ORIGIN}/a": html(title="A")}
    dom = {HOME: html(links("/a#top", "/a#bottom"))}
    _, fetcher, _ = await run_site(monkeypatch, response, dom)
    assert fetcher.requested.count(f"{ORIGIN}/a") == 1


@pytest.mark.asyncio
async def test_unsupported_schemes_never_enter_the_queue(monkeypatch):
    """8. `mailto:`, `tel:`, `javascript:` сторінками не є."""
    frontier = Frontier(origin=ORIGIN, max_depth=2)
    for bad in ("mailto:a@b.test", "tel:+123", "javascript:void(0)", "data:text/html,x"):
        assert frontier.offer(bad, 1, source=Source.RENDER) is False
        assert frontier.eligible(bad)[1] == "scheme"


@pytest.mark.asyncio
async def test_a_rendered_url_disallowed_by_robots_is_not_crawled(monkeypatch):
    """9. robots.txt діє на відрендеровані адреси так само, як на решту.

    Гейт стоїть у спільних дверях черги, а не в окремій гілці для
    рендеру: правило, написане двічі, розходиться на першій дрібниці.
    """
    from app.audit import robots as robots_rfc

    parsed = robots_rfc.parse("User-agent: *\nDisallow: /private\n")
    response = {HOME: html(), f"{ORIGIN}/private": html(), f"{ORIGIN}/ok": html()}
    dom = {HOME: html(links("/private", "/ok"))}
    _, fetcher, _ = await run_site(monkeypatch, response, dom, robots=parsed)
    assert f"{ORIGIN}/ok" in fetcher.requested
    assert f"{ORIGIN}/private" not in fetcher.requested


@pytest.mark.asyncio
async def test_an_already_visited_url_is_not_crawled_again(monkeypatch):
    """10. Прочитане лишається прочитаним між хвилями."""
    response = {HOME: html(links("/a")), f"{ORIGIN}/a": html(title="A")}
    dom = {HOME: html(links("/a")), f"{ORIGIN}/a": html(links("/", "/a"), title="A")}
    _, fetcher, _ = await run_site(monkeypatch, response, dom)
    assert fetcher.requested.count(HOME) <= 1
    assert fetcher.requested.count(f"{ORIGIN}/a") == 1


# ── 11–13. Завершення й бюджети ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_cyclic_js_only_links_terminate(monkeypatch):
    """11. `A → B → A` не має крутитися вічно."""
    response = {HOME: html(), f"{ORIGIN}/a": html(title="A"), f"{ORIGIN}/b": html(title="B")}
    dom = {
        HOME: html(links("/a")),
        f"{ORIGIN}/a": html(links("/b"), title="A"),
        f"{ORIGIN}/b": html(links("/a"), title="B"),
    }
    ctx, fetcher, _ = await run_site(monkeypatch, response, dom)
    assert len(fetcher.requested) == len(set(fetcher.requested))
    assert urls(ctx) == set(response)


@pytest.mark.asyncio
async def test_the_global_page_budget_is_one_budget(monkeypatch):
    """12. Знайдене через рендер витрачає той самий `max_pages`.

    Окремий бюджет на відрендероване означав би, що ліміт у звіті й
    ліміт насправді — різні числа.
    """
    response = {HOME: html()} | {f"{ORIGIN}/p{i}": html(title=f"P{i}") for i in range(10)}
    dom = {HOME: html(links(*(f"/p{i}" for i in range(10))))}
    ctx, _, _ = await run_site(monkeypatch, response, dom, max_pages=4)
    assert len(ctx.raw_pages) <= 4


@pytest.mark.asyncio
async def test_the_render_budget_bounds_the_number_of_waves(monkeypatch):
    """13. Рендер — паливо хвиль, і воно скінченне."""
    response = {HOME: html()} | {f"{ORIGIN}/p{i}": html(title=f"P{i}") for i in range(6)}
    dom = {HOME: html(links("/p0"))} | {
        f"{ORIGIN}/p{i}": html(links(f"/p{i + 1}"), title=f"P{i}") for i in range(5)
    }
    _, _, browser = await run_site(monkeypatch, response, dom, render_budget=2)
    assert len(browser.rendered) == 2


# ── 14–15. Невизначеність рендеру ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_disabled_renderer_leaves_the_static_crawl_untouched(monkeypatch):
    """14. Вимкнений рендер — це вибір користувача, а не збій."""
    site = {HOME: html(links("/a")), f"{ORIGIN}/a": html(title="A")}
    ctx, _, _ = await run_site(
        monkeypatch, site, renderer=FakeRenderer({}, disabled=True)
    )
    assert urls(ctx) == set(site)


@pytest.mark.asyncio
async def test_a_failed_render_does_not_conclude_that_there_are_no_js_links(monkeypatch):
    """15. Збій браузера — не доказ відсутності JS-навігації.

    Найважливіший запобіжник цієї роботи: висновок про відсутність
    вимагає успішного порівнюваного рендеру, а не його спроби.
    """
    from app.audit import render_diff

    response = {HOME: html(), f"{ORIGIN}/a": html(title="A")}
    ctx, _, _ = await run_site(
        monkeypatch, response, renderer=FakeRenderer({}, fails=True)
    )
    assert urls(ctx) == {HOME}
    diffs = render_diff.compare_all(ctx)
    assert diffs and all(not d.comparable for d in diffs)
    assert all(d.reason for d in diffs)


# ── 16–19. Походження, граф, глибина ──────────────────────────────────────


@pytest.mark.asyncio
async def test_provenance_says_which_source_actually_found_the_page(monkeypatch):
    """16. Походження відповідає на питання «звідки ми про неї дізналися».

    `/a` стоїть і у відповіді сервера, і в DOM — але походження в нього
    одне, `response`, і це правильно: у DOM воно не «зʼявилося», воно
    там просто лишилося. `Source.RENDER` означає рівно те, що показує
    `only_after_render` — посилання, якого у відповіді не було.
    """
    response = {
        HOME: html(links("/a")),
        f"{ORIGIN}/a": html(title="A"),
        f"{ORIGIN}/b": html(title="B"),
    }
    dom = {HOME: html(links("/a", "/b"))}
    ctx, _, _ = await run_site(monkeypatch, response, dom)
    by_url = {p.url: p.discovered_via for p in ctx.ok_pages}
    assert by_url[HOME] == ["entry"]
    assert by_url[f"{ORIGIN}/a"] == ["response"]
    assert by_url[f"{ORIGIN}/b"] == ["render"]


def test_two_sources_for_one_url_are_merged_not_duplicated():
    """17. Сторінка з меню, яка ще й у карті, — одна сторінка, два джерела.

    Це і є справжній випадок злиття, заради якого походження є списком,
    а не одним значенням.
    """
    frontier = Frontier(origin=ORIGIN, max_depth=2)
    assert frontier.offer(f"{ORIGIN}/a", 1, source=Source.RESPONSE) is True
    # Друга пропозиція в чергу не стає — але джерело записує.
    assert frontier.offer(f"{ORIGIN}/a", 1, source=Source.SITEMAP, seeded=True) is False
    assert frontier.sources_of(f"{ORIGIN}/a") == ("response", "sitemap")


@pytest.mark.asyncio
async def test_a_rendered_discovery_joins_the_ordinary_link_graph(monkeypatch):
    """18. Знайдена сторінка отримує вхідне ребро, а не статус сироти.

    Посилання на неї ми бачили на власні очі — просто в DOM, а не у
    відповіді сервера. Граф, побудований лише зі статичних посилань,
    назвав би її несиротою помилково.
    """
    from app.audit.link_graph import build

    response = {HOME: html(), f"{ORIGIN}/a": html(title="A")}
    dom = {HOME: html(links("/a"))}
    ctx, _, _ = await run_site(monkeypatch, response, dom)
    graph = build(ctx)
    assert graph.incoming.get(f"{ORIGIN}/a") == 1
    assert graph.outgoing.get(HOME) == 1


@pytest.mark.asyncio
async def test_graph_depth_reflects_the_path_actually_taken(monkeypatch):
    """19. `/b` знайдено через `/a`, тож воно глибше за `/a`."""
    from app.audit.link_graph import build

    response = {HOME: html(), f"{ORIGIN}/a": html(title="A"), f"{ORIGIN}/b": html(title="B")}
    dom = {HOME: html(links("/a")), f"{ORIGIN}/a": html(links("/b"), title="A")}
    ctx, _, _ = await run_site(monkeypatch, response, dom)
    graph = build(ctx)
    assert graph.depth[HOME] == 0
    assert graph.depth[f"{ORIGIN}/a"] == 1
    assert graph.depth[f"{ORIGIN}/b"] == 2


@pytest.mark.asyncio
async def test_coverage_counts_the_pages_we_actually_read(monkeypatch):
    """20. Сторінки, відкриті після рендеру, — теж прочитані сторінки."""
    response = {HOME: html(), f"{ORIGIN}/a": html(title="A")}
    dom = {HOME: html(links("/a"))}
    ctx, _, _ = await run_site(monkeypatch, response, dom)
    assert ctx.urls_crawled == 2
    assert len(ctx.raw_pages) == 2


# ── 21–24. Наявні поверхні лишаються цілими ───────────────────────────────


@pytest.mark.asyncio
async def test_render_delta_still_reports_the_difference_without_a_second_finding(monkeypatch):
    """21. Відкриття не породжує другого критерію про те саме."""
    from app.audit.checks import all_checks

    response = {HOME: html(), f"{ORIGIN}/a": html(title="A")}
    dom = {HOME: html(links("/a"))}
    ctx, _, _ = await run_site(monkeypatch, response, dom)

    issues = [i for c in all_checks() for i in c.run(ctx)]
    delta = [i for i in issues if i.code == "seo.render_delta"]
    assert delta, "різниця між відповіддю й DOM має лишатися знахідкою"
    assert len({i.code for i in issues if "render" in i.code}) == 1
    # Доказ збагачено, а не продубльовано окремою знахідкою.
    assert delta[0].evidence["links"]["only_after_render_crawled"] == 1


@pytest.mark.asyncio
async def test_a_snapshot_round_trip_keeps_discovery_provenance(monkeypatch):
    """22. Перерахунок має пояснювати, звідки взялася сторінка."""
    import json

    from app.audit import snapshot

    response = {HOME: html(), f"{ORIGIN}/a": html(title="A")}
    dom = {HOME: html(links("/a"))}
    ctx, _, _ = await run_site(monkeypatch, response, dom)

    restored = snapshot.load(json.loads(json.dumps(snapshot.dump(ctx))))
    assert {p.url: p.discovered_via for p in restored.ok_pages} == {
        p.url: p.discovered_via for p in ctx.ok_pages
    }


def test_an_old_snapshot_without_provenance_still_loads():
    """23. Знімок, старший за поле, лишається читаним — і мовчить про походження.

    Порожній список означає «невідомо», а не «зі статичного HTML»:
    вигадувати походження заднім числом ми не маємо права.
    """
    import json
    import pathlib

    from app.audit import snapshot

    old = next(pathlib.Path("benchmark/snapshots").glob("*.json"))
    ctx = snapshot.load(json.loads(old.read_text(encoding="utf-8")))
    assert ctx.pages
    assert all(p.discovered_via == [] for p in ctx.pages)


def test_no_scoring_constant_moved():
    """24. Це зміна спостереження, а не оцінки.

    Бали сайтів зміняться там, де ми справді дочитаємо більше сторінок,
    — це і є мета. Правила підрахунку при цьому не рухаються, і відбиток
    скорингу тримає межу.
    """
    from app.audit.versions import scoring_version

    # 3fdd28054fda — заморожені константи при SCORING_RULES=2.
    # 0cfbc304bc32 — ті САМІ константи при SCORING_RULES=3: покоління
    # підняли свідомо, коли придатність модулів до site-level бала
    # передали оцінці покриття (A/B на 969 знімках night3: жоден бал,
    # що існував в обох прогонах, не зсунувся ані на одиницю).
    # 7b16db310137 — глобальні ваги модулів, затверджені 2026-08-31
    # (сценарій F калібрування): SEO .26, perf .18, ai .16, llm .14,
    # tech .16, a11y .10. Покоління SCORING_RULES не рухалось: зміну
    # констант відбиток бачить сам. Зняття заморозки явне, A/B на тих
    # самих 969 знімках — у detector_sweep_packet.json.
    # c6a1c3fd43d8 — SCORING_RULES=4 (4 вересня 2026): жодна константа
    # формули не змінилась, але `tech.form_protection:get_method`
    # перестав бути безкоштовним, і бали по різні боки цієї межі
    # непорівнянні. Рішення власника, вимірювання — у пакеті.
    # aa4ecc62a5a3 — SCORING_RULES=5 (13 вересня 2026, G6: E-07): знову
    # жодна константа формули не змінилась. `scoring_version()` хешує
    # SCORING_RULES ПЕРШИМ, а вже потім ваги, півшкали, стелі, множники
    # й смуги — тож відбиток зсунуло саме покоління. Змінився набір
    # чеків: `ai.schema.faq` вилучено зі скорингу, і `ai_ready` зростає
    # рівно там, де він спрацьовував.
    assert scoring_version() == "aa4ecc62a5a3"


@pytest.mark.asyncio
async def test_a_prefetched_entry_survives_being_given_a_shared_queue(monkeypatch):
    """25. Найдорожча помилка цієї роботи, і фікстури її не бачили.

    Оркестратор тягне головну сторінку сам — щоб визначити origin — і
    передає її в краул готовою. Умова, яка вирішувала, чи брати цю
    сторінку, спиралась на «чи передали чергу»; черга ж передається
    завжди, тож у кожному справжньому аудиті головна мовчки зникала, і
    сайт виглядав порожнім. Тести з фікстур проходили всі: вони
    передавали `prefetched=None`.

    Тому перевірка саме на тій комбінації, яка працює в продукті:
    завантажена наперед сторінка плюс спільна черга.
    """
    from app.audit.crawler import crawl

    site = {HOME: html(links("/a")), f"{ORIGIN}/a": html(title="A")}
    fetcher = FakeFetcher(site)
    entry = await fetcher.get(HOME)
    frontier = Frontier(origin=ORIGIN, max_depth=2)

    pages, failed = await crawl(
        fetcher, HOME, ORIGIN, max_pages=10, max_depth=2,
        prefetched=entry, frontier=frontier,
    )
    assert [p.url for p in pages] == [HOME, f"{ORIGIN}/a"]
    assert not failed
    # І головну не перечитано: вона вже була в руках.
    assert fetcher.requested.count(HOME) == 1
