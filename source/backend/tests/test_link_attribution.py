"""Хто саме веде на зламану адресу — і де закінчується право це стверджувати.

Спостереження будуються справжнім `extract()` із розмітки, а не
підставляються готовими: питання ж саме в тому, чи доживає текст
посилання й ознака «лише після рендеру» від HTML до доказу.

Дві межі тут головні. Ціль, до якої краул не дійшов, зламаною не
називається ніколи. І одна зламана адреса, на яку ведуть чотирнадцять
посилань, лишається однією знахідкою, а не чотирнадцятьма.
"""

from __future__ import annotations

import json

import pytest

from app.audit import link_evidence, snapshot
from app.audit.checks.seo import BrokenInternalLinksCheck
from app.audit.extractor import extract, signals_from_html
from app.audit.fetcher import FetchResult, RedirectHop
from app.audit.link_evidence import Seen, TargetState
from app.audit.types import RenderResult
from tests.factories import context

SITE = "https://example.com"


def html(links: list[tuple[str, str]] | None = None, *, title: str = "Page") -> str:
    body = "".join(f'<a href="{href}">{anchor}</a>' for href, anchor in links or [])
    return (
        f"<html lang='en'><head><title>{title}</title></head>"
        f"<body><h1>{title}</h1>{body}<p>Some words here.</p></body></html>"
    )


def page(url: str, links: list[tuple[str, str]] | None = None, *, status: int = 200,
         hops: list[tuple[int, str]] | None = None, requested: str | None = None):
    body = html(links)
    return extract(
        FetchResult(
            url=requested or url, final_url=url, status_code=status,
            content_type="text/html", text=body, body_bytes=len(body), elapsed_ms=15,
            headers={},
            redirects=tuple(RedirectHop(status_code=c, url=u) for c, u in (hops or [])),
        ),
        origin=SITE,
    )


def rendered(ctx, url: str, links: list[tuple[str, str]]):
    """Домальовує сторінці відрендерену версію з іншим набором посилань."""
    body = html(links)
    result = RenderResult(url=url, rendered=True, html=body)
    result.signals = signals_from_html(url, body, origin=SITE, depth=0)
    ctx.renders[url] = result
    return ctx


def finding(ctx):
    found = list(BrokenInternalLinksCheck().run(ctx))
    return found[0] if found else None


def destination(ctx, url: str):
    return link_evidence.collect(ctx).get(url.rstrip("/"))


# ── 1–6. Підтверджені поламки й атрибуція ─────────────────────────────────


def test_a_healthy_link_produces_no_attribution():
    """1. Робоче посилання — не привід ні для чого."""
    ctx = context(page(f"{SITE}/", [(f"{SITE}/a", "About")]), page(f"{SITE}/a"))
    assert link_evidence.broken(ctx) == []
    assert finding(ctx) is None


def test_one_page_linking_to_one_404_names_the_page_and_anchor():
    """2. Найпростіший випадок — і саме те, чого раніше не було в доказі."""
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "Our prices")]),
        page(f"{SITE}/gone", status=404),
    )
    dest = link_evidence.broken(ctx)[0]
    assert dest.state is TargetState.CLIENT_ERROR and dest.status == 404
    assert dest.sources == (f"{SITE}/",)
    assert dest.observations[0].anchor == "Our prices"


def test_several_pages_linking_to_the_same_404_are_grouped():
    """3. Одна ціль — одна знахідка, скільки б сторінок на неї не вело."""
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "Prices")]),
        page(f"{SITE}/a", [(f"{SITE}/gone", "Prices")]),
        page(f"{SITE}/b", [(f"{SITE}/gone", "See prices")]),
        page(f"{SITE}/gone", status=404),
    )
    dest = link_evidence.broken(ctx)[0]
    assert len(dest.sources) == 3 and dest.links == 3
    assert len(list(BrokenInternalLinksCheck().run(ctx))) == 1


def test_the_same_broken_link_twice_on_one_page_is_one_observation():
    """4. Два однакові `<a>` на сторінці — одне посилання цієї сторінки.

    Дублювати ціль через повтор у розмітці означало б рахувати верстку,
    а не сайт.
    """
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "Prices"), (f"{SITE}/gone", "Prices again")]),
        page(f"{SITE}/gone", status=404),
    )
    dest = link_evidence.broken(ctx)[0]
    assert dest.links == 1 and dest.sources == (f"{SITE}/",)


def test_several_broken_destinations_from_one_page():
    """5. Дві мертві цілі — дві цілі в доказі, одна знахідка."""
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/x", "X"), (f"{SITE}/y", "Y")]),
        page(f"{SITE}/x", status=404),
        page(f"{SITE}/y", status=410),
    )
    assert len(link_evidence.broken(ctx)) == 2
    assert finding(ctx).evidence["destinations_total"] == 2


def test_a_confirmed_5xx_is_reported_as_a_server_error():
    """6. Той самий доказ, інший стан — і він у доказі названий."""
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/down", "Status")]),
        page(f"{SITE}/down", status=503),
    )
    assert link_evidence.broken(ctx)[0].state is TargetState.SERVER_ERROR


def test_a_redirect_that_ends_in_an_error_is_named_as_such():
    """7. `сторінка → редирект → помилка` — не те саме, що прямий 404.

    Ланцюг береться готовий; клієнтові важливо знати, що правити треба
    не тільки посилання, а й саме перенаправлення.
    """
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/old", "Old page")]),
        page(f"{SITE}/new", status=404, requested=f"{SITE}/old",
             hops=[(301, f"{SITE}/new")]),
    )
    dest = link_evidence.broken(ctx)[0]
    assert dest.state is TargetState.REDIRECT_TO_ERROR
    assert dest.detail["final_url"] == f"{SITE}/new"


# ── 8–10. Невизначеність не стає поламкою ─────────────────────────────────


def test_a_destination_we_never_crawled_is_not_called_broken():
    """8. Найважливіша межа: не перевіряли ≠ зламано."""
    ctx = context(page(f"{SITE}/", [(f"{SITE}/unvisited", "Somewhere")]))
    dest = destination(ctx, f"{SITE}/unvisited")
    assert dest.state is TargetState.NOT_CHECKED and not dest.broken
    assert link_evidence.broken(ctx) == []


def test_a_robots_blocked_destination_is_unverified_not_broken():
    """9. Ми свідомо не пішли — це не доказ, що там порожньо."""
    from app.audit import robots as robots_rfc
    from app.audit.types import RobotsInfo

    info = RobotsInfo(exists=True, status_code=200,
                      content="User-agent: *\nDisallow: /private\n")
    info.parsed = robots_rfc.parse(info.content)
    ctx = context(page(f"{SITE}/", [(f"{SITE}/private/x", "Members")]), robots=info)
    dest = destination(ctx, f"{SITE}/private/x")
    assert dest.state is TargetState.BLOCKED and not dest.broken


def test_a_transport_failure_is_not_a_confirmed_site_fault():
    """10. Обрив звʼязку може бути нашим боком, а не їхнім."""
    ctx = context(page(f"{SITE}/", [(f"{SITE}/flaky", "Try")]))
    ctx.failed_urls = {f"{SITE}/flaky": "ConnectTimeout: timed out"}
    dest = destination(ctx, f"{SITE}/flaky")
    assert dest.state is TargetState.FETCH_FAILED and not dest.broken


# ── 11–14. Походження, нормалізація, зовнішні ─────────────────────────────


def test_a_link_only_in_the_response_is_marked_response():
    """11. Рендеру не було — усе, що ми маємо, це відповідь сервера."""
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "Prices")]),
        page(f"{SITE}/gone", status=404),
    )
    assert link_evidence.broken(ctx)[0].observations[0].seen_in is Seen.RESPONSE


def test_a_link_added_by_scripts_is_attributed_to_the_render():
    """12. Посилання, якого у відповіді не було, теж треба полагодити."""
    ctx = context(page(f"{SITE}/"), page(f"{SITE}/gone", status=404))
    rendered(ctx, f"{SITE}/", [(f"{SITE}/gone", "Buy now")])
    dest = link_evidence.broken(ctx)[0]
    assert dest.observations[0].seen_in is Seen.RENDER
    assert dest.observations[0].anchor == "Buy now"


def test_a_link_in_both_versions_is_counted_once():
    """13. Те саме посилання у відповіді й у DOM — одне посилання."""
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "Prices")]),
        page(f"{SITE}/gone", status=404),
    )
    rendered(ctx, f"{SITE}/", [(f"{SITE}/gone", "Prices")])
    dest = link_evidence.broken(ctx)[0]
    assert dest.links == 1
    assert dest.observations[0].seen_in is Seen.BOTH


def test_equivalent_destination_spellings_merge():
    """14. `/gone` і `/gone/` — одна ціль, а не дві зламані адреси."""
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "A"), (f"{SITE}/gone/", "B")]),
        page(f"{SITE}/a", [(f"{SITE}/gone?utm_source=x", "C")]),
        page(f"{SITE}/gone", status=404),
    )
    found = link_evidence.broken(ctx)
    assert len(found) == 1 and found[0].links == 2


def test_an_external_broken_url_is_out_of_scope_here():
    """15. Це задача про внутрішні посилання, і межа береться наявна."""
    ctx = context(
        page(f"{SITE}/", [("https://elsewhere.test/gone", "Partner")]),
        page(f"{SITE}/gone", status=404),
    )
    assert all("elsewhere.test" not in d.key for d in link_evidence.collect(ctx).values())


# ── 16–18. Текст посилання як факт, без оцінки ────────────────────────────


def test_anchor_text_is_preserved_verbatim():
    """16. Наступний пункт дорожньої карти працюватиме саме з ним."""
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "Download the 2026 price list")]),
        page(f"{SITE}/gone", status=404),
    )
    assert link_evidence.broken(ctx)[0].observations[0].anchor == (
        "Download the 2026 price list"
    )


def test_an_empty_anchor_is_recorded_without_judgment():
    """17. Порожній текст — факт, а не зауваження.

    Оцінка якості тексту належить пункту #9; тут вона була б чужою
    роботою, зробленою наполовину.
    """
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "")]),
        page(f"{SITE}/gone", status=404),
    )
    observation = link_evidence.broken(ctx)[0].observations[0]
    assert observation.anchor == ""
    issue = finding(ctx)
    for field in (issue.title, issue.description, issue.recommendation):
        assert "anchor" not in field.lower() or "anchor text" in field.lower()


def test_attribution_agrees_with_the_link_graph():
    """18. Звіт не сміє казати «A веде на B», якщо граф каже інакше."""
    from app.audit.link_graph import build

    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "X")]),
        page(f"{SITE}/a", [(f"{SITE}/gone", "X")]),
        page(f"{SITE}/gone", status=404),
    )
    graph = build(ctx)
    dest = link_evidence.broken(ctx)[0]
    assert graph.incoming.get(dest.key) == len(dest.sources)


# ── 19–24. Доказ, знімки, мова, скоринг ───────────────────────────────────


def test_bounded_display_keeps_honest_totals():
    """19. Урізаний перелік не має вдавати повний."""
    sources = [
        page(f"{SITE}/p{i}", [(f"{SITE}/gone", f"Link {i}")]) for i in range(12)
    ]
    ctx = context(*sources, page(f"{SITE}/gone", status=404))
    dest = link_evidence.broken(ctx)[0]
    evidence = dest.as_evidence(limit=5)
    assert evidence["links"] == 12 and evidence["source_pages"] == 12
    assert evidence["examples_shown"] == 5
    assert evidence["examples_truncated"] is True


def test_the_displayed_order_is_deterministic():
    """20. Два прогони мусять давати той самий доказ."""
    sources = [page(f"{SITE}/p{i}", [(f"{SITE}/gone", f"L{i}")]) for i in range(9)]
    ctx = context(*sources, page(f"{SITE}/gone", status=404))
    first = link_evidence.broken(ctx)[0].as_evidence()
    second = link_evidence.broken(ctx)[0].as_evidence()
    assert first == second


def test_a_snapshot_round_trip_reproduces_attribution():
    """21. Перерахунок без мережі має давати ті самі джерела."""
    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "Prices")]),
        page(f"{SITE}/gone", status=404),
    )
    back = snapshot.load(json.loads(json.dumps(snapshot.dump(ctx))))
    assert link_evidence.broken(back)[0].observations[0].anchor == "Prices"
    assert finding(back).evidence["source_pages"] == 1


def test_old_snapshots_stay_readable_and_do_not_invent_sources():
    """22. Знімок без збережених посилань не вигадує атрибуцію."""
    import pathlib

    for path in sorted(pathlib.Path("benchmark/snapshots").glob("*.json"))[:6]:
        ctx = snapshot.load(json.loads(path.read_text(encoding="utf-8")))
        issue = finding(ctx)
        if issue is None:
            continue
        for dest in issue.evidence["destinations"]:
            assert dest["links"] == len(dest["examples"]) or dest.get("examples_truncated")


@pytest.mark.parametrize("code", ["en", "uk", "de", "es", "fr", "ru"])
def test_every_locale_explains_the_attribution(code):
    """23. Жодного тихого відкоту в англійську й жодного порожнього опису."""
    from app.audit.i18n import CATALOGS, Locale

    entry = CATALOGS[Locale(code)]["seo.broken_links"]
    for field in ("title", "description", "recommendation", "consequence"):
        assert entry[field].strip(), f"{code}: порожнє {field}"


def test_no_wording_claims_a_ranking_penalty():
    """24. Ми не міряли впливу на позиції — отже, не стверджуємо його."""
    from app.audit.i18n import CATALOGS

    banned = ("ranking", "rank ", "penalty", "penalis", "penaliz",
              "позиці", "штраф", "ранжув", "Rangfolge", "posicionamiento",
              "classement", "ранжир")
    offenders = [
        f"{locale}/{word}"
        for locale, catalog in CATALOGS.items()
        for word in banned
        for text in catalog["seo.broken_links"].values()
        if word.lower() in text.lower()
    ]
    assert not offenders, offenders


def test_attribution_adds_no_penalty_of_its_own():
    """25. Це збагачення наявного критерію, а не другий критерій.

    Атрибуція мусить лишити і кількість знахідок, і штраф тими самими:
    інакше сайти, зняті до неї, стали б непорівнянні.
    """
    import pathlib

    from app.audit import scoring

    for path in sorted(pathlib.Path("benchmark/snapshots").glob("*.json")):
        ctx = snapshot.load(json.loads(path.read_text(encoding="utf-8")))
        issues = [i for i in BrokenInternalLinksCheck().run(ctx)]
        assert len(issues) <= 1, path.stem
        for issue in issues:
            assert scoring.penalty(issue) == 9


def test_nested_evidence_renders_readably_in_word():
    """26. Доказ атрибуції вкладений, а Word не вміє читати `repr`.

    Раніше форматер віддавав список словників через `str(v)`, і в
    документ їхав сирий Python-словник із лапками й `False`. Дані —
    адреси й текст посилань — не перекладаються; підписи навколо них
    приходять із каталогу.
    """
    from app.report.docx import _format_evidence

    ctx = context(
        page(f"{SITE}/", [(f"{SITE}/gone", "Prices")]),
        page(f"{SITE}/a", [(f"{SITE}/gone", "Prices")]),
        page(f"{SITE}/gone", status=404),
    )
    text = _format_evidence(finding(ctx).evidence)
    assert "{'" not in text and "False" not in text
    assert f"{SITE}/gone" in text
    assert "source_pages=2" in text


def test_a_long_evidence_list_is_bounded_but_counted():
    """27. Показуємо три, рахуємо всі — і кажемо, скільки сховано."""
    from app.report.docx import _short

    items = [{"from": f"{SITE}/p{i}", "anchor": f"L{i}"} for i in range(9)]
    text = _short(items)
    assert text.count("|") == 2
    assert "(+6)" in text
