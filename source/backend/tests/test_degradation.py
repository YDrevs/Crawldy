"""Деградації: структуровані, але зі збереженим текстовим представленням."""

import pytest

from app.audit.enums import AuditStatus, DegradationKind, Module
from app.audit.orchestrator import AuditOptions, _module_coverage
from app.audit.types import (
    Degradation,
    LinkRef,
    PageSignals,
    PerformanceResult,
    SiteContext,
    Strategy,
)


def _perf(
    fetched: bool, error: str | None = None, accessibility: float | None = 92.0
) -> PerformanceResult:
    """Успішна відповідь PSI несе обидві категорії: доступність приходить
    тим самим запитом, і фікстура має це відображати."""
    result = PerformanceResult(
        provider="psi",
        strategy=Strategy.MOBILE,
        url="https://example.com/",
        fetched=fetched,
        error=error,
    )
    if fetched:
        result.accessibility_score = accessibility
    return result


# Скільки слів дає фікстура. Не деталь оформлення: оркестратор виключає
# контентні модулі, коли тексту на сайті майже немає, — сторінка-заглушка
# хостера на чотирнадцять слів інакше отримувала 68 балів.
FIXTURE_WORDS = 400


def _ctx(response_ms: int = 0) -> SiteContext:
    ctx = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    ctx.pages = [
        PageSignals(
            url="https://example.com/",
            status_code=200,
            response_ms=response_ms,
            word_count=FIXTURE_WORDS,
        )
    ]
    return ctx


def test_str_preserves_legacy_format():
    """audits.error і CLI склеюють деградації в рядок — формат не має змінитися."""
    collector = Degradation("sitemap", DegradationKind.COLLECTOR_FAILED, "timeout")
    check = Degradation("seo.title", DegradationKind.CHECK_FAILED, "boom")
    assert str(collector) == "sitemap: timeout"
    assert str(check) == "check seo.title: boom"


def test_json_roundtrip():
    original = Degradation(
        scope="performance",
        kind=DegradationKind.PROVIDER_UNAVAILABLE,
        reason="429 Too Many Requests",
        affected_modules=[Module.PERFORMANCE],
    )
    assert Degradation.from_json(original.to_json()) == original


def test_provider_failure_without_own_measurements_skips_the_module():
    degraded: list[Degradation] = []
    skipped, partial = _module_coverage(AuditOptions(), _ctx(0), [_perf(False, "429")], degraded)

    assert Module.PERFORMANCE in skipped
    # tech неповний з іншої причини: фікстура — одна сторінка без рендеру,
    # тож про лічильник, доданий скриптом, ми нічого не знаємо (G3).
    assert partial == {Module.TECH}
    speed = [d for d in degraded if d.scope == Module.PERFORMANCE.value]
    assert len(speed) == 1
    assert speed[0].kind == DegradationKind.PROVIDER_UNAVAILABLE
    assert "429" in speed[0].reason


def test_provider_failure_with_own_measurements_gives_a_partial_score():
    """Час відповіді ми міряємо самі — це не привід лишати напрям порожнім."""
    degraded: list[Degradation] = []
    skipped, partial = _module_coverage(AuditOptions(), _ctx(950), [_perf(False, "429")], degraded)

    assert Module.PERFORMANCE not in skipped, "модуль потрапляє в overall"
    assert Module.PERFORMANCE in partial
    assert degraded[0].kind == DegradationKind.PARTIAL_DATA
    assert "Core Web Vitals" in degraded[0].reason


def test_partial_data_is_not_an_audit_failure():
    """Неповні дані описуються в missing_data, але статус лишається completed."""
    degradation = Degradation(
        "performance", DegradationKind.PARTIAL_DATA, "CWV не виміряно", [Module.PERFORMANCE]
    )
    assert degradation.is_failure is False


def test_module_switched_off_is_not_a_provider_failure():
    """--no-perf і «PSI не відповів» — різні речі, звіт має їх розрізняти."""
    degraded: list[Degradation] = []
    options = AuditOptions(modules={Module.SEO})
    skipped, partial = _module_coverage(options, _ctx(950), [], degraded)

    assert Module.PERFORMANCE in skipped
    assert Module.SEO not in skipped
    assert partial == set()
    assert {d.kind for d in degraded} == {DegradationKind.MODULE_EXCLUDED}


def test_fetched_performance_produces_no_degradation():
    degraded: list[Degradation] = []
    skipped, partial = _module_coverage(AuditOptions(), _ctx(120), [_perf(True)], degraded)

    assert Module.PERFORMANCE not in skipped
    assert Module.PERFORMANCE not in partial
    # Швидкість не лишає прогалин. Єдиний запис тут — про іншу перевірку:
    # сторінку не рендерили, тож висновок про лічильник неповний (G3).
    assert [d.scope for d in degraded] == ["tech.analytics"]


def _blocked_ctx(status: int = 403) -> SiteContext:
    ctx = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    ctx.pages = [
        PageSignals(url="https://example.com/", status_code=status, word_count=FIXTURE_WORDS)
    ]
    return ctx


def test_site_that_served_no_content_is_not_scored_on_content_modules():
    """403 замість сторінки — це не «зауважень немає». Без цього Rozetka
    виходила на перше місце в групі за те, що нічого не показала."""
    degraded: list[Degradation] = []
    skipped, _ = _module_coverage(AuditOptions(), _blocked_ctx(), [_perf(True)], degraded)

    assert {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY} <= skipped
    assert degraded[0].kind == DegradationKind.COLLECTOR_FAILED
    assert "403" in degraded[0].reason


def test_blindness_is_detected_even_when_modules_were_filtered():
    """Вибір модулів не робить нас зрячими: перевірка йде першою."""
    options = AuditOptions(modules={Module.SEO, Module.TECH})
    degraded: list[Degradation] = []
    skipped, _ = _module_coverage(options, _blocked_ctx(), [_perf(True)], degraded)

    assert Module.SEO in skipped


def _one_page_with_links() -> SiteContext:
    page = PageSignals(url="https://example.com/", status_code=200, word_count=FIXTURE_WORDS)
    page.links = [
        LinkRef(url="https://example.com/about", anchor="Про нас", rel="", is_internal=True)
    ]
    ctx = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    ctx.pages = [page]
    return ctx


def test_a_single_stray_link_is_not_evidence_of_a_larger_site():
    """Одне непробуване посилання — не доказ більшого сайту.

    Стара логіка `crawl.shallow` позначала таку оцінку неповною. Нова
    оцінка покриття свідомо цього не робить: випадкове одне посилання
    трапляється й на справжніх односторінкових сайтах, а межа доказу
    проходить там, де кандидатів стає кілька (див. tests/test_coverage.py
    про withheld при трьох і більше).
    """
    degraded: list[Degradation] = []
    skipped, partial = _module_coverage(
        AuditOptions(), _one_page_with_links(), [_perf(True)], degraded
    )
    assert Module.SEO not in skipped
    # Покриття краулу неповним не стає. `tech` — стає, і з іншої причини:
    # сторінку не рендерили, тож лічильник, доданий скриптом, невидимий (G3).
    # `ai_ready` — теж, і з третьої: непрочитане посилання на придатну
    # сторінку лишає класифікацію ієрархії E-15 без вердикту (UNKNOWN), а
    # для цього стану контракт оголошує модуль неповним. Питання в них
    # різні: краул питає, чи вистачило прочитаного, щоб судити сайт
    # узагалі; E-15 — чи вистачило, щоб сказати, що ієрархії НЕМАЄ.
    assert partial == {Module.TECH, Module.AI_READY}


def test_genuine_one_page_site_is_not_called_partial():
    """Лендінг без внутрішніх посилань — це його будова, а не наша сліпота."""
    degraded: list[Degradation] = []
    _, partial = _module_coverage(AuditOptions(), _ctx(100), [_perf(True)], degraded)

    assert Module.SEO not in partial
    assert partial == {Module.TECH}, "лише незавершений висновок про аналітику"


def test_accessibility_without_data_is_skipped_not_scored():
    """PSI відповів, але категорії доступності не приїхало. Сто балів за
    неперевірене — саме та вигадана цифра, якої в цьому продукті бути не
    може."""
    degraded: list[Degradation] = []
    skipped, _ = _module_coverage(
        AuditOptions(), _ctx(120), [_perf(True, accessibility=None)], degraded
    )

    assert Module.ACCESSIBILITY in skipped
    assert any(d.scope == Module.ACCESSIBILITY.value for d in degraded)


def test_accessibility_with_data_is_scored():
    degraded: list[Degradation] = []
    skipped, _ = _module_coverage(AuditOptions(), _ctx(120), [_perf(True)], degraded)

    assert Module.ACCESSIBILITY not in skipped


def test_a_crawl_that_mostly_failed_gives_no_content_score():
    """Прочитане не представляє сайт, і бал за ним вводить в оману.

    На gocplumbing.com із одинадцяти адрес сім не відповіли, і за трьома
    прочитаними сайт отримав 64 бали — вище за половину верхнього рівня
    калібрувальної вибірки.
    """
    ctx = _ctx()
    ctx.failed_urls = {f"https://example.com/p{n}": "HTTP 500" for n in range(7)}
    skipped, _ = _module_coverage(AuditOptions(), ctx, [_perf(True)], [])
    assert {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY} <= skipped


def test_a_few_failures_do_not_blind_the_audit():
    """Одна-дві биті адреси — це знахідка про сайт, а не наша сліпота."""
    ctx = _ctx()
    ctx.pages += [
        PageSignals(url=f"https://example.com/p{n}", status_code=200, word_count=FIXTURE_WORDS)
        for n in range(8)
    ]
    ctx.failed_urls = {"https://example.com/gone": "HTTP 404"}
    skipped, _ = _module_coverage(AuditOptions(), ctx, [_perf(True)], [])
    assert Module.SEO not in skipped


def test_one_broken_link_on_a_tiny_crawl_is_not_blindness():
    """Частка невдач нічого не означає при малому знаменнику: на двох
    адресах одна битва — це вже 50%."""
    ctx = _ctx()
    ctx.failed_urls = {"https://example.com/gone": "HTTP 404"}
    skipped, _ = _module_coverage(AuditOptions(), ctx, [_perf(True)], [])
    assert Module.SEO not in skipped


def test_a_site_without_any_text_is_not_scored():
    """oldetownhall.com віддав чотирнадцять слів — повідомлення хостера
    про призупинення акаунта — і отримав 68 балів."""
    ctx = _ctx()
    ctx.pages[0].word_count = 14
    skipped, _ = _module_coverage(AuditOptions(), ctx, [_perf(True)], [])
    assert {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY} <= skipped


def test_a_small_but_real_site_is_still_scored():
    """Лендінг на кількасот слів — це сайт, а не заглушка."""
    ctx = _ctx()
    ctx.pages[0].word_count = 250
    skipped, _ = _module_coverage(AuditOptions(), ctx, [_perf(True)], [])
    assert Module.SEO not in skipped


# ── вимкнене користувачем ≠ зламане ────────────────────────────────────────


def test_disabled_layer_is_not_an_audit_failure():
    """Вимкнений семантичний шар не має робити аудит partial.

    Поки він писався як «провайдер недоступний», а llm_enabled за
    замовчуванням False, статус completed був недосяжний у штатній
    конфігурації: 28 із 35 аудитів валідаційної вибірки були partial без
    жодної справжньої причини. Поле, яке завжди має одне значення, не
    несе інформації.
    """
    disabled = Degradation(
        "llm", DegradationKind.LAYER_DISABLED, "вимкнено в налаштуваннях", [Module.LLM_VISIBILITY]
    )
    assert disabled.is_failure is False


def test_layer_that_broke_is_still_a_failure():
    """Розрізняємо саме вибір і поломку, а не мовчання взагалі.

    Причин мовчання чотири — вимкнено / немає пакета / немає ключа /
    невідома модель, — і лише перша є вибором користувача.
    """
    broken = Degradation(
        "llm", DegradationKind.PROVIDER_UNAVAILABLE, "не заданий ключ", [Module.LLM_VISIBILITY]
    )
    assert broken.is_failure is True


def test_analyst_reports_a_deliberate_switch_off_as_such():
    """Прапорець, а не розбір рядка reason: зіставляти текст мовою — шукати халепи."""
    import asyncio

    from app.audit.llm.factory import get_analyst

    off = asyncio.run(get_analyst(enabled=False).brief("https://example.com", []))
    assert off.analysed is False
    assert off.disabled is True

    misconfigured = asyncio.run(get_analyst(enabled=True, model="не-існує").brief("x", []))
    assert misconfigured.analysed is False
    assert misconfigured.disabled is False, "помилка налаштування — не вибір користувача"


def test_audit_without_the_semantic_layer_is_completed():
    """Наскрізна перевірка K1: статус аудиту, а не лише прапорець деградації."""
    from app.audit.enums import AuditStatus
    from app.audit.orchestrator import AuditOutcome
    from app.report.source import source_from_outcome

    ctx = _ctx(120)
    outcome = AuditOutcome(
        context=ctx,
        issues=[],
        scores={},
        overall=70,
        degraded=[
            Degradation(
                "llm",
                DegradationKind.LAYER_DISABLED,
                "семантичного аналізу не було: вимкнено в налаштуваннях",
                [Module.LLM_VISIBILITY],
            )
        ],
    )
    assert source_from_outcome(outcome).status is AuditStatus.COMPLETED


# ── вхідна адреса з помилкою ───────────────────────────────────────────────


def _entry_error_ctx(status: int = 404) -> SiteContext:
    """Вхід віддав помилку, але з нього ведуть посилання на живі сторінки."""
    broken = PageSignals(url="https://example.com/no-such-page", status_code=status, word_count=5)
    real = PageSignals(url="https://example.com/", status_code=200, word_count=FIXTURE_WORDS)
    ctx = SiteContext(entry_url="https://example.com/no-such-page", origin="https://example.com")
    ctx.pages = [broken, real]
    return ctx


def test_error_page_is_not_taken_for_the_home_page():
    """bosch.com/this-page-does-not-exist/ судився як головна сторінка компанії."""
    ctx = _entry_error_ctx()
    home = ctx.home
    assert home is not None
    assert home.url == "https://example.com/", "головна — перша, що справді відповіла"


def test_blocked_site_still_has_a_home_to_look_at():
    """Фолбек лишається: коли не відповіла жодна, 403-відповідь — усе, що ми маємо,
    і чеки про заголовки мають її бачити."""
    ctx = _blocked_ctx()
    home = ctx.home
    assert home is not None
    assert home.status_code == 403


def test_entry_that_returned_an_error_is_reported():
    """Ми виміряли не те, що просили, і звіт має це сказати.

    Швидкість Lighthouse міряє саме вхідну адресу: на bosch.com модуль
    вагою 0.22 описував сторінку 404, а звіт мовчав.
    """
    degraded: list[Degradation] = []
    skipped, partial = _module_coverage(
        AuditOptions(), _entry_error_ctx(), [_perf(True)], degraded
    )

    entry = [d for d in degraded if d.scope == "entry"]
    assert len(entry) == 1
    assert "404" in entry[0].reason
    assert entry[0].affected_modules == [Module.PERFORMANCE]
    assert Module.PERFORMANCE in partial
    assert Module.PERFORMANCE not in skipped, "числа справжні, просто про іншу сторінку"


def test_healthy_entry_produces_no_entry_degradation():
    degraded: list[Degradation] = []
    _module_coverage(AuditOptions(), _ctx(120), [_perf(True)], degraded)

    assert [d for d in degraded if d.scope == "entry"] == []


def test_blocked_site_does_not_also_complain_about_the_entry():
    """`crawl` уже пояснює це краще — другий рядок був би шумом."""
    degraded: list[Degradation] = []
    _module_coverage(AuditOptions(), _blocked_ctx(), [_perf(True)], degraded)

    assert [d for d in degraded if d.scope == "entry"] == []


# ── E-01: вибір модулів і наявність доказу — різні факти ──────────────────
#
# Фільтр модулів закінчував розбір раніше, ніж хтось питав, чи є в
# доступності дані, і на шести знімках Crawldy без швидкості вона виходила
# сотнею. Матриця нижче — перехресний добуток фільтра й стану провайдера. У
# кожній клітинці перевіряється одне й те саме: вид і ключ деградації
# доступності, статус аудиту, чи є в неї число, чи вона пропущена, яку
# причину бачить API, чи бере вона участь у загальному балі — і що «не
# виміряно» ніде не видано за «вимкнено клієнтом».

EXCLUDED = "excluded_by_request"
NOT_MEASURED = "withheld_not_measured"
NOT_MEASURED_KEY = "notice.accessibility.not_measured"

REQUESTED: dict[str, set[Module] | None] = {
    "no_filter": None,
    "seo_tech": {Module.SEO, Module.TECH},
    "all_but_performance": set(Module) - {Module.PERFORMANCE},
    "all_but_accessibility": set(Module) - {Module.ACCESSIBILITY},
}

PROVIDER = {
    "valid_category": lambda: [_perf(True)],
    "no_category": lambda: [_perf(True, accessibility=None)],
    "not_fetched": lambda: [_perf(False, "429")],
}

_OFF = (DegradationKind.MODULE_EXCLUDED, "notice.module.excluded")
_NO_CATEGORY = (DegradationKind.PROVIDER_UNAVAILABLE, "notice.accessibility.no_category")
_NOT_RUN = (DegradationKind.PARTIAL_DATA, NOT_MEASURED_KEY)
_COMPLETED = AuditStatus.COMPLETED
_PARTIAL = AuditStatus.PARTIAL

# (деградації доступності, причина доступності, причина швидкості, статус)
MATRIX = {
    ("no_filter", "valid_category"): ([], None, None, _COMPLETED),
    ("no_filter", "no_category"): ([_NO_CATEGORY], NOT_MEASURED, None, _PARTIAL),
    ("no_filter", "not_fetched"): ([], NOT_MEASURED, NOT_MEASURED, _PARTIAL),
    ("seo_tech", "valid_category"): ([_OFF], EXCLUDED, EXCLUDED, _COMPLETED),
    ("seo_tech", "no_category"): ([_OFF], EXCLUDED, EXCLUDED, _COMPLETED),
    ("seo_tech", "not_fetched"): ([_OFF], EXCLUDED, EXCLUDED, _COMPLETED),
    # Дані при вимкненій швидкості бувають лише в перерахунку знімка з
    # іншими опціями — тоді доступність виміряна, і число в неї справжнє.
    ("all_but_performance", "valid_category"): ([], None, EXCLUDED, _COMPLETED),
    ("all_but_performance", "no_category"): ([_NOT_RUN], NOT_MEASURED, EXCLUDED, _COMPLETED),
    ("all_but_performance", "not_fetched"): ([_NOT_RUN], NOT_MEASURED, EXCLUDED, _COMPLETED),
    ("all_but_accessibility", "valid_category"): ([_OFF], EXCLUDED, None, _COMPLETED),
    ("all_but_accessibility", "no_category"): ([_OFF], EXCLUDED, None, _COMPLETED),
    # Швидкість без відповіді провайдера й без часу відповіді сервера не
    # виміряна й під фільтром — так само, як без нього (G2.1).
    ("all_but_accessibility", "not_fetched"): ([_OFF], EXCLUDED, NOT_MEASURED, _PARTIAL),
}


def _presented(outcome):
    """Статус, документ і відповідь API — тим самим шляхом, що в продукті."""
    import uuid

    from app.audit.i18n import Locale
    from app.report.builder import build_report
    from app.report.source import source_from_outcome
    from app.report.web import to_web

    source = source_from_outcome(outcome)
    document = build_report(source, Locale.EN)
    result = to_web(
        document,
        audit_id=uuid.UUID(int=1),
        site_id=None,
        status=source.status.value,
        finished_at=None,
        fallback_locale="en",
    )
    return source, document, result


def _audit_state(options: AuditOptions, performance, ctx: SiteContext | None = None):
    """Покриття, бал, статус і відповідь API для одного стану — без мережі."""
    from app.audit.orchestrator import AuditOutcome, compute_scores_safe

    ctx = ctx if ctx is not None else _ctx(0)
    ctx.performance = list(performance)
    degraded: list[Degradation] = []
    skipped, partial = _module_coverage(options, ctx, ctx.performance, degraded)
    overall, scores = compute_scores_safe([], skipped)
    outcome = AuditOutcome(
        context=ctx,
        issues=[],
        scores=scores,
        overall=overall,
        degraded=degraded,
        skipped_modules=skipped,
        partial_modules=partial,
    )
    source, _, result = _presented(outcome)
    return outcome, source, result


def _accessibility_gaps(outcome) -> list[tuple[DegradationKind, str]]:
    return [
        (d.kind, d.reason_key)
        for d in outcome.degraded
        if Module.ACCESSIBILITY in d.affected_modules
    ]


def _assert_accessibility(outcome, result, reason: str | None) -> None:
    """Число, пропуск, причина в API й участь у балі кажуть одне й те саме."""
    from app.audit.scoring import active_weights

    measured = reason is None
    assert (Module.ACCESSIBILITY.value in outcome.scores) is measured
    assert (Module.ACCESSIBILITY in outcome.skipped_modules) is not measured
    assert (Module.ACCESSIBILITY in active_weights(outcome.skipped_modules)) is measured
    assert result.accessibility.withheld_reason == reason
    assert result.accessibility.counts_toward_overall is measured
    if reason == NOT_MEASURED:
        assert _OFF not in _accessibility_gaps(outcome), "не виміряне видано за вимкнене"


def _speed(result):
    return next(m for m in result.modules if m.module is Module.PERFORMANCE)


def _parsed(category: dict) -> PerformanceResult:
    """Вимір, пропущений через справжній парсер категорії доступності (G1)."""
    from app.audit.performance.psi import _parse_accessibility

    result = PerformanceResult(
        provider="psi", strategy=Strategy.MOBILE, url="https://example.com/", fetched=True
    )
    audits = {
        "image-alt": {"score": 1, "scoreDisplayMode": "binary", "title": "Images have alt"},
        "button-name": {"score": 0, "scoreDisplayMode": "binary", "title": "Buttons have no name"},
    }
    payload = {"lighthouseResult": {"categories": {"accessibility": category}, "audits": audits}}
    _parse_accessibility(payload, result)
    return result


def _snapshot(name: str) -> SiteContext:
    import json
    from pathlib import Path

    from app.audit.snapshot import load

    path = Path(__file__).parent / "fixtures" / "snapshots" / name
    return load(json.loads(path.read_text("utf-8")))


@pytest.mark.parametrize(("requested", "provider"), sorted(MATRIX))
def test_accessibility_state_follows_the_request_and_the_data(requested, provider):
    gaps, reason, speed_reason, status = MATRIX[(requested, provider)]
    modules = REQUESTED[requested]
    options = AuditOptions(modules=set(modules) if modules is not None else None)
    outcome, source, result = _audit_state(options, PROVIDER[provider]())

    assert _accessibility_gaps(outcome) == gaps
    _assert_accessibility(outcome, result, reason)
    assert source.status is status
    assert _speed(result).withheld_reason == speed_reason
    assert _speed(result).excluded is (speed_reason is not None)


def test_e01_f4_a_valid_category_is_scored_with_its_existing_weight():
    """Випадок 1: без фільтра, категорія придатна — модуль міряний, вага та сама."""
    from app.audit.scoring import MODULE_WEIGHT

    measured = _parsed({"score": 0.5, "auditRefs": [{"id": "image-alt"}, {"id": "button-name"}]})
    assert measured.accessibility_score == 50.0

    outcome, source, result = _audit_state(AuditOptions(), [measured])

    assert _accessibility_gaps(outcome) == []
    assert source.status is AuditStatus.COMPLETED
    _assert_accessibility(outcome, result, None)
    assert result.accessibility.overall_weight == pytest.approx(
        MODULE_WEIGHT[Module.ACCESSIBILITY]
    )


def test_a_malformed_category_keeps_the_accepted_g1_failure():
    """Випадок 3: провайдер відповів, але категорії вірити не можна.

    Парсер G1 лишає її невиміряною, і доступність притримується з тією самою
    деградацією-збоєм, що й без категорії взагалі (випадок 2 — у матриці).
    """
    unverifiable = _parsed({"score": 1.7, "auditRefs": [{"id": "image-alt"}]})
    assert unverifiable.fetched and unverifiable.accessibility_score is None

    outcome, source, result = _audit_state(AuditOptions(), [unverifiable])

    assert _accessibility_gaps(outcome) == [_NO_CATEGORY]
    assert source.status is AuditStatus.PARTIAL
    _assert_accessibility(outcome, result, NOT_MEASURED)


@pytest.mark.parametrize(
    ("response_ms", "kind", "key", "status"),
    [
        (
            0,
            DegradationKind.PROVIDER_UNAVAILABLE,
            "notice.performance.no_metrics",
            AuditStatus.PARTIAL,
        ),
        (
            950,
            DegradationKind.PARTIAL_DATA,
            "notice.performance.no_vitals",
            AuditStatus.COMPLETED,
        ),
    ],
)
def test_a_provider_that_did_not_answer_keeps_its_existing_semantics(
    response_ms, kind, key, status
):
    """Випадок 4: провайдера питали, і він не відповів зовсім.

    Прогалину, як і до G2, пояснює деградація швидкості; окремої деградації
    доступності тут не було й немає. Доступність однаково без числа й
    притримана як не виміряна, а не як вимкнена.
    """
    outcome, source, result = _audit_state(
        AuditOptions(), [_perf(False, "429")], _ctx(response_ms)
    )

    # Друга прогалина — про іншу перевірку: сторінку не рендерили, тож
    # висновок про лічильник неповний (G3). Швидкості це не змінює.
    assert [(d.scope, d.kind, d.reason_key) for d in outcome.degraded] == [
        (Module.PERFORMANCE.value, kind, key),
        ("tech.analytics", DegradationKind.PARTIAL_DATA, "notice.analytics.render_incomplete"),
    ]
    assert source.status is status
    _assert_accessibility(outcome, result, NOT_MEASURED)


def test_excluding_performance_leaves_accessibility_not_measured_and_the_audit_completed():
    """Випадок 5, як у живому аудиті: без швидкості провайдера не питали.

    Доступність клієнт не вимикав, тож «вимкнено» тут неправда, а збою не
    було — провайдера ніхто не питав. Швидкість лишається вимкненою клієнтом.
    """
    options = AuditOptions(modules=set(Module) - {Module.PERFORMANCE})
    outcome, source, result = _audit_state(options, [])

    assert _accessibility_gaps(outcome) == [_NOT_RUN]
    (gap,) = [d for d in outcome.degraded if d.reason_key == NOT_MEASURED_KEY]
    assert gap.is_failure is False
    assert source.status is AuditStatus.COMPLETED
    _assert_accessibility(outcome, result, NOT_MEASURED)
    assert _speed(result).withheld_reason == EXCLUDED
    assert {(g.scope, g.kind) for g in result.missing_data} == {
        (Module.PERFORMANCE.value, DegradationKind.MODULE_EXCLUDED.value),
        (Module.ACCESSIBILITY.value, DegradationKind.PARTIAL_DATA.value),
        # Аналітика: та сама неповнота, що й вище, у поданому вигляді (G3).
        ("tech.analytics", DegradationKind.PARTIAL_DATA.value),
    }


def test_excluding_performance_and_accessibility_is_two_requests_not_a_gap():
    """Випадок 6: обидва вимкнено клієнтом — «не виміряно» не пишеться."""
    options = AuditOptions(modules=set(Module) - {Module.PERFORMANCE, Module.ACCESSIBILITY})
    outcome, source, result = _audit_state(options, [])

    assert _accessibility_gaps(outcome) == [_OFF]
    assert all(d.reason_key != NOT_MEASURED_KEY for d in outcome.degraded)
    assert source.status is AuditStatus.COMPLETED
    _assert_accessibility(outcome, result, EXCLUDED)
    assert _speed(result).withheld_reason == EXCLUDED


def test_blindness_is_still_decided_first_when_accessibility_is_not_measured():
    """Випадок 9: сліпота йде перед фільтром і перед доступністю."""
    from app.audit.types import CRAWL_BLIND

    options = AuditOptions(modules=set(Module) - {Module.PERFORMANCE})
    outcome, source, result = _audit_state(options, [], _blocked_ctx())

    assert [(d.scope, d.kind) for d in outcome.degraded] == [
        (CRAWL_BLIND, DegradationKind.COLLECTOR_FAILED),
        (Module.PERFORMANCE.value, DegradationKind.MODULE_EXCLUDED),
        (Module.ACCESSIBILITY.value, DegradationKind.PARTIAL_DATA),
    ]
    assert source.status is AuditStatus.PARTIAL, "статус від сліпоти, а не від вибору модулів"
    assert outcome.overall is None
    _assert_accessibility(outcome, result, NOT_MEASURED)
    reasons = {m.module: m.withheld_reason for m in result.modules}
    assert reasons[Module.SEO] == NOT_MEASURED
    assert reasons[Module.PERFORMANCE] == EXCLUDED


@pytest.mark.parametrize(
    ("provider", "gaps", "reason"),
    [
        ("valid_category", [], None),
        ("no_category", [_NO_CATEGORY], NOT_MEASURED),
        ("not_fetched", [], NOT_MEASURED),
    ],
)
def test_a_filter_that_keeps_performance_judges_accessibility_by_its_data(provider, gaps, reason):
    """Під фільтром зі швидкістю доступність судиться так само, як без фільтра.

    До G2 усі три стани давали сотню: фільтр закінчував розбір до перевірки
    даних. Стан самої швидкості в такому аудиті — у матриці G2.1 нижче.
    """
    options = AuditOptions(modules=set(Module) - {Module.SEO})
    outcome, _, result = _audit_state(options, PROVIDER[provider]())

    assert _accessibility_gaps(outcome) == gaps
    _assert_accessibility(outcome, result, reason)


def test_e01_f3_a_seo_and_tech_audit_excludes_accessibility_by_request():
    """Випадок 8 на знімку: `{SEO, TECH}` — доступність вимкнено, сліпота перша."""
    from app.audit.orchestrator import rescore
    from app.audit.types import CRAWL_BLIND

    options = AuditOptions(modules={Module.SEO, Module.TECH})
    outcome = rescore(_snapshot("schema1_small_site.json"), options)

    assert _accessibility_gaps(outcome) == [_OFF]
    assert {Module.PERFORMANCE, Module.ACCESSIBILITY} <= outcome.skipped_modules
    assert Module.ACCESSIBILITY.value not in outcome.scores
    assert all(d.reason_key != NOT_MEASURED_KEY for d in outcome.degraded)

    blocked = rescore(_snapshot("schema1_blocked_crawl.json"), options)
    assert blocked.degraded[0].scope == CRAWL_BLIND
    assert Module.SEO in blocked.skipped_modules


def test_a_rescored_snapshot_with_accessibility_data_stays_measured_without_performance():
    """Вибір модулів і доказ — різні факти й у перерахунку.

    Знімок несе справжню категорію доступності. Вимкнена в перерахунку
    швидкість її не стирає: у живому аудиті без швидкості даних не буває,
    а тут вони є.
    """
    from app.audit.orchestrator import rescore

    options = AuditOptions(modules=set(Module) - {Module.PERFORMANCE})
    outcome = rescore(_snapshot("schema1_small_site.json"), options)

    assert Module.ACCESSIBILITY.value in outcome.scores
    assert Module.ACCESSIBILITY not in outcome.skipped_modules
    assert _accessibility_gaps(outcome) == []


# ── E-09: модуль, оцінений без семантичного детектора, неповний ───────────
#
# Стани проходять через справжній `run_audit`: підмінено лише введення-
# виведення (завантаження, краул, колектори й провайдер швидкості віддають
# зібране в знімку), а семантичний шар, покриття, чеки, бал і звіт — ті
# самі, що в продукті. Перерахунок знімка сюди не годиться: семантичного
# шару він не виконує. Жоден стан не робить платного виклику.
#
# E09-f1 disabled · f2 no_credentials · f3 provider_failure ·
# f4 facts_failed · f5 success. E09-f6 (збережений звіт) — у test_report_web.

BRIEF = {
    "name": "Pillow PA",
    "tagline": "Handmade pillows",
    "description": "A small pillow workshop.",
    "offerings": ["pillows"],
    "audience": "home owners",
}
FACTS = {
    "facts": [
        {"key": key, "stated": True, "quote": "stated on the site", "url": "https://pillowpa.org/"}
        for key in ("offering", "location", "pricing")
    ],
    "serves_an_area": False,
    "sells_listed_items": False,
}

# стан: (scope, вид, ключ, статус); None — жодної семантичної прогалини
SEMANTIC_STATES = {
    "disabled": ("llm", DegradationKind.LAYER_DISABLED, "notice.llm.disabled", _COMPLETED),
    "no_credentials": (
        "llm",
        DegradationKind.PROVIDER_UNAVAILABLE,
        "notice.llm.unavailable",
        _PARTIAL,
    ),
    "provider_failure": (
        "llm",
        DegradationKind.PROVIDER_UNAVAILABLE,
        "notice.llm.unavailable",
        _PARTIAL,
    ),
    "facts_failed": (
        "llm.unstated_facts",
        DegradationKind.PROVIDER_UNAVAILABLE,
        "notice.llm.facts_unavailable",
        _PARTIAL,
    ),
    "success": None,
}


def _offline_audit(
    monkeypatch,
    *,
    factory,
    llm: bool | None = None,
    provider=None,
    modules: set[Module] | None = None,
    response_times: bool = True,
):
    """Справжній `run_audit`, у якого мережу замінено знімком.

    `provider` підміняє провайдера швидкості, `modules` — вибір модулів,
    `response_times=False` стирає власні виміри краулера. Без них аудит той
    самий, що й у станах E-09.
    """
    import asyncio

    import app.audit.orchestrator as orchestrator
    from app.audit.fetcher import FetchResult

    snap = _snapshot("schema1_small_site.json")
    if not response_times:
        for page in snap.pages:
            page.response_ms = 0
    crawled: list[bool] = []

    class Offline:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def get(self, url: str) -> FetchResult:
            return FetchResult(
                url=url,
                final_url=url,
                status_code=200,
                content_type="text/html",
                text="",
                body_bytes=0,
                elapsed_ms=0,
                headers={},
            )

        async def aclose(self) -> None:
            return None

    async def crawl(fetcher, entry_url, origin, **kwargs):
        if crawled:
            return [], {}
        crawled.append(True)
        return list(snap.pages), dict(snap.failed_urls)

    async def robots(fetcher, origin):
        return snap.robots

    async def llms_txt(fetcher, origin):
        return snap.llms_txt

    async def infra(fetcher, origin):
        return snap.infra

    async def sitemap(fetcher, origin, robots_info):
        return snap.sitemap

    class Stored:
        async def measure(self, url, strategy):
            return next(r for r in snap.performance if r.strategy == strategy)

    stubs = {
        "Fetcher": Offline,
        "crawl": crawl,
        "collect_robots": robots,
        "collect_llms_txt": llms_txt,
        "collect_infra": infra,
        "collect_sitemap": sitemap,
        "get_provider": lambda name=None: provider or Stored(),
        "get_analyst": factory,
    }
    for name, stub in stubs.items():
        monkeypatch.setattr(orchestrator, name, stub)
    options = AuditOptions(strategies=[Strategy.MOBILE], render=False, llm=llm, modules=modules)
    return asyncio.run(orchestrator.run_audit(snap.entry_url, options))


def _transport_stub(replies: list[object]):
    """Справжній аналітик Anthropic, у якого підмінено лише транспорт.

    Клієнт підставлено до першого запиту, тож SDK не створюється, ключ не
    читається й платного виклику не буває. Відповідь — розібраний JSON
    моделі або виняток, яким упав би виклик API; далі працює справжній
    розбір аналітика.
    """
    import json
    from types import SimpleNamespace

    from app.audit.llm.anthropic_analyst import AnthropicAnalyst

    queue = list(replies)

    async def create(**kwargs: object) -> object:
        reply = queue.pop(0)
        if isinstance(reply, Exception):
            raise reply
        block = SimpleNamespace(type="text", text=json.dumps(reply))
        return SimpleNamespace(stop_reason="end_turn", content=[block])

    analyst = AnthropicAnalyst()
    analyst._client = SimpleNamespace(messages=SimpleNamespace(create=create))
    return analyst, queue


def _semantic_state(monkeypatch, state: str):
    """Один стан семантичного шару → (результат аудиту, невитрачені відповіді)."""
    import app.audit.orchestrator as orchestrator
    from app.audit.llm.base import NullAnalyst
    from app.core import runtime_config

    if state in ("disabled", "no_credentials"):
        real = orchestrator.get_analyst
        made: list[object] = []

        def factory(enabled=None, model=None):
            made.append(real(enabled, model))
            return made[-1]

        if state == "no_credentials":
            original = runtime_config.get
            monkeypatch.setattr(
                runtime_config,
                "get",
                lambda key: None if key == "anthropic_api_key" else original(key),
            )
        outcome = _offline_audit(monkeypatch, factory=factory, llm=state == "no_credentials")
        assert [type(analyst) for analyst in made] == [NullAnalyst], "платного клієнта немає"
        return outcome, []

    replies = {
        "provider_failure": [RuntimeError("upstream overloaded")],
        "facts_failed": [BRIEF, RuntimeError("upstream overloaded")],
        "success": [BRIEF, FACTS],
    }[state]
    analyst, queue = _transport_stub(replies)
    outcome = _offline_audit(monkeypatch, factory=lambda enabled=None, model=None: analyst)
    return outcome, queue


@pytest.mark.parametrize("state", sorted(SEMANTIC_STATES))
def test_llm_visibility_is_partial_exactly_when_the_semantic_check_did_not_run(
    monkeypatch, state
):
    from app.audit.i18n import Locale
    from app.report.i18n import t

    outcome, unused = _semantic_state(monkeypatch, state)
    source, document, result = _presented(outcome)
    semantic = [d for d in outcome.degraded if d.scope in ("llm", "llm.unstated_facts")]
    llm = next(m for m in result.modules if m.module is Module.LLM_VISIBILITY)

    assert unused == [], "транспорт отримав рівно стільки запитів, скільки мав"
    assert llm.excluded is False
    assert llm.score == outcome.scores[Module.LLM_VISIBILITY.value], "модуль лишається в балі"

    expected = SEMANTIC_STATES[state]
    if expected is None:
        assert semantic == []
        assert llm.partial is False
        assert Module.LLM_VISIBILITY not in outcome.partial_modules
        assert source.status is AuditStatus.COMPLETED
        # Вимкнений рендер теж торкається модуля, але семантичний детектор
        # від нього не мовчить — прапорець він не вмикає.
        assert any(
            d.scope == "render" and d.kind is DegradationKind.LAYER_DISABLED
            for d in outcome.degraded
        )
        return

    scope, kind, key, status = expected
    (gap,) = semantic
    assert (gap.scope, gap.kind, gap.reason_key) == (scope, kind, key)
    assert gap.affected_modules == [Module.LLM_VISIBILITY]
    assert gap.reason_params["checks"] == ["llm.unstated_facts"]
    assert llm.partial is True
    assert Module.LLM_VISIBILITY in outcome.partial_modules
    assert source.status is status
    (entry,) = [m for m in document.missing_data if m.scope == scope]
    assert entry.note == t("missing_note_partial", Locale.EN), "прапорець і примітка згодні"


def test_a_failed_facts_step_names_the_check_and_nothing_from_the_provider(monkeypatch):
    outcome, _ = _semantic_state(monkeypatch, "facts_failed")

    (gap,) = [d for d in outcome.degraded if d.scope == "llm.unstated_facts"]
    assert set(gap.reason_params) == {"checks"}
    assert "overloaded" not in gap.reason
    assert "overloaded" not in repr(gap.reason_params)
    assert not any(d.scope == "llm" for d in outcome.degraded), "бриф вийшов: шар працював"


def test_the_semantic_states_move_no_number():
    """Змінюються прогалини, прапорець і статус — жоден бал і жодна знахідка.

    Рівень покриття гостя теж той самий: він про краул, а не про
    необовʼязковий шар.
    """
    from app.report.coverage import coverage_level

    seen = {}
    for state in sorted(SEMANTIC_STATES):
        with pytest.MonkeyPatch.context() as patch:
            outcome, _ = _semantic_state(patch, state)
        _, document, _ = _presented(outcome)
        seen[state] = (
            outcome.overall,
            dict(outcome.scores),
            sorted(issue.issue_key for issue in outcome.issues),
            coverage_level(document),
        )
    assert len({repr(value) for value in seen.values()}) == 1, seen


def test_the_semantic_check_map_names_real_checks_that_read_the_model():
    """Мапа живе поруч із шаром, тож тест звіряє її з реєстром і з кодом чеків."""
    import inspect
    import re

    from app.audit.checks import REGISTRY
    from app.audit.orchestrator import SEMANTIC_CHECKS

    assert list(SEMANTIC_CHECKS) == sorted(set(SEMANTIC_CHECKS))
    assert set(SEMANTIC_CHECKS) <= {check.code for check in REGISTRY}
    readers = {
        check.code
        for check in REGISTRY
        if re.search(r"\bctx\.(facts|brief)\b", inspect.getsource(check))
    }
    assert readers == set(SEMANTIC_CHECKS)


def test_a_semantic_gap_never_marks_a_module_without_a_score():
    from app.audit.orchestrator import semantic_gaps

    off = Degradation("llm", DegradationKind.LAYER_DISABLED, "off", [Module.LLM_VISIBILITY])
    assert semantic_gaps([off]) == {Module.LLM_VISIBILITY}
    assert semantic_gaps([off], {Module.LLM_VISIBILITY}) == set()


def test_only_the_semantic_layer_makes_llm_visibility_partial():
    """Рендер і зламаний чек теж торкаються модуля, але це не E-09."""
    from app.audit.orchestrator import semantic_gaps

    unrelated = [
        Degradation("render", DegradationKind.LAYER_DISABLED, "off", [Module.LLM_VISIBILITY]),
        Degradation(
            "llm.contact_page", DegradationKind.CHECK_FAILED, "boom", [Module.LLM_VISIBILITY]
        ),
    ]
    assert semantic_gaps(unrelated) == set()


# ── G2.1: швидкість під фільтром модулів ──────────────────────────────────
#
# Фільтр модулів закінчував розбір раніше, ніж хтось питав, чи відповів
# провайдер швидкості: під будь-яким фільтром, що лишав швидкість, вона
# оцінювалась без жодної деградації, навіть коли провайдер не повернув
# нічого. Правило тепер одне з фільтром і без: фільтр вирішує лише, чи
# швидкість просили, дані — чи її виміряно. Матриця — добуток вибору
# модулів і стану доказу. Кожна клітинка звіряє прогалини (кількість,
# scope, вид, ключ, порядок), бал і прапорці швидкості, причину в API,
# статус, вагу швидкості, загальний бал і доступність.

SELECTIONS: dict[str, set[Module] | None] = {
    "no_filter": None,
    "all_but_seo": set(Module) - {Module.SEO},
    "all_but_accessibility": set(Module) - {Module.ACCESSIBILITY},
    "performance_and_seo": {Module.PERFORMANCE, Module.SEO},
    "performance_only": {Module.PERFORMANCE},
    "all_but_performance": set(Module) - {Module.PERFORMANCE},
    "seo_tech": {Module.SEO, Module.TECH},
}

RAISED = RuntimeError("PSI request failed: ReadTimeout")

# стан доказу: (відповідь провайдера на запит, власний час відповіді краулера, мс).
# Відповіді немає — не просили жодної стратегії: провайдера не питали, список порожній.
EVIDENCE = {
    "valid": (lambda: _perf(True), 120),
    "unfetched_with_response_times": (lambda: _perf(False, "429"), 950),
    "unfetched_without_response_times": (lambda: _perf(False, "429"), 0),
    "empty_with_response_times": (None, 950),
    "empty_without_response_times": (None, 0),
    "raised_with_response_times": (lambda: RAISED, 950),
    "raised_without_response_times": (lambda: RAISED, 0),
}

_SPEED = Module.PERFORMANCE.value
_NO_VITALS = (_SPEED, DegradationKind.PARTIAL_DATA, "notice.performance.no_vitals")
_NO_METRICS = (_SPEED, DegradationKind.PROVIDER_UNAVAILABLE, "notice.performance.no_metrics")
_RAISED = (_SPEED, DegradationKind.PROVIDER_UNAVAILABLE, "notice.performance.partial")

# Швидкість, яку просили: стан доказу → (її прогалина, бал є, бал неповний).
# Від фільтра це не залежить — у цьому й виправлення. Прогалину провайдера,
# що впав, записує сам вимір, і вона єдина.
REQUESTED_SPEED = {
    "valid": (None, True, False),
    "unfetched_with_response_times": (_NO_VITALS, True, True),
    "unfetched_without_response_times": (_NO_METRICS, False, False),
    "empty_with_response_times": (_NO_VITALS, True, True),
    "empty_without_response_times": (_NO_METRICS, False, False),
    "raised_with_response_times": (_RAISED, True, True),
    "raised_without_response_times": (_RAISED, False, False),
}


class _Provider:
    """Провайдер швидкості із заготовленою відповіддю; рахує, скільки разів його питали."""

    def __init__(self, reply: object) -> None:
        self.reply = reply
        self.calls = 0

    async def measure(self, url: str, strategy: Strategy) -> object:
        self.calls += 1
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def _speed_state(monkeypatch, selection: str, evidence: str):
    """Одна клітинка: справжні вимір, покриття, бал і відповідь API."""
    import asyncio

    import app.audit.orchestrator as orchestrator
    from app.audit.orchestrator import AuditOutcome, compute_scores_safe

    reply, response_ms = EVIDENCE[evidence]
    provider = _Provider(reply() if reply else None)
    monkeypatch.setattr(orchestrator, "get_provider", lambda name=None: provider)
    modules = SELECTIONS[selection]
    options = AuditOptions(
        modules=set(modules) if modules is not None else None,
        strategies=[Strategy.MOBILE] if reply else [],
    )
    ctx = _ctx(response_ms)
    degraded: list[Degradation] = []
    ctx.performance = asyncio.run(
        orchestrator._measure_performance(ctx.entry_url, options, degraded)
    )
    skipped, partial = _module_coverage(options, ctx, ctx.performance, degraded)
    overall, scores = compute_scores_safe([], skipped)
    outcome = AuditOutcome(
        context=ctx,
        issues=[],
        scores=scores,
        overall=overall,
        degraded=degraded,
        skipped_modules=skipped,
        partial_modules=partial,
    )
    source, _, result = _presented(outcome)
    return outcome, source, result, provider.calls


@pytest.mark.parametrize("evidence", sorted(EVIDENCE))
@pytest.mark.parametrize("selection", sorted(SELECTIONS))
def test_performance_state_follows_the_request_and_the_data(monkeypatch, selection, evidence):
    from app.audit.scoring import MIN_COVERED_WEIGHT, MODULE_WEIGHT, active_weights

    outcome, source, result, calls = _speed_state(monkeypatch, selection, evidence)
    modules = SELECTIONS[selection]
    requested = set(Module) if modules is None else modules
    speed_requested = Module.PERFORMANCE in requested
    asked = EVIDENCE[evidence][0] is not None

    # Швидкість, виключену клієнтом, не міряють і не судять: провайдера не питали.
    assert calls == (1 if speed_requested and asked else 0)
    if speed_requested:
        gap, scored, speed_partial = REQUESTED_SPEED[evidence]
        speed_reason = None if scored else NOT_MEASURED
    else:
        gap, scored, speed_partial, speed_reason = None, False, False, EXCLUDED

    # Доступність приходить тим самим запитом, що й швидкість.
    if Module.ACCESSIBILITY not in requested:
        accessibility_gaps, accessibility_reason = [_OFF], EXCLUDED
    elif not speed_requested:
        accessibility_gaps, accessibility_reason = [_NOT_RUN], NOT_MEASURED
    elif evidence == "valid":
        accessibility_gaps, accessibility_reason = [], None
    else:
        # Прогалину пояснює деградація швидкості; окремої немає.
        accessibility_gaps, accessibility_reason = [], NOT_MEASURED

    expected = [_RAISED] if gap == _RAISED else []
    expected += [(module.value, *_OFF) for module in Module if module not in requested]
    if accessibility_gaps == [_NOT_RUN]:
        expected.append((Module.ACCESSIBILITY.value, *_NOT_RUN))
    if gap in (_NO_VITALS, _NO_METRICS):
        expected.append(gap)
    # Аналітика (G3): фікстура — одна сторінка без рендеру й без лічильника.
    # Лічильник, доданий скриптом, ми побачити не могли, тож висновок про
    # вимірювання неповний, і про це є рівно один запис. Модуль tech при
    # цьому лишається в балі — деградація неповноти не є збоєм.
    if Module.TECH in requested:
        expected.append(
            ("tech.analytics", DegradationKind.PARTIAL_DATA, "notice.analytics.render_incomplete")
        )
    assert [(d.scope, d.kind, d.reason_key) for d in outcome.degraded] == expected
    assert len({d.scope for d in outcome.degraded}) == len(outcome.degraded), "прогалина двічі"
    assert (Module.TECH in outcome.partial_modules) is (Module.TECH in requested)
    assert _accessibility_gaps(outcome) == accessibility_gaps

    # Бал, прапорці й причина кажуть одне й те саме — у рушії й в API.
    speed = _speed(result)
    assert (_SPEED in outcome.scores) is scored
    assert (Module.PERFORMANCE in outcome.skipped_modules) is not scored
    assert (Module.PERFORMANCE in outcome.partial_modules) is speed_partial
    assert (speed.score is not None, speed.excluded, speed.partial) == (
        scored,
        not scored,
        speed_partial,
    )
    assert speed.withheld_reason == speed_reason
    _assert_accessibility(outcome, result, accessibility_reason)

    # Збій — лише провайдер, що не дав жодного виміру або впав.
    failed = gap in (_NO_METRICS, _RAISED)
    assert source.status is (_PARTIAL if failed else _COMPLETED)

    # Невиміряне не важить нічого; решта ваги перерозподіляється.
    measured = {
        module
        for module in requested
        if (module is not Module.PERFORMANCE or scored)
        and (module is not Module.ACCESSIBILITY or accessibility_reason is None)
    }
    weights = active_weights(outcome.skipped_modules)
    assert set(weights) == measured
    covered = sum(MODULE_WEIGHT[module] for module in measured)
    if scored:
        assert weights[Module.PERFORMANCE] == pytest.approx(
            MODULE_WEIGHT[Module.PERFORMANCE] / covered
        )
    assert speed.weight == pytest.approx(weights.get(Module.PERFORMANCE, 0.0))
    assert outcome.overall == (100 if covered >= MIN_COVERED_WEIGHT else None)
    assert result.overall_score == outcome.overall


@pytest.mark.parametrize("response_times", [True, False], ids=["with_times", "without_times"])
@pytest.mark.parametrize(
    "selection", ["all_but_seo", "all_but_accessibility", "performance_and_seo", "performance_only"]
)
def test_a_filter_that_keeps_performance_changes_only_the_weights(selection, response_times):
    """Фільтр зі швидкістю судить її так само, як аудит без фільтра.

    Справжній знімок, відповіді провайдера в якому не прочитали: той самий
    стан швидкості, та сама деградація, ті самі бали модулів. Різниться лише
    перерозподіл ваг між модулями, які просили.
    """
    from app.audit.orchestrator import rescore
    from app.audit.scoring import MIN_COVERED_WEIGHT, MODULE_WEIGHT

    def run(modules: set[Module] | None):
        ctx = _snapshot("schema1_small_site.json")
        ctx.performance = [_perf(False, "HTTP 429")]
        if not response_times:
            for page in ctx.pages:
                page.response_ms = 0
        return rescore(ctx, AuditOptions(modules=modules))

    requested = SELECTIONS[selection]
    assert requested is not None
    unfiltered, filtered = run(None), run(set(requested))

    def speed(outcome):
        return (
            [d for d in outcome.degraded if d.scope == _SPEED],
            Module.PERFORMANCE in outcome.skipped_modules,
            Module.PERFORMANCE in outcome.partial_modules,
            outcome.scores.get(_SPEED),
        )

    assert speed(filtered) == speed(unfiltered)
    assert len(speed(filtered)[0]) == 1
    assert filtered.scores == {
        name: score for name, score in unfiltered.scores.items() if Module(name) in requested
    }
    measured = [(m, w) for m, w in MODULE_WEIGHT.items() if m.value in filtered.scores]
    covered = sum(w for _, w in measured)
    expected = round(sum(filtered.scores[m.value] * (w / covered) for m, w in measured))
    assert filtered.overall == (expected if covered >= MIN_COVERED_WEIGHT else None)


@pytest.mark.parametrize("response_times", [True, False], ids=["with_times", "without_times"])
def test_a_provider_that_raised_is_reported_once_with_or_without_a_filter(response_times):
    """Виняток провайдера записує сам вимір; покриття другої прогалини не додає.

    Без фільтра звіт показував ту саму подію двічі — «дані про швидкість
    неповні» з текстом винятку й одразу «провайдер не повернув метрики:
    немає відповіді». Під фільтром бал швидкості лишався без застереження.
    Справжній `run_audit`, підмінено лише введення-виведення; семантичний
    шар вимкнено, тож клієнта моделі немає.
    """
    from app.audit.llm.factory import get_analyst

    seen = {}
    for name in ("no_filter", "all_but_seo", "performance_only"):
        modules = SELECTIONS[name]
        with pytest.MonkeyPatch.context() as patch:
            outcome = _offline_audit(
                patch,
                factory=lambda enabled=None, model=None: get_analyst(enabled=False),
                provider=_Provider(RAISED),
                modules=set(modules) if modules is not None else None,
                response_times=response_times,
            )
        source, _, result = _presented(outcome)
        (gap,) = [d for d in outcome.degraded if d.scope == _SPEED]
        assert (gap.scope, gap.kind, gap.reason_key) == _RAISED
        assert gap.reason_params == {"detail": str(RAISED)}
        assert [g.scope for g in result.missing_data].count(_SPEED) == 1
        assert source.status is AuditStatus.PARTIAL
        seen[name] = (
            _SPEED in outcome.scores,
            Module.PERFORMANCE in outcome.partial_modules,
            _speed(result).withheld_reason,
        )
    expected = (True, True, None) if response_times else (False, False, NOT_MEASURED)
    assert set(seen.values()) == {expected}, seen


def test_blindness_is_still_decided_first_when_requested_performance_is_not_measured():
    """Сліпота йде перед фільтром і перед швидкістю, яку просили (G2.1)."""
    from app.audit.types import CRAWL_BLIND

    options = AuditOptions(modules=set(Module) - {Module.SEO})
    outcome, source, result = _audit_state(options, [_perf(False, "429")], _blocked_ctx())

    assert [(d.scope, d.kind, d.reason_key) for d in outcome.degraded] == [
        (CRAWL_BLIND, DegradationKind.COLLECTOR_FAILED, "notice.crawl.blind"),
        (Module.SEO.value, *_OFF),
        _NO_METRICS,
    ]
    assert source.status is AuditStatus.PARTIAL
    assert outcome.overall is None
    assert _speed(result).withheld_reason == NOT_MEASURED
    _assert_accessibility(outcome, result, NOT_MEASURED)


# ── G3: невирішений висновок про аналітику робить модуль неповним ─────────
#
# Прийнята модель станів має для `tech.analytics` два випадки, у яких
# знахідка є, а відповіді немає: вимірювання без впізнаного вендора
# (NO_VERDICT + COMPLETE) і відсутність сліду там, де рендер міг би його
# показати (FAIL + PARTIAL). Обидва лишають бал і додають РІВНО один запис.

ANALYTICS_SCOPE = "tech.analytics"
_UNIDENTIFIED = (ANALYTICS_SCOPE, DegradationKind.PARTIAL_DATA, "notice.analytics.unidentified")
_RENDER_INCOMPLETE = (
    ANALYTICS_SCOPE, DegradationKind.PARTIAL_DATA, "notice.analytics.render_incomplete"
)


def _rendered_ctx(*, analytics=None, requests=None, runtime=None) -> SiteContext:
    from app.audit.types import RenderResult

    ctx = _ctx(120)
    page = ctx.pages[0]
    after = PageSignals(url=page.url, status_code=200, word_count=FIXTURE_WORDS)
    after.analytics = list(analytics or [])
    ctx.renders[page.url] = RenderResult(
        url=page.url, rendered=True, html="<html/>", signals=after,
        requests=list(requests or []), runtime_analytics=list(runtime or []),
    )
    return ctx


def _analytics_state(ctx: SiteContext, options: AuditOptions | None = None):
    degraded: list[Degradation] = []
    _, partial = _module_coverage(options or AuditOptions(), ctx, [_perf(True)], degraded)
    gaps = [(d.scope, d.kind, d.reason_key) for d in degraded if d.scope == ANALYTICS_SCOPE]
    return gaps, partial, degraded


def test_a_verified_vendor_leaves_no_analytics_gap():
    gaps, partial, _ = _analytics_state(_rendered_ctx(analytics=["google_analytics"]))

    assert gaps == []
    assert Module.TECH not in partial


def test_unidentified_measurement_marks_the_module_partial_once():
    """Власний `/api/collect` щось міряє: бал лишається, неповнота видима."""
    gaps, partial, degraded = _analytics_state(
        _rendered_ctx(requests=["https://example.com/api/collect"])
    )

    assert gaps == [_UNIDENTIFIED]
    assert Module.TECH in partial
    (gap,) = [d for d in degraded if d.scope == ANALYTICS_SCOPE]
    assert gap.is_failure is False, "неповні дані — не збій аудиту"
    assert gap.affected_modules == [Module.TECH]
    assert gap.reason_params["detail"], "неоднозначний доказ названо"


def test_no_signal_with_a_rendered_page_is_complete_not_partial():
    gaps, partial, _ = _analytics_state(_rendered_ctx())

    assert gaps == []
    assert Module.TECH not in partial


def test_no_signal_without_a_render_is_partial():
    gaps, partial, _ = _analytics_state(_ctx(120))

    assert gaps == [_RENDER_INCOMPLETE]
    assert Module.TECH in partial


def test_a_verified_vendor_beside_unidentified_traffic_leaves_no_gap():
    ctx = _rendered_ctx(requests=["https://api.segment.io/v1/t", "https://example.com/api/collect"])

    gaps, partial, _ = _analytics_state(ctx)

    assert gaps == []
    assert Module.TECH not in partial


def test_no_fetched_page_keeps_the_existing_not_measured_behaviour():
    gaps, partial, _ = _analytics_state(_blocked_ctx())

    assert gaps == []
    assert Module.TECH not in partial


def test_the_module_filter_silences_the_analytics_gap():
    gaps, _, _ = _analytics_state(_ctx(120), AuditOptions(modules={Module.SEO}))

    assert gaps == []


def test_the_analytics_gap_is_never_recorded_twice():
    """Перерахунок поверх тієї самої деградації другого запису не додає."""
    ctx = _rendered_ctx(requests=["https://example.com/api/collect"])
    degraded: list[Degradation] = []

    _module_coverage(AuditOptions(), ctx, [_perf(True)], degraded)
    _module_coverage(AuditOptions(), ctx, [_perf(True)], degraded)

    assert [d.scope for d in degraded].count(ANALYTICS_SCOPE) == 1
