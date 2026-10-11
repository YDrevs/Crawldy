"""Спільне представлення знахідок для порівняння двох продуктів.

Живе поза `app/` навмисно. Це інструмент вимірювання, а не частина
продукту: жоден модуль `app/` його не імпортує, тож він не може
просочитися в доменну модель. Порівняння — тимчасова робота, а
`Issue` — контракт, і змішувати їх означає зробити конкурента
частиною нашої схеми.

## Чому не рядки

Зіставляти знахідки за текстом заголовка неможливо: «Missing meta
description» і «Опис сторінки відсутній» — та сама проблема, а «Title
too long» і «Title missing» — різні, хоч і однаково починаються. Тому
кожна знахідка обох продуктів зводиться до `Topic` — нейтрального
поняття, названого так, як його назвав би той, хто робить виправлення,
а не той, хто його знайшов.

Оригінальне формулювання зберігається поруч (`raw_title`,
`raw_severity`, `source_ref`), бо без нього неможливо ані перевірити
зведення, ані процитувати конкурента чесно.

## Чого тут немає

Це не платформа для порівняння з будь-ким. Немає ані плагінів, ані
реєстру продуктів, ані схеми імпорту: два продукти, один прогін, файл
на кілька сотень рядків. Якщо колись знадобиться третій — дописати
адаптер дешевше, ніж утримувати абстракцію, яка чекала на нього роками.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Product(StrEnum):
    CRAWLDY = "crawldy"
    AUDITLENS = "auditlens"


class Topic(StrEnum):
    """Нейтральне поняття, до якого зводяться знахідки обох продуктів.

    Назване з боку виправлення, а не з боку детектора: якщо дві
    знахідки лагодяться одним і тим самим редагуванням, у них один
    `Topic`, як би по-різному продукти їх не називали.
    """

    # доступ
    ACCESS_BLOCKED = "access.blocked_to_crawler"
    ACCESS_ROBOTS = "access.robots_disallow"
    ACCESS_AI_AGENTS = "access.ai_agent_disallow"
    ACCESS_NEEDS_JS = "access.requires_javascript"

    # знаходження сторінок
    DISCOVERY_SITEMAP = "discovery.sitemap"
    DISCOVERY_ORPHANS = "discovery.orphan_pages"
    DISCOVERY_DEPTH = "discovery.click_depth"
    DISCOVERY_LINK_TARGETS = "discovery.link_targets"
    DISCOVERY_TOPICAL = "discovery.topical_structure"

    # індексованість
    INDEX_NOINDEX = "index.noindex_directive"
    INDEX_CANONICAL = "index.canonical"
    INDEX_HOST = "index.host_canonical"
    INDEX_STATUS = "index.status_codes"
    INDEX_HTTPS = "index.https"

    # сигнали на сторінці
    ONPAGE_TITLE = "onpage.title"
    ONPAGE_TITLE_DUPLICATE = "onpage.title_duplicate"
    ONPAGE_DESCRIPTION = "onpage.meta_description"
    ONPAGE_HEADINGS = "onpage.headings"
    ONPAGE_THIN = "onpage.thin_content"
    ONPAGE_IMAGE_ALT = "onpage.image_alt"
    ONPAGE_URL = "onpage.url_hygiene"
    ONPAGE_VIEWPORT = "onpage.viewport"

    # машинна читабельність
    MACHINE_SCHEMA_MISSING = "machine.structured_data_missing"
    MACHINE_SCHEMA_INVALID = "machine.structured_data_invalid"
    MACHINE_ENTITY = "machine.entity_identity"
    MACHINE_SCHEMA_TYPE = "machine.content_type_schema"
    MACHINE_SOCIAL_CARDS = "machine.social_cards"
    MACHINE_LLMS_TXT = "machine.llms_txt"
    MACHINE_LANGUAGE = "machine.language_declaration"

    # придатність бути джерелом
    CITE_DIRECT_ANSWER = "cite.direct_answer"
    CITE_AUTHORSHIP = "cite.authorship"
    CITE_ABOUT_CONTACT = "cite.about_contact"
    CITE_UNSTATED_FACTS = "cite.unstated_facts"
    CITE_BRAND = "cite.brand_consistency"
    CITE_FRESHNESS = "cite.freshness"
    CITE_STRUCTURE = "cite.document_structure"

    # швидкість
    PERF_FIELD_VITALS = "perf.field_vitals"
    PERF_LAB_DIAGNOSTICS = "perf.lab_diagnostics"
    PERF_SERVER = "perf.server_response"
    PERF_RENDER_BLOCKING = "perf.render_blocking"
    PERF_WEIGHT = "perf.page_weight"
    PERF_IMAGES = "perf.images"
    PERF_THIRD_PARTY = "perf.third_party"
    PERF_FONTS = "perf.fonts"
    PERF_MOBILE_GAP = "perf.mobile_gap"
    PERF_SCORE = "perf.score"

    # доступність
    A11Y_BLOCKING = "a11y.blocking"
    A11Y_NON_BLOCKING = "a11y.non_blocking"

    # захист і вимірювання
    TECH_SECURITY_HEADERS = "tech.security_headers"
    TECH_ANALYTICS = "tech.analytics"
    TECH_CACHING = "tech.caching"
    TECH_FORMS = "tech.form_protection"
    TECH_CONTACTS = "tech.contact_consistency"
    TECH_EMAIL = "tech.email_exposure"
    TECH_TEMPLATE = "tech.template_content"

    # конверсія — здебільшого територія AuditLens
    CRO_ACTION = "cro.call_to_action"
    CRO_TAP_TARGETS = "cro.tap_targets"
    CRO_COPY = "cro.copy_clarity"
    CRO_OFFER = "cro.offer_persuasiveness"
    CRO_HIERARCHY = "cro.visual_hierarchy"
    CRO_RESPONSIVE = "cro.responsiveness"
    # Додані після перших двох звітів AuditLens: у нас відповідників
    # немає й не планується, але без них знахідки конкурента довелося б
    # скласти в `unmapped`, тобто втратити те, чим саме він займається.
    CRO_SOCIAL_PROOF = "cro.social_proof"
    CRO_URGENCY = "cro.urgency"
    CONTENT_KEYWORDS = "content.keyword_coverage"

    # твердження про зовнішні системи: жоден продукт не міряє його на сайті
    EXTERNAL_AI_MENTIONS = "external.ai_mentions"

    # знахідка, яку не вдалося звести; лишається видимою, а не зникає
    UNMAPPED = "unmapped"


#: Crawldy: `issue_key` (або `code`, коли варіантів немає) → `Topic`.
#: Ключі беруться з реєстру чеків, а не з тексту повідомлень.
CRAWLDY_TOPICS: dict[str, Topic] = {
    "tech.crawler_blocked": Topic.ACCESS_BLOCKED,
    "llm.crawler_blocked": Topic.ACCESS_AI_AGENTS,
    "llm.client_rendered": Topic.ACCESS_NEEDS_JS,
    "seo.robots_txt:missing": Topic.ACCESS_ROBOTS,
    "seo.robots_txt:disallow_all": Topic.ACCESS_ROBOTS,
    "seo.robots_txt:no_sitemap": Topic.DISCOVERY_SITEMAP,
    "seo.sitemap:missing": Topic.DISCOVERY_SITEMAP,
    "seo.sitemap:invalid": Topic.DISCOVERY_SITEMAP,
    "seo.sitemap:empty": Topic.DISCOVERY_SITEMAP,
    "seo.sitemap:coverage": Topic.DISCOVERY_SITEMAP,
    "seo.sitemap.lastmod": Topic.DISCOVERY_SITEMAP,
    "seo.orphan_pages": Topic.DISCOVERY_ORPHANS,
    "seo.click_depth": Topic.DISCOVERY_DEPTH,
    "seo.broken_links": Topic.DISCOVERY_LINK_TARGETS,
    "seo.links_to_noindex": Topic.DISCOVERY_LINK_TARGETS,
    "seo.topic_islands": Topic.DISCOVERY_TOPICAL,
    "seo.noindex": Topic.INDEX_NOINDEX,
    "seo.canonical:missing": Topic.INDEX_CANONICAL,
    "seo.canonical:mismatch": Topic.INDEX_CANONICAL,
    "tech.host_canonical": Topic.INDEX_HOST,
    "tech.soft_404": Topic.INDEX_STATUS,
    "seo.https:missing": Topic.INDEX_HTTPS,
    "seo.https:invalid_cert": Topic.INDEX_HTTPS,
    "seo.https:no_hsts": Topic.INDEX_HTTPS,
    "seo.title:missing": Topic.ONPAGE_TITLE,
    "seo.title:too_short": Topic.ONPAGE_TITLE,
    "seo.title:too_long": Topic.ONPAGE_TITLE,
    "seo.title.duplicate": Topic.ONPAGE_TITLE_DUPLICATE,
    "seo.meta_description:missing": Topic.ONPAGE_DESCRIPTION,
    "seo.meta_description:too_long": Topic.ONPAGE_DESCRIPTION,
    "seo.meta_description:too_short": Topic.ONPAGE_DESCRIPTION,
    "seo.h1:missing": Topic.ONPAGE_HEADINGS,
    "seo.h1:multiple": Topic.ONPAGE_HEADINGS,
    "seo.heading_hierarchy": Topic.ONPAGE_HEADINGS,
    "seo.thin_content": Topic.ONPAGE_THIN,
    "seo.image_alt": Topic.ONPAGE_IMAGE_ALT,
    "seo.clean_url:uppercase": Topic.ONPAGE_URL,
    "seo.clean_url:underscore": Topic.ONPAGE_URL,
    "seo.clean_url:query": Topic.ONPAGE_URL,
    "seo.viewport": Topic.ONPAGE_VIEWPORT,
    "ai.jsonld.missing": Topic.MACHINE_SCHEMA_MISSING,
    "ai.jsonld.invalid:invalid": Topic.MACHINE_SCHEMA_INVALID,
    "ai.jsonld.invalid:no_type": Topic.MACHINE_SCHEMA_INVALID,
    "ai.schema.organization": Topic.MACHINE_ENTITY,
    "ai.entity.sameas": Topic.MACHINE_ENTITY,
    "ai.schema.contact": Topic.MACHINE_SCHEMA_TYPE,
    "ai.schema.content_type": Topic.MACHINE_SCHEMA_TYPE,
    "ai.schema.faq": Topic.MACHINE_SCHEMA_TYPE,
    "ai.schema.breadcrumb": Topic.MACHINE_SCHEMA_TYPE,
    "ai.schema.graph": Topic.MACHINE_SCHEMA_TYPE,
    "ai.opengraph:tags": Topic.MACHINE_SOCIAL_CARDS,
    "ai.opengraph:image": Topic.MACHINE_SOCIAL_CARDS,
    "ai.twitter_card": Topic.MACHINE_SOCIAL_CARDS,
    "ai.llms_txt:missing": Topic.MACHINE_LLMS_TXT,
    "ai.llms_txt:no_h1": Topic.MACHINE_LLMS_TXT,
    "ai.llms_txt:thin": Topic.MACHINE_LLMS_TXT,
    "ai.lang": Topic.MACHINE_LANGUAGE,
    "llm.direct_answer": Topic.CITE_DIRECT_ANSWER,
    "llm.authorship": Topic.CITE_AUTHORSHIP,
    "llm.about_page": Topic.CITE_ABOUT_CONTACT,
    "llm.contact_page": Topic.CITE_ABOUT_CONTACT,
    "llm.unstated_facts:offering": Topic.CITE_UNSTATED_FACTS,
    "llm.unstated_facts:location": Topic.CITE_UNSTATED_FACTS,
    "llm.unstated_facts:pricing": Topic.CITE_UNSTATED_FACTS,
    "llm.brand_consistency": Topic.CITE_BRAND,
    "llm.stale_content": Topic.CITE_FRESHNESS,
    "llm.structure": Topic.CITE_STRUCTURE,
    "perf.core_web_vitals:lcp": Topic.PERF_FIELD_VITALS,
    "perf.core_web_vitals:inp": Topic.PERF_FIELD_VITALS,
    "perf.core_web_vitals:cls": Topic.PERF_FIELD_VITALS,
    "perf.core_web_vitals:ttfb": Topic.PERF_LAB_DIAGNOSTICS,
    "perf.core_web_vitals:tbt": Topic.PERF_LAB_DIAGNOSTICS,
    "perf.server_response": Topic.PERF_SERVER,
    "perf.render_blocking": Topic.PERF_RENDER_BLOCKING,
    "perf.page_weight": Topic.PERF_WEIGHT,
    "perf.images:legacy_format": Topic.PERF_IMAGES,
    "perf.images:no_dimensions": Topic.PERF_IMAGES,
    "perf.images:no_lazy": Topic.PERF_IMAGES,
    "perf.responsive_images": Topic.PERF_IMAGES,
    "perf.third_party": Topic.PERF_THIRD_PARTY,
    "perf.external_fonts": Topic.PERF_FONTS,
    "perf.mobile_gap": Topic.PERF_MOBILE_GAP,
    "perf.lighthouse_score": Topic.PERF_SCORE,
    "perf.unavailable": Topic.PERF_SCORE,
    "a11y.blocking": Topic.A11Y_BLOCKING,
    "a11y.failures": Topic.A11Y_NON_BLOCKING,
    "tech.security_headers": Topic.TECH_SECURITY_HEADERS,
    "tech.analytics:missing": Topic.TECH_ANALYTICS,
    "tech.analytics:no_behaviour": Topic.TECH_ANALYTICS,
    "tech.caching": Topic.TECH_CACHING,
    "tech.form_protection:unprotected": Topic.TECH_FORMS,
    "tech.form_protection:get_method": Topic.TECH_FORMS,
    "tech.nap:phone_mismatch": Topic.TECH_CONTACTS,
    "tech.nap:phone_not_e164": Topic.TECH_CONTACTS,
    "tech.nap:schema_mismatch": Topic.TECH_CONTACTS,
    "tech.email_exposed": Topic.TECH_EMAIL,
    "tech.demo_content": Topic.TECH_TEMPLATE,
    "cro.no_action": Topic.CRO_ACTION,
    "cro.phone_not_tappable": Topic.CRO_TAP_TARGETS,
}


class Polarity(StrEnum):
    """Чи є знахідка твердженням про дефект.

    Потрібне, бо AuditLens рахує похвалу знахідкою: «Clear Value
    Proposition», «Strong Trust Signals», «Logical Content Flow» лежать
    у переліку «15 issues found» нарівні з дефектами. Зводити їх до
    `Topic` і мовчки рахувати як знахідки означало б порівнювати різні
    речі; викидати — правити звіт конкурента замість того, щоб його
    описати. Тому позначаємо.
    """

    DEFECT = "defect"
    PRAISE = "praise"
    """Спостереження позитивне, але подане в переліку проблем."""
    MIXED = "mixed"
    """«Добре, але могло б бути краще» — похвала з дорадчим хвостом."""


class Basis(StrEnum):
    """На чому тримається знахідка.

    Продукт може сам сказати, що не спостерігав того, про що пише:
    «Without a full page load analysis, this is an assumption»,
    «Assuming this is correctly implemented», «if any were present».
    Це не помилка нормалізації й не наша інтерпретація — це те, що
    написано в звіті, і воно мусить дожити до порівняння.
    """

    OBSERVED = "observed"
    ASSUMED = "assumed"
    """Звіт прямо називає це припущенням або пише в умовному способі."""
    UNVERIFIABLE = "unverifiable"
    """Звіт каже, що перевірити неможливо — і все одно щось стверджує."""
    INPUT_SUSPECT = "input_suspect"
    """Звіт сам сумнівається у вхідних даних, на яких стоїть знахідка."""


@dataclass(frozen=True)
class NormalizedFinding:
    """Одна знахідка одного продукту, зведена до спільного поняття.

    `topic` — те, за чим знахідки зіставляються. Решта полів зберігає
    оригінал: без них зведення неможливо перевірити, а конкурента
    неможливо процитувати чесно.
    """

    product: Product
    site: str
    topic: Topic
    raw_key: str
    """Ідентифікатор у джерелі: `issue_key` Crawldy або наш ярлик для AuditLens."""
    raw_title: str
    """Заголовок так, як його показує продукт. Не для зіставлення — для цитування."""
    raw_severity: str | None = None
    """Серйозність у шкалі джерела. Шкали різні, тому не нормалізується."""
    pages: tuple[str, ...] = ()
    evidence: dict[str, Any] = field(default_factory=dict)
    recommendation: str | None = None
    measurable: bool = True
    """Чи спирається знахідка на щось, що продукт справді спостерігав."""
    basis: Basis = Basis.OBSERVED
    """Підстава так, як її називає сам звіт. Див. `Basis`."""
    polarity: Polarity = Polarity.DEFECT
    """Чи це взагалі твердження про дефект. Див. `Polarity`."""
    source_category: str = ""
    """Розділ, у який знахідку поклав сам продукт.

    Зберігається окремо від `topic`, бо вони розходяться: AuditLens
    поклав «поле вводу не є посиланням» у розділ «Broken Links» і в тій
    самій рекомендації написав «This is a UI/UX issue, not a broken
    link». Розходження між тим, куди продукт поклав знахідку, і тим, про
    що вона насправді, — самостійний результат порівняння.
    """
    source_ref: str = ""
    """Звідки взято: файл звіту, знімок екрана, експорт."""

    def key(self) -> tuple[str, Topic]:
        return (self.site, self.topic)


@dataclass(frozen=True)
class Coverage:
    """Що продукт насправді прочитав, і чи зізнався він у прогалинах."""

    product: Product
    site: str
    pages_read: int | None
    pages_discovered: int | None
    pages_failed: int | None
    blocked: bool
    score: float | None
    """`None` означає «бала немає», а не нуль. Різниця тут головна."""
    score_withheld: bool
    """Чи продукт свідомо не дав бала, замість вигадати його."""
    disclosed: str = ""
    """Як саме продукт повідомив про прогалину, дослівно."""
    category_scores: dict[str, int] = field(default_factory=dict)
    """Бали за розділами так, як їх називає продукт.

    Не зводяться до наших модулів: розділи AuditLens («Copy & Offer»,
    «Conversion Potential») не мають відповідників, і вигадувати їх
    означало б стверджувати схожість, якої немає.
    """
    pages_stated: bool = True
    """Чи сказав продукт хоч щось про обсяг прочитаного.

    `pages_read=None` двозначне: воно означає і «не сказано», і «не
    зчитали з екрана». Цей прапорець розводить перше й друге, бо саме
    на першому тримається половина порівняння.
    """
    source_ref: str = ""


def _issue_key(issue: dict[str, Any]) -> str:
    """`issue_key`, якщо він є; інакше `code` — для звітів без варіантів."""
    return str(issue.get("issue_key") or issue.get("code") or "")


def from_crawldy_report(report: dict[str, Any], site: str, source_ref: str) -> tuple[
    list[NormalizedFinding], Coverage
]:
    """JSON-звіт Crawldy → спільне представлення.

    Читає публічний звіт, а не внутрішні обʼєкти: порівнюється те, що
    бачить клієнт, а не те, що знає рушій.
    """
    findings: list[NormalizedFinding] = []
    for issue in _walk_issues(report):
        raw = _issue_key(issue)
        topic = CRAWLDY_TOPICS.get(raw, Topic.UNMAPPED)
        findings.append(
            NormalizedFinding(
                product=Product.CRAWLDY,
                site=site,
                topic=topic,
                raw_key=raw,
                raw_title=str(issue.get("title") or ""),
                raw_severity=issue.get("severity"),
                pages=tuple(issue.get("pages") or ()),
                evidence=dict(issue.get("evidence") or {}),
                recommendation=issue.get("recommendation"),
                measurable=True,
                source_ref=source_ref,
            )
        )

    summary = report.get("summary") or {}
    cov = summary.get("coverage") or {}
    overall = summary.get("overall_score", summary.get("overall"))
    blocked = any(
        f.topic is Topic.ACCESS_BLOCKED for f in findings
    ) or bool(cov.get("blocked"))
    coverage = Coverage(
        product=Product.CRAWLDY,
        site=site,
        pages_read=cov.get("read"),
        pages_discovered=cov.get("known", cov.get("discovered")),
        pages_failed=cov.get("failed"),
        blocked=blocked,
        score=overall,
        score_withheld=overall is None,
        disclosed=json.dumps(summary.get("missing_data") or [], ensure_ascii=False),
        source_ref=source_ref,
    )
    return findings, coverage


def _walk_issues(report: dict[str, Any]) -> Iterable[dict[str, Any]]:
    """Знахідки зі звіту, у якому вони можуть лежати в кількох місцях."""
    for key in ("issues", "findings"):
        for issue in report.get(key) or ():
            yield issue
    for group in report.get("recommendations") or ():
        for issue in group.get("issues") or ():
            yield issue


def from_auditlens_export(path: Path) -> tuple[list[NormalizedFinding], list[Coverage]]:
    """Ручний експорт AuditLens → спільне представлення.

    Формат навмисно простий: продукт не має ані API, ані експорту в
    JSON, тож знахідки переносяться руками з екрана або з PDF. Файл
    зберігає дослівне формулювання й посилання на знімок, щоб кожне
    зведення можна було перевірити очима.
    """
    data = json.loads(path.read_text("utf-8"))
    findings: list[NormalizedFinding] = []
    coverages: list[Coverage] = []
    for run in data.get("runs", ()):
        site = run["site"]
        ref = run.get("source_ref", path.name)
        for row in run.get("findings", ()):
            findings.append(
                NormalizedFinding(
                    product=Product.AUDITLENS,
                    site=site,
                    topic=Topic(row["topic"]),
                    raw_key=row.get("raw_key", ""),
                    raw_title=row["raw_title"],
                    raw_severity=row.get("raw_severity"),
                    pages=tuple(row.get("pages") or ()),
                    evidence=dict(row.get("evidence") or {}),
                    recommendation=row.get("recommendation"),
                    measurable=bool(row.get("measurable", True)),
                    basis=Basis(row.get("basis", Basis.OBSERVED)),
                    polarity=Polarity(row.get("polarity", Polarity.DEFECT)),
                    source_category=row.get("source_category", ""),
                    source_ref=row.get("source_ref", ref),
                )
            )
        cov = run.get("coverage") or {}
        coverages.append(
            Coverage(
                product=Product.AUDITLENS,
                site=site,
                pages_read=cov.get("pages_read"),
                pages_discovered=cov.get("pages_discovered"),
                pages_failed=cov.get("pages_failed"),
                blocked=bool(cov.get("blocked")),
                score=cov.get("score"),
                score_withheld=bool(cov.get("score_withheld")),
                disclosed=cov.get("disclosed", ""),
                category_scores=dict(cov.get("category_scores") or {}),
                pages_stated=bool(cov.get("pages_stated", True)),
                source_ref=ref,
            )
        )
    return findings, coverages


@dataclass(frozen=True)
class Overlap:
    """Перетин знахідок двох продуктів на одному сайті."""

    site: str
    both: tuple[Topic, ...]
    crawldy_only: tuple[Topic, ...]
    auditlens_only: tuple[Topic, ...]


def compare(findings: Iterable[NormalizedFinding]) -> list[Overlap]:
    """Перетин за поняттям, а не за текстом.

    Свідомо не судить, хто має рацію: продукт, який єдиний щось знайшов,
    так само може мати хибне спрацювання, як і рацію. Це рішення
    ухвалює людина, дивлячись на сайт.
    """
    by_site: dict[str, dict[Product, set[Topic]]] = {}
    for finding in findings:
        by_site.setdefault(finding.site, {}).setdefault(finding.product, set()).add(
            finding.topic
        )
    result = []
    for site, products in sorted(by_site.items()):
        ours = products.get(Product.CRAWLDY, set())
        theirs = products.get(Product.AUDITLENS, set())
        result.append(
            Overlap(
                site=site,
                both=tuple(sorted(ours & theirs, key=lambda t: t.value)),
                crawldy_only=tuple(sorted(ours - theirs, key=lambda t: t.value)),
                auditlens_only=tuple(sorted(theirs - ours, key=lambda t: t.value)),
            )
        )
    return result


def unmapped_keys(findings: Iterable[NormalizedFinding]) -> dict[str, int]:
    """Знахідки, які не звелися. Порожньо — таблиця повна; ні — її треба дописати."""
    counts: dict[str, int] = {}
    for finding in findings:
        if finding.topic is Topic.UNMAPPED:
            counts[finding.raw_key] = counts.get(finding.raw_key, 0) + 1
    return counts
