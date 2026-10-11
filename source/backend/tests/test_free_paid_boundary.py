"""Межа безкоштовного й платного вигляду — на справжніх даних.

Документ будується продуктовим шляхом: знімок → перерахунок →
build_report → безкоштовна проєкція. Вигаданий макет за побудовою не
має ані доказів на вісім полів, ані технічних значень у текстах — і
саме тому нічого не перевіряє.

Головна властивість: у безкоштовному JSON діагностики немає
**структурно**. Не «поле порожнє», а «поля не існує».
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from app.audit.i18n import Locale
from app.audit.orchestrator import rescore
from app.audit.snapshot import load as load_snapshot
from app.report import build_report, source_from_outcome
from app.report.short import (
    _SENTENCE_END,
    TOP_PROBLEMS,
    _stable_order,
    to_short,
    top_recommendations,
)

FIXTURES = Path(__file__).parent / "fixtures" / "snapshots"

#: Ключі, яких у безкоштовній відповіді не може бути на жодному рівні.
#: Це і є межа: шість вимірів, знахідки, докази, адреси, поради.
FORBIDDEN_KEYS = {
    "modules",
    "module",
    "scores",
    "speed_score",
    "seo_score",
    "ai_ready_score",
    "llm_visibility_score",
    "tech_score",
    "accessibility_score",
    "issues",
    "findings",
    "recommendations",
    "next_actions",
    "actions",
    "evidence",
    "issue_key",
    "code",
    "msg",
    "pages",
    "affected_examples",
    "page_url",
    "action",
    "recommendation",
    "missing_data",
}

#: Сліди детекторної точкової нотації в текстах: `seo.title`,
#: `perf.core_web_vitals` тощо.
DETECTOR_ID = re.compile(r"\b(?:seo|perf|ai|llm|tech|cro|a11y)\.[a-z_.]+")


def _document(name: str):
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    ctx = load_snapshot(data)
    outcome = rescore(ctx)
    return build_report(source_from_outcome(outcome, url=ctx.entry_url))


@pytest.fixture(scope="module")
def small_site():
    """Живий сайт зі знахідками — головний випадок."""
    return _document("schema1_small_site")


@pytest.fixture(scope="module")
def blocked_crawl():
    """Сайт, що не пустив краулер: бала немає, і це має бути видно чесно."""
    return _document("schema1_blocked_crawl")


def _all_keys(payload) -> set[str]:
    keys: set[str] = set()
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(key)
            keys |= _all_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            keys |= _all_keys(item)
    return keys


def _all_strings(payload) -> list[str]:
    out: list[str] = []
    if isinstance(payload, dict):
        for value in payload.values():
            out.extend(_all_strings(value))
    elif isinstance(payload, list):
        for item in payload:
            out.extend(_all_strings(item))
    elif isinstance(payload, str):
        out.append(payload)
    return out


# ── структура: діагностики не існує ────────────────────────────────────────


def test_free_json_has_no_diagnostic_keys_at_any_depth(small_site):
    free = to_short(small_site, audit_id="a").to_json()
    leaked = _all_keys(free) & FORBIDDEN_KEYS
    assert not leaked, f"безкоштовна відповідь несе діагностичні поля: {leaked}"


def test_free_texts_carry_no_detector_ids_or_urls(small_site):
    free = to_short(small_site, audit_id="a").to_json()
    for text in _all_strings(free):
        assert not DETECTOR_ID.search(text), text
    # Адреси сторінок сайту не зʼявляються в текстах проблем: сам сайт
    # (url/origin) — єдині http-рядки відповіді.
    site = str(free["origin"])
    for problem in free["problems"]:
        # Картка несе й числа (вплив на бал), тож перевіряємо саме текст.
        for value in problem.values():
            if not isinstance(value, str):
                continue
            assert "http" not in value or site in value, value


def test_free_problems_expose_only_the_consequence_and_its_price(small_site):
    """Картка — наслідок і його ціна в балах. Більше нічого.

    Мітки терміновості тут більше немає: вона стояла бейджем поруч із
    лічильниками серйозності — два словники про одне й те саме, — і
    «Терміново» опинялося нижче за два «Важливо». Число, яке видно,
    пояснює порядок само.
    """
    free = to_short(small_site, audit_id="a").to_json()
    assert free["problems"], "на живому знімку мусять бути проблеми"
    for problem in free["problems"]:
        assert set(problem) == {"problem", "why", "impact_points", "floored"}
        assert problem["problem"]
        assert isinstance(problem["impact_points"], int)
        assert isinstance(problem["floored"], bool)
        assert "urgency" not in problem


def test_free_shows_at_most_three_problems(small_site):
    free = to_short(small_site, audit_id="a")
    assert 0 < len(free.problems) <= TOP_PROBLEMS


def test_top_problems_are_selected_by_ranking_and_ordered_by_impact(small_site):
    """Два різні питання, і відповіді на них різні.

    ВИБІР лишається за рекомендаціями продукту: смуга серйозності,
    потім вигода на вартість, потім різні модулі. Замінити його чистим
    впливом не можна — той структурно виносить дешеву косметику над
    критичним, і ми це вже проходили з Twitter-карткою при Lighthouse 25.

    ПОРЯДОК трьох уже вибраних іде за числом, яке на них написано.
    Інакше картка з більшим впливом стоїть під карткою з меншим, і
    читач бачить суперечність там, де її немає.
    """
    ranked = [r for r in small_site.recommendations if r.consequence]
    free = to_short(small_site, audit_id="a")

    # Вибір: та сама трійка, що дає наявне ранжування з розведенням модулів.
    sources = []
    for problem in free.problems:
        source = next(r for r in ranked if r.consequence.startswith(problem.problem))
        sources.append(source)
    assert sources[0] in ranked[: len(free.problems)], "вибір відірвався від ранжування"
    modules = [s.module for s in sources]
    assert len(set(modules)) == len(modules), "модулі мають різнитися"

    # Порядок: спадання впливу, і жодного винятку.
    impacts = [p.impact_points for p in free.problems]
    assert impacts == sorted(impacts, reverse=True), impacts


# ── числа: правильні й чесні ───────────────────────────────────────────────


def test_totals_and_severity_fold_match_the_document(small_site):
    free = to_short(small_site, audit_id="a")
    by_severity = small_site.summary["by_severity"]
    assert free.issues_total == small_site.summary["issues_total"]
    assert free.severity["high"] == by_severity["critical"] + by_severity["high"]
    assert free.severity["medium"] == by_severity["medium"]
    assert free.severity["low"] == by_severity["low"] + by_severity["info"]
    assert sum(free.severity.values()) == free.issues_total


def test_valid_score_appears(small_site):
    free = to_short(small_site, audit_id="a")
    assert free.overall_score == small_site.overall_score
    assert free.overall_score is not None


def test_null_score_stays_null_and_coverage_says_insufficient(blocked_crawl):
    """Заблокований краул: жодного вигаданого числа, рівень чесний."""
    assert blocked_crawl.overall_score is None, "фікстура мусить бути без бала"
    free = to_short(blocked_crawl, audit_id="a")
    assert free.overall_score is None
    assert free.coverage.level == "insufficient"


def test_coverage_is_high_level_only(small_site, blocked_crawl):
    """Покриття — числа й рівень. Без причин, кодів і адрес відмов."""
    for document in (small_site, blocked_crawl):
        coverage = to_short(document, audit_id="a").to_json()["coverage"]
        assert set(coverage) == {
            "pages_read",
            "pages_known",
            "level",
            "pages_failed",
        }
        # Невдачі — окреме число, а не різниця: у знаменнику є й адреси,
        # до яких краул не дійшов за бюджетом, і назвати їх невдачами
        # означало б звинуватити сайт у нашій межі.
        assert isinstance(coverage["pages_failed"], int)
        assert coverage["level"] in {"full", "partial", "insufficient"}


def test_free_problem_texts_contain_no_observed_values(small_site):
    """Тексти проблем — наслідок, не вимірювання: без чисел-доказів.

    `consequence` за побудовою без жаргону (є окремий тест каталогу),
    але тут страхуємось від майбутніх записів: мілісекунди, байти й
    відсотки — мова діагностики.
    """
    units = re.compile(r"\d+\s*(?:ms|мс|kb|мб|mb|%)", re.I)
    for problem in to_short(small_site, audit_id="a").problems:
        assert not units.search(problem.problem + " " + problem.why)


# ── платний вигляд лишається повним ────────────────────────────────────────


def test_paid_document_still_carries_full_diagnostics(small_site):
    """Повний JSON — увесь діагноз: виміри, знахідки, докази, поради."""
    paid = small_site.to_json()
    assert paid["scores"], "платний вигляд без вимірів — не платний вигляд"
    assert paid["issues"]
    first = paid["issues"][0]
    assert "evidence" in first
    assert paid["recommendations"]
    assert any(r.get("action") for r in paid["recommendations"])


# ── порядок трійки: одні дані — одна відповідь усіма мовами ────────────────


def _ordered_keys(name: str, locale: Locale) -> list[str]:
    """Ідентифікатори трьох головних проблем цією мовою."""
    data = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    outcome = rescore(load_snapshot(data))
    document = build_report(
        source_from_outcome(outcome, url=outcome.context.entry_url), locale
    )
    return [rec.issue_key for rec in top_recommendations(document)]


def test_top_three_order_is_identical_in_all_six_locales():
    """Той самий аудит — та сама послідовність, якою б мовою його не читали.

    Спіймано власником на живому екрані: ka-dent.com.ua з двома
    знахідками по −3 показував їх у різному порядку. Англійська й
    російська починали з телефонів, німецька, іспанська, французька й
    українська — з опису сторінки. Одні дані, шість відповідей.

    Причина була в останньому кроці сортування: ним стояло перше речення
    `consequence`, тобто текст МОВОЮ СТОРІНКИ. Порівняння рядків різними
    мовами дає різний порядок, і це не випадковість, а неминучість.
    """
    reference = _ordered_keys("schema1_small_site", Locale.EN)
    assert reference, "на живому знімку мусять бути проблеми"

    for locale in (Locale.UK, Locale.DE, Locale.ES, Locale.FR, Locale.RU):
        assert _ordered_keys("schema1_small_site", locale) == reference, locale.value


def test_the_order_key_contains_no_localised_text():
    """Правило, а не наслідок: локалізований рядок у ключ не входить.

    Однакового порядку на одному знімку замало — він міг збігтися. Тут
    перевіряється сам ключ: усі його складові або числа, або стабільні
    ідентифікатори.
    """
    document = _document("schema1_small_site")
    for rec in top_recommendations(document):
        key = _stable_order(rec)
        assert key[0] == -rec.impact_points
        assert key[3] == rec.issue_key
        # Жодна складова не дорівнює тексту, який читає клієнт.
        for part in key:
            assert part != rec.consequence
            assert part != rec.title
            assert part != rec.problem


def test_two_findings_with_equal_impact_are_separated_deterministically():
    """Рівний вплив розводиться серйозністю, пріоритетом і ключем.

    Саме цей випадок і ламався: −3 проти −3. Четвертий крок гарантує, що
    рівності не лишається взагалі — два різні `issue_key` завжди різні.
    """
    document = _document("schema1_small_site")
    picked = top_recommendations(document)
    keys = [_stable_order(rec) for rec in picked]
    assert len(set(keys)) == len(keys), "ключ порядку не розводить кандидатів"
    assert keys == sorted(keys), "порядок не відповідає власному ключу"


def test_the_free_view_preserves_the_backend_order():
    """Фронт нічого не пересортовує — подання йде тим самим порядком."""
    document = _document("schema1_small_site")
    expected = [
        _SENTENCE_END.split(rec.consequence.strip(), maxsplit=1)[0]
        for rec in top_recommendations(document)
    ]
    shown = [p.problem for p in to_short(document, audit_id="a").problems]
    assert shown == expected


# ── E-05: застосовність не перетинає межу безкоштовного вигляду ────────


def test_applicability_evidence_never_reaches_the_free_view(small_site):
    """Застосовність — діагностика, і в безкоштовному вигляді її немає.

    Блок додано в доказ, а доказу в безкоштовній відповіді немає
    структурно. Перевіряється саме це: не «поле порожнє», а поля не
    існує — ані самого блока, ані слів, якими він говорить.
    """
    payload = json.loads(json.dumps(to_short(small_site, audit_id="a").to_json()))
    keys = _all_keys(payload)
    assert "applicability" not in keys
    # `coverage` у цьому переліку немає навмисно: у безкоштовному вигляді
    # так зветься покриття краулу, і воно там доречне. Заборонені саме
    # слова застосовності.
    assert not keys & {"claim_class", "route_class", "reason_code", "verdict",
                       "aggregation_strategy", "not_applicable", "no_verdict"}
    blob = " ".join(_all_strings(payload))
    for word in ("NOT_APPLICABLE", "NO_VERDICT", "public_indexable_content", "A-02"):
        assert word not in blob, word


def test_the_paid_document_carries_the_applicability_block(small_site):
    """Платний документ несе стан кожної претензії — там він і потрібен."""
    block = small_site.evidence.get("applicability")
    assert isinstance(block, dict) and block
    row = next(iter(block.values()))
    assert {"verdict", "coverage", "rules", "examples"} <= set(row)


def test_the_free_score_is_the_paid_score_on_the_same_snapshot(small_site):
    """Одні дані — один бал. Застосовність не створює другої правди.

    Межа ділить те, що ПОКАЗУЮТЬ, а не те, що рахують: якби фільтр
    застосовності діяв лише в одному з двох шляхів, безкоштовне число
    розійшлося б із платним на тому самому знімку.
    """
    short = to_short(small_site, audit_id="a")
    assert short.overall_score == small_site.overall_score
    assert short.overall_band == small_site.overall_band


def test_a_blocked_crawl_still_has_no_applicable_page_to_praise(blocked_crawl):
    """Сайт, який нас не пустив: ані знахідок про вміст, ані пройдених.

    Тут сходяться дві межі — покриття й застосовність, — і обидві мусять
    давати ту саму відповідь: судити не було чого.
    """
    assert blocked_crawl.passed_checks == [] or all(
        check.scope in ("origin", "site") for check in blocked_crawl.passed_checks)
    block = blocked_crawl.evidence.get("applicability") or {}
    for key in ("seo.canonical:missing", "seo.title:missing"):
        row = block.get(key)
        if row is not None:
            assert row["evaluated"] == 0, key


# ══ E-14: перелік відкритих сторінок ══════════════════════════════════════
#
# Політика цілком належить застосунковому шару, тому й перевіряється тут
# через нього. Розподіл праці між цим файлом і
# `tests/integration/test_guest_inspected_pages.py` свідомий:
#
#   тут          те, що можна довести без бази — правило «прочитано»,
#                форма DTO, склад запиту, і межа безкоштовної проєкції;
#   в інтеграції те, що робить САМА база — порядок, collation, межа,
#                віконний рахунок, розвʼязання нічиїх, ізоляція.
#
# Порядок і обрізання тут не перевіряються навмисно: у SQL їх виконує
# сервер, і «перевірка» на фейкових рядках доводила б лише те, що Python
# уміє сортувати список.

import uuid as _uuid  # noqa: E402

from sqlalchemy.dialects import postgresql  # noqa: E402

from app.application import guest as _guest  # noqa: E402
from app.schemas.result import InspectedPageOut  # noqa: E402


class _CapturedResult:
    def __init__(self, rows):
        self._rows = list(rows)

    def all(self):
        return list(self._rows)


class _CapturingSession:
    """Сесія, яка нічого не виконує, але памʼятає КОЖЕН поданий запит."""

    def __init__(self, rows=()):
        self.statements = []
        self._rows = list(rows)

    async def execute(self, statement, *args, **kwargs):
        self.statements.append(statement)
        return _CapturedResult(self._rows)


class _SqlRow:
    """Рядок результату `pages_for`: три колонки плюс віконний рахунок."""

    def __init__(self, url, status_code, depth, total):
        self.url = url
        self.status_code = status_code
        self.depth = depth
        self.total = total


def _run(coro):
    import asyncio

    return asyncio.run(coro)


# ── правило «прочитано» ───────────────────────────────────────────────────


def test_read_is_derived_from_the_persisted_status_alone():
    """Двохсотий діапазон — прочитано. Усе інше, включно з null, — ні.

    Те саме правило, що в `SiteContext.ok_pages`. Розмір тіла, тип вмісту
    й `raw` тут не беруть участі: друга відповідь на те саме питання рано
    чи пізно розійшлася б із першою.
    """
    assert _guest.page_was_read(199) is False
    assert _guest.page_was_read(200) is True
    assert _guest.page_was_read(204) is True
    assert _guest.page_was_read(299) is True
    assert _guest.page_was_read(300) is False
    assert _guest.page_was_read(404) is False
    assert _guest.page_was_read(None) is False


def test_the_cap_is_exactly_one_hundred():
    """Сто — це число з рішення власника, а не налаштування.

    Пін стоїть на літералі навмисно. Кожне інше твердження про межу
    посилається на саму константу, тож зсув межі поїхав би разом із ними
    й лишився б непоміченим.
    """
    assert _guest.INSPECTED_PAGE_LIMIT == 100


def test_the_url_collation_is_pinned_and_explicit():
    """Правило сортування адрес назване, а не успадковане від сервера."""
    assert _guest.URL_COLLATION == "C"


# ── форма того, що перетинає межу шару ────────────────────────────────────


def test_the_application_layer_hands_out_a_dto_and_not_orm_rows():
    """Назовні йде маленький DTO з чотирма полями, а не рядок моделі."""
    from app.models.audit import AuditPage

    session = _CapturingSession([_SqlRow("https://example.com/a", 200, 0, 1)])
    result = _run(_guest.pages_for(session, _uuid.uuid4()))

    page = result.pages[0]
    assert isinstance(page, _guest.InspectedPageRow)
    assert not isinstance(page, AuditPage)
    assert set(_guest.InspectedPageRow.__dataclass_fields__) == {
        "url", "status", "depth", "read"}
    assert set(_guest.InspectedPages.__dataclass_fields__) == {"pages", "total", "truncated"}
    assert isinstance(result.pages, tuple), "зріз незмінний: викликач його не дописує"


def test_the_entry_has_exactly_the_four_approved_keys():
    """Чотири поля, не більше й не менше. Шостипольова пропозиція скасована."""
    assert set(InspectedPageOut.model_fields) == {"url", "status", "depth", "read"}
    assert "rendered" not in InspectedPageOut.model_fields
    assert "discovered_via" not in InspectedPageOut.model_fields


def test_a_missing_status_is_null_and_not_read():
    """Рядок є, відповіді не було. Статус не вигадується."""
    session = _CapturingSession([_SqlRow("https://x/a", None, 0, 1)])
    page = _run(_guest.pages_for(session, _uuid.uuid4())).pages[0]
    assert (page.url, page.status, page.depth, page.read) == ("https://x/a", None, 0, False)


def test_the_total_comes_from_the_window_count_not_from_the_returned_rows():
    """Три рядки на руках і 4096 у базі — саме цю пару й треба розрізняти."""
    session = _CapturingSession([
        _SqlRow("https://example.com/a", 200, 0, 4096),
        _SqlRow("https://example.com/b", 404, 1, 4096),
        _SqlRow("https://example.com/c", None, 2, 4096),
    ])
    result = _run(_guest.pages_for(session, _uuid.uuid4()))
    assert result.total == 4096
    assert len(result.pages) == 3
    assert result.truncated is True


def test_no_rows_means_a_total_of_zero_and_no_second_query():
    """Порожній аудит: рахувати нема чого, і питати вдруге теж."""
    session = _CapturingSession()
    result = _run(_guest.pages_for(session, _uuid.uuid4()))
    assert result.pages == ()
    assert result.total == 0
    assert result.truncated is False
    assert len(session.statements) == 1


# ── склад запиту ──────────────────────────────────────────────────────────


def test_the_order_the_collation_the_cap_and_the_total_are_in_the_query_itself():
    """Один запит, і в ньому порядок, collation, розвʼязання нічиїх, межа й рахунок.

    Читається скомпільований SQL, а не наміри виклику. Що ці частини
    РОБЛЯТЬ — властивість бази, і вона доводиться в
    `tests/integration/test_guest_inspected_pages.py`; тут доводиться, що
    вони взагалі поїхали в базу.
    """
    session = _CapturingSession()
    _run(_guest.pages_for(session, _uuid.uuid4()))

    assert len(session.statements) == 1, "повний звіт робить рівно один запит сторінок"
    sql = str(session.statements[0].compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "ORDER BY audit_pages.depth ASC" in sql
    assert 'audit_pages.url COLLATE "C" ASC' in sql
    assert "audit_pages.id ASC" in sql, "нічия між рівними рядками не розвʼязана"
    assert f"LIMIT {_guest.INSPECTED_PAGE_LIMIT}" in sql
    assert "count(*) OVER ()" in sql
    assert sql.count("FROM audit_pages") == 1, "другого проходу таблицею немає"
    assert sql.index("ORDER BY") < sql.index("LIMIT")


def test_the_policy_does_not_live_in_the_report_layer():
    """Межа, правило й порядок належать застосунковому шару, і лише йому.

    Роздвоєна політика — це два джерела істини про одне число. Тест меж
    імпортів ловить сам імпорт; цей ловить переїзд.
    """
    import app.report.types as report_types
    import app.report.web as report_web

    for module in (report_types, report_web):
        for name in ("INSPECTED_PAGE_LIMIT", "URL_COLLATION", "page_was_read",
                     "InspectedPageRow", "InspectedPages", "pages_for"):
            assert not hasattr(module, name), f"{module.__name__} знає про {name}"


# ── межа: тільки оплачений повний звіт ────────────────────────────────────


def test_the_free_projection_carries_no_inspected_page_list(small_site, blocked_crawl):
    """Безкоштовна проєкція не знає слова «сторінки»: ні ключа, ні адреси."""
    for document in (small_site, blocked_crawl):
        free = to_short(document, audit_id="a").to_json()
        blob = json.dumps(free, ensure_ascii=False)
        assert "inspected_pages" not in blob
        assert "inspected_pages_total" not in free
        assert "inspected_pages_truncated" not in free


def test_the_free_coverage_key_set_is_unchanged_by_e14(small_site, blocked_crawl):
    """Заморожені чотири ключі лишилися рівно чотирма."""
    for document in (small_site, blocked_crawl):
        coverage = to_short(document, audit_id="a").to_json()["coverage"]
        assert set(coverage) == {"pages_read", "pages_known", "level", "pages_failed"}


def test_an_old_report_without_pages_still_renders(small_site):
    """Збережений звіт без сторінок читається як раніше: поля порожні, не зламані.

    Поля адитивні, і саме тому вони необовʼязкові, а не порожні за
    замовчуванням: `None` означає «цей звіт про сторінки не каже», а `[]`
    означало б «сторінок не було».
    """
    from app.report.web import to_web

    response = to_web(small_site, audit_id=_uuid.uuid4(), site_id=None, status="completed",
                      finished_at=None, fallback_locale="en").model_dump(mode="json")
    assert response["inspected_pages"] is None
    assert response["inspected_pages_total"] is None
    assert response["inspected_pages_truncated"] is None
    assert response["overall_band"]
    assert "summary" in response


def test_e14_needs_no_migration_and_no_new_persistence_field():
    """Перелік читається з тих колонок, які вже є. Нових немає жодної."""
    from app.models.audit import AuditPage

    columns = {c.name for c in AuditPage.__table__.columns}
    assert columns == {"id", "audit_id", "target_id", "url", "status_code", "content_type",
                       "html_bytes", "response_ms", "depth", "raw"}
    assert {"url", "status_code", "depth", "id"} <= columns


def test_page_signals_to_json_was_not_touched():
    """`discovered_via` як не писався в `raw`, так і не пишеться."""
    from app.audit.types import PageSignals

    keys = set(PageSignals(url="https://x/y", status_code=200, depth=1).to_json())
    assert "discovered_via" not in keys
    assert "rendered" not in keys


# ── те, що цей блок зобовʼязався НЕ рухати ────────────────────────────────


def test_no_engine_or_contract_version_is_bumped():
    """Жоден відбиток не зрушив — і це перевіряється за значенням.

    E-13 і E-14 нічого не рахують і нічого не виявляють: вони описують
    уже порахований аудит. Зсув будь-якого з цих чисел означав би, що
    бали по різні боки цієї межі непорівнянні, — а тут порівнювати нічого,
    бо нічого й не змінилось.

    Числа стоять літералами навмисно. Порівняння відбитка з ним самим
    («не змінився відносно поточного») було б тавтологією: воно пройшло б
    і після зміни.
    """
    import hashlib

    from app.audit import versions
    from app.audit.applicability import CHECK_DECLARATIONS
    from app.audit.checks.base import REGISTRY
    from app.schemas.result import RESULT_CONTRACT_VERSION

    rows = sorted(
        f"{c.code}:{c.module.value}:{c.severity.value}:{c.weight}:{c.effort.value}"
        f":{','.join(c.variants)}" for c in REGISTRY)

    assert len(REGISTRY) == 80
    assert len(CHECK_DECLARATIONS) == 80
    assert str(versions.DETECTOR_RULES) == "14"
    assert str(versions.SCORING_RULES) == "5"
    assert str(versions.CRAWLER_VERSION) == "4"
    assert versions.detector_version() == "3b9a556ab798"
    assert versions.scoring_version() == "aa4ecc62a5a3"
    assert hashlib.sha256("\n".join(rows).encode()).hexdigest()[:16] == "fa42a134eb827580"
    assert RESULT_CONTRACT_VERSION == 2


def test_the_postgresql_coverage_is_present_and_not_disabled():
    """Постійне покриття проти справжньої бази не можна тихо вимкнути.

    Найдешевший спосіб «полагодити» червоний інтеграційний тест — не
    полагодити його, а зняти: `skip`, `xfail`, перейменований файл,
    закоментований блок. Жоден із них не робить запит правильним, і
    жоден не помітний у зеленому прогоні без цієї перевірки.

    Тому тут перелічені самі твердження, які мусять існувати. Це не
    дублювання інтеграційного файлу: він доводить поведінку, а цей тест
    доводить, що він узагалі є й не знешкоджений.
    """
    import ast

    path = (Path(__file__).resolve().parent / "integration"
            / "test_guest_inspected_pages.py")
    assert path.exists(), "постійне покриття проти PostgreSQL зникло"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    required = {
        "test_the_cap_and_the_total_hold_at_every_size",
        "test_the_total_is_measured_before_the_cap_not_after_it",
        "test_the_cap_is_applied_after_sorting_not_before",
        "test_depth_comes_first_and_url_second",
        "test_mixed_case_and_unicode_sort_by_bytes_under_the_explicit_collation",
        "test_the_same_rows_inserted_differently_come_back_identically",
        "test_equal_depth_and_url_are_broken_deterministically",
        "test_read_is_false_for_null_and_for_non_success_statuses",
        "test_read_is_true_across_the_whole_success_range",
        "test_a_neighbouring_audit_never_appears",
        "test_exactly_one_bounded_query_reaches_the_database",
    }
    defined = {node.name for node in ast.walk(tree)
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
    missing = sorted(required - defined)
    assert not missing, f"інтеграційні твердження зникли: {missing}"

    for node in ast.walk(tree):
        for decorator in getattr(node, "decorator_list", []):
            text = ast.unparse(decorator)
            assert "skip" not in text and "xfail" not in text, (
                f"{getattr(node, 'name', '?')} знешкоджено: {text}")
    assert "pytestmark = pytest.mark.asyncio" in source, "модуль більше не асинхронний"
    assert "skip" not in source.replace("skipped", ""), "у модулі зʼявився skip"
