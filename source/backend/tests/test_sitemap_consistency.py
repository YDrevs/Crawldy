"""Карта сайту проти побаченого: що звіряється й де закінчується право судити.

Карта тут не підставляється готовим обʼєктом там, де питання саме про
розбір: XML проходить справжній `_parse_sitemap`, а сторінки — справжній
`extract()` із `FetchResult`. Підміняється лише транспорт.

Головне, що ці випадки стережуть, — дві межі. Адреса, до якої не дійшов
краул, не стає знахідкою; і сторінка з двома вадами дає одну знахідку, а
не дві, бо дія в неї одна.
"""

from __future__ import annotations

import json

import pytest

from app.audit import sitemap_audit, snapshot
from app.audit.checks.seo import SitemapConsistencyCheck
from app.audit.extractor import extract
from app.audit.fetcher import FetchResult, RedirectHop
from app.audit.site_context import _parse_sitemap
from app.audit.sitemap_audit import Reason
from app.audit.types import SitemapInfo
from tests.factories import context, page_from_html

SITE = "https://example.com"


def html(*, canonical: str | None = None, robots: str | None = None) -> str:
    head = ""
    if canonical:
        head += f'<link rel="canonical" href="{canonical}">'
    if robots:
        head += f'<meta name="robots" content="{robots}">'
    return (
        f"<html lang='en'><head><title>Page</title>{head}</head>"
        "<body><h1>Heading</h1><p>Some words on the page.</p></body></html>"
    )


def page(url: str, *, status: int = 200, hops: list[tuple[int, str]] | None = None,
         requested: str | None = None, **kw):
    body = html(**kw)
    return extract(
        FetchResult(
            url=requested or url, final_url=url, status_code=status,
            content_type="text/html", text=body, body_bytes=len(body), elapsed_ms=20,
            headers={},
            redirects=tuple(RedirectHop(status_code=c, url=u) for c, u in (hops or [])),
        ),
        origin=SITE,
    )


def sitemap(urls: list[str], *, sources: dict[str, str] | None = None,
            declared: int | None = None, **kw) -> SitemapInfo:
    return SitemapInfo(
        exists=True, status_code=200, url=f"{SITE}/sitemap.xml",
        url_count=declared if declared is not None else len(urls),
        urls=urls,
        sources=sources if sources is not None else {u: f"{SITE}/sitemap.xml" for u in urls},
        **kw,
    )


def audit_of(*pages, urls: list[str], **kw):
    ctx = context(*pages, sitemap=sitemap(urls, **kw))
    return sitemap_audit.collect(ctx), ctx


def reasons(audit) -> dict[str, list[str]]:
    return {r.value: [e.url for e in entries] for r, entries in audit.by_reason().items()}


# ── 1–3. Здорова карта й помилки ──────────────────────────────────────────


def test_a_healthy_sitemap_produces_nothing():
    """1. Канонічні 200-сторінки, які самі себе й називають."""
    urls = [f"{SITE}/a", f"{SITE}/b"]
    pages = [page(u, canonical=u) for u in urls]
    audit, ctx = audit_of(*pages, urls=urls)
    assert audit.inconsistent == []
    assert list(SitemapConsistencyCheck().run(ctx)) == []


def test_a_sitemap_url_that_answered_404_is_reported():
    """2. Найпростіше для доказу: код ми прочитали самі."""
    audit, _ = audit_of(page(f"{SITE}/gone", status=404), urls=[f"{SITE}/gone"])
    assert reasons(audit) == {"error": [f"{SITE}/gone"]}


def test_a_sitemap_url_that_answered_5xx_is_reported():
    """3. Та сама причина, інший код — окремої знахідки не потребує."""
    audit, _ = audit_of(page(f"{SITE}/down", status=503), urls=[f"{SITE}/down"])
    assert [e.status for e in audit.inconsistent] == [503]


# ── 4–5. Перенаправлення ──────────────────────────────────────────────────


def test_a_sitemap_url_that_redirects_once_is_an_inconsistency():
    """4. Сам редирект законний, але в карті має стояти кінцева адреса.

    Це не суперечить `seo.redirect_chain`: там про довжину шляху, тут про
    те, що в переліку заявлено не ту адресу.
    """
    p = page(f"{SITE}/new", requested=f"{SITE}/old", hops=[(301, f"{SITE}/new")])
    audit, _ = audit_of(p, urls=[f"{SITE}/old"])
    assert reasons(audit) == {"redirects": [f"{SITE}/old"]}
    assert audit.inconsistent[0].detail["final_url"] == f"{SITE}/new"


def test_a_sitemap_url_that_redirects_through_a_chain_keeps_the_hops():
    """5. Ланцюг береться готовий із `redirects.py`, другого розбору немає."""
    p = page(f"{SITE}/new", requested=f"{SITE}/old",
             hops=[(301, f"{SITE}/mid"), (302, f"{SITE}/new")])
    audit, _ = audit_of(p, urls=[f"{SITE}/old"])
    detail = audit.inconsistent[0].detail
    assert detail["redirects"] == 2
    assert [h["url"] for h in detail["hops"]] == [f"{SITE}/mid", f"{SITE}/new"]


# ── 6–9. noindex і canonical ──────────────────────────────────────────────


def test_a_sitemap_url_observed_as_noindex_is_reported():
    """6. Сайт водночас просить знайти сторінку й просить її не показувати."""
    audit, _ = audit_of(page(f"{SITE}/x", robots="noindex"), urls=[f"{SITE}/x"])
    assert reasons(audit) == {"noindex": [f"{SITE}/x"]}
    assert audit.inconsistent[0].detail["noindex_source"] == "response"


def test_a_sitemap_url_canonicalizing_elsewhere_is_reported():
    """7. Карта заявляє одну адресу, сторінка називає головною іншу."""
    audit, _ = audit_of(page(f"{SITE}/dupe", canonical=f"{SITE}/main"), urls=[f"{SITE}/dupe"])
    assert reasons(audit) == {"canonical": [f"{SITE}/dupe"]}


def test_the_evidence_says_whether_the_canonical_is_also_in_the_sitemap():
    """8. Канонічна адреса теж заявлена — правка дрібніша."""
    urls = [f"{SITE}/dupe", f"{SITE}/main"]
    pages = [page(f"{SITE}/dupe", canonical=f"{SITE}/main"),
             page(f"{SITE}/main", canonical=f"{SITE}/main")]
    audit, _ = audit_of(*pages, urls=urls)
    detail = audit.inconsistent[0].detail
    assert detail["canonical_in_sitemap"] is True
    assert detail["canonical_observed"] is True


def test_a_canonical_absent_from_the_sitemap_is_recorded_as_absent():
    """9. Пара до попереднього: у карті немає жодної з двох адрес як слід."""
    audit, _ = audit_of(page(f"{SITE}/dupe", canonical=f"{SITE}/main"), urls=[f"{SITE}/dupe"])
    assert audit.inconsistent[0].detail["canonical_in_sitemap"] is False


def test_a_service_page_in_the_sitemap_is_reported():
    """10. Кошику й сторінці входу в переліку «знайдіть це» місця немає."""
    audit, _ = audit_of(page(f"{SITE}/wp-login.php"), urls=[f"{SITE}/wp-login.php"])
    assert Reason.NOT_FOR_SEARCH in audit.by_reason()


# ── 11–13. Межі знання ────────────────────────────────────────────────────


def test_a_sitemap_url_we_never_opened_produces_no_finding():
    """11. Не відкривали ≠ зламано. Найважливіша межа цієї роботи."""
    audit, ctx = audit_of(page(f"{SITE}/a", canonical=f"{SITE}/a"),
                          urls=[f"{SITE}/a", f"{SITE}/never-visited"])
    assert audit.inconsistent == []
    assert audit.checked == 1
    assert list(SitemapConsistencyCheck().run(ctx)) == []


def test_partial_coverage_is_stated_next_to_the_conclusion():
    """12. «Карта чиста» на 20 із 20 000 було б неправдою про сайт."""
    _, ctx = audit_of(page(f"{SITE}/gone", status=404),
                      urls=[f"{SITE}/gone"], declared=20_000)
    found = list(SitemapConsistencyCheck().run(ctx))
    evidence = found[0].evidence
    assert evidence["declared"] == 20_000
    assert evidence["checked"] == 1
    assert evidence["unchecked"] == 19_999


def test_one_url_with_two_faults_gives_one_finding_not_two():
    """13. Корінь один, дія одна — знахідка теж одна.

    Сторінка буває водночас `noindex` і з canonical на іншу. Дві знахідки
    описували б ту саму правку двічі, тож у групу йде найважча причина, а
    решта лишається поруч у доказі.
    """
    p = page(f"{SITE}/x", robots="noindex", canonical=f"{SITE}/main")
    audit, ctx = audit_of(p, urls=[f"{SITE}/x"])
    assert len(audit.inconsistent) == 1
    assert audit.inconsistent[0].primary is Reason.NOINDEX
    assert [r.value for r in audit.inconsistent[0].reasons] == ["noindex", "canonical"]
    assert len(list(SitemapConsistencyCheck().run(ctx))) == 1


# ── 14–16. Дедуплікат і походження ────────────────────────────────────────


def test_the_same_page_written_twice_is_one_entry_with_both_spellings():
    """14. `/a` і `/a/` — одна сторінка, хай і в двох файлах карти."""
    urls = [f"{SITE}/a", f"{SITE}/a/"]
    sources = {f"{SITE}/a": f"{SITE}/sitemap-1.xml", f"{SITE}/a/": f"{SITE}/sitemap-2.xml"}
    audit, _ = audit_of(page(f"{SITE}/a", status=404), urls=urls, sources=sources)
    assert len(audit.entries) == 1
    entry = audit.entries[0]
    assert set(entry.sources) == {f"{SITE}/sitemap-1.xml", f"{SITE}/sitemap-2.xml"}
    assert entry.detail["written_as"] == urls


def test_duplicate_membership_alone_is_not_a_warning():
    """15. Та сама адреса у двох файлах — не проблема клієнта."""
    urls = [f"{SITE}/a", f"{SITE}/a/"]
    audit, _ = audit_of(page(f"{SITE}/a", canonical=f"{SITE}/a"), urls=urls)
    assert audit.inconsistent == []


def test_a_sitemap_index_records_which_child_was_read():
    """16. Читаємо поки одну дитину — і кажемо, скільки їх було.

    Мовчання про решту мало б виглядати як «там нічого немає», а це
    неправда: ми туди не ходили.
    """
    xml = f"""<?xml version="1.0"?>
    <sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <sitemap><loc>{SITE}/sitemap-1.xml</loc></sitemap>
      <sitemap><loc>{SITE}/sitemap-2.xml</loc></sitemap>
    </sitemapindex>"""
    parsed = _parse_sitemap(xml)
    assert parsed.is_index and len(parsed.children) == 2

    info = sitemap([f"{SITE}/a"], is_index=True,
                   children_read=[f"{SITE}/sitemap-1.xml"], children_total=2)
    ctx = context(page(f"{SITE}/a", status=404), sitemap=info)
    evidence = next(iter(SitemapConsistencyCheck().run(ctx))).evidence
    assert evidence["sitemap_is_index"] is True
    assert (evidence["children_read"], evidence["children_total"]) == (1, 2)


def test_sitemap_hreflang_annotations_are_untouched():
    """17. Робота пункту #4 має пережити цю: це різні семантики."""
    from app.audit.types import HreflangRef

    info = sitemap([f"{SITE}/a"])
    info.hreflang = {f"{SITE}/a": [HreflangRef("de", f"{SITE}/de", "sitemap")]}
    info.hreflang_url_count = 1
    ctx = context(page(f"{SITE}/a", canonical=f"{SITE}/a"), sitemap=info)
    assert sitemap_audit.collect(ctx).inconsistent == []
    assert ctx.sitemap.hreflang[f"{SITE}/a"][0].value == "de"


# ── 18–21. Знімки, мова, звіт, скоринг ────────────────────────────────────


def test_a_fresh_snapshot_round_trips_the_cross_check():
    """18. Перерахунок без мережі має давати той самий висновок."""
    p = page(f"{SITE}/gone", status=404)
    ctx = context(p, sitemap=sitemap([f"{SITE}/gone"]))
    back = snapshot.load(json.loads(json.dumps(snapshot.dump(ctx))))
    assert back.sitemap.sources == {f"{SITE}/gone": f"{SITE}/sitemap.xml"}
    assert [i.title for i in SitemapConsistencyCheck().run(back)] == [
        i.title for i in SitemapConsistencyCheck().run(ctx)
    ]


def test_an_old_snapshot_reports_provenance_as_unknown_not_absent():
    """19. Знімок, старший за поле, не знає походження — і каже саме це."""
    import pathlib

    old = next(pathlib.Path("benchmark/snapshots").glob("*.json"))
    ctx = snapshot.load(json.loads(old.read_text(encoding="utf-8")))
    audit = sitemap_audit.collect(ctx)
    assert audit.provenance_known is False
    list(SitemapConsistencyCheck().run(ctx))


@pytest.mark.parametrize("code", ["en", "uk", "de", "es", "fr", "ru"])
def test_every_locale_carries_all_five_messages(code):
    """20. Жодного тихого відкоту в англійську."""
    from app.audit.i18n import CATALOGS, Locale

    catalog = CATALOGS[Locale(code)]
    for reason in sitemap_audit.ORDER:
        key = f"seo.sitemap_consistency.{reason.value}"
        assert key in catalog, f"{code}: бракує {key}"
        for field in ("title", "description", "recommendation", "consequence"):
            assert catalog[key][field].strip()


def test_no_wording_promises_indexing_or_ranking():
    """21. Карта — підказка, а не команда, і Google описує її саме так."""
    from app.audit.i18n import CATALOGS

    banned = (
        "guarantee", "will be indexed", "ranking", "penalty", "penalis", "penaliz",
        "гаранту", "буде проіндекс", "позиці", "штраф", "ранжув",
        "garantiert", "Rangfolge", "garantiza", "posicionamiento",
        "garantit", "classement", "гарантир", "проиндексир",
    )
    offenders = [
        f"{locale}/{key}: {word}"
        for locale, catalog in CATALOGS.items()
        for key, entry in catalog.items()
        if key.startswith("seo.sitemap_consistency")
        for text in entry.values()
        for word in banned
        if word.lower() in text.lower()
    ]
    assert not offenders, offenders


def test_the_finding_reaches_the_report_with_its_evidence():
    """22. Доказ мусить пережити шлях до звіту, а не лишитись у чеку."""
    from app.audit import i18n as audit_i18n
    from app.audit.orchestrator import rescore
    from app.report.builder import build_report
    from app.report.source import source_from_outcome

    ctx = context(
        page_from_html(html(), url=f"{SITE}/"),
        page(f"{SITE}/gone", status=404),
        sitemap=sitemap([f"{SITE}/gone"], declared=40),
    )
    doc = build_report(source_from_outcome(rescore(ctx)), audit_i18n.Locale("uk"))
    hits = [r for r in doc.recommendations if r.issue_key.startswith("seo.sitemap_consistency")]
    assert hits
    assert hits[0].evidence["declared"] == 40
    assert hits[0].action and hits[0].consequence


def test_the_new_capability_moves_no_score_on_the_frozen_corpus():
    """23. Здатність бачити більше не має рухати бали, зняті раніше."""
    import pathlib

    from app.audit import scoring
    from app.audit.checks import all_checks

    moved = []
    for f in sorted(pathlib.Path("benchmark/snapshots").glob("*.json")):
        ctx = snapshot.load(json.loads(f.read_text(encoding="utf-8")))
        every = [i for c in all_checks() for i in c.run(ctx)]
        without = [i for i in every if not i.code.startswith("seo.sitemap_consistency")]
        if scoring.overall_raw(every, set()) != scoring.overall_raw(without, set()):
            moved.append(f.stem)
    assert not moved, moved


def test_images_in_the_sitemap_are_not_judged_as_pages():
    """24. Помилка категорії, спіймана на вибірці.

    Карти часто змішують сторінки з картинками — `root.iter()` збирає й
    `image:loc`. На crustula.com.ua пʼять зниклих світлин виглядали як
    пʼять зламаних сторінок. `/logo.svg` не має ані canonical, ані
    `noindex`, тож судити його правилами для сторінок безглуздо; межа
    береться та сама, якою краул вирішує, що є сторінкою.
    """
    urls = [f"{SITE}/a", f"{SITE}/img/photo.jpg", f"{SITE}/img/logo.svg"]
    pages = [
        page(f"{SITE}/a", canonical=f"{SITE}/a"),
        page(f"{SITE}/img/photo.jpg", status=404),
        page(f"{SITE}/img/logo.svg", status=404),
    ]
    audit, ctx = audit_of(*pages, urls=urls)
    assert audit.inconsistent == []
    assert audit.non_pages == 2
    assert list(SitemapConsistencyCheck().run(ctx)) == []


# ── 25–31. Структурний поділ сторінок і медіа ─────────────────────────────

MEDIA_SITEMAP = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
        xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"
        xmlns:video="http://www.google.com/schemas/sitemap-video/1.1">
  <url>
    <loc>https://example.com/gallery</loc>
    <image:image><image:loc>https://example.com/photo.jpg</image:loc></image:image>
    <image:image><image:loc>https://example.com/render/1024</image:loc></image:image>
    <image:image><image:loc>https://example.com/img?id=7&amp;size=l</image:loc></image:image>
    <image:image><image:loc>https://cdn.elsewhere.net/a/b</image:loc></image:image>
  </url>
  <url>
    <loc>https://example.com/about</loc>
    <video:video><video:content_loc>https://example.com/clip.mp4</video:content_loc></video:video>
  </url>
  <url><loc>https://example.com/report.pdf</loc></url>
</urlset>"""


def test_media_children_never_become_sitemap_entries():
    """25. Розширення ніколи не було правильним розрізненням.

    Чотири форми адреси картинки, жодна з яких не ловиться однаково:
    `.jpg`, без розширення взагалі, з параметрами запиту й на чужому
    домені. Схема ж каже однозначно: `<image:image><image:loc>` — це
    ресурс запису, а не запис.
    """
    parsed = _parse_sitemap(MEDIA_SITEMAP)
    assert parsed.pages == [
        f"{SITE}/gallery",
        f"{SITE}/about",
        f"{SITE}/report.pdf",
    ]
    assert parsed.images[f"{SITE}/gallery"] == [
        f"{SITE}/photo.jpg",
        f"{SITE}/render/1024",
        f"{SITE}/img?id=7&size=l",
        "https://cdn.elsewhere.net/a/b",
    ]


def test_an_extensionless_page_stays_a_page():
    """26. Пара до попереднього з іншого боку: `/about` — сторінка."""
    assert f"{SITE}/about" in _parse_sitemap(MEDIA_SITEMAP).pages


def test_a_document_with_an_extension_stays_an_entry():
    """27. `/report.pdf` у `<url><loc>` — справжній запис карти.

    Фільтр розширень викинув би його разом із картинками, хоча сайт
    заявив його як документ, який варто знайти.
    """
    assert f"{SITE}/report.pdf" in _parse_sitemap(MEDIA_SITEMAP).pages


def test_video_children_are_kept_apart_from_pages():
    """28. Те саме для відео: свій `content_loc`, не сторінка."""
    parsed = _parse_sitemap(MEDIA_SITEMAP)
    assert parsed.images[f"{SITE}/about"] == [f"{SITE}/clip.mp4"]
    assert f"{SITE}/clip.mp4" not in parsed.pages


def test_the_consistency_check_never_sees_media_urls():
    """29. Наскрізно: помилка категорії не може повторитись.

    Раніше зникла світлина виглядала зламаною сторінкою. Тепер вона
    навіть не потрапляє в перелік, який звіряють.
    """
    parsed = _parse_sitemap(MEDIA_SITEMAP)
    info = sitemap(parsed.pages)
    info.images = parsed.images
    ctx = context(page(f"{SITE}/gallery", canonical=f"{SITE}/gallery"), sitemap=info)
    audit = sitemap_audit.collect(ctx)
    assert all(not e.url.endswith((".jpg", ".mp4")) for e in audit.entries)
    assert list(SitemapConsistencyCheck().run(ctx)) == []


# ── 30–32. Повнота індексу ────────────────────────────────────────────────


def test_a_partially_read_index_says_so():
    """30. Прочитали пʼять дітей зі ста — це не погляд на всю карту."""
    info = sitemap([f"{SITE}/a"], is_index=True, index_complete=False,
                   children_read=[f"{SITE}/s{i}.xml" for i in range(5)], children_total=100)
    ctx = context(page(f"{SITE}/a", status=404), sitemap=info)
    evidence = next(iter(SitemapConsistencyCheck().run(ctx))).evidence
    assert evidence["index_complete"] is False
    assert (evidence["children_read"], evidence["children_total"]) == (5, 100)


def test_a_fully_read_index_is_marked_complete():
    """31. Пара до попереднього: дві дитини з двох — повний погляд."""
    info = sitemap([f"{SITE}/a"], is_index=True, index_complete=True,
                   children_read=[f"{SITE}/s1.xml", f"{SITE}/s2.xml"], children_total=2)
    ctx = context(page(f"{SITE}/a", status=404), sitemap=info)
    assert next(iter(SitemapConsistencyCheck().run(ctx))).evidence["index_complete"] is True


def test_no_message_blames_the_crawl_budget_alone():
    """32. Причин, чому адресу не перевірено, дві, а не одна.

    Відколи індекс читається вибіркою, «решта не потрапила в бюджет
    краулу» стало неправдою: частина адрес лежить у дітях, яких ми не
    відкривали.
    """
    from app.audit.i18n import CATALOGS

    blamed = ("crawl budget", "бюджет краулу", "Crawl-Budget",
              "presupuesto de rastreo", "budget d'exploration", "бюджет обхода")
    offenders = [
        f"{locale}/{key}"
        for locale, catalog in CATALOGS.items()
        for key, entry in catalog.items()
        if key.startswith("seo.sitemap_consistency")
        for text in entry.values()
        for word in blamed
        if word.lower() in text.lower()
    ]
    assert not offenders, offenders
