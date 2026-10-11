"""Чеки швидкості, які працюють без зовнішнього провайдера."""

from __future__ import annotations

import asyncio

import httpx
import pytest

from app.audit.checks.performance import (
    CoreWebVitalsCheck,
    MobileGapCheck,
    ServerResponseCheck,
)
from app.audit.enums import Severity
from app.audit.performance import lighthouse as lighthouse_module
from app.audit.performance import psi as psi_module
from app.audit.types import (
    MetricValue,
    PageSignals,
    PerformanceResult,
    SiteContext,
    Strategy,
)


def ctx(*response_ms: int) -> SiteContext:
    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.pages = [
        PageSignals(url=f"https://example.com/{n}", status_code=200, response_ms=ms)
        for n, ms in enumerate(response_ms)
    ]
    return site


def run(*response_ms: int):
    return list(ServerResponseCheck().run(ctx(*response_ms)))


def test_fast_server_produces_no_issue():
    assert run(120, 200, 310) == []


def test_slow_server_is_flagged_medium():
    issues = run(900, 1000, 1100)

    assert len(issues) == 1
    assert issues[0].msg == "perf.server_response.slow"
    assert issues[0].severity is Severity.MEDIUM
    assert issues[0].params["median"] == 1000


def test_very_slow_server_escalates_to_high():
    issues = run(2000, 2500, 3000)

    assert issues[0].msg == "perf.server_response.very_slow"
    assert issues[0].severity is Severity.HIGH


def test_median_ignores_a_single_outlier():
    """Одна повільна сторінка не має характеризувати весь сайт."""
    assert run(100, 120, 140, 160, 9000) == []


def test_evidence_names_the_slowest_page():
    issues = run(900, 1000, 4000)
    evidence = issues[0].evidence

    assert evidence["slowest_ms"] == 4000
    assert evidence["slowest_url"] == "https://example.com/2"
    assert evidence["pages_measured"] == 3
    assert evidence["source"] == "crawler", "видно, що це наше вимірювання, а не PSI"


def test_pages_without_timing_are_ignored():
    assert run(0, 0, 0) == []


def test_only_successful_pages_are_measured():
    site = ctx(2000, 2000)
    site.pages[0].status_code = 500
    site.pages[1].response_ms = 100

    assert list(ServerResponseCheck().run(site)) == []


# ── вимірювання має пріоритет над евристикою ───────────────────────────────


def _ctx_with_cls(rating: str | None, images_without_dimensions: int = 10):
    from app.audit.types import MetricValue, PerformanceResult, Strategy

    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    page = PageSignals(url="https://example.com/", status_code=200)
    page.images_total = 12
    page.images_without_dimensions = images_without_dimensions
    site.pages = [page]
    if rating is not None:
        site.performance = [
            PerformanceResult(
                provider="psi",
                strategy=Strategy.MOBILE,
                url="https://example.com/",
                fetched=True,
                lab={"CLS": MetricValue(0.0, "", rating)},
            )
        ]
    return site


def test_measured_good_cls_silences_the_dimensions_heuristic():
    """Розміри зображень — передвісник CLS. Якщо CLS виміряний і нульовий,
    передвісник не спрацював, і карати нема за що."""
    from app.audit.checks.performance import ImageOptimizationCheck

    issues = [i.msg for i in ImageOptimizationCheck().run(_ctx_with_cls("good"))]
    assert "perf.images.no_dimensions" not in issues


def test_poor_cls_keeps_the_dimensions_finding():
    from app.audit.checks.performance import ImageOptimizationCheck

    issues = [i.msg for i in ImageOptimizationCheck().run(_ctx_with_cls("poor"))]
    assert "perf.images.no_dimensions" in issues


def test_unmeasured_cls_keeps_the_heuristic_as_the_only_signal():
    from app.audit.checks.performance import ImageOptimizationCheck

    issues = [i.msg for i in ImageOptimizationCheck().run(_ctx_with_cls(None))]
    assert "perf.images.no_dimensions" in issues


# ── розрив між телефоном і комп'ютером ─────────────────────────────────────


def _perf(strategy: Strategy, score: float, lcp: float) -> PerformanceResult:
    return PerformanceResult(
        provider="psi",
        strategy=strategy,
        url="https://example.com/",
        fetched=True,
        lighthouse_score=score,
        lab={"LCP": MetricValue(lcp, "ms", "poor" if lcp > 4000 else "good")},
    )


def _both(mobile: float, desktop: float, *, mobile_lcp=5000.0, desktop_lcp=1200.0):
    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.performance = [
        _perf(Strategy.MOBILE, mobile, mobile_lcp),
        _perf(Strategy.DESKTOP, desktop, desktop_lcp),
    ]
    return site


def test_fast_desktop_and_slow_mobile_is_reported():
    """Власник дивиться з ноутбука й не бачить проблеми, яку бачать клієнти."""
    issues = list(MobileGapCheck().run(_both(mobile=40, desktop=90)))

    assert len(issues) == 1
    assert issues[0].params["mobile"] == 40
    assert issues[0].evidence["worst_on_mobile"][0]["metric"] == "LCP"


def test_slow_on_both_is_not_a_device_problem():
    """Це вже сказали чеки Core Web Vitals — дублювати нема сенсу."""
    assert list(MobileGapCheck().run(_both(mobile=35, desktop=45))) == []


def test_small_gap_is_normal():
    """Мобільний завжди трохи гірший: інше залізо, інша мережа."""
    assert list(MobileGapCheck().run(_both(mobile=78, desktop=92))) == []


def test_one_strategy_alone_gives_nothing_to_compare():
    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.performance = [_perf(Strategy.MOBILE, 30, 6000.0)]

    assert list(MobileGapCheck().run(site)) == []


def test_core_web_vitals_counts_the_mobile_measurement_once():
    """Дві стратегії не мають подвоювати штраф за ту саму повільність."""
    issues = list(CoreWebVitalsCheck().run(_both(mobile=40, desktop=90)))

    assert [i.evidence["strategy"] for i in issues] == ["mobile"]


def _page_from_html(html: str):
    from tests.factories import page_from_html

    return page_from_html(html)


def _site(page):
    from tests.factories import context

    return context(page)


def test_vector_icons_do_not_demand_srcset():
    """SVG масштабується сам — набір розмірів для нього безглуздий.

    На головній ahrefs.com зі 133 зображень 120 були SVG, і чек карав
    сайт саме за те, що він робить правильно.
    """
    from app.audit.checks.performance import ResponsiveImagesCheck

    page = _page_from_html("<html><body><h1>x</h1></body></html>")
    page.images_total = 133
    page.images_by_format = {"svg": 120, "png": 3, "jpg": 1}
    page.images_with_srcset = 0
    assert not list(ResponsiveImagesCheck().run(_site(page)))


def test_many_photos_without_srcset_are_still_a_finding():
    from app.audit.checks.performance import ResponsiveImagesCheck

    page = _page_from_html("<html><body><h1>x</h1></body></html>")
    page.images_total = 20
    page.images_by_format = {"jpg": 12, "svg": 8}
    page.images_with_srcset = 0
    issues = list(ResponsiveImagesCheck().run(_site(page)))
    assert len(issues) == 1
    assert issues[0].evidence["raster_images"] == 12


def _measured(**metrics) -> SiteContext:
    """Вимірювання, де вказано, що прийшло з поля, а що з лабораторії."""
    from app.audit.types import PerformanceResult

    result = PerformanceResult(
        provider="psi", strategy=Strategy.MOBILE, url="https://example.com/", fetched=True
    )
    for name, (value, rating, field) in metrics.items():
        metric = MetricValue(value=value, unit="ms", rating=rating)
        result.lab[name] = metric
        if field:
            result.field_data[name] = metric
    ctx = ctx_with(result)
    return ctx


def ctx_with(result) -> SiteContext:
    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.performance = [result]
    return site


def test_lab_diagnostics_are_not_graded_critical():
    """TBT і TTFB пояснюють причину, але їх не переживає користувач.

    На вибірці всі дванадцять критичних TBT були лабораторними, тоді як
    INP тих самих сайтів, виміряний на живих людях, не був критичним
    жодного разу.
    """
    issues = list(CoreWebVitalsCheck().run(_measured(TBT=(2000.0, "poor", False))))
    assert [i.severity.value for i in issues] == ["high"]
    assert issues[0].confidence.value == "medium"


def test_a_real_vital_is_still_critical():
    issues = list(CoreWebVitalsCheck().run(_measured(LCP=(9000.0, "poor", True))))
    assert [i.severity.value for i in issues] == ["critical"]
    assert issues[0].confidence.value == "high"


def test_the_lab_proxy_steps_aside_for_the_real_measurement():
    """Коли INP виміряний на людях, TBT каже про те саме, лише гірше."""
    ctx = _measured(INP=(400.0, "needs-improvement", True), TBT=(2000.0, "poor", False))
    metrics = {i.evidence["metric"] for i in CoreWebVitalsCheck().run(ctx)}
    assert metrics == {"INP"}


def test_a_page_that_does_not_fit_the_read_limit_is_reported():
    """myfriendlythai.ca: головна ресторану на пʼять мегабайтів.

    У тексті — тисячі спам-коментарів із чужими посиланнями. Аудит це
    прочитав і не сказав нічого: ваги сторінки не перевіряв ніхто.
    """
    from app.audit.checks.performance import PageWeightCheck
    from app.core.config import settings

    page = _page_from_html("<html><body><h1>x</h1></body></html>")
    page.html_bytes = settings.max_response_bytes
    page.word_count = 111028
    issues = list(PageWeightCheck().run(_site(page)))
    assert len(issues) == 1
    assert issues[0].severity.value == "high"
    assert issues[0].evidence["truncated"] is True


def test_a_merely_heavy_page_is_reported_more_softly():
    from app.audit.checks.performance import PageWeightCheck

    page = _page_from_html("<html><body><h1>x</h1></body></html>")
    page.html_bytes = 3 * 1024 * 1024
    issues = list(PageWeightCheck().run(_site(page)))
    assert [i.severity.value for i in issues] == ["medium"]
    assert issues[0].evidence["truncated"] is False


def test_an_ordinary_page_weight_is_not_a_finding():
    """Сотні кілобайт розмітки — це звичайна сторінка, а не проблема."""
    from app.audit.checks.performance import PageWeightCheck

    page = _page_from_html("<html><body><h1>x</h1></body></html>")
    page.html_bytes = 800 * 1024
    assert not list(PageWeightCheck().run(_site(page)))


# ── число в заголовку читає людина ─────────────────────────────────────────


def _with_metric(name: str, value: float, unit: str) -> SiteContext:
    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.pages = [PageSignals(url="https://example.com/", status_code=200)]
    site.performance = [
        PerformanceResult(
            provider="psi",
            strategy=Strategy.MOBILE,
            url="https://example.com/",
            fetched=True,
            lab={name: MetricValue(value, unit, "poor")},
        )
    ]
    return site


def test_metric_title_reads_as_a_sentence_not_as_a_dump():
    """`LCP = 4126.042ms` — це дамп провайдера, а не текст для клієнта.

    Три знаки після коми обіцяють точність до мікросекунди там, де сама
    величина гуляє на сотні мілісекунд між вимірюваннями. Знайдено
    читанням згенерованого екрана: у Word-звіт це йшло так само.
    """
    from app.audit.i18n import Locale, render

    issue = next(iter(CoreWebVitalsCheck().run(_with_metric("LCP", 4126.042, "ms"))))
    title = render(issue.msg, issue.params, Locale.EN).title

    assert "4126.042" not in title
    assert "4.1" in title, title
    assert title.startswith("LCP = 4.1")


def test_sub_second_metrics_stay_in_milliseconds():
    """344 мс — не «0.3 s»: на цій шкалі десята частка секунди груба."""
    issue = next(iter(CoreWebVitalsCheck().run(_with_metric("INP", 344.0, "ms"))))

    assert issue.params["value"] == "344"
    assert issue.params["unit"].strip() == "ms"


def test_the_dimensionless_metric_keeps_its_decimals():
    """CLS живе в діапазоні 0..1, і округлення до цілого стерло б його."""
    issue = next(iter(CoreWebVitalsCheck().run(_with_metric("CLS", 0.25, ""))))

    assert issue.params["value"] == "0.25"
    assert issue.params["unit"] == ""


def test_evidence_keeps_the_exact_number_the_title_rounds():
    """Доказ має бути точним, заголовок — зрозумілим. Це різні вимоги."""
    issue = next(iter(CoreWebVitalsCheck().run(_with_metric("LCP", 4126.042, "ms"))))

    assert issue.evidence["value"] == 4126.042


def test_units_do_not_break_away_from_their_number():
    """Нерозривний пробіл: «4.1» на одному рядку й «s» на наступному —
    це вже інше число."""
    issue = next(iter(CoreWebVitalsCheck().run(_with_metric("LCP", 4126.042, "ms"))))

    assert issue.params["unit"].startswith("\u00a0")


# ── E-08: провайдери й категорія доступності ──────────────────────────
#
# Сайдкар Lighthouse повертає `accessibility` тим самим запитом, що й
# швидкість, і до 9 вересня 2026 движок цю категорію мовчки викидав:
# напрям доступності на цьому провайдері не існував узагалі. Тести нижче
# судять самі провайдери, а не парсер: між відповіддю й полями стоїть
# `measure()`, і саме там була вада.

class _StubResponse:
    def __init__(self, payload: object, status: int, text: str) -> None:
        self.status_code = status
        self.text = text
        self._payload = payload

    def json(self) -> object:
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class _StubClient:
    def __init__(self, owner: _StubHttpx) -> None:
        self._owner = owner

    async def __aenter__(self) -> _StubClient:
        return self

    async def __aexit__(self, *exc: object) -> bool:
        return False

    async def _respond(self) -> _StubResponse:
        self._owner.calls += 1
        if self._owner.raises is not None:
            raise self._owner.raises
        return _StubResponse(self._owner.payload, self._owner.status, self._owner.text)

    async def post(self, url: str, json: object = None) -> _StubResponse:
        return await self._respond()

    async def get(self, url: str, params: object = None) -> _StubResponse:
        return await self._respond()


class _StubHttpx:
    """Стоїть замість модуля `httpx` у провайдері.

    Мережі немає, а класи винятків — справжні: провайдер ловить саме
    `httpx.HTTPError`, і підміна його заглушкою перевіряла б заглушку.
    """

    HTTPError = httpx.HTTPError

    def __init__(
        self,
        payload: object = None,
        *,
        status: int = 200,
        text: str = "",
        raises: Exception | None = None,
    ) -> None:
        self.payload = payload
        self.status = status
        self.text = text
        self.raises = raises
        self.calls = 0

    def AsyncClient(self, timeout: float | None = None) -> _StubClient:
        return _StubClient(self)


def _a11y_report(score: float | object, audits: dict[str, dict[str, object]]) -> dict[str, object]:
    """Сирий звіт сайдкара: категорії, перевірки і одна метрика швидкості."""
    return {
        "categories": {
            "performance": {"score": 0.9},
            "accessibility": {"score": score, "auditRefs": [{"id": k} for k in audits]},
        },
        "audits": {
            "largest-contentful-paint": {"numericValue": 2400.0},
            **audits,
        },
    }


def _binary_audit(score: float, title: str = "") -> dict[str, object]:
    return {"score": score, "scoreDisplayMode": "binary", "title": title}


def _measure(module: object, provider: object, stub: _StubHttpx, strategy: Strategy):
    real = module.httpx
    module.httpx = stub
    try:
        return asyncio.run(provider.measure("https://example.com/", strategy))
    finally:
        module.httpx = real


def _lighthouse(stub: _StubHttpx, strategy: Strategy = Strategy.MOBILE):
    provider = lighthouse_module.LighthouseProvider(base_url="http://sidecar.invalid")
    return _measure(lighthouse_module, provider, stub, strategy)


def _psi(stub: _StubHttpx, strategy: Strategy = Strategy.MOBILE):
    provider = psi_module.PsiProvider(api_key="k")
    return _measure(psi_module, provider, stub, strategy)


def test_the_sidecar_accessibility_category_is_no_longer_discarded() -> None:
    """E-08: категорія приїжджала й нікуди не потрапляла."""
    report = _a11y_report(0.5, {"button-name": _binary_audit(0), "link-name": _binary_audit(1)})
    result = _lighthouse(_StubHttpx(report))

    assert result.fetched is True
    assert result.accessibility_score == 50.0
    assert [f["id"] for f in result.accessibility_failures] == ["button-name"]
    assert (result.accessibility_applicable, result.accessibility_passed) == (2, 1)
    assert result.accessibility_failed == 1


def test_ingesting_accessibility_leaves_the_speed_measurement_untouched() -> None:
    report = _a11y_report(0.5, {"button-name": _binary_audit(0)})
    with_a11y = _lighthouse(_StubHttpx(report))

    stripped = _a11y_report(0.5, {"button-name": _binary_audit(0)})
    del stripped["categories"]["accessibility"]
    without = _lighthouse(_StubHttpx(stripped))

    assert with_a11y.lighthouse_score == without.lighthouse_score == 90.0
    assert with_a11y.lab["LCP"].value == without.lab["LCP"].value == 2400.0
    assert with_a11y.opportunities == without.opportunities


def test_a_sidecar_report_without_the_category_measures_nothing_not_zero() -> None:
    report = _a11y_report(0.5, {"button-name": _binary_audit(0)})
    del report["categories"]["accessibility"]
    result = _lighthouse(_StubHttpx(report))

    assert result.accessibility_score is None
    assert result.accessibility_applicable is None
    assert result.accessibility_failures == []
    assert result.lighthouse_score == 90.0


@pytest.mark.parametrize(
    "broken",
    [
        {"score": "n/a", "auditRefs": [{"id": "button-name"}]},
        {"score": None, "auditRefs": [{"id": "button-name"}]},
        {"score": 0.5},
        {"score": 0.5, "auditRefs": "nope"},
    ],
)
def test_a_malformed_category_never_becomes_a_score(broken: dict[str, object]) -> None:
    """Ні нуля, ні ста з непрочитаної категорії. І швидкість не падає."""
    report = _a11y_report(0.5, {"button-name": _binary_audit(0)})
    report["categories"]["accessibility"] = broken
    result = _lighthouse(_StubHttpx(report))

    assert result.accessibility_score is None
    assert result.accessibility_applicable is None
    assert result.lighthouse_score == 90.0


def test_a_report_without_audits_leaves_accessibility_unmeasured() -> None:
    report = _a11y_report(0.5, {"button-name": _binary_audit(0)})
    del report["audits"]
    result = _lighthouse(_StubHttpx(report))
    assert result.accessibility_score is None


def test_a_sidecar_http_error_is_not_an_accessibility_verdict() -> None:
    result = _lighthouse(_StubHttpx(None, status=502, text="bad gateway"))

    assert result.fetched is False
    assert result.error is not None and "502" in result.error
    assert result.accessibility_score is None
    assert result.accessibility_failures == []


def test_a_sidecar_timeout_is_not_an_accessibility_verdict() -> None:
    result = _lighthouse(_StubHttpx(raises=httpx.ReadTimeout("timed out")))

    assert result.fetched is False
    assert result.error is not None and "ReadTimeout" in result.error
    assert result.accessibility_score is None
    assert result.accessibility_applicable is None


def test_an_unreadable_sidecar_body_is_not_an_accessibility_verdict() -> None:
    result = _lighthouse(_StubHttpx(ValueError("not json")))
    assert result.fetched is False
    assert result.accessibility_score is None


@pytest.mark.parametrize("strategy", [Strategy.MOBILE, Strategy.DESKTOP])
def test_both_strategies_ingest_accessibility(strategy: Strategy) -> None:
    report = _a11y_report(0.75, {"button-name": _binary_audit(0), "link-name": _binary_audit(1)})
    result = _lighthouse(_StubHttpx(report), strategy)

    assert result.strategy is strategy
    assert result.accessibility_score == 75.0
    assert result.accessibility_failed == 1


def test_a_sidecar_report_already_wrapped_is_accepted_too() -> None:
    """Сайдкар може віддати звіт як є або загорнутим — обидва варіанти."""
    report = _a11y_report(0.5, {"button-name": _binary_audit(0)})
    plain = _lighthouse(_StubHttpx(report))
    wrapped = _lighthouse(_StubHttpx({"lighthouseResult": report}))

    assert plain.accessibility_score == wrapped.accessibility_score == 50.0
    assert plain.accessibility_failed == wrapped.accessibility_failed


def test_psi_and_the_sidecar_report_the_same_accessibility_for_the_same_data() -> None:
    """Парність провайдерів: той самий звіт — ті самі поля.

    Це і є E-08: не новий детектор доступності, а однакове читання
    однакових даних двома шляхами.
    """
    audits = {
        "button-name": _binary_audit(0, "Buttons have no name"),
        "image-alt": _binary_audit(0, "No alt"),
        "link-name": _binary_audit(1),
    }
    report = _a11y_report(0.66, audits)

    from_sidecar = _lighthouse(_StubHttpx(report))
    from_psi = _psi(_StubHttpx({"lighthouseResult": report}))

    for field in (
        "accessibility_score",
        "accessibility_failures",
        "accessibility_failures_all",
        "accessibility_audits_total",
        "accessibility_applicable",
        "accessibility_passed",
        "accessibility_failed",
    ):
        assert getattr(from_sidecar, field) == getattr(from_psi, field), field


def test_psi_still_reads_its_own_field_data_and_the_sidecar_does_not_invent_it() -> None:
    """CrUX — польові дані Google. Сайдкар їх не має і вигадувати не сміє."""
    report = _a11y_report(0.9, {"button-name": _binary_audit(1)})
    payload = {
        "lighthouseResult": report,
        "loadingExperience": {
            "metrics": {"INTERACTION_TO_NEXT_PAINT": {"percentile": 180}}
        },
    }

    from_psi = _psi(_StubHttpx(payload))
    from_sidecar = _lighthouse(_StubHttpx(report))

    assert from_psi.field_data["INP"].value == 180
    assert from_sidecar.field_data == {}
    assert from_psi.accessibility_score == from_sidecar.accessibility_score == 90.0
