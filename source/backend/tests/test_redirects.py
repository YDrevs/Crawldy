"""Ланцюги перенаправлень: що з них видно й чого казати не можна.

Дані для цих випадків проходять справжній шлях — `FetchResult` із
`RedirectHop` через `extract()` у `PageSignals`, — а не підставляються
готовими в чек. Саме на цьому шляху й ховались обидві дрібниці, які
зіпсували б висновки: `Location` буває відносним, а `/a` і `/a/` — це
нуль переходів, а не один.
"""

from __future__ import annotations

import json

import pytest

from app.audit import redirects, snapshot
from app.audit.checks.seo import (
    RedirectChainCheck,
    RedirectLoopCheck,
    RedirectTargetCheck,
)
from app.audit.extractor import extract
from app.audit.fetcher import FetchResult, RedirectHop
from tests.factories import context, page_from_html

SITE = "https://example.com"
HTML = (
    "<html lang='en'><head><title>Page</title></head>"
    "<body><h1>Heading</h1><p>Some words here.</p></body></html>"
)


def fetched(requested: str, hops: list[tuple[int, str]], final: str, status: int = 200):
    """FetchResult так, як його будує справжній fetcher."""
    return FetchResult(
        url=requested,
        final_url=final,
        status_code=status,
        content_type="text/html",
        text=HTML,
        body_bytes=len(HTML),
        elapsed_ms=30,
        headers={},
        redirects=tuple(RedirectHop(status_code=c, url=u) for c, u in hops),
    )


def page(requested: str, hops: list[tuple[int, str]], final: str, status: int = 200):
    return extract(fetched(requested, hops, final, status), origin=SITE)


def issues(check_cls, ctx):
    return list(check_cls().run(ctx))


# ── 1–4. Ланцюг ───────────────────────────────────────────────────────────


def test_a_page_without_redirects_says_nothing():
    """1. Пряма відповідь — не привід для знахідки."""
    ctx = context(page_from_html(HTML))
    assert issues(RedirectChainCheck, ctx) == []
    assert issues(RedirectLoopCheck, ctx) == []
    assert issues(RedirectTargetCheck, ctx) == []


def test_a_single_legitimate_redirect_is_not_a_chain():
    """2. `http → https` правильний, і лаяти за нього нема за що."""
    ctx = context(page("http://example.com/", [(301, f"{SITE}/")], f"{SITE}/"))
    assert issues(RedirectChainCheck, ctx) == []


def test_two_hops_are_reported():
    """3. Два переходи — це вже нашарування правил."""
    p = page(f"{SITE}/old", [(301, f"{SITE}/mid"), (302, f"{SITE}/new")], f"{SITE}/new")
    found = issues(RedirectChainCheck, context(p))
    assert len(found) == 1
    assert found[0].evidence["redirects"] == 2


def test_a_longer_chain_counts_and_records_every_hop():
    """4. Кількість і послідовність мають збігатися з тим, що було."""
    hops = [(301, f"{SITE}/b"), (301, f"{SITE}/c"), (302, f"{SITE}/d")]
    p = page(f"{SITE}/a", hops, f"{SITE}/d")
    evidence = issues(RedirectChainCheck, context(p))[0].evidence
    assert evidence["redirects"] == 3
    assert [h["status"] for h in evidence["hops"]] == [301, 301, 302]
    assert [h["url"] for h in evidence["hops"]] == [f"{SITE}/b", f"{SITE}/c", f"{SITE}/d"]


# ── 5–6. Петля проти межі ─────────────────────────────────────────────────


def test_a_repeated_address_in_a_finished_path_is_reported_as_repetition():
    """5. `A → B → A → …`: обидва входження ми бачили на власні очі."""
    hops = [(302, f"{SITE}/b"), (302, f"{SITE}/a"), (302, f"{SITE}/end")]
    p = page(f"{SITE}/a", hops, f"{SITE}/end")
    found = [i for i in issues(RedirectLoopCheck, context(p))
             if i.issue_key.endswith("repeated")]
    assert found and f"{SITE}/a" in found[0].evidence["repeated"]


def test_exceeding_the_redirect_limit_is_not_called_a_loop():
    """6. Найважливіша межа цієї роботи.

    httpx кидає `TooManyRedirects` і не віддає історії: ми не бачили ні
    де крутилося, ні чи крутилося взагалі. Тому твердження вужче — «до
    кінця не дійшли», — і воно не має ані слова про петлю.
    """
    ctx = context(page_from_html(HTML))
    ctx.redirect_limited = [f"{SITE}/spins"]
    found = issues(RedirectLoopCheck, ctx)
    assert len(found) == 1
    assert found[0].issue_key.endswith("limit")
    assert found[0].evidence["chain_available"] is False
    for field in (found[0].title, found[0].description):
        assert "loop" not in field.lower()


# ── 7–9. Призначення ──────────────────────────────────────────────────────


def test_a_redirect_ending_in_404_is_reported():
    """7. Правило працює, сторінки немає."""
    p = page(f"{SITE}/gone", [(301, f"{SITE}/missing")], f"{SITE}/missing", status=404)
    found = issues(RedirectTargetCheck, context(p))
    assert found and found[0].evidence["final_status"] == 404


def test_a_redirect_ending_in_5xx_is_reported():
    """8. Те саме твердження, інший код у доказі."""
    p = page(f"{SITE}/x", [(302, f"{SITE}/broken")], f"{SITE}/broken", status=503)
    found = issues(RedirectTargetCheck, context(p))
    assert found and found[0].evidence["final_status"] == 503


def test_a_page_that_answered_normally_is_not_a_target_problem():
    """9. Пара до двох попередніх."""
    p = page(f"{SITE}/old", [(301, f"{SITE}/new")], f"{SITE}/new")
    assert issues(RedirectTargetCheck, context(p)) == []


# ── 10–11. Нормалізація ───────────────────────────────────────────────────


def test_a_relative_location_is_resolved_against_the_previous_hop():
    """10. httpbin віддає саме так, і це не виняток.

    Ми зберігаємо значення заголовка `Location`, а воно буває відносним.
    Без покрокового розвʼязання доказ показував би шлях без домену.
    """
    hops = [(302, "/relative/2"), (302, "/relative/1"), (302, "/done")]
    p = page(f"{SITE}/start", hops, f"{SITE}/done")
    chain = redirects.chain_of(p)
    assert [h.url for h in chain.hops] == [
        f"{SITE}/relative/2",
        f"{SITE}/relative/1",
        f"{SITE}/done",
    ]


def test_equivalent_addresses_do_not_invent_chain_length():
    """11. `/a` → `/a/` — нуль змістовних переходів, а не один.

    Рахувати сирі стрибки означало б вигадати клієнтові складність,
    якої в нього немає, і надіслати його правити те, що не зламане.
    """
    p = page(f"{SITE}/a", [(301, f"{SITE}/a/"), (301, f"{SITE}/a?utm_source=x")], f"{SITE}/a")
    assert redirects.chain_of(p).length == 0
    assert issues(RedirectChainCheck, context(p)) == []


# ── 12–13. Доказ ──────────────────────────────────────────────────────────


def test_a_page_linking_to_the_redirecting_address_is_named():
    """12. Саме тут лежить дія: виправити посилання, а не правило.

    Береться з уже зібраних `page.links` — того самого джерела, що й
    граф. Другого графа заради цього не заводимо.
    """
    linking = page_from_html(
        f'<html lang="en"><head><title>T</title></head><body><h1>H</h1>'
        f'<a href="{SITE}/old">go</a><p>text</p></body></html>',
        url=f"{SITE}/hub",
    )
    target = page(f"{SITE}/old", [(301, f"{SITE}/mid"), (302, f"{SITE}/new")], f"{SITE}/new")
    found = issues(RedirectChainCheck, context(linking, target))
    assert found[0].evidence["linked_from"] == [f"{SITE}/hub"]


def test_the_evidence_keeps_the_whole_path_not_only_the_destination():
    """13. Кінцева адреса без шляху не дає чого виправляти."""
    hops = [(301, f"{SITE}/b"), (302, f"{SITE}/c")]
    p = page(f"{SITE}/a", hops, f"{SITE}/c")
    evidence = issues(RedirectChainCheck, context(p))[0].evidence
    assert evidence["source"] == f"{SITE}/a"
    assert evidence["final_url"] == f"{SITE}/c"
    assert len(evidence["hops"]) == 2
    assert evidence["path"] == [f"{SITE}/a", f"{SITE}/b", f"{SITE}/c"]


# ── 14–15. Знімки ─────────────────────────────────────────────────────────


def test_a_snapshot_round_trip_keeps_the_chain_and_its_type():
    """14. Перерахунок має давати той самий висновок.

    Тип теж: JSON не знає кортежів, і ланцюг повертався списками списків
    при оголошеному `tuple[tuple[int, str], ...]`.
    """
    p = page(f"{SITE}/a", [(301, f"{SITE}/b"), (302, f"{SITE}/c")], f"{SITE}/c")
    ctx = context(p)
    ctx.redirect_limited = [f"{SITE}/spins"]
    back = snapshot.load(json.loads(json.dumps(snapshot.dump(ctx))))

    assert back.pages[0].redirect_chain == ((301, f"{SITE}/b"), (302, f"{SITE}/c"))
    assert isinstance(back.pages[0].redirect_chain, tuple)
    assert back.redirect_limited == [f"{SITE}/spins"]
    assert [i.title for i in issues(RedirectChainCheck, back)] == [
        i.title for i in issues(RedirectChainCheck, ctx)
    ]


def test_an_old_snapshot_reports_no_redirects_rather_than_failing():
    """15. Знімок, старший за цю роботу, лишається читаним.

    Порожній ланцюг там означає «перенаправлень не бачили» — і це
    правда: поле збиралося задовго до чеків. А ось `redirect_limited`
    порожній тому, що його не існувало, тож мовчання про межу — це
    «не записували», а не «межі не було».
    """
    import pathlib

    old = next(pathlib.Path("benchmark/snapshots").glob("*.json"))
    ctx = snapshot.load(json.loads(old.read_text(encoding="utf-8")))
    assert ctx.pages
    assert ctx.redirect_limited == []
    for check in (RedirectChainCheck, RedirectLoopCheck, RedirectTargetCheck):
        list(check().run(ctx))


# ── 16–19. Поверхні, мова, скоринг ────────────────────────────────────────


@pytest.mark.parametrize("code", ["en", "uk", "de", "es", "fr", "ru"])
def test_every_locale_has_all_four_messages(code):
    """16. Жодного тихого відкоту в англійську."""
    from app.audit.i18n import CATALOGS, Locale

    catalog = CATALOGS[Locale(code)]
    for key in (
        "seo.redirect_chain",
        "seo.redirect_loop.repeated",
        "seo.redirect_loop.limit",
        "seo.redirect_target",
    ):
        assert key in catalog, f"{code}: бракує {key}"
        for field in ("title", "description", "recommendation", "consequence"):
            assert catalog[key][field].strip()


def test_the_finding_reaches_the_report_with_its_evidence():
    """17. Доказ мусить пережити шлях до звіту, а не лишитись у чеку."""
    from app.audit import i18n as audit_i18n
    from app.audit.orchestrator import rescore
    from app.report.builder import build_report
    from app.report.source import source_from_outcome

    hub = page_from_html(
        f'<html lang="en"><head><title>T</title></head><body><h1>H</h1>'
        f'<a href="{SITE}/old">go</a><p>words words words</p></body></html>',
        url=f"{SITE}/hub",
    )
    target = page(f"{SITE}/old", [(301, f"{SITE}/mid"), (302, f"{SITE}/new")], f"{SITE}/new")
    doc = build_report(
        source_from_outcome(rescore(context(hub, target))), audit_i18n.Locale("uk")
    )
    hits = [r for r in doc.recommendations if r.issue_key.startswith("seo.redirect")]
    assert hits
    assert hits[0].evidence["redirects"] == 2
    assert hits[0].action and hits[0].consequence


def test_no_wording_promises_a_ranking_penalty():
    """18. Google цього не стверджує, і ми не міряли.

    Захищати можна лише видиме: зайвий запит, довше очікування,
    сторінка, якої не отримати.
    """
    from app.audit.i18n import CATALOGS

    banned = (
        "ranking", "rank ", "penalty", "penalis", "penaliz",
        "позиці", "штраф", "ранжув", "Rangfolge", "Platzierung", "sanción",
        "posicionamiento", "classement", "pénalit",
    )
    offenders = [
        f"{locale}/{key}: {word}"
        for locale, catalog in CATALOGS.items()
        for key, entry in catalog.items()
        if key.startswith("seo.redirect")
        for field, text in entry.items()
        for word in banned
        if word.lower() in text.lower()
    ]
    assert not offenders, offenders


def test_the_new_capability_moves_no_score_on_the_frozen_corpus():
    """19. Здатність бачити більше не має рухати бали, зняті раніше."""
    import pathlib

    from app.audit import scoring
    from app.audit.checks import all_checks

    moved = []
    for f in sorted(pathlib.Path("benchmark/snapshots").glob("*.json")):
        ctx = snapshot.load(json.loads(f.read_text(encoding="utf-8")))
        every = [i for c in all_checks() for i in c.run(ctx)]
        without = [i for i in every if not i.code.startswith("seo.redirect")]
        if scoring.overall_raw(every, set()) != scoring.overall_raw(without, set()):
            moved.append(f.stem)
    assert not moved, moved
