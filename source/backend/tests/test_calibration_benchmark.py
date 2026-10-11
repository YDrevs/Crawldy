"""Оркестрація прогону КАЛІБРУВАЛЬНОГО корпусу — без тисячі живих сайтів.

Назва файлу довша навмисно. `tests/test_benchmark.py` — це зовсім інший
benchmark: порівняння клієнта з конкурентами (`app/report/benchmark.py`).
Одне слово на дві незвʼязані речі вже коштувало одинадцяти затертих
тестів продуктової фічі, і збіг імен помітив лише `git status` перед
комітом.

Перевіряти інфраструктуру справжніми сайтами означало б залежати від
чужої мережі в кожному запуску тестів. Тут підмінений рівно один шар —
сам аудит; усе решта справжнє: маніфест, сховище, продовження, класи
збоїв, аналіз і черга на перегляд.

Найважливіші випадки — не «працює», а «не зашкодить»: один сайт не валить
прогін, перерваний прогін продовжується, а гард платних викликів падає
закрито.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from scripts.benchmark import analyzer, guard, manifest, review
from scripts.benchmark.config import Provenance, RunConfig, RunId
from scripts.benchmark.failures import Failure, classify, ours, retryable
from scripts.benchmark.results import ResultStore, SiteResult
from scripts.benchmark.runner import Runner, sites_for


@pytest.fixture(autouse=True)
def _guard_is_not_left_installed():
    """Гард — глобальний стан процесу, і його треба знімати.

    `install()` підміняє `anthropic` і `openai` у `sys.modules`, тобто
    впливає на весь інтерпретатор. Поки фікстури не було, тести цього
    файлу тихо ламали 23 інші — усе, що після них імпортувало справжні
    SDK, отримувало заглушку. Кожен файл окремо був зелений, падала лише
    повна вибірка: дефект залежав від порядку виконання.

    Фікстура автоматична навмисно. Розраховувати, що кожен наступний
    тест згадає прибрати за собою, вже не вийшло один раз.
    """
    yield
    guard.restore()

CORPUS = """
sites:
  - url: https://alpha.test
    segment: saas
    tags: [spa]
  - url: https://beta.test
    segment: ecommerce
  - url: https://gamma.test
    segment: saas
    enabled: false
  - https://delta.test
"""


@pytest.fixture
def corpus(tmp_path):
    path = tmp_path / "corpus.yaml"
    path.write_text(CORPUS, encoding="utf-8")
    return manifest.load(path)


def FakeOutcome(ctx, overall=70):
    """СПРАВЖНІЙ `AuditOutcome`, а не схожий на нього обʼєкт.

    Перша версія цього тесту підставляла власний клас із полем `status`,
    якого в `AuditOutcome` немає. Тести проходили, а живий прогін упав на
    першому ж сайті: перевірялася вигадка, а не продукт. Тепер тут той
    самий тип, що повертає рушій, і розбіжність структури впаде тут.
    """
    from app.audit.orchestrator import AuditOutcome

    return AuditOutcome(
        context=ctx,
        issues=[],
        scores={"seo": overall, "tech": 65},
        overall=overall,
        degraded=[],
        versions={"detector": "d1", "scoring": "s1"},
    )


def _context(pages=2):
    from tests.factories import context, page_from_html

    html = (
        "<html lang='en'><head><title>T</title></head><body><h1>H</h1>"
        "<p>Some words on the page.</p></body></html>"
    )
    return context(*[
        page_from_html(html, url=f"https://alpha.test/p{i}") for i in range(pages)
    ])


# ── 1–4. Маніфест ─────────────────────────────────────────────────────────


def test_a_manifest_parses_sites_segments_and_tags(corpus):
    """1. Формат поблажливий: рядок з адресою теж валідний запис."""
    assert len(corpus.sites) == 4
    assert len(corpus.active) == 3  # gamma вимкнено
    alpha = next(s for s in corpus.sites if "alpha" in s.url)
    assert alpha.segment == "saas" and alpha.tags == ("spa",)
    plain = next(s for s in corpus.sites if "delta" in s.url)
    assert plain.segment == "other" and plain.enabled


def test_site_ids_are_stable_and_distinguish_paths():
    """2. Ідентифікатор має пережити перезапуск і не злити різні адреси."""
    first = manifest.site_id_for("https://example.com")
    assert first == manifest.site_id_for("https://example.com/")
    assert first != manifest.site_id_for("https://example.com/uk")


def test_a_broken_manifest_reports_problems_without_raising(tmp_path):
    """3. Зламаний корпус — це повідомлення, а не стектрейс."""
    path = tmp_path / "bad.yaml"
    path.write_text("sites:\n  - {}\n  - url: x.test\n    segment: nonsense\n", encoding="utf-8")
    found = manifest.load(path)
    assert found.problems
    assert any("немає url" in p for p in found.problems)
    assert any("сегмент" in p for p in found.problems)


def test_a_missing_manifest_is_reported_not_raised(tmp_path):
    """4. Немає файлу — теж повідомлення."""
    found = manifest.load(tmp_path / "nope.yaml")
    assert found.problems and not found.sites


def test_disabled_sites_do_not_change_the_corpus_fingerprint(tmp_path):
    """5. Додати вимкнений рядок — не зробити прогін іншим."""
    path = tmp_path / "c.yaml"
    path.write_text(CORPUS, encoding="utf-8")
    before = manifest.load(path).fingerprint()
    path.write_text(CORPUS + "  - url: https://off.test\n    enabled: false\n",
                    encoding="utf-8")
    assert manifest.load(path).fingerprint() == before


# ── 6–8. Ідентифікатор прогону й походження ───────────────────────────────


def test_the_run_id_is_deterministic(corpus):
    """6. Той самий корпус, конфігурація й коміт — той самий прогін.

    Інакше перезапуск починав би новий набір даних замість продовження.
    """
    config = RunConfig()
    provenance = Provenance(commit="abc123def456", dirty=False,
                            scoring_version="s1", detector_version="d1")
    first = RunId.build(corpus.fingerprint(), config, provenance).value
    second = RunId.build(corpus.fingerprint(), config, provenance).value
    assert first == second


def test_a_different_config_is_a_different_run(corpus):
    """7. Інший бюджет краулу — інші дані, і змішувати їх не можна."""
    provenance = Provenance(commit="abc123def456", dirty=False,
                            scoring_version="s1", detector_version="d1")
    a = RunId.build(corpus.fingerprint(), RunConfig(max_pages=25), provenance).value
    b = RunId.build(corpus.fingerprint(), RunConfig(max_pages=8), provenance).value
    assert a != b


def test_provenance_carries_the_rule_versions():
    """8. Без версій правил дельта балів нічого не означає."""
    found = Provenance.current()
    assert found.scoring_version and found.detector_version
    assert len(found.commit) >= 7


# ── 9–13. Прогін, ізоляція збоїв, продовження ─────────────────────────────


def _runner(corpus, tmp_path, monkeypatch, behaviour):
    from scripts.benchmark import runner as runner_module

    async def fake_audit(url, options=None):
        return await behaviour(url)

    monkeypatch.setattr(runner_module, "measurements",
                        type("M", (), {"collect": staticmethod(lambda ctx: {"crawl": {}})}))
    import app.audit.orchestrator as orchestrator

    monkeypatch.setattr(orchestrator, "run_audit", fake_audit)
    # `min_free=0` навмисно: інакше тест залежав би від вільного місця
    # на машині, де його запускають. Сам запобіжник перевіряється окремо.
    return Runner(
        corpus, RunConfig(concurrency=2, site_timeout_s=5), tmp_path, min_free=0
    )


def test_a_single_failing_site_does_not_stop_the_run(corpus, tmp_path, monkeypatch):
    """9. Найважливіша властивість: одна погана адреса не валить тисячу."""
    async def behaviour(url):
        if "beta" in url:
            raise RuntimeError("ConnectError: connection refused")
        return FakeOutcome(_context())

    runner = _runner(corpus, tmp_path, monkeypatch, behaviour)
    summary = asyncio.run(runner.run())
    assert summary["ok"] == 2 and summary["failed"] == 1
    failed = runner.store.failed()
    assert next(iter(failed.values()))["failure"] == Failure.CONNECTION.value


def test_a_hanging_site_is_cut_by_the_timeout(corpus, tmp_path, monkeypatch):
    """10. Зависла сторінка не має тримати прогін нескінченно."""
    async def behaviour(url):
        if "alpha" in url:
            await asyncio.sleep(30)
        return FakeOutcome(_context())

    runner = _runner(corpus, tmp_path, monkeypatch, behaviour)
    runner.config = RunConfig(concurrency=2, site_timeout_s=1)
    summary = asyncio.run(runner.run())
    assert summary["failed"] == 1
    assert next(iter(runner.store.failed().values()))["failure"] == Failure.SITE_TIMEOUT.value


def test_completed_sites_are_skipped_on_the_second_run(corpus, tmp_path, monkeypatch):
    """11. Продовження, а не перезапуск."""
    async def behaviour(url):
        return FakeOutcome(_context())

    runner = _runner(corpus, tmp_path, monkeypatch, behaviour)
    asyncio.run(runner.run())
    assert runner.pending() == []
    again = asyncio.run(runner.run())
    assert again["attempted"] == 0


def test_retry_only_touches_failures_that_can_change(corpus, tmp_path, monkeypatch):
    """12. 403 другого разу не зміниться; обрив звʼязку може.

    Повторювати все підряд означало б ховати власні дефекти повтором.
    """
    async def behaviour(url):
        if "alpha" in url:
            raise RuntimeError("ConnectError: connection refused")
        if "beta" in url:
            raise RuntimeError("HTTP 403 Forbidden")
        return FakeOutcome(_context())

    runner = _runner(corpus, tmp_path, monkeypatch, behaviour)
    asyncio.run(runner.run())
    retryable_sites = [s.url for s in runner.pending(retry_failed=True)]
    assert any("alpha" in u for u in retryable_sites)
    assert not any("beta" in u for u in retryable_sites)


def test_an_interrupted_run_keeps_what_it_already_wrote(tmp_path):
    """13. Обірваний останній рядок не має валити читання набору."""
    store = ResultStore(tmp_path / "run")
    store.append(SiteResult(site_id="a", url="https://a.test", run_id="r"))
    with store.results_path.open("a", encoding="utf-8") as handle:
        handle.write('{"site_id": "b", "url": "https:')  # обірвано
    rows = store.rows()
    assert len(rows) == 1 and rows[0]["site_id"] == "a"


# ── 14–16. Знімки й місце ─────────────────────────────────────────────────


def test_snapshots_live_inside_their_run(corpus, tmp_path, monkeypatch):
    """14. Знімки різних прогонів у спільній теці не розрізнити."""
    async def behaviour(url):
        return FakeOutcome(_context())

    runner = _runner(corpus, tmp_path, monkeypatch, behaviour)
    asyncio.run(runner.run())
    saved = list(runner.store.snapshots.glob("*.json"))
    assert len(saved) == 3
    assert runner.run_id in str(saved[0])
    for row in runner.store.rows():
        assert (runner.store.snapshots / row["snapshot"]).exists()


def test_the_run_records_its_configuration_and_guard(corpus, tmp_path, monkeypatch):
    """15. Конфігурацію треба зберігати: бюджет краулу змінює те, що видно."""
    async def behaviour(url):
        return FakeOutcome(_context())

    runner = _runner(corpus, tmp_path, monkeypatch, behaviour)
    asyncio.run(runner.run())
    meta = runner.store.read_meta()
    assert meta["config"]["max_pages"] == 25
    assert meta["provenance"]["scoring_version"]
    assert any("anthropic" in entry for entry in meta["paid_ai_guard"])


def test_an_empty_crawl_is_not_counted_as_success(corpus, tmp_path, monkeypatch):
    """16. Аудит завершився, дивитись нема на що — окремий стан."""
    async def behaviour(url):
        return FakeOutcome(_context(pages=0))

    runner = _runner(corpus, tmp_path, monkeypatch, behaviour)
    summary = asyncio.run(runner.run())
    assert summary["ok"] == 0
    assert all(r["failure"] == Failure.EMPTY_CRAWL.value for r in runner.store.rows())


# ── 17–19. Класи збоїв ────────────────────────────────────────────────────


@pytest.mark.parametrize("text,expected", [
    ("UnsafeUrlError: DNS не резолвиться: x", Failure.DNS),
    ("SSLError: certificate verify failed", Failure.TLS),
    ("ConnectError: connection refused", Failure.CONNECTION),
    ("HTTP 403 Forbidden", Failure.ACCESS_DENIED),
    ("хост резолвиться у приватний IP", Failure.UNSAFE_TARGET),
    ("playwright browser closed", Failure.RENDERER),
])
def test_failures_are_classified_not_lumped_together(text, expected):
    """17. «Не вдалося» без причини — марні дані."""
    assert classify(RuntimeError(text)) is expected


def test_our_failures_are_distinguished_from_the_worlds():
    """18. Виняток усередині Crawldy — наш дефект, а не властивість сайту."""
    assert ours(Failure.INTERNAL) and ours(Failure.RENDERER)
    assert not ours(Failure.DNS) and not ours(Failure.ACCESS_DENIED)


def test_only_transient_failures_are_retried():
    """19. Повтор ховає постійні дефекти, тож він не для всіх причин."""
    assert retryable(Failure.CONNECTION) and retryable(Failure.SITE_TIMEOUT)
    assert not retryable(Failure.INTERNAL) and not retryable(Failure.ACCESS_DENIED)


# ── 20–24. Аналіз ─────────────────────────────────────────────────────────


def _row(site, *, codes=(), overall=70, segment="saas", outcome="ok",
         scoring="s1", detector="d1", duration=10.0):
    return {
        "site_id": site, "url": f"https://{site}.test", "run_id": "r",
        "segment": segment, "outcome": outcome, "overall": overall,
        "duration_s": duration,
        "scores": {"seo": overall}, "coverage": {"pages_ok": 5, "rendered": 3, "renders_ok": 3},
        "provenance": {"scoring_version": scoring, "detector_version": detector,
                       "commit": "abc", "dirty": False},
        "findings": [{"code": c, "issue_key": c, "module": "seo", "severity": "info",
                      "confidence": "high", "evidence": {}} for c in codes],
        "measurements": {},
    }


def test_the_analyzer_computes_firing_frequency():
    """20. Головне число калібрування — частка сайтів, а не кількість знахідок."""
    rows = [_row(f"s{i}", codes=("seo.a",) if i < 3 else ()) for i in range(10)]
    found = analyzer.analyse(rows)
    assert found.detectors["seo.a"]["sites"] == 3
    assert found.detectors["seo.a"]["share"] == 0.3


def test_mixing_rule_versions_is_reported_loudly():
    """21. Два прогони по різні боки зміни правил не порівнюються.

    Мовчазне зведення тут — найдорожча з можливих помилок аналізу.
    """
    rows = [_row("a", scoring="s1"), _row("b", scoring="s2")]
    found = analyzer.analyse(rows)
    assert any("scoring_version" in w for w in found.warnings)


def test_ubiquitous_and_silent_detectors_are_flagged_not_judged():
    """22. «Спрацював у всіх» буває і правдою, і вадою — вирішує людина."""
    rows = [_row(f"s{i}", codes=("seo.everywhere",)) for i in range(10)]
    found = analyzer.analyse(rows, known_codes=["seo.everywhere", "seo.never"])
    assert any("seo.everywhere" in a for a in found.attention)
    assert found.silent_detectors == ["seo.never"]


def test_our_own_failures_are_surfaced_as_a_warning():
    """23. Дефект прогону не має тонути серед мережевих збоїв."""
    rows = [_row("a"), {**_row("b", outcome="failed"), "failure": "internal"}]
    found = analyzer.analyse(rows)
    assert found.our_failures == 1
    assert any("нашому боці" in w for w in found.warnings)


def test_segments_and_runtime_outliers_are_reported():
    """24. Зріз за сегментом і найповільніші сайти — обидва для очей."""
    rows = [_row("a", segment="saas", overall=80, duration=5.0),
            _row("b", segment="ecommerce", overall=40, duration=900.0)]
    found = analyzer.analyse(rows)
    assert set(found.segments) == {"saas", "ecommerce"}
    assert found.runtime["slowest"][0]["url"].endswith("b.test")


def test_malformed_rows_do_not_break_the_analyzer():
    """25. Аналіз читає те, що є, а не падає на тому, чого немає."""
    assert analyzer.analyse([]).warnings
    analyzer.analyse([{"site_id": "x", "outcome": "ok"}])


# ── 26–28. Черга на перегляд ──────────────────────────────────────────────


def test_the_review_queue_offers_fired_and_silent_cases():
    """26. Для рішення потрібні обидва боки, а не лише спрацювання."""
    rows = [_row(f"s{i}", codes=("seo.anchor_text",) if i < 2 else ()) for i in range(6)]
    for row in rows:
        row["snapshot"] = f"{row['site_id']}.json"
    queue = review.build(rows, detectors=("seo.anchor_text",))
    kinds = {c["kind"] for c in queue["seo.anchor_text"]}
    assert "fired" in kinds and "silent" in kinds


def test_the_review_queue_is_deterministic():
    """27. Двоє людей мусять дивитися ті самі приклади."""
    rows = [_row(f"s{i}", codes=("seo.anchor_text",)) for i in range(20)]
    first = review.build(rows, detectors=("seo.anchor_text",))
    second = review.build(rows, detectors=("seo.anchor_text",))
    assert first == second


def test_the_review_queue_spreads_across_segments():
    """28. Десять магазинів нічого не кажуть про документацію."""
    rows = [
        _row(f"s{i}", codes=("seo.anchor_text",),
             segment="ecommerce" if i < 10 else "documentation")
        for i in range(14)
    ]
    queue = review.build(rows, detectors=("seo.anchor_text",), per_kind=6)
    segments = {c["segment"] for c in queue["seo.anchor_text"] if c["kind"] == "fired"}
    assert segments == {"ecommerce", "documentation"}


# ── 29–31. Гард платних викликів ──────────────────────────────────────────


def test_the_guard_blocks_paid_clients():
    """29. Тисяча сайтів × платний виклик — рахунок, якого ніхто не планував."""
    guard.install()
    assert guard.is_installed()
    import anthropic
    import openai

    with pytest.raises(guard.PaidCallBlocked):
        anthropic.AsyncAnthropic(api_key="x")
    with pytest.raises(guard.PaidCallBlocked):
        openai.AsyncOpenAI(api_key="x")


def test_the_guard_disables_the_paid_layers_in_settings():
    """30. Гард не покладається на налаштування, але й лишає їх вимкненими."""
    from app.core.config import settings

    guard.install()
    assert settings.llm_enabled is False and settings.enrich_enabled is False


def test_the_runner_refuses_to_start_without_the_guard(corpus, tmp_path, monkeypatch):
    """31. Падає закрито: без гарда прогін не починається взагалі."""
    from scripts.benchmark import runner as runner_module

    monkeypatch.setattr(runner_module.guard, "is_installed", lambda: False)
    runner = Runner(corpus, RunConfig(), tmp_path, min_free=0)
    with pytest.raises(RuntimeError, match="гард"):
        asyncio.run(runner.run())


# ── 32. Зрізи корпусу ─────────────────────────────────────────────────────


def test_a_corpus_can_be_sliced_for_a_pilot(corpus):
    """32. Пілот на 30–50 сайтах — це зріз корпусу, а не окремий файл."""
    assert [s.url for s in sites_for(corpus, segments=["saas"])] == ["https://alpha.test"]
    assert [s.url for s in sites_for(corpus, tags=["spa"])] == ["https://alpha.test"]


def test_results_round_trip_through_jsonl(tmp_path):
    """33. Формат має пережити запис і читання без втрат."""
    store = ResultStore(tmp_path / "run")
    result = SiteResult(site_id="a", url="https://a.test", run_id="r",
                        findings=[{"code": "seo.x"}], measurements={"crawl": {"pages_ok": 3}})
    store.append(result)
    rows = store.rows()
    assert rows[0]["findings"][0]["code"] == "seo.x"
    assert rows[0]["measurements"]["crawl"]["pages_ok"] == 3
    assert json.loads(store.results_path.read_text(encoding="utf-8").strip())


# ── 34. Спроба і сайт — різні одиниці ─────────────────────────────────────


def test_a_retried_site_is_counted_once_not_twice(tmp_path):
    """34. Журнал тримає всі спроби, аналіз рахує сайти.

    Живий пілот дав «8 рядків, 5 успішних, 3 збої» на корпусі з шести
    сайтів: повторений сайт потрапляв і в успішні, і в збійні. На тисячі
    сайтів це завищило б частку збоїв рівно на кількість повторів.
    """
    store = ResultStore(tmp_path / "run")
    store.append(SiteResult(site_id="a", url="https://a.test", run_id="r",
                            outcome="failed", failure="timeout", attempt=1))
    store.append(SiteResult(site_id="a", url="https://a.test", run_id="r",
                            outcome="ok", overall=62, attempt=2))
    store.append(SiteResult(site_id="b", url="https://b.test", run_id="r", overall=70))

    assert len(store.rows()) == 3, "журнал не має губити спроби"
    assert len(store.latest()) == 2, "аналіз рахує сайти, а не спроби"

    found = analyzer.analyse(store.latest())
    assert (found.rows, found.ok, found.failed) == (2, 2, 0)
    assert found.retried == 1, "повтор має бути видно: це нестабільність вимірювання"


def test_analysis_of_a_missing_run_says_so_instead_of_inventing_an_empty_one(tmp_path):
    """35. Читання не створює теку.

    `ResultStore` створює теку, якої немає. Для запису це правильно, для
    читання — ні: аналіз за ідентифікатором прогону мовчки робив порожню
    теку й повідомляв «немає рядків», описуючи себе, а не прогін.
    """
    from scripts.benchmark.cli import _locate

    (tmp_path / "runs" / "real").mkdir(parents=True)
    (tmp_path / "runs" / "real" / "results.jsonl").write_text("", encoding="utf-8")

    assert _locate("real", tmp_path / "runs") == tmp_path / "runs" / "real"

    with pytest.raises(SystemExit) as caught:
        _locate("no-such-run", tmp_path / "runs")
    assert "real" in str(caught.value), "помилка має назвати те, що є насправді"
    assert not (tmp_path / "runs" / "no-such-run").exists()


# ── 36. Бюджет прогону — теж правило ──────────────────────────────────────


def test_a_reduced_crawl_budget_is_announced_not_hidden():
    """36. Урізаний бюджет описує наш прогін, а не сайт.

    Калібрування вже ходило на 8 сторінок замість продуктових 25, і
    «жодного спрацювання» тоді описувало бюджет, а не чек. Відхилення
    має бачити читач результату, а не той, хто памʼятає команду запуску.
    """
    assert RunConfig().deviations() == [], "продуктовий бюджет не є відхиленням"

    thin = RunConfig(max_pages=8, render_max_pages=2)
    assert any("max_pages=8" in d for d in thin.deviations())
    assert any("render_max_pages=2" in d for d in thin.deviations())

    # Швидкість прогону не змінює того, що видно, — і відхиленням не є.
    assert RunConfig(concurrency=1, max_attempts=5).deviations() == []

    # А от час — змінює, і в обидва боки: коротший обриває сайт, який
    # продукт дочитує, довший дочитує той, який продукт покинув би.
    assert RunConfig(site_timeout_s=900).deviations() != []

    found = analyzer.analyse([
        {"site_id": "a", "outcome": "ok", "overall": 60, "provenance": {},
         "config": thin.as_dict(), "findings": [], "coverage": {}},
    ])
    assert any("бюджет прогону" in w for w in found.warnings)


def test_analysis_survives_rows_written_by_another_version(tmp_path):
    """37. Зайве поле конфігурації — не привід упасти на старих даних."""
    found = analyzer.analyse([
        {"site_id": "a", "outcome": "ok", "overall": 60, "provenance": {},
         "config": {**RunConfig().as_dict(), "field_from_the_future": 1},
         "findings": [], "coverage": {}},
    ])
    assert found.ok == 1


def test_the_guard_blocks_the_real_provider_adapters(monkeypatch):
    """38. Позитивний контроль на справжніх шарах, а не на гарді окремо.

    Гард підміняє модуль, бо SDK імпортується **всередині** методу
    провайдера. Перевірка `anthropic.AsyncAnthropic(...)` показує, що
    підміна стала, і не показує, що продуктовий шлях справді проходить
    через неї. Тут викликається саме `_ensure_client()` обох шарів —
    того, що стоїть до скора й уміє створити знахідку, і того, що після.

    Ключ виставляється навмисно: без нього провайдер відмовиться раніше
    за гард, і зелений тест не доводив би нічого.
    """
    from app.audit.llm.anthropic_analyst import AnthropicAnalyst
    from app.core.config import settings
    from app.enrich.providers.anthropic import AnthropicProvider

    guard.install()
    monkeypatch.setattr(settings, "anthropic_api_key", "sk-ant-not-a-real-key")

    for adapter in (AnthropicProvider(), AnthropicAnalyst()):
        with pytest.raises(guard.PaidCallBlocked):
            adapter._ensure_client()


def test_the_guard_can_be_taken_off_again(monkeypatch):
    """39. Глобальний стан має шлях назад.

    Гард підміняє записи в `sys.modules`, тобто діє на весь процес. Поки
    зняти його було нічим, тести цього файлу ламали 23 інші — усе, що
    після них імпортувало справжній SDK, отримувало заглушку. Кожен файл
    окремо лишався зеленим, падала лише повна вибірка.
    """
    import anthropic

    from app.core.config import settings

    real = anthropic.AsyncAnthropic
    # Через monkeypatch, а не присвоєнням: `restore()` поверне значення,
    # яке було на момент `install()`, тобто True — і воно поїхало б у
    # наступні тести. Рівно та пляма, яку цей тест і стереже.
    monkeypatch.setattr(settings, "llm_enabled", True)

    guard.install()
    import anthropic as blocked

    assert blocked.AsyncAnthropic is not real
    assert settings.llm_enabled is False

    guard.restore()
    import anthropic as back

    assert back.AsyncAnthropic is real, "справжній SDK має повернутись на місце"
    assert settings.llm_enabled is True, "налаштування теж стан, і теж вертається"
    assert not guard.is_installed()


def test_installing_the_guard_twice_does_not_lose_the_real_modules():
    """40. Повторний `install()` не має записати заглушку як «оригінал»."""
    import anthropic

    real = anthropic.AsyncAnthropic
    guard.install()
    guard.install()
    guard.restore()
    import anthropic as back

    assert back.AsyncAnthropic is real


# ── 41. Конфігурація прогону проти конфігурації продукту ──────────────────


def test_the_run_config_matches_the_product_it_measures():
    """41. Бенчмарк міряє продукт лише тоді, коли налаштований як продукт.

    Літерали в `RunConfig` навмисні: `run_id` не має залежати від
    оточення, інакше два прогони на різних машинах не звести. Ціна
    літерала — тихе розходження, і сторожем тут може бути лише тест.

    `site_timeout_s` спершу стояв 300 при продуктових 600
    (`app/worker/tasks.py` обгортає кожен аудит у `audit_timeout_s`):
    бенчмарк обривав би сайти, які продукт дочитує, і записував це
    збоєм сайту.
    """
    from app.core.config import settings

    product = RunConfig()
    assert product.max_pages == settings.crawl_max_pages
    assert product.max_depth == settings.crawl_max_depth
    assert product.render is settings.render_enabled
    assert product.render_max_pages == settings.render_max_pages
    assert product.site_timeout_s == settings.audit_timeout_s


def test_a_shortened_site_timeout_counts_as_a_deviation():
    """41b. Обрізаний час перетворює прочитаний сайт на збій.

    Це зміна даних, а не швидкості, — тож мовчати про неї не можна.
    """
    assert any("site_timeout_s" in d for d in RunConfig(site_timeout_s=120).deviations())
    assert RunConfig(concurrency=1).deviations() == []


# ── 42. Запас місця на томі ───────────────────────────────────────────────


def test_the_run_refuses_to_start_without_room_on_the_volume(corpus, tmp_path):
    """42. Бюджет прогону не захищає диск — захищає запас вільного місця.

    `disk_budget` міряє, скільки зайняв прогін. На томі з 13 ГБ вільного
    бюджет у 20 ГБ не спрацював би ніколи: місце скінчилося б першим, і
    нічний прогін помер би посеред ночі. Поруч із прогоном пише ще й
    браузер — профілі та дампи Playwright, — тож рахувати треба том, а не
    свою теку.
    """
    huge = 1024**6  # свідомо більше за будь-який реальний том
    runner = Runner(corpus, RunConfig(), tmp_path, min_free=huge)
    with pytest.raises(RuntimeError, match="вільно"):
        asyncio.run(runner.run())

    # Повідомлення має вести до розвʼязку, а не лише називати біду.
    try:
        asyncio.run(Runner(corpus, RunConfig(), tmp_path, min_free=huge).run())
    except RuntimeError as exc:
        assert "--root" in str(exc)


def test_performance_off_actually_skips_the_external_provider():
    """42b. Прапорець мусить робити те, що написано на ньому.

    `perf_provider="none"` не збігається з жодним `case` у фабриці
    провайдерів, тож `performance=False` мовчки давав `AutoProvider`:
    конфігурація казала «вимкнено», а PSI викликався на кожен сайт.
    Вимикання робиться фільтром модулів — `_measure_performance` виходить
    одразу, коли модуля немає в наборі.
    """
    from app.audit.enums import Module

    assert RunConfig().audit_options().modules is None, "увімкнено — без фільтра"

    modules = RunConfig(performance=False).audit_options().modules
    assert modules is not None
    assert Module.PERFORMANCE not in modules
    assert len(modules) == len(Module) - 1, "решта модулів лишається на місці"


# ── 43. Канонізація корпусу й дублікати ───────────────────────────────────


def test_corpus_normalization_collapses_the_same_site():
    """43. Одиниця корпусу — сайт, а не адреса.

    `example.com`, `www.example.com`, `http://…`, `…/about` і хвостова
    крапка в імені — це один сайт. Якби вони лишились різними записами,
    частота спрацювання чеків рахувалась би по адресах і мовчки завищила
    б усе, що виміряно «по сайтах».
    """
    from scripts.benchmark.corpus_check import normalize

    same = {
        normalize("https://example.com"),
        normalize("https://www.example.com"),
        normalize("http://example.com/"),
        normalize("https://EXAMPLE.com/about?x=1"),
        normalize("https://example.com."),
        normalize("example.com"),
    }
    assert same == {"example.com"}

    # Різні сайти не мають злипатися.
    assert normalize("https://sub.example.com") == "sub.example.com"
    assert normalize("https://example.org") == "example.org"


def test_corpus_normalization_rejects_what_is_not_a_site():
    """43b. Зламане має бути видно як зламане, а не тихо зникати."""
    from scripts.benchmark.corpus_check import is_malformed, normalize

    for bad in ("", "   ", "ftp://example.com", "javascript:alert(1)",
                "https://", "not a url", "https://localhost", "https://host"):
        assert is_malformed(bad), bad
    assert normalize("ftp://example.com") == ""
    assert not is_malformed("https://example.com")


def test_corpus_check_fails_on_structure_but_not_on_unknown_labels():
    """43c. Структура — помилка, неповнота міток — ні.

    Валити перевірку через невідому країну означало б заохочувати
    вигадати країну, аби вона позеленіла. Це найдорожча з можливих
    поразок: після неї жоден зріз за міткою нічого не означає.
    """
    from scripts.benchmark.corpus_check import check
    from scripts.benchmark.manifest import Site

    def site(url, segment="other", tags=()):
        # `site_id` обовʼязковий і має бути сталим — його ж перевіряє
        # дублікатний контроль.
        return Site(url=url, site_id=url.split("//")[-1], segment=segment, tags=tuple(tags))

    clean = [site("https://a.test-corpus.example"), site("https://b.example")]
    # Без міток узагалі — перевірка має пройти.
    assert check([site("https://a.example"), site("https://b.example")]).ok

    duped = [site("https://example.com"), site("https://www.example.com")]
    report = check(duped)
    assert not report.ok
    assert report.duplicate_urls == ["example.com"]

    assert not check(clean, expected=5).ok, "не та кількість — структурна помилка"
    assert check(clean, expected=2).ok


def test_corpus_hash_depends_on_membership_only():
    """43d. Відбиток описує склад, а не порядок і не оформлення."""
    from scripts.samples.build_corpus1000 import Entry, corpus_hash

    a = [Entry(url="https://one.example", segment="other"),
         Entry(url="https://two.example", segment="other")]
    b = list(reversed(a))
    assert corpus_hash(a) == corpus_hash(b), "порядок не має міняти відбиток"

    c = [*a, Entry(url="https://three.example", segment="other")]
    assert corpus_hash(c) != corpus_hash(a), "інший склад — інший відбиток"


# ── 44. Один словник сегментів, а не два ──────────────────────────────────


def test_the_taxonomy_and_the_loader_share_one_vocabulary():
    """44. Два переліки на одне поняття розходяться тихо.

    `manifest.KNOWN_SEGMENTS` довго казав `publisher` і `enterprise`, а
    таксономія корпусу — `publishing` і `corporate`. Завантажувач лаявся
    на кожен запис, і ця лайка була правдою: словники описували різні
    множини. Той самий клас, що й два ідентифікатори на одну знахідку.
    """
    from scripts.benchmark.manifest import KNOWN_SEGMENTS
    from scripts.samples.segments import CLASS_TO_SEGMENT, QUOTAS

    assert set(QUOTAS) <= set(KNOWN_SEGMENTS), (
        f"квоти згадують сегменти, яких не знає завантажувач: "
        f"{set(QUOTAS) - set(KNOWN_SEGMENTS)}"
    )
    mapped = {s for s in CLASS_TO_SEGMENT.values() if s}
    assert mapped <= set(KNOWN_SEGMENTS), (
        f"таблиця класів веде в невідомі сегменти: {mapped - set(KNOWN_SEGMENTS)}"
    )
    assert sum(QUOTAS.values()) == 1000


def test_observed_platform_markers_are_all_accepted_tags():
    """44b. Закритий список для СПОСТЕРЕЖЕНЬ викидав би доказ.

    Теґи бувають двох родів: гіпотеза людини («схоже на SPA») і те, що
    probe справді побачив у відповіді. Другі не можна відкидати через те,
    що їх не передбачили в переліку заздалегідь.
    """
    from scripts.benchmark.manifest import KNOWN_TAGS
    from scripts.samples.probe_corpus import _MARKERS

    observed = {name for name, _ in _MARKERS}
    assert observed <= set(KNOWN_TAGS), (
        f"probe вміє побачити теґи, яких завантажувач не приймає: "
        f"{observed - set(KNOWN_TAGS)}"
    )
