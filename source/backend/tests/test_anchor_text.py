"""Текст внутрішніх посилань: що ми з нього беремо й чого не стверджуємо.

Розмітка проходить справжній `extract()`, а спостереження — справжній
`link_evidence`. Другого представлення «звідки → куди → яким текстом» у
продукті немає, і тест ходить тим самим шляхом, що продукт.

Найважливіші випадки тут — не спрацювання, а мовчання: меню, невідома
мова, англійський перелік на чужій мові й осмислений короткий підпис.
"""

from __future__ import annotations

import json

import pytest

from app.audit import anchor_text, snapshot
from app.audit.checks.seo import AnchorTextCheck
from app.audit.extractor import extract, signals_from_html
from app.audit.fetcher import FetchResult
from app.audit.link_evidence import Seen
from app.audit.types import RenderResult
from tests.factories import context

SITE = "https://example.com"


def page(url: str, body: str = "", *, lang: str = "en", title: str = "Page"):
    html = (
        f"<html lang='{lang}'><head><title>{title}</title></head>"
        f"<body><h1>{title}</h1>{body}<p>Some words on the page.</p></body></html>"
    )
    return extract(
        FetchResult(url=url, final_url=url, status_code=200, content_type="text/html",
                    text=html, body_bytes=len(html), elapsed_ms=10, headers={}),
        origin=SITE,
    )


def a(href: str, text: str) -> str:
    return f'<a href="{href}">{text}</a>'


def targets(*paths: str):
    return [page(f"{SITE}{p}", title=p.strip('/') or 'Home') for p in paths]


def weak_of(ctx):
    return anchor_text.analyse(ctx).weak


def finding(ctx):
    found = list(AnchorTextCheck().run(ctx))
    return found[0] if found else None


# ── 1–5. Що вважається текстом посилання ──────────────────────────────────


def test_a_descriptive_contextual_anchor_is_not_a_finding():
    """1. Осмислений підпис — не привід ні для чого."""
    ctx = context(page(f"{SITE}/", a("/prices", "See our 2026 price list")),
                  *targets("/prices"))
    assert weak_of(ctx) == []
    assert finding(ctx) is None


def test_a_short_but_meaningful_anchor_is_not_generic():
    """2. Короткий ≠ беззмістовний. «Ціни» називають ціль точно."""
    ctx = context(page(f"{SITE}/", a("/prices", "Pricing") + a("/ship", "Delivery")),
                  *targets("/prices", "/ship"))
    assert weak_of(ctx) == []


def test_an_image_link_with_meaningful_alt_is_not_empty():
    """3. Google каже прямо: `alt` картинки і є текстом посилання.

    Без цього кожне логотипне й карткове посилання виглядало б порожнім.
    """
    ctx = context(page(f"{SITE}/", '<a href="/cat"><img src=x alt="Our catalogue"></a>'),
                  *targets("/cat"))
    link = next(link for link in ctx.ok_pages[0].links if link.url.endswith("/cat"))
    assert link.anchor == "" and link.image_alt == "Our catalogue"
    assert weak_of(ctx) == []


def test_an_icon_link_with_an_accessible_label_is_not_empty():
    """4. `aria-label` — теж назва посилання, і карати за неї безглуздо."""
    ctx = context(page(f"{SITE}/", '<a href="/menu" aria-label="Open menu"><svg></svg></a>'),
                  *targets("/menu"))
    link = next(link for link in ctx.ok_pages[0].links if link.url.endswith("/menu"))
    assert link.label == "Open menu"
    assert weak_of(ctx) == []


def test_whitespace_only_anchor_normalizes_to_empty():
    """5. `clean()` згортає пробіли, тож «   » і «» — те саме."""
    ctx = context(page(f"{SITE}/", a("/x", "   ")), *targets("/x"))
    link = next(link for link in ctx.ok_pages[0].links if link.url.endswith("/x"))
    assert link.anchor == ""
    # Знахідкою це не стає: клас «порожній текст» не спричиняє чека.
    assert weak_of(ctx) == []


def test_links_without_any_text_are_counted_but_never_claimed():
    """6. Найважливіше рішення цієї роботи, і воно про нашу сліпоту.

    `_extract_links` лишає перше посилання на адресу, а в картці першим
    стоїть зображення без `alt`; текст із сусіднього `<a>` до нас не
    доходить. На вибірці це давало 524 «порожніх» на одному сайті. Тому
    число лишається в покритті, а знахідки з нього немає.
    """
    card = '<a href="/p"><img src=x></a><h3><a href="/p">Moon cake</a></h3>'
    ctx = context(page(f"{SITE}/", card), *targets("/p"))
    analysis = anchor_text.analyse(ctx)
    assert analysis.unnamed == 1
    assert analysis.weak == []
    assert analysis.coverage()["links_without_any_text"] == 1


# ── 7–10. Загальні фрази ──────────────────────────────────────────────────


@pytest.mark.parametrize("text", ["Click here", "Read more", "Learn more", "here"])
def test_documented_generic_phrases_are_detected(text):
    """7. Саме ці приклади наводить документація Google."""
    ctx = context(page(f"{SITE}/", a("/a", text) + a("/b", text)), *targets("/a", "/b"))
    assert [w.reason for w in weak_of(ctx)] == [anchor_text.Reason.GENERIC] * 2


def test_one_generic_link_to_one_page_is_not_reported():
    """8. Двозначність зʼявляється лише з другою ціллю.

    Одне «читати далі» на одну сторінку — питання стилю, і знахідка про
    нього була б причіпкою.
    """
    ctx = context(page(f"{SITE}/", a("/a", "Read more")), *targets("/a"))
    assert weak_of(ctx)
    assert finding(ctx) is None


def test_the_same_phrase_across_destinations_is_grouped_once():
    """9. Одна фраза — одна робота, а не сорок робіт на сорок посилань."""
    body = "".join(a(f"/p{i}", "Learn more") for i in range(5))
    ctx = context(page(f"{SITE}/", body), *targets(*(f"/p{i}" for i in range(5))))
    issue = finding(ctx)
    phrases = issue.evidence["phrases"]
    assert len(phrases) == 1
    assert phrases[0]["anchor"] == "learn more"
    assert phrases[0]["links"] == 5 and phrases[0]["destinations"] == 5


def test_a_repeated_navigation_label_makes_no_noise():
    """10. «Ціни» в шапці — орієнтир, а не дефект.

    Меню є на кожній сторінці; знахідка про нього була б шумом всюди.
    """
    nav = f'<nav>{a("/prices", "Learn more")}{a("/about", "Learn more")}</nav>'
    ctx = context(page(f"{SITE}/", nav), *targets("/prices", "/about"))
    analysis = anchor_text.analyse(ctx)
    assert analysis.weak == [] and analysis.in_chrome == 2
    assert finding(ctx) is None


# ── 11–14. Мова ───────────────────────────────────────────────────────────


def test_a_ukrainian_generic_phrase_is_detected_on_a_ukrainian_page():
    """11. Перелік свій для кожної мови, і український працює."""
    body = a("/a", "Детальніше") + a("/b", "Детальніше")
    ctx = context(page(f"{SITE}/", body, lang="uk"), *targets("/a", "/b"))
    assert len(weak_of(ctx)) == 2
    assert weak_of(ctx)[0].language == "uk"


def test_an_english_phrase_on_a_ukrainian_page_is_not_flagged():
    """12. Прогнати чужий перелік по сторінці означало б вигадати знахідку."""
    body = a("/a", "Read more") + a("/b", "Read more")
    ctx = context(page(f"{SITE}/", body, lang="uk"), *targets("/a", "/b"))
    assert weak_of(ctx) == []


def test_a_page_without_a_language_suppresses_the_phrase_registry():
    """13. Мови не знаємо — судимо лише те, що від неї не залежить."""
    ctx = context(page(f"{SITE}/", a("/a", "Read more") + a("/b", "Read more"), lang=""),
                  *targets("/a", "/b"))
    analysis = anchor_text.analyse(ctx)
    assert analysis.weak == []
    assert analysis.pages_without_language == 2


def test_a_language_without_a_registry_stays_silent():
    """14. Японська сторінка не отримує англійських зауважень."""
    ctx = context(page(f"{SITE}/", a("/a", "Read more") + a("/b", "Read more"), lang="ja"),
                  *targets("/a", "/b"))
    assert weak_of(ctx) == []


# ── 15–18. Походження й нормалізація ──────────────────────────────────────


def test_a_rendered_only_anchor_is_analysed():
    """15. Підпис, домальований скриптом, читач бачить так само."""
    ctx = context(page(f"{SITE}/"), *targets("/a", "/b"))
    body = a("/a", "Learn more") + a("/b", "Learn more")
    html = f"<html lang='en'><head><title>P</title></head><body><h1>P</h1>{body}</body></html>"
    result = RenderResult(url=f"{SITE}/", rendered=True, html=html)
    result.signals = signals_from_html(f"{SITE}/", html, origin=SITE, depth=0)
    ctx.renders[f"{SITE}/"] = result
    found = weak_of(ctx)
    assert len(found) == 2
    assert found[0].seen_in is Seen.RENDER


def test_a_response_only_anchor_is_analysed():
    """16. Пара до попереднього."""
    ctx = context(page(f"{SITE}/", a("/a", "Learn more") + a("/b", "Learn more")),
                  *targets("/a", "/b"))
    assert weak_of(ctx)[0].seen_in is Seen.RESPONSE


def test_the_same_link_in_both_versions_is_counted_once():
    """17. Відповідь і DOM — одне посилання, а не два."""
    body = a("/a", "Learn more") + a("/b", "Learn more")
    ctx = context(page(f"{SITE}/", body), *targets("/a", "/b"))
    html = f"<html lang='en'><head><title>P</title></head><body><h1>P</h1>{body}</body></html>"
    result = RenderResult(url=f"{SITE}/", rendered=True, html=html)
    result.signals = signals_from_html(f"{SITE}/", html, origin=SITE, depth=0)
    ctx.renders[f"{SITE}/"] = result
    assert len(weak_of(ctx)) == 2
    assert weak_of(ctx)[0].seen_in is Seen.BOTH


def test_equivalent_destinations_are_one_destination():
    """18. `/a` і `/a/` — одна ціль, тож двозначності ще немає."""
    ctx = context(page(f"{SITE}/", a("/a", "Learn more") + a("/a/", "Learn more")),
                  *targets("/a"))
    assert finding(ctx) is None


def test_a_broken_destination_does_not_change_the_anchor_verdict():
    """19. Поламаність цілі — інший корінь і інша знахідка."""
    broken = page(f"{SITE}/gone")
    broken.status_code = 404
    ctx = context(page(f"{SITE}/", a("/gone", "Learn more") + a("/b", "Learn more")),
                  broken, *targets("/b"))
    assert len(weak_of(ctx)) == 2
    assert finding(ctx) is not None


# ── 20–27. Доказ, знімки, мова звіту, скоринг ─────────────────────────────


def test_the_evidence_counts_are_accurate():
    """20. Числа мусять збігатися з тим, що справді спостережено."""
    body = "".join(a(f"/p{i}", "Learn more") for i in range(4))
    ctx = context(page(f"{SITE}/", body), *targets(*(f"/p{i}" for i in range(4))))
    evidence = finding(ctx).evidence
    row = evidence["phrases"][0]
    assert row["links"] == 4 and row["destinations"] == 4 and row["source_pages"] == 1
    assert evidence["contextual_links"] == 4


def test_bounded_examples_are_named_as_bounded():
    """21. Урізаний перелік не має вдавати повний."""
    body = "".join(a(f"/p{i}", "Learn more") for i in range(8))
    ctx = context(page(f"{SITE}/", body), *targets(*(f"/p{i}" for i in range(8))))
    row = finding(ctx).evidence["phrases"][0]
    assert len(row["examples"]) == 3 and row["examples_truncated"] is True
    assert row["links"] == 8


def test_a_snapshot_round_trip_reproduces_the_analysis():
    """22. Перерахунок без мережі має давати той самий висновок."""
    body = a("/a", "Learn more") + a("/b", "Learn more")
    ctx = context(page(f"{SITE}/", body), *targets("/a", "/b"))
    back = snapshot.load(json.loads(json.dumps(snapshot.dump(ctx))))
    assert [w.anchor for w in weak_of(back)] == [w.anchor for w in weak_of(ctx)]
    assert finding(back).title == finding(ctx).title


def test_old_snapshots_stay_readable():
    """23. Знімок без `image_alt` і `label` не має валити аналіз."""
    import pathlib

    for path in sorted(pathlib.Path("benchmark/snapshots").glob("*.json"))[:8]:
        ctx = snapshot.load(json.loads(path.read_text(encoding="utf-8")))
        anchor_text.analyse(ctx)
        list(AnchorTextCheck().run(ctx))


@pytest.mark.parametrize("code", ["en", "uk", "de", "es", "fr", "ru"])
def test_every_locale_carries_the_message(code):
    """24. Жодного тихого відкоту в англійську."""
    from app.audit.i18n import CATALOGS, Locale

    entry = CATALOGS[Locale(code)]["seo.anchor_text"]
    for field in ("title", "description", "recommendation", "consequence"):
        assert entry[field].strip(), f"{code}: порожнє {field}"


def test_no_recommendation_asks_for_keyword_stuffing():
    """25. Порада — писати зрозуміло, а не «додати ключові слова»."""
    from app.audit.i18n import CATALOGS

    banned = ("keyword", "ключов", "Schlüsselwort", "palabra clave", "mot-clé",
              "exact match", "точний збіг", "плотност", "density")
    offenders = [
        f"{locale}: {word}"
        for locale, catalog in CATALOGS.items()
        for word in banned
        # Порада «не набивайте ключові слова» — це заборона, а не заклик.
        if word.lower() in catalog["seo.anchor_text"]["recommendation"].lower()
        and "не " not in catalog["seo.anchor_text"]["recommendation"].lower()
        and "not " not in catalog["seo.anchor_text"]["recommendation"].lower()
        and "keine" not in catalog["seo.anchor_text"]["recommendation"].lower()
        and "no " not in catalog["seo.anchor_text"]["recommendation"].lower()
        and "n'" not in catalog["seo.anchor_text"]["recommendation"].lower()
    ]
    assert not offenders, offenders


def test_no_wording_claims_ranking_loss():
    """26. Google цього не стверджує, і ми не міряли."""
    from app.audit.i18n import CATALOGS

    banned = ("ranking", "rank ", "penalty", "penalis", "penaliz", "позиці",
              "штраф", "ранжув", "Rangfolge", "posicionamiento", "classement",
              "ранжир")
    offenders = [
        f"{locale}: {word}"
        for locale, catalog in CATALOGS.items()
        for word in banned
        for text in catalog["seo.anchor_text"].values()
        if word.lower() in text.lower()
    ]
    assert not offenders, offenders


def test_the_check_moves_no_score_on_the_frozen_corpus():
    """27. Здатність бачити більше не рухає бали, зняті раніше."""
    import pathlib

    from app.audit import scoring
    from app.audit.checks import all_checks

    moved = []
    for path in sorted(pathlib.Path("benchmark/snapshots").glob("*.json")):
        ctx = snapshot.load(json.loads(path.read_text(encoding="utf-8")))
        every = [i for c in all_checks() for i in c.run(ctx)]
        without = [i for i in every if i.code != "seo.anchor_text"]
        if scoring.overall_raw(every, set()) != scoring.overall_raw(without, set()):
            moved.append(path.stem)
    assert not moved, moved


def test_the_graph_is_untouched_by_anchor_analysis():
    """28. Аналіз тексту не сміє рухати важливість сторінок.

    Ваги в графі — питання калібрування, а не побічний ефект нового
    чека.
    """
    from app.audit.link_graph import build

    body = a("/a", "Learn more") + a("/b", "Learn more")
    ctx = context(page(f"{SITE}/", body), *targets("/a", "/b"))
    before = build(ctx)
    anchor_text.analyse(ctx)
    after = build(ctx)
    assert before.incoming == after.incoming
    assert before.outgoing == after.outgoing
    assert before.depth == after.depth
