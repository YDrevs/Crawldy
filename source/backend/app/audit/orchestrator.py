"""Оркестратор: від URL до (scores, issues, pages). Без залежності від БД."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Awaitable, Callable, Collection, Iterable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from app.audit import about_page, hierarchy, render_diff
from app.audit.checks import all_checks
from app.audit.coverage import CoverageState, assess, collect_evidence
from app.audit.crawler import crawl
from app.audit.duplicates import canonical_text
from app.audit.enums import DegradationKind
from app.audit.extractor import signals_from_html, vendors_in_urls
from app.audit.fetcher import Fetcher, SiteUnreachable, normalize_url, origin_of
from app.audit.frontier import Frontier, Source
from app.audit.link_graph import build as build_link_graph
from app.audit.llm import get_analyst
from app.audit.logical_pages import group as group_logical_pages
from app.audit.logical_pages import normalize
from app.audit.page_kinds import SELLS_SOMETHING, PageKind, kind_of
from app.audit.performance.factory import get_provider
from app.audit.render import Renderer, get_renderer
from app.audit.site_context import (
    collect_infra,
    collect_llms_txt,
    collect_robots,
    collect_sitemap,
)
from app.audit.site_facts import collect as collect_site_facts
from app.audit.standards import analytics_vendors
from app.audit.types import (
    COVERAGE_LIMITED,
    COVERAGE_WITHHELD,
    CRAWL_BLIND,
    CRAWL_EMPTY,
    CRAWL_EMPTY_STATIC,
    ENTRY_ERROR,
    Confidence,
    Degradation,
    Issue,
    Module,
    PageSignals,
    SiteContext,
    Strategy,
)
from app.audit.versions import audit_versions
from app.core.config import settings
from app.core.logging import log

# Який модуль лишається без даних, якщо колектор впав.
COLLECTOR_MODULES: dict[str, list[Module]] = {
    "robots": [Module.SEO, Module.LLM_VISIBILITY],
    "sitemap": [Module.SEO],
    "llms_txt": [Module.AI_READY],
    "infra": [Module.TECH],
}



async def _report(
    on_progress: ProgressReporter | None, stage: str, read: int, known: int
) -> None:
    """Повідомити хід, якщо є кому.

    Слухач пише в базу, тобто ходить назовні, — і його збій не має
    валити аудит: показник ходу дешевший за результат, заради якого все
    й робиться.
    """
    if on_progress is None:
        return
    try:
        await on_progress(stage, read, max(known, read))
    except Exception:  # noqa: BLE001 - показник не важливіший за аудит
        log.warning("progress_report_failed", stage=stage)


def _staged(
    on_progress: ProgressReporter | None, stage: str
) -> Callable[[int, int], Awaitable[None]] | None:
    """Приклеїти стадію до слухача, який знає лише числа.

    Краул стадії не знає навмисно: та сама функція працює і в другій
    хвилі, після рендеру, і називати її одним словом мав би той, хто цю
    хвилю замовив.
    """
    if on_progress is None:
        return None

    async def report(read: int, known: int) -> None:
        await _report(on_progress, stage, read, known)

    return report


def _shifted(
    on_progress: ProgressReporter | None, already: int
) -> Callable[[int, int], Awaitable[None]] | None:
    """Слухач другої хвилі краулу: її числа плюс уже прочитане.

    Хвиля після рендеру рахує свої сторінки з нуля, а екран показує весь
    аудит. Без зсуву лічильник на очах у клієнта стрибав би назад.
    """
    stage = _staged(on_progress, STAGE_CRAWL)
    if stage is None:
        return None

    async def report(read: int, known: int) -> None:
        await stage(already + read, already + known)

    return report

# Стадії, які аудит показує назовні, поки він триває. Перелік короткий
# навмисно: кожен рядок мусить мати переклад і щось означати для людини,
# яка дивиться на екран очікування. Дрібніші кроки (robots, карта сайту)
# сюди не входять — вони швидкі, і миготіння підписів дратує.
# Перед краулом стоїть робота на десяток секунд: вхідна сторінка,
# robots.txt і карта сайту. Чисел вона не дає — і саме тому потребує
# власного імені: інакше екран мовчить рівно там, де людина щойно
# натиснула кнопку й найбільше сумнівається, чи щось узагалі сталось.
STAGE_DISCOVERY = "discovery"
STAGE_CRAWL = "crawl"
# Вимірювання швидкості йде ПАРАЛЕЛЬНО з краулом і зазвичай довше за
# нього: PSI міряє живий сайт двома стратегіями. Без власного імені
# екран завмирав на «прочитано 10 з 10» рівно на цей час — тобто на
# найдовшу частину аудиту.
STAGE_MEASURING = "measuring"
STAGE_RENDER = "render"
STAGE_ANALYSIS = "analysis"
STAGE_SCORING = "scoring"

# Куди повідомляти хід: (стадія, прочитано, відомо). Числа справжні — ті
# самі, що потім стануть покриттям у звіті. Слухач передається окремим
# аргументом, а не полем `AuditOptions`: опції серіалізуються в базу, а
# функція — ні.
ProgressReporter = Callable[[str, int, int], Awaitable[None]]


@dataclass(slots=True)
class AuditOptions:
    max_pages: int | None = None
    max_depth: int | None = None
    # Обидві стратегії за замовчуванням: розрив між ними — окрема
    # знахідка, і без десктопу її нема з чим порівняти. PSI обидва
    # виміри робить паралельно, тож аудит від цього не довшає.
    strategies: list[Strategy] = field(
        default_factory=lambda: [Strategy.MOBILE, Strategy.DESKTOP]
    )
    modules: set[Module] | None = None
    perf_provider: str | None = None
    # None — як налаштовано глобально; False вимикає рендер для цього аудиту.
    render: bool | None = None
    render_max_pages: int | None = None
    # None — як налаштовано глобально; False вимикає семантику для цього аудиту.
    llm: bool | None = None
    llm_max_pages: int | None = None
    # Модель впливає на результат, а не лише на ціну: на калібрувальній
    # вибірці різниця між найдорожчою й найдешевшою — 13 балів. Тому це
    # параметр аудиту, а не глобальне налаштування процесу.
    llm_model: str | None = None
    # Ким аудит представляється сайту. `None` — глобальний рядок.
    #
    # Існує заради підтвердженого володіння: сайт, який відбиває
    # сторонніх ботів, зможе впустити перевірку власного власника. Сам
    # механізм підтвердження ще не зроблений, і поведінка звичайного
    # краулу не змінена — відкритий лише шлях, щоб потім не переробляти
    # збір заново.
    user_agent: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AuditOptions:
        data = data or {}
        modules = data.get("modules")
        strategies = data.get("strategies") or ["mobile", "desktop"]
        return cls(
            max_pages=data.get("max_pages"),
            max_depth=data.get("max_depth"),
            strategies=[Strategy(s) for s in strategies],
            modules={Module(m) for m in modules} if modules else None,
            perf_provider=data.get("perf_provider"),
            render=data.get("render"),
            render_max_pages=data.get("render_max_pages"),
            llm=data.get("llm"),
            llm_max_pages=data.get("llm_max_pages"),
            llm_model=data.get("llm_model"),
            user_agent=data.get("user_agent"),
        )


@dataclass(slots=True)
class AuditOutcome:
    context: SiteContext
    issues: list[Issue]
    scores: dict[str, int]
    overall: int | None
    degraded: list[Degradation]
    skipped_modules: set[Module] = field(default_factory=set)
    partial_modules: set[Module] = field(default_factory=set)
    # Чим саме це порахували. Без цього різниця між двома аудитами
    # однаково пояснюється змінами на сайті й змінами в нас.
    versions: dict[str, str | None] = field(default_factory=dict)


async def run_audit(
    url: str,
    options: AuditOptions | None = None,
    *,
    on_progress: ProgressReporter | None = None,
) -> AuditOutcome:
    options = options or AuditOptions()
    await _report(on_progress, STAGE_DISCOVERY, 0, 0)
    entry_url = normalize_url(url)
    origin = origin_of(entry_url)
    degraded: list[Degradation] = []

    fetcher = Fetcher(user_agent=options.user_agent)
    tls_error: str | None = None
    try:
        entry = await fetcher.get(entry_url)

        # Зламаний сертифікат — це не збій аудиту, а найважливіша знахідка
        # для клієнта: браузер показує його відвідувачам попередження. Тому
        # пробуємо ще раз без перевірки TLS і аудитуємо сайт до кінця.
        if entry.error and _is_tls_error(entry.error):
            tls_error = entry.error
            await fetcher.aclose()
            fetcher = Fetcher(verify_tls=False, user_agent=options.user_agent)
            entry = await fetcher.get(entry_url)
            if entry.error:
                tls_error = None

        if entry.error:
            raise SiteUnreachable(f"не вдалося завантажити {entry_url}: {entry.error}")

        final_url = entry.final_url
        origin = origin_of(final_url)
        ctx = SiteContext(entry_url=final_url, origin=origin)
        ctx.is_https = final_url.startswith("https://")
        ctx.hsts = "strict-transport-security" in entry.headers
        ctx.tls_error = tls_error

        robots, llms, infra = await asyncio.gather(
            _safe(collect_robots(fetcher, origin), "robots", degraded),
            _safe(collect_llms_txt(fetcher, origin), "llms_txt", degraded),
            _safe(collect_infra(fetcher, origin), "infra", degraded),
        )
        ctx.robots = robots or ctx.robots
        ctx.llms_txt = llms or ctx.llms_txt
        ctx.infra = infra or ctx.infra

        sitemap = await _safe(collect_sitemap(fetcher, origin, ctx.robots), "sitemap", degraded)
        ctx.sitemap = sitemap or ctx.sitemap

        max_pages = options.max_pages or settings.crawl_max_pages
        max_depth = (
            options.max_depth if options.max_depth is not None else settings.crawl_max_depth
        )
        # Черга переживає межу виклику: після рендеру буде друга хвиля, і
        # вона мусить знати, що вже прочитано. Robots стоїть у дверях
        # черги й діє однаково на статичні й відрендерені адреси.
        frontier = Frontier(
            origin=origin,
            max_depth=max_depth,
            robots=ctx.robots.parsed,
            user_agent=settings.user_agent,
        )
        # Стадію додає оркестратор, бо краул знає лише свої числа: та
        # сама функція працює і в другій хвилі, після рендеру.
        crawl_progress = _staged(on_progress, STAGE_CRAWL)
        crawl_task = crawl(
            fetcher,
            final_url,
            origin,
            max_pages=max_pages,
            max_depth=max_depth,
            seed_urls=_seed_from_sitemap(ctx.sitemap.urls),
            prefetched=entry,
            frontier=frontier,
            on_progress=crawl_progress,
        )
        # Окрема задача, а не `gather`, саме заради екрана: щойно краул
        # скінчився, вимірювання лишається єдиною роботою, і назвати треба
        # його. `gather` віддав би керування аж після обох.
        perf_job = asyncio.ensure_future(
            _measure_performance(final_url, options, degraded)
        )
        pages, failed = await crawl_task
        if not perf_job.done():
            await _report(on_progress, STAGE_MEASURING, len(pages), len(pages))
        performance = await perf_job
        ctx.performance = performance
        _absorb(ctx, final_url, pages, failed)
        ctx.redirect_limited = sorted(frontier.redirect_limited)

        # Рендер — після краулу, а не всередині: інакше ніде взяти
        # статичну версію сторінки, а вся цінність саме в різниці. Але
        # всередині життя fetcher'а, бо адреси, які видно лише після
        # виконання JS, ще треба завантажити тим самим краулом.
        await _report(on_progress, STAGE_RENDER, len(ctx.raw_pages), max_pages)
        await _render_and_discover(
            ctx,
            options,
            degraded,
            fetcher=fetcher,
            frontier=frontier,
            entry_url=final_url,
            max_pages=max_pages,
            max_depth=max_depth,
            on_progress=on_progress,
        )
    finally:
        await fetcher.aclose()

    # Зведення фактів іде перед семантикою навмисно: модель отримує
    # питання лише про те, чого в розмітці немає. Порядок джерел істини —
    # детерміністичні докази, потім зведення, і аж потім висновок моделі.
    #
    # Далі сторінки вже не додаються, тож знаменник дорівнює лічильнику:
    # смужка доходить до кінця, і це правда, а не округлення вгору.
    await _report(on_progress, STAGE_ANALYSIS, len(ctx.raw_pages), len(ctx.raw_pages))

    ctx.known = collect_site_facts(ctx)
    ctx.links = build_link_graph(ctx)

    # Семантика — останньою: вона читає вже зібраний текст сторінок і
    # нічого не додає до збору даних.
    await _analyse_semantics(ctx, options, degraded)

    skipped, partial = _module_coverage(options, ctx, performance, degraded)

    issues = _stamp_importance(
        _temper_by_coverage(_run_checks(ctx, options.modules, degraded), ctx), ctx
    )
    await _report(on_progress, STAGE_SCORING, len(ctx.raw_pages), len(ctx.raw_pages))
    overall, scores = compute_scores_safe(issues, skipped)
    versions = audit_versions(options, _model_used(ctx, options))
    log.info(
        "audit_scored",
        url=final_url,
        overall=overall,
        issues=len(issues),
        detector=versions["detector"],
        scoring=versions["scoring"],
    )
    return AuditOutcome(
        context=ctx,
        issues=issues,
        scores=scores,
        overall=overall,
        degraded=degraded,
        skipped_modules=skipped,
        partial_modules=partial,
        versions=versions,
    )


# Нижче цієї частки сайту твердження про весь сайт спирається на надто
# малу вибірку. Карта на 8 тисяч адрес і 20 прочитаних сторінок — це
# 0.25%: сказати «на сайті немає» тут можна лише про те, що видно з
# кожної сторінки, як заголовок відповіді.
COVERAGE_FOR_SITE_WIDE_CLAIMS = 0.2

# Скільки слів має бути на всьому сайті, щоб було що оцінювати.
# oldetownhall.com віддав єдину сторінку на чотирнадцять слів — повідомлення
# хостера про призупинення акаунта, — і отримав 68 балів. Сайту немає, а
# оцінка вища за середню: гірше за таку відповідь лише мовчання.
MIN_WORDS_FOR_A_SITE = 100


def _unique_words(ctx: SiteContext, view: Callable[[PageSignals], PageSignals]) -> int:
    """Скільки на сайті СВОГО тексту: однаковий вміст рахується один раз.

    Поріг питає, чи є що оцінювати. Сума по сторінках відповідала на інше
    питання — скільки адрес віддали текст, — і різниця між ними не
    теоретична: каталог-заглушка на 25 слів, відданий під вісьмома
    адресами з різними query, давав 200 слів, проходив поріг і отримував
    бал 61. Сайту немає, а оцінка вища за середню — рівно та відповідь,
    заради якої поріг і писався.

    Звести адреси в логічні сторінки тут недосить: `group()` приєднує
    варіант до представника лише тоді, коли сторінка САМА оголосила
    canonical. Заглушка його не оголошує ніколи, тож саме той випадок,
    якого поріг стосується, повз нього й проходив.

    Ознака однаковості береться та сама, якою користується `duplicates`
    для точних збігів, — `canonical_text` і його хеш. Другого визначення
    «той самий вміст» у проєкті бути не повинно: розійшовшись, вони дали
    б дві різні відповіді на одне питання.

    Рахується те саме представлення, яке потім і порівнюється з порогом:
    ключ статичної суми береться зі статичної відповіді, ключ суми після
    рендеру — з відрендереної. Інакше поріг міряв би одне, а ключ — інше.

    Сторінки НЕ зливаються й не викидаються: це арифметика порога, а не
    зміна складу `ctx.pages`. Представник групи — перша прочитана
    сторінка, і береться саме її `word_count`, як і до цієї правки.
    """
    seen: set[str] = set()
    total = 0
    for page in ctx.ok_pages:
        signals = view(page)
        digest = hashlib.sha256(canonical_text(signals.text or "").encode()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        total += signals.word_count
    return total


def _temper_by_coverage(issues: list[Issue], ctx: SiteContext) -> list[Issue]:
    """Знижує впевненість у твердженнях про весь сайт при малому покритті.

    Знахідка на конкретній сторінці від покриття не залежить: ми її
    бачили. А «ніде на сайті немає» при двадцяти прочитаних сторінках із
    восьми тисяч — це твердження про нашу вибірку, і воно має бути
    позначене як менш тверде, а не подане нарівні зі статусом відповіді.
    """
    known = ctx.sitemap.url_count or len(ctx.pages)
    if not known:
        return issues
    coverage = len(ctx.pages) / known
    if coverage >= COVERAGE_FOR_SITE_WIDE_CLAIMS:
        return issues

    for issue in issues:
        if issue.page_url or issue.confidence is not Confidence.HIGH:
            continue
        issue.confidence = Confidence.MEDIUM
        issue.evidence.setdefault("coverage", f"{len(ctx.pages)} з {known} відомих адрес")
    return issues


def _accessibility_coverage(
    performance: list[Any], skipped: set[Module], degraded: list[Degradation]
) -> None:
    """Доступність без даних — не «сто балів», а виключений напрям.

    PSI відповів, але категорія accessibility могла не приїхати: інший
    провайдер, урізана відповідь, старий кеш. Мовчазні сто балів за
    неперевірене — саме та вигадана цифра, якої в цьому продукті бути
    не може.
    """
    if any(r.accessibility_score is not None for r in performance):
        return
    skipped.add(Module.ACCESSIBILITY)
    degraded.append(
        Degradation(
            scope=Module.ACCESSIBILITY.value,
            kind=DegradationKind.PROVIDER_UNAVAILABLE,
            reason="перевірок доступності не було: провайдер не повернув цю категорію",
            reason_key="notice.accessibility.no_category",
            affected_modules=[Module.ACCESSIBILITY],
        )
    )


def _accessibility_under_filter(
    requested: set[Module],
    performance: list[Any],
    skipped: set[Module],
    degraded: list[Degradation],
) -> None:
    """Доступність, коли клієнт обрав модулі: вибір і доказ — різні факти.

    Фільтр модулів закінчував розбір раніше, ніж хтось питав, чи є в
    доступності дані. На шести знімках Crawldy без швидкості вона виходила
    сотнею: категорії у відповіді не було, а бал був. Тепер фільтр вирішує
    лише, чи модуль просили; чи його виміряно, вирішують дані — так само,
    як без фільтра.

    Чому доступності може не бути, коли її просили:

    - клієнт вимкнув швидкість, тож спільного запиту до провайдера не
      було. Це не збій — провайдера ніхто не питав, — і не вибір щодо
      доступності: її клієнт не вимикав. Тому `PARTIAL_DATA` зі своїм
      ключем, а не `PROVIDER_UNAVAILABLE` і не `MODULE_EXCLUDED`;
    - провайдер відповів без придатної категорії — те саме, що без фільтра;
    - провайдер не відповів зовсім — модуль виключається, як і без фільтра.

    Дані є при вимкненій швидкості лише в перерахунку знімка з іншими
    опціями. Тоді доступність виміряна, і бал у неї справжній.
    """
    if Module.ACCESSIBILITY not in requested:
        return
    if any(r.accessibility_score is not None for r in performance):
        return
    if Module.PERFORMANCE not in requested:
        skipped.add(Module.ACCESSIBILITY)
        degraded.append(
            Degradation(
                scope=Module.ACCESSIBILITY.value,
                kind=DegradationKind.PARTIAL_DATA,
                reason=(
                    "доступність не виміряно: вимірювання швидкості виключено "
                    "з цієї перевірки"
                ),
                reason_key="notice.accessibility.not_measured",
                affected_modules=[Module.ACCESSIBILITY],
            )
        )
        return
    if any(r.fetched for r in performance):
        _accessibility_coverage(performance, skipped, degraded)
        return
    # Провайдер не відповів. Прогалину пояснює деградація швидкості — та сама,
    # що й без фільтра (`_performance_coverage`); друга, про доступність,
    # розповідала б ту саму подію вдруге.
    skipped.add(Module.ACCESSIBILITY)


def _model_used(ctx: SiteContext, options: AuditOptions) -> str | None:
    """Модель записуємо лише тоді, коли вона справді відповіла.

    Заданий у налаштуваннях ключ ще нічого не означає: виклик міг не
    відбутися, і тоді аудит порахований без семантики.
    """
    brief = ctx.brief
    if brief is None or not getattr(brief, "analysed", False):
        return None
    return options.llm_model or settings.llm_model


def _module_coverage(
    options: AuditOptions,
    ctx: SiteContext,
    performance: list[Any],
    degraded: list[Degradation],
) -> tuple[set[Module], set[Module]]:
    """Які модулі без даних узагалі, а які оцінені не на всіх сигналах.

    Три різні стани, які раніше зливалися в один:
    вимкнено користувачем / провайдер мовчить / порахували чим маємо.
    """
    skipped, partial = _collected_coverage(options, ctx, performance, degraded)
    # Семантичний шар працює раніше за цей розбір і свої прогалини вже
    # записав у `degraded`. Правило спільне зі збереженими аудитами.
    partial |= semantic_gaps(degraded, skipped)
    # Сторінка «про нас» без вердикту (E-10): кандидат є, а прочитати його
    # не вдалося або не пробували. Це прогалина даних, а не знахідка, і
    # вона мусить стояти в `missing_data` й робити модуль неповним — тому
    # рішення питається ТУТ, до чеків, у того самого детектора, якого
    # питає й сам чек. Збережений аудит виводить те саме з деградації.
    gap = about_page.degradation(about_page.detect(ctx))
    if (
        gap is not None
        and Module.LLM_VISIBILITY not in skipped
        and (options.modules is None or Module.LLM_VISIBILITY in options.modules)
    ):
        degraded.append(gap)
        partial.add(Module.LLM_VISIBILITY)
    # Ієрархія без вердикту (E-15): прочитаного замало, щоб сказати, чи
    # стоять сторінки одна під одною. Те саме, що вище, і з тієї ж причини:
    # це прогалина даних, а не знахідка, тож вона мусить стояти в
    # `missing_data` й робити модуль неповним. Рішення питається в того
    # самого класифікатора, якого питають чек і рядок застосовності.
    hierarchy_gap = hierarchy.degradation(hierarchy.classify(ctx))
    if (
        hierarchy_gap is not None
        and Module.AI_READY not in skipped
        and (options.modules is None or Module.AI_READY in options.modules)
    ):
        degraded.append(hierarchy_gap)
        partial.add(Module.AI_READY)
    return skipped, partial


def _collected_coverage(
    options: AuditOptions,
    ctx: SiteContext,
    performance: list[Any],
    degraded: list[Degradation],
) -> tuple[set[Module], set[Module]]:
    """Покриття за зібраними даними: сліпота, вхід, охоплення, фільтр, провайдер."""
    skipped: set[Module] = set()
    partial: set[Module] = set()

    # Жодної сторінки з контентом — оцінювати нічого. Перевірка йде перед
    # вибором модулів: сліпота не залежить від того, які модулі замовили.
    # Без неї сайт, що віддає ботам 403, отримував найвищий бал у групі —
    # чеки мовчали не тому, що все добре, а тому, що не було на що дивитися.
    if not ctx.ok_pages:
        blind = [Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY]
        skipped.update(blind)
        statuses = sorted({p.status_code for p in ctx.pages if p.status_code})
        degraded.append(
            Degradation(
                scope=CRAWL_BLIND,
                kind=DegradationKind.COLLECTOR_FAILED,
                reason=(
                    "сайт не віддав жодної сторінки з контентом "
                    f"(статуси відповіді: {statuses or 'немає'})"
                ),
                reason_key="notice.crawl.blind",
                reason_params={"statuses": statuses or []},
                affected_modules=blind,
            )
        )

    # Тексту немає. Це не «поганий контент», а відсутність сайту:
    # сторінка-заглушка хостера, порожній домен, редірект у нікуди.
    #
    # Але «немає тексту» — питання ДО ЯКОГО ЧИТАЧА. Поріг мусить міряти
    # те саме представлення, яке читають чеки модуля, інакше він вимикає
    # чеки, у яких дані були:
    #
    #   SEO дивиться на сторінку після виконання JS (`as_seen`), бо
    #   Google її так і бачить. Порожня оболонка SPA у відповіді сервера
    #   нічого не каже про те, що індексує пошук.
    #
    #   AI_READY і LLM_VISIBILITY навмисно лишаються на статичній
    #   відповіді: асистенти JS здебільшого не виконують, і розмітки,
    #   якої немає у відповіді, для них не існує.
    #
    # Спільний поріг на статиці виключав SEO у 36 сайтів night2, які ми
    # успішно відрендерили: `zenit.win` мав 0 слів у відповіді й 22 129
    # після рендеру, `dagrasso.pl` — 0 і 9 161. Повідомлення при цьому
    # казало клієнтові «на всьому сайті 0 слів», що для відрендереного
    # сайту просто неправда.
    static_words = _unique_words(ctx, lambda page: page)
    rendered_words = _unique_words(ctx, ctx.as_seen)

    if ctx.ok_pages and rendered_words < MIN_WORDS_FOR_A_SITE:
        # Тексту немає навіть після рендеру — не бачить ніхто.
        blind = [Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY]
        skipped.update(blind)
        degraded.append(
            Degradation(
                scope=CRAWL_EMPTY,
                kind=DegradationKind.COLLECTOR_FAILED,
                reason=(
                    f"на всьому сайті {rendered_words} слів навіть після "
                    f"виконання скриптів; прочитано сторінок: "
                    f"{len(ctx.ok_pages)}. Оцінювати нема чого"
                ),
                reason_key="notice.crawl.empty",
                reason_params={
                    "words": rendered_words,
                    "pages": len(ctx.ok_pages),
                },
                affected_modules=blind,
            )
        )
    elif ctx.ok_pages and static_words < MIN_WORDS_FOR_A_SITE:
        # Текст є, але лише після виконання скриптів. Для пошуку сайт
        # читається — SEO лишається в скорі. Для асистентів він порожній,
        # і це не наша сліпота, а властивість сайту: саме тому модулі
        # AI виключаються, а не отримують низький бал за вигаданими
        # даними.
        blind = [Module.AI_READY, Module.LLM_VISIBILITY]
        skipped.update(blind)
        degraded.append(
            Degradation(
                scope=CRAWL_EMPTY_STATIC,
                kind=DegradationKind.COLLECTOR_FAILED,
                reason=(
                    f"у відповіді сервера {static_words} слів; текст "
                    f"зʼявляється лише після виконання скриптів "
                    f"({rendered_words} слів). Пошук таку сторінку бачить, "
                    f"асистенти — здебільшого ні"
                ),
                reason_key="notice.crawl.empty_static",
                reason_params={
                    "words": static_words,
                    "rendered": rendered_words,
                    "pages": len(ctx.ok_pages),
                },
                affected_modules=blind,
            )
        )

    # Вхідна адреса відповіла помилкою, але сайт читається: краул пішов за
    # посиланнями зі сторінки помилки й приніс справжні сторінки.
    #
    # Мовчати про це не можна — ми виміряли не те, що просили.
    # `bosch.com/this-page-does-not-exist/` повернув 404 і отримав 76 балів,
    # причому Lighthouse міряв саме цю адресу: модуль швидкості вагою 0.22
    # описував сторінку 404, а звіт про це не казав ані слова. Єдиним слідом
    # був `seo.broken_links`, який називав вхідну адресу серед битих.
    entry = ctx.pages[0] if ctx.pages else None
    entry_status = entry.status_code if entry else None
    if ctx.ok_pages and entry_status and not 200 <= entry_status < 300:
        # Модуль лишається в скорі: числа справжні, просто про іншу
        # сторінку. Виключати його означало б викинути виміряне.
        partial.add(Module.PERFORMANCE)
        stand_in = ctx.home
        degraded.append(
            Degradation(
                scope=ENTRY_ERROR,
                kind=DegradationKind.PARTIAL_DATA,
                reason=(
                    f"вхідна адреса повернула HTTP {entry_status}: швидкість виміряно "
                    "на сторінці помилки, а не на сайті"
                    + (f"; за головну взято {stand_in.url}" if stand_in else "")
                ),
                # Два ключі, а не один із необовʼязковим хвостом: підстановка
                # порожнього рядка лишила б у перекладі висячу крапку з комою,
                # і перекладач не мав би як це виправити.
                reason_key=(
                    "notice.crawl.entry_error_stand_in"
                    if stand_in
                    else "notice.crawl.entry_error"
                ),
                reason_params={
                    "status": entry_status,
                    **({"stand_in": stand_in.url} if stand_in else {}),
                },
                affected_modules=[Module.PERFORMANCE],
            )
        )

    # Спільна оцінка покриття: чи репрезентує прочитане той живий сайт,
    # який справді існує. Вона замінила два незалежні правила —
    # `crawl.failures` (частка невдач, яка рахувала спостережені 404 як
    # недоступність і забирала бал у сайтів, прочитаних без жодної
    # помилки) і `crawl.shallow` (лічив 4xx-сторінки як обійдені й
    # мовчав рівно там, де доказів більшого сайту найбільше).
    if ctx.ok_pages:
        evidence = collect_evidence(ctx, max_pages=options.max_pages)
        state, why = assess(evidence)
        content = [Module.SEO, Module.AI_READY, Module.LLM_VISIBILITY]
        untouched = [m for m in content if m not in skipped]
        if state is CoverageState.WITHHELD and untouched:
            skipped.update(untouched)
            degraded.append(
                Degradation(
                    scope=COVERAGE_WITHHELD,
                    kind=DegradationKind.COLLECTOR_FAILED,
                    reason=(
                        f"проаналізовані сторінки: {evidence.analysed_pages}; "
                        "на сайті видно живий вміст, якого ми не оглянули — "
                        "оцінку за прочитаним було б видано за оцінку сайту"
                    ),
                    reason_key="notice.coverage.withheld",
                    reason_params={
                        "pages": evidence.analysed_pages,
                        "access": evidence.access_failures,
                        "attempted": evidence.attempted,
                        "untried": evidence.untried_live,
                        "reasons": why,
                    },
                    affected_modules=untouched,
                )
            )
        elif state is CoverageState.LIMITED and untouched:
            # Бали лишаються: доказ достатній. Але читач мусить знати,
            # що ширшому оглядові щось матеріально завадило.
            partial.update(untouched)
            degraded.append(
                Degradation(
                    scope=COVERAGE_LIMITED,
                    kind=DegradationKind.PARTIAL_DATA,
                    reason=(
                        f"проаналізовані сторінки: {evidence.analysed_pages}; "
                        "ширшому оглядові завадили зовнішні обмеження"
                    ),
                    reason_key="notice.coverage.limited",
                    reason_params={
                        "pages": evidence.analysed_pages,
                        "access": evidence.access_failures,
                        "attempted": evidence.attempted,
                        "untried": evidence.untried_live,
                        "reasons": why,
                    },
                    affected_modules=untouched,
                )
            )

    if options.modules is not None:
        for module in Module:
            if module not in options.modules:
                skipped.add(module)
                degraded.append(
                    Degradation(
                        scope=module.value,
                        kind=DegradationKind.MODULE_EXCLUDED,
                        reason="модуль вимкнено в опціях аудиту",
                        reason_key="notice.module.excluded",
                        affected_modules=[module],
                    )
                )
        # Фільтр вирішує, що просили, а не що виміряно. Доступність досі
        # виходила звідси без жодної перевірки даних — і сотнею балів.
        _accessibility_under_filter(options.modules, performance, skipped, degraded)
    elif any(r.fetched for r in performance):
        _accessibility_coverage(performance, skipped, degraded)
    else:
        # PSI не відповів — доступності ми теж не міряли: вона приходить тим
        # самим запитом. Модуль виключається, а не отримує сто балів за те,
        # чого ніхто не перевіряв.
        skipped.add(Module.ACCESSIBILITY)

    # Швидкість — те саме: фільтр вирішує лише, чи її просили, а чи її
    # виміряно — дані, за одним правилом для аудиту з фільтром і без нього.
    if options.modules is None or Module.PERFORMANCE in options.modules:
        _performance_coverage(ctx, performance, skipped, partial, degraded)
    # Аналітика: буває, що знахідка є, а відповіді немає. Тоді модуль
    # неповний, і читач має бачити це поруч із балом.
    _analytics_coverage(ctx, skipped, partial, degraded)
    return skipped, partial


# Scope прогалини аналітики — код самого чека: прапорець неповноти
# виводиться з деградацій і в збереженому аудиті, за тим самим правилом.
ANALYTICS_CHECK = "tech.analytics"
# Скільки символів неоднозначного доказу йде в примітку. Назвати його
# вимагає стан NO_VERDICT + COMPLETE; возити туди весь журнал — ні.
_ANALYTICS_DETAIL_CAP = 200


def _analytics_coverage(
    ctx: SiteContext,
    skipped: set[Module],
    partial: set[Module],
    degraded: list[Degradation],
) -> None:
    """Невирішений висновок про аналітику: неповний модуль і одна прогалина.

    Два випадки, у яких знахідка є, а відповіді немає. Перший: вимірювання
    видно, вендора назвати не можна (`NO_VERDICT + COMPLETE`) — власний
    `/api/collect` кудись шле події, і сказати «аналітики немає» було б
    неправдою. Другий: сліду немає, але сторінки, які могли б показати
    лічильник після виконання скриптів, ми не рендерили (`FAIL + PARTIAL`).

    Бал модуля лишається в обох: чеки, що виконались, дали свій результат.
    Змінюється те, що поруч із балом стоїть неповнота — і рівно один запис
    про неї. Повторний виклик (перерахунок поверх тієї самої деградації)
    другого не додає.
    """
    if Module.TECH in skipped or not ctx.ok_pages:
        return
    if any(d.scope == ANALYTICS_CHECK for d in degraded):
        return
    state = ctx.analytics_classification()
    if not state.unresolved:
        return
    if state.unidentified:
        key = "notice.analytics.unidentified"
        detail = ", ".join(state.endpoints())[:_ANALYTICS_DETAIL_CAP] or state.kind.value
        reason = f"вимірювання без впізнаного вендора: {detail}"
    else:
        key = "notice.analytics.render_incomplete"
        rendered = sum(1 for page in ctx.ok_pages if ctx.was_rendered(page))
        detail = f"{rendered}/{len(ctx.ok_pages)}"
        reason = f"лічильника в розмітці немає; відрендерено сторінок: {detail}"
    partial.add(Module.TECH)
    degraded.append(
        Degradation(
            scope=ANALYTICS_CHECK,
            kind=DegradationKind.PARTIAL_DATA,
            reason=reason,
            reason_key=key,
            reason_params={"detail": detail},
            affected_modules=[Module.TECH],
        )
    )


def _performance_coverage(
    ctx: SiteContext,
    performance: list[Any],
    skipped: set[Module],
    partial: set[Module],
    degraded: list[Degradation],
) -> None:
    """Швидкість, яку просили, без відповіді провайдера — не звичайний бал.

    Правило одне для аудиту з фільтром модулів і без нього. Поки фільтр
    закінчував розбір раніше, ніж хтось питав про провайдера, швидкість без
    жодного його виміру оцінювалась без застереження: знімок
    schema1_small_site отримував 88 без позначки неповноти, а сторінка без
    власного часу відповіді — сотню за те, чого ніхто не міряв. Без фільтра
    той самий стан давав деградацію й неповний або виключений модуль.

    Провайдер, що впав винятком, уже записав це сам — у
    `_measure_performance`, разом із текстом винятку. Стан модуля
    вирішується так само, але другої деградації про ту саму подію немає:
    звіт показував би її двічі, вдруге — без причини.
    """
    if any(r.fetched for r in performance):
        return

    errors = "; ".join(str(r.error) for r in performance if r.error) or "немає відповіді"
    own_measurements = any(p.response_ms > 0 for p in ctx.ok_pages)
    if own_measurements:
        # Час відповіді сервера ми міряємо самі, тож модуль не порожній.
        # Але це не Core Web Vitals — оцінка неповна, і звіт має це сказати.
        partial.add(Module.PERFORMANCE)
        kind = DegradationKind.PARTIAL_DATA
        key = "notice.performance.no_vitals"
        reason = (
            f"Core Web Vitals не виміряно ({errors}). Оцінка побудована лише на часі "
            "відповіді сервера та статичних сигналах HTML."
        )
    else:
        skipped.add(Module.PERFORMANCE)
        kind = DegradationKind.PROVIDER_UNAVAILABLE
        key = "notice.performance.no_metrics"
        reason = f"провайдер не повернув метрики: {errors}"

    if any(
        d.scope == Module.PERFORMANCE.value and d.kind is DegradationKind.PROVIDER_UNAVAILABLE
        for d in degraded
    ):
        return
    degraded.append(
        Degradation(
            scope=Module.PERFORMANCE.value,
            kind=kind,
            reason=reason,
            reason_key=key,
            reason_params={"detail": errors},
            affected_modules=[Module.PERFORMANCE],
        )
    )


# Формулювання httpx/ssl для проблем саме з сертифікатом. DNS, таймаут і
# відмова в зʼєднанні сюди свідомо не входять: там аудитувати нічого.
_TLS_MARKERS = (
    "certificate_verify_failed",
    "certificate verify failed",
    "sslcertverificationerror",
    "ssl: ",
    "sslerror",
)


# Детектор, який судить відповідь семантичного шару: `llm.unstated_facts`
# читає `ctx.facts`, і без неї йому немає що судити. Оголошення про таку
# залежність у самих чеках немає, тому перелік живе поруч із шаром, що їх
# живить, а тест звіряє його з реєстром і з тим, які чеки справді читають
# відповідь моделі.
FACTS_CHECK = "llm.unstated_facts"
SEMANTIC_CHECKS: tuple[str, ...] = (FACTS_CHECK,)

# Scope деградації всього шару. Прогалина одного його кроку пишеться кодом
# детектора, який через неї не виконався.
SEMANTIC_LAYER = "llm"


def semantic_gaps(
    degraded: Iterable[Degradation], skipped: Collection[Module] = frozenset()
) -> set[Module]:
    """Модулі, оцінені без семантичного детектора.

    Модуль лишається в балі за тими чеками, що виконались, але бал
    неповний, і прапорець `partial` мусить казати те саме, що примітка
    поруч. Поки неповними вважались лише модулі з `PARTIAL_DATA`, звіт
    при вимкненому шарі казав `partial: false` і тут же — «бал модуля
    порахований на неповних даних».

    Вимкнений шар теж тут: вибір клієнта пояснює статус аудиту
    (`LAYER_DISABLED` не є збоєм), а не повноту бала. Виключений модуль
    неповним не буває — бала в нього немає. Правило одне на свіжий аудит
    і на збережений: другий виводить прапорець із тих самих деградацій
    при показі, без міграції.
    """
    return {
        module
        for d in degraded
        if (d.scope == SEMANTIC_LAYER or d.scope in SEMANTIC_CHECKS)
        and d.kind in (DegradationKind.LAYER_DISABLED, DegradationKind.PROVIDER_UNAVAILABLE)
        for module in d.affected_modules
        if module not in skipped
    }


async def _analyse_semantics(
    ctx: SiteContext, options: AuditOptions, degraded: list[Degradation]
) -> None:
    """Що модель зрозуміла зі сторінок. Єдина платна частина аудиту.

    Бюджет тут не оптимізація, а частина контракту: кожен виклик коштує
    грошей, і сайт на двадцять сторінок не має коштувати вдвадцятеро
    більше за сайт на одну.
    """
    budget = options.llm_max_pages or settings.llm_max_pages
    targets = _pages_worth_reading(ctx, budget)
    if not targets:
        return

    analyst = get_analyst(options.llm, options.llm_model)
    ctx.brief = await analyst.brief(
        ctx.origin, [(p.title or "", p.text) for p in targets]
    )
    if not ctx.brief.analysed:
        # Одна причина на весь аудит: якщо ключа немає, він не зʼявиться
        # на другій сторінці.
        degraded.append(
            Degradation(
                scope=SEMANTIC_LAYER,
                kind=(
                    DegradationKind.LAYER_DISABLED
                    if ctx.brief.disabled
                    else DegradationKind.PROVIDER_UNAVAILABLE
                ),
                reason=f"семантичного аналізу не було: {ctx.brief.error}",
                reason_key=(
                    "notice.llm.disabled"
                    if ctx.brief.disabled
                    else "notice.llm.unavailable"
                ),
                # `checks` — детектори, які через це не виконались: лише
                # ідентифікатори з реєстру, жодного тексту провайдера.
                reason_params={"detail": ctx.brief.error, "checks": sorted(SEMANTIC_CHECKS)},
                affected_modules=[Module.LLM_VISIBILITY],
            )
        )
        return

    # Фактам дається окремий, більший бюджет. Виклик тут один незалежно
    # від кількості сторінок, тож платимо за токени, а не за виклики — а
    # висновок «цього немає ніде» тим чесніший, чим більше ми прочитали.
    # На бюджеті у три сторінки stripe.com отримував «немає цін»: сторінка
    # з цінами просто не потрапляла у вибірку.
    ctx.facts = await analyst.facts(
        ctx.origin,
        [(p.url, p.title or "", p.text) for p in _pages_worth_reading(ctx, FACTS_MAX_PAGES)],
    )
    if not ctx.facts.analysed:
        # Бриф вийшов, факти — ні. Шар працює, тож «аналізу не було» тут
        # неправда: не виконався один детектор, і деградація названа ним,
        # а не шаром, — про решту модуля вона не каже нічого. Причина та
        # сама, що в брифа без відповіді, тож і вид той самий. Текст
        # помилки провайдера сюди не йде: аналітик уже записав його в
        # журнал, а звіт отримує лише ідентифікатор детектора.
        degraded.append(
            Degradation(
                scope=FACTS_CHECK,
                kind=DegradationKind.PROVIDER_UNAVAILABLE,
                reason=(
                    "семантичний аналіз не повернув фактів про бізнес: "
                    f"{FACTS_CHECK} не виконано"
                ),
                reason_key="notice.llm.facts_unavailable",
                reason_params={"checks": [FACTS_CHECK]},
                affected_modules=[Module.LLM_VISIBILITY],
            )
        )


# Сторінки, на яких компанії зазвичай і пишуть, хто вони й як з ними
# звʼязатися. Порядок краулу тут не годиться: у бюджет на три сторінки
# /contact не потрапляє майже ніколи, і висновок «контактів немає» вийшов
# би властивістю нашої вибірки, а не сайту.
FACTS_MAX_PAGES = 12

# Скільки адрес із карти сайту підкидаємо краулеру.
SITEMAP_SEEDS = 50
# Скільки місць у засіві гарантовано віддаємо службовим сторінкам.
TELLING_SEEDS = 15
# І скільки з них максимум з одного розділу.
SEEDS_PER_SECTION = 3


def _few_per_section(urls: list[str], per_section: int) -> list[str]:
    """Рівномірно з кожного розділу, а не всі з найбільшого."""
    by_section: dict[str, list[str]] = {}
    for url in urls:
        section = (urlparse(url).path.strip("/").split("/") or [""])[0]
        by_section.setdefault(section, []).append(url)
    picked: list[str] = []
    for group in by_section.values():
        picked += _spread_pick(group, min(per_section, len(group)))
    return picked


def _seed_from_sitemap(urls: list[str]) -> list[str]:
    """Засів із карти за видом сторінки, а не за позицією в файлі.

    Рівний крок тут не працює: на furniturerow.com сторінки магазинів —
    півтора відсотка карти, і вибірка з пʼятдесяти не ловила жодної.
    А саме на них лежать адреса, години й geo, тобто відповідь на «хто
    робить це в моєму місті».

    Тому службовим сторінкам віддано частину місць окремо, а решта
    добирається рівномірно по всій карті — щоб засів лишався
    представницьким, а не з одного розділу.
    """
    if len(urls) <= SITEMAP_SEEDS:
        return list(urls)

    # Не більше кількох з одного розділу: мережа має триста сторінок
    # магазинів, і взяти чотирнадцять означало б віддати їм увесь бюджет
    # краулу. Дві-три доводять шаблон так само добре.
    telling = _few_per_section(
        [u for u in urls if kind_of(u) is PageKind.TELLING], SEEDS_PER_SECTION
    )
    picked: list[str] = _spread_pick(telling, min(TELLING_SEEDS, len(telling)))

    # Решту добираємо рівномірно з того, що ще не взяли. Саме «з решти»:
    # розтягнути вибірку по всій карті й потім обрізати її початком — це
    # те саме обрізання за позицією, лише двома кроками.
    seen = set(picked)
    rest = [u for u in urls if u not in seen]
    picked += _spread_pick(rest, SITEMAP_SEEDS - len(picked))
    return picked


def _spread_pick(urls: list[str], count: int) -> list[str]:
    """Рівномірна вибірка по всій довжині, а не її початок."""
    if count <= 0:
        return []
    if len(urls) <= count:
        return list(urls)
    step = len(urls) / count
    return [urls[int(i * step)] for i in range(count)]


def _pages_worth_reading(ctx: SiteContext, budget: int) -> list[PageSignals]:
    """Головна плюс сторінки, де факти про компанію лежать за звичаєм."""
    pages = [p for p in ctx.content_pages if kind_of(p.url) is not PageKind.BOILERPLATE]
    if not pages:
        return []

    home = ctx.home
    picked: list[PageSignals] = []
    seen: set[str] = set()

    def take(page: PageSignals) -> None:
        if page.url not in seen:
            seen.add(page.url)
            picked.append(page)

    if home is not None and home in pages:
        take(home)

    def telling(page: PageSignals) -> bool:
        return kind_of(page.url, page.title or "") is PageKind.TELLING

    for wanted in (True, False):
        for page in pages:
            if len(picked) >= budget:
                return picked
            if telling(page) is wanted:
                take(page)
    return picked


def _render_targets(ctx: SiteContext, budget: int) -> list[PageSignals]:
    """Кого саме відкривати в браузері в межах бюджету.

    За порядком краулу — і обовʼязково одну сторінку, яка щось продає.
    Питання «чи видно вміст без JS» найдорожче коштує саме там, а до
    вибірки за порядком комерційні сторінки не потрапляли зовсім: на
    ka-dent.com.ua з вісьмох сторінок послуг у рендер не пішла жодна.
    """
    if budget <= 0:
        return []
    # Уже відрендерене пропускаємо: хвиля друга має дивитись на нове, а
    # не переплачувати за ту саму сторінку.
    fresh = [page for page in ctx.ok_pages if page.url not in ctx.renders]
    chosen = fresh[:budget]
    if not chosen or any(ctx.type_of(page) in SELLS_SOMETHING for page in chosen):
        return chosen
    seller = next((page for page in fresh if ctx.type_of(page) in SELLS_SOMETHING), None)
    return chosen if seller is None else [*chosen[:-1], seller]


# Скільки разів поспіль ми готові рендерити знайдене й шукати далі.
# Не бюджет, а запобіжник: бюджети — це сторінки й рендери, а ця межа
# існує лише на випадок, коли обидва чомусь не вичерпуються.
MAX_DISCOVERY_WAVES = 5


def _absorb(
    ctx: SiteContext, entry_url: str, pages: list[PageSignals], failed: dict[str, str]
) -> None:
    """Долучає результат хвилі краулу до контексту.

    Логічні сторінки, а не адреси. Краулер бачить URL, сайт має сторінки:
    `site` і `site/` — одна, варіанти форми з різним ?subject — теж одна.
    Без цього кроку один нормальний патерн давав три різні претензії:
    дубль title, «немає в карті» і canonical.

    Групування щоразу проганяється по всьому набору, а не по новому
    шматку: сторінка з другої хвилі може виявитись варіантом сторінки з
    першої, і побачити це можна лише разом.
    """
    ctx.raw_pages.extend(pages)
    ctx.pages = _ordered(group_logical_pages(ctx.raw_pages), entry_url)
    ctx.urls_crawled = len(ctx.raw_pages)
    ctx.failed_urls = {**ctx.failed_urls, **failed}


def _links_only_after_render(ctx: SiteContext, frontier: Frontier) -> int:
    """Адреси з DOM, яких не було у відповіді, — у спільну чергу.

    Порівняння береться готове з `render_diff`: другого компаратора
    HTML проти DOM у продукті бути не повинно, інакше відкриття й
    знахідка `seo.render_delta` розійдуться в показаннях.

    `comparable=False` — це не «нових посилань немає», а «порівнювати не
    було чим». Рендер вимкнено, браузер не піднявся, сторінка зависла —
    у всіх цих випадках ми мовчимо, а не робимо висновок.
    """
    admitted = 0
    depths = {normalize(p.url): p.depth for p in ctx.ok_pages}
    for diff in render_diff.compare_all(ctx):
        if not diff.comparable:
            continue
        depth = depths.get(normalize(diff.url), 0) + 1
        for url in diff.links.only_after_render:
            if frontier.offer(url, depth, source=Source.RENDER):
                admitted += 1
    return admitted


async def _render_and_discover(
    ctx: SiteContext,
    options: AuditOptions,
    degraded: list[Degradation],
    *,
    fetcher: Fetcher,
    frontier: Frontier,
    entry_url: str,
    max_pages: int,
    max_depth: int,
    on_progress: ProgressReporter | None = None,
) -> None:
    """Рендер і краул хвилями, поки хоч один бюджет лишає місце.

    ## Навіщо хвилі

    Один прохід «відрендерили, поставили знайдене в чергу, спинились»
    відкриває рівно один шар. У SPA другий шар — звичайна річ: оболонка
    показує список, сторінка списку домальовує картки. Тому хвиля
    повторюється: відрендерили нове → знайшли нове → прочитали нове.

    ## Чим це обмежено

    Нічим новим. Бюджет сторінок один на весь аудит: сторінки, знайдені
    після рендеру, витрачають ті самі `max_pages`. Бюджет рендерів теж
    один і теж прямує до нуля — саме він природно й спиняє цикл на
    статичному сайті, де рендерити треба всі перші сторінки, і саме він
    лишає паливо на SPA, де перша хвиля має рівно одну сторінку.
    `MAX_DISCOVERY_WAVES` — запобіжник поверх двох бюджетів.
    """
    budget = options.render_max_pages or settings.render_max_pages
    renderer = get_renderer(options.render)
    try:
        for _wave in range(MAX_DISCOVERY_WAVES):
            room = budget - len(ctx.renders)
            targets = _render_targets(ctx, room)
            if not targets:
                return
            if not await _render_batch(ctx, targets, renderer, degraded):
                # Браузера немає. Друга спроба його не поверне, і
                # висновків про JS-посилання ми не робимо.
                return

            if len(ctx.raw_pages) >= max_pages:
                return
            if not _links_only_after_render(ctx, frontier):
                return

            pages, failed = await crawl(
                fetcher,
                entry_url,
                ctx.origin,
                max_pages=max_pages - len(ctx.raw_pages),
                max_depth=max_depth,
                frontier=frontier,
                on_progress=_shifted(on_progress, len(ctx.raw_pages)),
            )
            if not pages:
                return
            _absorb(ctx, entry_url, pages, failed)
            ctx.redirect_limited = sorted(frontier.redirect_limited)
    finally:
        await renderer.aclose()


async def _render_pages(
    ctx: SiteContext, options: AuditOptions, degraded: list[Degradation]
) -> None:
    """Один прохід рендеру, без відкриття нових адрес.

    Рендер і відкриття — різні речі, і розділені вони навмисно. Відкриття
    потребує живого fetcher'а й черги; сам рендер не потребує нічого, крім
    браузера, і саме в такому вигляді його зручно перевіряти. Хвильовий
    прохід складається з цього ж кроку, викликаного кілька разів.
    """
    targets = _render_targets(ctx, options.render_max_pages or settings.render_max_pages)
    if not targets:
        return
    renderer = get_renderer(options.render)
    try:
        await _render_batch(ctx, targets, renderer, degraded)
    finally:
        await renderer.aclose()


async def _render_batch(
    ctx: SiteContext,
    targets: list[PageSignals],
    renderer: Renderer,
    degraded: list[Degradation],
) -> bool:
    """Рендерить перелік. `False` — браузера немає, продовжувати марно."""
    for page in targets:
        result = await renderer.render(page.url)
        if result.rendered:
            result.signals = signals_from_html(
                page.url, result.html, origin=ctx.origin, depth=page.depth
            )
            # Три джерела про лічильники: розмітка після рендеру,
            # глобальні обʼєкти сторінки й адреси її запитів. Жодного
            # не досить окремо — див. коментарі біля кожного.
            #
            # Ідентифікатори префіксовані (`global:` від рендерера,
            # `request:` тут), бо саме в цьому полі вони змішуються. Голий
            # рядок у знімку завдяки цьому однозначно означає старий аудит,
            # і класифікатор читає його як спадщину, а не як свіжий доказ.
            result.runtime_analytics = sorted(
                set(result.runtime_analytics)
                | {
                    f"{analytics_vendors.REQUEST_PREFIX}{vendor}"
                    for vendor in vendors_in_urls(result.requests)
                }
            )
        ctx.renders[page.url] = result
        if not result.rendered:
            # Одна причина на весь аудит, а не по разу на сторінку:
            # якщо браузера немає, він не зʼявиться на другій.
            degraded.append(
                Degradation(
                    scope="render",
                    kind=(
                        DegradationKind.LAYER_DISABLED
                        if result.disabled
                        else DegradationKind.PROVIDER_UNAVAILABLE
                    ),
                    reason=f"сторінки не відрендерено: {result.error}",
                    reason_key=(
                        "notice.render.disabled"
                        if result.disabled
                        else "notice.render.failed"
                    ),
                    reason_params={"detail": result.error},
                    affected_modules=[Module.LLM_VISIBILITY],
                )
            )
            return False
    return True


def _has_internal_links(ctx: SiteContext) -> bool:
    """Чи вело зі сторінки хоч кудись у межах сайту.

    Питання тут те саме, що ставить краул: чи існувала навігація далі.
    Тому й доказ мусить бути той самий — модель посилань краулера
    включає і те, що віддав сервер, і те, що зʼявилося після рендеру
    (`_links_only_after_render` ставить другі в ту саму чергу).

    Поки перевірялися лише статичні посилання, шість сайтів night2 з
    навігацією винятково після рендеру не позначались як `shallow`:
    `cbu.edu.tr` мав 60 внутрішніх посилань у DOM і жодного у відповіді.
    Бала це не зачіпало — гейт ставить лише `partial`, — але стан
    покриття виходив фактично неправильним: «одна сторінка й іти було
    нікуди» замість «одна сторінка, хоча йти було куди».

    Обʼєднання, а не заміна: рендер буває невдалим, і тоді `as_seen`
    віддає статичну сторінку; а скрипт буває таким, що прибирає
    посилання з DOM. Обидва представлення бачив краул — обидва й
    питаємо.
    """
    for page in ctx.ok_pages:
        for source in (page, ctx.as_seen(page)):
            if any(link.is_internal for link in source.links):
                return True
    return False


def _is_tls_error(error: str) -> bool:
    lowered = error.lower()
    return any(marker in lowered for marker in _TLS_MARKERS)


def _ordered(pages: list[PageSignals], entry_url: str) -> list[PageSignals]:
    """Точка входу має бути ctx.home, навіть якщо краулер повернув її не першою."""
    target = entry_url.rstrip("/")
    entry = [p for p in pages if p.url.rstrip("/") == target]
    entry_ids = {id(p) for p in entry}
    rest = [p for p in pages if id(p) not in entry_ids]
    return entry + rest


async def _measure_performance(
    url: str, options: AuditOptions, degraded: list[Degradation]
) -> list[Any]:
    if options.modules is not None and Module.PERFORMANCE not in options.modules:
        return []
    provider = get_provider(options.perf_provider)
    try:
        return list(
            await asyncio.gather(*(provider.measure(url, s) for s in options.strategies))
        )
    except Exception as exc:  # noqa: BLE001 — провайдер не має валити весь аудит
        log.warning("performance_failed", url=url, error=str(exc))
        degraded.append(
            Degradation(
                scope=Module.PERFORMANCE.value,
                kind=DegradationKind.PROVIDER_UNAVAILABLE,
                # Текст винятку лишається в `reason` як технічний слід і
                # не йде в переклад: він англійський, машинний і мінятиме
                # формулювання разом із бібліотекою. Клієнту призначений
                # ключ, який каже, що саме не виміряли.
                reason=str(exc),
                reason_key="notice.performance.partial",
                reason_params={"detail": str(exc)},
                affected_modules=[Module.PERFORMANCE],
            )
        )
        return []


def _run_checks(
    ctx: SiteContext, modules: set[Module] | None, degraded: list[Degradation]
) -> list[Issue]:
    issues: list[Issue] = []
    for check in all_checks(modules):
        try:
            issues.extend(check.run(ctx))
        except Exception as exc:  # noqa: BLE001 — один зламаний чек не валить аудит
            log.warning("check_failed", check=check.code, error=str(exc), exc_info=True)
            degraded.append(
                Degradation(
                    scope=check.code,
                    kind=DegradationKind.CHECK_FAILED,
                    reason=str(exc),
                    reason_key="notice.check.failed",
                    affected_modules=[check.module],
                )
            )
    return issues


def rescore(ctx: SiteContext, options: AuditOptions | None = None) -> AuditOutcome:
    """Прогін чеків і скорингу по вже зібраних даних. Без мережі.

    Те саме, що робить `run_audit` після краулу, — і рівно те, чого досі
    бракувало: перерахувати старий аудит за новими правилами. Без цього
    кожна зміна ваг чи чека відрізає нас від усього, що пораховано
    раніше, бо єдиний спосіб оновити число — прокраулити сайт ще раз,
    тобто вже інший сайт.

    Похідні дані рахуються заново навмисно: `known` і `links` виводяться
    зі сторінок, тож нова версія коду має отримати їх за новими
    правилами, а не дістати законсервованими.
    """
    options = options or AuditOptions()
    degraded: list[Degradation] = []
    ctx.known = collect_site_facts(ctx)
    ctx.links = build_link_graph(ctx)

    skipped, partial = _module_coverage(options, ctx, ctx.performance, degraded)
    issues = _stamp_importance(
        _temper_by_coverage(_run_checks(ctx, options.modules, degraded), ctx), ctx
    )
    overall, scores = compute_scores_safe(issues, skipped)
    return AuditOutcome(
        context=ctx,
        issues=issues,
        scores=scores,
        overall=overall,
        degraded=degraded,
        skipped_modules=skipped,
        partial_modules=partial,
        versions=audit_versions(options, None),
    )


def _stamp_importance(issues: list[Issue], ctx: SiteContext) -> list[Issue]:
    """Записує в докази, наскільки важлива сторінка знахідки за версією сайту.

    Пріоритезація у звіті досі рахувала знахідку на головній і на забутій
    сторінці третього рівня однаково, хоча коштують вони клієнту різного.
    Число лягає в `evidence`, а не в окреме поле: воно там і зберігається
    разом з рештою доказів, і переживає перебудову звіту з бази.
    """
    graph = ctx.links
    if graph is None:
        return issues
    by_url = {page.url: page for page in ctx.ok_pages}
    for issue in issues:
        page = by_url.get(issue.page_url or "")
        if page is not None:
            issue.evidence.setdefault("page_importance", graph.importance(page))
    return issues


def compute_scores_safe(
    issues: list[Issue], skipped: set[Module]
) -> tuple[int | None, dict[str, int]]:
    from app.audit.scoring import compute_scores

    return compute_scores(issues, skipped_modules=skipped)


async def _safe(coro: Any, label: str, degraded: list[Degradation]) -> Any:
    try:
        return await coro
    except Exception as exc:  # noqa: BLE001
        log.warning("collector_failed", collector=label, error=str(exc))
        degraded.append(
            Degradation(
                scope=label,
                kind=DegradationKind.COLLECTOR_FAILED,
                reason=str(exc),
                reason_key="notice.layer.failed",
                affected_modules=COLLECTOR_MODULES.get(label, []),
            )
        )
        return None


__all__ = ["AuditOptions", "AuditOutcome", "run_audit"]
