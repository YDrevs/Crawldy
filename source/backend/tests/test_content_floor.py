"""Поріг вмісту міряє те представлення, яке читає модуль.

## Дефект, через який ці тести існують

Поріг був спільний і рахував слова у **відповіді сервера**. Але чеки
різних модулів читають різне, і це задокументований намір, а не випадок:

- SEO дивиться на сторінку ПІСЛЯ виконання скриптів (`ctx.as_seen`), бо
  Google її так і бачить;
- AI_READY і LLM_VISIBILITY навмисно лишаються на СТАТИЧНІЙ відповіді:
  асистенти JS здебільшого не виконують.

Через спільний статичний поріг SEO вимикався там, де його чеки мали
повні дані. На night2 це 36 сайтів: `zenit.win` віддав 0 слів у
відповіді й 22 129 після рендеру, `dagrasso.pl` — 0 і 9 161. Клієнтові
при цьому писали «на всьому сайті 0 слів», що для відрендереного сайту
просто неправда.

## Що ці тести стережуть

Головне тут — не «36 сайтів отримали бал», а **інваріант**: рішення про
придатність модуля спирається на те саме представлення, що й його чеки.
Тому перевіряється кожен модуль окремо, а не лише загальний бал: якщо
завтра SEO повернеться на статику, тест має впасти.

Окремо стережеться протилежна помилка: відрендерений текст НЕ має
робити сайт «доступним» для модулів, які судять статичну відповідь.
Видимість для пошуку ≠ доступність для асистента.
"""

from __future__ import annotations

import pytest

from app.audit.enums import Module
from app.audit.orchestrator import AuditOptions, _module_coverage
from app.audit.types import (
    CRAWL_EMPTY,
    CRAWL_EMPTY_STATIC,
    RenderResult,
)
from tests.factories import context, page_from_html

WORDS = " ".join(f"слово{i}" for i in range(200))  # понад поріг у 100


def _outcome(ctx):
    """Прогнати покриття так само, як це робить оркестратор."""
    degraded: list = []
    skipped, _partial = _module_coverage(AuditOptions(), ctx, [], degraded)
    return skipped, degraded


def _ctx(static_html: str, rendered_html: str | None, url="https://example.com/"):
    """Контекст із заданим статичним і (необовʼязково) відрендереним виглядом."""
    page = page_from_html(static_html, url=url)
    ctx = context(page)
    if rendered_html is not None:
        ctx.renders = {
            url: RenderResult(
                url=url, rendered=True,
                signals=page_from_html(rendered_html, url=url),
            )
        }
    return ctx


@pytest.fixture
def spa_context():
    """Оболонка SPA: у відповіді порожньо, після рендеру — текст."""
    return _ctx("<html><body><div id='root'></div></body></html>",
                f"<html><body><main>{WORDS}</main></body></html>")


@pytest.fixture
def empty_context():
    """Порожньо і у відповіді, і після рендеру."""
    return _ctx("<html><body><div id='root'></div></body></html>",
                "<html><body><div id='root'></div></body></html>")


@pytest.fixture
def ssr_context():
    """Звичайний сайт: текст є одразу у відповіді."""
    return _ctx(f"<html><body><main>{WORDS}</main></body></html>",
                f"<html><body><main>{WORDS}</main></body></html>")


@pytest.fixture
def no_render_context():
    """У відповіді порожньо, рендеру не було взагалі."""
    return _ctx("<html><body><div id='root'></div></body></html>", None)


def test_rendered_content_keeps_seo_and_still_hides_the_site_from_assistants(
    spa_context,
):
    """1. Порожня оболонка SPA з текстом після рендеру.

    Для пошуку сайт читається — SEO лишається. Для асистентів він
    порожній, і це властивість сайту, а не наша сліпота.
    """
    skipped, degraded = _outcome(spa_context)
    assert Module.SEO not in skipped, "SEO мав лишитись: Google цю сторінку бачить"
    assert Module.AI_READY in skipped
    assert Module.LLM_VISIBILITY in skipped

    scopes = {d.scope for d in degraded}
    assert CRAWL_EMPTY_STATIC in scopes
    assert CRAWL_EMPTY not in scopes, "сайт не порожній — порожня лише відповідь"


def test_the_reason_does_not_claim_the_site_is_empty(spa_context):
    """2. Доказ мусить назвати представлення, а не брехати про сайт.

    «на всьому сайті 0 слів» для сайту, який ми відрендерили й прочитали,
    — неправда в тексті, що йде клієнтові.
    """
    _, degraded = _outcome(spa_context)
    notice = next(d for d in degraded if d.scope == CRAWL_EMPTY_STATIC)
    assert notice.reason_params["rendered"] >= 100
    assert notice.reason_params["words"] < 100
    assert "0 слів" not in notice.reason or "відповіді сервера" in notice.reason


def test_a_site_empty_even_after_rendering_stays_fully_excluded(empty_context):
    """3. Протилежний випадок лишається як був: не бачить ніхто."""
    skipped, degraded = _outcome(empty_context)
    assert {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY} <= skipped
    assert CRAWL_EMPTY in {d.scope for d in degraded}


def test_static_content_site_is_untouched(ssr_context):
    """4. Звичайний SSR-сайт поводиться точно як раніше."""
    skipped, degraded = _outcome(ssr_context)
    assert not ({Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY} & skipped)
    assert CRAWL_EMPTY not in {d.scope for d in degraded}
    assert CRAWL_EMPTY_STATIC not in {d.scope for d in degraded}


def test_static_empty_and_render_failed_is_honestly_unavailable(no_render_context):
    """5. Рендеру не було — судити нема чим, і мовчати треба про все.

    `as_seen` повертає статичну сторінку, коли рендеру немає, тож поріг
    бачить ті самі нуль слів і виключає всі три модулі. Це правильно:
    вигадувати, що «мабуть, після рендеру текст був би», не можна.
    """
    skipped, degraded = _outcome(no_render_context)
    assert {Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY} <= skipped
    assert CRAWL_EMPTY in {d.scope for d in degraded}


# ── стан покриття: доказ той самий, що бачив краул ────────────────────────
#
# Старі правила `crawl.shallow` і `crawl.failures` замінені спільною
# оцінкою покриття (app/audit/coverage.py). Ці тести стережуть те, що
# лишилося незмінним по суті: рішення спирається на ОБИДВА представлення
# сторінки — і статичне, і відрендерене.

LINKED3 = (
    '<a href="https://example.com/a">a</a>'
    '<a href="https://example.com/b">b</a>'
    '<a href="https://example.com/c">c</a>'
)


def test_navigation_only_after_render_still_counts_as_evidence_of_more():
    """Навігація лише в DOM — це так само «іти було куди».

    Шість сайтів night2 мали таку навігацію: `cbu.edu.tr` — 60 внутрішніх
    посилань у DOM і жодного у відповіді. Кандидати з рендеру мусять
    рахуватися, інакше SPA завжди виглядає односторінковим сайтом.
    """
    from app.audit.types import COVERAGE_WITHHELD

    ctx = _ctx(
        f"<html><body><main>{WORDS}</main></body></html>",
        f"<html><body><main>{WORDS}{LINKED3}</main></body></html>",
    )
    _, degraded = _outcome(ctx)
    assert COVERAGE_WITHHELD in {d.scope for d in degraded}


def test_a_genuine_single_page_site_keeps_its_score():
    """Іти справді нікуди — бал лишається, застережень немає.

    Інакше кожна односторінкова візитівка втрачала б оцінку за
    властивість, яка є її суттю, а не дефектом.
    """
    from app.audit.types import COVERAGE_LIMITED, COVERAGE_WITHHELD

    ctx = _ctx(
        f"<html><body><main>{WORDS}</main></body></html>",
        f"<html><body><main>{WORDS}</main></body></html>",
    )
    skipped, degraded = _outcome(ctx)
    scopes = {d.scope for d in degraded}
    assert COVERAGE_WITHHELD not in scopes
    assert COVERAGE_LIMITED not in scopes
    assert Module.SEO not in skipped


def test_external_links_are_not_evidence_of_a_larger_site():
    from app.audit.types import COVERAGE_WITHHELD

    ctx = _ctx(
        "<html><body><main>"
        + WORDS
        + '<a href="https://other.org/x">x</a>'
        + '<a href="https://other.org/y">y</a>'
        + '<a href="https://other.org/z">z</a>'
        + "</main></body></html>",
        None,
    )
    _, degraded = _outcome(ctx)
    assert COVERAGE_WITHHELD not in {d.scope for d in degraded}


def test_static_links_survive_a_failed_render():
    """Рендер не вдався — судимо за тим, що віддав сервер."""
    from app.audit.types import COVERAGE_WITHHELD

    ctx = _ctx(f"<html><body><main>{WORDS}{LINKED3}</main></body></html>", None)
    _, degraded = _outcome(ctx)
    assert COVERAGE_WITHHELD in {d.scope for d in degraded}


def test_one_page_plus_genuine_access_failures_is_withheld_with_the_true_reason():
    """Одна сторінка + девʼять 500-х: бал притримано через ДОСТУП.

    Раніше це звалося `crawl.failures` і рахувало будь-які невдачі. Тепер
    причина названа точно: живі адреси не відповіли.
    """
    from app.audit.types import COVERAGE_WITHHELD

    page = page_from_html(
        f"<html><body><main>{WORDS}{LINKED3}</main></body></html>",
        url="https://example.com/",
    )
    broken = [
        page_from_html("<html><body>500</body></html>", url=f"https://example.com/{i}")
        for i in range(9)
    ]
    for b in broken:
        b.status_code = 500
    ctx = context(page, *broken)
    ctx.failed_urls = {f"https://example.com/{i}": "HTTP 500" for i in range(9)}

    skipped, degraded = _outcome(ctx)
    hit = next(d for d in degraded if d.scope == COVERAGE_WITHHELD)
    assert "access_failures" in (hit.reason_params or {}).get("reasons", [])
    assert Module.SEO in skipped


# ── Поріг міряє СВІЙ текст, а не суму адрес (E2-ENGINE-FINDING-01) ──────────
#
# Той самий вміст під кількома адресами рахувався стільки разів, скільки було
# адрес. Каталог-заглушка на 25 слів, відданий під вісьмома query-адресами,
# давав 200 слів, проходив поріг у 100 і отримував бал 61 — при тому, що свого
# тексту на сайті двадцять пʼять слів. Логічні сторінки тут не рятували:
# `group()` приєднує варіант до представника лише тоді, коли сторінка САМА
# оголосила canonical, а заглушка його не оголошує ніколи.

LISTING_WORDS = " ".join(f"рядок{i}" for i in range(25))  # 25 слів — менше за поріг

#: Назви параметрів навмисно довільні й не мають нічого спільного з `?ND`,
#: `?MA`, `?SA` автоіндексу: правило про однаковий вміст, а не про конкретний
#: веб-сервер. Тест нижче повторює його на ще одному, іншому наборі.
LISTING_QUERIES = ("", "?alpha", "?beta=1", "?gamma=x&delta=y",
                   "?epsilon", "?zeta=2", "?eta", "?theta=3")


def _same_page_under(queries, body: str = LISTING_WORDS, base="https://example.com/"):
    """Один і той самий вміст під кількома адресами. Canonical не оголошено."""
    pages = []
    for query in queries:
        page = page_from_html(
            f"<html><body><main>{body}</main></body></html>", url=f"{base}{query}"
        )
        assert page.canonical is None, "фікстура мусить лишатись без canonical"
        pages.append(page)
    return pages


def test_one_listing_under_many_urls_does_not_clear_the_content_floor():
    """Вісім адрес, один вміст — поріг бачить двадцять пʼять слів, а не двісті."""
    pages = _same_page_under(LISTING_QUERIES)
    assert len(pages) == 8
    assert sum(p.word_count for p in pages) >= 200, "інакше фікстура не відтворює дефект"

    skipped, degraded = _outcome(context(*pages))

    assert Module.SEO in skipped
    assert Module.AI_READY in skipped
    assert Module.LLM_VISIBILITY in skipped
    assert CRAWL_EMPTY in {d.scope for d in degraded}


def test_deduplication_does_not_require_a_declared_canonical():
    """Саме цей випадок і проходив повз поріг: заглушка canonical не оголошує."""
    pages = _same_page_under(LISTING_QUERIES)
    assert all(p.canonical is None for p in pages)

    skipped, _ = _outcome(context(*pages))

    assert Module.SEO in skipped, "без canonical дедуплікація однаково мусить працювати"


def test_arbitrary_query_names_reproduce_the_rule():
    """Правило про однаковий ВМІСТ, а не про перелік відомих імен параметрів."""
    other = ("", "?zzz", "?q=1", "?page=2", "?ref=x", "?tab=b", "?v=9", "?mode=list")
    assert not set(other) & set(LISTING_QUERIES) - {""}

    skipped, degraded = _outcome(context(*_same_page_under(other)))

    assert Module.SEO in skipped
    assert CRAWL_EMPTY in {d.scope for d in degraded}


def test_distinct_query_pages_with_distinct_content_count_independently():
    """Різні query з різним вмістом лишаються різними сторінками."""
    pages = [
        page_from_html(
            "<html><body><main>"
            + " ".join(f"унікальне{i}слово{j}" for j in range(20))
            + "</main></body></html>",
            url=f"https://example.com/?q={i}",
        )
        for i in range(8)
    ]

    skipped, degraded = _outcome(context(*pages))

    assert Module.SEO not in skipped
    assert Module.AI_READY not in skipped
    assert CRAWL_EMPTY not in {d.scope for d in degraded}


def test_a_substantive_unique_site_remains_auditable():
    """Одна змістовна сторінка над порогом судиться як і раніше."""
    page = page_from_html(
        f"<html><body><main>{WORDS}</main></body></html>", url="https://example.com/"
    )

    skipped, degraded = _outcome(context(page))

    assert Module.SEO not in skipped
    assert CRAWL_EMPTY not in {d.scope for d in degraded}


def test_tracking_parameters_are_still_normalised_away():
    """Нормалізація адрес не змінена: мітки джерела й далі не створюють сторінки."""
    from app.audit.logical_pages import normalize

    assert normalize("https://example.com/?utm_source=x") == normalize("https://example.com/")
    assert normalize("https://example.com/?a=1&b=2") == normalize("https://example.com/?b=2&a=1")
    assert normalize("https://example.com/?id=12") != normalize("https://example.com/?id=13")


def test_page_inventory_stays_available_to_downstream_checks():
    """Це арифметика порога, а не зміна складу сторінок: жодна не зникає."""
    pages = _same_page_under(LISTING_QUERIES)
    ctx = context(*pages)

    _outcome(ctx)

    assert len(ctx.pages) == 8, "сторінки не зливаються й не викидаються"
    assert len(ctx.ok_pages) == 8
    assert [p.url for p in ctx.pages] == [p.url for p in pages]


def test_no_numeric_score_for_a_site_of_repeated_content():
    """Повний шлях оркестрації: бала немає ні загального, ні контентних модулів."""
    from app.audit.logical_pages import group as group_logical_pages
    from app.audit.orchestrator import rescore

    pages = _same_page_under(LISTING_QUERIES)
    ctx = context(*pages)
    ctx.raw_pages = list(pages)
    ctx.pages = group_logical_pages(list(pages))

    outcome = rescore(ctx)

    assert outcome.overall is None, "сайту немає — числа не буде"
    assert "seo" not in outcome.scores
    assert "ai_ready" not in outcome.scores
    assert "llm_visibility" not in outcome.scores
    assert CRAWL_EMPTY in {d.scope for d in outcome.degraded}


def test_version_transition_is_pinned_for_unique_content_qualification():
    """Літеральні значення переходу, а не звірка величини з нею самою.

    Поріг вирішує, чи мають контентні модулі бал, — той самий клас, що
    покоління 4 і 5, тому піднято `DETECTOR_RULES`. Краул не змінився:
    ті самі адреси в тому самому порядку, тож `CRAWLER_VERSION` лишається 4.
    """
    from app.audit import versions

    assert versions.DETECTOR_RULES == "14"
    assert versions.detector_version() == "3b9a556ab798"

    assert versions.CRAWLER_VERSION == "4"
    assert versions.SCORING_RULES == "5"
    assert versions.scoring_version() == "aa4ecc62a5a3"


def test_the_content_floor_itself_is_unchanged():
    """Змінилось, ЩО рахується, а не поріг: сто слів лишились сотнею."""
    from app.audit.orchestrator import MIN_WORDS_FOR_A_SITE

    assert MIN_WORDS_FOR_A_SITE == 100
