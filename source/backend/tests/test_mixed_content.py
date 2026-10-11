"""Незахищені підресурси на захищеній сторінці: заявлене проти спостереженого.

Розмітка проходить справжній `extract()`, журнал запитів — справжній
`RenderResult`. Головне, що ці випадки стережуть, — межа між тим, що
сайт написав, і тим, що браузер зробив: злиття цих двох в одне
твердження було б вигадкою в обидва боки.
"""

from __future__ import annotations

import json

import pytest

from app.audit import mixed_content, snapshot
from app.audit.checks.tech import MixedContentCheck
from app.audit.extractor import extract, signals_from_html
from app.audit.fetcher import FetchResult
from app.audit.mixed_content import Handling, Observed
from app.audit.types import RenderResult
from tests.factories import context

SECURE = "https://example.com/"
PLAIN = "http://example.com/"


def page(url: str = SECURE, head: str = "", body: str = "", headers: dict | None = None):
    html = (
        f"<html lang='en'><head><title>Page</title>{head}</head>"
        f"<body><h1>Heading</h1>{body}<p>Some words here.</p></body></html>"
    )
    return extract(
        FetchResult(url=url, final_url=url, status_code=200, content_type="text/html",
                    text=html, body_bytes=len(html), elapsed_ms=10,
                    headers=headers or {}),
        origin="https://example.com",
    )


def rendered(ctx, url: str, *, head: str = "", body: str = "", requests: list[str] | None = None):
    html = (
        f"<html lang='en'><head><title>Page</title>{head}</head>"
        f"<body><h1>Heading</h1>{body}<p>Some words here.</p></body></html>"
    )
    result = RenderResult(url=url, rendered=True, html=html)
    result.signals = signals_from_html(url, html, origin="https://example.com", depth=0)
    result.requests = list(requests or [])
    ctx.renders[url] = result
    return ctx


def refs(ctx):
    return mixed_content.analyse(ctx).references


def finding(ctx, variant: str):
    return next(
        (i for i in MixedContentCheck().run(ctx) if i.issue_key.endswith(variant)), None
    )


# ── 1–2. Коли змішаного вмісту не буває ───────────────────────────────────


def test_a_secure_page_with_secure_resources_says_nothing():
    """1. Усе по https — і говорити нема про що."""
    ctx = context(page(head='<script src="https://cdn.new/a.js"></script>'))
    assert refs(ctx) == []
    assert list(MixedContentCheck().run(ctx)) == []


def test_an_insecure_page_produces_no_mixed_content_finding():
    """2. Змішаний вміст існує лише в захищеному контексті.

    Про сам незахищений документ говорить `seo.https`; дублювати той
    самий корінь другою знахідкою не можна.
    """
    ctx = context(page(PLAIN, head='<script src="http://cdn.old/a.js"></script>'))
    assert refs(ctx) == []
    assert list(MixedContentCheck().run(ctx)) == []


# ── 3–6. Клас, який браузер не пропускає ──────────────────────────────────


@pytest.mark.parametrize(
    "head,body,kind",
    [
        ('<script src="http://cdn.old/a.js"></script>', "", "script"),
        ('<link rel="stylesheet" href="http://cdn.old/a.css">', "", "stylesheet"),
        ("", '<iframe src="http://widget.old/w"></iframe>', "iframe"),
        ("", '<object data="http://old/o.swf"></object>', "object"),
    ],
)
def test_blockable_resource_classes(head, body, kind):
    """3. Скрипт, стиль, фрейм, обʼєкт — браузер їх не підвищує."""
    ctx = context(page(head=head, body=body))
    found = refs(ctx)
    assert [r.kind for r in found] == [kind]
    assert found[0].handling is Handling.BLOCKABLE


def test_a_script_built_request_is_seen_only_in_the_network_log():
    """4. Запит, якого в розмітці немає, — окремий варіант.

    Пошук по коду сторінки його не знайде: адресу складає скрипт.
    """
    ctx = rendered(context(page()), SECURE, requests=["http://beacon.old/hit"])
    found = refs(ctx)
    assert [r.seen_in for r in found] == ["network"]
    assert found[0].observed is Observed.REQUESTED_INSECURELY
    assert found[0].handling is Handling.UNKNOWN
    assert finding(ctx, "runtime") is not None


# ── 5–8. Клас, який браузер підвищує сам ──────────────────────────────────


@pytest.mark.parametrize(
    "body,kind",
    [
        ('<img src="http://img.old/p.jpg">', "img"),
        ('<audio src="http://media.old/a.mp3"></audio>', "audio"),
        ('<video src="http://media.old/v.mp4"></video>', "video"),
    ],
)
def test_upgradeable_resource_classes(body, kind):
    """5. Зображення, аудіо, відео: схему браузер підніме сам."""
    ctx = context(page(body=body))
    found = [r for r in refs(ctx) if r.kind == kind]
    assert found and found[0].handling is Handling.UPGRADEABLE


def test_srcset_candidates_are_each_collected():
    """6. `srcset` — набір адрес, і незахищеною буває будь-яка з них."""
    body = '<img srcset="http://img.old/1x.png 1x, https://img.new/2x.png 2x">'
    found = refs(context(page(body=body)))
    assert len(found) == 1
    assert found[0].in_srcset is True and found[0].url.endswith("1x.png")


def test_an_ip_host_is_not_promised_an_upgrade():
    """7. Алгоритм підвищення до IP-літералів не застосовується.

    Назвати такий ресурс «браузер полагодить сам» було б неправдою, а
    стверджувати блокування ми не міряли. Чесна відповідь — не знаємо.
    """
    ctx = context(page(body='<img src="http://192.0.2.10/p.jpg">'))
    assert refs(ctx)[0].handling is Handling.UNKNOWN


def test_a_mixed_download_is_its_own_class():
    """8. Завантаження з захищеної сторінки браузери судять окремо."""
    ctx = context(page(body='<a download href="http://files.old/r.pdf">Report</a>'))
    found = refs(ctx)
    assert [r.handling for r in found] == [Handling.MIXED_DOWNLOAD]
    assert finding(ctx, "download") is not None


def test_ordinary_navigation_to_an_http_page_is_not_mixed_content():
    """9. `<a href="http://…">` — це перехід, а не підресурс.

    Браузер нічого не підвантажує; він іде на інший сайт. Плутати ці
    речі означало б лаяти сайт за те, чого не сталося.
    """
    ctx = context(page(body='<a href="http://other.test/page">Partner</a>'))
    assert refs(ctx) == []


# ── 10–13. Заявлене проти спостереженого ──────────────────────────────────


def test_a_declared_resource_without_a_render_claims_no_outcome():
    """10. Найважливіша межа: сторінку не відкривали — висновку немає."""
    ctx = context(page(head='<script src="http://cdn.old/a.js"></script>'))
    found = refs(ctx)
    assert found[0].observed is Observed.NO_RENDER
    assert found[0].handling is Handling.BLOCKABLE


def test_an_observed_upgrade_is_recorded_as_an_upgrade():
    """11. Браузер пішов по https за тією самою адресою — це видно."""
    ctx = context(page(body='<img src="http://img.old/p.jpg">'))
    rendered(ctx, SECURE, body='<img src="http://img.old/p.jpg">',
             requests=["https://img.old/p.jpg"])
    assert refs(ctx)[0].observed is Observed.UPGRADED


def test_an_observed_insecure_request_is_recorded_as_such():
    """12. Ми бачили запит по http на власні очі."""
    ctx = context(page(head='<script src="http://cdn.old/a.js"></script>'))
    rendered(ctx, SECURE, head='<script src="http://cdn.old/a.js"></script>',
             requests=["http://cdn.old/a.js"])
    assert refs(ctx)[0].observed is Observed.REQUESTED_INSECURELY


def test_a_rendered_page_without_the_request_says_not_observed():
    """13. Дивилися й не побачили — це не «заблоковано»."""
    ctx = context(page(head='<script src="http://cdn.old/a.js"></script>'))
    rendered(ctx, SECURE, head='<script src="http://cdn.old/a.js"></script>',
             requests=["https://other.new/x.js"])
    assert refs(ctx)[0].observed is Observed.NOT_OBSERVED


# ── 14–16. Відповідь, рендер, CSP ─────────────────────────────────────────


def test_a_resource_introduced_only_after_rendering_is_attributed_to_the_render():
    """14. Скрипт домалював тег — його теж треба полагодити."""
    ctx = rendered(context(page()), SECURE,
                   head='<script src="http://cdn.old/a.js"></script>')
    found = refs(ctx)
    assert [r.seen_in for r in found] == ["render"]


def test_a_resource_in_both_versions_is_counted_once():
    """15. Відповідь і DOM — один ресурс, а не два."""
    head = '<script src="http://cdn.old/a.js"></script>'
    ctx = rendered(context(page(head=head)), SECURE, head=head)
    found = refs(ctx)
    assert len(found) == 1 and found[0].seen_in == "both"


def test_the_upgrade_directive_is_recorded_without_hiding_the_fact():
    """16. CSP каже, що браузер підвищить схему, — не що ресурс існує.

    Тому директива стає поруч у доказі, а не скасовує знахідку.
    """
    headers = {"content-security-policy": "upgrade-insecure-requests"}
    ctx = context(page(head='<script src="http://cdn.old/a.js"></script>', headers=headers))
    analysis = mixed_content.analyse(ctx)
    assert analysis.coverage()["pages_with_upgrade_insecure_requests"] == 1
    assert analysis.references
    assert finding(ctx, "blockable") is not None


def test_no_recommendation_offers_the_obsolete_directive():
    """17. `block-all-mixed-content` позначено застарілим — не радимо."""
    from app.audit.i18n import CATALOGS

    offenders = [
        locale
        for locale, catalog in CATALOGS.items()
        for key, entry in catalog.items()
        if key.startswith("tech.mixed_content")
        for text in entry.values()
        if "block-all-mixed-content" in text.lower()
    ]
    assert not offenders, offenders


# ── 18–21. Групування й походження ────────────────────────────────────────


def test_first_and_third_party_are_distinguished():
    """18. Дія різна: своє налаштування проти чужого постачальника."""
    body = '<img src="http://example.com/p.jpg"><img src="http://cdn.other/q.jpg">'
    found = {r.url: r.third_party for r in refs(context(page(body=body)))}
    assert found["http://example.com/p.jpg"] is False
    assert found["http://cdn.other/q.jpg"] is True


def test_resources_are_grouped_by_class_not_emitted_per_resource():
    """19. Двадцять картинок — одна знахідка, а не двадцять."""
    body = "".join(f'<img src="http://img.old/{i}.jpg">' for i in range(20))
    ctx = context(page(body=body))
    issues = list(MixedContentCheck().run(ctx))
    assert len(issues) == 1
    assert issues[0].evidence["resources_total"] == 20


def test_bounded_examples_are_honest_about_truncation():
    """20. Урізаний перелік не має вдавати повний."""
    body = "".join(f'<img src="http://img.old/{i}.jpg">' for i in range(20))
    evidence = finding(context(page(body=body)), "upgradeable").evidence
    assert len(evidence["resources"]) == 8
    assert evidence["resources_truncated"] is True
    assert evidence["resources_total"] == 20


def test_the_evidence_counts_pages_not_just_resources():
    """21. Одна адреса на восьми сторінках — це вісім місць правки."""
    head = '<script src="http://cdn.old/a.js"></script>'
    pages = [page(f"https://example.com/p{i}", head=head) for i in range(4)]
    evidence = finding(context(*pages), "blockable").evidence
    assert evidence["pages_affected"] == 4 and evidence["resources_total"] == 4


# ── 22–27. Знімки, мова, скоринг ──────────────────────────────────────────


def test_a_fresh_snapshot_round_trip_reproduces_the_analysis():
    """22. Перерахунок без мережі має давати той самий висновок."""
    head = '<script src="http://cdn.old/a.js"></script>'
    ctx = rendered(context(page(head=head)), SECURE, head=head,
                   requests=["http://cdn.old/a.js"])
    back = snapshot.load(json.loads(json.dumps(snapshot.dump(ctx))))
    before, after = refs(ctx), refs(back)
    assert [r.as_evidence() for r in before] == [r.as_evidence() for r in after]


def test_old_snapshots_stay_readable_and_invent_no_outcome():
    """23. Знімок без `insecure_refs` не має породжувати вигаданих ресурсів."""
    import pathlib

    for path in sorted(pathlib.Path("benchmark/snapshots").glob("*.json"))[:8]:
        ctx = snapshot.load(json.loads(path.read_text(encoding="utf-8")))
        for ref in refs(ctx):
            # Єдине, що може прийти зі старого знімка, — журнал запитів.
            assert ref.seen_in == "network"
        list(MixedContentCheck().run(ctx))


@pytest.mark.parametrize("code", ["en", "uk", "de", "es", "fr", "ru"])
def test_every_locale_carries_all_four_messages(code):
    """24. Жодного тихого відкоту в англійську."""
    from app.audit.i18n import CATALOGS, Locale

    catalog = CATALOGS[Locale(code)]
    for variant in ("blockable", "upgradeable", "download", "runtime"):
        key = f"tech.mixed_content.{variant}"
        assert key in catalog, f"{code}: бракує {key}"
        for field in ("title", "description", "recommendation", "consequence"):
            assert catalog[key][field].strip()


def test_no_wording_claims_a_ranking_penalty_or_a_security_scan():
    """25. Ми не міряли позицій і не сканували вразливостей."""
    from app.audit.i18n import CATALOGS

    banned = ("ranking", "rank ", "penalty", "penalis", "penaliz", "vulnerab",
              "позиці", "штраф", "ранжув", "вразлив", "Rangfolge", "уязвим",
              "posicionamiento", "classement", "ранжир")
    offenders = [
        f"{locale}/{key}: {word}"
        for locale, catalog in CATALOGS.items()
        for key, entry in catalog.items()
        if key.startswith("tech.mixed_content")
        for text in entry.values()
        for word in banned
        if word.lower() in text.lower()
    ]
    assert not offenders, offenders


def test_the_finding_reaches_the_report_with_its_evidence():
    """26. Доказ мусить пережити шлях до звіту."""
    from app.audit import i18n as audit_i18n
    from app.audit.orchestrator import rescore
    from app.report.builder import build_report
    from app.report.source import source_from_outcome

    ctx = context(page(head='<script src="http://cdn.old/a.js"></script>'))
    doc = build_report(source_from_outcome(rescore(ctx)), audit_i18n.Locale("uk"))
    hits = [r for r in doc.recommendations if r.issue_key.startswith("tech.mixed_content")]
    assert hits
    assert hits[0].evidence["resources"][0]["handling"] == "blockable"
    assert hits[0].action and hits[0].consequence


def test_the_new_capability_moves_no_score_on_the_frozen_corpus():
    """27. Здатність бачити більше не рухає бали, зняті раніше."""
    import pathlib

    from app.audit import scoring
    from app.audit.checks import all_checks

    moved = []
    for path in sorted(pathlib.Path("benchmark/snapshots").glob("*.json")):
        ctx = snapshot.load(json.loads(path.read_text(encoding="utf-8")))
        every = [i for c in all_checks() for i in c.run(ctx)]
        without = [i for i in every if i.code != "tech.mixed_content"]
        if scoring.overall_raw(every, set()) != scoring.overall_raw(without, set()):
            moved.append(path.stem)
    assert not moved, moved
