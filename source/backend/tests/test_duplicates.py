"""Однаковий вміст під різними адресами — і межа того, що з цього видно.

Сторінки будуються справжнім `extract()`; кластери — справжнім
`duplicates.analyse`. Найважливіші випадки тут не про спрацювання, а про
мовчання: спільний шаблон, різні статті під тим самим меню, дрібні
сторінки й мовні версії.
"""

from __future__ import annotations

import json

import pytest

from app.audit import duplicates, snapshot
from app.audit.checks.seo import DuplicateContentCheck
from app.audit.duplicates import Consolidation, Indexability
from app.audit.extractor import extract, signals_from_html
from app.audit.fetcher import FetchResult, RedirectHop
from app.audit.types import RenderResult
from tests.factories import context

SITE = "https://example.com"

NAV = (
    "<nav>Home Products Services Pricing About Contact Blog Careers Support "
    "Documentation Partners Legal Privacy Terms Sitemap</nav>"
)
FOOT = (
    "<footer>Company registered 2011 all rights reserved contact us by phone "
    "or email our office is open weekdays nine to six</footer>"
)


def words(seed: str, n: int = 60) -> str:
    return " ".join(f"{seed}-token-{i}" for i in range(n))


def page(url: str, body: str, *, canonical: str | None = None, robots: str | None = None,
         status: int = 200, hops: list[tuple[int, str]] | None = None,
         requested: str | None = None, chrome: bool = True):
    head = ""
    if canonical:
        head += f'<link rel="canonical" href="{canonical}">'
    if robots:
        head += f'<meta name="robots" content="{robots}">'
    html = (
        f"<html lang='en'><head><title>T</title>{head}</head><body>"
        f"{NAV if chrome else ''}<h1>H</h1><p>{body}</p>{FOOT if chrome else ''}</body></html>"
    )
    return extract(
        FetchResult(url=requested or url, final_url=url, status_code=status,
                    content_type="text/html", text=html, body_bytes=len(html),
                    elapsed_ms=10, headers={},
                    redirects=tuple(RedirectHop(status_code=c, url=u) for c, u in (hops or []))),
        origin=SITE,
    )


def clusters(ctx):
    return duplicates.analyse(ctx).clusters


def finding(ctx, variant: str | None = None):
    found = list(DuplicateContentCheck().run(ctx))
    if variant:
        found = [i for i in found if i.issue_key.endswith(variant)]
    return found[0] if found else None


# ── 1–5. Що дублікатом не є ───────────────────────────────────────────────


def test_two_genuinely_different_pages_are_not_a_cluster():
    """1. Різний вміст — і говорити нема про що."""
    ctx = context(page(f"{SITE}/a", words("alpha")), page(f"{SITE}/b", words("beta")),
                  page(f"{SITE}/c", words("gamma")))
    assert clusters(ctx) == []
    assert finding(ctx) is None


def test_the_same_template_with_different_bodies_is_not_a_duplicate():
    """2. Спільне меню й підвал — не привід оголошувати сторінки однаковими.

    Без чистки обвʼязки будь-який сайт із великою навігацією виглядав би
    суцільним дублікатом.
    """
    ctx = context(*[page(f"{SITE}/p{i}", words(f"article{i}")) for i in range(5)])
    assert clusters(ctx) == []


def test_different_articles_under_the_same_navigation_stay_distinct():
    """3. Те саме з іншого боку: меню однакове, статті різні."""
    ctx = context(*[page(f"{SITE}/news/{i}", words(f"story{i}", 120)) for i in range(4)])
    assert clusters(ctx) == []


def test_tiny_pages_with_different_text_do_not_form_fake_clusters():
    """4. Дрібні сторінки схожі випадково, і вимірювання там не працює.

    Межа існує заради статистики, а не щоб судити обсяг тексту: чотири
    короткі сторінки з різними словами кластером не стають, хай яка
    велика в них спільна обвʼязка.
    """
    ctx = context(*[page(f"{SITE}/t{i}", f"short text {i}") for i in range(4)])
    assert duplicates.analyse(ctx).clusters == []


def test_a_page_whose_whole_text_is_boilerplate_is_set_aside():
    """4b. Межа власного вмісту: у каркасі судити нема чого.

    Це не про обсяг, а про те, що після чистки не лишається нічого, чим
    сторінки можна було б розрізнити.
    """
    shell = "<html lang='en'><head><title>A</title></head><body>" + NAV + "</body></html>"
    pages = [
        extract(FetchResult(url=f"{SITE}/z{i}", final_url=f"{SITE}/z{i}", status_code=200,
                            content_type="text/html", text=shell, body_bytes=len(shell),
                            elapsed_ms=5, headers={}), origin=SITE)
        for i in range(3)
    ]
    analysis = duplicates.analyse(context(*pages))
    assert analysis.clusters == []
    assert analysis.skipped_thin >= 3


def test_a_client_rendered_shell_is_not_a_duplicate_set():
    """5. Випадок із вибірки: чотири адреси SPA віддають один каркас.

    Статичний текст у них справді однаковий, але це оболонка, а не
    сторінки. Після чистки власного вмісту в них нуль, і межа це ловить.
    """
    shell = "<html lang='en'><head><title>App</title></head><body>" + NAV + "</body></html>"
    pages = [
        extract(FetchResult(url=f"{SITE}/s{i}", final_url=f"{SITE}/s{i}", status_code=200,
                            content_type="text/html", text=shell, body_bytes=len(shell),
                            elapsed_ms=5, headers={}), origin=SITE)
        for i in range(4)
    ]
    assert duplicates.analyse(context(*pages)).clusters == []


# ── 6–10. Точні збіги ─────────────────────────────────────────────────────


def test_the_same_content_under_two_urls_is_one_cluster():
    """6. Класика: `/` і `/index.html` віддають одне й те саме."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/", same), page(f"{SITE}/index.html", same),
                  page(f"{SITE}/other", words("other", 80)))
    found = clusters(ctx)
    assert len(found) == 1 and len(found[0].members) == 2


def test_whitespace_and_case_differences_still_count_as_exact():
    """7. Нормалізація прибирає те, що для читача не існує."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same),
                  page(f"{SITE}/b", "   " + same.upper() + "  \n "),
                  page(f"{SITE}/c", words("other", 80)))
    assert len(clusters(ctx)) == 1


def test_query_parameter_variants_form_one_cluster():
    """8. `?utm_source` та подібне — та сама сторінка іншими словами."""
    same = words("facet", 80)
    ctx = context(page(f"{SITE}/list", same), page(f"{SITE}/list?sort=asc", same),
                  page(f"{SITE}/other", words("other", 80)))
    found = clusters(ctx)
    assert len(found) == 1 and len(found[0].members) == 2


def test_three_identical_pages_are_one_cluster_not_three_pairs():
    """9. Кластер, а не перебір пар: клієнтові тут одна робота."""
    same = words("shared", 80)
    ctx = context(*[page(f"{SITE}/p{i}", same) for i in range(3)],
                  page(f"{SITE}/x", words("x", 80)))
    found = clusters(ctx)
    assert len(found) == 1 and len(found[0].members) == 3
    assert len(list(DuplicateContentCheck().run(ctx))) == 1


def test_cluster_identity_is_stable_across_runs():
    """10. Два прогони мусять давати той самий кластер і той самий ключ."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same), page(f"{SITE}/b", same),
                  page(f"{SITE}/c", words("c", 80)))
    first = [c.identifier for c in clusters(ctx)]
    second = [c.identifier for c in clusters(ctx)]
    assert first == second and first


# ── 11–14. Canonical ──────────────────────────────────────────────────────


def test_consistent_consolidation_is_not_a_problem_finding():
    """11. Сайт сам звів дублікати до одного — це і є правильно."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same, canonical=f"{SITE}/a"),
                  page(f"{SITE}/b", same, canonical=f"{SITE}/a"),
                  page(f"{SITE}/c", words("c", 80)))
    assert clusters(ctx)[0].consolidation is Consolidation.CONSISTENT
    assert finding(ctx) is None


def test_both_self_canonical_is_an_unconsolidated_cluster():
    """12. Кожен називає головним себе — вибору сайт не зробив."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same, canonical=f"{SITE}/a"),
                  page(f"{SITE}/b", same, canonical=f"{SITE}/b"),
                  page(f"{SITE}/c", words("c", 80)))
    assert clusters(ctx)[0].consolidation is Consolidation.ALL_SELF
    assert finding(ctx, "unconsolidated") is not None


def test_a_member_pointing_outside_the_cluster_is_a_conflict():
    """13. Canonical веде на адресу, якої в групі немає взагалі."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same, canonical=f"{SITE}/a"),
                  page(f"{SITE}/b", same, canonical=f"{SITE}/elsewhere"),
                  page(f"{SITE}/c", words("c", 80)))
    assert clusters(ctx)[0].consolidation is Consolidation.CONFLICTING
    assert finding(ctx, "conflicting") is not None


def test_no_canonical_anywhere_is_recorded_as_absent():
    """14. Мовчання сайту — окремий стан, а не суперечність."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same), page(f"{SITE}/b", same),
                  page(f"{SITE}/c", words("c", 80)))
    assert clusters(ctx)[0].consolidation is Consolidation.ABSENT


def test_the_representative_follows_a_stated_rule():
    """15. Представник — не «вибір Google», а детермінований вибір показу."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/long-old-address", same, canonical=f"{SITE}/short"),
                  page(f"{SITE}/short", same, canonical=f"{SITE}/short"),
                  page(f"{SITE}/c", words("c", 80)))
    assert clusters(ctx)[0].representative.url == f"{SITE}/short"


# ── 16–19. Індексованість ─────────────────────────────────────────────────


def test_a_noindex_member_is_kept_as_context_not_as_action():
    """16. Сторінку вже прибрали з пошуку — шуміти про неї не треба."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same), page(f"{SITE}/b", same, robots="noindex"),
                  page(f"{SITE}/c", words("c", 80)))
    cluster = clusters(ctx)[0]
    assert len(cluster.members) == 2 and len(cluster.indexable_members) == 1
    assert finding(ctx) is None


def test_a_redirected_url_is_marked_and_not_treated_as_a_rival():
    """17. Перенаправлену адресу сайт уже звів — це не конкурент."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same),
                  page(f"{SITE}/b", same, requested=f"{SITE}/old",
                       hops=[(301, f"{SITE}/b")]),
                  page(f"{SITE}/c", words("c", 80)))
    states = {m.indexability for m in clusters(ctx)[0].members}
    assert Indexability.REDIRECTED in states


def test_service_pages_are_not_counted_as_rival_duplicates():
    """18. Вхід в адмінку в переліку однакових сторінок нікому не потрібен."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/wp-login.php", same), page(f"{SITE}/a", same),
                  page(f"{SITE}/c", words("c", 80)))
    assert len(clusters(ctx)[0].indexable_members) == 1
    assert finding(ctx) is None


def test_error_pages_never_enter_the_comparison():
    """19. Порівнюємо лише те, що сервер віддав успішно."""
    same = words("shared", 80)
    gone = page(f"{SITE}/gone", same, status=404)
    ctx = context(page(f"{SITE}/a", same), gone, page(f"{SITE}/c", words("c", 80)))
    urls = {m.url for c in clusters(ctx) for m in c.members}
    assert f"{SITE}/gone" not in urls


# ── 20–22. Мовні версії ───────────────────────────────────────────────────


def test_declared_language_variants_are_not_reported_as_duplicates():
    """20. Регіональні варіанти однією мовою законно майже однакові.

    Google прямо радить розводити їх canonical разом із hreflang, тож
    оголошена пара — це налаштування, а не недогляд.
    """
    same = words("shared", 80)
    head_a = '<link rel="alternate" hreflang="en-gb" href="https://example.com/gb">'
    head_b = '<link rel="alternate" hreflang="en-us" href="https://example.com/us">'
    html = ("<html lang='en'><head><title>T</title>" + head_a + head_b +
            "</head><body>" + NAV + f"<h1>H</h1><p>{same}</p>" + FOOT + "</body></html>")
    pages = [
        extract(FetchResult(url=u, final_url=u, status_code=200, content_type="text/html",
                            text=html, body_bytes=len(html), elapsed_ms=5, headers={}),
                origin=SITE)
        for u in (f"{SITE}/gb", f"{SITE}/us")
    ]
    ctx = context(*pages, page(f"{SITE}/c", words("c", 80)))
    assert clusters(ctx) == []


def test_pages_in_different_languages_are_not_clustered_by_template():
    """21. Спільний шаблон — не підстава рівняти німецьку з англійською."""
    ctx = context(page(f"{SITE}/en", words("english", 80)),
                  page(f"{SITE}/de", words("deutsch", 80)),
                  page(f"{SITE}/fr", words("francais", 80)))
    assert clusters(ctx) == []


# ── 22–25. Репрезентації ──────────────────────────────────────────────────


def test_response_text_is_compared_with_response_text():
    """22. Порівняння всередині однієї репрезентації, а не впоперек."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same), page(f"{SITE}/b", same),
                  page(f"{SITE}/c", words("c", 80)))
    assert {m.representation for m in clusters(ctx)[0].members} == {"response"}


def test_rendered_pages_are_compared_with_rendered_pages():
    """23. Дублікат, який видно лише після виконання скриптів."""
    shell = "<html lang='en'><head><title>App</title></head><body>" + NAV + "</body></html>"
    ctx = context(*[
        extract(FetchResult(url=f"{SITE}/s{i}", final_url=f"{SITE}/s{i}", status_code=200,
                            content_type="text/html", text=shell, body_bytes=len(shell),
                            elapsed_ms=5, headers={}), origin=SITE)
        for i in range(3)
    ])
    same = words("rendered", 80)
    for i, body in enumerate((same, same, words("unique", 80))):
        html = ("<html lang='en'><head><title>T</title></head><body>" + NAV +
                f"<h1>H</h1><p>{body}</p>" + FOOT + "</body></html>")
        result = RenderResult(url=f"{SITE}/s{i}", rendered=True, html=html)
        result.signals = signals_from_html(f"{SITE}/s{i}", html, origin=SITE, depth=0)
        ctx.renders[f"{SITE}/s{i}"] = result
    found = clusters(ctx)
    assert len(found) == 1
    assert {m.representation for m in found[0].members} == {"rendered"}


def test_a_failed_render_fabricates_nothing():
    """24. Браузер не піднявся — висновку про схожість це не дає."""
    ctx = context(page(f"{SITE}/a", words("a", 80)), page(f"{SITE}/b", words("b", 80)),
                  page(f"{SITE}/c", words("c", 80)))
    ctx.renders[f"{SITE}/a"] = RenderResult(url=f"{SITE}/a", rendered=False, error="no browser")
    assert clusters(ctx) == []


# ── 25–31. Доказ, знімки, скоринг, складність ─────────────────────────────


def test_the_evidence_carries_canonical_and_indexability_context():
    """25. Без цього контексту кластер не підказує, що робити."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same, canonical=f"{SITE}/a"),
                  page(f"{SITE}/b", same, canonical=f"{SITE}/b"),
                  page(f"{SITE}/c", words("c", 80)))
    cluster = finding(ctx).evidence["clusters"][0]
    assert cluster["consolidation"] == "all_self"
    assert cluster["representative"].startswith(SITE)
    assert all("indexability" in m and "canonical" in m for m in cluster["members"])


def test_bounded_cluster_display_keeps_accurate_totals():
    """26. Урізаний перелік не має вдавати повний."""
    pages = []
    for group in range(8):
        same = words(f"group{group}", 80)
        pages += [page(f"{SITE}/g{group}-{i}", same) for i in range(2)]
    pages.append(page(f"{SITE}/solo", words("solo", 80)))
    evidence = finding(context(*pages)).evidence
    assert evidence["clusters_total"] == 8
    assert len(evidence["clusters"]) == 5 and evidence["clusters_truncated"] is True


def test_a_snapshot_round_trip_reproduces_identical_clusters():
    """27. Перерахунок без мережі має давати ті самі кластери."""
    same = words("shared", 80)
    ctx = context(page(f"{SITE}/a", same), page(f"{SITE}/b", same),
                  page(f"{SITE}/c", words("c", 80)))
    back = snapshot.load(json.loads(json.dumps(snapshot.dump(ctx))))
    assert [c.identifier for c in clusters(back)] == [c.identifier for c in clusters(ctx)]


def test_old_snapshots_stay_readable():
    """28. Знімки, старші за цю роботу, мусять відкриватися."""
    import pathlib

    for path in sorted(pathlib.Path("benchmark/snapshots").glob("*.json"))[:6]:
        ctx = snapshot.load(json.loads(path.read_text(encoding="utf-8")))
        duplicates.analyse(ctx)
        list(DuplicateContentCheck().run(ctx))


@pytest.mark.parametrize("code", ["en", "uk", "de", "es", "fr", "ru"])
def test_every_locale_carries_both_messages(code):
    """29. Жодного тихого відкоту в англійську."""
    from app.audit.i18n import CATALOGS, Locale

    catalog = CATALOGS[Locale(code)]
    for variant in ("unconsolidated", "conflicting"):
        key = f"seo.duplicate_content.{variant}"
        assert key in catalog, f"{code}: бракує {key}"
        for field in ("title", "description", "recommendation", "consequence"):
            assert catalog[key][field].strip()


def test_no_wording_calls_duplicates_a_violation_or_a_penalty():
    """30. Google прямо пише, що дублікати правил не порушують.

    Слово «порушення» в текстах є — але лише в запереченні («порушенням
    правил не є»). Тому перевіряється не наявність слова, а наявність
    заперечення поруч: інакше тест забороняв би саме той рядок, яким ми
    спростовуємо міф.
    """
    from app.audit.i18n import CATALOGS

    banned = ("violation", "penalty", "penalis", "penaliz", "ranking",
              "порушенн", "штраф", "позиці", "ранжув", "Verstoß", "Rangfolge",
              "infracción", "posicionamiento", "infraction", "classement",
              "нарушени", "ранжир")
    # Заперечення бувають і перед словом, і після нього: «порушенням
    # правил не є», «rather than a rule violation». Тому вікно з обох боків.
    negations = ("not ", "no ", "kein", "nicht", "не ", "ne ", "n'", "pas ", "sin ",
                 "rather than", "а не", "не є", "es kein", "no una", "pas une")

    offenders = []
    for locale, catalog in CATALOGS.items():
        for key, entry in catalog.items():
            if not key.startswith("seo.duplicate_content"):
                continue
            for text in entry.values():
                lowered = text.lower()
                for word in banned:
                    at = lowered.find(word.lower())
                    if at < 0:
                        continue
                    window = lowered[max(0, at - 80): at + len(word) + 40]
                    if not any(n in window for n in negations):
                        offenders.append(f"{locale}/{key}: {word}")
    assert not offenders, offenders


def test_candidate_generation_stays_far_below_all_pairs():
    """31. Запобіжник проти випадкового O(n²).

    Пʼятсот різних сторінок дали б 124 750 порівнянь перебором. LSH
    добирає кандидатів за спільними кошиками, і на різному вмісті їх
    практично немає.
    """
    pages = [page(f"{SITE}/p{i}", words(f"unique{i}", 70)) for i in range(200)]
    analysis = duplicates.analyse(context(*pages))
    all_pairs = 200 * 199 // 2
    assert analysis.candidate_pairs < all_pairs * 0.05
    assert analysis.clusters == []


def test_the_check_moves_no_score_on_the_frozen_corpus():
    """32. Здатність бачити більше не рухає бали, зняті раніше."""
    import pathlib

    from app.audit import scoring
    from app.audit.checks import all_checks

    moved = []
    for path in sorted(pathlib.Path("benchmark/snapshots").glob("*.json")):
        ctx = snapshot.load(json.loads(path.read_text(encoding="utf-8")))
        every = [i for c in all_checks() for i in c.run(ctx)]
        without = [i for i in every if i.code != "seo.duplicate_content"]
        if scoring.overall_raw(every, set()) != scoring.overall_raw(without, set()):
            moved.append(path.stem)
    assert not moved, moved
