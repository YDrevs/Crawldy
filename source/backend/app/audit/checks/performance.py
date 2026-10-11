"""Чеки швидкості: пороги Core Web Vitals + статичні евристики з HTML."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.audit.checks.base import Check, register
from app.audit.performance.base import THRESHOLDS
from app.audit.types import (
    Confidence,
    Effort,
    Issue,
    Module,
    Severity,
    SiteContext,
    Strategy,
)
from app.core.config import settings

CWV_METRICS = ("LCP", "INP", "CLS", "TTFB", "TBT")

# Справжніх Core Web Vitals три. TTFB і TBT — діагностика: вони
# пояснюють, чому погані перші три, але самі нічого не переживає
# користувач. Тільки ці три можуть бути критичними.
CORE_VITALS = frozenset({"LCP", "INP", "CLS"})


def _grade(metric: str, rating: str | None) -> Severity:
    """Критичною може бути лише метрика, яку переживає користувач.

    TBT і TTFB діагностичні, і на вибірці саме вони роздавали
    «критично»: усі дванадцять критичних TBT — лабораторні, тобто
    симуляція під штучним тротлінгом, тоді як INP тих самих сайтів,
    виміряний на живих людях, не був критичним жодного разу.
    """
    if rating != "poor":
        return Severity.MEDIUM
    return Severity.CRITICAL if metric in CORE_VITALS else Severity.HIGH


@register
class CoreWebVitalsCheck(Check):
    code = "perf.core_web_vitals"
    module = Module.PERFORMANCE
    severity = Severity.HIGH
    weight = 4
    effort = Effort.HIGH
    # FCP свідомо не в CWV_METRICS: додати його — це зміна скорингу,
    # а не переклад. Тому й ключа для нього в каталозі немає.
    messages = tuple(f"perf.core_web_vitals.{m.lower()}" for m in CWV_METRICS)
    variants = tuple(m.lower() for m in CWV_METRICS)

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Тільки одна стратегія, і це мобільна: інакше та сама повільність
        # дає дві знахідки — окремо для телефона й для комп'ютера — і
        # штраф подвоюється за одну проблему. Розрив між пристроями
        # повідомляє окремий чек.
        result = ctx.primary_performance()
        if result is not None:
            for metric in CWV_METRICS:
                value = result.metric(metric)
                if value is None or value.value is None or value.rating == "good":
                    continue
                # TBT — лабораторне наближення до INP. Коли INP виміряний
                # на живих користувачах, наближення зайве: воно каже про
                # те саме, лише гірше. На вибірці воно ще й суперечило —
                # дванадцять «критичних» TBT проти жодного критичного INP
                # на тих самих сайтах.
                if metric == "TBT" and "INP" in result.field_data:
                    continue
                good, _ = THRESHOLDS[metric]
                value_text, unit = _for_reading(value.value, value.unit)
                yield self.issue(
                    key=metric.lower(),
                    msg=f"perf.core_web_vitals.{metric.lower()}",
                    params={
                        "value": value_text,
                        "unit": unit,
                        "strategy": result.strategy.value,
                        # У шаблоні поріг ділить одиницю зі значенням
                        # ({threshold}{unit}), тож і масштаб мусить бути
                        # той самий: «4.1 s … поріг 2500 s» стверджував
                        # неправду, помиляючись у тисячу разів.
                        "threshold": _in_unit_of(good, unit),
                    },
                    evidence={
                        "metric": metric,
                        "value": round(value.value, 3),
                        "threshold_good": good,
                        "rating": value.rating,
                        "strategy": result.strategy.value,
                        "source": "field" if metric in result.field_data else "lab",
                        "provider": result.provider,
                    },
                    severity=_grade(metric, value.rating),
                    confidence=(
                        Confidence.HIGH
                        if metric in result.field_data
                        else Confidence.MEDIUM
                    ),
                    page_url=result.url,
                )


def _for_reading(value: float, unit: str) -> tuple[str, str]:
    """Метрика так, як її вимовляють, а не як її віддав провайдер.

    `LCP = 4126.042ms` — це дамп, а не речення для клієнта: три знаки
    після коми обіцяють точність до мікросекунди там, де сама величина
    гуляє на сотні мілісекунд між вимірюваннями. Секунди читаються
    швидше за чотиризначні мілісекунди, тому від 1000 мс переходимо на
    них.

    Точне значення нікуди не зникає — воно лишається в `evidence`, де
    йому й місце: доказ має бути точним, заголовок — зрозумілим.

    Одиниця повертається з нерозривним пробілом: число, відірване від
    своєї одиниці переносом рядка, читається як інше число.
    """
    if unit == "ms":
        if value >= 1000:
            return f"{value / 1000:.1f}", " s"
        return f"{value:.0f}", " ms"
    if not unit:
        # CLS безрозмірний: `:g` прибирає хвіст нулів, лишаючи 0.25 і 0.1.
        return f"{round(value, 3):g}", ""
    return f"{round(value, 3):g}", f" {unit}"


def _in_unit_of(threshold: float, unit: str) -> str:
    """Поріг у тій самій одиниці, яку `_for_reading` обрала для значення."""
    if unit == " s":
        return f"{threshold / 1000:g}"
    return f"{threshold:g}"


@register
class PerformanceScoreCheck(Check):
    """Агрегат Lighthouse — контекст і список можливостей, а не окремий дефект.

    Штрафу немає свідомо. Lighthouse-скор обчислюється з тих самих LCP,
    TBT і CLS, які вже перевіряють окремі чеки: на вибірці зі 114 сайтів
    82 з 84 спрацювань цього чека супроводжувались знахідками по
    конкретних метриках. Вага 3 при severity HIGH означала, що за ту саму
    повільність сайт карали двічі.

    Знахідка лишається, бо несе те, чого немає більше ніде: top_opportunities
    із оцінкою економії в мілісекундах — конкретні дії, а не діагноз.
    """

    code = "perf.lighthouse_score"
    module = Module.PERFORMANCE
    severity = Severity.INFO
    weight = 0
    effort = Effort.HIGH

    BELOW_TYPICAL = 75

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        result = ctx.primary_performance()
        if result is None:
            return
        score = result.lighthouse_score
        if score is None or score >= self.BELOW_TYPICAL:
            return
        yield self.issue(
            # Lighthouse віддає 63.0 — дріб тут не несе інформації,
            # шкала цілочислова.
            params={"score": round(score), "strategy": result.strategy.value},
            evidence={"score": score, "top_opportunities": result.opportunities[:5]},
            page_url=result.url,
        )


@register
class MobileGapCheck(Check):
    """Сайт швидкий на комп'ютері й повільний на телефоні.

    Найкоштовніший вид повільності, і водночас найлегший, щоб його не
    помітити: власник дивиться на свій сайт із робочого ноутбука й
    бачить, що все добре. Google ранжує за мобільною версією, і
    більшість відвідувачів приходить звідти ж.

    Спрацьовує лише коли десктоп справді добрий: якщо повільно всюди,
    це вже сказали чеки Core Web Vitals, і дублювати їх нема сенсу.
    """

    code = "perf.mobile_gap"
    module = Module.PERFORMANCE
    severity = Severity.HIGH
    weight = 3
    effort = Effort.HIGH

    # Наскільки мобільний Lighthouse має відставати, щоб це була
    # проблема пристрою, а не загальна повільність сайту.
    MIN_GAP = 25
    DESKTOP_IS_FINE = 70

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        mobile = ctx.performance_for(Strategy.MOBILE)
        desktop = ctx.performance_for(Strategy.DESKTOP)
        if mobile is None or desktop is None:
            return
        if mobile.lighthouse_score is None or desktop.lighthouse_score is None:
            return
        gap = desktop.lighthouse_score - mobile.lighthouse_score
        if desktop.lighthouse_score < self.DESKTOP_IS_FINE or gap < self.MIN_GAP:
            return

        yield self.issue(
            params={
                "mobile": round(mobile.lighthouse_score),
                "desktop": round(desktop.lighthouse_score),
            },
            evidence={
                "mobile_score": mobile.lighthouse_score,
                "desktop_score": desktop.lighthouse_score,
                "gap": round(gap, 1),
                "worst_on_mobile": _worst_metrics(mobile, desktop),
            },
            page_url=mobile.url,
        )


def _worst_metrics(mobile: Any, desktop: Any) -> list[dict[str, Any]]:
    """Метрики, які на телефоні гірші за десктопні більш ніж удвічі."""
    worse = []
    for name in CWV_METRICS:
        on_phone = mobile.metric(name)
        on_desktop = desktop.metric(name)
        if on_phone is None or on_desktop is None:
            continue
        if on_phone.value is None or not on_desktop.value:
            continue
        if on_phone.value > on_desktop.value * 2:
            worse.append(
                {
                    "metric": name,
                    "mobile": round(on_phone.value, 3),
                    "desktop": round(on_desktop.value, 3),
                }
            )
    return worse


@register
class ServerResponseCheck(Check):
    """TTFB із власних вимірювань краулера.

    Fetcher і так заміряє час відповіді на кожній сторінці. Це єдиний
    сигнал швидкості, який не залежить від зовнішнього провайдера, тож
    саме він тримає модуль живим, коли PSI недоступний.
    """

    code = "perf.server_response"
    module = Module.PERFORMANCE
    severity = Severity.MEDIUM
    weight = 3
    effort = Effort.HIGH
    messages = ("perf.server_response.slow", "perf.server_response.very_slow")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        measured = [p for p in ctx.ok_pages if p.response_ms > 0]
        if not measured:
            return
        good, poor = THRESHOLDS["TTFB"]
        slowest = max(measured, key=lambda p: p.response_ms)
        median = _median(sorted(p.response_ms for p in measured))
        if median <= good:
            return

        very_slow = median > poor
        yield self.issue(
            msg="perf.server_response.very_slow" if very_slow else "perf.server_response.slow",
            params={"median": median, "threshold": int(good)},
            evidence={
                "median_ms": median,
                "slowest_ms": slowest.response_ms,
                "slowest_url": slowest.url,
                "pages_measured": len(measured),
                "threshold_good_ms": int(good),
                "source": "crawler",
            },
            severity=Severity.HIGH if very_slow else Severity.MEDIUM,
        )


def _median(values: list[int]) -> int:
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return (values[middle - 1] + values[middle]) // 2


@register
class PerformanceUnavailableCheck(Check):
    code = "perf.unavailable"
    module = Module.PERFORMANCE
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        failed = [r for r in ctx.performance if not r.fetched]
        if failed and len(failed) == len(ctx.performance):
            yield self.issue(evidence={"errors": [r.error for r in failed][:3]})


@register
class RenderBlockingCheck(Check):
    code = "perf.render_blocking"
    module = Module.PERFORMANCE
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.MEDIUM

    # Кілька блокуючих ресурсів має майже кожен сайт (80% вибірки), тож
    # поріг 3 нічого не розрізняв. І якщо LCP виміряний і добрий, блокування
    # ні на що не вплинуло — рахуватися має вимірювання, а не підрахунок.
    THRESHOLD = 8

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        if ctx.measured_rating("LCP") == "good":
            return
        for page in ctx.ok_pages:
            total = page.render_blocking_scripts + page.render_blocking_styles
            if total >= self.THRESHOLD:
                yield self.issue(
                    params={"count": total},
                    evidence={
                        "scripts": page.render_blocking_scripts,
                        "styles": page.render_blocking_styles,
                    },
                    page_url=page.url,
                )


@register
class ExternalFontsCheck(Check):
    code = "perf.external_fonts"
    module = Module.PERFORMANCE
    severity = Severity.LOW
    weight = 2
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        hosts = sorted({h for page in ctx.ok_pages for h in page.font_hosts})
        if hosts:
            yield self.issue(
                params={"hosts": ", ".join(hosts)},
                evidence={"hosts": hosts},
            )


@register
class ThirdPartyCheck(Check):
    code = "perf.third_party"
    module = Module.PERFORMANCE
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.MEDIUM
    messages = ("perf.third_party", "perf.third_party.weight")

    # Поодинокі зовнішні хости — норма; проблема починається з кількості.
    # Поріг лишається для сайтів, які не рендерились.
    THRESHOLD = 8
    # Частка ваги сторінки, віддана чужому коду, вище якої це вже не
    # «кілька віджетів», а залежність швидкості від чужих серверів.
    HEAVY_SHARE = 0.4
    # Нижче цього рахувати частки безглуздо: на легкій сторінці навіть
    # один шрифт дає більшість байтів.
    MEANINGFUL_BYTES = 200_000

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        home = ctx.home
        if home is None:
            return

        measured = ctx.third_party_weight()
        if measured is not None:
            third_party, total, top = measured
            share = third_party / total if total else 0.0
            if total >= self.MEANINGFUL_BYTES and share >= self.HEAVY_SHARE:
                yield self.issue(
                    msg="perf.third_party.weight",
                    params={"share": f"{share:.0%}", "kb": third_party // 1024},
                    evidence={
                        "third_party_kb": third_party // 1024,
                        "total_kb": total // 1024,
                        "share": round(share, 2),
                        "heaviest": [{"host": h, "kb": b // 1024} for h, b in top[:5]],
                        "measured": True,
                    },
                    page_url=home.url,
                )
            return

        # Без рендеру лишається рахувати хости в розмітці.
        hosts = home.third_party_hosts
        if len(hosts) >= self.THRESHOLD:
            yield self.issue(
                msg="perf.third_party",
                params={"count": len(hosts)},
                evidence={"hosts": hosts[:15], "threshold": self.THRESHOLD},
                page_url=home.url,
            )


# Формати, для яких `srcset` має сенс. Вектор масштабується сам, тож
# просити для нього набір розмірів — просити зайвого.
RASTER_FORMATS = ("jpg", "jpeg", "png", "webp", "avif", "gif")


@register
class ResponsiveImagesCheck(Check):
    """Багато растрових зображень і жодного набору розмірів.

    Рахуються лише растрові. Поки рахувались усі, чек спрацьовував на
    23 сайтах із 29 — тобто не розрізняв нікого, — і найгучніше на тих,
    хто робить правильно: на головній ahrefs.com зі 133 зображень 120 це
    SVG, якому `srcset` не потрібен за визначенням. Ми карали сайт за
    векторні іконки.
    """

    code = "perf.responsive_images"
    module = Module.PERFORMANCE
    severity = Severity.LOW
    weight = 1
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            raster = sum(page.images_by_format.get(fmt, 0) for fmt in RASTER_FORMATS)
            if raster >= 5 and page.images_with_srcset == 0:
                yield self.issue(
                    params={"count": raster},
                    evidence={
                        "raster_images": raster,
                        "images_total": page.images_total,
                        "with_srcset": 0,
                        "by_format": dict(page.images_by_format),
                    },
                    page_url=page.url,
                )


@register
class ImageOptimizationCheck(Check):
    code = "perf.images"
    module = Module.PERFORMANCE
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.MEDIUM
    messages = (
        "perf.images.legacy_format",
        "perf.images.no_dimensions",
        "perf.images.no_lazy",
    )
    variants = ("legacy_format", "no_dimensions", "no_lazy")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            if page.images_total < 3:
                continue
            legacy = sum(page.images_by_format.get(f, 0) for f in ("jpg", "png", "gif"))
            modern = sum(page.images_by_format.get(f, 0) for f in ("webp", "avif"))
            if legacy and modern == 0:
                yield self.issue(
                    key="legacy_format",
                    msg="perf.images.legacy_format",
                    params={"count": legacy},
                    evidence={"by_format": page.images_by_format},
                    severity=Severity.LOW,
                    page_url=page.url,
                )
            # Розміри зображень — передвісник CLS. Якщо CLS виміряний і
            # добрий, передвісник не спрацював: карати нема за що.
            if page.images_without_dimensions >= 3 and ctx.measured_rating("CLS") != "good":
                yield self.issue(
                    key="no_dimensions",
                    msg="perf.images.no_dimensions",
                    params={"count": page.images_without_dimensions},
                    evidence={
                        "without_dimensions": page.images_without_dimensions,
                        "measured_cls": ctx.measured_rating("CLS") or "не вимірювався",
                    },
                    page_url=page.url,
                )
            if page.images_total >= 8 and page.lazy_images == 0:
                yield self.issue(
                    key="no_lazy",
                    msg="perf.images.no_lazy",
                    evidence={"images": page.images_total},
                    severity=Severity.LOW,
                    page_url=page.url,
                )


# Скільки важить розмітка сторінки, перш ніж це стає проблемою саме по
# собі. Звичайна сторінка — десятки або сотні кілобайт; мегабайт HTML
# без картинок і скриптів означає, що в документ потрапило те, чого там
# бути не мало.
HEAVY_HTML_BYTES = 2 * 1024 * 1024


@register
class PageWeightCheck(Check):
    """Сторінка, розмітка якої не має права стільки важити.

    Знайдено на myfriendlythai.ca: головна сторінка ресторану впиралася
    в нашу межу завантаження — пʼять мегабайтів — і містила 111 тисяч
    слів. У тексті виявились тисячі спам-коментарів із чужими адресами
    й посиланнями. Аудит прочитав це й не сказав ані слова.

    Чек не стверджує, що сайт зламали: довести це з розмітки не можна.
    Він стверджує рівно те, що видно, — розмір і обсяг тексту, — і
    називає звичні причини, лишаючи висновок людині. Наслідок від
    причини не залежить: таку сторінку не дочитає ні відвідувач, ні
    пошук.
    """

    code = "perf.page_weight"
    module = Module.PERFORMANCE
    severity = Severity.MEDIUM
    weight = 3
    effort = Effort.MEDIUM
    messages = ("perf.page_weight", "perf.page_weight.truncated")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        limit = settings.max_response_bytes
        for page in ctx.ok_pages:
            if page.html_bytes < HEAVY_HTML_BYTES:
                continue
            # Впертися в межу завантаження означає, що сторінку не
            # дочитали навіть ми. Решта висновків про неї — про той
            # шматок, який встиг поміститися.
            cut = page.html_bytes >= limit
            yield self.issue(
                msg="perf.page_weight.truncated" if cut else "perf.page_weight",
                params={
                    "megabytes": round(page.html_bytes / 1024 / 1024, 1),
                    "words": page.word_count,
                },
                evidence={
                    "html_bytes": page.html_bytes,
                    "words": page.word_count,
                    "read_limit_bytes": limit,
                    "truncated": cut,
                    # Уперлись у власну стелю читання — отже, розмір
                    # ЩОНАЙМЕНШЕ такий. Точного ми не виміряли, і
                    # подавати межу як вимір означало б вигадати
                    # точність, якої в нас немає.
                    "size_is_lower_bound": cut,
                    "text_sample": page.text[:200],
                },
                severity=Severity.HIGH if cut else Severity.MEDIUM,
                page_url=page.url,
            )
