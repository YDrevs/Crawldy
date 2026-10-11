"""`seo.click_depth`: що саме він міряє — і чого з цього не випливає.

Чек рахує посилання **зі** сторінки. Його код зветься `click_depth`, а
підпис для власника колись стверджував «на цю сторінку майже нічого не
веде» — три різні поняття під одним іменем: вихідні посилання, вхідні
посилання й глибина кліків.

Помилку зробили не в коді, а в тексті: `consequence` дописали пізніше, і
автор прочитав ім'я коду, а не тіло методу. Жоден тест того не побачив,
бо на сам чек тесту не було взагалі — лише згадка в параметрах
`test_report_builder`.

Тому тут перевіряється не «чек спрацював», а **відповідність твердження
вимірюванню**: сторінка з великою кількістю вхідних посилань і малою
вихідних мусить спрацьовувати, а сторінка з багатьма вихідними — мовчати
незалежно від глибини. Граф будується справжній: якби тест підмінив його
результат, та сама плутанина повернулася б непоміченою.
"""

from __future__ import annotations

import importlib

from app.audit.checks.seo import ThinOutboundLinkingCheck
from app.audit.i18n import Locale
from app.audit.link_graph import build
from app.audit.logical_pages import normalize
from app.audit.types import PageSignals
from tests.factories import context, page_from_html

LOCALES = ("en", "uk", "de", "es", "fr", "ru")


def _page(url: str, links: list[str], *, depth: int = 1) -> PageSignals:
    anchors = "".join(f'<a href="{href}">x</a>' for href in links)
    html = f"<html><head><title>t</title></head><body><h1>h</h1>{anchors}</body></html>"
    return page_from_html(html, url=url, depth=depth)


def _flagged(ctx: object) -> set[str]:
    return {issue.page_url for issue in ThinOutboundLinkingCheck().run(ctx)}


# ── що чек стверджує ───────────────────────────────────────────────────────


def test_a_page_everyone_links_to_is_still_flagged_when_it_leads_nowhere():
    """Найважливіший тест файлу: вхідні посилання чека не обходять.

    Саме цей випадок робив старий підпис неправдою. Сторінку `/services/`
    згадують усі — і про неї ж клієнт читав «на цю сторінку майже нічого
    не веде».
    """
    home = _page("https://example.com/", ["/services/", "/a/", "/b/"], depth=0)
    a = _page("https://example.com/a/", ["/services/", "/b/", "/"], depth=1)
    b = _page("https://example.com/b/", ["/services/", "/a/", "/"], depth=1)
    services = _page("https://example.com/services/", [], depth=1)
    ctx = context(home, a, b, services)

    # Граф ключується нормалізованою адресою, знахідка — тією, якою
    # сторінку відкривали. Різниця навмисна, і тест її не приховує.
    graph = build(ctx)
    key = normalize("https://example.com/services/")
    assert graph.incoming[key] == 3, "на сторінку справді веде весь сайт"
    assert graph.outgoing[key] == 0, "а сама вона не веде нікуди"

    assert "https://example.com/services/" in _flagged(ctx), (
        "чек судить вихідні посилання, і вони відсутні"
    )


def test_a_page_that_links_onward_is_silent_however_deep_it_sits():
    """Глибина — не предмет цього чека, хай як зветься його код."""
    home = _page("https://example.com/", ["/a/"], depth=0)
    deep = _page(
        "https://example.com/deep/", ["/a/", "/b/", "/c/", "/d/"], depth=4
    )
    ctx = context(home, deep)

    graph = build(ctx)
    key = normalize("https://example.com/deep/")
    assert graph.depth[key] == 4, "сторінка справді лежить глибоко"

    assert "https://example.com/deep/" not in _flagged(ctx), (
        "але посилань зі себе в неї вистачає"
    )


def test_a_shallow_dead_end_and_a_deep_hub_are_told_apart():
    """Дві сторінки, протилежні за обома ознаками, мають різні відповіді."""
    home = _page("https://example.com/", ["/dead/", "/hub/"], depth=0)
    shallow_dead_end = _page("https://example.com/dead/", [], depth=1)
    deep_hub = _page(
        "https://example.com/hub/", ["/1/", "/2/", "/3/"], depth=5
    )
    ctx = context(home, shallow_dead_end, deep_hub)

    flagged = _flagged(ctx)
    assert "https://example.com/dead/" in flagged
    assert "https://example.com/hub/" not in flagged


def test_the_threshold_counts_only_internal_links():
    """Посилання назовні не роблять сторінку зв'язаною з рештою сайту."""
    home = _page("https://example.com/", ["/a/"], depth=0)
    outward = _page(
        "https://example.com/outward/",
        ["https://other.example/1", "https://other.example/2", "/a/"],
        depth=1,
    )
    ctx = context(home, outward)

    assert "https://example.com/outward/" in _flagged(ctx)


def test_the_evidence_names_the_direction_it_measured():
    """Доказ читає інструмент, і з нього має бути видно, що саме порахували."""
    home = _page("https://example.com/", [], depth=0)
    ctx = context(home)

    issues = list(ThinOutboundLinkingCheck().run(ctx))
    assert issues, "порожня головна — випадок чека"
    evidence = issues[0].evidence
    assert evidence["outbound_internal_links"] == 0
    assert "links from this page" in evidence["measures"]


# ── чи відповідає текст вимірюванню ────────────────────────────────────────

# Твердження про ВХІДНІ посилання. Жодне з них не випливає з підрахунку
# вихідних, і саме таке речення стояло тут до виправлення.
INCOMING_CLAIMS = {
    "en": ("links to this page", "nothing links to", "few pages link"),
    "uk": ("на сторінку", "на цю сторінку", "нічого не веде"),
    "de": ("verlinkt auf diese seite", "auf diese seite"),
    "es": ("enlaza a esta página", "a esta página"),
    "fr": ("pointe vers cette page", "vers cette page"),
    "ru": ("на страницу", "на эту страницу", "ничто не ссылается"),
}


def test_no_locale_claims_anything_about_incoming_links():
    """Регресія на саму помилку: підпис не має говорити про вхідні.

    Перевіряється `consequence` і `title` — тексти, які бачить власник.
    `description` виняток: там ми навмисно згадуємо вхідні посилання, щоб
    сказати, що про них цей чек НЕ говорить.
    """
    offenders = []
    for loc in LOCALES:
        entry = importlib.import_module(f"app.audit.i18n.{loc}").MESSAGES["seo.click_depth"]
        for field in ("title", "consequence"):
            text = entry[field].lower()
            for claim in INCOMING_CLAIMS[loc]:
                if claim in text:
                    offenders.append(f"{loc}/{field}: {claim!r}")
    assert not offenders, f"твердження про вхідні посилання: {offenders}"


def test_every_locale_still_renders_the_measured_number():
    """Число в заголовку — те саме, що порахував чек."""
    for loc in LOCALES:
        entry = importlib.import_module(f"app.audit.i18n.{loc}").MESSAGES["seo.click_depth"]
        assert "{internal_links}" in entry["title"], loc


def test_the_finding_reads_consistently_end_to_end():
    """Заголовок і наслідок беруться з каталогу тим самим шляхом, що в звіті."""
    home = _page("https://example.com/", [], depth=0)
    issue = next(iter(ThinOutboundLinkingCheck().run(context(home))))

    from app.audit import i18n

    # Той самий виклик, яким звіт перетворює знахідку на текст
    # (`report.builder._localise`), а не окремий шлях для тесту.
    text = i18n.render(issue.msg or issue.code, issue.params, Locale.EN)
    assert "Few links from this page onward: 0" == text.title
    assert "nowhere to go next" in i18n.CATALOGS[Locale.EN]["seo.click_depth"]["consequence"]


# ── чи доходить критерій до кожної поверхні ────────────────────────────────


def _report_source(issues: list) -> object:
    """Той самий збірник, яким користуються тести звіту."""
    from tests.test_report_builder import source

    return source(issues)


def _finding() -> tuple[object, list]:
    page = _page("https://example.com/", ["/x/"], depth=0)
    issues = list(ThinOutboundLinkingCheck().run(context(page)))
    assert issues, "сторінка з одним посиланням — випадок чека"
    return _report_source(issues), issues


def test_the_criterion_reaches_every_surface_in_every_supported_locale():
    """Критерій не існує, поки він не дійшов до всіх поверхонь усіма мовами.

    Знахідка може загубитися між детектором і клієнтом кількома різними
    способами: не потрапити в рекомендації, зникнути з JSON, не дійти до
    екрана або до Word, чи дійти англійською в німецькому звіті. Кожен із
    них видно лише там, де його шукають, — тому шукаємо в усіх одразу.

    Авторитет щодо мов звіту — `COMPLETE_LOCALES`: похідна від явного
    прапорця `complete=True` в реєстрі `LOCALES`. Сам `LOCALES` ширший
    (12 мов) і описує сайт та інтерфейс, а не звіти; просити повноти від
    усіх дванадцяти означало б або фарбувати тест червоним за задумом,
    або плодити каталоги мовами, якими звіт не продається. Запит звіту
    непідтримуваною мовою лягає на англійський фолбек явно — це рішення,
    а не випадковість, і перевіряється воно окремо.
    """
    import io
    import re
    import uuid
    import zipfile

    from app.audit import i18n
    from app.report.builder import build_report
    from app.report.docx import render_docx
    from app.report.web import to_web

    src, issues = _finding()
    audit_id, site_id = uuid.uuid4(), uuid.uuid4()

    gaps: list[str] = []
    for locale in i18n.COMPLETE_LOCALES:
        document = build_report(src, locale)
        title = i18n.render("seo.click_depth", issues[0].params, locale).title

        if not any(i.code == "seo.click_depth" for i in document.issues):
            gaps.append(f"{locale.value}: немає серед знахідок")
        if not any(r.issue_key == "seo.click_depth" for r in document.recommendations):
            gaps.append(f"{locale.value}: немає серед рекомендацій")
        if title not in str(document.to_json()):
            gaps.append(f"{locale.value}: немає в JSON-звіті")

        web = to_web(
            document,
            audit_id=audit_id,
            site_id=site_id,
            status="completed",
            finished_at=None,
            fallback_locale=i18n.FALLBACK_LOCALE.value,
        )
        if title not in web.model_dump_json():
            gaps.append(f"{locale.value}: немає у відповіді API")

        blob = render_docx(document, locale)
        xml = zipfile.ZipFile(io.BytesIO(blob)).read("word/document.xml").decode("utf-8")
        if title.split(":")[0][:20] not in re.sub(r"<[^>]+>", "", xml):
            gaps.append(f"{locale.value}: немає у Word-звіті")

    assert not gaps, f"критерій не доїхав до поверхні: {gaps}"


def test_no_locale_silently_falls_back_to_english():
    """Фолбек тут був би невидимим: німецький звіт з англійським рядком.

    Тест порівнює не з англійською взагалі, а саме заголовок і наслідок:
    збіг означав би, що переклад не дійшов, а не що мови схожі.
    """
    from app.audit import i18n

    english = i18n.CATALOGS[i18n.Locale.EN]["seo.click_depth"]
    borrowed = [
        f"{locale.value}/{field}"
        for locale in i18n.COMPLETE_LOCALES
        if locale is not i18n.Locale.EN
        for field in ("title", "description", "recommendation", "consequence")
        if i18n.CATALOGS[locale]["seo.click_depth"][field] == english[field]
    ]
    assert not borrowed, f"англійський рядок у неанглійському каталозі: {borrowed}"


def test_the_free_view_still_builds_in_every_locale_with_this_finding():
    """Безкоштовний вигляд не зобов'язаний показати LOW-знахідку.

    Він показує три головні проблеми, і слабка перелінковка серед них
    опиниться рідко. Перевіряється інше: що присутність цієї знахідки не
    ламає збірку короткого вигляду жодною з мов.
    """
    from app.audit import i18n
    from app.report.builder import build_report
    from app.report.short import to_short

    src, _ = _finding()
    for locale in i18n.COMPLETE_LOCALES:
        short = to_short(build_report(src, locale), audit_id="a1", unlocked=False)
        assert short.overall_band, locale.value

