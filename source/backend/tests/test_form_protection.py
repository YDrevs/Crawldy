"""Видимі ознаки захисту форм: що детектор доводить, а чого не сміє.

Перевіряється рівно межа тверджень:

* побачений маркер провайдера всередині форми — доказ про цю форму;
* згадка провайдера в тексті — не доказ ні про що;
* бібліотека сторінки — не доказ про форму, але й не дозволяє сказати
  протилежне (саме так виглядає невидима reCAPTCHA v3);
* відсутність форм — напрям незастосовний, а не «пройдено»;
* знімок, знятий до появи сканування, не свідчить про сайт.

Жоден шлях не надсилає форму й не перевіряє rate limit: доказ цього —
відсутність будь-якого мережевого виклику в детекторі, зафіксована тестом
`test_the_detector_never_calls_the_network`.
"""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from app.audit import form_protection
from app.audit.checks.tech import FormProtectionCheck, observe_forms
from app.audit.i18n import Locale
from app.audit.types import PageSignals, SiteContext
from app.report.builder import _form_protection_fact
from app.report.i18n import STRINGS
from app.report.passed import PassState, evaluate_all
from tests.factories import context, page_from_html

ORIGIN = "https://example.com"

LEAD_FIELDS = """
  <input type="text" name="name">
  <input type="email" name="email">
  <textarea name="message"></textarea>
"""


def page_of(html: str, url: str = f"{ORIGIN}/contact") -> PageSignals:
    """Сторінка з РОЗМІТКИ через справжній екстрактор.

    Саме він і перевіряється: детектор читає те, що екстрактор поклав у
    `PageSignals`, і синтетичний обʼєкт із виставленими полями перевіряв
    би сам себе.
    """
    return page_from_html(html, url=url)


def context_of(*pages: PageSignals) -> SiteContext:
    return context(*pages)


def issues_for(ctx: SiteContext) -> list[Any]:
    return list(FormProtectionCheck().run(ctx))


# ── 1. сторінка без форм ───────────────────────────────────────────────────


def test_a_page_without_forms_is_not_applicable() -> None:
    ctx = context_of(page_of("<html><body><h1>Про нас</h1></body></html>"))
    assert issues_for(ctx) == []
    fact = _form_protection_fact(ctx)
    assert fact["forms_total"] == 0
    # Саме NOT_APPLICABLE, а не PASSED: бал за відсутність предмета
    # перевірки був би вигаданим.
    states = evaluate_all({"form_protection": fact}, set())
    assert states["tech.form_protection"] is PassState.NOT_APPLICABLE


# ── 2–5. провайдери, яких ми впізнаємо ─────────────────────────────────────


@pytest.mark.parametrize(
    ("markup", "provider"),
    [
        ('<div class="cf-turnstile" data-sitekey="0x4AAA"></div>', "turnstile"),
        ('<div class="g-recaptcha" data-sitekey="6Lc"></div>', "recaptcha"),
        ('<div class="h-captcha" data-sitekey="10000000"></div>', "hcaptcha"),
        ('<div class="frc-captcha" data-sitekey="FCM"></div>', "friendly_captcha"),
    ],
)
def test_a_protected_form_names_its_provider(markup: str, provider: str) -> None:
    page = page_of(
        f'<html><body><form method="post" action="/send">{LEAD_FIELDS}{markup}'
        f"<button>Send</button></form></body></html>"
    )
    form = page.forms[0]
    assert form.protections == (provider,)
    assert form.scanned is True

    ctx = context_of(page)
    # Знахідки немає: форма захищена, і мовчання тут правильне.
    assert issues_for(ctx) == []

    fact = _form_protection_fact(ctx)
    assert len(fact["protected"]) == 1
    entry = fact["protected"][0]
    assert entry["providers"] == [provider]
    assert entry["page_url"] == f"{ORIGIN}/contact"
    # Доказ несе і селектор форми, і те, що саме збіглося.
    assert entry["form"].startswith("form")
    assert entry["signals"][0]["source"] == "static"
    assert entry["signals"][0]["scope"] == "form"


def test_a_visible_honeypot_counts_as_a_signal() -> None:
    page = page_of(
        '<html><body><form method="post" action="/send">'
        f"{LEAD_FIELDS}"
        '<input type="text" name="honeypot" style="display:none">'
        "</form></body></html>"
    )
    assert page.forms[0].honeypots == ("honeypot",)
    assert issues_for(context_of(page)) == []


def test_a_honeypot_name_on_a_visible_field_is_not_a_honeypot() -> None:
    """Приманка, яку видно людині, приманкою не є."""
    page = page_of(
        '<html><body><form method="post" action="/send">'
        f'{LEAD_FIELDS}<input type="text" name="trap">'
        "</form></body></html>"
    )
    assert page.forms[0].honeypots == ()


# ── 6. форма без видимого сигналу ──────────────────────────────────────────


def test_a_form_without_any_visible_signal_is_reported_as_such() -> None:
    page = page_of(
        f'<html><body><form method="post" action="/send">{LEAD_FIELDS}'
        "</form></body></html>"
    )
    ctx = context_of(page)
    issues = issues_for(ctx)
    assert [issue.issue_key for issue in issues] == [
        "tech.form_protection:no_visible_marker"
    ]
    evidence = issues[0].evidence
    # Межі пасивної перевірки їдуть у доказі, а не в примітці.
    assert evidence["server_side_controls_assessed"] is False
    assert evidence["form_submission_tested"] is False
    assert evidence["waf_or_rate_limiting_assessed"] is False
    assert evidence["observation_scope"] == "form_attributes"

    fact = _form_protection_fact(ctx)
    assert len(fact["unprotected"]) == 1
    states = evaluate_all({"form_protection": fact}, set())
    assert states["tech.form_protection"] is PassState.FAILED


# ── 7. згадка CAPTCHA в тексті ─────────────────────────────────────────────


def test_a_textual_mention_of_captcha_does_not_prove_protection() -> None:
    """Абзац «ми використовуємо reCAPTCHA» — не підключений віджет."""
    page = page_of(
        '<html><body><form method="post" action="/send">'
        f"{LEAD_FIELDS}"
        "<p>Ми використовуємо reCAPTCHA та hCaptcha для захисту форми.</p>"
        "</form></body></html>"
    )
    assert page.forms[0].protections == ()
    # І навпаки: сторінка з текстом про CAPTCHA й БЕЗ форми не створює
    # ані знахідки, ані позитивного факту.
    text_only = page_of(
        "<html><body><p>reCAPTCHA захищає наші форми</p></body></html>"
    )
    assert issues_for(context_of(text_only)) == []
    assert _form_protection_fact(context_of(text_only))["forms_total"] == 0


# ── 8. захист, який зʼявляється лише після виконання JS ────────────────────


def test_protection_visible_only_after_rendering_is_honoured() -> None:
    """Turnstile частіше домальовує скрипт, ніж віддає сервер."""
    static_html = (
        '<html><body><form id="lead" method="post" action="/send">'
        f"{LEAD_FIELDS}</form></body></html>"
    )
    rendered_html = (
        '<html><body><form id="lead" method="post" action="/send">'
        f'{LEAD_FIELDS}<div class="cf-turnstile" data-sitekey="0x4"></div>'
        "</form></body></html>"
    )
    page = page_of(static_html)
    rendered = page_of(rendered_html)

    ctx = context_of(page)
    # Без рендеру знахідка була б; з рендером — ні, бо віджет справді є.
    assert issues_for(ctx) != []

    ctx.renders = {page.url: _render_of(rendered)}
    assert issues_for(ctx) == []
    entry = _form_protection_fact(ctx)["protected"][0]
    assert entry["providers"] == ["turnstile"]
    assert {signal["source"] for signal in entry["signals"]} == {"rendered"}


def test_a_page_level_library_forbids_the_negative_claim() -> None:
    """Невидима reCAPTCHA v3: у формі порожньо, бібліотека на сторінці."""
    page = page_of(
        '<html><head><script src="https://www.google.com/recaptcha/api.js"></script>'
        f'</head><body><form method="post" action="/send">{LEAD_FIELDS}</form>'
        "</body></html>"
    )
    assert page.protection_libraries == ["recaptcha"]
    ctx = context_of(page)
    # Ані знахідки (звинувачення недоведене), ані «пройдено» (сигналу
    # про саму форму немає).
    assert issues_for(ctx) == []
    fact = _form_protection_fact(ctx)
    assert fact["protected"] == []
    assert len(fact["undetermined"]) == 1
    assert fact["undetermined"][0]["page_libraries"] == ["recaptcha"]


# ── 9. кілька форм із різними станами на одній сторінці ────────────────────


def test_two_forms_with_different_states_on_one_page() -> None:
    page = page_of(
        "<html><body>"
        f'<form id="protected" method="post" action="/a">{LEAD_FIELDS}'
        '<div class="h-captcha" data-sitekey="1"></div></form>'
        f'<form id="plain" method="post" action="/b">{LEAD_FIELDS}</form>'
        "</body></html>"
    )
    ctx = context_of(page)
    fact = _form_protection_fact(ctx)
    assert [entry["form"] for entry in fact["protected"]] == ["form#protected"]
    assert [entry["form"] for entry in fact["unprotected"]] == ["form#plain"]
    # Знахідка стосується саме незахищеної форми й називає її.
    issues = issues_for(ctx)
    assert len(issues) == 1
    assert issues[0].evidence["forms"][0]["form"] == "form#plain"
    # Одна захищена форма не робить сторінку «пройденою», поки є інша.
    states = evaluate_all({"form_protection": fact}, set())
    assert states["tech.form_protection"] is PassState.FAILED


# ── 10. доказ і адреса сторінки ────────────────────────────────────────────


def test_evidence_maps_to_the_page_it_was_seen_on() -> None:
    first = page_of(
        f'<html><body><form method="post" action="/send">{LEAD_FIELDS}'
        '<div class="cf-turnstile"></div></form></body></html>',
        url=f"{ORIGIN}/contact",
    )
    second = page_of(
        f'<html><body><form method="post" action="/x">{LEAD_FIELDS}</form></body></html>',
        url=f"{ORIGIN}/support",
    )
    ctx = context_of(first, second)
    fact = _form_protection_fact(ctx)
    assert fact["protected"][0]["page_url"] == f"{ORIGIN}/contact"
    assert fact["unprotected"][0]["page_url"] == f"{ORIGIN}/support"
    assert issues_for(ctx)[0].page_url == f"{ORIGIN}/support"


# ── 11–12. пасивність: ані надсилання, ані перевірки rate limit ────────────


def test_the_detector_never_calls_the_network() -> None:
    """Пасивність доводиться кодом, а не обіцянкою в документації."""
    sources = "\n".join(
        inspect.getsource(module)
        for module in (form_protection,)
    )
    sources += inspect.getsource(observe_forms)
    sources += inspect.getsource(FormProtectionCheck)
    sources += inspect.getsource(_form_protection_fact)
    for forbidden in ("httpx", "requests", "urlopen", "fetch(", "post(", "session."):
        assert forbidden not in sources, forbidden


def test_the_detector_reports_that_it_tested_nothing_active() -> None:
    page = page_of(
        f'<html><body><form method="post" action="/send">{LEAD_FIELDS}</form></body></html>'
    )
    fact = _form_protection_fact(context_of(page))
    assert fact["form_submission_tested"] is False
    assert fact["rate_limiting_tested"] is False
    assert fact["server_side_controls_assessed"] is False


# ── 13–14. звіт і локалізація ──────────────────────────────────────────────


def test_the_passed_line_is_localized_in_every_report_locale() -> None:
    # Мови ЗВІТУ — це ключі каталогу, а не всі значення `Locale`: тип
    # перелічує мови, які система вміє прийняти, каталог — ті, якими
    # звіт написаний.
    assert set(STRINGS) <= set(Locale)
    for locale in STRINGS:
        template = STRINGS[locale].get("passed.tech.form_protection")
        assert template, locale
        rendered = template.format(providers="turnstile", forms=1)
        assert "{" not in rendered, locale
        # Жодна мова не обіцяє перевіреного сервера.
        for overclaim in ("server-side", "серверн", "servidor", "serveur", "serverseit"):
            assert overclaim not in rendered.lower(), (locale, overclaim)


def test_a_protected_form_reaches_the_report_as_a_passed_check() -> None:
    page = page_of(
        f'<html><body><form method="post" action="/send">{LEAD_FIELDS}'
        '<div class="cf-turnstile" data-sitekey="0x4"></div></form></body></html>'
    )
    fact = _form_protection_fact(context_of(page))
    states = evaluate_all({"form_protection": fact}, set())
    assert states["tech.form_protection"] is PassState.PASSED


# ── 15. знімок, старіший за сканування ─────────────────────────────────────


def test_an_old_snapshot_that_never_looked_does_not_testify() -> None:
    """Порожнеча в старому знімку описує нас, а не сайт."""
    page = page_of(
        f'<html><body><form method="post" action="/send">{LEAD_FIELDS}</form></body></html>'
    )
    # Саме так виглядає знімок, знятий до появи цих полів: форма є,
    # ознак немає, і жоден із двох прапорців не виставлений.
    page.forms_scanned = False
    for form in page.forms:
        form.scanned = False
        form.protections = ()
        form.protection_markers = ()
    ctx = context_of(page)
    assert issues_for(ctx) == []
    fact = _form_protection_fact(ctx)
    assert fact["available"] is False
    states = evaluate_all({"form_protection": fact}, set())
    assert states["tech.form_protection"] is PassState.UNAVAILABLE


def test_the_two_findings_of_this_check_have_different_prices() -> None:
    """Рішення власника від 4 вересня 2026: ціни різні, і розводить їх
    серйозність.

    `no_visible_marker` лишається INFO — множник нуль. Пасивний огляд не
    може довести відсутність серверного захисту, і брати за недоведене
    бали означало б продавати здогад.

    `get_method` — MEDIUM × вага 3. Тут доводити нічого не треба:
    поведінка браузера задокументована, а метод ми бачимо очима.
    """
    from app.audit.scoring import SEVERITY_MULTIPLIER, penalty

    assert FormProtectionCheck.severity.name == "INFO"
    assert FormProtectionCheck.weight == 3

    unprotected = issues_for(
        context_of(
            page_of(
                f'<html><body><form method="post" action="/send">{LEAD_FIELDS}'
                "</form></body></html>"
            )
        )
    )[0]
    assert unprotected.issue_key.endswith("no_visible_marker")
    assert SEVERITY_MULTIPLIER[unprotected.severity] == 0
    assert penalty(unprotected) == 0

    by_get = next(
        i
        for i in issues_for(
            context_of(
                page_of(
                    f'<html><body><form method="get" action="/send">{TURNSTILE}'
                    f"{LEAD_FIELDS}</form></body></html>"
                )
            )
        )
        if i.issue_key.endswith("get_method")
    )
    assert SEVERITY_MULTIPLIER[by_get.severity] == 2
    assert penalty(by_get) == 6


def _render_of(signals: PageSignals) -> Any:
    from app.audit.types import RenderResult

    return RenderResult(url=signals.url, rendered=True, signals=signals)


# ── 4. безпека методу — незалежний факт ────────────────────────────────────
#
# Захист від ботів і спосіб відправки — два різні твердження. Форма з
# челенджем на GET має дати обидві знахідки: Turnstile нічого не каже про
# те, куди браузер покладе імʼя, пошту й текст звернення.
#
# Найдорожча помилка тут була наша власна: правило вимагало ще й
# непорожнього `action`, і сторінка «Контакти» самого Crawldy (`get` +
# порожня дія) знахідки не давала — тобто чек глушив рівно той випадок,
# заради якого існує.

TURNSTILE = '<div class="cf-turnstile" data-sitekey="0x4AAA"></div>'


def _keys(ctx: SiteContext) -> set[str]:
    return {issue.issue_key for issue in issues_for(ctx)}


def test_get_with_turnstile_gives_both_the_signal_and_the_method_finding() -> None:
    """Головний випадок промпту: захист видно, метод усе одно небезпечний."""
    page = page_of(
        f'<html><body><form method="get" action="/send">{TURNSTILE}{LEAD_FIELDS}'
        "</form></body></html>"
    )
    ctx = context_of(page)

    observation = observe_forms(ctx, page)[0][0]
    assert observation.protected is True
    assert "turnstile" in observation.providers

    keys = _keys(ctx)
    assert "tech.form_protection:get_method" in keys
    # Захист побачено, тож твердження про його відсутність не звучить.
    assert "tech.form_protection:no_visible_marker" not in keys


def test_post_with_turnstile_gives_neither_finding() -> None:
    page = page_of(
        f'<html><body><form method="post" action="/send">{TURNSTILE}{LEAD_FIELDS}'
        "</form></body></html>"
    )
    assert _keys(context_of(page)) == set()


def test_get_without_protection_gives_both_findings() -> None:
    """Два незалежні дефекти — дві знахідки, а не одна.

    Вони мають різні `issue_key`, тобто й різні стелі штрафу: для клієнта
    це різні дії (додати перевірку / змінити метод).
    """
    page = page_of(
        f'<html><body><form method="get" action="/send">{LEAD_FIELDS}</form></body></html>'
    )
    keys = _keys(context_of(page))
    assert "tech.form_protection:get_method" in keys
    assert "tech.form_protection:no_visible_marker" in keys


def test_post_without_protection_gives_only_the_protection_finding() -> None:
    page = page_of(
        f'<html><body><form method="post" action="/send">{LEAD_FIELDS}</form></body></html>'
    )
    keys = _keys(context_of(page))
    assert "tech.form_protection:get_method" not in keys
    assert "tech.form_protection:no_visible_marker" in keys


def test_an_empty_action_no_longer_silences_the_method_finding() -> None:
    """Регресія на власний сайт.

    Порожня дія — це «на поточну адресу», а не «нікуди»: браузер зробить
    GET саме туди, і поля підуть у рядок адреси так само.
    """
    page = page_of(
        f'<html><body><form method="get">{LEAD_FIELDS}</form></body></html>'
    )
    issues = [i for i in issues_for(context_of(page)) if i.issue_key.endswith("get_method")]
    assert issues, "GET із порожньою дією не дав знахідки"
    assert issues[0].evidence["actions"] == ["(current page)"]


def test_a_form_without_a_method_attribute_is_still_a_get() -> None:
    """Браузер поводиться однаково, а доказ розрізняє написане й дефолт."""
    page = page_of(f"<html><body><form>{LEAD_FIELDS}</form></body></html>")
    issues = [i for i in issues_for(context_of(page)) if i.issue_key.endswith("get_method")]
    assert issues, "форма без method не дала знахідки"
    # Автор нічого не писав — доказ це й каже.
    assert issues[0].evidence["method_declared"] == [False]


def test_a_declared_get_is_recorded_as_declared() -> None:
    page = page_of(
        f'<html><body><form method="GET" action="/send">{LEAD_FIELDS}</form></body></html>'
    )
    issues = [i for i in issues_for(context_of(page)) if i.issue_key.endswith("get_method")]
    assert issues[0].evidence["method_declared"] == [True]


def test_the_method_finding_does_not_depend_on_a_honeypot_either() -> None:
    """Приманка — теж захист, і теж нічого не каже про метод."""
    page = page_of(
        '<html><body><form method="get" action="/send">'
        '<input type="text" name="company" style="display:none">'
        f"{LEAD_FIELDS}</form></body></html>"
    )
    assert "tech.form_protection:get_method" in _keys(context_of(page))


def test_the_method_finding_declares_its_independence_in_evidence() -> None:
    """Незалежність — властивість правила, і доказ мусить її нести."""
    page = page_of(
        f'<html><body><form method="get" action="/send">{TURNSTILE}{LEAD_FIELDS}'
        "</form></body></html>"
    )
    issue = next(
        i for i in issues_for(context_of(page)) if i.issue_key.endswith("get_method")
    )
    assert issue.evidence["protection_independent"] is True


def test_nothing_is_submitted_and_no_limits_are_probed() -> None:
    """Перевірка лишається пасивною: жодного запиту з чека не виходить.

    Доводиться текстом самого чека — мережевих викликів у ньому немає
    ані прямо, ані через клієнт.
    """
    source = inspect.getsource(FormProtectionCheck)
    for forbidden in ("httpx", "requests", "fetch", "post(", "await ", "async "):
        assert forbidden not in source, f"чек не має бути активним: {forbidden}"


def test_the_message_about_invisible_protection_reads_the_same_in_six_locales() -> None:
    """Точний текст власника, і саме він доходить до клієнта.

    Слот — `description`: український «відрендереній» і російський
    «отрендеренной» містять основу «рендер», яку тест про жаргон не
    пускає в нетехнічний `consequence`. Послабити той тест заради
    формулювання означало б проміняти правило на рядок.
    """
    from app.audit.i18n import CATALOGS

    expected = {
        "en": "No visible protection was found in the initial HTML or the rendered form.",
        "uk": "Видимого захисту не знайдено ні у вихідному HTML, ні у відображеній формі.",
        "de": "Weder im ursprünglichen HTML noch im gerenderten Formular wurde sichtbarer",
        "es": "No se encontró protección visible ni en el HTML inicial ni en el formulario",
        "fr": "Aucune protection visible n’a été trouvée dans le HTML initial",
        "ru": "Видимая защита не найдена ни в исходном HTML, ни в отображённой форме.",
    }
    titles = {
        "en": "No visible anti-bot protection was detected in the form.",
        "uk": "У формі не виявлено видимих ознак захисту від ботів.",
        "de": "Im Formular wurde kein sichtbarer Schutz vor Bots erkannt.",
        "es": "No se detectó protección visible contra bots en el formulario.",
        "fr": "Aucune protection visible contre les robots n’a été détectée dans le formulaire.",
        "ru": "В форме не обнаружено видимых признаков защиты от ботов.",
    }
    hedge = {
        "en": "cannot be confirmed by this passive check",
        "uk": "пасивна перевірка не може його підтвердити",
        "de": "lässt sich mit dieser passiven Prüfung nicht bestätigen",
        "es": "esta comprobación pasiva no puede confirmarla",
        "fr": "sans pouvoir être confirmée par cette vérification passive",
        "ru": "пассивная проверка не может её подтвердить",
    }
    seen = 0
    for locale, catalog in CATALOGS.items():
        code = locale.value
        if code not in expected:
            continue
        entry = catalog["tech.form_protection.no_visible_marker"]
        text = entry["description"]
        assert entry["title"] == titles[code], code
        assert text.startswith(expected[code]), code
        # Застереження обовʼязкове: без нього спостереження стає вироком.
        assert hedge[code] in text, code
        seen += 1
    assert seen == 6, f"перевірено лише {seen} мов"
