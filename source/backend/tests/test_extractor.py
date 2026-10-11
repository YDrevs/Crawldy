from app.audit.extractor import extract
from app.audit.fetcher import FetchResult
from tests.factories import page_from_html

HTML = """
<!doctype html>
<html lang="uk">
<head>
  <meta charset="utf-8">
  <title>Тестова сторінка про аудит сайтів для LLM</title>
  <meta name="description" content="Достатньо довгий опис сторінки, який має пройти перевірку довжини у чеку.">
  <meta name="robots" content="index, follow">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta property="og:title" content="Тестова сторінка">
  <link rel="canonical" href="https://example.com/">
  <link rel="stylesheet" href="/a.css">
  <script src="/blocking.js"></script>
  <script src="/async.js" defer></script>
  <script type="application/ld+json">
    {"@context":"https://schema.org","@graph":[
      {"@type":"Organization","name":"Acme","sameAs":["https://wikidata.org/wiki/Q1"]},
      {"@type":"WebSite","name":"Acme"}]}
  </script>
</head>
<body>
  <main>
    <h1>Головний заголовок</h1>
    <h2>Підрозділ</h2>
    <p>Текст сторінки з достатньою кількістю слів для перевірки лічильника.</p>
    <img src="/hero.webp" alt="Герой" width="800" height="600">
    <img src="/no-alt.png" loading="lazy">
    <a href="/about">Про нас</a>
    <a href="https://external.com/x">Зовнішнє</a>
    <a href="#anchor">Якір</a>
  </main>
  <script>var inline = 1;</script>
</body>
</html>
"""


def test_extracts_head_metadata():
    page = page_from_html(HTML)
    assert page.title == "Тестова сторінка про аудит сайтів для LLM"
    assert page.lang == "uk"
    assert page.canonical == "https://example.com/"
    assert page.meta_robots == "index, follow"
    assert page.viewport
    assert page.opengraph["og:title"] == "Тестова сторінка"


def test_extracts_headings_and_text():
    page = page_from_html(HTML)
    assert page.h1 == ["Головний заголовок"]
    assert (2, "Підрозділ") in page.headings
    assert page.word_count > 5
    assert "inline" not in page.text  # скрипти вилучені з тексту


def test_extracts_links_with_internal_flag():
    page = page_from_html(HTML)
    urls = {link.url: link.is_internal for link in page.links}
    assert urls["https://example.com/about"] is True
    assert urls["https://external.com/x"] is False
    assert not any("#anchor" in u for u in urls)


def test_extracts_images():
    page = page_from_html(HTML)
    assert page.images_total == 2
    assert page.images_without_alt == 1
    assert page.images_without_dimensions == 1
    assert page.lazy_images == 1
    assert page.images_by_format == {"webp": 1, "png": 1}


def test_flattens_jsonld_graph():
    page = page_from_html(HTML)
    types = {node["@type"] for node in page.jsonld}
    assert types == {"Organization", "WebSite"}
    assert not page.jsonld_errors


def test_counts_render_blocking_resources():
    page = page_from_html(HTML)
    assert page.render_blocking_scripts == 1  # defer не рахується
    assert page.render_blocking_styles == 1
    assert page.inline_script_bytes > 0


def test_reports_invalid_jsonld():
    page = page_from_html('<html><head><script type="application/ld+json">{bad json}</script></head><body></body></html>')
    assert page.jsonld_errors


# ── сигнали для модуля захисту й аналітики ─────────────────────────────────

TECH_HTML = """<html><head>
<meta name="google-site-verification" content="abc">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Inter">
<link rel="preload" as="image" href="/hero.webp">
<script src="https://www.googletagmanager.com/gtag/js?id=G-1"></script>
<script>window.clarity=window.clarity||function(){};clarity("start")</script>
</head><body>
<a href="mailto:hi@example.com?subject=x">пошта</a>
<a href="tel:+380441234567">подзвонити</a>
<img src="/a.webp" srcset="/a-2x.webp 2x" alt="a">
<img src="/b.webp" alt="b">
<form method="post" action="/lead">
  <input name="name"><input type="email" name="email">
  <input type="hidden" name="csrf"><input type="text" name="honeypot" style="display:none">
  <button type="submit">ok</button>
</form>
<form method="get" action="/search"><input name="q"></form>
</body></html>"""


def tech_page():
    return page_from_html(TECH_HTML)


def test_response_headers_are_lowercased_and_available():
    result = FetchResult(
        url="https://example.com/", final_url="https://example.com/", status_code=200,
        content_type="text/html", text="<html></html>", body_bytes=13, elapsed_ms=10,
        headers={"Content-Security-Policy": "default-src 'self'", "X-Frame-Options": "DENY"},
    )
    page = extract(result, origin="https://example.com")

    assert page.header("content-security-policy") == "default-src 'self'"
    assert page.header("X-FRAME-OPTIONS") == "DENY", "пошук не має залежати від регістру"


def test_analytics_detected_from_src_and_from_inline_code():
    page = tech_page()
    assert "google_analytics" in page.analytics, "gtag/js на хості GTM — завантажувач GA4"
    assert "microsoft_clarity" in page.analytics, "clarity() часто вставляють інлайном"


def test_every_observation_names_its_rule_channel_and_safe_signal():
    """Доказ пояснює класифікацію, а не перевозить журнал мережі."""
    page = tech_page()

    assert page.analytics_observations, "спостереження їдуть поруч із переліком вендорів"
    for row in page.analytics_observations:
        assert row["kind"] in {"VERIFIED_VENDOR", "VERIFIED_CO_SIGNAL", "UNIDENTIFIED_MEASUREMENT"}
        assert row["rule_id"] and row["channel"] and row["signal"]
        assert "?" not in row["signal"], "параметри запиту несуть ідентифікатори — не доказ"


def test_a_measurement_host_on_an_own_subdomain_is_unidentified_not_a_vendor():
    """python.org міряє себе з analytics.python.org: вимірювання є, вендора не назвати.

    Раніше це давало мітку `first_party` — «власний лічильник», — і та
    сама мітка діставалась чужому `…-analytics.paddle.com` (E-11c). Тепер
    власність хоста вирішується межами міток імені, а вид доказу чесно
    каже, що вендора не впізнано.
    """
    html = '<html><head><script src="https://analytics.example.com/js/s.js"></script></head></html>'
    page = page_from_html(html, url="https://example.com/")

    assert page.analytics == [], "вендора ніхто не назвав"
    (row,) = page.analytics_observations
    assert row["kind"] == "UNIDENTIFIED_MEASUREMENT"
    assert row["rule_id"] == "generic.measurement_host"
    assert "first_party" not in str(page.analytics_observations)


def test_a_third_party_measurement_host_proves_nothing_about_this_site():
    """Каса Paddle шле події на власний хост: це не лічильник цього сайту (E-11c)."""
    html = (
        '<html><head><script src="https://sandbox-checkout-analytics.paddle.com/events.js">'
        "</script></head></html>"
    )
    page = page_from_html(html, url="https://example.com/")

    assert page.analytics == []
    assert page.analytics_observations == []


def test_an_app_route_named_analytics_is_not_measurement():
    """`/admin/analytics` — сторінка адмінки, а її чанк — статичний ресурс (E-11b)."""
    html = (
        '<html><head><script src="/_next/static/chunks/app/admin/analytics/page-0a1b.js">'
        "</script></head></html>"
    )
    page = page_from_html(html, url="https://example.com/admin/analytics")

    assert page.analytics == []
    assert page.analytics_observations == []


def test_a_deceptive_suffix_host_is_not_owned():
    """`analytics.example.com.evil.example` лише ПОЧИНАЄТЬСЯ з нашого імені.

    Власність хоста вирішується межами міток, а не входженням підрядка:
    інакше будь-хто, хто поставить наше імʼя всередину свого домену, дістав
    би право свідчити про наш сайт.
    """
    html = (
        '<html><head><script src="https://analytics.example.com.evil.example/js/s.js">'
        "</script></head></html>"
    )
    page = page_from_html(html, url="https://example.com/")

    assert page.analytics == []
    assert page.analytics_observations == [], "чужий хост нічого не доводить"


def test_a_look_alike_vendor_domain_does_not_match():
    """`google-analytics.com.evil.example` закінчується не на те імʼя."""
    html = (
        '<html><head><script src="https://google-analytics.com.evil.example/gtag/js">'
        "</script></head></html>"
    )
    page = page_from_html(html, url="https://example.com/")

    assert page.analytics == []


def test_self_hosted_plausible_is_recognised_by_inline_code():
    """Hugging Face віддає /js/script.js зі свого домену — впізнати можна
    лише за window.plausible в inline-коді поруч."""
    html = """<html><head><script defer src="/js/script.js"></script>
    <script>window.plausible = window.plausible || function () {};</script></head></html>"""
    page = page_from_html(html, url="https://example.com/")

    assert "plausible" in page.analytics


def test_article_about_analytics_is_not_counted_as_an_installed_counter():
    """Блог про SEO згадує google-analytics.com у тексті статті. Якби ми
    сканували весь HTML, кожна така стаття зараховувалась би за лічильник."""
    html = """<html><body><article>
    <p>Щоб підключити лічильник, вставте скрипт із google-analytics.com і
    викличте gtag( 'config' ). Альтернативи — plausible.io та matomo.js.</p>
    </article></body></html>"""
    page = page_from_html(html, url="https://example.com/")

    assert page.analytics == []


def test_verification_meta_is_recognised():
    assert tech_page().verifications == ["google_search_console"]


def test_font_hosts_are_separated_from_other_third_parties():
    page = tech_page()
    assert page.font_hosts == ["fonts.googleapis.com"]
    assert "www.googletagmanager.com" in page.third_party_hosts


def test_mailto_and_tel_are_collected_and_kept_out_of_links():
    page = tech_page()
    assert page.mailto_addresses == ["hi@example.com"], "параметри після ? відкидаються"
    assert page.tel_links == ["+380441234567"]
    assert all("mailto:" not in link.url for link in page.links)


def test_forms_capture_protection_and_field_count():
    lead, search = tech_page().forms

    assert lead.method == "post"
    # name + email + honeypot: приманка теж текстове поле, hidden і button — ні.
    assert lead.field_count == 3
    assert lead.has_honeypot is True
    assert lead.has_email_field is True
    assert search.method == "get"
    assert search.field_count == 1


def test_srcset_and_preload_are_counted():
    page = tech_page()
    assert page.images_with_srcset == 1
    assert page.images_total == 2
    assert "image" in page.preloads


# ── E-16: заголовки в порядку документа ───────────────────────────────
#
# Порядок заголовків — це факт про документ, і до E-16 він губився в самому
# екстракторі: обхід `h1`…`h6` рівень за рівнем віддавав `h1,h3,h3,h2` як
# `1,2,3,3`. Пропуск рівня в порядку читання ставав недосяжним за побудовою,
# а не «іноді непоміченим», тож жоден чек не міг його побачити.

ORDER_HTML = (
    "<html><head><title>Порядок</title></head><body><main>"
    "<h1>Заголовок</h1><h3>Глибше</h3><h3>Ще глибше</h3><h2>Назад</h2>"
    "<p>Текст сторінки.</p></main></body></html>"
)


def test_headings_keep_document_order():
    page = page_from_html(ORDER_HTML)
    assert [level for level, _text in page.headings] == [1, 3, 3, 2]
    assert page.headings[0] == (1, "Заголовок")
    assert page.headings[3] == (2, "Назад")


def test_document_order_is_marked_as_such():
    # Провенанс ставить лише екстрактор, і лише побачивши документ.
    assert page_from_html(ORDER_HTML).headings_in_document_order is True
    assert page_from_html("<html><body><main><p>Без заголовків</p></main></body></html>"
                          ).headings_in_document_order is True


def test_repeated_and_nested_headings_keep_exact_order():
    page = page_from_html(
        "<html><body><header><h2>Меню</h2></header><main>"
        "<h1>Тема</h1><section><h3>Розділ</h3><div><h2>Знову другий</h2></div></section>"
        "<h3>Останній</h3></main></body></html>"
    )
    assert page.headings == [
        (2, "Меню"), (1, "Тема"), (3, "Розділ"), (2, "Знову другий"), (3, "Останній"),
    ]


def test_h1_list_and_level_facts_are_unchanged_by_the_new_order():
    page = page_from_html(
        "<html><body><main><h1>Перший</h1><h3>Третій</h3><h1>Другий перший</h1>"
        "<h2>Другий</h2></main></body></html>"
    )
    # Список h1 — у порядку появи, як і був.
    assert page.h1 == ["Перший", "Другий перший"]
    # Набір (рівень, текст) той самий, що давав старий групований обхід:
    # змінився лише порядок, а не те, що прочитано.
    assert sorted(page.headings) == sorted([
        (1, "Перший"), (1, "Другий перший"), (2, "Другий"), (3, "Третій"),
    ])


def test_empty_headings_are_still_skipped():
    page = page_from_html(
        "<html><body><main><h1></h1><h2>  </h2><h3>Є текст</h3></main></body></html>"
    )
    assert page.headings == [(3, "Є текст")]
    assert page.h1 == []


def test_a_comma_selector_does_not_give_document_order():
    """Чому обхід дерева, а не `css("h1,h2,…")` — виміряно, а не припущено.

    selectolax віддає збіги за СЕЛЕКТОРАМИ: спершу всі `h1`, потім усі `h2`.
    Це рівно той самий групований порядок, який E-16 і виправляє, лише
    коротшим записом — тож «спрощення» екстрактора до одного селектора тихо
    поверне дефект. Тест падає, якщо хтось це зробить.
    """
    from selectolax.parser import HTMLParser

    tree = HTMLParser("<h1>A</h1><h3>B</h3><h2>C</h2>")
    by_selector = [node.tag for node in tree.css("h1,h2,h3,h4,h5,h6")]
    assert by_selector == ["h1", "h2", "h3"]  # згруповано, не за документом
    assert [level for level, _t in page_from_html(
        "<html><body><main><h1>A</h1><h3>B</h3><h2>C</h2></main></body></html>"
    ).headings] == [1, 3, 2]


# ── E-16: від видобутого порядку до правила ───────────────────────────
#
# Тести цієї секції наскрізні навмисно: вони перевіряють не сам чек, а що
# порядок, здобутий екстрактором, ДОХОДИТЬ до правила. Розділити їх означало
# б перевіряти представлення й правило окремо — а дефект E-16 жив саме на
# межі між ними, і кожна половина окремо виглядала справною.


def _order_issues(html: str):
    from app.audit.checks.seo import HeadingHierarchyCheck
    from tests.factories import context

    page = page_from_html(
        f"<html><head><title>Сторінка</title></head><body><main>{html}"
        f"<p>{'слово ' * 120}</p></main></body></html>"
    )
    return list(HeadingHierarchyCheck().run(context(page)))


def _sequence(levels: str) -> str:
    return "".join(f"<h{ch}>Заголовок {n}</h{ch}>" for n, ch in enumerate(levels, start=1))


def test_e16_f1_order_skip_is_detected():
    """E16-f1 з contracts/fixtures.json: `h1,h3,h3,h2` → FAIL, список h1 не рухається."""
    issues = _order_issues(_sequence("1332"))
    assert len(issues) == 1
    assert issues[0].code == "seo.heading_hierarchy"
    assert issues[0].params == {"previous": 1, "level": 3}
    assert issues[0].evidence["in_document_order"] is True


def test_non_skipping_sequences_stay_clean():
    for levels in ("1", "12", "123", "12321", "1223", "112233"):
        assert _order_issues(_sequence(levels)) == [], levels


def test_the_real_route_sequences_are_detected():
    """Три послідовності, що справді трапляються на 24 маршрутах пакета доказів.

    Взяті з `ROUTE-MATRIX.json → rend_heading_levels` прийнятого
    `crawldy-self-audit-v3.1-final`; повний реєстр усіх 80 маршрутів живе в
    аудиті пакета, а тут лишається постійний сторож у самому репозиторії.
    """
    for levels in ("13332222222", "1333222222", "133333222222"):
        issues = _order_issues(_sequence(levels))
        assert len(issues) == 1, levels
        assert issues[0].params == {"previous": 1, "level": 3}, levels


def test_a_level_absent_everywhere_is_reported_without_an_order_claim():
    # Рівня 2 немає ніде: це факт про множину рівнів, а не про порядок, і він
    # спрацьовував і до E-16. Доказ не отримує позначки про порядок читання
    # лише тому, що сторінка свіжа — позначка каже, що порядок доведено.
    issues = _order_issues(_sequence("133"))
    assert len(issues) == 1
    assert issues[0].params == {"previous": 1, "level": 3}
