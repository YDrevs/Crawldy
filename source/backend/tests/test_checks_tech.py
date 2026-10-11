"""Чеки захисту, аналітики та інфраструктури."""

from __future__ import annotations

from app.audit.checks.tech import (
    SECURITY_HEADERS,
    AnalyticsCheck,
    CachingCheck,
    CrawlerBlockedCheck,
    EmailExposureCheck,
    FormProtectionCheck,
    HostCanonicalizationCheck,
    NapConsistencyCheck,
    SecurityHeadersCheck,
    SoftNotFoundCheck,
)
from app.audit.enums import Severity
from app.audit.types import FormSignals, InfraInfo, PageSignals, RenderResult, SiteContext

# Справжні значення, а не заглушка «x»: x-content-type-options захищає
# лише зі значенням nosniff, і чек тепер це перевіряє.
ALL_HEADERS = {
    "content-security-policy": "default-src 'self'",
    "x-frame-options": "DENY",
    "x-content-type-options": "nosniff",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "geolocation=()",
}


def page(url: str = "https://example.com/", **kwargs) -> PageSignals:
    signals = PageSignals(url=url, status_code=200)
    for key, value in kwargs.items():
        setattr(signals, key, value)
    # Фікстура з формами описує сторінку, яку ми ПРОЧИТАЛИ: інакше вона
    # моделювала б знімок, знятий до появи сканування форм, і мовчання
    # детектора там правильне, але перевіряє воно не те, що написано.
    if "forms" in kwargs:
        signals.forms_scanned = True
    return signals


def ctx(*pages: PageSignals, infra: InfraInfo | None = None) -> SiteContext:
    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.pages = list(pages)
    if infra is not None:
        site.infra = infra
    return site


# ── security headers ───────────────────────────────────────────────────────


def test_all_headers_present_gives_no_issue():
    assert list(SecurityHeadersCheck().run(ctx(page(headers=ALL_HEADERS)))) == []


def test_no_headers_at_all_is_informational_not_high():
    """Жодного захисного заголовка — можливість, а не HIGH.

    Раніше повна відсутність давала HIGH зі штрафом 9 — на 50.9% сайтів
    night3, тобто «серйозне» стояло в кожному другому звіті й не
    розрізняло нікого. Браузерні захисні заголовки — гігієна, а не
    видимість у пошуку чи ШІ.
    """
    issues = list(SecurityHeadersCheck().run(ctx(page(headers={"content-type": "text/html"}))))

    assert len(issues) == 1
    assert issues[0].msg == "tech.security_headers.none"
    assert issues[0].severity is Severity.INFO
    assert issues[0].params["count"] == len(SECURITY_HEADERS)


def test_some_headers_present_is_reported_softer():
    headers = {"content-security-policy": "default-src 'self'", "x-frame-options": "DENY"}
    issues = list(SecurityHeadersCheck().run(ctx(page(headers=headers))))

    assert issues[0].msg == "tech.security_headers.missing"
    assert issues[0].severity is Severity.INFO
    assert issues[0].params["count"] == len(SECURITY_HEADERS) - 2
    assert "content-security-policy" in issues[0].evidence["present"]


def test_page_without_headers_is_skipped_not_flagged():
    """Немає заголовків у сигналах — це не «сайт без захисту», а брак даних."""
    assert list(SecurityHeadersCheck().run(ctx(page(headers={})))) == []


# ── доступність для роботів ────────────────────────────────────────────────


def blocked(status: int = 403) -> PageSignals:
    signals = page()
    signals.status_code = status
    return signals


def test_blocked_crawler_is_reported_when_nothing_else_can_be():
    """Rozetka й Allo віддають агенту 403. Без цього чека сайт мовчав
    усіма перевірками одразу й отримував найвищий бал у групі."""
    issues = list(CrawlerBlockedCheck().run(ctx(blocked(403))))

    assert [i.msg for i in issues] == ["tech.crawler_blocked"]
    assert issues[0].severity is Severity.CRITICAL
    assert issues[0].params["status"] == 403


def test_site_that_serves_content_is_not_called_blocked():
    assert list(CrawlerBlockedCheck().run(ctx(page()))) == []


def test_plain_404_is_not_a_block():
    """Сторінки немає — це інша проблема, і в неї є свій чек."""
    assert list(CrawlerBlockedCheck().run(ctx(blocked(404)))) == []


# ── аналітика ──────────────────────────────────────────────────────────────


def rendered(
    site: SiteContext,
    url: str,
    *,
    analytics: list[str] | None = None,
    requests: list[str] | None = None,
    runtime: list[str] | None = None,
) -> SiteContext:
    """Кладе поруч зі сторінкою її версію після виконання JS."""
    after = PageSignals(url=url, status_code=200)
    after.analytics = analytics or []
    site.renders[url] = RenderResult(
        url=url,
        rendered=True,
        html="<html/>",
        signals=after,
        requests=list(requests or []),
        runtime_analytics=list(runtime or []),
    )
    return site


def analytics_issue(site: SiteContext):
    issues = list(AnalyticsCheck().run(site))
    return issues[0] if issues else None


def test_analytics_absent_in_html_is_only_unconfirmed():
    """Без рендеру це твердження про межі нашого зору, а не про сайт:
    Vercel вставляє свій лічильник після гідрації."""
    issue = analytics_issue(ctx(page()))

    assert issue.msg == "tech.analytics.unconfirmed"
    assert issue.severity is Severity.MEDIUM
    assert issue.evidence["checked_after_render"] is False
    assert (issue.evidence["verdict"], issue.evidence["coverage"]) == ("FAIL", "PARTIAL")


def test_render_turns_absence_into_a_statement_about_the_site():
    site = rendered(ctx(page()), "https://example.com/")

    issue = analytics_issue(site)

    assert issue.msg == "tech.analytics.missing"
    assert issue.severity is Severity.HIGH, "тепер це вимірювання, а не здогадка"
    assert issue.evidence["checked_after_render"] is True
    assert (issue.evidence["verdict"], issue.evidence["coverage"]) == ("FAIL", "COMPLETE")
    assert issue.evidence["kind"] == "NONE"


def test_counter_injected_by_js_is_credited_to_the_site():
    """Linear вантажить PostHog при гідрації. У статичному HTML його немає,
    і без рендеру ми звинувачували сайт у тому, чого він не робив."""
    site = rendered(ctx(page()), "https://example.com/", analytics=["posthog"])

    assert [i.msg for i in AnalyticsCheck().run(site)] == []


# ── E-11: вид доказу вирішує, а не наявність рядка ─────────────────────────


def test_a_legacy_first_party_label_is_measurement_without_a_vendor():
    """gov.uk і python.org міряють себе власним скриптом, а не Google.

    Раніше мітка `first_party` означала «це аналітика», і та сама мітка
    діставалась чужому `…-analytics.paddle.com` та маршрутові
    `/admin/analytics`. Тепер вона означає рівно те, чим була: вимірювання
    бачили, вендора не назвали. Знахідка лишається нейтральною
    (`unconfirmed`), пройденою перевіркою це не стає, а «аналітики немає»
    ми не кажемо (E-11b, E-11c).
    """
    issue = analytics_issue(ctx(page(analytics=["first_party"])))

    assert issue.msg == "tech.analytics.unconfirmed"
    assert issue.severity is Severity.MEDIUM
    assert issue.evidence["kind"] == "UNIDENTIFIED_MEASUREMENT"
    assert (issue.evidence["verdict"], issue.evidence["coverage"]) == ("NO_VERDICT", "COMPLETE")
    assert issue.evidence["found"] == []
    assert issue.evidence["unidentified"][0]["rule_id"] == "legacy.first_party"


def test_a_legacy_bare_segment_string_proves_nothing():
    """Голий `segment` міг народитися з нашого ж `/v1/plans` (E-11a).

    Він не вендор — і не «вимірювання без вендора»: стара умова
    спрацьовувала на будь-якій адресі з `/v1/p`. Тому знахідка лишається
    категоричною, а сам рядок видно у провенансі.
    """
    issue = analytics_issue(rendered(ctx(page(analytics=["segment"])), "https://example.com/"))

    assert issue.msg == "tech.analytics.missing"
    assert issue.evidence["found"] == []
    assert issue.evidence["unidentified"] == []
    (row,) = issue.evidence["observations"]
    assert (row["rule_id"], row["kind"]) == ("legacy.segment.unverified", "NONE")


def test_a_legacy_vendor_string_from_an_old_snapshot_still_counts():
    """Знімок без розмітки й глобальних обʼєктів: вендорський маркер лишається доказом."""
    assert list(AnalyticsCheck().run(ctx(page(analytics=["matomo"])))) == []


def test_own_api_routes_never_identify_segment():
    """`/v1/plans` і `/v1/presence/models` — наш власний API (E-11a)."""
    site = rendered(
        ctx(page()),
        "https://example.com/",
        requests=[
            "https://example.com/v1/plans?lang=de",
            "https://example.com/v1/presence/models",
            "https://example.com/v1/public/checkout-config",
        ],
    )

    issue = analytics_issue(site)
    assert issue.msg == "tech.analytics.missing", "жодного сліду вимірювання"
    assert issue.evidence["found"] == []


def test_an_own_measurement_endpoint_is_unconfirmed_not_missing():
    """Власний `/api/collect` кудись шле події: сказати «немає» не можна."""
    site = rendered(ctx(page()), "https://example.com/", requests=["https://example.com/api/collect"])

    issue = analytics_issue(site)
    assert (issue.msg, issue.severity) == ("tech.analytics.unconfirmed", Severity.MEDIUM)
    assert issue.evidence["kind"] == "UNIDENTIFIED_MEASUREMENT"
    assert issue.evidence["unidentified"][0]["channel"] == "request"


def test_a_documented_proxy_needs_the_vendor_signal():
    """Власний `/ingest/e/` стає PostHog лише поруч із його глобальним обʼєктом."""
    alone = rendered(ctx(page()), "https://example.com/", requests=["https://example.com/ingest/e/"])
    assert analytics_issue(alone).msg == "tech.analytics.unconfirmed"

    with_signal = rendered(
        ctx(page()),
        "https://example.com/",
        requests=["https://example.com/ingest/e/"],
        runtime=["global:posthog"],
    )
    assert list(AnalyticsCheck().run(with_signal)) == []


def test_a_generic_analytics_track_global_is_not_segment():
    """`window.analytics.track` має будь-яка бібліотека з методом `track` (E11-d1)."""
    site = rendered(ctx(page()), "https://example.com/", runtime=["global:analytics.track"])

    issue = analytics_issue(site)
    assert issue.evidence["found"] == []
    assert issue.evidence["kind"] == "UNIDENTIFIED_MEASUREMENT"


def test_one_verified_vendor_settles_it_beside_unidentified_traffic():
    """ANY_SUFFICIENT_EVIDENCE: впізнаний вендор вирішує питання сам."""
    site = rendered(
        ctx(page()),
        "https://example.com/",
        requests=["https://api.segment.io/v1/t", "https://example.com/api/collect"],
    )

    assert list(AnalyticsCheck().run(site)) == []


def test_a_behaviour_tool_alone_does_not_answer_the_measurement_question():
    """Clarity показує запис сесій, а не «скільки людей прийшло»."""
    site = rendered(ctx(page(analytics=["microsoft_clarity"])), "https://example.com/")

    issue = analytics_issue(site)
    assert issue.msg == "tech.analytics.missing"
    assert issue.evidence["found"] == ["microsoft_clarity"], "впізнане лишається в доказі"


def test_observations_are_deduplicated_and_deterministically_ordered():
    """Те саме спостереження двічі — один запис; порядок не залежить від сідів."""
    site = rendered(
        ctx(page()),
        "https://example.com/",
        requests=[
            "https://www.google-analytics.com/g/collect?v=2",
            "https://www.google-analytics.com/g/collect?v=2",
            "https://example.com/telemetry",
            "https://example.com/api/collect",
        ],
    )

    rows = site.analytics_classification().evidence()
    assert len(rows) == len({(r["rule_id"], r["signal"]) for r in rows})
    assert [r["kind"] for r in rows] == sorted(
        (r["kind"] for r in rows), key=["VERIFIED_VENDOR", "VERIFIED_CO_SIGNAL",
                                        "UNIDENTIFIED_MEASUREMENT", "NONE"].index
    )


def test_non_google_vendor_counts_as_analytics():
    """Не-Google лічильник — теж лічильник."""
    site = ctx(page(analytics=["plausible"]))
    assert list(AnalyticsCheck().run(site)) == []


def test_missing_session_recording_is_not_reported_at_all():
    """Відсутність теплових карт — не проблема видимості в пошуку й для ШІ.

    furniturerow.com має Google Analytics, GTM, Meta Pixel і власну
    аналітику — і отримував зауваження за те, що серед них немає Hotjar.
    Спершу це полагодили серйозністю INFO: штрафу немає. Людська
    валідація показала, що цього замало — питання не у вазі, а в обсязі
    продукту. Кожен зайвий рядок робить аудит галасливішим, а сайт із
    трьома лічильниками не має чути зауважень про четвертий.
    """
    assert list(AnalyticsCheck().run(ctx(page(analytics=["google_analytics"])))) == []


def test_full_analytics_stack_is_clean():
    signals = page(analytics=["google_analytics", "microsoft_clarity"])
    assert list(AnalyticsCheck().run(ctx(signals))) == []


def test_analytics_found_on_any_page_counts_for_the_site():
    """Лічильник у футері однієї сторінки означає, що він на сайті є."""
    site = ctx(page(), page(url="https://example.com/b", analytics=["google_analytics"]))
    assert list(AnalyticsCheck().run(site)) == []


# ── форми ──────────────────────────────────────────────────────────────────


def lead_form(**kwargs) -> FormSignals:
    """Три поля, серед них email — це саме форма заявки."""
    kwargs.setdefault("has_email_field", True)
    return FormSignals(method="post", field_count=3, **kwargs)


def test_form_without_captcha_or_honeypot_yields_the_observation():
    issues = list(FormProtectionCheck().run(ctx(page(forms=[lead_form()]))))

    assert [i.msg for i in issues] == ["tech.form_protection.no_visible_marker"]
    assert issues[0].evidence["forms_total"] == 1


def test_captcha_or_honeypot_is_enough():
    assert list(FormProtectionCheck().run(ctx(page(forms=[lead_form(has_captcha=True)])))) == []
    assert list(FormProtectionCheck().run(ctx(page(forms=[lead_form(has_honeypot=True)])))) == []


def test_search_box_is_not_treated_as_a_lead_form():
    """Одне поле — це пошук по сайту, а не форма заявки."""
    tiny = FormSignals(method="get", field_count=1)
    assert list(FormProtectionCheck().run(ctx(page(forms=[tiny])))) == []


def test_form_sending_by_get_is_reported_separately():
    form = FormSignals(
        method="get", action="/lead", field_count=3,
        has_captcha=True, has_email_field=True,
    )
    issues = list(FormProtectionCheck().run(ctx(page(forms=[form]))))

    assert [i.msg for i in issues] == ["tech.form_protection.get_method"]


def test_a_js_form_without_action_is_still_judged_by_its_method():
    """Скасування попереднього правила, і причина в тому, чим воно було.

    Тут стояло «React-форма не має ні action, ні method — атрибут
    декоративний», і чек мовчав. Міркування неправильне двічі.

    По-перше, браузер поводиться однаково: форма без дії робить GET на
    поточну адресу, і при збої скрипта імʼя, пошта й текст звернення
    йдуть у рядок адреси, в історію та в `Referer` наступного переходу.
    «Декоративний» він лише поки скрипт працює.

    По-друге, саме цей стан мала сторінка «Контакти» самого Crawldy, і
    побачив його наш власний детектор. Правило глушило рівно той
    випадок, заради якого чек існує.

    Наявність челенджу знахідку теж не скасовує: захист від ботів і
    спосіб відправки — два незалежні твердження.
    """
    form = FormSignals(
        method="get", action="", field_count=3,
        has_captcha=True, has_email_field=True,
    )
    issues = list(FormProtectionCheck().run(ctx(page(forms=[form]))))
    assert [i.issue_key for i in issues] == ["tech.form_protection:get_method"]
    assert issues[0].severity is Severity.MEDIUM
    # Порожня дія читається як «на поточну адресу», а не «нікуди».
    assert issues[0].evidence["actions"] == ["(current page)"]
    # Знімок, знятий до появи поля, нічого не заявляє про декларацію.
    assert issues[0].evidence["method_declared"] == [None]


def test_newsletter_signup_is_not_a_lead_form():
    """Підписка у футері — email і кнопка. Вона є на кожній сторінці сайту,
    і без цього фільтра одна форма давала знахідку на всьому сайті."""
    newsletter = FormSignals(method="post", field_count=2, has_email_field=True)
    assert list(FormProtectionCheck().run(ctx(page(forms=[newsletter])))) == []


def test_contact_form_with_email_and_message_still_counts():
    contact = FormSignals(method="post", action="/contact", field_count=3, has_email_field=True)
    issues = list(FormProtectionCheck().run(ctx(page(forms=[contact]))))

    assert [i.msg for i in issues] == ["tech.form_protection.no_visible_marker"]


# ── решта ──────────────────────────────────────────────────────────────────


def test_exposed_email_is_collected_across_pages():
    site = ctx(
        page(mailto_addresses=["a@example.com"]),
        page(url="https://example.com/b", mailto_addresses=["a@example.com", "b@example.com"]),
    )
    issues = list(EmailExposureCheck().run(site))

    assert issues[0].params["count"] == 2, "адреси не дублюються між сторінками"


def test_pages_without_mailto_are_clean():
    assert list(EmailExposureCheck().run(ctx(page()))) == []


def test_missing_caching_headers_are_flagged_only_when_every_page_lacks_them():
    without = ctx(page(headers={"content-type": "text/html"}))
    mixed = ctx(
        page(headers={"content-type": "text/html"}),
        page(url="https://example.com/b", headers={"etag": "W/'1'"}),
    )

    assert len(list(CachingCheck().run(without))) == 1
    assert list(CachingCheck().run(mixed)) == [], "часткове кешування — не привід карати"


def test_no_store_does_not_count_as_caching():
    site = ctx(page(headers={"cache-control": "no-store"}))
    assert len(list(CachingCheck().run(site))) == 1


def test_soft_404_is_flagged():
    infra = InfraInfo(not_found_checked=True, not_found_status=200, not_found_is_soft=True)
    issues = list(SoftNotFoundCheck().run(ctx(page(), infra=infra)))

    assert issues[0].params["status"] == 200
    assert issues[0].evidence["expected"] == 404


def test_real_404_is_fine():
    infra = InfraInfo(not_found_checked=True, not_found_status=404, not_found_is_soft=False)
    assert list(SoftNotFoundCheck().run(ctx(page(), infra=infra))) == []


def test_unchecked_probe_never_produces_an_issue():
    """Проба не виконалась — мовчимо, а не звинувачуємо сайт."""
    assert list(SoftNotFoundCheck().run(ctx(page(), infra=InfraInfo()))) == []
    assert list(HostCanonicalizationCheck().run(ctx(page(), infra=InfraInfo()))) == []


def test_both_hosts_serving_content_is_flagged():
    infra = InfraInfo(
        alt_host_checked=True,
        alt_host="https://www.example.com/",
        alt_host_status=200,
        alt_host_redirects_home=False,
    )
    issues = list(HostCanonicalizationCheck().run(ctx(page(), infra=infra)))

    assert issues[0].params["host"] == "https://www.example.com/"


def test_alt_host_redirecting_to_canonical_is_correct_setup():
    infra = InfraInfo(
        alt_host_checked=True,
        alt_host="https://www.example.com/",
        alt_host_status=200,
        alt_host_redirects_home=True,
    )
    assert list(HostCanonicalizationCheck().run(ctx(page(), infra=infra))) == []


# ── NAP ────────────────────────────────────────────────────────────────────


def test_single_consistent_phone_is_clean():
    site = ctx(
        page(tel_links=["+380441234567"]),
        page(url="https://example.com/contacts", tel_links=["+380441234567"]),
    )
    assert list(NapConsistencyCheck().run(site)) == []


def test_same_number_written_differently_is_not_a_mismatch():
    """+38 (044) 123-45-67 і +380441234567 — той самий номер."""
    site = ctx(
        page(tel_links=["+380441234567"]),
        page(url="https://example.com/b", tel_links=["+38 (044) 123-45-67"]),
    )
    codes = [i.msg for i in NapConsistencyCheck().run(site)]

    assert "tech.nap.phone_mismatch" not in codes
    assert "tech.nap.phone_not_e164" in codes, "формат усе одно варто вирівняти"


def test_genuinely_different_numbers_are_flagged():
    site = ctx(
        page(tel_links=["+380441234567"]),
        page(url="https://example.com/b", tel_links=["+380507654321"]),
    )
    issues = {i.msg: i for i in NapConsistencyCheck().run(site)}

    assert issues["tech.nap.phone_mismatch"].params["count"] == 2


def test_schema_phone_must_match_the_visible_one():
    signals = page(
        tel_links=["+380441234567"],
        jsonld=[{"@type": "LocalBusiness", "telephone": "+380509999999"}],
    )
    issues = {i.msg for i in NapConsistencyCheck().run(ctx(signals))}

    assert "tech.nap.schema_mismatch" in issues


def test_matching_schema_phone_is_clean():
    signals = page(
        tel_links=["+380441234567"],
        jsonld=[{"@type": "LocalBusiness", "telephone": "+38 044 123 45 67"}],
    )
    issues = {i.msg for i in NapConsistencyCheck().run(ctx(signals))}

    assert "tech.nap.schema_mismatch" not in issues


def test_site_without_phone_numbers_is_not_audited_for_nap():
    """Немає телефону — нема чого звіряти; вигадувати вимогу не будемо."""
    assert list(NapConsistencyCheck().run(ctx(page()))) == []


# ── калібрування: гігієна без штрафу, еквіваленти без хибних спрацювань ──


def _tech_score(issues):
    from app.audit.enums import Module
    from app.audit.scoring import module_score

    return module_score(list(issues), Module.TECH)


def test_missing_headers_cost_zero_points():
    """Відсутні необовʼязкові захисти не знижують Tech і overall."""
    issues = list(SecurityHeadersCheck().run(ctx(page(headers={"content-type": "text/html"}))))
    assert issues, "можливість називається"
    assert _tech_score(issues) == 100 == _tech_score([])


def test_csp_frame_ancestors_prevents_a_false_missing_xfo_claim():
    """CSP frame-ancestors — повноцінна сучасна заміна X-Frame-Options.

    На night3 40 сайтів мали цей захист і все одно чули «бракує
    x-frame-options» — хибне спрацювання, а не знахідка.
    """
    headers = dict(ALL_HEADERS)
    del headers["x-frame-options"]
    headers["content-security-policy"] = "default-src 'self'; frame-ancestors 'none'"
    assert list(SecurityHeadersCheck().run(ctx(page(headers=headers)))) == []


def test_report_only_csp_is_not_enforced_csp():
    """Report-only — телеметрія, а не захист: CSP лишається відсутнім."""
    headers = {"content-security-policy-report-only": "default-src 'self'"}
    issues = list(SecurityHeadersCheck().run(ctx(page(headers=headers))))
    assert "content-security-policy" in issues[0].evidence["missing"]
    assert issues[0].evidence["report_only_csp_present"] is True


def test_x_content_type_options_requires_nosniff_value():
    """Заголовок без nosniff — не захист, і «є» про нього не кажемо."""
    headers = dict(ALL_HEADERS)
    headers["x-content-type-options"] = "sniff-away"
    issues = list(SecurityHeadersCheck().run(ctx(page(headers=headers))))
    assert "x-content-type-options" in issues[0].evidence["missing"]
    assert issues[0].evidence["invalid_values"] == {"x-content-type-options": "sniff-away"}


def test_headers_wording_makes_no_search_or_ai_claims():
    """Жодною з шести мов: ні «зламано», ні ранжування, ні видимість у ШІ."""
    forbidden = ("ранжув", "ranking", "позиці", "posicionamiento", "classement",
                 "ранжиров", "chatgpt", "perplexity", "зламано", "hacked",
                 "vulnerab", "вразлив", "критичн", "critical")
    for locale in ("uk", "en", "de", "es", "fr", "ru"):
        module = __import__(f"app.audit.i18n.{locale}", fromlist=["MESSAGES"])
        for key in ("tech.security_headers.missing", "tech.security_headers.none"):
            blob = " ".join(module.MESSAGES[key].values()).lower()
            for mark in forbidden:
                assert mark not in blob, f"{locale}/{key}: заборонене «{mark}»"


def test_hsts_on_http_is_not_required():
    """На http замість no_hsts спрацьовує missing: HSTS там незастосовний."""
    from app.audit.checks.seo import HttpsCheck
    from app.audit.types import SiteContext

    site = SiteContext(entry_url="http://example.com/", origin="http://example.com")
    site.is_https = False
    site.hsts = False
    issues = list(HttpsCheck().run(site))
    assert [i.key for i in issues] == ["missing"]


def test_missing_hsts_on_https_costs_zero_points():
    """HSTS не впливає на Search (Google, office hours 2023) — штраф нуль."""
    from app.audit.checks.seo import HttpsCheck
    from app.audit.enums import Module
    from app.audit.scoring import module_score
    from app.audit.types import SiteContext

    site = SiteContext(entry_url="https://example.com/", origin="https://example.com")
    site.is_https = True
    site.hsts = False
    issues = list(HttpsCheck().run(site))
    assert [i.key for i in issues] == ["no_hsts"]
    assert module_score(issues, Module.SEO) == 100
