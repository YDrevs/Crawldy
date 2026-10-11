"""Білдер звіту: групування, пріоритезація, локалізація, прогалини в даних."""

from __future__ import annotations

from dataclasses import replace

from app.audit.enums import AuditStatus, DegradationKind, Effort, Module, Severity
from app.audit.i18n import Locale
from app.audit.types import Degradation, Issue
from app.report.builder import build_report
from app.report.types import NEXT_ACTIONS_LIMIT, ReportSource


def issue(
    *,
    code="seo.canonical",
    msg="seo.canonical.missing",
    key="missing",
    module=Module.SEO,
    severity=Severity.MEDIUM,
    weight=2,
    page_url=None,
    params=None,
    evidence=None,
) -> Issue:
    return Issue(
        code=code,
        module=module,
        severity=severity,
        title="t",
        evidence=evidence or {},
        weight=weight,
        page_url=page_url,
        msg=msg,
        params=params or {},
        key=key,
    )


def source(issues, *, skipped=None, degraded=None, scores=None, overall=50) -> ReportSource:
    return ReportSource(
        url="https://example.com",
        entry_url="https://example.com/",
        origin="https://example.com",
        overall=overall,
        scores=scores if scores is not None else {m.value: 50 for m in Module},
        issues=list(issues),
        degraded=list(degraded or []),
        skipped_modules=set(skipped or ()),
        evidence={},
        pages_crawled=3,
        status=AuditStatus.COMPLETED,
    )


def test_issues_group_into_recommendations_by_issue_key_not_code():
    """Один code може давати різні проблеми — зливати їх в один пункт не можна."""
    issues = [
        issue(key="missing", msg="seo.title.missing", code="seo.title",
              page_url="https://example.com/a"),
        issue(key="missing", msg="seo.title.missing", code="seo.title",
              page_url="https://example.com/b"),
        issue(
            key="too_short",
            msg="seo.title.too_short",
            code="seo.title",
            params={"length": 10, "min": 30, "max": 60},
            page_url="https://example.com/c",
        ),
    ]
    report = build_report(source(issues))

    by_key = {r.issue_key: r for r in report.recommendations}
    assert set(by_key) == {"seo.title:missing", "seo.title:too_short"}
    assert by_key["seo.title:missing"].affected_pages == 2
    assert by_key["seo.title:too_short"].affected_pages == 1
    assert len(report.issues) == 3, "плоский список issues лишається повним"


def test_grouping_survives_a_reworded_message():
    """`msg` — presentation layer: переписаний текст не має розсипати групу.

    Саме тому ключем групування став `issue_key`, а не рядок каталогу.
    """
    issues = [
        issue(key="missing", msg="seo.title.missing", code="seo.title",
              page_url="https://example.com/a"),
        issue(key="missing", msg="seo.title.absent", code="seo.title",
              page_url="https://example.com/b"),
    ]
    report = build_report(source(issues))

    assert len(report.recommendations) == 1
    assert report.recommendations[0].affected_pages == 2


def test_recommendation_carries_page_examples_and_scope():
    issues = [issue(page_url=f"https://example.com/{n}") for n in range(15)]
    site_level = issue(msg="seo.sitemap.missing", code="seo.sitemap")
    report = build_report(source([*issues, site_level]))

    page_rec = next(r for r in report.recommendations if r.msg == "seo.canonical.missing")
    site_rec = next(r for r in report.recommendations if r.msg == "seo.sitemap.missing")

    assert page_rec.scope == "page"
    assert page_rec.affected_pages == 15
    assert len(page_rec.affected_examples) == 10, "прикладів не більше десяти"
    assert site_rec.scope == "site"
    assert site_rec.affected_pages == 0


def test_impact_points_come_from_the_real_scorer():
    """Фікс має піднімати скор рівно настільки, наскільки каже звіт."""
    issues = [
        issue(msg="seo.h1.missing", code="seo.h1", severity=Severity.HIGH, weight=3),
        issue(msg="seo.viewport", code="seo.viewport", severity=Severity.HIGH, weight=3),
    ]
    src = source(issues)
    report = build_report(src)

    from app.audit.scoring import compute_scores

    base, _ = compute_scores(issues)
    for rec in report.recommendations:
        remaining = [i for i in issues if (i.msg or i.code) != rec.msg]
        fixed, _ = compute_scores(remaining)
        assert rec.impact_points == fixed - base


def test_floored_module_still_gets_ranked():
    """Модуль на нулі: заклампаний impact = 0, але пріоритет має лишитися."""
    issues = [
        issue(
            msg=f"ai.k{n}",
            code=f"ai.c{n}",
            module=Module.AI_READY,
            severity=Severity.CRITICAL,
            weight=5,
        )
        # Двадцять, а не вісім: модуль має бути справді на дні, щоб
        # прибирання одного коду не рухало округлений бал. З появою
        # шостого напряму базовий рівень піднявся, і восьми стало замало.
        for n in range(20)
    ]
    report = build_report(source(issues, scores={Module.AI_READY.value: 0}))

    assert all(r.impact_points == 0 for r in report.recommendations)
    assert all(r.floored for r in report.recommendations)
    assert all(r.priority_score > 0 for r in report.recommendations), (
        "без незаклампованого приросту сортувати такий модуль було б нічим"
    )


TWELVE_REAL_KEYS = [
    ("seo.h1", "seo.h1.missing"),
    ("seo.viewport", "seo.viewport"),
    ("seo.canonical", "seo.canonical.missing"),
    ("seo.noindex", "seo.noindex"),
    ("seo.https", "seo.https.missing"),
    ("seo.robots_txt", "seo.robots_txt.missing"),
    ("seo.sitemap", "seo.sitemap.missing"),
    ("seo.broken_links", "seo.broken_links"),
    ("seo.click_depth", "seo.click_depth"),
    ("seo.thin_content", "seo.thin_content"),
    ("seo.image_alt", "seo.image_alt"),
    ("seo.meta_description", "seo.meta_description.missing"),
]


def test_next_actions_are_capped_and_ordered_by_priority():
    issues = [
        issue(code=code, msg=msg, severity=Severity.HIGH, weight=3, params={
            "count": 1, "min": 30, "max": 60, "without_alt": 1, "total": 2,
            "word_count": 10, "threshold": 250, "internal_links": 1,
        })
        for code, msg in TWELVE_REAL_KEYS
    ]
    report = build_report(source(issues))

    assert len(report.next_actions) == NEXT_ACTIONS_LIMIT
    assert [a.rank for a in report.next_actions] == list(range(1, NEXT_ACTIONS_LIMIT + 1))
    order = [r.priority_score for r in report.recommendations]
    assert order == sorted(order, reverse=True)
    assert [a.msg for a in report.next_actions] == [
        r.msg for r in report.recommendations[:NEXT_ACTIONS_LIMIT]
    ]


def test_unknown_message_key_does_not_become_an_action():
    """Ключ без запису в каталозі не має тексту дії — вести його клієнту нікуди."""
    issues = [issue(code="seo.mystery", msg="seo.mystery.unknown", severity=Severity.HIGH)]
    report = build_report(source(issues))

    assert report.recommendations[0].title == "seo.mystery.unknown"
    assert report.next_actions == []


def test_info_severity_never_reaches_next_actions():
    issues = [
        issue(msg="perf.unavailable", code="perf.unavailable", module=Module.PERFORMANCE,
              severity=Severity.INFO, weight=0),
        issue(msg="seo.viewport", code="seo.viewport", severity=Severity.HIGH, weight=3),
    ]
    report = build_report(source(issues))

    assert "perf.unavailable" not in {a.msg for a in report.next_actions}
    assert "perf.unavailable" in {r.msg for r in report.recommendations}, (
        "у повний список він усе одно потрапляє"
    )


def test_effort_is_taken_from_the_check_class():
    """seo.h1 оголошений як LOW, seo.image_alt — як HIGH."""
    issues = [
        issue(msg="seo.h1.missing", code="seo.h1"),
        issue(msg="seo.image_alt", code="seo.image_alt", params={"without_alt": 2, "total": 5}),
    ]
    report = build_report(source(issues))
    efforts = {r.msg: r.effort for r in report.recommendations}

    assert efforts["seo.h1.missing"] is Effort.LOW
    assert efforts["seo.image_alt"] is Effort.HIGH


def test_locale_switches_every_client_facing_string():
    issues = [issue(msg="seo.h1.missing", code="seo.h1", page_url="https://example.com/a")]

    uk = build_report(source(issues), Locale.UK)
    en = build_report(source(issues), Locale.EN)

    assert uk.issues[0].title == "Немає h1 у проаналізованому поданні"
    assert en.issues[0].title == "No h1 in the analysed view"
    assert uk.recommendations[0].action != en.recommendations[0].action
    assert en.next_actions[0].action.startswith("Consider one clear h1")


def test_skipped_module_is_null_not_zero():
    """Немає даних — це не «все погано». Інваріант 5."""
    src = source(
        [issue()],
        skipped={Module.PERFORMANCE},
        scores={m.value: 60 for m in Module if m is not Module.PERFORMANCE},
    )
    document = build_report(src).to_json()

    assert document["speed_score"] is None
    assert document["seo_score"] == 60
    speed = next(s for s in document["scores"] if s["field"] == "speed_score")
    assert speed["excluded"] is True
    assert speed["band"] == "unknown"


def test_active_module_weights_are_renormalised_when_one_is_skipped():
    src = source([issue()], skipped={Module.PERFORMANCE})
    document = build_report(src).to_json()

    from app.audit.scoring import MODULE_WEIGHT

    active = [s for s in document["scores"] if not s["excluded"]]
    # Доступність показується знімком, а не балом, тож у таблиці її немає.
    # Вклад у загальний бал вона при цьому досі має — саме тому видимі
    # ваги сходяться не до 1.0, а до 1.0 без її частки. Це проміжний
    # стан: коли вага доступності стане нулем, сума знову буде 1.0.
    from app.audit.scoring import active_weights

    hidden = active_weights({Module.PERFORMANCE}).get(Module.ACCESSIBILITY, 0.0)
    visible = sum(s["effective_weight"] for s in active)
    # Ваги у звіті округлені до чотирьох знаків для читача, тож їхня сума
    # не мусить сходитись до останнього біта — важливо, що вони справді
    # перерозподілені, а не лишились початковими.
    assert abs(visible - (1.0 - hidden)) < 0.001
    assert not any(s["field"] == "accessibility_score" for s in document["scores"])
    seo = next(s for s in active if s["field"] == "seo_score")
    assert seo["weight"] == MODULE_WEIGHT[Module.SEO]
    assert seo["effective_weight"] > seo["weight"], "вага перерозподілена, а не збережена"


def test_missing_data_explains_which_report_field_suffered():
    degraded = [
        Degradation(
            scope="performance",
            kind=DegradationKind.PROVIDER_UNAVAILABLE,
            reason="429 Too Many Requests",
            affected_modules=[Module.PERFORMANCE],
        )
    ]
    src = source([issue()], skipped={Module.PERFORMANCE}, degraded=degraded)
    entry = build_report(src).to_json()["missing_data"][0]

    assert entry["kind"] == "provider_unavailable"
    assert entry["affects"] == ["speed_score"]
    assert "429" in entry["reason"]
    # Тест довго вимагав тут українського рядка — і проходив на
    # англомовному звіті рівно тому, що приписка була зашита однією
    # мовою. Перевіряємо мову звіту, а не конкретне формулювання.
    assert "excluded" in entry["note"].lower()
    assert "виключено" in build_report(src, Locale.UK).to_json()["missing_data"][0]["note"]


def test_report_json_has_every_field_the_roadmap_promises():
    required = {
        "overall_score",
        "speed_score",
        "seo_score",
        "ai_ready_score",
        "llm_visibility_score",
        "issues",
        "recommendations",
        "evidence",
        "missing_data",
        "next_actions",
    }
    document = build_report(source([issue()])).to_json()

    assert required <= set(document)


def test_summary_marks_impacts_as_non_additive():
    """Клієнт не має сумувати impact_points — вони незалежні."""
    document = build_report(source([issue()])).to_json()
    assert document["summary"]["impact_is_independent"] is True


# --- пріоритет і впевненість ---------------------------------------------


def _recs(issues):
    from app.audit.scoring import compute_scores
    from app.report import build_report
    from app.report.types import ReportSource

    overall, scores = compute_scores(issues)
    return build_report(ReportSource(
        url="https://e.com", entry_url="https://e.com/", origin="https://e.com",
        overall=overall, scores=scores, issues=issues, degraded=[],
        skipped_modules=set(), evidence={},
    ))


def test_a_cheap_cosmetic_fix_never_outranks_a_critical_one():
    """На furniturerow.com рекомендацією номер один стояла відсутня
    Twitter-картка при Lighthouse 25 і TBT понад три секунди. Обидві
    знахідки правильні, але порядок між ними був неправильний — а клієнт
    читає перші три рядки."""
    from app.audit.enums import Module, Severity
    from app.audit.types import Issue

    cheap = [
        Issue(code="ai.twitter_card", module=Module.AI_READY, severity=Severity.LOW,
              title="", msg="ai.twitter_card", weight=1, page_url=f"https://e.com/p{n}")
        for n in range(20)
    ]
    grave = Issue(code="perf.core_web_vitals", module=Module.PERFORMANCE,
                  severity=Severity.CRITICAL, title="", msg="perf.core_web_vitals.tbt",
                  params={"value": 3200, "unit": "ms", "strategy": "mobile", "threshold": 200},
                  weight=4)

    document = _recs([*cheap, grave])
    order = [r.msg for r in document.recommendations]

    assert order.index("perf.core_web_vitals.tbt") < order.index("ai.twitter_card")


def test_a_guess_does_not_stand_above_a_measurement():
    """Судження моделі може бути правильним, але ставити його попереду
    виміряного факту не можна."""
    from app.audit.enums import Confidence, Module, Severity
    from app.audit.types import Issue

    guess = Issue(code="llm.unstated_facts", module=Module.LLM_VISIBILITY,
                  severity=Severity.HIGH, title="", msg="llm.unstated_facts.pricing",
                  weight=3, confidence=Confidence.MEDIUM)
    fact = Issue(code="seo.h1", module=Module.SEO, severity=Severity.HIGH,
                 title="", msg="seo.h1.missing", weight=3, page_url="https://e.com/")

    order = [r.msg for r in _recs([guess, fact]).recommendations]

    assert order.index("seo.h1.missing") < order.index("llm.unstated_facts.pricing")


def test_a_low_confidence_guess_stays_out_of_the_first_steps():
    """Повний перелік його зберігає — у «Що робити першим» він не йде: за
    цим списком клієнт починає витрачати гроші."""
    from app.audit.enums import Confidence, Module, Severity
    from app.audit.types import Issue

    shaky = Issue(code="llm.unstated_facts", module=Module.LLM_VISIBILITY,
                  severity=Severity.HIGH, title="", msg="llm.unstated_facts.offering",
                  weight=3, confidence=Confidence.LOW)

    document = _recs([shaky])

    assert any(r.msg == "llm.unstated_facts.offering" for r in document.recommendations)
    assert not any(a.msg == "llm.unstated_facts.offering" for a in document.next_actions)


def test_a_recommendation_is_as_firm_as_its_weakest_evidence():
    from app.audit.enums import Confidence, Module, Severity
    from app.audit.types import Issue

    group = [
        Issue(code="seo.h1", module=Module.SEO, severity=Severity.HIGH, title="",
              msg="seo.h1.missing", weight=3, page_url="https://e.com/a"),
        Issue(code="seo.h1", module=Module.SEO, severity=Severity.HIGH, title="",
              msg="seo.h1.missing", weight=3, page_url="https://e.com/b",
              confidence=Confidence.MEDIUM),
    ]

    rec = next(r for r in _recs(group).recommendations if r.msg == "seo.h1.missing")

    assert rec.confidence is Confidence.MEDIUM


def test_a_problem_on_an_important_page_outranks_the_same_problem_on_a_forgotten_one():
    """Дві однакові знахідки різняться лише сторінкою — і порядок це бачить.

    Досі знахідка на головній і на забутій сторінці третього рівня важили
    в пріоритеті однаково, хоча коштують клієнту різного.
    """
    report = build_report(
        source(
            [
                # Знахідка на забутій сторінці має алфавітну перевагу в
                # тайбрейку: якщо важливість не враховувати, вона стане
                # першою. Саме так тест і розрізняє два порядки.
                issue(
                    msg="seo.canonical.missing",
                    code="seo.canonical",
                    page_url="https://example.com/forgotten/",
                    evidence={"page_importance": 0.05},
                ),
                issue(
                    msg="seo.h1.missing",
                    code="seo.h1",
                    page_url="https://example.com/",
                    evidence={"page_importance": 1.0},
                ),
            ]
        ),
        Locale.UK,
    )
    order = [r.msg for r in report.recommendations]
    assert order.index("seo.h1.missing") < order.index("seo.canonical.missing")


def test_importance_is_the_highest_page_of_the_group_not_the_average():
    """Проблема, що є і на головній, лишається проблемою головної."""
    report = build_report(
        source(
            [
                issue(
                    msg="seo.h1.missing",
                    code="seo.h1",
                    page_url="https://example.com/",
                    evidence={"page_importance": 1.0},
                ),
                issue(
                    msg="seo.h1.missing",
                    code="seo.h1",
                    page_url="https://example.com/deep/",
                    evidence={"page_importance": 0.02},
                ),
            ]
        ),
        Locale.UK,
    )
    assert report.recommendations[0].page_importance == 1.0


def test_site_wide_finding_loses_nothing_to_page_importance():
    """У знахідки про сайт загалом сторінки немає — і карати її ні за що."""
    report = build_report(
        source([issue(msg="seo.robots_txt.missing", code="seo.robots_txt")]),
        Locale.UK,
    )
    assert report.recommendations[0].page_importance is None


# ── звіт не стверджує того, чого не бачив ──────────────────────────────────


def _blind(issues, **kwargs) -> ReportSource:
    """Краул не приніс жодної сторінки: контентні модулі виключені зі скора."""
    return source(
        issues,
        skipped={Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY},
        degraded=[
            Degradation(
                scope="crawl",
                kind=DegradationKind.COLLECTOR_FAILED,
                reason="сайт не віддав жодної сторінки з контентом (статуси відповіді: [403])",
                affected_modules=[Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY],
            )
        ],
        overall=None,
        **kwargs,
    )


def test_blind_crawl_drops_claims_about_content_we_never_read():
    """unilever.com віддав 403 на все й отримав тринадцять тверджень про себе.

    Бал ми притримали чесно, а зміст — ні. Якщо даних не досить для бала
    модуля, їх не досить і для його тверджень.
    """
    report = build_report(
        _blind(
            [
                issue(code="llm.about_page", msg="llm.about_page", module=Module.LLM_VISIBILITY),
                issue(code="seo.sitemap", msg="seo.sitemap.missing"),
                issue(code="tech.crawler_blocked", msg="tech.crawler_blocked", module=Module.TECH),
            ]
        )
    )
    codes = {i.code for i in report.issues}
    assert codes == {"tech.crawler_blocked"}, "лишається те, що ми справді бачили"


def test_blind_crawl_keeps_what_the_response_itself_proves():
    """Недійсний сертифікат видно з відповіді сервера, а не зі сторінки.

    На badssl це була єдина знахідка, заради якої звіт узагалі вартий
    читання, — і вона в модулі SEO, тобто серед виключених.
    """
    report = build_report(
        _blind(
            [
                issue(code="seo.https", msg="seo.https.invalid_cert", severity=Severity.CRITICAL),
                issue(code="seo.sitemap", msg="seo.sitemap.missing"),
            ]
        )
    )
    assert {i.code for i in report.issues} == {"seo.https"}


def test_a_partly_failed_crawl_keeps_its_findings():
    """Прочитали меншість адрес — але прочитане бачили. Викидати нема за що:
    низьке покриття вже знижує впевненість окремо."""
    src = source(
        [issue(code="seo.sitemap", msg="seo.sitemap.missing")],
        skipped={Module.SEO},
        degraded=[
            Degradation(
                scope="crawl.failures",
                kind=DegradationKind.COLLECTOR_FAILED,
                reason="не відповіли 19 адрес із 25",
                affected_modules=[Module.SEO],
            )
        ],
    )
    assert [i.code for i in build_report(src).issues] == ["seo.sitemap"]


def test_a_healthy_audit_keeps_every_finding():
    report = build_report(source([issue(), issue(code="tech.nap", module=Module.TECH)]))
    assert len(report.issues) == 2


# ── покриття поруч із балом ────────────────────────────────────────────────


def test_summary_says_how_much_of_the_site_we_read():
    """asana.com — 20 сторінок із 3407 і бал 59, поданий так само впевнено,
    як бал за сайтом, прочитаним повністю."""
    src = source([issue()])
    src.evidence = {
        "crawl": {"pages_ok": 20, "pages_total": 22, "pages_failed": 2},
        "sitemap_xml": {"url_count": 3407},
    }
    coverage = build_report(src).summary["coverage"]

    assert coverage["pages_read"] == 20
    assert coverage["pages_failed"] == 2
    assert coverage["pages_known"] == 3407
    assert coverage["share"] < 0.01


def test_coverage_without_a_sitemap_measures_against_what_we_found():
    """Карти немає — рівняємось на знайдене, інакше покриття завжди 100%."""
    src = source([issue()])
    src.evidence = {"crawl": {"pages_ok": 7, "pages_total": 7, "pages_failed": 0}}
    coverage = build_report(src).summary["coverage"]

    assert coverage["pages_known"] == 7
    assert coverage["share"] == 1.0


# ── E-05: застосовність у доказі, у підсумку й у пройдених ─────────────

import uuid  # noqa: E402

from app.audit import applicability  # noqa: E402
from app.audit.applicability import ClaimVerdict, Coverage  # noqa: E402
from app.audit.checks import REGISTRY  # noqa: E402
from app.audit.site_context import _parse_robots  # noqa: E402
from app.audit.types import RobotsInfo  # noqa: E402
from app.report.builder import build_evidence  # noqa: E402
from app.report.passed import PassState, collect_passed, evaluate_all  # noqa: E402
from app.report.web import to_web  # noqa: E402
from tests.factories import context, page_from_html  # noqa: E402

_PROSE = "<p>%s</p>" % ("Текст сторінки, якого досить для судження. " * 10)


def _e05_page(url: str, *, title: str = "Заголовок сторінки про послугу"):
    page = page_from_html(
        f'<html lang="uk"><head><title>{title}</title></head>'
        f'<body><h1>{title}</h1>{_PROSE}</body></html>', url=url)
    page.status_code = 200
    return page


def _e05_robots(*disallow: str) -> RobotsInfo:
    lines = ["User-agent: *", *(f"Disallow: {p}" for p in disallow)] if disallow else [
        "User-agent: *", "Allow: /"]
    info = RobotsInfo(status_code=200, content=chr(10).join(lines) + chr(10))
    info.exists = True
    _parse_robots(info)
    return info


def _e05_site(n_content: int = 3, *, funnels: tuple[str, ...] = ("/login", "/checkout")):
    pages = [_e05_page(f"https://example.com/guide-{i}", title=f"Посібник номер {i} про аудит")
             for i in range(n_content)]
    pages += [_e05_page(f"https://example.com{path}", title="") for path in funnels]
    return context(*pages, robots=_e05_robots(*funnels))


def test_applicability_evidence_is_written_for_every_declared_claim():
    """Доказ несе стан КОЖНОЇ претензії, а не лише тих, що спрацювали."""
    evidence = build_evidence(_e05_site())
    block = evidence["applicability"]
    assert block, "блок застосовності порожній"
    assert set(applicability.CHECK_DECLARATIONS) <= {row["check"] for row in block.values()}
    row = block["seo.canonical:missing"]
    assert set(row) == {
        "check", "variant", "claim_class", "aggregation_strategy", "evaluated", "failed",
        "not_applicable", "no_verdict", "not_measured", "verdict", "coverage", "rules", "examples",
    }
    assert row["evaluated"] == 3 and row["not_applicable"] == 2


def test_applicability_evidence_is_bounded_and_ordered_deterministically():
    """≤5 прикладів на стан, порядок незалежний від обходу.

    Доказ, чий порядок залежить від того, в якому порядку краул приніс
    сторінки, не можна порівняти із самим собою між прогонами — а саме
    для порівняння його й зберігають.
    """
    site = _e05_site(n_content=9)
    block = build_evidence(site)["applicability"]
    examples = block["seo.canonical:missing"]["examples"]
    assert len(examples["evaluated"]) == applicability.EVIDENCE_CAP == 5
    assert len(examples["not_applicable"]) == 2
    assert examples["evaluated"] == sorted(examples["evaluated"])
    # Той самий контекст, інший порядок сторінок — той самий доказ.
    shuffled = context(*reversed(site.pages), robots=site.robots)
    assert build_evidence(shuffled)["applicability"] == block


def test_a_check_with_no_applicable_page_never_enters_passed_checks():
    """E05-f6 з боку звіту: нуль судимих сторінок — нуль похвали.

    Це та сама межа, що й «порожній результат чека не означає все добре»,
    але доведена вже не тишею чека, а канонічним станом.
    """
    evidence = build_evidence(_e05_site(n_content=0))
    row = evidence["applicability"]["ai.jsonld.missing"]
    assert row["evaluated"] == 0
    # Не `NOT_APPLICABLE`, а `FAIL`: порожній випадок цього чека контракт
    # називає `FAIL_IF_COMPLETE` — сайт, у якого немає жодної сторінки,
    # придатної нести розмітку, розмітки таки не має. Важливо тут інше:
    # у пройдені він не потрапляє в ЖОДНОМУ з двох станів.
    assert row["verdict"] == ClaimVerdict.FAIL
    # Оцінювач сам по собі сказав би «пройдено»: розмітку в доказі видно.
    evidence["structured_data"] = {"pages_with_jsonld": 2, "pages_total": 2}
    assert "ai.jsonld" not in {p.key for p in collect_passed(evidence, set())}
    assert evaluate_all(evidence, set())["ai.jsonld"] is PassState.NO_VERDICT
    # А там, де сторінки для судження є, той самий доказ дає пройдене.
    with_content = build_evidence(_e05_site(n_content=2))
    with_content["structured_data"] = {"pages_with_jsonld": 2, "pages_total": 2}
    assert "ai.jsonld" in {p.key for p in collect_passed(with_content, set())}


def test_pass_with_partial_coverage_is_never_eligible_in_any_strategy():
    """PASS + PARTIAL не проходить у жодній стратегії агрегації.

    «На тому, що прочитали, не знайшли» — не те саме, що «перевірили»,
    і екзистенційні чеки винятку не мають: їхній PASS уже означає
    COMPLETE за побудовою.
    """
    evidence = {
        "robots_txt": {"exists": True, "status_code": 200},
        "applicability": {"seo.robots_txt": {
            "check": "seo.robots_txt", "variant": "", "verdict": ClaimVerdict.PASS,
            "coverage": Coverage.PARTIAL, "evaluated": 4,
        }},
    }
    assert [p.key for p in collect_passed(evidence, set())] == []
    assert evaluate_all(evidence, set())["seo.robots_txt"] is PassState.NO_VERDICT
    evidence["applicability"]["seo.robots_txt"]["coverage"] = Coverage.COMPLETE
    assert [p.key for p in collect_passed(evidence, set())] == ["seo.robots_txt"]


def test_an_audit_taken_before_e05_keeps_the_passed_checks_it_had():
    """Старий знімок блока не має — і не має вигадувати собі стану.

    Правило застосовності може лише притримати успіх. Там, де стану немає
    взагалі, рішення лишається за оцінювачем, як було до цієї хвилі.
    """
    old = {
        "http": {"origin": "https://example.com", "is_https": True, "tls_error": None},
        "robots_txt": {"exists": True, "status_code": 200},
    }
    assert {p.key for p in collect_passed(old, set())} == {"seo.https", "seo.robots_txt"}


def test_summary_applicability_counts_claims_not_policy_cells():
    """Підсумок по модулях: одиниця — претензія, а не клітинка політики.

    Блок доказу несе і рядок чека, і рядок кожного варіанта; порахувати
    обидва означало б показати читачеві клітинки політики там, де
    перевірок рівно стільки, скільки оголошено.

    Числа тут навмисно немає. Воно стояло — 81, — і G6 зробило його
    хибним, вилучивши `ai.schema.faq` зі скорингу. Замінити одну магічну
    константу на іншу означало б чекати наступного вилучення; тому
    підсумок звіряється з ЖИВОЮ таблицею оголошень, а та — з живим
    реєстром. Те, що саме зникло, стереже окремий assert нижче: без
    нього рівність трьох похідних чисел лишилась би правдивою і після
    випадкового видалення будь-якого іншого чека.
    """
    document = build_report(source([]))
    document.evidence = build_evidence(_e05_site())
    result = to_web(document, audit_id=uuid.uuid4(), site_id=None, status="completed",
                    finished_at=None, fallback_locale="uk")
    totals = result.summary.applicability
    assert totals, "підсумок застосовності порожній"
    active = len(applicability.CHECK_DECLARATIONS)
    assert sum(t.checks for t in totals.values()) == active
    assert {c.code for c in REGISTRY} == set(applicability.CHECK_DECLARATIONS), (
        "оголошення розійшлися з реєстром"
    )
    assert "ai.schema.faq" not in applicability.CHECK_DECLARATIONS, (
        "вилучений у G6 чек повернувся в таблицю оголошень"
    )
    # Число тут стоїть ПІСЛЯ трьох рівностей вище, а не замість них: воно
    # називає прийняту 81 мінус рівно один поіменований рядок. Зникне ще
    # щось — упадуть обидва твердження, і те, що вище, скаже, що саме.
    assert active == 81 - 1
    seo = totals[Module.SEO.value]
    assert seo.evaluated and seo.not_applicable
    assert sum(seo.verdicts.values()) == seo.checks
    assert sum(seo.coverage.values()) == seo.checks


def test_summary_applicability_is_empty_for_an_audit_without_the_block():
    """Порожньо означає «не рахували», а не «вийшов нуль»."""
    document = build_report(source([]))
    result = to_web(document, audit_id=uuid.uuid4(), site_id=None, status="completed",
                    finished_at=None, fallback_locale="uk")
    assert result.summary.applicability == {}


def test_finalised_evidence_carries_the_findings_into_the_verdict():
    """Вердикт дописується там, де знахідки стають відомі — в обох шляхах.

    `build_evidence` рахує застосовність із контексту, де знахідок ще
    немає. Свіжий аудит і звіт, перебудований з бази, мусять отримати той
    самий блок, інакше збережений звіт розійшовся б зі щойно знятим.
    """
    evidence = build_evidence(_e05_site())
    assert evidence["applicability"]["seo.canonical:missing"]["verdict"] == ClaimVerdict.PASS
    found = issue(code="seo.canonical", key="missing", msg="seo.canonical.missing",
                  page_url="https://example.com/guide-0")
    base = source([found])
    rebuilt = build_report(replace(base, evidence=evidence))
    row = rebuilt.evidence["applicability"]["seo.canonical:missing"]
    assert row["failed"] == 1
    assert row["verdict"] == ClaimVerdict.FAIL
