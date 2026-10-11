"""Мовні версії: граматика значень, три механізми оголошення, чеки.

Кожен випадок відповідає на одне питання, і майже кожен має пару «чиста
сторінка мовчить»: чек, який спрацьовує там, де все правильно, гірший за
відсутній — його знахідку клієнт спростує за десять секунд.

Найважливіше тут — не окремі спрацювання, а те, що HTML, заголовок HTTP
і карта сайту дають однаковий результат. Google називає ці три способи
рівноцінними; сайт, який зробив усе правильно в карті, не має отримувати
зауваження за те, що ми дивилися лише в HTML.
"""

from __future__ import annotations

import json

import pytest

from app.audit import hreflang, snapshot
from app.audit.checks.seo import (
    HreflangBrokenTargetCheck,
    HreflangConflictCheck,
    HreflangInvalidCheck,
    HreflangMissingCheck,
    HreflangReciprocityCheck,
)
from app.audit.extractor import extract
from app.audit.fetcher import FetchResult
from app.audit.site_context import _parse_sitemap
from app.audit.standards import language_tags
from app.audit.standards.language_tags import TagProblem
from app.audit.types import HreflangRef, SitemapInfo
from tests.factories import context

HOME = "https://example.com/"
DE = "https://example.com/de"
FR = "https://example.com/fr"


def html(links=(), canonical=None, lang="en", robots=None):
    head = "".join(f'<link rel="alternate" hreflang="{c}" href="{h}">' for c, h in links)
    if canonical:
        head += f'<link rel="canonical" href="{canonical}">'
    if robots:
        head += f'<meta name="robots" content="{robots}">'
    return (
        f'<html lang="{lang}"><head><title>Page</title>{head}</head>'
        "<body><h1>Heading</h1><p>Some text for the page.</p></body></html>"
    )


def page(links=(), url=HOME, headers=None, **kw):
    body = html(links, **kw)
    return extract(
        FetchResult(
            url=url,
            final_url=url,
            status_code=200,
            content_type="text/html",
            text=body,
            body_bytes=len(body),
            elapsed_ms=90,
            headers=headers or {},
        ),
        origin="https://example.com",
    )


def issues(check_cls, ctx):
    return list(check_cls().run(ctx))


# ── 1–8. Граматика значень ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "value,language,script,region",
    [
        ("en", "en", None, None),
        ("en-GB", "en", None, "GB"),
        ("zh-Hant", "zh", "Hant", None),
        ("zh-Hans-US", "zh", "Hans", "US"),
        ("PT-br", "pt", None, "BR"),
    ],
)
def test_google_accepts_language_script_and_region_in_that_order(
    value, language, script, region
):
    """1. Граматика Google, а не BCP 47 цілком.

    Письмо за ISO 15924 в документації названо прямо: «zh-Hant, zh-Hans»,
    і комбінація `zh-Hans-US` теж наведена як приклад. Валідатор лише на
    мову й регіон відкидав би обидві правильні форми.
    """
    tag = language_tags.parse(value)
    assert tag.valid, tag.problem
    assert (tag.language, tag.script, tag.region) == (language, script, region)


@pytest.mark.parametrize(
    "value,problem",
    [
        ("en_US", TagProblem.SEPARATOR),
        ("en-UK", TagProblem.UNKNOWN_REGION),
        ("gb", TagProblem.REGION_AS_LANGUAGE),
        ("en-US-Latn", TagProblem.ORDER),
        ("zz", TagProblem.NOT_A_LANGUAGE),
        ("en-Xxxx", TagProblem.UNKNOWN_SCRIPT),
        ("", TagProblem.EMPTY),
        ("en-GB-US-FR", TagProblem.MALFORMED),
    ],
)
def test_each_way_of_getting_the_value_wrong_is_named_separately(value, problem):
    """2. Різні помилки — різні поради, тож розрізняємо їх, а не звалюємо в купу."""
    assert language_tags.parse(value).problem is problem


def test_x_default_is_reserved_and_case_insensitive():
    """3. `x-default` не мова й не регіон — окремий випадок граматики."""
    tag = language_tags.parse("X-Default")
    assert tag.x_default and tag.valid and tag.normalized == "x-default"


def test_normalisation_is_canonical_not_verbatim():
    """4. `PT-br` і `pt-BR` — те саме оголошення, і порівнюються так само."""
    assert language_tags.parse("PT-br").normalized == "pt-BR"


def test_the_registry_checks_itself():
    """5. Довідкові дані з друкарською помилкою мовчки псували б висновки."""
    assert language_tags.registry_problems() == []


def test_the_registry_names_its_sources_and_the_date_it_was_verified():
    """6. Реєстр без джерела не можна перевірити, а отже й підтримувати."""
    assert language_tags.SOURCES["google_hreflang"].startswith("https://developers.google.com")
    assert language_tags.LAST_VERIFIED_AT.year >= 2026


# ── 7–10. Три механізми оголошення ────────────────────────────────────────


def test_html_link_elements_are_collected():
    """7. Найзвичніший спосіб: `<link rel="alternate" hreflang>` у `<head>`."""
    signals = page([("de", DE)])
    assert [(r.value, r.source) for r in signals.hreflang] == [("de", "html")]


def test_http_link_header_is_collected():
    """8. Другий рівноцінний спосіб — заголовок за RFC 8288."""
    header = {"Link": f'<{DE}>; rel="alternate"; hreflang="de"'}
    signals = page(headers=header)
    assert [(r.value, r.source) for r in signals.hreflang] == [("de", "http_header")]


def test_the_header_is_read_even_when_the_response_is_not_html():
    """9. Саме заради PDF Google цей спосіб і радить.

    Заголовок читається до перевірки на HTML: інакше файл, який HTML не
    є, не мав би де оголосити свої версії взагалі.
    """
    header = {"Link": f'<{DE}>; rel="alternate"; hreflang="de"'}
    signals = extract(
        FetchResult(
            url="https://example.com/a.pdf",
            final_url="https://example.com/a.pdf",
            status_code=200,
            content_type="application/pdf",
            text="",
            body_bytes=2048,
            elapsed_ms=40,
            headers=header,
        ),
        origin="https://example.com",
    )
    assert [r.value for r in signals.hreflang] == ["de"]


def test_a_link_header_that_is_not_an_alternate_is_ignored():
    """10. `rel="preload"` мовною версією не є, хоч і живе в тому ж заголовку."""
    header = {"Link": "</style.css>; rel=preload; as=style"}
    assert page(headers=header).hreflang == []


def test_sitemap_annotations_are_kept_per_url():
    """11. Третій спосіб. Без нього сайт із правильною картою виглядав би німим."""
    xml = f"""<?xml version="1.0"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
            xmlns:xhtml="http://www.w3.org/1999/xhtml">
      <url><loc>{HOME}</loc>
        <xhtml:link rel="alternate" hreflang="en" href="{HOME}"/>
        <xhtml:link rel="alternate" hreflang="de" href="{DE}"/>
      </url>
      <url><loc>{DE}</loc></url>
    </urlset>"""
    parsed = _parse_sitemap(xml)
    assert parsed.pages == [HOME, DE] and not parsed.is_index
    assert [r.value for r in parsed.hreflang[HOME]] == ["en", "de"]
    assert DE not in parsed.hreflang


def test_a_site_that_declares_only_in_the_sitemap_is_not_warned():
    """12. Головна вимога замовника цього пункту.

    Оголошення лише в карті — повністю коректне налаштування. Чек, який
    дивиться тільки в HTML, обвинуватив би сайт у чужій помилці.
    """
    home, de = page(url=HOME), page(url=DE, lang="de")
    sitemap = SitemapInfo(
        exists=True,
        hreflang={
            HOME: [HreflangRef("en", HOME, "sitemap"), HreflangRef("de", DE, "sitemap")],
            DE: [HreflangRef("en", HOME, "sitemap"), HreflangRef("de", DE, "sitemap")],
        },
        hreflang_url_count=2,
    )
    ctx = context(home, de, sitemap=sitemap)
    assert issues(HreflangReciprocityCheck, ctx) == []
    assert issues(HreflangInvalidCheck, ctx) == []
    assert issues(HreflangMissingCheck, ctx) == []


def test_the_same_pair_declared_twice_is_one_annotation_with_two_sources():
    """13. Дублювання заради переживання зміни CMS — не дефект.

    Зведення за змістом, а не за місцем: інакше кожен обережний сайт
    отримував би вигадану знахідку про подвійні оголошення.
    """
    home = page([("de", DE)], url=HOME)
    sitemap = SitemapInfo(exists=True, hreflang={HOME: [HreflangRef("de", DE, "sitemap")]})
    site = hreflang.collect(context(home, sitemap=sitemap))
    declaration = site.by_page[HOME]
    assert len(declaration.annotations) == 1
    assert declaration.annotations[0].sources == (hreflang.Source.HTML, hreflang.Source.SITEMAP)


# ── 14–23. Чеки ───────────────────────────────────────────────────────────


def test_a_monolingual_site_is_silent_on_every_check():
    """14. Сайт, який нічого не оголосив, нічого й не порушив."""
    ctx = context(page(url=HOME), page(url="https://example.com/about"))
    for check in (
        HreflangInvalidCheck,
        HreflangReciprocityCheck,
        HreflangConflictCheck,
        HreflangBrokenTargetCheck,
    ):
        assert issues(check, ctx) == [], check.code


def test_an_invalid_value_is_reported_with_the_reason_for_each_one():
    """15. Доказ мусить казати, що саме не так, — інакше правити навмання."""
    ctx = context(page([("en_US", HOME), ("gb", DE)]))
    found = issues(HreflangInvalidCheck, ctx)
    assert len(found) == 1
    problems = {e["problem"] for e in found[0].evidence["invalid"]}
    assert problems == {"separator", "region_as_language"}


def test_a_valid_set_produces_no_invalid_finding():
    """16. Пара до попереднього: правильні значення мовчать."""
    ctx = context(page([("en", HOME), ("zh-Hans-US", DE)]))
    assert issues(HreflangInvalidCheck, ctx) == []


def test_a_page_that_never_names_itself_is_reported():
    """17. Набір без самопосилання Google вважає неповним."""
    found = issues(HreflangReciprocityCheck, context(page([("de", DE)])))
    assert [i.evidence.get("url") for i in found] == [HOME]


def test_an_x_default_pointing_here_is_not_a_self_reference():
    """18. `x-default` означає «сюди, якщо нічого не збіглося», а не «це вона»."""
    ctx = context(page([("x-default", HOME), ("de", DE)]))
    # Знахідка про самопосилання — та, що не несе доказу про взаємність.
    found = [i for i in issues(HreflangReciprocityCheck, ctx) if "missing_return" not in i.evidence]
    assert found and found[0].evidence["declared_versions"] == 2


def test_a_page_that_names_itself_is_not_reported():
    """19. Пара до 17."""
    home = page([("en", HOME), ("de", DE)], url=HOME)
    de = page([("en", HOME), ("de", DE)], url=DE, lang="de")
    assert issues(HreflangReciprocityCheck, context(home, de)) == []


def test_a_target_we_read_that_does_not_point_back_is_reported():
    """20. Взаємність вимагає Google, і тут ми її бачили на власні очі."""
    home = page([("en", HOME), ("de", DE)], url=HOME)
    de = page(url=DE, lang="de")
    found = [i for i in issues(HreflangReciprocityCheck, context(home, de))
             if i.evidence.get("missing_return")]
    assert found and found[0].evidence["missing_return"] == [DE]


def test_a_target_we_never_opened_is_not_called_missing():
    """21. Найважливіший запобіжник цього чека.

    «Сторінка не посилається назад» про сторінку, якої ми не відкривали,
    — твердження про наш бюджет краулу, а не про сайт.
    """
    ctx = context(page([("en", HOME), ("fr", FR)], url=HOME))
    found = [i for i in issues(HreflangReciprocityCheck, ctx) if i.evidence.get("missing_return")]
    assert found == []


def test_the_reciprocity_evidence_says_how_much_of_the_set_it_saw():
    """22. Число перевірених проти оголошених — межа нашого твердження."""
    home = page([("en", HOME), ("de", DE), ("fr", FR)], url=HOME)
    de = page(url=DE, lang="de")
    found = [i for i in issues(HreflangReciprocityCheck, context(home, de))
             if i.evidence.get("missing_return")]
    evidence = found[0].evidence
    assert (evidence["targets_checked"], evidence["targets_declared"]) == (1, 2)
    assert evidence["coverage_complete"] is False


def test_one_value_pointing_at_two_addresses_is_a_conflict():
    """23. Google не знає, котра мається на увазі, і може відкинути весь набір."""
    ctx = context(page([("en", HOME), ("de", DE), ("de", FR)]))
    found = [i for i in issues(HreflangConflictCheck, ctx) if i.evidence.get("kind") == "duplicate"]
    assert found and set(found[0].evidence["targets"]) == {DE, FR}


def test_two_different_x_defaults_are_a_conflict_of_their_own_kind():
    """24. Інша правка, ніж у дубля значень, — тому інший варіант."""
    ctx = context(page([("en", HOME), ("x-default", DE), ("x-default", FR)]))
    kinds = {i.evidence.get("kind") for i in issues(HreflangConflictCheck, ctx)}
    assert "x_default" in kinds


def test_a_missing_x_default_is_not_a_finding():
    """25. Він необовʼязковий, і вимагати його означало б вигадати вимогу."""
    home = page([("en", HOME), ("de", DE)], url=HOME)
    de = page([("en", HOME), ("de", DE)], url=DE, lang="de")
    assert issues(HreflangConflictCheck, context(home, de)) == []


def test_a_canonical_pointing_elsewhere_contradicts_the_declared_set():
    """26. Сторінка одночасно каже «в мене є версії» і «показуйте не мене»."""
    ctx = context(page([("en", HOME), ("de", DE)], canonical="https://example.com/other"))
    found = [i for i in issues(HreflangConflictCheck, ctx)
             if i.evidence.get("canonical_normalized")]
    assert found and found[0].evidence["canonical_normalized"] == "https://example.com/other"


def test_a_self_referential_canonical_is_not_a_conflict():
    """27. Пара до попереднього — і найчастіший правильний випадок."""
    home = page([("en", HOME), ("de", DE)], url=HOME, canonical=HOME)
    de = page([("en", HOME), ("de", DE)], url=DE, lang="de", canonical=DE)
    assert issues(HreflangConflictCheck, context(home, de)) == []


def test_a_declared_version_that_answered_with_an_error_is_reported():
    """28. Виміряне: ми відкривали адресу, і сервер відповів помилкою."""
    home = page([("en", HOME), ("de", DE)], url=HOME)
    gone = page(url=DE, lang="de")
    gone.status_code = 404
    found = issues(HreflangBrokenTargetCheck, context(home, gone))
    assert [t["status"] for i in found for t in i.evidence["targets"]] == [404]


def test_a_declared_version_closed_to_search_is_reported_separately():
    """29. Інша причина й інша правка, ніж «адреса не відповідає»."""
    home = page([("en", HOME), ("de", DE)], url=HOME)
    closed = page([("en", HOME)], url=DE, lang="de", robots="noindex")
    found = issues(HreflangBrokenTargetCheck, context(home, closed))
    assert [i.evidence["targets"][0]["target"] for i in found] == [DE]


def test_a_target_outside_the_crawl_is_not_called_broken():
    """30. Мовчання про неї — «не дивилися», а не «все гаразд»."""
    ctx = context(page([("en", HOME), ("fr", FR)], url=HOME))
    assert issues(HreflangBrokenTargetCheck, ctx) == []


def test_two_languages_without_any_declaration_are_worth_checking():
    """31. Єдиний чек родини, що спрацьовує за відсутності оголошень."""
    pages = [
        page(url=f"https://example.com/{slug}", lang=lang)
        for slug, lang in (("a", "en"), ("b", "en"), ("c", "de"), ("d", "de"))
    ]
    found = issues(HreflangMissingCheck, context(*pages))
    assert found and set(found[0].evidence["languages"]) == {"en", "de"}


def test_regional_variants_of_one_language_are_not_two_languages():
    """32. `en-US` і `en-GB` — одна мова; вимагати hreflang тут було б хибою."""
    pages = [
        page(url=f"https://example.com/{slug}", lang=lang)
        for slug, lang in (("a", "en-US"), ("b", "en-GB"), ("c", "en"), ("d", "en-AU"))
    ]
    assert issues(HreflangMissingCheck, context(*pages)) == []


def test_too_few_pages_is_not_enough_to_judge_the_languages_of_a_site():
    """33. На двох сторінках різні `lang` частіше означають помилку шаблону."""
    pages = [page(url=HOME, lang="en"), page(url=DE, lang="de")]
    assert issues(HreflangMissingCheck, context(*pages)) == []


# ── 34–36. Знімок і межі моделі ───────────────────────────────────────────


def test_a_snapshot_round_trip_keeps_every_declaration():
    """34. Перерахунок старого аудиту не має втрачати мовні версії.

    Знімок бере поля дата-класу автоматично, але збирає їх назад
    вручну — тож нове поле мовчки поверталося б словниками замість
    обʼєктів, і чек падав би вже на живих даних.
    """
    home = page([("en", HOME), ("de", DE)], url=HOME)
    sitemap = SitemapInfo(
        exists=True,
        hreflang={DE: [HreflangRef("en", HOME, "sitemap")]},
        hreflang_url_count=1,
    )
    restored = snapshot.load(json.loads(json.dumps(snapshot.dump(context(home, sitemap=sitemap)))))
    assert [r.value for r in restored.pages[0].hreflang] == ["en", "de"]
    assert restored.sitemap.hreflang[DE][0].href == HOME
    assert restored.sitemap.hreflang_url_count == 1


def test_the_findings_survive_a_snapshot_round_trip_unchanged():
    """35. Перерахунок без мережі мусить давати той самий висновок."""
    before = context(page([("en_US", HOME)], url=HOME))
    after = snapshot.load(json.loads(json.dumps(snapshot.dump(before))))
    assert [i.title for i in issues(HreflangInvalidCheck, before)] == [
        i.title for i in issues(HreflangInvalidCheck, after)
    ]


def test_a_relative_href_is_resolved_but_remembered():
    """36. Google вимагає повну адресу; ми розберемо, але запишемо факт."""
    site = hreflang.collect(context(page([("de", "/de")], url=HOME)))
    annotation = site.by_page[HOME].annotations[0]
    assert annotation.target == DE and annotation.relative is True


def test_a_snapshot_taken_before_we_could_see_hreflang_does_not_claim_absence():
    """37. Порожнеча старого знімка описує нас, а не сайт.

    Знімок схеми 1 робився до появи поля, тож у ньому мовних версій
    немає ні в кого — і чек про відсутність оголошень видав би знахідку
    56 сайтам вибірки замість двох. Це той самий клас, що й «твердження
    про відсутність вимагає, щоб ми там дивилися».
    """
    pages = [
        page(url=f"https://example.com/{slug}", lang=lang)
        for slug, lang in (("a", "en"), ("b", "en"), ("c", "de"), ("d", "de"))
    ]
    fresh = snapshot.dump(context(*pages))
    assert issues(HreflangMissingCheck, snapshot.load(fresh))

    old = json.loads(json.dumps(fresh))
    old["schema"] = "1"
    for row in old["pages"]:
        row.pop("hreflang")
    restored = snapshot.load(old)
    assert restored.hreflang_observed is False
    assert issues(HreflangMissingCheck, restored) == []


def test_a_contradictory_set_is_reported_once_not_three_times():
    """38. Одна помилка шаблону — одна знахідка, а не три.

    fastapi.tiangolo.com позначає всі тринадцять версій як `en`. Поки
    чек про взаємність судив і такі сторінки, одна правка породжувала
    три різні issue_key — суперечність, відсутнє самопосилання й брак
    зворотних посилань — і забирала 17 балів SEO замість девʼяти.
    Набір, який Google може відкинути цілком, судити на повноту нема з
    чого: спершу треба усунути суперечність.
    """
    home = page([("en", HOME), ("en", DE), ("en", FR)], url=HOME)
    de = page(url=DE, lang="de")
    ctx = context(home, de)
    assert issues(HreflangReciprocityCheck, ctx) == []
    assert [i.evidence["kind"] for i in issues(HreflangConflictCheck, ctx)] == ["duplicate"]


def test_suppression_applies_only_to_the_page_that_contradicts_itself():
    """39. Пара до попереднього: сусідня сторінка судиться як завжди."""
    broken = page([("en", HOME), ("en", DE)], url=HOME)
    lonely = page([("fr", FR)], url="https://example.com/x", lang="fr")
    found = issues(HreflangReciprocityCheck, context(broken, lonely))
    assert [i.evidence["url"] for i in found] == ["https://example.com/x"]


# ── 40–45. Реєстр письма: повнота, а не добірка ───────────────────────────


@pytest.mark.parametrize(
    "value,script",
    [
        ("zh-Bopo", "Bopo"),   # китайська, бопомофо
        ("jv-Java", "Java"),   # яванська власним письмом
        ("su-Sund", "Sund"),   # сунданська
        ("ur-Aran", "Aran"),   # урду насталіком
        ("ks-Aran", "Aran"),   # кашмірська насталіком
    ],
)
def test_scripts_outside_the_first_hand_picked_list_are_valid(value, script):
    """40. Саме ці коди добірка «поширених» і відкидала.

    Перша версія реєстру містила 39 кодів письма, вибраних на око, без
    жодного джерела. Реєстр ISO 15924 містить 226, і жодного з наведених
    тут серед тих 39 не було: клієнтові, який написав правильно, ми
    сказали б, що значення недійсне. Хибне спрацювання на коректній
    розмітці — найдорожча помилка, яку цей продукт уміє робити.
    """
    tag = language_tags.parse(value)
    assert tag.valid, tag.problem
    assert tag.script == script


def test_the_script_registry_matches_the_snapshot_it_vendored():
    """41. Мовчазне усічення списку мусить валити перевірку, а не проходити."""
    assert len(language_tags.ISO_15924) == language_tags.ISO_15924_COUNT == 226
    assert language_tags.registry_problems() == []


def test_the_script_registry_carries_its_provenance():
    """42. Реєстр без джерела й дати перевірити неможливо, а отже й оновити."""
    assert language_tags.ISO_15924_SOURCE.startswith("https://www.unicode.org/iso15924/")
    assert language_tags.ISO_15924_AMENDED.year >= 2025
    assert language_tags.ISO_15924_RETRIEVED >= language_tags.ISO_15924_AMENDED


def test_an_invented_script_code_is_still_rejected():
    """43. Пара до 40: повнота не означає, що приймається будь-що."""
    assert language_tags.parse("zh-Qzzz").problem is TagProblem.UNKNOWN_SCRIPT
    assert language_tags.parse("en-Zqqq").problem is TagProblem.UNKNOWN_SCRIPT


def test_a_deprecated_language_code_is_accepted_and_marked():
    """44. `iw` замінили на `he`, але код справжній.

    Сказати клієнтові, що його `iw` недійсний, — хибне спрацювання того
    самого роду, що й відкинутий `ks-Aran`. Факт застарілості йде в
    доказ, а не в текст: нового повідомлення це не потребує.
    """
    tag = language_tags.parse("iw-IL")
    assert tag.valid and tag.deprecated
    assert tag.as_evidence()["deprecated"] is True
    assert language_tags.parse("en-GB").deprecated is False


def test_the_region_list_is_officially_assigned_codes_by_a_stated_rule():
    """45. На відміну від письма, тут правило було й лишається.

    249 — це офіційно призначені коди ISO 3166-1 alpha-2. Винятково
    зарезервовані (`EU`, `UN`) і вилучені (`SU`, `YU`) свідомо поза
    переліком: Google націлює на країни. Це рішення про продукт, і воно
    записане у звірці покриття, а не виведене з випадкового джерела.
    """
    assert len(language_tags.ISO_3166_1) == 249
    assert "GB" in language_tags.ISO_3166_1
    assert "EU" not in language_tags.ISO_3166_1


def test_the_whole_family_costs_nothing_until_calibration():
    """46. Заморожена база скорингу — інваріант, а не намір.

    Ваговиті чеки заморозка не забороняє, але ці підібрані на одному
    багатомовному сайті й рухали SEO на девʼять балів. Аудит учора й
    аудит сьогодні дали б різні бали одному сайту без змін на ньому.
    Знахідки, докази й рекомендації працюють; ціна — рішення §K.4.
    """
    from app.audit.checks import all_checks
    from app.audit.enums import Severity

    family = [c for c in all_checks() if c.code.startswith("seo.hreflang")]
    assert len(family) == 5
    for check in family:
        assert check.weight == 0, check.code
        assert check.severity is Severity.INFO, check.code


def test_findings_still_reach_the_report_while_costing_nothing():
    """47. Нуль ваги не має означати нуль присутності.

    Вимога була явною: прибрати вплив на бал, зберігши виявлення,
    докази, рекомендації й звіт. Тест тримає обидві половини разом —
    інакше наступна правка «спростить» одну з них.
    """
    from app.audit import i18n as audit_i18n
    from app.audit import scoring
    from app.audit.checks import all_checks
    from app.audit.enums import Module
    from app.audit.orchestrator import rescore
    from app.report.builder import build_report
    from app.report.source import source_from_outcome

    ctx = context(page([("en", HOME), ("en", DE)], url=HOME), page(url=DE, lang="de"))
    everything = [i for c in all_checks() for i in c.run(ctx)]
    without = [i for i in everything if not i.code.startswith("seo.hreflang")]
    assert any(i.code.startswith("seo.hreflang") for i in everything)
    assert scoring.module_score(everything, Module.SEO) == scoring.module_score(
        without, Module.SEO
    )

    doc = build_report(source_from_outcome(rescore(ctx)), audit_i18n.Locale("en"))
    hits = [r for r in doc.recommendations if r.issue_key.startswith("seo.hreflang")]
    assert hits and hits[0].evidence and hits[0].action
