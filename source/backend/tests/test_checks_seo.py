from app.audit import applicability
from app.audit.applicability import (
    ClaimVerdict,
    Coverage,
    declare,
    evidence_for_context,
    finalise,
)
from app.audit.checks.base import all_checks
from app.audit.checks.seo import (
    CanonicalCheck,
    CleanUrlCheck,
    DuplicateTitleCheck,
    H1Check,
    HttpsCheck,
    IndexabilityCheck,
    RobotsTxtCheck,
    TitleCheck,
)
from app.audit.route_classes import RouteClass, classify_page, classify_route
from app.audit.site_context import _parse_robots
from app.audit.types import RobotsInfo
from tests.factories import context, page_from_html

GOOD = """<html lang="uk"><head>
<title>Достатньо довгий заголовок сторінки для SEO перевірки</title>
<link rel="canonical" href="https://example.com/"></head>
<body><h1>Один</h1></body></html>"""


def test_title_check_passes_on_good_page():
    assert list(TitleCheck().run(context(page_from_html(GOOD)))) == []


def test_title_check_flags_missing_title():
    issues = list(TitleCheck().run(context(page_from_html("<html><body>x</body></html>"))))
    assert [i.code for i in issues] == ["seo.title"]
    assert issues[0].severity.value == "critical"


def test_duplicate_titles_detected():
    p1 = page_from_html(GOOD, url="https://example.com/a")
    p2 = page_from_html(GOOD, url="https://example.com/b")
    issues = list(DuplicateTitleCheck().run(context(p1, p2)))
    assert len(issues) == 1
    assert issues[0].evidence["urls"] == ["https://example.com/a", "https://example.com/b"]


def test_h1_check_flags_multiple():
    html = "<html><body><h1>A</h1><h1>B</h1></body></html>"
    issues = list(H1Check().run(context(page_from_html(html))))
    # Ключ і параметри, а не текст: чек віддає саме їх, а формулювання
    # належить каталогу й міняється разом із мовою.
    assert issues[0].msg == "seo.h1.multiple"
    assert issues[0].params == {"count": 2}


def test_noindex_is_an_observation_not_an_accusation():
    """Ми бачимо вказівку, але не намір, тож і не кричимо «критично».

    На калібрувальній вибірці критичними ставали PPC-лендинги Shopify,
    архів вебінару й закрите демо Cloudflare — усе закрито навмисно й
    правильно. Випадок без сумнівів ловить `seo.links_to_noindex`.
    """
    html = '<html><head><meta name="robots" content="noindex,nofollow"></head><body></body></html>'
    issues = list(IndexabilityCheck().run(context(page_from_html(html))))
    assert issues
    assert issues[0].severity.value == "medium"
    assert issues[0].confidence.value == "medium"


def test_canonical_mismatch():
    html = '<html><head><link rel="canonical" href="https://example.com/other"></head><body></body></html>'
    issues = list(CanonicalCheck().run(context(page_from_html(html))))
    assert issues[0].msg == "seo.canonical.mismatch"


def test_robots_disallow_all():
    ctx = context(page_from_html(GOOD), robots=RobotsInfo(exists=True, disallows_all=True, sitemaps=["s"]))
    issues = list(RobotsTxtCheck().run(ctx))
    assert any(i.severity.value == "critical" for i in issues)


def test_https_check_flags_plain_http():
    ctx = context(page_from_html(GOOD), is_https=False)
    assert next(iter(HttpsCheck().run(ctx))).severity.value == "critical"


def test_invalid_certificate_is_critical_and_outranks_hsts():
    """Сайт із таким сертифікатом відвідувач узагалі не побачить, тож
    докоряти йому за відсутній HSTS немає сенсу."""
    ctx = context(page_from_html(GOOD), is_https=True, hsts=False, tls_error="[SSL: BAD_CERT]")
    issues = list(HttpsCheck().run(ctx))

    assert [i.msg for i in issues] == ["seo.https.invalid_cert"]
    assert issues[0].severity.value == "critical"
    assert issues[0].evidence["error"] == "[SSL: BAD_CERT]"


def test_valid_certificate_produces_no_tls_issue():
    ctx = context(page_from_html(GOOD), is_https=True, hsts=True, tls_error=None)
    assert list(HttpsCheck().run(ctx)) == []


# ── E-05: перевірка застосовується лише до маршрутів, яких стосується ──
#
# Фікстури контракту `E-05-STATE` і `E-05-ROUTES`. Кожен тест названий
# своїм ідентифікатором, щоб знахідку в звіті можна було привʼязати до
# рядка контракту, а не до здогаду про намір.

BODY = "<p>%s</p>" % ("Достатньо тексту, щоб сторінку було з чого судити. " * 12)


def _html(title: str = "", *, noindex: bool = False, canonical: str = "", head: str = "") -> str:
    parts = [f"<title>{title}</title>" if title else ""]
    if noindex:
        parts.append('<meta name="robots" content="noindex,follow">')
    if canonical:
        parts.append(f'<link rel="canonical" href="{canonical}">')
    parts.append(head)
    return (f'<html lang="en"><head>{"".join(parts)}</head>'
            f'<body><h1>{title or "Заголовок"}</h1>{BODY}</body></html>')


def _robots(body: str | None) -> RobotsInfo:
    """robots.txt як факт: або прочитаний, або відповідь «файлу немає».

    `None` тут означає саме «сервер відповів 404», а не «ми не питали»:
    друге — окремий стан, і плутати їх не можна.
    """
    info = RobotsInfo(status_code=200 if body else 404, content=body or "")
    if body:
        info.exists = True
        _parse_robots(info)
    return info


def _site(*specs, robots: str | None = None):
    """Контекст із перелічених (адреса, html, статус)."""
    pages = []
    for url, html, status in specs:
        page = page_from_html(html, url=url)
        page.status_code = status
        pages.append(page)
    return context(*pages, robots=_robots(robots))


def _issues(ctx, code: str):
    """Знахідки чека рівно так, як їх бачить аудит — через шов застосовності."""
    check = next(c for c in all_checks() if c.code == code)
    return list(check.run(ctx))


def _keys(ctx, code: str) -> list[str]:
    return sorted(i.issue_key for i in _issues(ctx, code))


def _state(ctx, key: str) -> tuple[str, str]:
    """Канонічний стан претензії — з дописаними знахідками, як у звіті.

    `evidence_for_context` рахує застосовність із контексту, де знахідок
    ще немає, тож без `finalise` кожна судима претензія виглядала б
    пройденою. Той самий порядок, що й у білдері звіту.
    """
    code = key.split(":")[0]
    row = finalise(evidence_for_context(ctx), _issues(ctx, code))[key]
    return row["verdict"], row["coverage"]


# `contracts/fixtures.json → E-05-ROUTES`, дванадцять випадків. Перелічені
# тут, а не зчитані з файлу контракту: тест мусить лишатися правдою і тоді,
# коли контракту поруч немає, а розбіжність із ним ловить окремий аудит
# таблиці на всі 1008 клітинок.
_SEARCH_MODES_ON_CONTENT = {
    "seo.canonical:missing": "EVALUATE", "seo.canonical:mismatch": "EVALUATE",
    "seo.title:missing": "EVALUATE", "seo.title:too_long": "EVALUATE",
    "seo.clean_url:uppercase": "EVALUATE", "seo.clean_url:query": "EVALUATE",
    "ai.opengraph:tags": "EVALUATE", "ai.twitter_card": "EVALUATE",
    "tech.mixed_content:blockable": "EVALUATE", "seo.noindex": "NA_A12",
}
_MODES_OFF_SEARCH = {
    "seo.canonical:missing": "NA_%(a)s", "seo.canonical:mismatch": "NA_%(a)s",
    "seo.title:missing": "NA_%(a)s", "seo.title:too_long": "NA_%(a)s",
    "seo.clean_url:uppercase": "NA_%(a)s", "seo.clean_url:query": "NA_%(a)s",
    "ai.opengraph:tags": "NA_A06", "ai.twitter_card": "NA_A06",
    "tech.mixed_content:blockable": "EVALUATE", "seo.noindex": "NA_%(n)s",
}
_MODES_PUBLIC_NOT_A_TARGET = {
    "seo.canonical:missing": "NA_A01", "seo.canonical:mismatch": "EVALUATE",
    "seo.title:missing": "EVALUATE", "seo.title:too_long": "NA_A01",
    "seo.clean_url:uppercase": "EVALUATE", "seo.clean_url:query": "NA_A01",
    "ai.opengraph:tags": "EVALUATE", "ai.twitter_card": "EVALUATE",
    "tech.mixed_content:blockable": "EVALUATE", "seo.noindex": "COND",
}


def _off_search(reason: str, noindex_reason: str = "A08") -> dict[str, str]:
    return {k: v % {"a": reason, "n": noindex_reason} for k, v in _MODES_OFF_SEARCH.items()}


_UNKNOWN_MODES = {**{k: "NO_VERDICT_UNKNOWN" for k in _SEARCH_MODES_ON_CONTENT},
                  "tech.mixed_content:blockable": "EVALUATE"}

def _rules(*disallow: str) -> str:
    """robots.txt із перелічених заборон. Без заборон — дозволено все."""
    lines = ["User-agent: *", *(f"Disallow: {path}" for path in disallow)]
    if not disallow:
        lines.append("Allow: /")
    return "\n".join(lines) + "\n"


FIXTURES = [
    {"id": "E05R-01", "url": "https://example.com/pricing", "fetched": True, "status": 200,
     "robots": _rules(), "page": {"title": "Ціни"},
     "route_class": "public_indexable_content", "expected_modes": _SEARCH_MODES_ON_CONTENT},
    {"id": "E05R-02", "url": "https://example.com/privacy", "fetched": True, "status": 200,
     "robots": _rules(), "page": {"title": "Приватність", "noindex": True},
     "route_class": "public_noindex_informational", "expected_modes": _MODES_PUBLIC_NOT_A_TARGET},
    {"id": "E05R-03", "url": "https://example.com/methodology", "fetched": True, "status": 200,
     "robots": _rules(), "page": {"title": "Як ми рахуємо"},
     "route_class": "public_indexable_content", "expected_modes": _SEARCH_MODES_ON_CONTENT},
    {"id": "E05R-04", "url": "https://example.com/login", "fetched": True, "status": 200,
     "robots": _rules("/login"), "page": {},
     "route_class": "known_non_search_funnel", "expected_modes": _off_search("A02")},
    {"id": "E05R-05", "url": "https://example.com/checkout", "fetched": True, "status": 200,
     "robots": _rules("/checkout"), "page": {},
     "route_class": "known_non_search_funnel", "expected_modes": _off_search("A02")},
    {"id": "E05R-06", "url": "https://example.com/buy", "fetched": True, "status": 200,
     "robots": _rules("/buy"), "page": {},
     "route_class": "known_non_search_funnel", "expected_modes": _off_search("A02")},
    {"id": "E05R-07", "url": "https://example.com/app/audits", "fetched": True, "status": 200,
     "robots": _rules("/app"), "page": {},
     "route_class": "authenticated_account", "expected_modes": _off_search("A03")},
    {"id": "E05R-08", "url": "https://example.com/admin/payments", "fetched": True, "status": 200,
     "robots": _rules("/admin"), "page": {},
     "route_class": "private_admin_system", "expected_modes": _off_search("A04")},
    {"id": "E05R-09", "url": "https://example.com/this-route-does-not-exist", "fetched": True,
     "status": 404, "robots": _rules(), "page": {},
     "route_class": "error_transient", "expected_modes": _off_search("A05", "A05")},
    {"id": "E05R-10", "url": "https://example.com/payment-processing", "fetched": True,
     "status": 200, "robots": _rules(), "page": {},
     "route_class": "error_transient", "expected_modes": _off_search("A05", "A05")},
    # Єдиний нефетчений випадок, і це не дрібниця фікстури: клас
    # «невизначений» існує рівно для адреси, яку ми знаємо з карти чи з
    # посилання й не відкривали. Прочитана сторінка завжди має спостережену
    # індексованість, тож невизначеною бути не може.
    {"id": "E05R-11", "url": "https://example.com/xyzzy", "fetched": False, "status": None,
     "robots": None, "page": {}, "route_class": "unknown_unclassified",
     "expected_modes": _UNKNOWN_MODES},
    {"id": "E05R-12", "url": "https://example.com/campaign/spring", "fetched": True, "status": 200,
     "robots": _rules(), "page": {"title": "Весна", "noindex": True},
     "route_class": "public_shareable_content", "expected_modes": _MODES_PUBLIC_NOT_A_TARGET},
]


def test_e05r_every_route_example_lands_on_its_declared_class():
    """E05R-01…12: вісім класів маршруту, дванадцять прикладів контракту.

    Клас перевіряється на ЖИВОМУ класифікаторі, тим самим входом, яким
    користується двигун. `/xyzzy` єдиний іде іншим шляхом навмисно: це
    адреса, яку ми знаємо з карти й не відкривали, а застосовність
    вирішується з завантажених фактів — без них вердикту немає.
    """
    for case in FIXTURES:
        if case["fetched"]:
            ctx = _site((case["url"], _html(**case["page"]), case["status"]),
                        robots=case["robots"])
            # Саме `ctx.pages[0]`, а не `ok_pages`: сторінка помилки в
            # прочитані не входить, а класифікувати її треба — інакше
            # клас «документ помилки» нічим не перевірити.
            got = classify_page(ctx, ctx.pages[0]).route_class.value
        else:
            got = classify_route(case["url"], title="", schema_types=(), locales=()).route_class.value
        assert got == case["route_class"], f'{case["id"]}: {case["url"]} → {got}'


def test_e05r_every_declared_mode_matches_the_contract():
    """E05R-01…12: по десять варіантів на випадок — 120 оголошених режимів."""
    for case in FIXTURES:
        for spec, want in case["expected_modes"].items():
            code, _, variant = spec.partition(":")
            got = declare(code, RouteClass(case["route_class"]), variant).mode.value
            assert got == want, f'{case["id"]} {spec}: {got} ≠ {want}'


def test_e05_f12_a_login_page_without_a_title_is_not_an_seo_penalty():
    """E05-f12. Заголовок сторінки входу обіцяє результат у пошуку, якого

    в неї немає й бути не повинно. Доти `/login` роками втрачав бали за
    відсутній title — і жоден звіт не пояснював, що з цим робити.
    """
    ctx = _site(("https://example.com/login", _html(), 200),
                robots=_rules("/login"))
    assert classify_page(ctx, ctx.ok_pages[0]).route_class is RouteClass.KNOWN_NON_SEARCH_FUNNEL
    assert _keys(ctx, "seo.title") == []
    assert _state(ctx, "seo.title") == (ClaimVerdict.NOT_APPLICABLE, Coverage.COMPLETE)
    assert declare("seo.title", RouteClass.KNOWN_NON_SEARCH_FUNNEL, "missing").reason_code == "A-02"


def test_e05_f13_underscore_in_a_checkout_url_is_not_an_seo_penalty():
    """E05-f13. Гігієна адреси — твердження про пошук, а не про сторінку."""
    ctx = _site(("https://example.com/Checkout_Step_2", _html("Оплата"), 200),
                robots=_rules("/Checkout_Step_2"))
    assert classify_page(ctx, ctx.ok_pages[0]).route_class is RouteClass.KNOWN_NON_SEARCH_FUNNEL
    assert _keys(ctx, "seo.clean_url") == []
    # Той самий слоґ на публічній сторінці лишається знахідкою: змінилось
    # не правило гігієни, а те, до чого воно застосовується.
    public = _site(("https://example.com/Case_Study", _html("Кейс"), 200), robots=None)
    assert list(CleanUrlCheck().run(public))
    assert "seo.clean_url:underscore" in _keys(public, "seo.clean_url")


def test_e05_f2_a_funnel_route_withholds_the_index_only_and_structure_family():
    """E05-f2. Маршрут воронки не судиться пошуковими претензіями…"""
    ctx = _site(("https://example.com/checkout", _html(), 200),
                robots=_rules("/checkout"))
    for code in ("seo.title", "seo.canonical", "seo.clean_url", "ai.opengraph", "ai.twitter_card"):
        assert _keys(ctx, code) == [], code
        assert _state(ctx, code)[0] == ClaimVerdict.NOT_APPLICABLE, code


def test_e05_f3_page_facts_are_still_judged_on_a_funnel_route():
    """E05-f3. …але факти про саму сторінку лишаються фактами.

    Форма входу, яка шле пароль методом GET, кладе його в адресний рядок
    і в журнали проксі. Те, що сторінка поза пошуком, цього не змінює.
    """
    form = ('<form method="get" action="/in">'
            '<input type="text" name="name">'
            '<input type="email" name="email">'
            '<textarea name="message"></textarea>'
            "</form>")
    ctx = _site(("https://example.com/login",
                 _html().replace("</body>", f"{form}</body>"), 200),
                robots=_rules("/login"))
    assert "tech.form_protection:get_method" in _keys(ctx, "tech.form_protection")
    assert _state(ctx, "tech.form_protection")[0] == ClaimVerdict.FAIL


def test_e05_f1_a_missing_canonical_on_indexable_content_still_fails():
    """E05-f1. Контроль: там, де претензія доречна, вона судить як судила.

    Без цього тесту решта переліку доводила б лише те, що двигун навчився
    мовчати.
    """
    ctx = _site(("https://example.com/pricing", _html("Ціни на аудит сайту"), 200),
                robots=_rules())
    assert "seo.canonical:missing" in _keys(ctx, "seo.canonical")
    assert _state(ctx, "seo.canonical") == (ClaimVerdict.FAIL, Coverage.COMPLETE)


def test_e05_f4_noindex_withholds_index_only_but_not_the_page_facts():
    """E05-f4. Сторінка під `noindex`: три різні відповіді на одній адресі.

    Претензія про індекс не має предмета (A-01); намір власника лишається
    питанням, на яке відповідає сам чек; факт про сторінку лишається
    фактом.
    """
    ctx = _site(("https://example.com/privacy",
                 _html("Політика приватності", noindex=True), 200), robots=_rules())
    assert classify_page(ctx, ctx.ok_pages[0]).route_class is RouteClass.PUBLIC_NOINDEX_INFORMATIONAL
    assert _keys(ctx, "seo.canonical") == []
    # Стан читається на ВАРІАНТІ, а не на коді: під `seo.canonical` живуть
    # дві різні претензії, і на цьому маршруті вони розходяться — саме
    # тому варіанти й оголошують свій клас окремо.
    assert _state(ctx, "seo.canonical:missing") == (ClaimVerdict.NOT_APPLICABLE, Coverage.COMPLETE)
    assert declare("seo.canonical", RouteClass.PUBLIC_NOINDEX_INFORMATIONAL,
                   "missing").reason_code == "A-01"
    # `seo.noindex` судить саме намір, і на цьому маршруті він судиться.
    assert declare("seo.noindex", RouteClass.PUBLIC_NOINDEX_INFORMATIONAL).mode.value == "COND"
    assert _keys(ctx, "seo.viewport") or _state(ctx, "seo.viewport")[0] in (
        ClaimVerdict.PASS, ClaimVerdict.FAIL)


def test_e05_f11_a_contradictory_canonical_survives_noindex():
    """E05-f11. Canonical, що вказує не туди, — факт про саму розмітку.

    `missing` і `mismatch` живуть під одним кодом і мусять розійтися тут:
    перший питає про індекс, другий описує суперечність, яку видно на
    сторінці незалежно від того, чи є вона ціллю пошуку.
    """
    ctx = _site(("https://example.com/terms",
                 _html("Умови", noindex=True, canonical="https://example.com/elsewhere"), 200),
                robots=_rules())
    assert "seo.canonical:mismatch" in _keys(ctx, "seo.canonical")
    assert declare("seo.canonical", RouteClass.PUBLIC_NOINDEX_INFORMATIONAL,
                   "mismatch").mode.value == "EVALUATE"


def test_e05_f5_a_mixed_site_judges_only_its_content_pages():
    """E05-f5. Вісім сторінок вмісту, три службові: судяться вісім.

    Перевіряється саме ЛІЧИЛЬНИК, а не лише мовчання: підрахунок
    застосовного — те, з чого потім складається покриття, і помилитись у
    ньому можна, не помилившись у жодній знахідці.
    """
    pages = [(f"https://example.com/guide-{i}", _html(f"Посібник номер {i} про аудит"), 200)
             for i in range(8)]
    pages += [("https://example.com/login", _html(), 200),
              ("https://example.com/checkout", _html(), 200),
              ("https://example.com/app", _html(), 200)]
    ctx = _site(*pages, robots=_rules("/login", "/checkout", "/app"))
    row = evidence_for_context(ctx)["seo.canonical:missing"]
    assert row["evaluated"] == 8
    assert row["not_applicable"] == 3
    assert set(row["rules"]) == {"R-APPLIES", "A-02", "A-03"}
    assert row["rules"]["A-02"] == 2 and row["rules"]["A-03"] == 1
    # Однакові заголовки службових сторінок не роблять їх дублікатами.
    assert _keys(ctx, "seo.title.duplicate") == []


def test_e05_f6_a_site_of_only_funnel_routes_has_nothing_to_judge():
    """E05-f6. Жодної застосовної сторінки: нуль знахідок, нуль похвали.

    Саме тут ламався старий двигун в обидва боки: він і штрафував такий
    сайт за відсутні title, і зараховував мовчання решти чеків у
    пройдені.
    """
    ctx = _site(("https://example.com/login", _html(), 200),
                ("https://example.com/checkout", _html(), 200),
                ("https://example.com/buy", _html(), 200),
                robots=_rules("/login", "/checkout", "/buy"))
    row = evidence_for_context(ctx)["seo.canonical:missing"]
    assert row["evaluated"] == 0
    assert (row["verdict"], row["coverage"]) == (ClaimVerdict.NOT_APPLICABLE, Coverage.COMPLETE)
    assert row["rules"] == {"A-02": 3}
    for code in ("seo.title", "seo.canonical", "seo.clean_url"):
        assert _keys(ctx, code) == [], code


def test_e05_f7_an_indexable_checkout_stays_judged_and_is_recorded():
    """E05-f7. Форма воронки без підтвердження наміру — публічний вміст.

    Це межа правила, а не виняток із нього: ми бачимо адресу, але наміру
    власника не бачимо, а сторінка, яку сайт САМ віддає пошуку, лишається
    сторінкою для пошуку. Запис A-11 зберігає те, що форма помічена.
    """
    ctx = _site(("https://example.com/checkout", _html("Оформлення замовлення"), 200),
                robots=_rules())
    verdict = classify_page(ctx, ctx.ok_pages[0])
    assert verdict.route_class is RouteClass.PUBLIC_INDEXABLE_CONTENT
    assert verdict.funnel_shaped_but_indexable is True
    assert verdict.shape is RouteClass.KNOWN_NON_SEARCH_FUNNEL
    assert "seo.canonical:missing" in _keys(ctx, "seo.canonical")


def test_e05_f8_localized_funnel_routes_are_recognised_after_the_locale_strip():
    """E05-f8. `/de/login` і `/uk/kabinet` — ті самі маршрути, інші адреси.

    Працює лише разом з E-12: мову знімають зі шляху тоді, коли сайт її
    оголосив. Неоголошений префікс маршруту не змінює.
    """
    head = ('<link rel="alternate" hreflang="de" href="https://example.com/de/login">'
            '<link rel="alternate" hreflang="uk" href="https://example.com/uk/kabinet">')
    ctx = _site(("https://example.com/de/login", _html(head=head), 200),
                ("https://example.com/uk/kabinet", _html(head=head), 200),
                robots=_rules("/de/login", "/uk/kabinet"))
    classes = {p.url: classify_page(ctx, p).route_class for p in ctx.ok_pages}
    assert classes["https://example.com/de/login"] is RouteClass.KNOWN_NON_SEARCH_FUNNEL
    assert classes["https://example.com/uk/kabinet"] is RouteClass.AUTHENTICATED_ACCOUNT
    assert _keys(ctx, "seo.title") == []


def test_e05_a_route_we_never_opened_gets_no_verdict_at_all():
    """Межа E05R-11: застосовність вирішується із ЗАВАНТАЖЕНИХ фактів.

    Адреса з карти, яку ми не відкривали, не має ані класу, ані вердикту.
    Назвати її публічним вмістом означало б вигадати спостереження; назвати
    службовою — вигадати намір власника.
    """
    verdict = classify_route("https://example.com/xyzzy", title="", schema_types=(), locales=())
    assert verdict.route_class is RouteClass.UNKNOWN_UNCLASSIFIED
    declaration = declare("seo.title", RouteClass.UNKNOWN_UNCLASSIFIED, "missing")
    assert declaration.mode.value == "NO_VERDICT_UNKNOWN"
    assert declaration.can_emit_factual_finding is False
    assert declaration.score_affecting is False
    assert declaration.reason_code == "R-UNKNOWN-ROUTE-CLASS"


# ── E-05: важіль сумісності дістає ВСІХ трьох споживачів ──────────────
#
# Відкат оголошений контрактом як одна дія: «policy table to
# always-applicable restores today's behaviour». Споживач, який лишився
# збоку від цього важеля, робить відкат неповним — і саме так виглядав
# перший варіант: бал повертався, а тридцять одна site-level знахідка
# лишалась на новому джерелі. Тести нижче тримають усіх трьох на одному
# важелі, кожного своїм питанням.


def _legacy(monkeypatch) -> None:
    """Увімкнути режим сумісності так, як його вмикає сам відкат."""
    monkeypatch.setattr(applicability, "COMPATIBILITY_MODE", True)


def _service_page(url: str, *, disallow: str | None = None):
    ctx = _site((url, _html(), 200), robots=_rules(*( [disallow] if disallow else [])))
    return ctx, ctx.ok_pages[0]


def test_compatibility_mode_is_read_from_the_policy_table_itself():
    """Важіль — сама таблиця, а не окремий прапорець.

    Прапорець можна забути перемкнути; таблицю — ні, бо саме її змінює
    відкат. Перевіряється обидва боки: чинна таблиця дає «політика є»,
    а таблиця, у якій жодна клітинка нічого не притримує, дає «політики
    немає».
    """
    assert applicability.COMPATIBILITY_MODE is False
    assert applicability._policy_is_always_applicable() is False

    from app.audit.applicability import ClaimClass, Mode
    everything_applies = {claim: dict.fromkeys(RouteClass, Mode.EVALUATE) for claim in ClaimClass}
    original = applicability.POLICY
    try:
        applicability.POLICY = everything_applies
        assert applicability._policy_is_always_applicable() is True
    finally:
        applicability.POLICY = original


def test_duplicates_returns_to_the_legacy_indexability_source(monkeypatch):
    """Дублікати: у режимі сумісності службовість знову питає `type_of`.

    Випадок обраний так, щоб дві відповіді РОЗІЙШЛИСЬ, інакше тест
    проходив би й тоді, коли важіль не під'єднано: `/app/audits` під
    забороною robots — підтверджений кабінет за новою таблицею, і
    `PageType.OTHER`, тобто звичайна сторінка за старим набором.
    """
    from app.audit.page_kinds import NOT_FOR_SEARCH

    ctx, page = _service_page("https://example.com/app/audits", disallow="/app")
    assert ctx.type_of(page) not in NOT_FOR_SEARCH
    assert applicability.service_shaped(ctx, page) is True
    _legacy(monkeypatch)
    assert applicability.service_shaped(ctx, page) is False


def test_sitemap_audit_returns_to_the_legacy_reason_and_evidence(monkeypatch):
    """Звірка карти: і причина, і ДОКАЗ мусять збігтися зі старими.

    Новий ключ `route_class` у доказі — нова відповідь на нове питання.
    У режимі сумісності його не сміє бути взагалі, інакше доказ старої
    знахідки відрізнявся б від прийнятого, і відкат був би неповним у
    місці, куди ніхто не дивиться.
    """
    from app.audit import sitemap_audit

    url = "https://example.com/app/audits"
    ctx, page = _service_page(url, disallow="/app")
    reasons, detail = sitemap_audit._reasons_for(ctx, url, page, {url: page}, {url})
    assert sitemap_audit.Reason.NOT_FOR_SEARCH in reasons
    assert detail["route_class"] == "authenticated_account"

    _legacy(monkeypatch)
    reasons, detail = sitemap_audit._reasons_for(ctx, url, page, {url: page}, {url})
    assert sitemap_audit.Reason.NOT_FOR_SEARCH not in reasons
    assert "route_class" not in detail


def test_link_graph_returns_to_reporting_every_noindex_target(monkeypatch):
    """Граф посилань: до G4b він не питав про службовість узагалі.

    Тому режим сумісності мусить давати не «інший набір службових», а
    ЖОДНОГО — інакше посилання на власний вхід лишилось би прихованим і
    після відкату.
    """
    from app.audit import link_graph

    closed = ('<html lang="en"><head><meta name="robots" content="noindex"></head>'
              "<body><h1>Вхід</h1></body></html>")
    home = _html("Головна сторінка про послуги")
    home = home.replace("</body>", '<a href="https://example.com/login">Вхід</a></body>')
    ctx = _site(("https://example.com/", home, 200),
                ("https://example.com/login", closed, 200),
                robots=_rules("/login"))

    assert applicability.service_route(ctx, ctx.ok_pages[1]) is True
    assert link_graph.build(ctx).to_noindex == []

    _legacy(monkeypatch)
    assert applicability.service_route(ctx, ctx.ok_pages[1]) is False
    pairs = link_graph.build(ctx).to_noindex
    assert pairs == [("https://example.com/", "https://example.com/login")]


def test_passed_checks_eligibility_is_part_of_the_same_lever(monkeypatch):
    """Правило `PASS + COMPLETE` теж вимикається таблицею, не окремо.

    Інакше відкат повертав би знахідки й лишав змінений перелік
    пройдених — той самий дефект, на пів кроку далі.
    """
    from app.report import passed as passed_module

    evidence = {
        "robots_txt": {"exists": True, "status_code": 200},
        "applicability": {"seo.robots_txt": {
            "check": "seo.robots_txt", "variant": "", "verdict": "PASS",
            "coverage": "PARTIAL", "evaluated": 4,
        }},
    }
    assert passed_module.eligible(evidence, "seo.robots_txt") is False
    _legacy(monkeypatch)
    assert passed_module.eligible(evidence, "seo.robots_txt") is True
