"""Реєстр AI-краулерів і оцінка robots.txt за RFC 9309.

Два предмети в одному файлі, бо перевіряються вони разом: реєстр без
правильної оцінки дає хибні знахідки, оцінка без провенансу — знахідки,
яких нема кому пояснити.

Жодного мока розбирача: усе, що тут перевіряється, — це і є семантика
розбору. Підмінити її означало б перевірити власну підміну.
"""

from __future__ import annotations

import importlib
from datetime import date, timedelta

import pytest

from app.audit import robots
from app.audit.checks.llm_visibility import AiCrawlerAccessCheck
from app.audit.i18n import CATALOGS, COMPLETE_LOCALES
from app.audit.standards import AI_CRAWLERS, CrawlerPurpose
from app.audit.standards import ai_crawlers as reg
from app.audit.types import RobotsInfo
from tests.factories import context, page_from_html

PAGE = "<html><head><title>t</title></head><body><h1>h</h1><p>text here</p></body></html>"


def _ctx(robots_txt: str, *, paths: tuple[str, ...] = ("/",)):
    pages = [page_from_html(PAGE, url=f"https://example.com{p}", depth=0) for p in paths]
    return context(*pages, robots=RobotsInfo(exists=True, status_code=200, content=robots_txt))


def _issue(robots_txt: str, **kw):
    found = list(AiCrawlerAccessCheck().run(_ctx(robots_txt, **kw)))
    return found[0] if found else None


# ── RFC 9309: вибір групи ──────────────────────────────────────────────────


def test_a_specific_group_overrides_the_wildcard_group():
    """Своя група краулера скасовує загальну, а не додається до неї."""
    parsed = robots.parse(
        "User-agent: *\nDisallow: /\n\nUser-agent: OAI-SearchBot\nAllow: /\n"
    )
    assert parsed.evaluate("OAI-SearchBot", "/page").allowed is True
    assert parsed.evaluate("GPTBot", "/page").allowed is False


def test_the_wildcard_group_applies_when_nothing_else_matches():
    parsed = robots.parse("User-agent: *\nDisallow: /secret/\n")
    decision = parsed.evaluate("Claude-User", "/secret/x")
    assert decision.allowed is False
    assert decision.matched_group == "*"


def test_with_no_group_at_all_everything_is_allowed():
    """RFC: немає групи — немає правил. Це не те саме, що заборона."""
    parsed = robots.parse("Sitemap: https://example.com/sitemap.xml\n")
    assert parsed.evaluate("GPTBot", "/anything").allowed is True


def test_groups_sharing_a_user_agent_are_merged():
    """Кілька груп з тим самим агентом зливаються в одну."""
    parsed = robots.parse(
        "User-agent: GPTBot\nDisallow: /a/\n\nUser-agent: GPTBot\nDisallow: /b/\n"
    )
    assert parsed.evaluate("GPTBot", "/a/x").allowed is False
    assert parsed.evaluate("GPTBot", "/b/x").allowed is False


def test_several_agents_in_one_group_share_its_rules():
    parsed = robots.parse("User-agent: GPTBot\nUser-agent: ClaudeBot\nDisallow: /\n")
    assert parsed.evaluate("GPTBot", "/x").allowed is False
    assert parsed.evaluate("ClaudeBot", "/x").allowed is False


def test_agent_matching_ignores_case():
    parsed = robots.parse("User-agent: gptbot\nDisallow: /\n")
    assert parsed.evaluate("GPTBot", "/x").allowed is False


# ── RFC 9309: правила шляху ────────────────────────────────────────────────


def test_the_longest_matching_rule_wins():
    """Найдовший збіг, а не останній і не перший у файлі."""
    parsed = robots.parse(
        "User-agent: *\nDisallow: /docs/\nAllow: /docs/public/\n"
    )
    assert parsed.evaluate("GPTBot", "/docs/private").allowed is False
    assert parsed.evaluate("GPTBot", "/docs/public/a").allowed is True


def test_an_equal_length_tie_goes_to_allow():
    """RFC: за однакової довжини перемагає `allow`."""
    parsed = robots.parse("User-agent: *\nDisallow: /x\nAllow: /x\n")
    assert parsed.evaluate("GPTBot", "/x").allowed is True


def test_wildcard_and_end_anchor_are_supported():
    parsed = robots.parse("User-agent: *\nDisallow: /*.pdf$\n")
    assert parsed.evaluate("GPTBot", "/files/report.pdf").allowed is False
    # `$` прив'язує до кінця: рядок запиту вже не збігається.
    assert parsed.evaluate("GPTBot", "/files/report.pdf?v=2").allowed is True


def test_an_empty_disallow_forbids_nothing():
    """`Disallow:` без значення — це «дозволено все», а не заборона."""
    parsed = robots.parse("User-agent: *\nDisallow:\n")
    assert parsed.evaluate("GPTBot", "/anything").allowed is True


def test_a_decision_names_the_rule_that_produced_it():
    """Доказ мусить показувати правило, а не лише вирок."""
    parsed = robots.parse("User-agent: *\nDisallow: /private/\n")
    decision = parsed.evaluate("GPTBot", "/private/x")
    assert decision.reason == "Disallow: /private/"
    assert decision.rule is not None and decision.rule.allow is False


# ── детектор: призначення вирішує формулювання ─────────────────────────────


def test_a_blocked_search_crawler_is_reported_as_a_search_problem():
    issue = _issue("User-agent: OAI-SearchBot\nDisallow: /\n")
    assert issue is not None
    assert issue.msg == "llm.crawler_blocked.search"
    assert issue.evidence["purpose"] == "search"


def test_a_blocked_user_agent_is_reported_as_user_directed():
    issue = _issue("User-agent: Claude-User\nDisallow: /\n")
    assert issue is not None
    assert issue.msg == "llm.crawler_blocked.user"


def test_a_blocked_training_crawler_is_not_dressed_up_as_a_visibility_defect():
    """Найважливіше розрізнення файлу: відмова від навчання — це вибір."""
    issue = _issue("User-agent: GPTBot\nDisallow: /\n")
    assert issue is not None
    assert issue.msg == "llm.crawler_blocked.training"

    from app.audit.i18n import Locale

    entry = CATALOGS[Locale.EN]["llm.crawler_blocked.training"]
    assert "legitimate choice" in entry["description"]
    assert "not a fault" in entry["consequence"]


def test_search_outranks_training_when_both_are_blocked():
    """Сказати треба про найважливіше, а не про перше в файлі."""
    issue = _issue(
        "User-agent: GPTBot\nDisallow: /\n\nUser-agent: OAI-SearchBot\nDisallow: /\n"
    )
    assert issue is not None
    assert issue.msg == "llm.crawler_blocked.search"
    # Але навчальний краулер не зникає — він у доказі.
    assert "training" in issue.evidence["by_purpose"]


def test_one_vendor_with_different_purposes_is_not_collapsed():
    """Anthropic має три токени з трьома різними призначеннями."""
    issue = _issue(
        "User-agent: ClaudeBot\nDisallow: /\n\nUser-agent: Claude-SearchBot\nDisallow: /\n"
    )
    assert issue is not None
    by_purpose = issue.evidence["by_purpose"]
    assert by_purpose["search"] == ["Claude-SearchBot"]
    assert by_purpose["training"] == ["ClaudeBot"]


# ── детектор: обсяг заборони ───────────────────────────────────────────────


def test_a_partial_block_is_reported_with_the_paths_it_affects():
    """Часткова заборона — теж заборона, і раніше її не було видно взагалі."""
    issue = _issue(
        "User-agent: OAI-SearchBot\nDisallow: /blog/\n",
        paths=("/", "/blog/post", "/about"),
    )
    assert issue is not None
    entry = next(e for e in issue.evidence["blocked"] if e["token"] == "OAI-SearchBot")
    assert entry["scope"] == "paths"
    assert entry["denied_paths"] == ["/blog/post"]
    assert entry["rule"] == "Disallow: /blog/"


def test_a_full_block_is_marked_as_covering_the_site():
    issue = _issue(
        "User-agent: OAI-SearchBot\nDisallow: /\n", paths=("/", "/a", "/b")
    )
    assert issue is not None
    entry = next(e for e in issue.evidence["blocked"] if e["token"] == "OAI-SearchBot")
    assert entry["scope"] == "site"


def test_an_unrelated_disallow_does_not_make_a_crawler_blocked():
    """Заборона на шлях, якого ми не читали, знахідкою не є."""
    assert _issue("User-agent: *\nDisallow: /admin/\n", paths=("/", "/about")) is None


def test_an_open_robots_file_produces_nothing():
    assert _issue("User-agent: *\nAllow: /\n") is None


def test_a_retired_token_no_longer_triggers_anything():
    """`anthropic-ai` вендор більше не документує — реєстр його не знає."""
    assert _issue("User-agent: anthropic-ai\nDisallow: /\n") is None
    assert _issue("User-agent: CCBot\nDisallow: /\n") is None


def test_the_evidence_carries_provenance_for_every_blocked_crawler():
    """Клієнт має бачити, звідки ми взагалі знаємо про цього бота."""
    issue = _issue("User-agent: Claude-SearchBot\nDisallow: /\n")
    assert issue is not None
    entry = issue.evidence["blocked"][0]
    assert entry["vendor"] == "Anthropic"
    assert entry["source"].startswith("https://")
    assert entry["matched_group"] == "claude-searchbot"


# ── реєстр: провенанс ──────────────────────────────────────────────────────


def test_the_registry_passes_its_own_validation():
    assert reg.registry_problems() == []


def test_every_entry_has_a_vendor_source_and_verification_date():
    for crawler in AI_CRAWLERS:
        assert crawler.vendor.strip(), crawler.token
        assert crawler.source_url.startswith("https://"), crawler.token
        assert isinstance(crawler.last_verified_at, date), crawler.token
        assert crawler.purposes, crawler.token
        assert all(isinstance(p, CrawlerPurpose) for p in crawler.purposes), crawler.token


def test_tokens_are_unique():
    keys = [c.key for c in AI_CRAWLERS]
    assert len(keys) == len(set(keys))


def test_stale_verification_is_reported_not_ignored():
    """Реєстр без свіжості нічим не кращий за кортеж, з якого він виріс."""
    future = date.today() + timedelta(days=reg.VERIFICATION_MAX_AGE_DAYS + 30)
    problems = reg.registry_problems(today=future)
    assert problems, "прострочену звірку має бути видно"
    assert all("звірку не оновлювали" in p for p in problems)


def test_retired_tokens_are_not_silently_resurrected():
    known = {c.key for c in AI_CRAWLERS}
    assert not (known & set(reg.RETIRED_TOKENS))
    # І кожне зняття має причину, а не порожній рядок.
    assert all(reason.strip() for reason in reg.RETIRED_TOKENS.values())


def test_every_purpose_in_the_taxonomy_has_a_real_entry():
    """Таксономія існує, лише поки кожне значення має справжній запис.

    Значення додається під конкретний запис, а не про запас: інакше
    зʼявляється категорія, якої ніхто ніколи не бачив у звіті.
    """
    present = {p for c in AI_CRAWLERS for p in c.purposes}
    assert present == set(CrawlerPurpose)


def test_google_extended_carries_both_of_its_documented_purposes():
    """Один токен, два призначення — і саме тому призначення це кортеж.

    Google описує його як керування і навчанням, і grounding. Назвати це
    лише навчанням означало б промовчати про єдину частину, що справді
    коштує видимості.
    """
    google = reg.crawler_for("Google-Extended")
    assert google is not None
    assert set(google.purposes) == {CrawlerPurpose.GROUNDING, CrawlerPurpose.TRAINING}


def test_blocking_google_extended_is_never_called_a_search_problem():
    """Google прямо каже, що цей токен Пошуку не стосується."""
    issue = _issue("User-agent: Google-Extended\nDisallow: /\n")
    assert issue is not None
    assert issue.msg == "llm.crawler_blocked.grounding"
    assert issue.evidence["purpose"] == "grounding"

    from app.audit.i18n import Locale

    entry = CATALOGS[Locale.EN]["llm.crawler_blocked.grounding"]
    assert "not a Search problem" in entry["description"]
    assert "unaffected" in entry["consequence"]


def test_a_multi_purpose_crawler_appears_under_each_of_its_purposes():
    issue = _issue("User-agent: Google-Extended\nDisallow: /\n")
    assert issue is not None
    by_purpose = issue.evidence["by_purpose"]
    assert by_purpose["grounding"] == ["Google-Extended"]
    assert by_purpose["training"] == ["Google-Extended"]


def test_search_still_outranks_grounding():
    issue = _issue(
        "User-agent: Google-Extended\nDisallow: /\n\n"
        "User-agent: OAI-SearchBot\nDisallow: /\n"
    )
    assert issue is not None
    assert issue.msg == "llm.crawler_blocked.search"


# ── агент, який robots.txt не виконує ──────────────────────────────────────


def test_perplexity_user_is_not_reported_as_blocked_by_robots():
    """Вендор пише, що цей агент robots.txt зазвичай ігнорує.

    Отже, заборона в robots.txt не є доказом блокування, і знахідкою
    вона стати не може — інакше ми б спростовували власне джерело.
    """
    assert reg.crawler_for("Perplexity-User").obeys_robots is False
    assert _issue("User-agent: Perplexity-User\nDisallow: /\n") is None


def test_the_directive_is_still_recorded_as_an_observation():
    """Мовчати теж не можна: власник міг вважати, що закрив доступ."""
    issue = _issue(
        "User-agent: Perplexity-User\nDisallow: /\n\n"
        "User-agent: PerplexityBot\nDisallow: /\n"
    )
    assert issue is not None
    # Пошуковий краулер того самого вендора robots.txt виконує — він і є знахідкою.
    assert [e["token"] for e in issue.evidence["blocked"]] == ["PerplexityBot"]
    ignored = issue.evidence["directives_ignored_by_vendor"]
    assert [e["token"] for e in ignored] == ["Perplexity-User"]
    assert ignored[0]["rule"] == "Disallow: /"


def test_the_sibling_search_crawler_still_obeys_robots():
    """Розрізнення всередині одного вендора: бот виконує, агент — ні."""
    assert reg.crawler_for("PerplexityBot").obeys_robots is True
    issue = _issue("User-agent: PerplexityBot\nDisallow: /\n")
    assert issue is not None and issue.msg == "llm.crawler_blocked.search"


def test_the_registry_needs_no_network_at_audit_time():
    """Оновлення реєстру — реліз, а не запит у документацію вендора."""
    source = (
        importlib.import_module("app.audit.standards.ai_crawlers").__file__ or ""
    )
    text = open(source, encoding="utf-8").read()
    for forbidden in ("httpx", "requests", "urlopen", "aiohttp"):
        assert forbidden not in text, f"реєстр не має ходити в мережу: {forbidden}"


# ── повнота по всіх мовах звіту ────────────────────────────────────────────

PURPOSE_KEYS = (
    "llm.crawler_blocked.search",
    "llm.crawler_blocked.grounding",
    "llm.crawler_blocked.user",
    "llm.crawler_blocked.training",
)


@pytest.mark.parametrize("key", PURPOSE_KEYS)
def test_every_report_locale_has_the_message(key: str):
    """Мови звіту — COMPLETE_LOCALES, а не ширший реєстр LOCALES."""
    missing = [
        f"{locale.value}/{field}"
        for locale in COMPLETE_LOCALES
        for field in ("title", "description", "recommendation", "consequence")
        if not (CATALOGS[locale].get(key) or {}).get(field)
    ]
    assert not missing, f"немає рядків: {missing}"


@pytest.mark.parametrize("key", PURPOSE_KEYS)
def test_no_locale_silently_borrows_the_english_string(key: str):
    from app.audit.i18n import Locale

    english = CATALOGS[Locale.EN][key]
    borrowed = [
        f"{locale.value}/{field}"
        for locale in COMPLETE_LOCALES
        if locale is not Locale.EN
        for field in ("title", "description", "recommendation", "consequence")
        if CATALOGS[locale][key][field] == english[field]
    ]
    assert not borrowed, f"англійський рядок у неанглійському каталозі: {borrowed}"


def test_no_wording_equates_crawler_access_with_actual_presence():
    """Доступ краулера — не присутність у відповідях. Межа продукту.

    Забороняються не слова, а обіцянки: «будете згадані», «гарантує
    цитування», «не з'явитеся ніде». Дозволене «may reduce» лишається,
    бо воно говорить про ймовірність, а не про факт.
    """
    forbidden = (
        "will be cited", "guarantees", "ensures you appear", "will appear in",
        "буде процитовано", "гарантує", "з'явитеся у відповідях",
        "wird zitiert", "garantiert",
        "será citado", "garantiza",
        "sera cité", "garantit",
        "будет процитировано", "гарантирует",
    )
    offenders = [
        f"{locale.value}/{key}: {phrase}"
        for locale in COMPLETE_LOCALES
        for key in PURPOSE_KEYS
        for field in ("title", "description", "recommendation", "consequence")
        for phrase in forbidden
        if phrase in CATALOGS[locale][key][field].lower()
    ]
    assert not offenders, f"готовність подана як присутність: {offenders}"


def test_the_grounding_copy_stays_within_what_the_vendor_establishes():
    """Формулювання не має розширювати те, що Google справді каже.

    Було: «асистент не може спиратися на ваші сторінки» — твердження про
    будь-якого асистента і як про доконаний факт. Google встановлює
    вужче: токен керує тим, чи МОЖЕ зібраний ним вміст іти в grounding у
    Gemini Apps і Vertex AI. Тому в тексті мусять бути і названі
    поверхні, і застереження про інших асистентів.
    """
    from app.audit.i18n import Locale

    entry = CATALOGS[Locale.EN]["llm.crawler_blocked.grounding"]
    assert "Gemini Apps and Vertex AI" in entry["description"]
    assert "may be used for grounding" in entry["description"]
    assert "not a Search problem" in entry["description"]

    consequence = entry["consequence"]
    assert "may not be used as a source" in consequence
    assert "nothing about other assistants" in consequence
    assert "unaffected" in consequence
    # Категоричних тверджень про будь-якого асистента бути не може.
    for overclaim in ("cannot draw", "an assistant may draw", "will not appear"):
        assert overclaim not in consequence.lower()


def test_grounding_copy_is_revisited_if_a_non_google_token_appears():
    """Текст називає поверхні Google, бо grounding-токен поки один.

    Щойно зʼявиться чужий, ці рядки перестануть бути правдою для нього —
    і тест має впасти тут, а не в клієнтському звіті.
    """
    grounding = [c for c in AI_CRAWLERS if CrawlerPurpose.GROUNDING in c.purposes]
    vendors = {c.vendor for c in grounding}
    assert vendors == {"Google"}, (
        "зʼявився grounding-токен іншого вендора: перепишіть "
        "llm.crawler_blocked.grounding у всіх COMPLETE_LOCALES"
    )
