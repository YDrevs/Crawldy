"""Стани покриття: чи репрезентує прочитане той живий сайт, який існує.

Спільна оцінка замінила два незалежні правила. `crawl.failures` рахував
спостережені 404 як недоступність і забирав бал у сайтів, прочитаних без
жодної помилки доступу (scikit-learn.org). `crawl.shallow` лічив
4xx-сторінки як обійдені й мовчав рівно там, де доказів більшого сайту
найбільше. Кожен тест тут — випадок, на якому одна зі старих логік
брехала, або вимога, зафіксована в рішенні про модель.
"""

from __future__ import annotations

from app.audit.coverage import (
    CoverageState,
    assess,
    clean_untried_candidates,
    collect_evidence,
    looks_like_content,
)
from app.audit.enums import Module
from app.audit.orchestrator import AuditOptions, _module_coverage
from app.audit.types import COVERAGE_LIMITED, COVERAGE_WITHHELD
from tests.factories import context, page_from_html

WORDS = " ".join(f"слово{i}" for i in range(200))


def _page(url: str, links: list[str] | None = None, status: int = 200):
    body = WORDS + "".join(f'<a href="{u}">x</a>' for u in links or [])
    page = page_from_html(f"<html><body><main>{body}</main></body></html>", url=url)
    page.status_code = status
    return page


def _run(ctx):
    degraded: list = []
    skipped, partial = _module_coverage(AuditOptions(), ctx, [], degraded)
    return skipped, partial, degraded


# ── справжній односторінковий сайт ────────────────────────────────────


def test_a_one_page_site_with_no_evidence_of_more_stays_scored() -> None:
    """Візитівка репрезентована однією сторінкою повністю."""
    ctx = context(_page("https://example.com/"))
    evidence = collect_evidence(ctx)
    state, reasons = assess(evidence)
    assert state is CoverageState.SCORED
    assert reasons == ["no_evidence_of_additional_live_content"]

    skipped, _, degraded = _run(ctx)
    assert Module.SEO not in skipped
    assert not {d.scope for d in degraded} & {COVERAGE_WITHHELD, COVERAGE_LIMITED}


# ── robots ────────────────────────────────────────────────────────────


def test_one_page_plus_robots_restriction_is_withheld() -> None:
    """Сайт сам сказав не ходити далі — і оголошує більший розмір.

    22 сайти night3 читалися однією сторінкою саме через
    `User-agent: * / Disallow: /` при картах на сотні адрес. Оцінювати
    їх за головною означало б видати оцінку сторінки за оцінку сайту.
    """
    ctx = context(_page("https://example.com/"))
    ctx.robots.exists = True
    ctx.robots.disallows_all = True

    state, reasons = assess(collect_evidence(ctx))
    assert state is CoverageState.WITHHELD
    assert "robots_restricted" in reasons

    skipped, _, degraded = _run(ctx)
    assert {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY} <= skipped
    assert COVERAGE_WITHHELD in {d.scope for d in degraded}


# ── C10: жива вікі, бюджет спалено на мертві адреси ───────────────────


def test_one_page_with_many_clean_untried_candidates_is_withheld() -> None:
    """C10 magictownehouse.com: 1 сторінка, десятки живих статей не відкрито."""
    links = [f"https://example.com/wiki/article-{i}" for i in range(10)]
    ctx = context(_page("https://example.com/", links))
    state, reasons = assess(collect_evidence(ctx))
    assert state is CoverageState.WITHHELD
    assert "untried_live_candidates" in reasons


# ── C8: суттєвий доказ + матеріальні збої ─────────────────────────────


def test_substantial_sample_with_material_access_failures_keeps_scores_with_a_limitation() -> None:
    """C8 microsoft.com: 22 сторінки не стають невідомими від 29 збоїв 429.

    Бали лишаються — доказ суттєвий. Але обмеження назване, бо воно
    матеріальне: більше десятої частини спроб не відповіло.
    """
    pages = [_page(f"https://example.com/p{i}") for i in range(22)]
    ctx = context(*pages)
    ctx.failed_urls = {f"https://example.com/f{i}": "HTTP 429" for i in range(29)}

    state, reasons = assess(collect_evidence(ctx))
    assert state is CoverageState.LIMITED
    assert reasons == ["access_failures"]

    skipped, partial, degraded = _run(ctx)
    assert Module.SEO not in skipped, "бал лишається"
    assert Module.SEO in partial, "але з явним контекстом обмеження"
    hit = next(d for d in degraded if d.scope == COVERAGE_LIMITED)
    assert hit.reason_params["reasons"] == ["access_failures"]


# ── C7/C9: багато 404, добре прочитаний сайт ──────────────────────────


def test_a_404_heavy_but_well_read_site_is_scored_normally() -> None:
    """scikit-learn.org: 11 сторінок без жодної помилки доступу, 14 биті
    посилання. 404 — оглянутий факт, а не недоступний вміст."""
    pages = [_page(f"https://example.com/p{i}") for i in range(11)]
    ctx = context(*pages)
    ctx.failed_urls = {f"https://example.com/dead{i}": "HTTP 404" for i in range(14)}

    evidence = collect_evidence(ctx)
    assert evidence.access_failures == 0
    assert evidence.observed_dead == 14

    state, _ = assess(evidence)
    assert state is CoverageState.SCORED

    skipped, _partial, degraded = _run(ctx)
    assert Module.SEO not in skipped
    assert not {d.scope for d in degraded} & {COVERAGE_WITHHELD, COVERAGE_LIMITED}


def test_observed_404_and_410_never_reduce_coverage_even_on_a_small_crawl() -> None:
    """Навіть при одній сторінці мертві адреси — не доказ більшого сайту."""
    ctx = context(_page("https://example.com/"))
    ctx.failed_urls = {
        "https://example.com/old": "HTTP 404",
        "https://example.com/gone": "HTTP 410",
    }
    state, reasons = assess(collect_evidence(ctx))
    assert state is CoverageState.SCORED
    assert reasons == ["no_evidence_of_additional_live_content"]


# ── фільтр кандидатів: частина визначення, а не оптимізація ───────────


def test_media_share_and_service_urls_do_not_create_untried_evidence() -> None:
    """splrr.com: усі «кандидати» були jpg; fashion.blog — кнопки share.

    Без фільтра ми рахували б власну неохайність як вміст сайту.
    """
    noise = [
        "https://example.com/wp-content/a.jpg",
        "https://example.com/menu.pdf",
        "https://example.com/?share=facebook",
        "https://example.com/w/index.php?title=X&action=edit",
        "https://example.com/w/index.php?title=X&redlink=1",
        "https://example.com/wp-login",
        "https://example.com/logo.svg",
    ]
    ctx = context(_page("https://example.com/", noise))
    assert clean_untried_candidates(ctx) == []
    state, _reasons = assess(collect_evidence(ctx))
    assert state is CoverageState.SCORED


def test_scheme_and_slash_variants_of_tried_pages_are_not_candidates() -> None:
    """`http://x.jp` і `http://x.jp/` — та сама сторінка."""
    ctx = context(_page("https://www.example.com/about/",
                        ["http://example.com/about", "https://example.com/about"]))
    assert clean_untried_candidates(ctx) == []


def test_looks_like_content_is_the_documented_boundary() -> None:
    assert looks_like_content("https://example.com/wiki/Escapology")
    assert looks_like_content("https://example.com/products?page=2")
    assert not looks_like_content("https://example.com/img/logo.png")
    assert not looks_like_content("https://example.com/?title=X&oldid=5")
    assert not looks_like_content("https://example.com/Special:Cite")


# ── шум не є обмеженням ───────────────────────────────────────────────


def test_one_or_two_incidental_failures_on_a_substantial_crawl_are_not_a_limitation() -> None:
    """ubuntu.com: 25 прочитано, 1 таймаут. Це шум вимірювання.

    На night3 45% позначок припадало б на 1-2 збиті адреси — і позначка,
    яка стоїть скрізь, навчила б читача не вірити їй там, де вона важить.
    """
    pages = [_page(f"https://example.com/p{i}") for i in range(25)]
    ctx = context(*pages)
    ctx.failed_urls = {"https://example.com/f1": "ReadTimeout: timed out",
                       "https://example.com/f2": "HTTP 503"}
    state, _ = assess(collect_evidence(ctx))
    assert state is CoverageState.SCORED

    _, _partial, degraded = _run(ctx)
    assert COVERAGE_LIMITED not in {d.scope for d in degraded}


def test_routine_budget_sampling_creates_no_limitation() -> None:
    """Звичайна вибірка великого сайту — не обмеження покриття.

    Вичерпаний бюджет — наша межа, і про неї вже каже summary.coverage.
    """
    pages = [_page(f"https://example.com/p{i}",
                   [f"https://example.com/more{i}-{j}" for j in range(3)])
             for i in range(25)]
    ctx = context(*pages)
    state, reasons = assess(collect_evidence(ctx, max_pages=25))
    assert state is CoverageState.SCORED
    assert reasons == []


def test_unverified_sitemap_surplus_alone_does_not_withhold() -> None:
    """Оголошення в карті — не доказ живого вмісту, поки не підтверджене.

    Рядок карти буває застарілим чи мертвим; сам-один він лишається
    контекстом. Підтверджений випадок покривається кандидатами з
    посилань — оголошена адреса, яку сайт сам і лінкує.
    """
    ctx = context(_page("https://example.com/"))
    ctx.sitemap.exists = True
    ctx.sitemap.url_count = 2

    evidence = collect_evidence(ctx)
    assert evidence.sitemap_declared == 2, "факт зберігається як контекст"
    state, reasons = assess(evidence)
    assert state is CoverageState.SCORED
    assert reasons == ["no_evidence_of_additional_live_content"]


# ── неоднозначні причини не забирають бал ─────────────────────────────


def test_ambiguous_failures_do_not_count_as_access() -> None:
    """HTTP 400 на дев'ятьох адресах — не привід забрати бал: ми не
    розібрали, що це було, і наш недогляд не стає твердженням про сайт."""
    ctx = context(_page("https://example.com/"))
    ctx.failed_urls = {f"https://example.com/f{i}": "HTTP 400" for i in range(9)}
    evidence = collect_evidence(ctx)
    assert evidence.access_failures == 0
    state, _ = assess(evidence)
    assert state is CoverageState.SCORED


# ── поширення стану по поверхнях ──────────────────────────────────────


def test_the_state_travels_from_context_to_the_public_contract() -> None:
    """ctx -> evidence -> summary -> API: один ланцюг, без другого джерела."""
    import uuid

    from app.audit.orchestrator import rescore
    from app.report.builder import build_report
    from app.report.source import source_from_outcome
    from app.report.web import to_web

    ctx = context(_page("https://example.com/",
                        [f"https://example.com/wiki/a{i}" for i in range(10)]))
    outcome = rescore(ctx)
    document = build_report(source_from_outcome(outcome))
    summary = document.summary["coverage"]
    assert summary["state"] == "withheld"
    assert summary["state_reasons"] == ["untried_live_candidates"]

    result = to_web(
        document,
        audit_id=uuid.uuid4(), site_id=None, status="partial",
        finished_at=None, fallback_locale="uk",
    )
    assert result.summary.coverage.state == "withheld"
    assert result.summary.coverage.state_reasons == ["untried_live_candidates"]
    # факти покриття — і в доказах документа
    facts = document.evidence["coverage_assessment"]
    assert facts["untried_live"] >= 3
    assert facts["observed_dead"] == 0


def test_an_audit_saved_before_coverage_states_reads_as_plain_scored() -> None:
    """Старий аудит без coverage_assessment не падає й не вигадує стан.

    Його деградації лишаються зі старими scope і читаються старими
    рядками каталогу; нового стану в нього немає — отже, "scored" без
    причин, і фронт не показує нічого.
    """
    import uuid

    from app.audit.enums import AuditStatus
    from app.report.builder import build_report
    from app.report.types import ReportSource
    from app.report.web import to_web

    src = ReportSource(
        url="https://old.example", entry_url="https://old.example/",
        origin="https://old.example", overall=60,
        scores={m.value: 60 for m in Module}, issues=[], degraded=[],
        skipped_modules=set(), evidence={}, pages_crawled=5,
        status=AuditStatus.COMPLETED,
    )
    document = build_report(src)
    assert document.summary["coverage"]["state"] == "scored"
    assert document.summary["coverage"]["state_reasons"] == []
    result = to_web(document, audit_id=uuid.uuid4(), site_id=None,
                    status="completed", finished_at=None, fallback_locale="uk")
    assert result.summary.coverage.state == "scored"


# ── G2.1: покриття вирішується раніше за швидкість, яку просили ──────────


def test_a_filtered_audit_still_decides_coverage_before_requested_performance() -> None:
    """Фільтр зі швидкістю не зсуває порядку: покриття, потім вибір, потім провайдер.

    Провайдер не відповів, але час відповіді краулер виміряв сам: швидкість
    лишається в балі неповною — так само, як без фільтра.
    """
    from app.audit.enums import DegradationKind

    ctx = context(_page("https://example.com/"))
    ctx.robots.exists = True
    ctx.robots.disallows_all = True
    degraded: list = []
    options = AuditOptions(modules=set(Module) - {Module.SEO})
    skipped, partial = _module_coverage(options, ctx, [], degraded)

    # Остання прогалина — аналітика (G3): сторінку не рендерили, тож
    # лічильник, доданий скриптом, ми побачити не могли, і висновок про
    # вимірювання лишається неповним.
    assert [(d.scope, d.kind, d.reason_key) for d in degraded] == [
        (COVERAGE_WITHHELD, DegradationKind.COLLECTOR_FAILED, "notice.coverage.withheld"),
        (Module.SEO.value, DegradationKind.MODULE_EXCLUDED, "notice.module.excluded"),
        (Module.PERFORMANCE.value, DegradationKind.PARTIAL_DATA, "notice.performance.no_vitals"),
        ("tech.analytics", DegradationKind.PARTIAL_DATA, "notice.analytics.render_incomplete"),
    ]
    assert {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY} <= skipped
    assert Module.PERFORMANCE not in skipped
    assert {Module.PERFORMANCE, Module.TECH} <= partial
