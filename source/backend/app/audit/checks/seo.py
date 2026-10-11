"""Чеки базового SEO."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from typing import Any, ClassVar
from urllib.parse import urldefrag, urljoin, urlparse

from app.audit import (
    anchor_text,
    applicability,
    duplicates,
    hreflang,
    link_evidence,
    redirects,
    render_diff,
    sitemap_audit,
)
from app.audit.checks.base import Check, register
from app.audit.logical_pages import normalize
from app.audit.page_kinds import (
    BUILDS_A_TOPIC,
    CONTENT_IS_NOT_PROSE,
    NOT_FOR_SEARCH,
    is_safe_topic_section,
    section_of,
)
from app.audit.standards import language_tags
from app.audit.types import (
    Confidence,
    Effort,
    Issue,
    Module,
    PageSignals,
    Severity,
    SiteContext,
)

THIN_CONTENT_WORDS = 250

# Не «дозволена довжина», а те, скільки пошук реально показує, перш ніж
# обрізати. Усе понад це існує, але його ніхто не побачить — тому міряємо
# не перевищення в символах, а частку тексту, яка пропаде.
TITLE_VISIBLE = 60
DESC_VISIBLE = 160

# Нижня межа — не норматив, а поріг змістовності. Специфікація мінімуму
# не задає, тож ловимо лише те, що справді нічого не каже: голу назву
# бренду. «Blog · Dronehub» — нормальний заголовок розділу, не дефект.
TITLE_INFORMATIVE = 15
DESC_INFORMATIVE = 50

# Обрізання — питання показу, а не індексації: сторінка ранжується так
# само, а AI-краулери читають опис цілком. Тому довгий опис чи заголовок
# сам собою не дефект, а спостереження: перевір, що суть на початку.
# Оцінку це не змінює (INFO має множник 0) — крім випадку, коли невидимою
# стає більша частина тексту, і початок уже навряд чи несе всю суть.
SIGNIFICANT_CUT = 0.50


def _cut_share(length: int, visible: int) -> float:
    return (length - visible) / length if length > visible else 0.0


# Код мови в адресі: /en-US/, /uk/, /pt-BR/ — це стандарт, а не недбалість.
_LOCALE_SEGMENT = re.compile(r"^[a-z]{2}(-[a-zA-Z]{2,4})?$")


def _has_stray_uppercase(path: str) -> bool:
    for segment in path.strip("/").split("/"):
        if not segment or not any(c.isupper() for c in segment):
            continue
        if _LOCALE_SEGMENT.match(segment):
            continue
        # Назва сутності одним словом (Element, HTMLElement) — теж домовленість.
        if segment.isalnum() and "-" not in segment and "_" not in segment:
            continue
        return True
    return False


@register
class TitleCheck(Check):
    code = "seo.title"
    module = Module.SEO
    severity = Severity.CRITICAL
    weight = 5
    effort = Effort.MEDIUM
    messages = ("seo.title.missing", "seo.title.too_short", "seo.title.too_long")
    variants = ("missing", "too_short", "too_long")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.pages_as_seen(ctx.content_pages):
            if not page.title:
                yield self.issue(
                    key="missing",
                    msg="seo.title.missing",
                    evidence={"found": None, "h1": page.h1[:1], "words_on_page": page.word_count},
                    page_url=page.url,
                )
                continue

            length = len(page.title)
            cut = _cut_share(length, TITLE_VISIBLE)
            if cut > 0:
                yield self.issue(
                    key="too_long",
                    msg="seo.title.too_long",
                    params={"length": length, "visible": TITLE_VISIBLE},
                    evidence={
                        "title": page.title,
                        "length": length,
                        "shown": page.title[:TITLE_VISIBLE],
                        "hidden": page.title[TITLE_VISIBLE:],
                    },
                    severity=Severity.LOW if cut >= SIGNIFICANT_CUT else Severity.INFO,
                    page_url=page.url,
                )
            elif length < TITLE_INFORMATIVE:
                yield self.issue(
                    key="too_short",
                    msg="seo.title.too_short",
                    params={"length": length, "min": TITLE_INFORMATIVE},
                    evidence={"title": page.title, "length": length},
                    severity=Severity.LOW,
                    page_url=page.url,
                )


@register
class DuplicateTitleCheck(Check):
    code = "seo.title.duplicate"
    module = Module.SEO
    severity = Severity.HIGH
    weight = 3
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Суперниками за той самий заголовок бувають лише сторінки, які
        # СПРАВДІ змагаються в пошуку. Вхід, кошик і кабінет ділять
        # заголовок за задумом, і рахувати їх дублікатами означало б
        # порадити переписати title сторінці, якої в пошуку немає.
        pages = applicability.pages_for(ctx, self.code)
        counts = Counter(p.title for p in pages if p.title)
        for title, count in counts.items():
            if count > 1:
                urls = [p.url for p in pages if p.title == title]
                yield self.issue(
                    params={"count": count},
                    evidence={"title": title, "urls": urls[:10]},
                )


@register
class MetaDescriptionCheck(Check):
    code = "seo.meta_description"
    module = Module.SEO
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.MEDIUM
    messages = (
        "seo.meta_description.missing",
        "seo.meta_description.too_long",
        "seo.meta_description.too_short",
    )
    variants = ("missing", "too_long", "too_short")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.pages_as_seen(ctx.content_pages):
            desc = page.meta_description
            if not desc:
                yield self.issue(
                    key="missing",
                    msg="seo.meta_description.missing",
                    params={"visible": DESC_VISIBLE},
                    evidence={
                        # Докази машиночитані: вони йдуть в обидві мовні
                        # версії звіту, тож тексту в них бути не може.
                        "found": None,
                        "expected_max_chars": DESC_VISIBLE,
                        "title": page.title,
                        "og_description": page.opengraph.get("og:description"),
                    },
                    page_url=page.url,
                )
                continue

            length = len(desc)
            cut = _cut_share(length, DESC_VISIBLE)
            if cut > 0:
                yield self.issue(
                    key="too_long",
                    msg="seo.meta_description.too_long",
                    params={
                        "length": length,
                        "visible": DESC_VISIBLE,
                        "percent": round(cut * 100),
                    },
                    evidence={
                        "length": length,
                        "shown": desc[:DESC_VISIBLE],
                        "hidden": desc[DESC_VISIBLE:],
                    },
                    severity=Severity.LOW if cut >= SIGNIFICANT_CUT else Severity.INFO,
                    page_url=page.url,
                )
            elif length < DESC_INFORMATIVE:
                yield self.issue(
                    key="too_short",
                    msg="seo.meta_description.too_short",
                    params={"length": length, "min": DESC_INFORMATIVE},
                    evidence={"length": length, "description": desc},
                    severity=Severity.LOW,
                    page_url=page.url,
                )


@register
class H1Check(Check):
    """Сімʼя заголовків: рівно один факт на сторінку, без обіцянок.

    h1 — одне з девʼяти джерел, з яких Google складає title-link
    (developers.google.com/search/docs/appearance/title-link), і
    рекомендована практика структури документа (MDN, W3C WAI), а не
    вимога. Тому:

    * немає h1, але є інший HTML-заголовок — LOW: практика, з якої
      сторінка нічого страшного не втрачає (95% таких сторінок night3
      мають title, 72% — інший заголовок);
    * HTML-заголовків h1–h6 немає ВЗАГАЛІ — MEDIUM: структури, за яку
      можуть триматися читачі й допоміжні технології, немає. Відсутній
      title при цьому НЕ підвищує серйозність — наслідок відсутнього
      title належить seo.title:missing, а ця сімʼя міряє лише
      заголовки. Формулювання обмежене HTML: ARIA-заголовків ми не
      збираємо;
    * кілька h1 — INFO без штрафу: стандарт HTML це дозволяє, видимість
      дублів (типовий desktop/mobile-шаблон — 54% випадків night3 мають
      рівно два) ми з CSS не відновлюємо, тож карати нема за що.

    Одна знахідка сімʼї на сторінку; сильніший варіант виграє.
    """

    code = "seo.h1"
    module = Module.SEO
    severity = Severity.LOW
    weight = 3
    effort = Effort.LOW
    messages = ("seo.h1.missing", "seo.h1.multiple", "seo.h1.no_headings")
    variants = ("missing", "multiple", "no_headings")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.pages_as_seen(ctx.content_pages):
            if len(page.h1) == 1:
                continue
            if len(page.h1) > 1:
                yield self.issue(
                    key="multiple",
                    msg="seo.h1.multiple",
                    params={"count": len(page.h1)},
                    evidence={
                        "h1": page.h1[:5],
                        # CSS ми не читаємо: чи видимі дублі — не знаємо.
                        "css_visibility_assessed": False,
                    },
                    severity=Severity.INFO,
                    confidence=Confidence.MEDIUM,
                    page_url=page.url,
                )
                continue
            first = next(iter(page.headings), None)
            if first is not None:
                level, text = first
                # Шаблон param-вільний навмисно: історичні рядки цього ключа
                # не мають параметрів, і частина з них — сторінки взагалі без
                # заголовків. Рівень і текст першого заголовка несе evidence.
                yield self.issue(
                    key="missing",
                    msg="seo.h1.missing",
                    evidence={
                        "found": [],
                        "first_heading": f"h{level}: {text[:120]}",
                        # До E-16 список приходив згрупованим за рівнем, тож
                        # «перший» тут означало найнижчий рівень на сторінці, а
                        # не те, що читач бачить першим. Тепер це справді
                        # перший заголовок — але сказати так можна лише там, де
                        # порядок доведено, тож ключ зʼявляється саме там.
                        **({"first_heading_in_document_order": True}
                           if page.headings_in_document_order else {}),
                        "title": page.title,
                    },
                    page_url=page.url,
                )
            else:
                yield self.issue(
                    key="no_headings",
                    msg="seo.h1.no_headings",
                    evidence={
                        "html_heading_count": 0,
                        # діагностика, не ескалація: наслідок відсутнього
                        # title належить seo.title:missing.
                        "title_present": bool(page.title),
                    },
                    severity=Severity.MEDIUM,
                    page_url=page.url,
                )


@register
class HeadingHierarchyCheck(Check):
    code = "seo.heading_hierarchy"
    module = Module.SEO
    severity = Severity.LOW
    weight = 1
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.pages_as_seen(ctx.content_pages):
            # Рівні, що є на сторінці ВЗАГАЛІ. Ними розводяться два різні
            # твердження, які досі збігалися лише тому, що список приходив
            # відсортованим:
            #
            #   рівня немає ніде  — доводиться будь-яким представленням, бо це
            #                       факт про множину рівнів, а не про порядок;
            #   рівень пропущено  — факт про ПОРЯДОК читання, і його можна
            #     у порядку читання   стверджувати лише там, де порядок доведено.
            present = {level for level, _text in page.headings}
            previous = 0
            for level, text in page.headings:
                if previous and level > previous + 1:
                    missing_everywhere = not any(
                        step in present for step in range(previous + 1, level)
                    )
                    if not (missing_everywhere or page.headings_in_document_order):
                        # Проміжний рівень на сторінці є, а порядку ми не
                        # доводили: сказати «пропущено» означало б вигадати
                        # послідовність, якої знімок не зберігав.
                        break
                    yield self.issue(
                        params={"previous": previous, "level": level},
                        evidence={
                            "heading": text,
                            "level": level,
                            "previous": previous,
                            # Ключ зʼявляється лише там, де порядок доведено:
                            # на старому знімку доказ мусить лишитися байт у
                            # байт таким, яким був, інакше перерахунок покаже
                            # дельту там, де сайт не змінився.
                            **({"in_document_order": True}
                               if page.headings_in_document_order else {}),
                        },
                        page_url=page.url,
                    )
                    break
                previous = level


@register
class CanonicalCheck(Check):
    code = "seo.canonical"
    module = Module.SEO
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.LOW
    messages = ("seo.canonical.missing", "seo.canonical.mismatch")
    variants = ("missing", "mismatch")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            if not page.canonical:
                yield self.issue(
                    key="missing",
                    msg="seo.canonical.missing",
                    evidence={
                        "found": None,
                        "expected": page.url,
                        "og_url": page.opengraph.get("og:url"),
                    },
                    page_url=page.url,
                )
                continue
            canonical, _ = urldefrag(page.canonical)
            current, _ = urldefrag(page.url)
            if canonical.rstrip("/") != current.rstrip("/"):
                yield self.issue(
                    key="mismatch",
                    msg="seo.canonical.mismatch",
                    evidence={"canonical": page.canonical, "page": page.url},
                    severity=Severity.LOW,
                    page_url=page.url,
                )


@register
class IndexabilityCheck(Check):
    """Сторінка закрита від пошуку. Питання — чи навмисно.

    `noindex` — це вказівка, яку власник дав сам, а не поломка. Ми
    бачимо саму вказівку й не бачимо наміру, тож стверджувати «це
    помилка» не можемо.

    Так було не завжди, і дані показали ціну: на калібрувальній вибірці
    чек видавав `critical` на PPC-лендингах Shopify, архіві вебінару,
    закритому демо Cloudflare і варіанті сторінки контактів Stripe для
    внутрішнього трафіку. Усе це закрито навмисно й правильно, а ми
    сімом сайтам верхнього рівня ставили критичну ваду там, де вади
    немає. Нижньому рівню — жодної: у нього просто немає таких сторінок.

    Тепер це спостереження середньої серйозності з невисокою
    впевненістю, і воно каже «перевірте, чи так задумано». Випадок, коли
    сумнівів немає, ловить окремий чек: `seo.links_to_noindex` — там
    сайт сам веде на сторінку, яку заборонив показувати.
    """

    code = "seo.noindex"
    module = Module.SEO
    severity = Severity.MEDIUM
    weight = 3
    effort = Effort.LOW
    confidence = Confidence.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            robots = page.meta_robots or ""
            if "noindex" not in robots:
                continue
            # Вхід в адмінку, кошик, архів тегів не мають ранжуватися, і
            # noindex на них — правильне рішення власника. Критична
            # знахідка «приберіть noindex з wp-login.php» дискредитує
            # увесь список: клієнт бачить, що ми не розуміємо його сайт.
            kind = ctx.type_of(page)
            if kind in NOT_FOR_SEARCH:
                continue
            yield self.issue(
                evidence={"meta_robots": robots, "page_type": str(kind)},
                page_url=page.url,
            )


@register
class RobotsTxtCheck(Check):
    code = "seo.robots_txt"
    module = Module.SEO
    severity = Severity.HIGH
    weight = 3
    effort = Effort.LOW
    messages = (
        "seo.robots_txt.missing",
        "seo.robots_txt.disallow_all",
        "seo.robots_txt.no_sitemap",
    )
    variants = ("missing", "disallow_all", "no_sitemap")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        if not ctx.robots.exists:
            yield self.issue(
                key="missing",
                msg="seo.robots_txt.missing",
                evidence={"status_code": ctx.robots.status_code},
                severity=Severity.MEDIUM,
            )
            return
        if ctx.robots.disallows_all:
            yield self.issue(
                key="disallow_all",
                msg="seo.robots_txt.disallow_all",
                evidence={"found": "Disallow: /", "url": f"{ctx.origin}/robots.txt"},
                severity=Severity.CRITICAL,
            )
        if not ctx.robots.sitemaps:
            yield self.issue(
                key="no_sitemap",
                msg="seo.robots_txt.no_sitemap",
                evidence={
                    "found": [],
                    "expected": f"Sitemap: {ctx.origin}/sitemap.xml",
                    "sitemap_reachable": ctx.sitemap.exists,
                },
                severity=Severity.LOW,
            )


@register
class SitemapCheck(Check):
    code = "seo.sitemap"
    module = Module.SEO
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.LOW
    messages = (
        "seo.sitemap.missing",
        "seo.sitemap.invalid",
        "seo.sitemap.empty",
        "seo.sitemap.coverage",
    )
    variants = ("missing", "invalid", "empty", "coverage")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        sitemap = ctx.sitemap
        if not sitemap.exists:
            yield self.issue(
                key="missing",
                msg="seo.sitemap.missing",
                evidence={
                    "checked": f"{ctx.origin}/sitemap.xml",
                    "status_code": sitemap.status_code,
                    "declared_in_robots": ctx.robots.sitemaps,
                },
                severity=Severity.HIGH,
            )
            return
        if sitemap.parse_error:
            yield self.issue(
                key="invalid",
                msg="seo.sitemap.invalid",
                evidence={"error": sitemap.parse_error, "url": sitemap.url},
                severity=Severity.HIGH,
            )
            return
        if sitemap.url_count == 0:
            yield self.issue(
                key="empty",
                msg="seo.sitemap.empty",
                evidence={
                    "url_count": 0,
                    "pages_crawled": len(ctx.ok_pages),
                    "url": sitemap.url,
                },
                severity=Severity.HIGH,
            )
            return
        indexed = {u.rstrip("/") for u in sitemap.urls}
        missing = [p.url for p in ctx.ok_pages if p.url.rstrip("/") not in indexed]
        if missing:
            yield self.issue(
                key="coverage",
                msg="seo.sitemap.coverage",
                params={"count": len(missing)},
                evidence={"examples": missing[:10], "sitemap_urls": sitemap.url_count},
                severity=Severity.LOW,
            )


@register
class BrokenInternalLinksCheck(Check):
    """Адреси, які віддали помилку, — і сторінки, що на них ведуть.

    ## Що змінилося й що ні

    Умова спрацювання лишилась дослівно та сама: перелік битих адрес
    будується з `failed_urls` і зі сторінок зі статусом ≥ 400. Це
    навмисно — чек ваговитий, а база скорингу заморожена, тож звузити
    або розширити його означало б зрушити бали сайтів, знятих раніше.

    Змінився доказ. Раніше він був пласким `{адреса: "HTTP 404"}` і на
    питання «де це полагодити» не відповідав ніяк: клієнт отримував
    перелік поламаного без жодної згадки, з якої сторінки на нього
    ведуть. Тепер поруч стоять сторінки-джерела, текст посилання й те,
    чи видно посилання у відповіді сервера, чи лише після рендеру.

    ## Ціль без жодного посилання

    Буває: адресу взято з карти сайту, а не з посилання. Такі лишаються
    в переліку — прибрати їх означало б змінити спрацювання ваговитого
    чека, — але в доказі вони чесно позначені `source_pages: 0`, і про
    них є окрема знахідка `seo.sitemap_consistency.error`.

    ## Чого тут немає

    Жодного судження про текст посилання. Він зберігається як факт, бо
    наступний пункт дорожньої карти саме про його якість; порожній
    `anchor` тут теж просто факт, а не зауваження.
    """

    code = "seo.broken_links"
    module = Module.SEO
    severity = Severity.HIGH
    weight = 3
    effort = Effort.MEDIUM

    # Скільки цілей показуємо в доказі. Числа поруч завжди повні.
    SHOWN = 15

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        broken = {
            url: reason
            for url, reason in ctx.failed_urls.items()
            if reason.startswith("HTTP 4") or reason.startswith("HTTP 5")
        }
        for page in ctx.pages:
            if page.status_code and page.status_code >= 400:
                broken.setdefault(page.url, f"HTTP {page.status_code}")
        if not broken:
            return

        attributed = {d.key: d for d in link_evidence.broken(ctx)}
        destinations = []
        for url, reason in broken.items():
            found = attributed.get(normalize(url))
            if found is not None:
                destinations.append(found.as_evidence())
                continue
            # Ціль підтверджено битою, але посилань на неї ми не бачили:
            # вона прийшла з карти сайту або з адреси, яку хтось вписав
            # руками. Мовчати про це не можна — інакше нуль джерел
            # виглядав би як недоробка доказу.
            destinations.append(
                {"url": url, "state": _state_from(reason), "status": _status_from(reason),
                 "source_pages": 0, "links": 0, "examples": [], "examples_shown": 0}
            )

        destinations.sort(key=lambda d: (-int(d["links"]), str(d["url"])))
        shown = destinations[: self.SHOWN]
        evidence: dict[str, object] = {
            # Сумісність: пласка мапа лишається, на неї спираються
            # збережені звіти й тести, старші за атрибуцію.
            "urls": dict(list(broken.items())[:15]),
            "destinations": shown,
            "destinations_total": len(destinations),
            "linked_destinations": sum(1 for d in destinations if d["links"]),
            "source_pages": len({
                example["from"]
                for d in destinations for example in d["examples"]
            }),
        }
        if len(shown) < len(destinations):
            evidence["destinations_truncated"] = True
        yield self.issue(params={"count": len(broken)}, evidence=evidence)


def _state_from(reason: str) -> str:
    if reason.startswith("HTTP 4"):
        return link_evidence.TargetState.CLIENT_ERROR.value
    if reason.startswith("HTTP 5"):
        return link_evidence.TargetState.SERVER_ERROR.value
    return link_evidence.TargetState.FETCH_FAILED.value


def _status_from(reason: str) -> int | None:
    tail = reason.split()[-1]
    return int(tail) if tail.isdigit() else None


@register
class HttpsCheck(Check):
    code = "seo.https"
    module = Module.SEO
    severity = Severity.CRITICAL
    weight = 5
    effort = Effort.MEDIUM
    messages = ("seo.https.missing", "seo.https.invalid_cert", "seo.https.no_hsts")
    variants = ("missing", "invalid_cert", "no_hsts")

    # Сертифікат і HSTS видно з самої відповіді, а не зі сторінки. Саме тому
    # цей чек лишається єдиним осмисленим на сайті, який не віддав вмісту:
    # на badssl він і був єдиною причиною, з якої звіт узагалі щось вартий.
    reads_content = False

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Недійсний сертифікат гірший за його відсутність: браузер не просто
        # позначає сайт незахищеним, а перекриває вхід сторінкою попередження.
        if ctx.tls_error:
            yield self.issue(
                key="invalid_cert",
                msg="seo.https.invalid_cert",
                evidence={"origin": ctx.origin, "error": ctx.tls_error},
            )
            return
        if not ctx.is_https:
            yield self.issue(
                key="missing",
                msg="seo.https.missing",
                evidence={"origin": ctx.origin},
            )
        elif not ctx.hsts:
            # HSTS — захист браузера, а не сигнал пошуку: Google прямо
            # каже, що на Search він не впливає (office hours, червень
            # 2023). INFO без штрафу; вимога діє лише на https-сайті —
            # на http замість неї спрацьовує `missing`, бо HSTS на
            # незашифрованій відповіді незастосовний.
            yield self.issue(
                key="no_hsts",
                msg="seo.https.no_hsts",
                evidence={
                    "found": None,
                    "expected": "Strict-Transport-Security: max-age=31536000",
                    "origin": ctx.origin,
                },
                severity=Severity.INFO,
            )


@register
class ImageAltCheck(Check):
    code = "seo.image_alt"
    module = Module.SEO
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.HIGH

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.content_pages:
            if page.images_without_alt:
                yield self.issue(
                    params={
                        "without_alt": page.images_without_alt,
                        "total": page.images_total,
                    },
                    evidence={
                        "without_alt": page.images_without_alt,
                        "total": page.images_total,
                    },
                    severity=Severity.LOW if page.images_without_alt < 3 else Severity.MEDIUM,
                    page_url=page.url,
                )


@register
class ThinContentCheck(Check):
    code = "seo.thin_content"
    module = Module.SEO
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.HIGH

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.content_pages:
            # Цінність картки товару й категорії несуть не слова, а самі
            # товари, ціни, фільтри й розмітка. Порада «допишіть 250 слів»
            # до каталогу меблів — це вимога зіпсувати робочу сторінку.
            if ctx.type_of(page) in CONTENT_IS_NOT_PROSE:
                continue
            if page.word_count < THIN_CONTENT_WORDS:
                yield self.issue(
                    params={"word_count": page.word_count, "threshold": THIN_CONTENT_WORDS},
                    evidence={"word_count": page.word_count},
                    severity=Severity.LOW if page.word_count > 100 else Severity.MEDIUM,
                    page_url=page.url,
                )


@register
class ThinOutboundLinkingCheck(Check):
    """Зі сторінки майже нікуди піти: вона сама майже ні на що не посилається.

    ## Що саме тут міряється — і чого тут немає

    Рахуються посилання **зі** сторінки на решту сайту. Це вихідні
    посилання, і жодного висновку про вхідні з них не випливає:
    сторінка, на яку веде все меню, може при цьому не посилатися нікуди.

    Код чека — `seo.click_depth` — цього не каже, і саме це вже коштувало
    нам неправди в звіті. Ім'я з'явилося у фазі 0, коли клас звався
    «Слабка внутрішня перелінковка» й `consequence` ще не існувало. Коли
    його додали для звіту власнику, автор прочитав ім'я коду, а не тіло
    методу, і написав «на цю сторінку майже нічого не веде» — твердження
    про вхідні посилання, яке граф посилань спростовує власним полем
    `incoming`.

    Код лишається старим навмисно: `issue_key` тримає стелю штрафу й
    групування, а `detector_version()` хешує саме коди — перейменування
    зробило б непорівнянними всі пари аудитів, що перетинають цю зміну.
    Ім'я класу натомість не бачить ані база, ані відбиток версії, тож
    правду видно там, де її читають.

    Глибина сторінки й вхідні посилання в графі є (`link_graph.depth`,
    `link_graph.incoming`) і вже працюють: перше — у важливості сторінки,
    друге — ще й у `seo.orphan_pages`. Тут вони не потрібні.
    """

    code = "seo.click_depth"
    module = Module.SEO
    severity = Severity.LOW
    weight = 1
    effort = Effort.MEDIUM

    # Менше трьох — поріг із фази 0. Він не змінюється разом із цим
    # виправленням: рухати його означало б рухати бали, а виправлення
    # стосується того, що ми стверджуємо, а не того, кого позначаємо.
    MIN_OUTBOUND = 3

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            outbound = sum(1 for link in page.links if link.is_internal)
            if outbound < self.MIN_OUTBOUND:
                yield self.issue(
                    params={"internal_links": outbound},
                    evidence={
                        "outbound_internal_links": outbound,
                        # Стара назва лишається поруч: на неї спираються
                        # збережені звіти й шаблон заголовка.
                        "internal_links": outbound,
                        "measures": "links from this page to the rest of the site",
                    },
                    page_url=page.url,
                )


@register
class CleanUrlCheck(Check):
    code = "seo.clean_url"
    module = Module.SEO
    severity = Severity.LOW
    weight = 1
    effort = Effort.HIGH
    # Окремий ключ на кожну ваду, а не список у params: інакше назви вад
    # довелося б збирати рядком у чеку, і в англійському звіті вони
    # лишилися б українськими.
    messages = ("seo.clean_url.uppercase", "seo.clean_url.underscore", "seo.clean_url.query")
    variants = ("uppercase", "underscore", "query")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            parsed = urlparse(page.url)
            evidence = {"path": parsed.path, "query": parsed.query}
            # Код локалі (/en-US/) і назви сутностей (/API/Element) пишуться
            # з великої за стандартом — MDN давав вісім хибних знахідок
            # саме на них. Скаржимося лише коли великі літери в звичайних
            # словах, тобто не в короткому сегменті й не в коді мови.
            if _has_stray_uppercase(parsed.path):
                yield self.issue(
                    key="uppercase",
                    msg="seo.clean_url.uppercase",
                    evidence=evidence,
                    page_url=page.url,
                )
            if "_" in parsed.path:
                yield self.issue(
                    key="underscore",
                    msg="seo.clean_url.underscore",
                    evidence=evidence,
                    page_url=page.url,
                )
            if parsed.query:
                yield self.issue(
                    key="query",
                    msg="seo.clean_url.query",
                    evidence=evidence,
                    page_url=page.url,
                )


@register
class SitemapFreshnessCheck(Check):
    code = "seo.sitemap.lastmod"
    module = Module.SEO
    severity = Severity.LOW
    weight = 1
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        sitemap = ctx.sitemap
        if not sitemap.exists or sitemap.parse_error or sitemap.url_count == 0:
            return
        if not sitemap.has_lastmod:
            yield self.issue(
                evidence={"url_count": sitemap.url_count, "url": sitemap.url},
            )


@register
class ViewportCheck(Check):
    code = "seo.viewport"
    module = Module.SEO
    severity = Severity.HIGH
    weight = 3
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            if not page.viewport:
                # Без доказів знахідку неможливо перевірити: на profound.com
                # тег є на головній і немає на легасі-сторінці /SignIn.aspx,
                # і без URL та вмісту тега це виглядало як хибне спрацювання.
                yield self.issue(
                    evidence={"found": None, "expected": "width=device-width, initial-scale=1"},
                    page_url=page.url,
                )


# Яку частку карти сайту треба прочитати, щоб «на цю сторінку ніхто не
# посилається» було твердженням про сайт, а не про наш бюджет краулу.
SITEMAP_COVERAGE_FOR_ORPHANS = 0.5


def _sample_covers_the_site(ctx: SiteContext) -> bool:
    """Чи прочитано досить, щоб робити висновок із відсутності посилань.

    На furniturerow.com у карті 8147 адрес, а в бюджет краулу входить
    двадцять пʼять. Сторінка, на яку ніхто з цих двадцяти пʼяти не
    посилається, майже напевно має посилання з категорії, якої ми не
    відкривали. Найдорожча помилка проєкту — порада додати те, що в
    клієнта вже було, і цей чек стоїть рівно на тому ж місці.
    """
    total = ctx.sitemap.url_count
    if not total:
        return False
    return len(ctx.ok_pages) / total >= SITEMAP_COVERAGE_FOR_ORPHANS


@register
class OrphanPagesCheck(Check):
    """Сторінка є в карті сайту, але на неї не веде жодне посилання.

    Пошук її знайде — карта для того й потрібна. Але відвідувач не
    знайде ніколи, а сама вага сторінки в очах пошуку тримається лише на
    карті, тобто на найслабшому з можливих сигналів.

    Судимо лише про прочитане: сторінка, на яку посилається непрочитана
    нами сторінка, сиротою не є, і назвати її такою означало б описати
    нашу вибірку замість сайту.
    """

    code = "seo.orphan_pages"
    module = Module.SEO
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.MEDIUM
    confidence = Confidence.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        graph = ctx.links
        orphans = list(getattr(graph, "orphans", []))
        if not orphans or not _sample_covers_the_site(ctx):
            return
        yield self.issue(
            params={"count": len(orphans)},
            evidence={
                "orphans": orphans[:8],
                "pages_read": len(ctx.ok_pages),
                "sitemap_urls": ctx.sitemap.url_count,
            },
        )


@register
class LinksToNoindexCheck(Check):
    """Меню веде на сторінку, яку сайт сам заборонив показувати в пошуку.

    Це не помилка настройки noindex і не помилка посилання окремо —
    суперечність між ними. Або сторінка потрібна людям і має індексуватися,
    або вона службова й не має бути в навігації.
    """

    code = "seo.links_to_noindex"
    module = Module.SEO
    severity = Severity.LOW
    weight = 1
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Граф складає пари, обходячи множину адрес, тож їхній порядок залежить
        # від PYTHONHASHSEED, і той самий сайт давав різні п'ять прикладів.
        # Приклади беремо з повністю впорядкованого переліку (джерело, ціль);
        # самі пари, їхні повтори й кількість не змінюються.
        pairs = sorted(getattr(ctx.links, "to_noindex", []))
        if not pairs:
            return
        targets = sorted({target for _, target in pairs})
        yield self.issue(
            params={"count": len(targets)},
            evidence={
                "targets": targets[:8],
                "examples": [f"{source} → {target}" for source, target in pairs[:5]],
            },
        )


# Скільки сторінок одного розділу треба прочитати, щоб мовчання між ними
# щось означало. На двох це збіг, на трьох — уже поведінка.
MIN_PAGES_FOR_TOPIC = 3

# Скільки адрес показуємо переліком у доказах.
MAX_LISTED_PAGES = 6


@register
class TopicIslandsCheck(Check):
    """Сторінки однієї теми не посилаються одна на одну.

    Розділ на кшталт /blog чи /services — це заявка сайту на тему. Якщо
    сторінки всередині нього ніколи не згадують сусідніх, тема лишається
    набором окремих аркушів: відвідувач після першої статті йде нікуди, а
    для пошуку й для асистента сайт виглядає як розсип одноразових
    сторінок, а не як джерело з глибиною.

    Судимо лише про прочитане і лише про посилання, які бачили самі.
    Посилання на сусіда, якого ми не відкривали, теж рахується: адресу
    видно в розмітці, і читати ціль для цього не треба.

    Знахідка навмисно слабка. Сторінки теми можуть бути звʼязані через
    сторінку-перелік, і тоді дістатися від однієї до іншої все-таки можна
    за два кроки. Відрізнити такий перелік від звичайного меню нашими
    даними не виходить: спроба шукати спільну ціль посилань дала на
    backlinko.com сімдесят шість «хабів», і всі вони були шапкою сайту.
    Тому твердження тут — лише те, що ми бачили: сторінки однієї теми не
    згадують одна одну. Це привід додати звʼязки, а не привід кричати.
    """

    code = "seo.topic_islands"
    module = Module.SEO
    severity = Severity.LOW
    weight = 1
    effort = Effort.MEDIUM
    confidence = Confidence.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for topic, pages in _topics(ctx).items():
            if any(_links_to_a_sibling(page, pages) for page in pages):
                continue
            # Сторінка без жодного внутрішнього посилання — це інша
            # проблема (найчастіше рендер), і плутати їх не можна.
            if not any(any(link.is_internal for link in p.links) for p in pages):
                continue
            yield self.issue(
                params={"count": len(pages)},
                evidence={
                    "topic": topic,
                    "pages": [p.url for p in pages][:MAX_LISTED_PAGES],
                    "internal_links_each": [
                        sum(1 for link in p.links if link.is_internal) for p in pages
                    ][:MAX_LISTED_PAGES],
                    "sibling_links": 0,
                },
                page_url=pages[0].url,
            )


def _topics(ctx: SiteContext) -> dict[str, list[PageSignals]]:
    """Групи сторінок, які сайт подає як одну тему.

    Ключ — розділ адреси, якщо він є. Якщо немає, групуємо за типом
    сторінки: чимало сайтів тримають усі статті в корені (`/audience-
    research`, `/product-page-examples`), і вимагати від них теки `/blog`
    означало б перевіряти домовленість про адреси замість структури.
    """
    grouped: dict[str, list[PageSignals]] = {}
    for page in ctx.ok_pages:
        kind = ctx.type_of(page)
        if kind not in BUILDS_A_TOPIC:
            continue
        # Розділ береться лише тоді, коли з нього можна назвати тему.
        # `/2024/05/31/slug/` і `/911/carrera` з адреси не розрізнити,
        # тож про такий сегмент ми просто мовчимо: сторінка групується за
        # типом, як і ті, що лежать у корені. Це відмова від твердження,
        # а не висновок про будову чужої CMS.
        section = section_of(page.url)
        if not is_safe_topic_section(section):
            section = ""
        grouped.setdefault(section or str(kind), []).append(page)
    return {key: pages for key, pages in grouped.items() if len(pages) >= MIN_PAGES_FOR_TOPIC}


def _links_to_a_sibling(page: PageSignals, topic: list[PageSignals]) -> bool:
    """Чи веде сторінка бодай на одну іншу сторінку своєї ж теми.

    Два способи це побачити, і досить будь-якого. Перший — адреса цілі в
    тому самому розділі; він працює й для сторінок, яких ми не читали.
    Другий — ціль є серед прочитаних сторінок теми; він потрібен там, де
    розділу немає й адреса нічого не каже.

    Сама сторінка й корінь розділу не рахуються: посилання на «всі
    статті» є в кожному шаблоні й не свідчить ні про що.
    """
    own = normalize(page.url)
    section = section_of(page.url)
    neighbours = {normalize(p.url) for p in topic} - {own}
    return any(
        link.is_internal
        and normalize(link.url) != own
        and (
            (bool(section) and section_of(link.url) == section)
            or normalize(link.url) in neighbours
        )
        for link in page.links
    )


@register
class RenderDeltaCheck(Check):
    """Сигнали сторінки, що розходяться між відповіддю сервера й DOM.

    ## Що це, а що ні

    Це факт, а не діагноз: «у відповіді сервера canonical один, після
    виконання JS — інший». Чому так і чи це погано, вирішує людина, яка
    знає свій сайт. Ми не стверджуємо, що Google щось проігнорує: Google
    рендерить, але відкладено — його документація каже, що сторінка
    «may stay on this queue for a few seconds, but it can take longer».
    І та сама документація нагадує: «not all bots can run JavaScript».

    ## Чому знахідка інформаційна

    `severity=INFO` і `weight=0` дають рівно нуль штрафу, тож бал не
    рухається: база скорингу заморожена, а нова знахідка, що спрацьовує
    на кожному SPA, зсунула б історію всіх аудитів. Факт при цьому
    потрапляє у звіт із повним доказом, і коли настане фаза калібрування,
    буде на чому вирішувати, скільки це має коштувати.

    Найгостріший випадок — `index` у відповіді проти `noindex` після
    рендеру — теж поки інформаційний. Це компроміс із замороженим
    скорингом, а не оцінка важливості; він винесений у звіт окремо.

    ## Одна знахідка на сторінку

    Заголовок бере найважливішу групу з тих, що змінилися; решта лежить
    у доказі повністю. Чотири знахідки про одну сторінку читалися б як
    чотири проблеми, хоча причина зазвичай одна.
    """

    code = "seo.render_delta"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.MEDIUM
    messages = (
        "seo.render_delta.indexing",
        "seo.render_delta.identity",
        "seo.render_delta.markup",
        "seo.render_delta.links",
    )

    # Порядок = важливість. Спершу те, що керує індексацією, потім те, як
    # сторінка себе називає, потім розмітка, потім навігація.
    GROUPS: ClassVar[tuple[tuple[str, tuple[str, ...]], ...]] = (
        ("indexing", ("meta_robots", "canonical")),
        ("identity", ("title", "h1", "meta_description")),
        ("markup", ("jsonld",)),
    )

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for diff in render_diff.compare_all(ctx):
            # `changed` хибний і тоді, коли різниці немає, і тоді, коли
            # порівнювати не було чим. Друге твердженням про сторінку не є.
            if not diff.changed:
                continue

            changed = set(diff.field_names())
            group = "links"
            fields: list[str] = []
            for name, members in self.GROUPS:
                hit = [f for f in members if f in changed]
                if hit:
                    group, fields = name, hit
                    break

            params: dict[str, object] = (
                {"count": len(diff.links.only_after_render)}
                if group == "links"
                else {"fields": ", ".join(fields)}
            )
            evidence = diff.as_evidence()
            # Скільки з побачених лише після рендеру адрес ми потім
            # справді прочитали. Це не друга знахідка про те саме, а
            # відповідь на питання, яке знахідка породжує: «і що, ці
            # сторінки взагалі існують?». Обидві половини лежать у
            # знімку, тож доказ відтворюється й на перерахунку.
            only_after = diff.links.only_after_render
            if only_after:
                read = {normalize(page.url) for page in ctx.ok_pages}
                evidence["links"] = {
                    **evidence.get("links", {}),
                    "only_after_render_crawled": sum(
                        1 for url in only_after if normalize(url) in read
                    ),
                }
            yield self.issue(
                msg=f"seo.render_delta.{group}",
                params=params,
                evidence=evidence,
                page_url=diff.url,
            )


# ── Мовні версії ──────────────────────────────────────────────────────────
#
# ## Чому вся родина інформаційна
#
# `severity=INFO` і `weight=0` дають рівно нуль штрафу. Це не оцінка
# важливості: помилка в hreflang цілком реальна, і Google документує, що
# робить із нею. Це наслідок замороженої бази скорингу.
#
# Заморозка стосується формули, і додавати ваговиті чеки правила не
# забороняють. Але вимірювання сказало інше: на fastapi.tiangolo.com нові
# знахідки рухали SEO на девʼять балів, а до придушення похідних — на
# сімнадцять. Аудит, зроблений учора, і аудит, зроблений сьогодні, дали б
# різні бали одному сайту без жодної зміни на ньому, і історія скорів
# перестала б читатися через цю межу. Ваги, підібрані на одному
# багатомовному сайті, такої ціни не варті.
#
# Тому знахідки, докази, рекомендації й звіт працюють повністю, а коштує
# це поки нуль. Скільки має коштувати — рішення фази калібрування (§K.4
# звірки покриття), яке приймається на розподілі, а не на інтуїції. Той
# самий компроміс, що й у `seo.render_delta`.
#
# Уся родина мовчить на сайті, який не оголосив жодної версії: одномовний
# сайт нічого не порушує, і зауваження йому було б чистим шумом. Виняток
# один — `seo.hreflang_missing`, і він якраз про те, що сайт схожий на
# багатомовний, а оголошень немає ніде.
#
# Збір і нормалізація живуть в `app/audit/hreflang.py`: три механізми
# оголошення (HTML, заголовок HTTP, карта сайту) Google називає
# рівноцінними, тож перевіряти можна лише їхнє обʼєднання.


@register
class HreflangInvalidCheck(Check):
    """Значення, якого Google не прийме.

    Граматика вужча за BCP 47 і описана в самій документації Google:
    мова за ISO 639-1, необовʼязкове письмо за ISO 15924, необовʼязковий
    регіон за ISO 3166-1 Alpha 2 — саме в такому порядку, — плюс
    зарезервоване `x-default`. Тому `zh-Hant` і `zh-Hans-US` дійсні, а
    `en_US`, `en-UK` і `en-US-Latn` — ні.

    Помилка тиха: сторінка виглядає налаштованою, у вихідному коді все
    на місці, а анотація не працює. Найчастіше туди кладуть код країни
    замість мови — `gb` замість `en-GB`, — і про це каталог каже окремо.
    """

    code = "seo.hreflang_invalid"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        site = hreflang.collect(ctx)
        if not site.used:
            return
        for page in ctx.ok_pages:
            declaration = site.declaration(page.url)
            if declaration is None or not declaration.invalid:
                continue
            bad = declaration.invalid
            yield self.issue(
                params={
                    "count": len(bad),
                    "values": ", ".join(a.tag.raw for a in bad),
                },
                evidence={
                    "invalid": [a.as_evidence() for a in bad],
                    "declared_versions": len(declaration.annotations),
                    "sources": [s.value for s in declaration.sources],
                    "grammar": language_tags.SOURCES["google_hreflang"],
                },
                page_url=page.url,
            )


@register
class HreflangReciprocityCheck(Check):
    """Оголошення, на які ніхто не відповів взаємністю.

    Google вимагає двох речей: сторінка називає саму себе, і кожна
    названа сторінка називає її у відповідь. Без першого набір неповний;
    без другого Google може проігнорувати анотації обох сторін.

    Друге твердження ми робимо обережно. «Сторінка B не посилається
    назад» можна стверджувати лише про B, яку ми відкривали самі: решту
    цілей краул міг просто не встигнути. Тому в тексті стоїть, скільки
    цілей перевірено з оголошених, а `Reciprocity.complete` каже, чи
    покриття повне. Мовчання про решту — це «не дивилися», а не «все
    гаразд».
    """

    code = "seo.hreflang_reciprocity"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.MEDIUM
    variants = ("self", "return")
    messages = (
        "seo.hreflang_reciprocity.self",
        "seo.hreflang_reciprocity.return",
    )

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        site = hreflang.collect(ctx)
        if not site.used:
            return
        for page in ctx.ok_pages:
            declaration = site.declaration(page.url)
            if declaration is None or not declaration.declared:
                continue
            # Набір, який сам собі суперечить, Google може відкинути
            # цілком — а повноту відкинутого набору судити нема сенсу.
            # Це не поблажка: на fastapi.tiangolo.com одна помилка
            # шаблону (усі тринадцять версій позначені `en`) давала три
            # знахідки й забирала 17 балів SEO, хоча правка одна. Про
            # суперечність скаже `seo.hreflang_conflict`, і поки її не
            # усунуто, відповідь про взаємність нам просто нізвідки взяти.
            if site.conflicts(declaration):
                continue

            if declaration.self_reference() is None:
                yield self.issue(
                    key="self",
                    msg="seo.hreflang_reciprocity.self",
                    params={"count": len(declaration.annotations)},
                    evidence=declaration.as_evidence(),
                    page_url=page.url,
                )

            back = site.reciprocity(declaration)
            if back.missing:
                yield self.issue(
                    key="return",
                    msg="seo.hreflang_reciprocity.return",
                    params={
                        "count": len(back.missing),
                        "checked": back.checked,
                        "declared": back.declared,
                    },
                    evidence={**declaration.as_evidence(), **back.as_evidence()},
                    page_url=page.url,
                )


@register
class HreflangConflictCheck(Check):
    """Оголошення, які не можуть бути правдою одночасно.

    Три різні суперечності, три різні правки — тому це три варіанти, а
    не один. `duplicate`: одне значення веде на дві адреси. `x_default`:
    двоє різних «за замовчуванням». `canonical`: сторінка бере участь у
    наборі мовних версій і водночас каже пошуку, що головна не вона, —
    тоді анотації описують сторінку, яку Google не збирається показувати.

    Порожній `x-default` дефектом не є й тут не зʼявляється: він
    необовʼязковий, і вимагати його означало б вигадувати вимогу.
    """

    code = "seo.hreflang_conflict"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.MEDIUM
    variants = ("duplicate", "x_default", "canonical")
    messages = (
        "seo.hreflang_conflict.duplicate",
        "seo.hreflang_conflict.x_default",
        "seo.hreflang_conflict.canonical",
    )

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        site = hreflang.collect(ctx)
        if not site.used:
            return
        for page in ctx.ok_pages:
            declaration = site.declaration(page.url)
            if declaration is None or not declaration.declared:
                continue

            for conflict in site.conflicts(declaration):
                yield self.issue(
                    key=conflict.kind,
                    msg=f"seo.hreflang_conflict.{conflict.kind}",
                    params={"value": conflict.value, "count": len(conflict.targets)},
                    evidence={
                        **conflict.as_evidence(),
                        "page": declaration.url,
                        "sources": [s.value for s in declaration.sources],
                    },
                    page_url=page.url,
                )

            # Canonical читаємо тим самим способом, що й решта SEO-чеків —
            # після рендеру: Google виконує JS, і canonical, дописаний
            # скриптом, для нього існує.
            canonical = (ctx.as_seen(page).canonical or "").strip()
            if not canonical:
                continue
            target = normalize(urljoin(page.url, canonical))
            if target == declaration.url:
                continue
            yield self.issue(
                key="canonical",
                msg="seo.hreflang_conflict.canonical",
                params={"canonical": canonical},
                evidence={
                    "page": declaration.url,
                    "canonical": canonical,
                    "canonical_normalized": target,
                    "declared_versions": len(declaration.annotations),
                    "sources": [s.value for s in declaration.sources],
                },
                page_url=page.url,
            )


@register
class HreflangBrokenTargetCheck(Check):
    """Мовна версія, яку ми відкривали й не отримали придатної сторінки.

    Тільки про адреси, куди краул справді сходив: цілі, яких ми не
    торкались, тут не згадуються взагалі. Відповідь сервера й `noindex` —
    це не здогад, а прочитане, тож знахідка тримається на власних очах.

    Дві причини й дві правки: адреса не відповідає — виправляють
    посилання; адреса закрита від індексації — прибирають `noindex` або
    прибирають її з набору.
    """

    code = "seo.hreflang_broken"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW
    variants = ("unreachable", "noindex")
    messages = (
        "seo.hreflang_broken.unreachable",
        "seo.hreflang_broken.noindex",
    )

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        site = hreflang.collect(ctx)
        if not site.used:
            return
        seen = {normalize(p.url): p for p in ctx.pages}
        for page in ctx.ok_pages:
            declaration = site.declaration(page.url)
            if declaration is None or not declaration.declared:
                continue

            dead: list[dict[str, object]] = []
            closed: list[dict[str, object]] = []
            for annotation in declaration.annotations:
                other = seen.get(annotation.target)
                if other is None:
                    continue
                status = other.status_code
                if status is not None and not 200 <= status < 300:
                    dead.append({"value": annotation.tag.raw, "target": annotation.target,
                                 "status": status})
                elif "noindex" in (other.meta_robots or ""):
                    closed.append({"value": annotation.tag.raw, "target": annotation.target,
                                   "meta_robots": other.meta_robots})

            if dead:
                yield self.issue(
                    key="unreachable",
                    msg="seo.hreflang_broken.unreachable",
                    params={"count": len(dead)},
                    evidence={"targets": dead, "page": declaration.url},
                    page_url=page.url,
                )
            if closed:
                yield self.issue(
                    key="noindex",
                    msg="seo.hreflang_broken.noindex",
                    params={"count": len(closed)},
                    evidence={"targets": closed, "page": declaration.url},
                    page_url=page.url,
                )


# Скільки сторінок треба прочитати, щоб узагалі судити про мови сайту.
# На двох сторінках різні `lang` частіше означають помилку шаблону, ніж
# другу мовну версію.
MIN_PAGES_TO_JUDGE_LANGUAGES = 4


@register
class HreflangMissingCheck(Check):
    """Сайт віддає сторінки різними мовами й не каже, що це версії однієї.

    Єдиний чек родини, який спрацьовує за відсутності оголошень, — і
    тому єдиний, який спирається на здогад. Ми бачимо `lang` різних
    базових мов на прочитаних сторінках; що це саме переклади одного
    вмісту, а не окремі розділи різними мовами, ми не бачимо. Звідси
    середня впевненість і низька серйозність.

    Порівнюється базова мова, а не повне значення: `en-US` і `en-GB` —
    одна мова, і вимагати від них hreflang через саму лише різницю
    регіону було б хибним спрацюванням.
    """

    code = "seo.hreflang_missing"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.MEDIUM
    confidence = Confidence.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        pages = ctx.ok_pages
        # Стверджувати відсутність можна лише там, де ми дивилися.
        if not ctx.hreflang_observed or len(pages) < MIN_PAGES_TO_JUDGE_LANGUAGES:
            return
        if hreflang.collect(ctx).used:
            return

        by_language: dict[str, list[str]] = {}
        for page in pages:
            tag = language_tags.parse(page.lang or "")
            if tag.language is None:
                continue
            by_language.setdefault(tag.language, []).append(page.url)
        if len(by_language) < 2:
            return

        yield self.issue(
            params={
                "count": len(by_language),
                "languages": ", ".join(sorted(by_language)),
            },
            evidence={
                "languages": {lang: urls[:5] for lang, urls in sorted(by_language.items())},
                "pages_read": len(pages),
                # Три місця, де оголошення могло би бути. Жодного не знайшли.
                "checked_sources": [s.value for s in hreflang.Source],
            },
        )


# ── Перенаправлення ───────────────────────────────────────────────────────
#
# Дані збиралися давно й не читалися: `PageSignals.redirect_chain` лежав
# без жодного чека. Тут вони стають твердженнями — розбір ланцюга живе в
# `app/audit/redirects.py` і про серйозність нічого не знає.
#
# ## Чому вся родина інформаційна
#
# `severity=INFO`, `weight=0` — рівно нуль штрафу. База скорингу
# заморожена, а нова здатність не має рухати бали сайтів, зняті до неї:
# інакше два аудити по різні боки випуску стають непорівнянними. Скільки
# це має коштувати — рішення фази калібрування (§K.4 звірки покриття).
# Той самий компроміс, що в `seo.render_delta` і родини hreflang.
#
# ## Чого ці чеки не кажуть
#
# Що редирект знижує позиції. Google цього не стверджує, а ми не міряли.
# Захищати можна лише те, що видно: кожен зайвий крок — це ще один
# запит, а ланцюг, який не дійшов до кінця, не віддає сторінки взагалі.

# Скільки переходів вважаємо звичайною справою. Один — це http → https
# або стара адреса на нову, і воно цілком доречне. Попереджати про таке
# означало б лаяти правильно налаштований сайт.
NORMAL_REDIRECTS = 1


@register
class RedirectChainCheck(Check):
    """Шлях до сторінки довший за один крок.

    Довжина рахується в нормалізованих адресах: `/a` → `/a/` — нуль
    змістовних переходів, а не один. Інакше ми вигадували б клієнтові
    складність, якої в нього немає.

    Якщо на початкову адресу веде внутрішнє посилання, воно потрапляє в
    доказ: саме там і лежить дія — виправити посилання на кінцеву
    адресу, а не чіпати самі правила перенаправлень.
    """

    code = "seo.redirect_chain"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for chain in redirects.chains(ctx.ok_pages):
            if chain.length <= NORMAL_REDIRECTS:
                continue
            evidence = chain.as_evidence()
            linked_from = _links_to(ctx, chain.source)
            if linked_from:
                evidence["linked_from"] = linked_from
            yield self.issue(
                params={"count": chain.length},
                evidence=evidence,
                page_url=chain.final_url,
            )


@register
class RedirectLoopCheck(Check):
    """Шлях, який не веде до сторінки.

    Два різні твердження, і плутати їх не можна. `repeated` — адреса
    трапилась у ланцюзі двічі, ланцюг завершився, обидва входження ми
    бачили. `limit` — ми спинилися на межі перенаправлень і не дійшли до
    кінця; історії httpx при цьому не віддає, тож де саме крутилося й чи
    крутилося взагалі, ми не знаємо.

    Назвати друге петлею було б припущенням замість спостереження.
    """

    code = "seo.redirect_loop"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.MEDIUM
    variants = ("repeated", "limit")
    messages = ("seo.redirect_loop.repeated", "seo.redirect_loop.limit")
    # Сторінки тут немає взагалі, тож судити прочитане нічим.
    reads_content = False

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for chain in redirects.chains(ctx.ok_pages):
            if not chain.repeated:
                continue
            yield self.issue(
                key="repeated",
                msg="seo.redirect_loop.repeated",
                params={"count": len(chain.repeated)},
                evidence={**chain.as_evidence(), "repeated": list(chain.repeated)},
                page_url=chain.final_url,
            )

        for url in ctx.redirect_limited:
            yield self.issue(
                key="limit",
                msg="seo.redirect_loop.limit",
                params={"url": url, "followed": MAX_REDIRECTS_FOLLOWED},
                evidence={
                    "url": url,
                    # Скільки кроків ми готові пройти, перш ніж спинитись.
                    "followed": MAX_REDIRECTS_FOLLOWED,
                    # Чого ми НЕ знаємо — і чому не кажемо «петля».
                    "chain_available": False,
                },
            )


@register
class RedirectTargetCheck(Check):
    """Перенаправлення веде туди, звідки сторінки не отримати.

    Найдорожчий випадок родини й найпростіший для доказу: код відповіді
    ми прочитали самі. Причина зазвичай не в самому редиректі, а в тому,
    що адресу призначення прибрали пізніше за правило.
    """

    code = "seo.redirect_target"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for chain in redirects.chains(ctx.pages):
            if not chain.lands_badly:
                continue
            evidence = chain.as_evidence()
            linked_from = _links_to(ctx, chain.source)
            if linked_from:
                evidence["linked_from"] = linked_from
            yield self.issue(
                params={"status": chain.final_status},
                evidence=evidence,
                page_url=chain.final_url,
            )


# Скільки перенаправлень поспіль проходить fetcher, перш ніж спинитись.
# Значення httpx-клієнта; тримається поруч із чеком, бо саме воно
# пояснює клієнтові, звідки взялося число в доказі.
MAX_REDIRECTS_FOLLOWED = 5


def _links_to(ctx: SiteContext, url: str) -> list[str]:
    """Прочитані сторінки, які посилаються на цю адресу.

    Береться з уже зібраних `page.links` — того самого джерела, з якого
    будується граф. Другого графа тут не заводимо: питання вузьке, і
    відповідь на нього не потребує ані ваг, ані обходу.
    """
    wanted = normalize(url)
    return [
        page.url
        for page in ctx.ok_pages
        if any(link.is_internal and normalize(link.url) == wanted for link in page.links)
    ][:10]


# ── Узгодженість карти сайту ──────────────────────────────────────────────


@register
class SitemapConsistencyCheck(Check):
    """Карта заявляє адресу, а ми за нею побачили щось інше.

    ## Чим це не є

    Це не твердження про індексацію. Наявність адреси в карті нічого не
    гарантує, а відсутність нічого не забороняє — Google описує карту як
    підказку, не як команду. Тут лише неузгодженість двох джерел на
    самому сайті: заявки власника і того, що віддав його ж сервер.

    ## Одна знахідка на причину, а не на адресу

    Карта на пʼять тисяч адрес із двомастами перенаправленнями — це одна
    робота, а не двісті. Тому знахідка одна на причину, а перелік адрес
    лежить у доказі. Причина в кожної адреси теж одна: сторінка буває
    водночас `noindex` і з canonical на іншу, але корінь у цього один, і
    дві знахідки описували б одну дію двічі.

    ## Чому це не дублює наявні чеки

    `seo.noindex` каже «ця сторінка закрита від пошуку» і питає, чи так
    задумано. Тут інше твердження: «ви самі просите її знайти й самі ж її
    закрили». Дія теж інша — прибрати адресу з карти або зняти заборону,
    а не переглянути заборону саму по собі. Те саме з перенаправленнями:
    `seo.redirect_chain` про шлях, а це — про те, що в карті стоїть не та
    адреса, якою все закінчується.

    ## Чому інформаційний

    `severity=INFO`, `weight=0`. База скорингу заморожена, а нова
    здатність не має рухати бали, зняті до неї. Ціна — рішення фази
    калібрування (§K.4 звірки покриття).
    """

    code = "seo.sitemap_consistency"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW
    variants = tuple(r.value for r in sitemap_audit.ORDER)
    messages = tuple(f"seo.sitemap_consistency.{r.value}" for r in sitemap_audit.ORDER)

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        audit = sitemap_audit.collect(ctx)
        if not audit.entries:
            return
        coverage = audit.coverage()
        for reason, entries in audit.by_reason().items():
            yield self.issue(
                key=reason.value,
                msg=f"seo.sitemap_consistency.{reason.value}",
                params={
                    "count": len(entries),
                    "checked": audit.checked,
                    "declared": audit.declared,
                },
                evidence={
                    # Межі звірки — поруч із висновком, а не в примітці:
                    # «карта чиста» на 20 прочитаних із 20 000 було б
                    # неправдою про сайт.
                    **coverage,
                    "reason": reason.value,
                    "urls": [e.as_evidence() for e in entries[:20]],
                    "urls_total": len(entries),
                },
            )


# ── Текст внутрішніх посилань ─────────────────────────────────────────────


@register
class AnchorTextCheck(Check):
    """Той самий беззмістовний текст веде на різні сторінки.

    ## Що саме стверджується

    Не «загальний текст шкодить позиціям» — Google цього не каже, а ми не
    міряли. Твердження вужче й перевірне: коли десяток посилань підписані
    однаково («Дізнатися більше»), а ведуть у різні місця, підпис не
    каже читачеві нічого про те, куди він потрапить.

    ## Чому саме кілька цілей

    Поріг тут не з голови. Одне «читати далі» на одну сторінку — це
    питання стилю, і знахідка про нього була б причіпкою. Двозначність
    зʼявляється рівно тоді, коли за тим самим підписом ховаються різні
    адреси: саме тоді підпис перестає розрізняти. Умова збігається з
    твердженням, а не підібрана до бажаної кількості спрацювань.

    ## Де ми не судимо

    Меню й підвал — `in_chrome`; сторінки, мову яких не встановили;
    мови, для яких у нас немає переліку. Порожній текст посилання сюди
    теж не входить, і це не недогляд: пояснення в `anchor_text`.

    ## Чому інформаційний

    `severity=INFO`, `weight=0` — нуль штрафу. База скорингу заморожена,
    а чи має це коштувати балів, вирішує фаза калібрування (§K.4).
    """

    code = "seo.anchor_text"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW

    # Скільки різних цілей робить підпис двозначним. Менше — це стиль,
    # а не дефект, і про стиль ми клієнта не повчаємо.
    AMBIGUOUS_FROM = 2

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        analysis = anchor_text.analyse(ctx)
        if not analysis.weak:
            return
        phrases = [
            row
            for row in analysis.by_phrase()
            if int(row["destinations"]) >= self.AMBIGUOUS_FROM
        ]
        if not phrases:
            return
        yield self.issue(
            params={
                "count": len(phrases),
                "links": sum(int(row["links"]) for row in phrases),
            },
            evidence={
                **analysis.coverage(),
                "phrases": phrases,
                "phrases_total": len(phrases),
            },
        )


# ── Однаковий вміст під різними адресами ──────────────────────────────────


@register
class DuplicateContentCheck(Check):
    """Кілька адрес віддають той самий вміст.

    ## Що стверджується, а що ні

    Не «дублікати шкодять позиціям». Google прямо пише, що дублікати —
    звичайна річ і порушенням правил не є, що він групує схожі сторінки
    сам і що обраний ним представник може не збігтися з вашим. Ми не
    знаємо, кого він обрав, і не вгадуємо. Твердження вужче: ці адреси
    віддали однаковий вміст, і сайт не сказав, яка з них головна.

    ## Чому лише точні збіги

    Близька подібність вимірюється, але знахідкою не стає. На вибірці
    поріг 0.7 давав `fastapi.tiangolo.com/about/` проти `/newsletter/`
    з 0.944 — і це не дублікати, а дві майже порожні сторінки, чий текст
    складається з бічної панелі. Поки головний вміст не виділяється
    надійно, поріг означав би «однакова навігація». Точний збіг порога
    не потребує взагалі. Подробиці — в `app/audit/duplicates.py`.

    ## Дві різні розмови

    `unconsolidated` — сайт ніде не сказав, яка адреса головна.
    `conflicting` — сказав, але суперечливо: учасники вказують на різне
    або поза кластер. Кластер, де всі узгоджено вказують на одного,
    знахідкою не стає взагалі: це і є правильно налаштована
    консолідація.

    ## Чому інформаційний

    `severity=INFO`, `weight=0`. База скорингу заморожена, а чи мають
    точні збіги коштувати балів — питання фази калібрування (§K.4).
    """

    code = "seo.duplicate_content"
    module = Module.SEO
    severity = Severity.INFO
    weight = 0
    effort = Effort.MEDIUM
    variants = ("unconsolidated", "conflicting")
    messages = ("seo.duplicate_content.unconsolidated", "seo.duplicate_content.conflicting")

    # Скільки кластерів показуємо. Числа поруч завжди повні.
    SHOWN = 5
    # Скільки індексованих учасників робить кластер вартим розмови.
    # Менше — сайт уже сам прибрав зайве з пошуку.
    MIN_INDEXABLE = 2

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        analysis = duplicates.analyse(ctx)
        actionable = [
            cluster
            for cluster in analysis.clusters
            if len(cluster.indexable_members) >= self.MIN_INDEXABLE
        ]
        if not actionable:
            return

        groups: dict[str, list[Any]] = {"unconsolidated": [], "conflicting": []}
        for cluster in actionable:
            state = cluster.consolidation
            if state is duplicates.Consolidation.CONSISTENT:
                # Сайт сам звів їх до одного представника — це не вада.
                continue
            key = "conflicting" if state is duplicates.Consolidation.CONFLICTING else (
                "unconsolidated"
            )
            groups[key].append(cluster)

        coverage = analysis.coverage()
        for variant, clusters in groups.items():
            if not clusters:
                continue
            shown = clusters[: self.SHOWN]
            evidence: dict[str, Any] = {
                **coverage,
                "clusters": [c.as_evidence() for c in shown],
                "clusters_total": len(clusters),
                "pages_affected": sum(len(c.indexable_members) for c in clusters),
                # Близька подібність поруч як вимірювання, а не знахідка.
                "near_duplicate_pairs_measured": len(analysis.near),
            }
            if len(shown) < len(clusters):
                evidence["clusters_truncated"] = True
            yield self.issue(
                key=variant,
                msg=f"seo.duplicate_content.{variant}",
                params={"count": len(clusters), "pages": evidence["pages_affected"]},
                evidence=evidence,
            )
