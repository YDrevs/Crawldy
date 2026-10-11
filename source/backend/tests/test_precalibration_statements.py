"""Твердження, виправлені після людської валідації.

Кожен тест тут стереже РІЗНИЦЮ між фактом і його тлумаченням. Детектори
в усіх цих випадках виявляли правильно; неправильним було те, що з
виявленого казали клієнтові.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.audit.checks import all_checks
from app.audit.enums import Confidence
from app.audit.types import PageSignals
from tests.factories import context, page_from_html

CHECKS = {c.code: c for c in all_checks()}


def _dated(url: str, when: datetime) -> PageSignals:
    """Дата береться з розмітки JSON-LD — саме її читає чек.

    Видимий `<time>` він навмисно не читає: «з 2019 року на ринку» — це
    не дата оновлення сторінки.
    """
    html = (
        "<html><body>"
        '<script type="application/ld+json">'
        f'{{"@type": "Article", "dateModified": "{when.date().isoformat()}"}}'
        "</script>"
        f'<main>{"слово " * 60}</main></body></html>'
    )
    return page_from_html(html, url=url)


def _plain(url: str) -> PageSignals:
    return page_from_html(f'<html><body><main>{"слово " * 60}</main></body></html>', url=url)


# ── llm.stale_content ─────────────────────────────────────────────────────


def test_sparse_dates_do_not_support_a_claim_about_the_whole_site():
    """1. Три датовані сторінки з двадцяти чотирьох — не привід судити сайт.

    `nomadgames.co.uk`: найновіша дата — червень 2024, але дату несли
    лише 3 сторінки з 24. Відсутність дати на решті не є доказом, що
    вони старі.
    """
    old = datetime.now(UTC) - timedelta(days=365 * 3)
    pages = [_dated(f"https://example.com/a{i}", old) for i in range(3)]
    pages += [_plain(f"https://example.com/b{i}") for i in range(21)]
    found = list(CHECKS["llm.stale_content"].run(context(*pages)))
    assert found, "знахідка лишається: факт про датовані сторінки правдивий"
    issue = found[0]
    assert issue.msg == "llm.stale_content.sparse", "формулювання має бути вузьким"
    assert issue.evidence["claim_scope"] == "dated_pages_only"
    assert issue.confidence is Confidence.LOW
    assert issue.evidence["dated_coverage"] < 0.5


def test_wide_date_coverage_still_supports_the_site_level_claim():
    """2. Коли дати майже скрізь, узагальнення виправдане."""
    old = datetime.now(UTC) - timedelta(days=365 * 3)
    pages = [_dated(f"https://example.com/a{i}", old) for i in range(8)]
    pages += [_plain("https://example.com/b1")]
    issue = next(iter(CHECKS["llm.stale_content"].run(context(*pages))))
    assert issue.msg == "llm.stale_content"
    assert issue.evidence["claim_scope"] == "site"
    assert issue.confidence is Confidence.MEDIUM


def test_recent_dates_produce_no_finding():
    """3. Свіжий сайт лишається без знахідки."""
    now = datetime.now(UTC) - timedelta(days=30)
    pages = [_dated(f"https://example.com/a{i}", now) for i in range(5)]
    assert not list(CHECKS["llm.stale_content"].run(context(*pages)))


# ── perf.page_weight ──────────────────────────────────────────────────────


def test_a_truncated_page_reports_its_size_as_a_lower_bound():
    """4. Уперлись у власну стелю — розмір це «щонайменше», а не вимір.

    `hyundai.com` дав рівно 5 242 880 байтів, бо стільки ми читаємо.
    Подавати межу читання як розмір сторінки означало б вигадати
    точність, якої в нас немає.
    """
    from app.core.config import settings

    page = _plain("https://example.com/heavy")
    page.html_bytes = settings.max_response_bytes
    issue = next(iter(CHECKS["perf.page_weight"].run(context(page))))
    assert issue.msg == "perf.page_weight.truncated"
    assert issue.evidence["size_is_lower_bound"] is True


def test_a_heavy_but_complete_page_reports_a_measured_size():
    """5. Дочитану сторінку міряємо, а не оцінюємо знизу."""
    from app.audit.checks.performance import HEAVY_HTML_BYTES
    from app.core.config import settings

    page = _plain("https://example.com/big")
    page.html_bytes = max(HEAVY_HTML_BYTES + 1, settings.max_response_bytes // 2)
    issue = next(iter(CHECKS["perf.page_weight"].run(context(page))))
    assert issue.msg == "perf.page_weight"
    assert issue.evidence["size_is_lower_bound"] is False


# ── tech.analytics ────────────────────────────────────────────────────────


def test_missing_heatmaps_is_no_longer_a_customer_finding():
    """6. Відсутність теплокарт — не проблема видимості.

    Сайт із first-party аналітикою, GA і GTM отримував зауваження за те,
    що серед них немає Hotjar. INFO рятувало від штрафу, але не від
    зайвого рядка у звіті клієнта.
    """
    page = _plain("https://example.com/")
    page.analytics = ["first_party", "google_analytics", "google_tag_manager"]
    found = list(CHECKS["tech.analytics"].run(context(page)))
    assert not found, "аналітика є — казати більше нема чого"


def test_a_site_with_no_analytics_at_all_still_reports():
    """7. Справжня відсутність вимірювання лишається знахідкою."""
    page = _plain("https://example.com/")
    page.analytics = []
    found = list(CHECKS["tech.analytics"].run(context(page)))
    assert found and found[0].issue_key.endswith("missing")


# ── tech.crawler_blocked ──────────────────────────────────────────────────


@pytest.mark.parametrize("status", [401, 403, 405, 406, 429, 503])
def test_blocking_statuses_are_reported_when_nothing_was_readable(status: int):
    """8. Детектор рідкісного режиму відмови — з детермінованим доказом.

    На корпусі night3 він не спрацював жодного разу, бо всі 958 сайтів
    віддали вміст. Це не привід ані видаляти його, ані послаблювати
    умову: корпус успішних сайтів — неправильна популяція для перевірки
    того, що робиться з заблокованими.
    """
    page = page_from_html("<html><body>відмова</body></html>", url="https://example.com/")
    page.status_code = status
    found = list(CHECKS["tech.crawler_blocked"].run(context(page)))
    assert found, f"HTTP {status} при порожньому вмісті має бути названий"
    assert found[0].evidence["statuses"] == [status]


def test_a_readable_site_never_reports_being_blocked():
    """9. Найважливіше тут — мовчання, коли сайт нас пустив."""
    assert not list(CHECKS["tech.crawler_blocked"].run(context(_plain("https://example.com/"))))


def test_an_ordinary_404_is_not_a_block():
    """10. Не кожна невдача є відмовою в доступі."""
    page = page_from_html("<html><body>не знайдено</body></html>", url="https://example.com/")
    page.status_code = 404
    assert not list(CHECKS["tech.crawler_blocked"].run(context(page)))


# ── ai.llms_txt: можливість, а не вада ────────────────────────────────────


def _no_llms_txt_context():
    from app.audit.types import LlmsTxtInfo

    ctx = context(_plain("https://example.com/"))
    ctx.llms_txt = LlmsTxtInfo(exists=False, status_code=404)
    return ctx


def test_llms_txt_is_marked_experimental_in_evidence():
    """11. Поверхня звіту має відрізняти можливість від вади машинно.

    Заголовок можна перефразувати, і тоді ознака зникне разом із ним.
    Позначка в доказі лишається незалежно від формулювання.
    """
    issue = next(iter(CHECKS["ai.llms_txt"].run(_no_llms_txt_context())))
    assert issue.evidence["status"] == "experimental"


@pytest.mark.parametrize("locale", ["uk", "en", "de", "es", "fr", "ru"])
def test_llms_txt_wording_does_not_claim_a_ranking_problem(locale: str):
    """12. Жодною з шести мов не обіцяємо впливу на ранжування.

    Людська валідація: відсутність llms.txt не є ані відомою проблемою
    ранжування, ані загальною вимогою видимості в мовних моделях. Текст
    мусить це казати, а не мовчати про це.
    """
    module = __import__(f"app.audit.i18n.{locale}", fromlist=["MESSAGES"])
    entry = module.MESSAGES["ai.llms_txt.missing"]
    blob = " ".join(entry.values()).lower()

    # Статус названо явно — інакше читач бере знахідку за звичайний дефект.
    assert any(
        mark in blob
        for mark in ("експеримент", "experimental", "experimentell",
                     "expérimental", "experimental", "эксперимент")
    ), f"{locale}: статус не названо"

    # І сказано, що це не проблема ранжування.
    assert any(
        mark in blob
        for mark in ("ранжув", "ranking", "ranking-problem", "posicionamiento",
                     "classement", "ранжиров")
    ), f"{locale}: не сказано, що це не проблема ранжування"


def test_llms_txt_never_reaches_the_first_things_to_do():
    """13. Можливість не стоїть у переліку, за яким витрачають гроші.

    Перевірено на 55 сайтах night3 зі знахідкою: жодного разу. Тримається
    це на низькій серйозності й вазі 1, а не на окремому правилі, тож
    тест стереже саме результат.
    """
    from app.audit.orchestrator import rescore
    from app.report.builder import build_report
    from app.report.source import source_from_outcome

    outcome = rescore(_no_llms_txt_context())
    report = build_report(source_from_outcome(outcome))
    assert not any("llms_txt" in a.msg for a in report.next_actions)
