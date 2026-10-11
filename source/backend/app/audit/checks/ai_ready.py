"""Чеки AI-ready / LLMO: структуровані дані, llms.txt, entity signals."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urlparse

from app.audit import about_page, applicability, hierarchy
from app.audit.checks.base import Check, register
from app.audit.page_kinds import PageType
from app.audit.standards.schema_entities import is_identity_type
from app.audit.types import Effort, Issue, Module, PageSignals, Severity, SiteContext

KEY_ENTITY_TYPES = {"Organization", "LocalBusiness", "Person", "WebSite"}
CONTENT_TYPES = {"Article", "BlogPosting", "NewsArticle", "Product", "Service", "Recipe"}
# Підтипи LocalBusiness зі schema.org, які реально зустрічаються.
LOCAL_TYPES = {
    "LocalBusiness", "Store", "Restaurant", "ProfessionalService", "AutoRepair",
    "HomeAndConstructionBusiness", "MedicalBusiness", "LegalService", "Dentist",
}


def types_on(page: PageSignals) -> set[str]:
    """Усі @type зі сторінки, включно з ВКЛАДЕНИМИ вузлами.

    `publisher: {"@type": "Organization", ...}` — так само оголошена
    сутність, як і вузол верхнього рівня. Раніше вкладені губились, і
    сайт із видавцем-організацією всередині Article чув «організації
    немає».
    """
    found: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            raw = node.get("@type")
            if isinstance(raw, str):
                found.add(raw)
            elif isinstance(raw, list):
                found.update(t for t in raw if isinstance(t, str))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for node in page.jsonld:
        walk(node)
    return found


@register
class LlmsTxtCheck(Check):
    """llms.txt — експериментальна можливість, а не передумова.

    Файл корисний, і ми його генеруємо клієнту готовим. Але його
    відсутність не заважає моделям читати сайт: на калібрувальній вибірці
    він відсутній у 69% сайтів, зокрема на всіх найкраще зроблених. Чек,
    що спрацьовує на двох третинах вибірки, майже нічого не розрізняє, а
    вага 3 при severity MEDIUM робила з нього помітний штраф.

    Лишається у звіті як можливість, зі скора майже виходить.

    Людська валідація додала до цього головне: llms.txt — це ПРОПОЗИЦІЯ,
    а не усталений стандарт, і його відсутність не є ані відомою
    проблемою ранжування, ані загальною вимогою видимості в мовних
    моделях. Тому знахідка несе позначку `status: experimental` — щоб
    поверхні звіту могли відрізнити її від звичайного дефекту машинно, а
    не за формулюванням заголовка.
    """

    # Ознака для поверхонь звіту: це можливість, а не вада. Лежить у
    # доказі, бо туди дивляться і JSON-звіт, і Word, і майбутній розділ
    # пройдених перевірок — окреме поле в схемі довелося б заводити
    # тричі й тричі ж синхронізувати.
    STATUS = "experimental"

    code = "ai.llms_txt"
    module = Module.AI_READY
    # INFO і вага 0 — штрафу немає ВЗАГАЛІ, і це рішення продукту, а не
    # наслідок малої ваги. Специфікація v2 (серпень 2026) досі називає
    # себе «a proposal to standardise», а Lighthouse ставить 404 у
    # Not Applicable: файл необовʼязковий. Раніше LOW із вагою 1 давав
    # штраф 1 — тобто ми таки карали за відсутність необовʼязкового.
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW
    messages = ("ai.llms_txt.missing", "ai.llms_txt.no_h1", "ai.llms_txt.thin")
    variants = ("missing", "no_h1", "thin")

    # Статуси, за яких відсутність СПОСТЕРЕЖЕНА, а не припущена.
    _OBSERVED_ABSENT = frozenset({404, 410})

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        info = ctx.llms_txt
        if not info.exists:
            status = info.status_code
            # Немає відповіді, 403/429, 5xx — ми НЕ ЗНАЄМО, чи є файл.
            # Твердження про відсутність вимагає, щоб ми там дивилися;
            # на night3 таких «невідомо» 20 із 969 — і всі вони раніше
            # звалися «немає».
            observed = status in self._OBSERVED_ABSENT or (
                status is not None and 200 <= status < 300
            )
            if not observed:
                return
            # 2xx без придатного вмісту — сайт віддає за цією адресою
            # звичайну сторінку або порожній файл. Для читача це та сама
            # відповідь («файла немає»), але доказ інший, і він названий.
            if status in self._OBSERVED_ABSENT:
                response = "not_found"
            elif not info.content.strip():
                response = "empty_file"
            else:
                response = "fallback_page"
            yield self.issue(
                key="missing",
                msg="ai.llms_txt.missing",
                evidence={
                    "status": self.STATUS,
                    "status_code": status,
                    "response": response,
                },
            )
            return
        if not info.has_h1:
            yield self.issue(
                key="no_h1",
                msg="ai.llms_txt.no_h1",
                evidence={
                    "status": self.STATUS,
                    "found": None,
                    "sections": info.section_count,
                    "links": info.link_count,
                },
            )
        if info.section_count == 0 or info.link_count < 3:
            yield self.issue(
                key="thin",
                msg="ai.llms_txt.thin",
                evidence={
                    "status": self.STATUS,
                    "sections": info.section_count,
                    "links": info.link_count,
                },
            )


@register
class JsonLdPresenceCheck(Check):
    """Розмітки не знайдено — у форматах, які ми справді оцінюємо.

    Google підтримує три формати: JSON-LD, Microdata і RDFa. Ми
    оцінюємо перші два; RDFa у збережених сторінках не зберігається
    (сирого HTML у знімку немає), тож чесне твердження обмежене:
    «JSON-LD і Microdata не знайдено; RDFa не оцінювався». Саме тому
    INFO без штрафу — карати за «відсутність», не подивившись на один
    із трьох підтримуваних форматів, не можна. Штраф повернеться лише
    разом із повним покриттям форматів (збір RDFa — у плані чистого
    бенчмарку).

    Часткове покриття БІЛЬШЕ НЕ ВАДА. Розмітка не мусить стояти на
    кожній сторінці (Google: Organization — на головній або about), і
    посторінкову застосовність ми надійно не визначаємо. Було: 150
    сайтів night3 діставали MEDIUM за «є не всюди».

    Зіпсована спроба розмітки — НЕ відсутність: нею опікується
    `ai.jsonld.invalid`, і подвоювати корінь другим ключем не можна.
    """

    code = "ai.jsonld.missing"
    module = Module.AI_READY
    severity = Severity.INFO
    weight = 0
    effort = Effort.MEDIUM
    messages = ("ai.jsonld.missing",)

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Від сторінки входу чи кошика структурованих даних не чекають;
        # сайт, у якого розмітка є всюди, крім них, розмітку має.
        pages = applicability.pages_for(ctx, self.code)
        if not pages:
            return
        for page in pages:
            if page.jsonld or page.microdata_types:
                # Хоч якась підтримувана розмітка є — проблеми немає.
                return
        if any(page.jsonld_errors for page in pages):
            # Спроба розмітки була, вона зламана: про це каже
            # `ai.jsonld.invalid`, а «відсутності» тут немає.
            return
        yield self.issue(
            msg="ai.jsonld.missing",
            evidence={
                "pages_checked": len(pages),
                "jsonld_found": 0,
                "microdata_found": 0,
                "rdfa_assessed": False,
                "examples": [p.url for p in pages[:5]],
            },
        )


@register
class JsonLdValidityCheck(Check):
    code = "ai.jsonld.invalid"
    module = Module.AI_READY
    severity = Severity.HIGH
    weight = 4
    effort = Effort.LOW
    messages = ("ai.jsonld.invalid", "ai.jsonld.no_type")
    variants = ("invalid", "no_type")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            if page.jsonld_errors:
                yield self.issue(
                    key="invalid",
                    msg="ai.jsonld.invalid",
                    evidence={"errors": page.jsonld_errors[:5]},
                    page_url=page.url,
                )
            for node in page.jsonld:
                if "@type" not in node:
                    yield self.issue(
                        key="no_type",
                        msg="ai.jsonld.no_type",
                        evidence={"keys": list(node.keys())[:10]},
                        severity=Severity.MEDIUM,
                        page_url=page.url,
                    )
                    break


@register
class OrganizationSchemaCheck(Check):
    """Ідентичність у розмітці — інформаційна можливість, не вада.

    Google: Organization необовʼязковий, без обовʼязкових властивостей,
    місце йому на головній АБО на сторінці про організацію, і
    рекомендовано найконкретніший підтип. Тож чек визнає всі нащадки
    Organization з вендорованого знімка schema.org (standards/
    schema_entities.py), Person і WebSite, без регістру, у вкладених
    вузлах, на головній і на about-сторінках вибірки — і мовчить, коли
    розмітки немає взагалі: про це вже сказав кореневий чек, а два
    ключі за один корінь — подвійний штраф (544 сайти night3).

    INFO без штрафу: застосовність «чи потрібен цьому САЙТУ вузол
    ідентичності» надійно не визначається, а карати всіх за
    необовʼязкове — те саме, що з llms.txt.
    """

    code = "ai.schema.organization"
    module = Module.AI_READY
    severity = Severity.INFO
    weight = 0
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        pages = ctx.ok_pages
        has_markup = any(p.jsonld or p.microdata_types for p in pages)
        if not has_markup:
            # Кореневої розмітки немає — це вже сказано (або замовчано
            # свідомо), і дублювати корінь другим ключем не можна.
            return
        home = ctx.home
        if home is None:
            return
        # Друге законне місце для розмітки — сторінка «про нас», і яка саме
        # сторінка нею є, вирішує детектор E-10, а не підрядок в адресі.
        candidates = [home] + [
            p for p in about_page.selected_pages(ctx) if p is not home
        ]
        found: set[str] = set()
        for page in candidates:
            found |= types_on(page)
            found |= set(page.microdata_types)
        if any(is_identity_type(t) for t in found):
            return
        yield self.issue(
            evidence={
                "found_types": sorted(found),
                "checked_pages": [p.url for p in candidates[:5]],
            },
            page_url=home.url,
        )


@register
class SameAsCheck(Check):
    code = "ai.entity.sameas"
    module = Module.AI_READY
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        home = ctx.home
        if home is None or not home.jsonld:
            return
        has_same_as = any(
            node.get("sameAs")
            for node in home.jsonld
            if types_on(home) & KEY_ENTITY_TYPES or "sameAs" in node
        )
        if not has_same_as:
            yield self.issue(
                evidence={
                    "found": None,
                    "types": sorted(types_on(home)),
                    "expected_property": "sameAs",
                },
                page_url=home.url,
            )


@register
class BreadcrumbCheck(Check):
    code = "ai.schema.breadcrumb"
    module = Module.AI_READY
    severity = Severity.LOW
    weight = 1
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Обидва рішення — централізовані (E-15). Чек не повторює ані
        # виявлення звʼязків, ані правила дійсності, ані межі сайту, ані
        # жодного порога: він питає класифікатор і віддає його доказ.
        #
        # Знахідка є рівно тоді, коли ієрархія ДОВЕДЕНА і жодного дійсного
        # `BreadcrumbList` на виміряному придатному обсязі немає. Плаский
        # сайт, сайт без придатних сторінок і сайт, якого ми не дочитали,
        # знахідки не дають — у перших двох випадків претензія незастосовна,
        # у третьому ми просто не знаємо.
        decision = hierarchy.classify(ctx)
        if decision is not None and decision.finding:
            yield self.issue(evidence={
                **decision.as_evidence(),
                "pages_checked": len(decision.eligible),
            })


# ВИЛУЧЕНО ЗІ СКОРИНГУ 13 вересня 2026 (G6: E-07), рішення власника OD-01.
#
# Придатність до FAQ-сніпета — не загальна вимога до сайту. Google не вимагає
# окремої розмітки для своїх AI-функцій, і сторінка, яка просто ставить
# питання («Чи знайде вас пошук?»), не стає через це дефектною. Чек спрацьовував
# на головній Crawldy в усіх шести мовах саме на маркетингових заголовках.
#
# Знято лише `@register`. Клас, його логіка, серйозність, вага, варіанти й
# ключі каталогу лишаються недоторканими: канонічний відкат — це повернути
# декоратор на місце, а не відновлювати видалений код. Ключі повідомлень
# лишаються дійсними через `RETIRED_MESSAGE_KEYS`, тож збережені звіти
# рендеряться далі. Заміни цьому чеку в цій серії не додається.
class FaqSchemaCheck(Check):
    """Питання й відповіді на сторінці є, а розмітки для них немає.

    Раніше чек вимагав FAQPage від усіх підряд і спрацьовував на 85%
    вибірки зі 114 сайтів — від документації Stripe до сторінки
    автосервісу. «У вас немає FAQ» — це не дефект, а спостереження про
    те, чого сайт не зобовʼязаний мати.

    Тепер він мовчить, поки не побачить справжні питання: заголовки,
    що закінчуються знаком питання, або сторінку з faq в адресі. Тоді
    знахідка означає конкретну втрачену можливість — готова відповідь,
    яку модель не може процитувати як відповідь.
    """

    code = "ai.schema.faq"
    module = Module.AI_READY
    severity = Severity.LOW
    weight = 2
    effort = Effort.MEDIUM

    # Одне питання в заголовку — це риторичний прийом, а не FAQ.
    MIN_QUESTIONS = 3
    FAQ_PATHS = ("faq", "questions", "pytannya", "voprosy", "help/answers")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        found = {t for page in ctx.ok_pages for t in types_on(page)}
        if found & {"FAQPage", "HowTo", "QAPage"}:
            return

        for page in ctx.content_pages:
            questions = [text for _, text in page.headings if text.rstrip().endswith("?")]
            path = urlparse(page.url).path.lower()
            looks_like_faq = any(marker in path for marker in self.FAQ_PATHS)
            if len(questions) < self.MIN_QUESTIONS and not (looks_like_faq and questions):
                continue
            yield self.issue(
                params={"count": len(questions)},
                evidence={
                    "questions": questions[:5],
                    "found_types": sorted(types_on(page)),
                    "expected_any_of": ["FAQPage", "QAPage"],
                },
                page_url=page.url,
            )
            return


@register
class ContentSchemaCheck(Check):
    """Довга стаття чи картка товару без розмітки, яка каже, що це таке.

    Тип сторінки береться з `type_of`, а не зі співставлення префіксів
    адреси. Префікси давали рівно ту помилку, від якої застерігає власний
    досвід проєкту: `startswith("/product")` ловив
    `docs.stripe.com/products-prices/manage-prices`, а `"/news"` —
    `fastapi.tiangolo.com/newsletter/`. Плюс під вимогу потрапляли
    сторінки-переліки й пагінація на кшталт
    `ahrefs.com/blog/category/product-blog/page/4/`, де Article був би
    неправдою.

    Мовчання на сторінці, тип якої ми не впізнали, навмисне: вимагати
    Article там, де ми не впевнені, що це стаття, означає просити
    клієнта поставити неправдиву розмітку.
    """

    code = "ai.schema.content_type"
    module = Module.AI_READY
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.MEDIUM

    # Типи, для яких розмітка вмісту доречна й однозначна.
    # Документації тут немає: Article на сторінці API-референсу — це
    # не те, чого від неї хтось чекає.
    EXPECTS_SCHEMA = frozenset({PageType.ARTICLE, PageType.PRODUCT})

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.content_pages:
            if page.depth == 0 or page.word_count < 300:
                continue
            kind = ctx.type_of(page)
            if kind not in self.EXPECTS_SCHEMA:
                continue
            if not (types_on(page) & CONTENT_TYPES):
                yield self.issue(
                    evidence={
                        "word_count": page.word_count,
                        "types": sorted(types_on(page)),
                        "page_type": str(kind),
                    },
                    page_url=page.url,
                )


@register
class OpenGraphCheck(Check):
    code = "ai.opengraph"
    module = Module.AI_READY
    severity = Severity.LOW
    weight = 1
    effort = Effort.LOW
    messages = ("ai.opengraph", "ai.opengraph.no_image")
    variants = ("tags", "image")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        required = {"og:title", "og:description", "og:type", "og:url"}
        for page in ctx.ok_pages:
            missing = sorted(required - set(page.opengraph))
            if missing:
                yield self.issue(
                    key="tags",
                    params={"missing": ", ".join(missing)},
                    evidence={"missing": missing},
                    page_url=page.url,
                )
            # Картинка окремо: без неї посилання виглядає голим навіть
            # тоді, коли базові теги на місці.
            #
            # `og:locale` ми не вимагаємо. На калібрувальній вибірці її
            # немає в 59% сайтів — і в майже всіх верхнього рівня, — тоді
            # як og:title і og:image бракує лише 7%. Різниця не випадкова:
            # локаль справді необовʼязкова, для одномовного сайту вона не
            # додає нічого, а споживачі OG підставляють розумний дефолт.
            # Вимога до неї робила чек таким, що спрацьовує на всіх, тобто
            # не розрізняє нікого.
            if not page.opengraph.get("og:image"):
                yield self.issue(
                    key="image",
                    msg="ai.opengraph.no_image",
                    evidence={"opengraph": sorted(page.opengraph)},
                    page_url=page.url,
                )


@register
class TwitterCardCheck(Check):
    """Картка для соцмереж — корисна дрібниця, не вада сайту.

    На furniturerow.com вона стояла рекомендацією номер один при
    Lighthouse 25. Порядок ми вже виправили, але й у балі їй не місце:
    посилання без картинки в X не заважає ні пошуку, ні моделям.
    """

    code = "ai.twitter_card"
    module = Module.AI_READY
    severity = Severity.INFO
    weight = 1
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            if not page.twitter_card.get("twitter:card"):
                yield self.issue(
                    evidence={"twitter": sorted(page.twitter_card)},
                    page_url=page.url,
                )


@register
class LocalBusinessSchemaCheck(Check):
    code = "ai.schema.contact"
    module = Module.AI_READY
    severity = Severity.MEDIUM
    weight = 3
    effort = Effort.MEDIUM
    messages = ("ai.schema.contact.missing", "ai.schema.contact.incomplete")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Розмітка LocalBusiness потрібна локальному бізнесу, а не будь-кому.
        # На вибірці з 25 сайтів цей чек спрацьовував на 84% — бо вимагав
        # адресу й години роботи від Stripe, MDN і gov.uk, у яких їх немає
        # і не має бути. Ознака локальності — телефон або адреса на сайті.
        if not _looks_local(ctx):
            return

        entities = [node for page in ctx.ok_pages for node in page.jsonld]
        local = [n for n in entities if _types(n) & LOCAL_TYPES]
        contact_points = [
            n for n in entities if "ContactPoint" in _types(n) or n.get("contactPoint")
        ]

        if not local and not contact_points:
            yield self.issue(
                msg="ai.schema.contact.missing",
                evidence={
                    "found_types": sorted({t for n in entities for t in _types(n)}),
                    "expected_any_of": ["LocalBusiness", "ContactPoint"],
                    "phones_on_pages": sorted(
                        {p for page in ctx.ok_pages for p in page.tel_links}
                    )[:3],
                },
            )
            return
        if not local:
            return

        # LocalBusiness без цих полів не дає ані картки в пошуку, ані
        # відповіді на «коли ви працюєте» в AI-сервісах.
        expected = ("address", "telephone", "openingHoursSpecification", "geo", "priceRange")
        missing = sorted({f for f in expected if not any(n.get(f) for n in local)})
        if missing:
            yield self.issue(
                msg="ai.schema.contact.incomplete",
                params={"missing": ", ".join(missing)},
                evidence={
                    "missing": missing,
                    "types": sorted({t for n in local for t in _types(n)}),
                },
                severity=Severity.LOW,
            )


@register
class EntityGraphCheck(Check):
    code = "ai.schema.graph"
    module = Module.AI_READY
    severity = Severity.LOW
    weight = 2
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        home = ctx.home
        if home is None or len(home.jsonld) < 2:
            return
        has_ids = any(node.get("@id") for node in home.jsonld)
        if not has_ids:
            yield self.issue(
                evidence={
                    "blocks": len(home.jsonld),
                    "types": sorted({t for n in home.jsonld for t in _types(n)}),
                },
                page_url=home.url,
            )


def _looks_local(ctx: SiteContext) -> bool:
    """Сайт із фізичною присутністю: є телефон або поштова адреса."""
    if any(page.tel_links for page in ctx.ok_pages):
        return True
    return any(
        node.get("address") or node.get("telephone")
        for page in ctx.ok_pages
        for node in page.jsonld
    )


def _types(node: dict[str, Any]) -> set[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        return {raw}
    if isinstance(raw, list):
        return {t for t in raw if isinstance(t, str)}
    return set()


@register
class LangCheck(Check):
    code = "ai.lang"
    module = Module.AI_READY
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.ok_pages:
            if not page.lang:
                yield self.issue(
                    evidence={"found": None, "expected_attribute": "<html lang>"},
                    page_url=page.url,
                )
