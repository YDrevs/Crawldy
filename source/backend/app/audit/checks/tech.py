"""Захист, аналітика та інфраструктура.

Усе тут читається із заголовків відповіді або зі статичного HTML —
жодних додаткових запитів, окрім двох проб у collect_infra.
"""

from __future__ import annotations

from collections.abc import Iterable
from urllib.parse import urljoin, urlsplit

from app.audit import form_protection, mixed_content, transport
from app.audit.checks.base import Check, register
from app.audit.demo_content import detect as detect_demo_content
from app.audit.site_scope import CRAWLABLE_SCHEMES, same_site
from app.audit.standards import analytics_vendors
from app.audit.types import (
    Confidence,
    Effort,
    FormSignals,
    Issue,
    Module,
    PageSignals,
    Severity,
    SiteContext,
)

# Заголовки з розділу «security headers» специфікації. HSTS перевіряється
# окремо в seo.https, тому тут його немає — двічі карати за одне не можна.
SECURITY_HEADERS = (
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
)

# Без цих двох сайт неможливо ані виміряти, ані діагностувати.
#
# «Скільки людей прийшло» вміє рахувати будь-що з першого списку. «Що
# людина робила на сторінці» — лише інструменти запису сесій і теплових
# карт із другого.
#
# Перелік береться з реєстру вендорів, а не дублюється тут: два переліки
# розійшлись би на першому ж новому вендорі. `first_party` у ньому немає
# взагалі — мітка «власний лічильник» більше не вендор, а невпізнане
# вимірювання зі своїм видом доказу (E-11b, E-11c).
CORE_ANALYTICS = analytics_vendors.MEASUREMENT_VENDORS
BEHAVIOUR_ANALYTICS = (
    "microsoft_clarity", "hotjar", "fullstory", "logrocket", "pendo",
    "posthog", "heap",
)


def security_header_gaps(page: PageSignals) -> tuple[list[str], dict[str, str]]:
    """Яких захисних заголовків бракує на відповіді — з еквівалентами.

    Одна функція для чека і для звіту: «повний набір» у розділі
    пройдених перевірок мусить означати рівно те саме, що «нічого не
    бракує» у детекторі, інакше два місця розійдуться на першому ж
    еквіваленті.

    * CSP frame-ancestors — повноцінна заміна X-Frame-Options (MDN);
    * x-content-type-options рахується лише зі значенням nosniff.
    """
    enforced_csp = page.header("content-security-policy") or ""
    missing: list[str] = []
    invalid: dict[str, str] = {}
    for name in SECURITY_HEADERS:
        value = page.header(name)
        if name == "x-frame-options" and value is None:
            if "frame-ancestors" in enforced_csp.lower():
                continue
        if name == "x-content-type-options" and value is not None:
            if "nosniff" not in value.lower():
                invalid[name] = value
                missing.append(name)
                continue
        if value is None:
            missing.append(name)
    return missing, invalid


def _home_or_first(ctx: SiteContext) -> PageSignals | None:
    return ctx.home if ctx.home is not None else (ctx.ok_pages[0] if ctx.ok_pages else None)


@register
class SecurityHeadersCheck(Check):
    """Браузерні захисні заголовки — гігієна, а не видимість.

    Crawldy міряє Search і AI Visibility, а ці заголовки — механізми
    захисту браузера (OWASP), і на ранжування вони не впливають. На
    night3 чек спрацьовував на 96.4% сайтів, з них HIGH на 50.9% — тобто
    половина всіх звітів несла «серйозну» знахідку, яка не розрізняє
    нікого й не стосується предмета продукту. Тому INFO і вага 0:
    можливість для розробника, а не дефект видимості.

    Відсутній заголовок — не доказ вразливості, і навпаки: наявний — не
    гарантія захисту. Ми кажемо лише те, що бачили у ВІДПОВІДІ ОДНІЄЇ
    сторінки, і формулювання це називає.
    """

    code = "tech.security_headers"
    module = Module.TECH
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW
    messages = ("tech.security_headers.missing", "tech.security_headers.none")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        page = _home_or_first(ctx)
        if page is None or not page.headers:
            # Заголовків відповіді немає в доказах — це «не знаємо»,
            # а не «бракує». Відсутності без погляду не стверджуємо.
            return

        report_only = page.header("content-security-policy-report-only")
        missing, invalid = security_header_gaps(page)
        if not missing:
            return

        everything = len(missing) == len(SECURITY_HEADERS)
        evidence: dict[str, object] = {
            "missing": missing,
            "present": [h for h in SECURITY_HEADERS if h not in missing],
            "checked_url": page.url,
        }
        if invalid:
            evidence["invalid_values"] = invalid
        if report_only and "content-security-policy" in missing:
            # Report-only не блокує нічого — це телеметрія, а не захист.
            # Але факт, що сайт уже щось налаштував, вартий згадки.
            evidence["report_only_csp_present"] = True
        yield self.issue(
            msg="tech.security_headers.none" if everything else "tech.security_headers.missing",
            params={"count": len(missing), "headers": ", ".join(missing)},
            evidence=evidence,
            page_url=page.url,
        )


@register
class CrawlerBlockedCheck(Check):
    """Сайт відмовляє нашому агенту в доступі.

    Читає ctx.pages, а не ok_pages: саме тут потрібні сторінки, які
    контенту не віддали. Це єдиний чек, який працює, коли не працює
    жоден інший, — інакше блокування виглядало б як чистий сайт.
    """

    code = "tech.crawler_blocked"
    module = Module.TECH
    severity = Severity.CRITICAL
    weight = 5
    effort = Effort.MEDIUM
    messages = ("tech.crawler_blocked",)

    BLOCKING_STATUSES = (401, 403, 405, 406, 429, 503)

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        if ctx.ok_pages or not ctx.pages:
            return
        blocked = [p for p in ctx.pages if p.status_code in self.BLOCKING_STATUSES]
        if not blocked:
            return
        statuses = sorted({p.status_code for p in blocked if p.status_code})
        yield self.issue(
            params={"status": statuses[0] if statuses else 403},
            evidence={
                "statuses": statuses,
                "urls": [p.url for p in blocked][:5],
                "pages_attempted": len(ctx.pages),
            },
            page_url=blocked[0].url,
        )


@register
class AnalyticsCheck(Check):
    """Чи вимірює сайт відвідування.

    Severity залежить від того, чи бачили ми сторінку після виконання JS.
    Лічильник, вставлений при гідрації (так робить Vercel зі своїм
    /_vercel/insights, а Linear — PostHog), у статичному HTML невидимий
    у принципі. Без рендеру ми можемо сказати лише «не знайшли», і це
    твердження про межі нашого зору, а не про сайт.
    """

    code = "tech.analytics"
    module = Module.TECH
    severity = Severity.MEDIUM
    weight = 3
    effort = Effort.LOW
    messages = ("tech.analytics.missing", "tech.analytics.unconfirmed")
    variants = ("missing",)

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        if not ctx.ok_pages:
            return
        state = ctx.analytics_classification()
        if state.measurement:
            return

        # Невпізнане вимірювання — не доказ відсутності. Сайт, який шле
        # події на власний `/api/collect`, щось міряє; ми лише не можемо
        # назвати чим. Це той самий нейтральний текст `unconfirmed`, що й
        # без рендеру, і ніколи не HIGH (E-11).
        unresolved = bool(state.unidentified)
        categorical = state.rendered and not unresolved
        yield self.issue(
            key="missing",
            msg="tech.analytics.missing" if categorical else "tech.analytics.unconfirmed",
            evidence={
                "found": state.verified,
                "checked_after_render": state.rendered,
                "kind": state.kind.value,
                "verdict": state.verdict,
                "coverage": state.coverage,
                "observations": state.evidence(),
                "unidentified": state.unidentified_evidence(),
            },
            severity=Severity.HIGH if categorical else Severity.MEDIUM,
        )
        return
        # Раніше тут була знахідка «немає теплових карт і запису сесій».
        # Людська валідація визнала її поза обсягом продукту: сайт із
        # first-party аналітикою, GA і GTM отримував зауваження за
        # відсутність Hotjar, хоча для видимості в пошуку й для моделей
        # запис сесій не потрібен. INFO рятувало від математичної шкоди,
        # але не від продуктової — кожна зайва знахідка робить аудит
        # галасливішим і менш переконливим.
        #
        # Сам факт лишається у сигналах (`ctx.analytics_found`) для тих
        # чеків, яким він справді потрібен; окремої знахідки більше
        # немає. Розширювати Crawldy у CRO-аудит лише тому, що сигнал
        # легко зловити, не будемо.


@register
class FormProtectionCheck(Check):
    """Форми звертання: вузьке спостереження замість вироку.

    За HTML неможливо довести, що форма незахищена: перевірка може жити
    на сервері, у WAF, у rate limiting чи в невидимій reCAPTCHA v3 без
    жодного сліду в розмітці (Google і Cloudflare самі вимагають
    серверної перевірки токена — віджет без неї нічого не захищає).
    Тому активний варіант стверджує рівно побачене: у самій формі в
    статичній відповіді не видно клієнтських маркерів анти-абюзу.
    INFO без штрафу; passed-чека немає навмисно — маркер не є доказом
    захисту. Форми з action на чужому сайті мовчать: їх обробляє
    провайдер, і його механізми поза нашими доказами.

    `get_method` — інший клас: дані в адресі запиту — задокументована
    поведінка браузера, тож твердження довідне, і MEDIUM лишається.

    Історичний ключ `unprotected` вилучено з емісії: сама його назва
    стверджувала недовідне. Збережені звіти читає legacy-запис каталогу.
    """

    code = "tech.form_protection"
    module = Module.TECH
    severity = Severity.INFO
    # Дві знахідки чека мають РІЗНУ ціну, і розводить їх серйозність,
    # а не окрема вага: множник INFO дорівнює нулю, тож `weight` для
    # `no_visible_marker` не має значення взагалі.
    #
    # `no_visible_marker` — INFO, штраф нуль. Пасивний огляд не може
    # довести відсутність серверного захисту, і брати за недоведене
    # бали означало б продавати здогад. Це не тимчасовий стан.
    #
    # `get_method` — MEDIUM (множник 2) × вага 3 = 6. Форма, яка при
    # збої скрипта кладе імʼя, пошту й текст звернення в адресний
    # рядок, — доведений факт: поведінка браузера задокументована, і
    # ми бачимо метод власними очима.
    #
    # Ціну затвердив власник 4 вересня 2026 за вимірюванням на 50
    # знімках: 16 сайтів із формою заявки, 5 із них на GET, знахідка
    # спрацювала на всіх пʼятьох, хибних спрацювань нема. Зсув
    # загального бала −2…−3, модуля tech −11…−20.
    #
    # Межу видно у відбитках: `detector_version` рухається сам (вага в
    # ньому), `SCORING_RULES` піднято до 4 — див. `versions.py`.
    weight = 3
    effort = Effort.MEDIUM
    messages = (
        "tech.form_protection.no_visible_marker",
        "tech.form_protection.get_method",
    )
    variants = ("no_visible_marker", "get_method")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            lead_forms = [f for f in page.forms if _is_lead_form(f)]
            if not lead_forms:
                continue

            # Знімок, знятий до появи сканування, не бачив нічого — і не
            # має свідчити про сайт. Порожнеча там описує нас. Прапорець
            # читається зі СТОРІНКИ: він єдиний, який є і тоді, коли форм
            # не знайшлося.
            if not page.forms_scanned:
                continue
            observations = observe_forms(ctx, page)

            observed = []
            for observation, form in observations:
                if not _is_lead_form(form):
                    continue
                if observation.protected or observation.undetermined:
                    continue
                # Чужий action обробляє провайдер форм, невідома схема —
                # JS: в обох випадках наш доказ ні про що не свідчить.
                if observation.action_scope in ("empty", "same_site"):
                    observed.append(observation)
            if observed:
                yield self.issue(
                    key="no_visible_marker",
                    msg="tech.form_protection.no_visible_marker",
                    evidence={
                        "forms_total": len(lead_forms),
                        "forms": [entry.to_json() for entry in observed[:5]],
                        "providers_checked": list(
                            form_protection.PROVIDER_MARKERS
                        ),
                        "honeypot_names_checked": list(
                            form_protection.HONEYPOT_NAMES
                        ),
                        "markers_observed": [],
                        "observation_scope": "form_attributes",
                        "static_html_assessed": True,
                        "rendered_controls_assessed": ctx.rendered(page.url)
                        is not None,
                        "server_side_controls_assessed": False,
                        "form_submission_tested": False,
                        "csrf_assessed": False,
                        "waf_or_rate_limiting_assessed": False,
                    },
                    confidence=Confidence.MEDIUM,
                    page_url=page.url,
                )

            # Безпека методу судиться ОКРЕМО від захисту: наявність
            # Turnstile нічого не каже про те, куди браузер покладе поля.
            # Це два незалежні факти, і форма з челенджем на GET має дати
            # обидві знахідки.
            #
            # Порожній `action` знахідку більше не глушить. Колись тут
            # стояло `and f.action` з міркуванням «форму без дії
            # відправляє JS, method у неї декоративний» — і воно
            # неправильне двічі. По-перше, браузер поводиться однаково:
            # форма без дії робить GET на поточну адресу, і поля йдуть у
            # рядок адреси так само. По-друге, саме цей стан мав наш
            # власний сайт (`get` + порожня дія), тобто правило глушило
            # рівно той випадок, заради якого чек існує.
            sending_by_get = [f for f in lead_forms if f.method == "get"]
            if sending_by_get:
                yield self.issue(
                    key="get_method",
                    msg="tech.form_protection.get_method",
                    params={"count": len(sending_by_get)},
                    evidence={
                        # Порожня дія — це «на поточну адресу», а не
                        # «нікуди»: у доказі вона мусить читатись саме так.
                        "actions": [f.action or "(current page)" for f in sending_by_get][
                            :5
                        ],
                        # Заявлене окремо від спостереженого: `method="get"`
                        # написав автор, а відсутність атрибута — це
                        # значення за замовчуванням. Браузер поводиться
                        # однаково, але доказ мусить казати, що ми бачили.
                        # `None` — знімок, знятий до появи поля.
                        "method_declared": [f.method_declared for f in sending_by_get][:5],
                        "protection_independent": True,
                    },
                    severity=Severity.MEDIUM,
                    page_url=page.url,
                )


def observe_forms(
    ctx: SiteContext, page: PageSignals
) -> list[tuple[form_protection.FormObservation, FormSignals]]:
    """Форми сторінки з обох представлень: відповідь сервера і рендер.

    Turnstile і reCAPTCHA частіше домальовує скрипт, ніж віддає сервер,
    тож судити лише за статикою означало б називати незахищеною кожну
    форму, віджет якої зʼявляється після виконання JS. Форми двох
    представлень зіставляються за `identity`, а коли її немає — за
    порядком: селектор `form:nth-of-type(n)` для того й будується.
    """
    rendered = ctx.rendered(page.url)
    rendered_forms: dict[str, FormSignals] = {}
    if rendered is not None:
        for index, form in enumerate(rendered.forms):
            rendered_forms[form.identity or f"#{index}"] = form
    libraries = list(page.protection_libraries)
    if rendered is not None:
        libraries += [
            name for name in rendered.protection_libraries if name not in libraries
        ]

    out: list[tuple[form_protection.FormObservation, FormSignals]] = []
    for index, form in enumerate(page.forms):
        identity = form.identity or f"#{index}"
        observation = form_protection.FormObservation(
            identity=form.identity or f"form:nth-of-type({index + 1})",
            method=form.method,
            action_scope=_action_scope(form.action, page.url, ctx.origin),
        )
        pairs = [("static", form)]
        twin = rendered_forms.get(identity)
        if twin is not None and rendered is not None:
            pairs.append(("rendered", twin))
        for source, signals in pairs:
            for marker in signals.protection_markers:
                provider, _, exact = marker.partition(":")
                observation.signals.append(
                    form_protection.Signal(
                        provider=provider, scope="form", marker=exact, source=source
                    )
                )
            for name in signals.honeypots:
                observation.signals.append(
                    form_protection.Signal(
                        provider="honeypot", scope="form", marker=name, source=source
                    )
                )
            # Знімок, знятий старим екстрактором, несе лише булеве «маркер
            # був». Це позитивне спостереження, і зневажити його означало б
            # на перерахунку ВИГАДАТИ знахідку про форму, яку попередній
            # аудит бачив захищеною. Провайдер тоді невідомий — так і
            # написано, замість підставленої назви.
            if not signals.protection_markers and signals.has_captcha:
                observation.signals.append(
                    form_protection.Signal(
                        provider="unidentified",
                        scope="form",
                        marker="legacy_marker",
                        source=source,
                    )
                )
            if not signals.honeypots and signals.has_honeypot:
                observation.signals.append(
                    form_protection.Signal(
                        provider="honeypot",
                        scope="form",
                        marker="legacy_marker",
                        source=source,
                    )
                )
        for name in libraries:
            if name not in observation.providers:
                observation.signals.append(
                    form_protection.Signal(
                        provider=name,
                        scope="page",
                        marker="script",
                        source="rendered" if rendered is not None else "static",
                    )
                )
        out.append((observation, form))
    return out


def _action_scope(action: str, page_url: str, origin: str) -> str:
    """Куди насправді йде форма: спільне правило сайту, не префікс рядка."""
    if not action:
        return "empty"
    resolved = urljoin(page_url, action)
    if urlsplit(resolved).scheme not in CRAWLABLE_SCHEMES:
        return "unknown"
    return "same_site" if same_site(resolved, origin) else "external"


# Ознаки форми пошуку по сайту: вона є в шапці кожної сторінки й лід-формою
# не є. На вибірці з 25 сайтів саме вона давала знахідку на кожній сторінці
# gov.uk — вісім «незахищених форм» там, де форма одна й вона нешкідлива.
SEARCH_MARKERS = ("search", "пошук", "q=", "/s?", "role=\"search\"")


def _is_lead_form(form: FormSignals) -> bool:
    """Форма заявки, а не пошук і не підписка на розсилку.

    Підписка — це один email і кнопка; захищати її CAPTCHA ніхто не
    вимагає, а сидить вона у футері кожної сторінки, тож без цього
    фільтра одна форма давала знахідку на всьому сайті.
    """
    if form.field_count < 2:
        return False
    haystack = form.action.lower()
    if any(marker in haystack for marker in SEARCH_MARKERS):
        return False
    # Форма без email узагалі не схожа на спосіб залишити заявку.
    if not form.has_email_field:
        return False
    newsletter = form.field_count <= 2
    return not newsletter


@register
class EmailExposureCheck(Check):
    code = "tech.email_exposed"
    module = Module.TECH
    severity = Severity.LOW
    weight = 1
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        addresses = {a for page in ctx.ok_pages for a in page.mailto_addresses if "@" in a}
        if addresses:
            yield self.issue(
                params={"count": len(addresses)},
                evidence={"addresses": sorted(addresses)[:5]},
            )


@register
class CachingCheck(Check):
    code = "tech.caching"
    module = Module.TECH
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        measured = [p for p in ctx.ok_pages if p.headers]
        if not measured:
            return
        without = [p for p in measured if not _has_caching(p)]
        if len(without) == len(measured):
            yield self.issue(
                params={"count": len(without)},
                evidence={
                    "pages_checked": len(measured),
                    "example": without[0].url,
                    "cache_control": without[0].header("cache-control"),
                },
            )


def _has_caching(page: PageSignals) -> bool:
    cache_control = (page.header("cache-control") or "").lower()
    if cache_control and "no-store" not in cache_control:
        return True
    return bool(page.header("etag") or page.header("last-modified"))


@register
class NapConsistencyCheck(Check):
    """Звірка контактів, які вже є на сайті — між сторінками й з розміткою.

    Нічого не «дізнається» про бізнес: порівнює лише те, що сайт сам
    про себе написав. Вимога специфікації — NAP байт-у-байт однаковий
    скрізь, де він зустрічається.
    """

    code = "tech.nap"
    module = Module.TECH
    severity = Severity.MEDIUM
    weight = 3
    effort = Effort.LOW
    messages = ("tech.nap.phone_mismatch", "tech.nap.phone_not_e164", "tech.nap.schema_mismatch")
    variants = ("phone_mismatch", "phone_not_e164", "schema_mismatch")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        page_phones = {_normalize_phone(p) for page in ctx.ok_pages for p in page.tel_links}
        page_phones.discard("")
        if not page_phones:
            return

        if len(page_phones) > 1:
            yield self.issue(
                key="phone_mismatch",
                msg="tech.nap.phone_mismatch",
                params={"count": len(page_phones)},
                evidence={"phones": sorted(page_phones)},
            )

        raw = [p for page in ctx.ok_pages for p in page.tel_links]
        not_e164 = sorted({p for p in raw if not _is_e164(p)})
        if not_e164:
            yield self.issue(
                key="phone_not_e164",
                msg="tech.nap.phone_not_e164",
                # Приклад беремо з самого сайту, а не з каталогу. У каталозі
                # стояв український номер, і американський клієнт читав
                # пораду привести телефони «до вигляду +380441234567».
                params={"count": len(not_e164), "example": not_e164[0]},
                evidence={"examples": not_e164[:5]},
                severity=Severity.LOW,
            )

        schema_phones = {
            _normalize_phone(str(node.get("telephone")))
            for page in ctx.ok_pages
            for node in page.jsonld
            if node.get("telephone")
        }
        schema_phones.discard("")
        if schema_phones and not (schema_phones & page_phones):
            yield self.issue(
                key="schema_mismatch",
                msg="tech.nap.schema_mismatch",
                evidence={
                    "in_markup": sorted(schema_phones),
                    "on_pages": sorted(page_phones),
                },
            )


def _normalize_phone(value: str) -> str:
    """Лишаємо лише цифри: +38 (044) 123-45-67 і +380441234567 — те саме."""
    digits = "".join(c for c in value if c.isdigit())
    return digits.lstrip("0") if digits else ""


def _is_e164(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith("+") and stripped[1:].isdigit() and 8 <= len(stripped) <= 16


@register
class SoftNotFoundCheck(Check):
    code = "tech.soft_404"
    module = Module.TECH
    severity = Severity.HIGH
    weight = 3
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        infra = ctx.infra
        if not infra.not_found_checked or not infra.not_found_is_soft:
            return
        yield self.issue(
            params={"status": infra.not_found_status},
            evidence={"probe_status": infra.not_found_status, "expected": 404},
        )


@register
class HostCanonicalizationCheck(Check):
    code = "tech.host_canonical"
    module = Module.TECH
    severity = Severity.MEDIUM
    weight = 3
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        infra = ctx.infra
        if not infra.alt_host_checked or infra.alt_host_redirects_home:
            return
        # Обидва хости віддають контент і не зводяться до одного — той самий
        # сайт існує за двома адресами.
        if infra.alt_host_status and 200 <= infra.alt_host_status < 300:
            yield self.issue(
                params={"host": infra.alt_host or ""},
                evidence={
                    "alternate": infra.alt_host,
                    "status": infra.alt_host_status,
                    "canonical_origin": ctx.origin,
                },
            )


@register
class DemoContentCheck(Check):
    """Чужий шаблонний вміст, який лишився на сайті.

    Для клієнта це дорожче за більшість технічних знахідок: відвідувач
    бачить вісім облич із чужими іменами й розуміє, що сайт зроблений
    абияк, а пошук і мовні моделі беруть ці сторінки за факти про
    компанію.

    Кожен сигнал окремо помиляється — українська компанія може мати
    іноземних працівників, пошта на чужому домені буває справжньою. Тому
    знахідка зʼявляється лише там, де сходяться щонайменше два незалежні
    сигнали, а серйозність росте з їхньою кількістю.
    """

    code = "tech.demo_content"
    module = Module.TECH
    severity = Severity.HIGH
    weight = 4
    effort = Effort.MEDIUM
    # Скільки різних сигналів має зійтися. Один — ще не знахідка.
    MIN_SIGNALS = 2
    # Скільки їх робить висновок твердим. Кожен сигнал окремо може бути
    # збігом; три різні — вже ні.
    CERTAIN_SIGNALS = 3

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        found = detect_demo_content(ctx)
        if found.kinds < self.MIN_SIGNALS:
            return
        # Впевненість росте разом із кількістю сигналів, а не задана
        # наперед. Два сигнали — ймовірно; пошта на домені теми, службові
        # сторінки конструктора й вигадана команда одночасно — це вже не
        # збіг, і ставити таку знахідку нижче за виміряний H1 було б
        # помилкою пріоритезації.
        certain = found.kinds >= self.CERTAIN_SIGNALS
        yield self.issue(
            params={"count": found.kinds},
            evidence=found.to_json(),
            severity=Severity.CRITICAL if certain else Severity.HIGH,
            confidence=Confidence.HIGH if certain else Confidence.MEDIUM,
        )


# ── Змішаний вміст ────────────────────────────────────────────────────────


@register
class MixedContentCheck(Check):
    """Захищена сторінка просить підресурси по http.

    ## Чотири різні розмови, а не одна

    `blockable` — скрипт, стиль, iframe: сучасний браузер такий запит не
    підвищує й не пропускає, тож частина сторінки може просто не
    працювати. `upgradeable` — картинка, аудіо, відео: схему браузер
    підніме сам, але лише поки https-версія ресурсу існує, і в розмітці
    лишається адреса, яка колись перестане відповідати. `download` —
    завантаження файлу з захищеної сторінки по http, яке браузери
    блокують окремо. `runtime` — запит, якого в розмітці немає взагалі:
    його зробив скрипт, і бачили ми це в журналі браузера.

    ## Що ми стверджуємо, а що ні

    Заявлене й спостережене розділені: `handling` — це очікувана
    поведінка за специфікацією, `observed` — те, що ми справді бачили.
    Сторінку, яку не відкривали в браузері, ми не описуємо словами
    «заблоковано»: доказу немає.

    `upgrade-insecure-requests` у CSP знахідку не скасовує, а стає
    поруч у доказі. Директива каже, що браузер підвищить схему, — вона
    не каже, що https-версія ресурсу існує.

    Сканування вразливостей це не є й не стане: тут рівно те, що видно
    з розмітки й журналу запитів.

    ## Чому інформаційний

    `severity=INFO`, `weight=0`. База скорингу заморожена, а чи мають
    класи коштувати різного — питання фази калібрування (§K.4).
    """

    code = "tech.mixed_content"
    module = Module.TECH
    severity = Severity.INFO
    weight = 0
    effort = Effort.MEDIUM
    variants = ("blockable", "upgradeable", "download", "runtime")
    messages = tuple(f"tech.mixed_content.{v}" for v in
                     ("blockable", "upgradeable", "download", "runtime"))

    # Скільки ресурсів показуємо. Числа поруч завжди повні.
    SHOWN = 8

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        analysis = mixed_content.analyse(ctx)
        if not analysis.references:
            return
        coverage = analysis.coverage()
        groups = {
            "blockable": [
                r for r in analysis.references
                if r.handling is mixed_content.Handling.BLOCKABLE
            ],
            "upgradeable": [
                r for r in analysis.references
                if r.handling is mixed_content.Handling.UPGRADEABLE
            ],
            "download": [
                r for r in analysis.references
                if r.handling is mixed_content.Handling.MIXED_DOWNLOAD
            ],
            # Те, чого в розмітці немає: доказ тут — сам журнал запитів.
            "runtime": [r for r in analysis.references if r.seen_in == "network"],
        }
        for variant, refs in groups.items():
            if not refs:
                continue
            shown = sorted(refs, key=lambda r: (r.page, r.url))[: self.SHOWN]
            evidence: dict[str, object] = {
                **coverage,
                "resources": [r.as_evidence() for r in shown],
                "resources_total": len(refs),
                "pages_affected": mixed_content.pages_with(refs),
                "third_party": sum(1 for r in refs if r.third_party),
                "observed": sorted({r.observed.value for r in refs}),
            }
            if len(shown) < len(refs):
                evidence["resources_truncated"] = True
            yield self.issue(
                key=variant,
                msg=f"tech.mixed_content.{variant}",
                params={"count": len(refs), "pages": evidence["pages_affected"]},
                evidence=evidence,
            )


# ── Транспорт: стиснення й версія протоколу ───────────────────────────────

# Від якого розміру нестиснена текстова відповідь варта розмови. Це наш
# запобіжник від шуму, а не вимога пошуку: дрібний JSON без стиснення
# нікому не шкодить. Число обране з запасом — найменша нестиснена
# відповідь на живій вибірці була 39 КБ, тож поріг у 10 КБ нікого з них
# не відсікає й водночас глушить дрібноту.
SUBSTANTIAL_TEXT_BYTES = 10 * 1024


@register
class TransportCheck(Check):
    """Як відповіді доїхали: без стиснення й яким протоколом.

    ## Межа, яка тут головна

    Ми бачимо ВІДПОВІДЬ, а не сервер. «Цю відповідь віддано без
    стиснення» — спостереження. «Сервер не вміє стискати» — вигадка:
    наш клієнт просить лише `gzip, deflate`, і сервер, який уміє лише
    Brotli, віддасть нам identity. Те саме з протоколом: погоджена
    версія залежить від ALPN, CDN і можливостей нашої бібліотеки.

    ## Чому про HTTP/1.1 узагалі можна говорити

    Бо перевірено, що наш клієнт справді вміє інше: `http2=True`, пакет
    `h2` встановлено, і на живій вибірці він погодив HTTP/2 у 50 із 60
    відповідей. Тобто HTTP/1.1 тут — вибір іншого боку, а не наша
    неспроможність. Якби клієнт не вмів HTTP/2, ця знахідка була б
    твердженням про нас і не мала б права існувати.

    HTTP/3 не згадуємо взагалі: наш стек його не погоджує, тож його
    відсутність — невідомість, а не факт про сайт.

    ## Чого не стверджуємо

    Що стиснення чи HTTP/2 піднімають позиції — цього ми не міряли й
    Google цього не обіцяє. Що Brotli обовʼязковий — ні: gzip цілком
    робочий, і радити його заміну без вимірювання було б порожньою
    порадою.

    ## Чому інформаційний

    `severity=INFO`, `weight=0`. База скорингу заморожена; чи має це
    коштувати балів — питання фази калібрування (§K.4).
    """

    code = "tech.transport"
    module = Module.TECH
    severity = Severity.INFO
    weight = 0
    effort = Effort.MEDIUM
    variants = ("uncompressed", "http1")
    messages = ("tech.transport.uncompressed", "tech.transport.http1")
    # Заголовки й версія протоколу видно з самої відповіді, а не зі
    # сторінки: судити є що навіть там, де вмісту ми не отримали.
    reads_content = False

    SHOWN = 8

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        analysis = transport.analyse(ctx)
        if not analysis.observations:
            return
        coverage = analysis.coverage()

        heavy = [
            o for o in analysis.unencoded
            if o.decoded_bytes >= SUBSTANTIAL_TEXT_BYTES
        ]
        if heavy:
            shown = sorted(heavy, key=lambda o: (-o.decoded_bytes, o.url))[: self.SHOWN]
            evidence: dict[str, object] = {
                **coverage,
                "responses": [o.as_evidence() for o in shown],
                "responses_total": len(heavy),
                "largest_bytes": max(o.decoded_bytes for o in heavy),
                # Скільки саме байтів зекономить стиснення, ми не знаємо:
                # для цього треба стиснути й порівняти, а ми лише бачили
                # відповідь. Вигадувати відсотки не будемо.
                "savings_measured": False,
            }
            if len(shown) < len(heavy):
                evidence["responses_truncated"] = True
            yield self.issue(
                key="uncompressed",
                msg="tech.transport.uncompressed",
                params={"count": len(heavy),
                        "size": max(o.decoded_bytes for o in heavy) // 1024},
                evidence=evidence,
            )

        # HTTP/1.1 має сенс називати лише тоді, коли ми справді вміємо
        # більше. Доказ — можливості нашого клієнта, а не контраст
        # усередині аудиту: сайт, який усюди віддає HTTP/1.1, інакше
        # ніколи б не потрапив у знахідку, хоча саме він і є випадком.
        protocols = analysis.protocols()
        if transport.client_offers_http2() and protocols.get("HTTP/1.1"):
            old = [o for o in analysis.observations if o.protocol == "HTTP/1.1"]
            shown = sorted(old, key=lambda o: o.url)[: self.SHOWN]
            yield self.issue(
                key="http1",
                msg="tech.transport.http1",
                params={"count": len(old)},
                evidence={
                    **coverage,
                    "responses": [o.as_evidence() for o in shown],
                    "responses_total": len(old),
                    # Доказ того, що межа виміряна нами, а не сервером.
                    "client_negotiated_http2_elsewhere": protocols.get("HTTP/2", 0),
                },
            )
