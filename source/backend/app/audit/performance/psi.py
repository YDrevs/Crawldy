"""Провайдер на базі Google PageSpeed Insights API (lab + CrUX field data)."""

from __future__ import annotations

import math
from typing import Any, NamedTuple
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.audit.performance.base import rate
from app.audit.types import MetricValue, PerformanceResult, Strategy
from app.core.config import settings
from app.core.logging import log

ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

LAB_AUDITS = {
    "largest-contentful-paint": ("LCP", "ms"),
    "first-contentful-paint": ("FCP", "ms"),
    "cumulative-layout-shift": ("CLS", ""),
    "total-blocking-time": ("TBT", "ms"),
    "server-response-time": ("TTFB", "ms"),
    "speed-index": ("SI", "ms"),
}

FIELD_METRICS = {
    "LARGEST_CONTENTFUL_PAINT_MS": ("LCP", "ms"),
    "FIRST_CONTENTFUL_PAINT_MS": ("FCP", "ms"),
    "CUMULATIVE_LAYOUT_SHIFT_SCORE": ("CLS", ""),
    "INTERACTION_TO_NEXT_PAINT": ("INP", "ms"),
    "EXPERIMENTAL_TIME_TO_FIRST_BYTE": ("TTFB", "ms"),
}


class PsiProvider:
    name = "psi"

    def __init__(self, api_key: str | None = None, timeout: float = 90.0) -> None:
        self._api_key = api_key or settings.psi_api_key
        self._timeout = timeout

    async def measure(self, url: str, strategy: Strategy) -> PerformanceResult:
        result = PerformanceResult(provider=self.name, strategy=strategy, url=url)
        params: dict[str, Any] = {
            "url": url,
            "strategy": strategy.value,
            # Дві категорії одним запитом. Доступність не коштує ні
            # окремого виклику, ні окремого движка: Lighthouse усередині
            # PSI — це той самий axe-core, який довелося б підключати.
            "category": ["performance", "accessibility"],
        }
        if self._api_key:
            params["key"] = self._api_key
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(ENDPOINT, params=params)
            if response.status_code != 200:
                result.error = f"PSI HTTP {response.status_code}: {response.text[:200]}"
                return result
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            result.error = f"{type(exc).__name__}: {exc}"
            log.warning("psi_failed", url=url, error=result.error)
            return result

        result.fetched = True
        _parse_lab(payload, result)
        _parse_field(payload, result)
        _parse_accessibility(payload, result)
        return result


def _parse_lab(payload: dict[str, Any], result: PerformanceResult) -> None:
    lighthouse = payload.get("lighthouseResult") or {}
    categories = lighthouse.get("categories") or {}
    if (perf := categories.get("performance")) and perf.get("score") is not None:
        result.lighthouse_score = round(float(perf["score"]) * 100, 1)

    audits = lighthouse.get("audits") or {}
    for audit_id, (metric, unit) in LAB_AUDITS.items():
        audit = audits.get(audit_id) or {}
        value = audit.get("numericValue")
        if value is None:
            continue
        value = float(value)
        result.lab[metric] = MetricValue(value=value, unit=unit, rating=rate(metric, value))

    for audit_id, audit in audits.items():
        details = audit.get("details") or {}
        savings = details.get("overallSavingsMs") or 0
        if details.get("type") == "opportunity" and savings >= 100:
            result.opportunities.append(
                {
                    "id": audit_id,
                    "title": audit.get("title", ""),
                    "savings_ms": int(savings),
                    "description": (audit.get("description") or "")[:400],
                }
            )
    result.opportunities.sort(key=lambda o: o["savings_ms"], reverse=True)


def _parse_field(payload: dict[str, Any], result: PerformanceResult) -> None:
    metrics = (payload.get("loadingExperience") or {}).get("metrics") or {}
    for key, (metric, unit) in FIELD_METRICS.items():
        entry = metrics.get(key)
        if not entry or entry.get("percentile") is None:
            continue
        raw = float(entry["percentile"])
        value = raw / 100 if metric == "CLS" else raw
        result.field_data[metric] = MetricValue(
            value=value, unit=unit, rating=rate(metric, value)
        )


# Перевірки доступності, які Lighthouse позначає як провалені, але які
# нічого не кажуть про сайт: вони або дублюють наші власні чеки, або
# стосуються вмісту, якого на сторінці може не бути за задумом.
_A11Y_NOISE = frozenset({"heading-order", "image-alt", "html-has-lang"})

# Режими, у яких Lighthouse нічого не перевіряв: `notApplicable` — на
# сторінці немає того, що перевіряють; `manual` — потрібна людина;
# `informative` — довідка без вироку. Жоден із них не свідчить ані за
# сайт, ані проти нього, тож у знаменник вони не входять.
_NOT_AUTOMATED = frozenset({"notApplicable", "manual", "informative"})


def _finite(value: Any) -> float | None:
    """Число, яким справді можна вимірювати.

    Провайдер може покласти в поле бала будь-що: рядок `"n/a"` в урізаній
    відповіді, `null`, прапорець, NaN. Жодне з цього не є вимірюванням, і
    перетворювати його на бал не можна — саме так і зʼявляються вигадані
    цифри, яких у цьому продукті бути не може. `bool` відсіюється окремо:
    у Python він підклас `int`, тож `True` мовчки став би одиницею.
    """
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _unit_score(value: Any) -> float | str:
    """Бал Lighthouse як число — або код причини, чому його не можна прийняти.

    Бал Lighthouse — скінченне число від 0 до 1 включно. Число поза цими
    межами — не «дуже добре» й не «дуже погано», а відповідь, якій не
    можна вірити: `1.1` дав би у звіті 110 балів доступності, а `-0.1` —
    провалену перевірку, якої ніхто не провалював. Одне правило на бал
    категорії й на бал кожної перевірки.
    """
    number = _finite(value)
    if number is None:
        return "not_a_finite_number"
    if not 0.0 <= number <= 1.0:
        return "out_of_range"
    return number


def _loggable_url(url: str) -> str:
    """Адреса для журналу: схема, хост і шлях — без запиту й фрагмента.

    У запиті бувають токени сесії й підписані посилання, а перед хостом —
    облікові дані. Для розслідування досить знати, яку сторінку міряли.
    """
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return ""
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    netloc = f"{host}:{port}" if port is not None else host
    return urlunsplit((parts.scheme, netloc, parts.path, "", ""))


class _AccessibilityReading(NamedTuple):
    """Цілком перевірена категорія доступності, ще не записана в результат."""

    score: float
    failures: list[dict[str, Any]]
    failures_all: list[dict[str, Any]]
    audits_total: int
    applicable: int
    passed: int
    failed: int


def _read_accessibility(
    lighthouse: dict[str, Any], category: dict[str, Any]
) -> _AccessibilityReading | str:
    """Уся категорія, перевірена до першого запису, або причина відмови.

    Категорія придатна лише цілком. Бал без жодного посилання на перевірку,
    посилання на перевірку, якої у відповіді немає, чи перевірка з балом
    поза межами — це не «виміряно частково», а відповідь, якій не можна
    вірити. Порахувати лічильники за вцілілою частиною означало б видати
    знімок того, чого Lighthouse не підтвердив.
    """
    score = _unit_score(category.get("score"))
    if isinstance(score, str):
        return f"score_{score}"
    refs = category.get("auditRefs")
    if not isinstance(refs, list):
        return "audit_refs_not_a_list"
    audits = lighthouse.get("audits")
    if not isinstance(audits, dict):
        return "audits_not_an_object"

    # Перелік беремо з самої категорії, а не з усіх перевірок відповіді:
    # у payload лежать разом і accessibility, і performance, і «Minify CSS»
    # серед проблем доступності виглядав би саме так, як і є, — помилкою.
    # Окремий сміттєвий елемент переліку ігнорується, поки лишаються
    # справжні посилання; порожній або цілком сміттєвий перелік — ні, бо
    # без жодного посилання немає й знаменника.
    wanted = dict.fromkeys(
        ref["id"]
        for ref in refs
        if isinstance(ref, dict) and isinstance(ref.get("id"), str) and ref["id"].strip()
    )
    if not wanted:
        return "no_valid_audit_refs"
    # Посилання, що не веде до перевірки, — не сміття, а розрив: категорія
    # оголосила перевірку, а її результату у відповіді немає. Бал такої
    # категорії неможливо звірити з тим, з чого він складений.
    for ref_id in wanted:
        if ref_id not in audits:
            return "audit_ref_unresolved"
        if not isinstance(audits[ref_id], dict):
            return "audit_record_not_an_object"

    # Порядок обходу — той самий, що й був: за `audits`, а не за `wanted`,
    # щоб перелік провалів, який бачить клієнт, не змінився.
    checked: list[tuple[str, dict[str, Any], float]] = []
    for audit_id, audit in audits.items():
        # Лише те, що Lighthouse справді перевірив на цій сторінці.
        if audit_id not in wanted or audit.get("scoreDisplayMode") in _NOT_AUTOMATED:
            continue
        value = _unit_score(audit.get("score"))
        if isinstance(value, str):
            return "audit_score_invalid"
        checked.append((audit_id, audit, value))
    if not checked:
        return "no_applicable_audits"

    failures: list[dict[str, Any]] = []
    failures_all: list[dict[str, Any]] = []
    passed = 0
    for audit_id, audit, value in checked:
        if value >= 1:
            passed += 1
            continue
        # Провал рахується завжди, і ДО фільтра шуму: питання «скільки
        # Lighthouse перевірив і скільки з того впало» не залежить від
        # того, про що з цього ми вирішили розповідати клієнту.
        details = audit.get("details")
        entry = {
            "id": audit_id,
            "title": audit.get("title", ""),
            "impact": details.get("impact", "") if isinstance(details, dict) else "",
        }
        # Клієнтові — все, чекам — без дублів. Один прохід, два переліки:
        # інакше правда для звіту й вхід для скора розійшлися б у складі.
        failures_all.append(entry)
        if audit_id not in _A11Y_NOISE:
            failures.append(entry)

    # Знаменник кладемо поруч із балом: сам бал без нього не читається.
    # На 456 перевірках шести сайтів усі застосовні виявились бінарними
    # (score 0 або 1), тож `passed + failed == applicable` тут — не
    # припущення, а спостереження. Дробовий бал потрапляє в `failed` рівно
    # так само, як уже потрапляє в `accessibility_failures`: успадкована
    # поведінка, а не нове рішення.
    return _AccessibilityReading(
        score=round(score * 100, 1),
        failures=failures,
        failures_all=failures_all,
        audits_total=len(wanted),
        applicable=len(checked),
        passed=passed,
        failed=len(checked) - passed,
    )


def _parse_accessibility(payload: dict[str, Any], result: PerformanceResult) -> None:
    """Бал і провалені перевірки доступності з тієї самої відповіді.

    Один парсер на обидва провайдери: PSI і власний Lighthouse-сайдкар
    віддають ту саму структуру `lighthouseResult`, тож окремої логіки
    доступності для сайдкара не існує. Якби вона зʼявилась, два шляхи
    розійшлися б, і бал модуля залежав би від того, хто відповів.

    Категорія придатна лише тоді, коли придатна вся:
      - бал — скінченне число від 0 до 1 включно;
      - `auditRefs` — список, у якому є хоча б одне справжнє посилання;
      - `audits` — обʼєкт, і кожне справжнє посилання веде до обʼєкта
        перевірки;
      - кожна автоматична перевірка має бал від 0 до 1;
      - хоча б одна перевірка справді застосовна, тобто знаменник існує.
    Непридатна категорія лишає напрям невиміряним: жодного бала, жодного
    лічильника, жодного провалу. Запис у `result` відбувається один раз і
    лише після того, як уся категорія перевірена.

    Дублікати наших власних чеків відсіюються: сказати клієнту двічі про
    відсутній alt означає подвоїти штраф за одну ваду.

    Відповідь не змінюється: її після нас читають інші парсери.
    """
    lighthouse = payload.get("lighthouseResult")
    if not isinstance(lighthouse, dict):
        return
    categories = lighthouse.get("categories")
    category = categories.get("accessibility") if isinstance(categories, dict) else None
    # Категорії немає взагалі: її не запитували, або відповідь урізана.
    # Це звичайний стан — модуль просто лишається невиміряним, і мовчання
    # тут правильне.
    if category is None:
        return

    reading = (
        _read_accessibility(lighthouse, category)
        if isinstance(category, dict)
        else "category_not_an_object"
    )
    if isinstance(reading, str):
        # Категорія є, але вірити їй не можна. Нуль чи сто з цього були б
        # видачею нашої сліпоти за вимір, тож напрям лишається невиміряним.
        # Одне попередження з кодом причини — без вмісту відповіді, без
        # ідентифікаторів перевірок і без запиту чи фрагмента адреси.
        log.warning(
            "accessibility_category_unusable",
            provider=result.provider,
            url=_loggable_url(result.url),
            reason=reading,
        )
        return

    result.accessibility_score = reading.score
    result.accessibility_failures_all.extend(reading.failures_all)
    result.accessibility_failures.extend(reading.failures)
    result.accessibility_audits_total = reading.audits_total
    result.accessibility_applicable = reading.applicable
    result.accessibility_passed = reading.passed
    result.accessibility_failed = reading.failed
