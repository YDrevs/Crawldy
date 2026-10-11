"""Граф внутрішніх посилань: важливість сторінки, сироти, глухі кути."""

from __future__ import annotations

from app.audit.checks.seo import (
    LinksToNoindexCheck,
    OrphanPagesCheck,
    TopicIslandsCheck,
)
from app.audit.link_graph import build
from app.audit.types import SitemapInfo
from tests.factories import context, page_from_html


def _page(url: str, links: list[str], *, depth: int = 1, robots: str | None = None) -> object:
    meta = f'<meta name="robots" content="{robots}">' if robots else ""
    anchors = "".join(f'<a href="{href}">x</a>' for href in links)
    html = f"<html><head><title>t</title>{meta}</head><body><h1>h</h1>{anchors}</body></html>"
    return page_from_html(html, url=url, depth=depth)


def test_home_is_always_the_most_important_page():
    home = _page("https://example.com/", ["/a/"], depth=0)
    inner = _page("https://example.com/a/", [])
    graph = build(context(home, inner))
    assert graph.importance(home) == 1.0
    assert graph.importance(inner) < 1.0


def test_a_page_the_whole_menu_links_to_outweighs_a_forgotten_one():
    """Важливість читається з поведінки сайту, а не з нашої думки про адресу."""
    home = _page("https://example.com/", ["/services/", "/forgotten/"], depth=0)
    second = _page("https://example.com/b/", ["/services/"])
    third = _page("https://example.com/c/", ["/services/"])
    services = _page("https://example.com/services/", [])
    forgotten = _page("https://example.com/forgotten/", [], depth=3)
    graph = build(context(home, second, third, services, forgotten))
    assert graph.importance(services) > graph.importance(forgotten)


def test_page_nobody_links_to_is_still_worth_something():
    """Забута сторінка теж коштує грошей: нуль означав би «не чіпайте її»."""
    home = _page("https://example.com/", [], depth=0)
    orphan = _page("https://example.com/orphan/", [], depth=4)
    graph = build(context(home, orphan))
    assert graph.importance(orphan) > 0


def test_sitemap_page_without_incoming_links_is_an_orphan():
    home = _page("https://example.com/", ["/linked/"], depth=0)
    linked = _page("https://example.com/linked/", [])
    lonely = _page("https://example.com/lonely/", [])
    ctx = context(
        home,
        linked,
        lonely,
        sitemap=SitemapInfo(
            exists=True,
            status_code=200,
            url_count=3,
            urls=["https://example.com/", "https://example.com/linked/",
                  "https://example.com/lonely/"],
        ),
    )
    ctx.links = build(ctx)
    issues = list(OrphanPagesCheck().run(ctx))
    assert len(issues) == 1
    assert issues[0].evidence["orphans"] == ["https://example.com/lonely/"]


def test_home_is_never_reported_as_an_orphan():
    """На головну зазвичай не посилаються з меню, і це не проблема."""
    home = _page("https://example.com/", ["/a/"], depth=0)
    inner = _page("https://example.com/a/", [])
    ctx = context(
        home,
        inner,
        sitemap=SitemapInfo(
            exists=True, status_code=200, url_count=2,
            urls=["https://example.com/", "https://example.com/a/"],
        ),
    )
    ctx.links = build(ctx)
    assert not list(OrphanPagesCheck().run(ctx))


def test_page_outside_the_sitemap_is_not_called_an_orphan():
    """Без карти сайту ми не знаємо, чи сторінка задумана як самостійна."""
    home = _page("https://example.com/", [], depth=0)
    unlinked = _page("https://example.com/unlinked/", [])
    ctx = context(home, unlinked)
    ctx.links = build(ctx)
    assert not list(OrphanPagesCheck().run(ctx))


def test_link_to_a_noindex_page_is_a_contradiction():
    home = _page("https://example.com/", ["/cabinet/"], depth=0)
    cabinet = _page("https://example.com/cabinet/", [], robots="noindex")
    ctx = context(home, cabinet)
    ctx.links = build(ctx)
    issues = list(LinksToNoindexCheck().run(ctx))
    assert len(issues) == 1
    assert issues[0].evidence["targets"] == ["https://example.com/cabinet/"]


def test_a_consistent_site_gives_no_findings():
    home = _page("https://example.com/", ["/a/", "/b/"], depth=0)
    first = _page("https://example.com/a/", ["/b/"])
    second = _page("https://example.com/b/", ["/a/"])
    ctx = context(
        home,
        first,
        second,
        sitemap=SitemapInfo(
            exists=True, status_code=200, url_count=3,
            urls=["https://example.com/", "https://example.com/a/", "https://example.com/b/"],
        ),
    )
    ctx.links = build(ctx)
    assert not list(OrphanPagesCheck().run(ctx))
    assert not list(LinksToNoindexCheck().run(ctx))


def test_self_links_do_not_inflate_importance():
    home = _page("https://example.com/", [], depth=0)
    looping = _page("https://example.com/a/", ["/a/", "/a/?utm_source=x"])
    graph = build(context(home, looping))
    assert graph.incoming.get("https://example.com/a/", 0) == 0


def test_orphans_stay_silent_when_we_read_a_fraction_of_the_site():
    """Судити з відсутності посилань можна лише там, де ми справді дивилися.

    На furniturerow.com у карті 8147 адрес проти двадцяти п'яти в бюджеті:
    сторінка без вхідних посилань серед прочитаних — це наш бюджет, а не
    структура сайту.
    """
    home = _page("https://example.com/", [], depth=0)
    lonely = _page("https://example.com/lonely/", [])
    ctx = context(
        home,
        lonely,
        sitemap=SitemapInfo(
            exists=True,
            status_code=200,
            url_count=8147,
            urls=["https://example.com/", "https://example.com/lonely/"],
        ),
    )
    ctx.links = build(ctx)
    assert ctx.links.orphans == ["https://example.com/lonely/"]
    assert not list(OrphanPagesCheck().run(ctx))


# ── тематична структура ────────────────────────────────────────────────────


def _article(slug: str, links: list[str]) -> object:
    anchors = "".join(f'<a href="{href}">x</a>' for href in links)
    html = (
        f"<html><head><title>Стаття про {slug} на сайті компанії</title></head>"
        f"<body><h1>{slug}</h1><p>Текст статті.</p>{anchors}</body></html>"
    )
    return page_from_html(html, url=f"https://example.com/blog/{slug}", depth=1)


def test_section_whose_pages_never_link_to_each_other_is_a_finding():
    ctx = context(
        _article("first", ["/", "/contacts/"]),
        _article("second", ["/", "/about/"]),
        _article("third", ["/"]),
    )
    issues = list(TopicIslandsCheck().run(ctx))
    assert len(issues) == 1
    assert issues[0].evidence["sibling_links"] == 0


def test_one_link_between_neighbours_is_enough_to_stay_silent():
    """Чек шукає відсутність звʼязків, а не їхню достатню кількість."""
    ctx = context(
        _article("first", ["/blog/second"]),
        _article("second", ["/"]),
        _article("third", ["/"]),
    )
    assert not list(TopicIslandsCheck().run(ctx))


def test_link_to_the_section_root_does_not_count_as_a_connection():
    """«Усі статті» є в кожному шаблоні й не свідчить ні про що."""
    ctx = context(
        _article("first", ["/blog"]),
        _article("second", ["/blog"]),
        _article("third", ["/blog"]),
    )
    assert list(TopicIslandsCheck().run(ctx))


def test_two_pages_are_not_enough_to_call_it_a_topic():
    ctx = context(_article("first", ["/"]), _article("second", ["/"]))
    assert not list(TopicIslandsCheck().run(ctx))


def test_pages_with_no_internal_links_at_all_are_a_different_problem():
    """Порожні посилання — це найчастіше рендер, і плутати не можна."""
    ctx = context(_article("first", []), _article("second", []), _article("third", []))
    assert not list(TopicIslandsCheck().run(ctx))


def test_contacts_and_about_are_not_expected_to_form_a_cluster():
    """Такі сторінки існують в однині — вимагати від них кластера безглуздо."""
    pages = [
        page_from_html(
            f"<html><head><title>Контакти офісу {n}</title></head>"
            f"<body><h1>Контакти</h1><a href='/'>x</a></body></html>",
            url=f"https://example.com/contacts/office-{n}",
            depth=1,
        )
        for n in range(3)
    ]
    assert not list(TopicIslandsCheck().run(context(*pages)))


# ── приклади посилань на закриті сторінки: той самий доказ на тих самих даних ──
#
# Граф складає пари (джерело, ціль), обходячи множину адрес, тож їхній порядок
# залежить від PYTHONHASHSEED. Приклади мусять бути однаковими в кожному
# запуску: перші п'ять із повністю впорядкованого переліку пар. Самі пари, їхні
# повтори, кількість, серйозність і бал від цього не змінюються.

# Навмисно перемішано: дві сторінки-джерела, Unicode, запит, фрагмент, регістр.
LINKS_TO_NOINDEX = [
    ("https://example.com/b/", "https://example.com/мова/"),
    ("https://example.com/", "https://example.com/zeta/"),
    ("https://example.com/b/", "https://example.com/a?b=2&a=1"),
    ("https://example.com/", "HTTPS://EXAMPLE.com/Upper/"),
    ("https://example.com/b/", "https://example.com/a#part"),
    ("https://example.com/b/", "https://example.com/%D0%BC%D0%BE%D0%B2%D0%B0/"),
    ("https://example.com/", "https://example.com/Über/"),
    ("https://example.com/b/", "https://example.com/zeta/"),
]

# Порядок — за джерелом, потім за ціллю, посимвольно (кодові точки), без жодного
# переписування адрес.
CANONICAL_FIVE = [
    "https://example.com/ → HTTPS://EXAMPLE.com/Upper/",
    "https://example.com/ → https://example.com/zeta/",
    "https://example.com/ → https://example.com/Über/",
    "https://example.com/b/ → https://example.com/%D0%BC%D0%BE%D0%B2%D0%B0/",
    "https://example.com/b/ → https://example.com/a#part",
]

HASH_SEEDS = ("0", "1", "7", "123")


def _with_links_to_noindex(pairs):
    from app.audit.link_graph import LinkGraph

    ctx = context(_page("https://example.com/", [], depth=0))
    ctx.links = LinkGraph(to_noindex=list(pairs))
    return ctx


def _evidence(ctx):
    return [(issue.params, issue.evidence) for issue in LinksToNoindexCheck().run(ctx)]


def test_links_to_noindex_shows_the_first_five_pairs_of_one_total_order():
    ((params, evidence),) = _evidence(_with_links_to_noindex(LINKS_TO_NOINDEX))

    assert evidence["examples"] == CANONICAL_FIVE
    assert params == {"count": 7}
    assert evidence["targets"] == [
        "HTTPS://EXAMPLE.com/Upper/",
        "https://example.com/%D0%BC%D0%BE%D0%B2%D0%B0/",
        "https://example.com/a#part",
        "https://example.com/a?b=2&a=1",
        "https://example.com/zeta/",
        "https://example.com/Über/",
        "https://example.com/мова/",
    ]


def test_links_to_noindex_evidence_does_not_depend_on_pair_order():
    orders = [
        LINKS_TO_NOINDEX,
        list(reversed(LINKS_TO_NOINDEX)),
        LINKS_TO_NOINDEX[3:] + LINKS_TO_NOINDEX[:3],
        sorted(LINKS_TO_NOINDEX, key=lambda pair: pair[1][::-1]),
    ]
    seen = [_evidence(_with_links_to_noindex(order)) for order in orders]

    assert all(result == seen[0] for result in seen)
    assert seen[0][0][1]["examples"] == CANONICAL_FIVE


def test_links_to_noindex_keeps_repeated_pairs_exactly_as_the_graph_reports_them():
    """Повтори вирішує граф, а не приклади: два варіанти адреси — дві пари."""
    home = _page("https://example.com/", ["/cabinet/", "/old-cabinet/", "/cabinet/"], depth=0)
    cabinet = _page("https://example.com/cabinet/", [], robots="noindex")
    cabinet.url_variants = ["https://example.com/old-cabinet/"]
    ctx = context(home, cabinet)
    ctx.links = build(ctx)

    assert ctx.links.to_noindex == [("https://example.com/", "https://example.com/cabinet/")] * 2
    ((params, evidence),) = _evidence(ctx)
    assert evidence["examples"] == ["https://example.com/ → https://example.com/cabinet/"] * 2
    assert evidence["targets"] == ["https://example.com/cabinet/"]
    assert params == {"count": 1}


def test_links_to_noindex_order_moves_no_status_count_or_score():
    from app.audit.enums import Effort, Module, Severity
    from app.audit.scoring import compute_scores

    results = []
    for order in (LINKS_TO_NOINDEX, list(reversed(LINKS_TO_NOINDEX))):
        issues = list(LinksToNoindexCheck().run(_with_links_to_noindex(order)))
        (issue,) = issues
        results.append((issue.code, issue.issue_key, issue.severity, issue.confidence, issue.weight,
                        issue.page_url, issue.params, compute_scores(issues)))

    assert results[0] == results[1]
    code, issue_key, severity, _, weight, page_url, params, (_, scores) = results[0]
    assert (code, issue_key, page_url, params) == ("seo.links_to_noindex", "seo.links_to_noindex", None,
                                                   {"count": 7})
    assert (severity, weight) == (Severity.LOW, 1)
    assert (LinksToNoindexCheck.module, LinksToNoindexCheck.effort) == (Module.SEO, Effort.LOW)
    assert scores[Module.SEO.value] == compute_scores(
        list(LinksToNoindexCheck().run(_with_links_to_noindex(LINKS_TO_NOINDEX)))
    )[1][Module.SEO.value]


def test_links_to_noindex_without_pairs_or_with_fewer_than_five():
    assert _evidence(_with_links_to_noindex([])) == []
    no_graph = context(_page("https://example.com/", [], depth=0))
    no_graph.links = None
    assert _evidence(no_graph) == []

    few = [LINKS_TO_NOINDEX[0], LINKS_TO_NOINDEX[3], LINKS_TO_NOINDEX[6]]
    ((params, evidence),) = _evidence(_with_links_to_noindex(few))
    assert evidence["examples"] == [
        "https://example.com/ → HTTPS://EXAMPLE.com/Upper/",
        "https://example.com/ → https://example.com/Über/",
        "https://example.com/b/ → https://example.com/мова/",
    ]
    assert params == {"count": 3}


def test_links_to_noindex_orders_unicode_queries_and_fragments_without_rewriting_them():
    ((_, evidence),) = _evidence(_with_links_to_noindex(LINKS_TO_NOINDEX))
    written = {f"{source} → {target}" for source, target in LINKS_TO_NOINDEX}

    assert set(evidence["examples"]) <= written, "кожен приклад — пара як є, без переписування"
    assert evidence["examples"] == sorted(evidence["examples"], key=lambda text: text.split(" → "))
    assert "https://example.com/ → https://example.com/Über/" in evidence["examples"]
    assert "https://example.com/b/ → https://example.com/a#part" in evidence["examples"]


def _seeded_site():
    """Дві сторінки ведуть на дванадцять закритих: вісімнадцять пар з графа."""
    targets = [f"/noindex-{n:02d}/" for n in range(12)]
    home = _page("https://example.com/", targets, depth=0)
    hub = _page("https://example.com/hub/", targets[:6])
    closed = [_page(f"https://example.com{target}", [], robots="noindex") for target in targets]
    ctx = context(home, hub, *closed)
    ctx.links = build(ctx)
    return ctx


def _seeded_site_evidence():
    return [{"params": issue.params, "evidence": issue.evidence}
            for issue in LinksToNoindexCheck().run(_seeded_site())]


_SEED_CHILD = (
    "import json, sys\n"
    "sys.meta_path = [f for f in sys.meta_path if '__editable__' not in "
    "(getattr(f, '__name__', '') or '') + (getattr(f, '__module__', '') or '')]\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import app\n"
    "from tests.test_link_graph import _seeded_site_evidence\n"
    "print(json.dumps({'app': app.__file__, 'evidence': _seeded_site_evidence()}))\n"
)


def test_links_to_noindex_evidence_is_identical_across_hash_seeds():
    """Кожне зерно — окремий інтерпретатор тієї самої гілки коду.

    Зміна PYTHONHASHSEED усередині працюючого процесу нічого не перевіряє:
    хеш рядків фіксується на старті інтерпретатора.
    """
    import json
    import os
    import subprocess
    import sys
    from pathlib import Path

    import app

    backend = str(Path(__file__).resolve().parents[1])
    outputs = {}
    for seed in HASH_SEEDS:
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONDONTWRITEBYTECODE": "1"}
        done = subprocess.run([sys.executable, "-c", _SEED_CHILD, backend], cwd=backend, env=env,
                              capture_output=True, text=True, timeout=180)
        assert done.returncode == 0, done.stderr
        outputs[seed] = done.stdout.strip().splitlines()[-1]

    parsed = {seed: json.loads(line) for seed, line in outputs.items()}
    parent = os.path.normcase(os.path.realpath(app.__file__))
    children = {os.path.normcase(os.path.realpath(result["app"])) for result in parsed.values()}
    assert children == {parent}, "дочірні процеси — та сама гілка"
    assert len(set(outputs.values())) == 1, outputs
    (result,) = parsed["0"]["evidence"]
    assert result["evidence"]["examples"] == [
        f"https://example.com/ → https://example.com/noindex-{n:02d}/" for n in range(5)
    ]
    assert result["params"] == {"count": 12}
    assert parsed["0"]["evidence"] == _seeded_site_evidence()
