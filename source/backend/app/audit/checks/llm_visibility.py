"""Чеки видимості для мовних моделей: чи легко LLM зрозуміти й процитувати сторінку."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, ClassVar
from urllib.parse import urlparse

from app.audit import about_page, applicability, render_diff
from app.audit import robots as robots_rfc
from app.audit.checks.base import Check, register
from app.audit.page_kinds import EXPECTS_AUTHORSHIP, path_words
from app.audit.standards import AI_CRAWLERS, AiCrawler, CrawlerPurpose
from app.audit.types import (
    Confidence,
    Effort,
    Issue,
    Module,
    PageSignals,
    Severity,
    SiteContext,
)

CONTACT_PATTERNS = ("contact", "kontakt", "kontakty", "contacts", "support")


def _has_page_like(ctx: SiteContext, patterns: tuple[str, ...]) -> bool:
    for page in ctx.ok_pages:
        path = urlparse(page.url).path.lower()
        haystack = f"{path} {(page.title or '').lower()}"
        if any(p in haystack for p in patterns):
            return True
    for page in ctx.ok_pages:
        for link in page.links:
            target = f"{urlparse(link.url).path.lower()} {link.anchor.lower()}"
            if any(p in target for p in patterns):
                return True
    return False


@register
class StructuredContentCheck(Check):
    code = "llm.structure"
    module = Module.LLM_VISIBILITY
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.HIGH

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.content_pages:
            if page.word_count < 300:
                continue
            subheadings = sum(1 for level, _ in page.headings if level >= 2)
            if subheadings < 2:
                yield self.issue(
                    params={"word_count": page.word_count},
                    evidence={"word_count": page.word_count, "subheadings": subheadings},
                    page_url=page.url,
                )


@register
class AboutPageCheck(Check):
    code = "llm.about_page"
    module = Module.LLM_VISIBILITY
    severity = Severity.MEDIUM
    weight = 3
    effort = Effort.HIGH

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Рішення — в одного детектора (E-10). Знахідка є лише тоді, коли
        # кандидата немає при повному покритті; кандидат, якого не прочитали,
        # дає не знахідку, а прогалину даних — її записує оркестратор.
        about = about_page.detect(ctx)
        if about is not None and about.finding:
            yield self.issue(
                evidence={
                    **about.as_evidence(),
                    "crawled": [p.url for p in ctx.ok_pages][:10],
                }
            )


@register
class ContactPageCheck(Check):
    code = "llm.contact_page"
    module = Module.LLM_VISIBILITY
    severity = Severity.MEDIUM
    weight = 2
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Контакти в тілі сторінки — теж контакти.
        #
        # Чек шукав адресу виду /contact і на цьому зупинявся, тож
        # односторінкова пекарня на Wix і історичне товариство, у якого
        # телефон стоїть на всіх девʼяти сторінках, отримували «немає
        # сторінки Contact». Це не просто хибне спрацювання, а перекіс
        # проти класу: малий сайт кладе контакти на єдину сторінку
        # замість окремої адреси, і карати його за це нема за що.
        if any(page.body_contacts for page in ctx.ok_pages):
            return
        if not _has_page_like(ctx, CONTACT_PATTERNS):
            yield self.issue(
                evidence={
                    "expected_url_like": list(CONTACT_PATTERNS),
                    "crawled": [p.url for p in ctx.ok_pages][:10],
                }
            )


@register
class BrandConsistencyCheck(Check):
    code = "llm.brand_consistency"
    module = Module.LLM_VISIBILITY
    severity = Severity.LOW
    weight = 2
    effort = Effort.LOW

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        home = ctx.home
        if home is None or not home.title:
            return
        # Імена з розмітки — з головної й, коли сторінку «про нас» справді
        # прочитано, з неї: обидва законні місця для вузла ідентичності
        # (E-10: споживачі ділять одне рішення). Без вердикту — лише головна.
        sources = [home, *about_page.selected_pages(ctx)]
        schema_names = {
            str(node.get("name", "")).lower()
            for page in sources for node in page.jsonld if node.get("name")
        }
        if not schema_names:
            return
        title_lower = home.title.lower()
        if not any(name and name in title_lower for name in schema_names):
            yield self.issue(
                evidence={"title": home.title, "schema_names": sorted(schema_names)[:5]},
                page_url=home.url,
            )


@register
class AuthorshipCheck(Check):
    code = "llm.authorship"
    module = Module.LLM_VISIBILITY
    severity = Severity.LOW
    weight = 2
    effort = Effort.MEDIUM

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        for page in ctx.content_pages:
            # Авторство очікується від статті, а не від будь-якої довгої
            # сторінки: у комерційної послуги, опису продукту чи кейс-стаді
            # автора немає й не має бути. Тип сторінки тут головніший за
            # довжину: /projects/sis-srem — проєкт, а не публікація.
            if page.word_count < 400 or ctx.type_of(page) not in EXPECTS_AUTHORSHIP:
                continue
            has_author = any(node.get("author") for node in page.jsonld)
            has_date = any(
                node.get("datePublished") or node.get("dateModified") for node in page.jsonld
            )
            if not (has_author and has_date):
                yield self.issue(
                    evidence={"has_author": has_author, "has_date": has_date},
                    page_url=page.url,
                )


ARTICLE_TYPES = {"Article", "BlogPosting", "NewsArticle", "TechArticle", "Report"}
ARTICLE_PATHS = ("/blog", "/news", "/article", "/post", "/insights", "/stories", "/press")


def _looks_like_article(page: PageSignals) -> bool:
    """Стаття — це розмітка Article або окремий матеріал усередині розділу.

    Сам /blog — це перелік, а не стаття: вимагати від нього автора й дати
    публікації безглуздо.
    """
    types = {
        t
        for node in page.jsonld
        for t in ([node["@type"]] if isinstance(node.get("@type"), str) else node.get("@type", []))
        if isinstance(t, str)
    }
    if types & ARTICLE_TYPES:
        return True
    return _is_inside_section(page.url, ARTICLE_PATHS)


def _is_inside_section(url: str, markers: tuple[str, ...]) -> bool:
    path = urlparse(url).path.lower().rstrip("/")
    return any(path.startswith(m) and len(path) > len(m) for m in markers)


@dataclass(frozen=True, slots=True)
class _Access:
    """Що robots.txt каже одному краулеру про сторінки, які ми читали."""

    crawler: AiCrawler
    denied: list[str]
    checked: list[str]
    reason: str
    group: str | None

    @property
    def blocked(self) -> bool:
        return bool(self.denied)

    @property
    def everywhere(self) -> bool:
        return bool(self.denied) and len(self.denied) == len(self.checked)


def _paths_under_audit(ctx: SiteContext) -> list[str]:
    """Шляхи, про які ми маємо право робити висновок.

    Корінь плюс те, що справді читали. Судити про сторінки, яких ми не
    відкривали, означало б описувати свою вибірку замість сайту — та
    сама помилка, яку проєкт уже ловив у сиротах і темах.
    """
    seen: dict[str, None] = {"/": None}
    for page in ctx.ok_pages:
        path = urlparse(page.url).path or "/"
        seen.setdefault(path, None)
    return list(seen)


def _ignored_directives(parsed: Any) -> list[dict[str, str]]:
    """Заборони, які власник написав, а вендор виконувати не обіцяє.

    Це не знахідка: доказу блокування тут немає. Але змовчати теж
    неправильно — власник міг вважати, що закрив доступ, а документація
    вендора каже інше.
    """
    out = []
    for crawler in AI_CRAWLERS:
        if crawler.obeys_robots:
            continue
        decision = parsed.evaluate(crawler.token, "/")
        if not decision.allowed:
            out.append({
                "vendor": crawler.vendor,
                "token": crawler.token,
                "rule": decision.reason,
                "source": crawler.source_url,
            })
    return out


def _assess(ctx: SiteContext) -> list[_Access]:
    """Доступ кожного відомого краулера до цих шляхів, за RFC 9309."""
    parsed = getattr(ctx.robots, "parsed", None)
    if parsed is None:
        parsed = robots_rfc.parse(ctx.robots.content or "")
    paths = _paths_under_audit(ctx)

    out: list[_Access] = []
    for crawler in AI_CRAWLERS:
        if not crawler.obeys_robots:
            # Заборона є, але вендор пише, що агент її не виконує. Назвати
            # це блокуванням означало б спростувати власне джерело.
            continue
        denied, reason, group = [], "", None
        for path in paths:
            decision = parsed.evaluate(crawler.token, path)
            group = decision.matched_group
            if not decision.allowed:
                denied.append(path)
                reason = reason or decision.reason
        if denied:
            out.append(_Access(crawler, denied, paths, reason, group))
    return out


@register
class AiCrawlerAccessCheck(Check):
    """Кого з AI-краулерів сайт не пускає — і чи це взагалі проблема.

    ## Призначення вирішує все

    Заблокувати навчальний краулер — законна позиція власника щодо своїх
    текстів. Заблокувати пошуковий — майже завжди недогляд, який коштує
    видимості. Раніше обидва випадки давали однакову знахідку «N AI
    crawlers are blocked», і власник, який свідомо закрив GPTBot, читав
    про це як про дефект.

    Тепер формулювання обирає найважливіше з того, що справді
    заблоковано: пошук → користувацький доступ → навчання. Повний
    розклад по кожному краулеру лишається в доказі.

    ## Що тут НЕ стверджується

    Доступ краулера — не присутність у відповідях. Ми бачимо директиву в
    robots.txt і кажемо, що вона робить із доступом; чи згадає модель
    сайт, ми не міряємо й не обіцяємо. Це межа продукту, а не обережність
    формулювання.

    ## Одна знахідка, а не три

    Розділити на варіанти було б правильніше за структурою, але кожен
    варіант отримує власну стелю штрафу — тобто це зміна скорингу, а він
    заморожений. Тому поки одна знахідка з повним доказом; поділ чекає
    на фазу калібрування.
    """

    code = "llm.crawler_blocked"
    module = Module.LLM_VISIBILITY
    severity = Severity.HIGH
    weight = 4
    effort = Effort.LOW
    messages = (
        "llm.crawler_blocked.search",
        "llm.crawler_blocked.grounding",
        "llm.crawler_blocked.user",
        "llm.crawler_blocked.training",
    )

    # Що важливіше сказати першим, якщо заблоковано кілька призначень.
    # Grounding одразу за пошуком: без нього асистент не бере вміст сайту
    # у відповідь, і це втрата видимості, а не питання навчання.
    ORDER = (
        (CrawlerPurpose.SEARCH, "search"),
        (CrawlerPurpose.GROUNDING, "grounding"),
        (CrawlerPurpose.USER_INITIATED, "user"),
        (CrawlerPurpose.TRAINING, "training"),
    )

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        blocked = _assess(ctx)
        if not blocked:
            return

        # Краулер із кількома призначеннями потрапляє в кожне своє: одне
        # місце в переліку приховало б половину сенсу Google-Extended.
        by_purpose = {purpose: [a for a in blocked if a.crawler.serves(purpose)]
                      for purpose, _ in self.ORDER}
        leading = next(
            ((purpose, name) for purpose, name in self.ORDER if by_purpose[purpose]),
            None,
        )
        if leading is None:  # pragma: no cover — призначень рівно три
            return
        purpose, name = leading
        affected = by_purpose[purpose]

        yield self.issue(
            msg=f"llm.crawler_blocked.{name}",
            params={
                "count": len(affected),
                "crawlers": ", ".join(a.crawler.token for a in affected),
            },
            evidence={
                "purpose": purpose.value,
                "paths_checked": len(_paths_under_audit(ctx)),
                # Директиви, які вендор виконувати не обіцяє. Окремо від
                # `blocked`, бо блокуванням вони не є.
                "directives_ignored_by_vendor": _ignored_directives(
                    getattr(ctx.robots, "parsed", None)
                    or robots_rfc.parse(ctx.robots.content or "")
                ),
                # Повний розклад: вендор, токен, призначення, обсяг
                # заборони, правило, що її спричинило, і джерело, з якого
                # ми взагалі знаємо про цього краулера.
                "blocked": [
                    {
                        "vendor": a.crawler.vendor,
                        "token": a.crawler.token,
                        "purposes": [p.value for p in a.crawler.purposes],
                        "scope": "site" if a.everywhere else "paths",
                        "denied_paths": a.denied[:5],
                        "denied_count": len(a.denied),
                        "matched_group": a.group,
                        "rule": a.reason,
                        "source": a.crawler.source_url,
                    }
                    for a in blocked
                ],
                "by_purpose": {
                    p.value: [a.crawler.token for a in group]
                    for p, group in by_purpose.items()
                    if group
                },
            },
        )


@register
class ClientRenderedCheck(Check):
    code = "llm.client_rendered"
    module = Module.LLM_VISIBILITY
    severity = Severity.CRITICAL
    weight = 5
    effort = Effort.HIGH

    # Контактні й службові сторінки навмисно ховають вміст від парсерів —
    # це стандартна практика захисту контактів, а не дефект. Цитувати їх
    # мовні моделі й не мають: вони не джерело фактів, а точка звернення.
    EXPECTED_TO_HIDE = (*CONTACT_PATTERNS, "privacy", "terms", "legal", "cookie")

    # Частка тексту, видима без JS, нижче за яку сторінка вважається
    # недоступною тому, хто JS не виконує. Не нуль: майже кожен сайт має
    # у статичному HTML шапку, футер і меню, і вимагати рівно нуля
    # означало б не спрацьовувати ніколи.
    VISIBLE_ENOUGH = 0.3
    # Нижче цього рендер не показав нічого вартого уваги, і різниця
    # ділиться на надто малі числа, щоб щось означати.
    MEANINGFUL_WORDS = 100

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        measured = self._measured(ctx)
        if measured is not None:
            yield from measured
            return

        shells = [p for p in ctx.ok_pages if p.is_content_shell and not self._may_hide(p)]
        if not shells:
            return

        # Порожній HTML на всьому сайті й на одній сторінці з двадцяти —
        # різні за наслідками проблеми, тож і severity різна.
        share = len(shells) / max(len(ctx.ok_pages), 1)
        if share >= 0.5:
            severity = Severity.CRITICAL
        elif share >= 0.2:
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM

        for page in shells:
            text_ratio = len(page.text) / page.html_bytes
            yield self.issue(
                evidence={
                    "word_count": page.word_count,
                    "html_bytes": page.html_bytes,
                    "text_ratio": round(text_ratio, 4),
                    "affected_share": round(share, 2),
                },
                severity=severity,
                page_url=page.url,
            )


    @classmethod
    def _may_hide(cls, page: PageSignals) -> bool:
        haystack = f"{urlparse(page.url).path.lower()} {(page.title or '').lower()}"
        return any(marker in haystack for marker in cls.EXPECTED_TO_HIDE)

    def _measured(self, ctx: SiteContext) -> list[Issue] | None:
        """Знахідки за прямим вимірюванням, або None — якщо міряти не було чим.

        Евристика `is_content_shell` вгадує за відношенням тексту до
        розміру HTML і на калібруванні давала хибні спрацювання: важкий
        інлайновий CSS робив «оболонкою» звичайну сторінку. Коли є
        відрендерена версія, гадати не треба — видно точно, скільки
        тексту втрачає той, хто JS не виконує.

        None замість порожнього списку тут принципове: «не міряли» — не
        те саме, що «виміряли й усе гаразд».
        """
        pages = [p for p in ctx.ok_pages if p.url in ctx.renders and not self._may_hide(p)]
        if not pages:
            return None

        hidden = []
        for page in pages:
            after = ctx.rendered(page.url)
            visible = ctx.visible_without_js(page)
            if after is None or visible is None or after.word_count < self.MEANINGFUL_WORDS:
                continue
            if visible < self.VISIBLE_ENOUGH:
                hidden.append((page, after, visible))

        if not hidden:
            return []

        share = len(hidden) / len(pages)
        if share >= 0.5:
            severity = Severity.CRITICAL
        elif share >= 0.2:
            severity = Severity.HIGH
        else:
            severity = Severity.MEDIUM
        return [
            self.issue(
                evidence={
                    "words_without_js": page.word_count,
                    "words_after_render": after.word_count,
                    "visible_without_js": f"{visible:.0%}",
                    "measured": True,
                    # Те саме порівняння, що й у `seo.render_delta`: обсяг
                    # тексту каже, чи видно сторінку без JS, а поля —
                    # які саме сигнали при цьому розходяться. Два
                    # незалежні порівняння тут розійшлися б у показаннях.
                    "render_delta": render_diff.compare(
                        page, ctx.renders.get(page.url)
                    ).as_evidence(),
                    "affected_share": round(share, 2),
                },
                severity=severity,
                page_url=page.url,
            )
            for page, after, visible in hidden
        ]


@register
class UnstatedFactsCheck(Check):
    """Факт, якого немає ніде на сайті.

    Питання навмисно на рівні сайту, а не сторінки. Головна Stripe теж не
    називає цін — і це нормально, бо вони на /pricing. Проблема там, де
    факту немає ніде: модель, яку спитають про компанію, не має звідки
    його взяти й або промовчить, або вигадає.

    Два з чотирьох фактів потрібні не всім, і рішення про це приймається
    тут, а не моделлю: вона лише спостерігає тип бізнесу, а порогом
    розпоряджається код — так його видно й можна протестувати. Без цих
    гейтів чек карав би Stripe за відсутність вулиці, а python.org — за
    відсутність прайса; на живій вибірці саме так і виходило.
    """

    code = "llm.unstated_facts"
    module = Module.LLM_VISIBILITY
    severity = Severity.HIGH
    weight = 3
    effort = Effort.MEDIUM
    # Судження моделі про те, чого на сайті немає. Воно спирається на
    # прочитану вибірку й на розуміння тексту — тут можна помилитися,
    # на відміну від відсутнього заголовка відповіді.
    confidence = Confidence.MEDIUM
    messages = (
        "llm.unstated_facts.offering",
        "llm.unstated_facts.location",
        "llm.unstated_facts.pricing",
    )
    variants = ("offering", "location", "pricing")

    # Адреса важить для того, хто працює в межах міста чи країни. Для
    # глобального SaaS вона нічого не додає покупцеві.
    AREA_ONLY = ("location",)
    # Ціна важить там, де є що порівнювати. Безкоштовний проєкт і
    # enterprise-угода під кожного клієнта — не той випадок.
    PRICED_ONLY = ("pricing",)

    # Де факт лежить за звичаєм. Про головну не питаємо: чим компанія
    # займається, пишуть на ній, і вона прочитана завжди.
    LIVES_ON: ClassVar[dict[str, tuple[str, ...]]] = {
        "location": ("contact", "kontakt", "контакти", "about", "про-нас", "company"),
        "pricing": ("pricing", "price", "prices", "ціни", "tariffs", "тарифи",
                    "services", "послуги", "products", "shop", "catalog", "каталог"),
    }

    # Факти, які ми вміємо перевірити самі. Модель тут не арбітр: якщо
    # адреса лежить у розмітці або місто написане в мета-описі, її
    # висновок «ніде не вказано» просто хибний.
    #
    # Саме так звіт по smartkp.com.ua одночасно стверджував «ніде не
    # вказано, де ви працюєте» і містив у згенерованому нами ж llms.txt
    # рядок про Камʼянець-Подільський.
    KNOWN_DETERMINISTICALLY: ClassVar[dict[str, str]] = {
        "location": "has_location",
        "contact": "has_contact",
    }

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        facts = ctx.facts
        if facts is None or not facts.analysed:
            return

        for fact in facts.missing():
            attribute = self.KNOWN_DETERMINISTICALLY.get(fact.key)
            if attribute and getattr(ctx.known, attribute, False):
                continue
            if fact.key in self.AREA_ONLY and not facts.serves_an_area:
                continue
            if fact.key in self.PRICED_ONLY and not facts.sells_listed_items:
                continue
            where = self.LIVES_ON.get(fact.key)
            looked = self._looked_where_it_lives(ctx, facts, where)
            if looked is False:
                continue
            yield self.issue(
                key=fact.key,
                msg=f"{self.code}.{fact.key}",
                evidence={
                    "fact": fact.key,
                    # Твердження «цього немає» перевіряється лише разом зі
                    # списком прочитаного: інакше воно про нашу вибірку, а
                    # не про сайт.
                    "pages_read": facts.read_pages,
                    "serves_an_area": facts.serves_an_area,
                    "sells_listed_items": facts.sells_listed_items,
                    "conventional_page": "прочитано" if looked else "немає на сайті",
                },
            )

    def _looked_where_it_lives(
        self, ctx: SiteContext, facts: object, words: tuple[str, ...] | None
    ) -> bool | None:
        """True — сторінку з фактом прочитано, None — такої сторінки немає,
        False — вона на сайті є, але в бюджет читання не потрапила.

        Останній випадок і є причина цього методу. На stripe.com краул
        приносив самі юридичні сторінки, /pricing лишалась за бортом — і
        чек звинувачував сайт у тому, чого ми не дивилися. Знахідка без
        доказу гірша за пропущену: клієнт відкриє свій прайс і більше не
        повірить жодному рядку звіту.
        """
        if words is None:
            return True
        read: list[str] = list(getattr(facts, "read_pages", []))
        if any(path_words(url) & set(words) for url in read):
            return True
        if _has_page_like(ctx, words):
            return False
        return None



# Скільки датованих сторінок треба побачити, щоб «найсвіжіше — старе»
# було твердженням про сайт, а не про нашу вибірку.
MIN_DATED_PAGES = 3

# Яка частка прочитаних сторінок має нести дату, щоб говорити про САЙТ,
# а не лише про знайдені дати. Поріг вирішує, ЩО МИ КАЖЕМО, а не скільки
# це коштує: на nomadgames.co.uk датованими були 3 сторінки з 24, і з
# них виводилось «сайт виглядає занедбаним». Відсутність дати на
# двадцяти одній сторінці не є доказом, що вони старі.
DATED_COVERAGE_FOR_SITE_CLAIM = 0.5

# Через скільки років без жодного оновлення сайт читається як покинутий.
STALE_AFTER_YEARS = 2


@register
class StaleContentCheck(Check):
    """Найсвіжіше, що ми знайшли на сайті, — багаторічної давнини.

    Питання не до окремої сторінки: посібник, написаний у 2019-му, може
    бути актуальним і сьогодні. Питання до сайту загалом. Коли жодна з
    прочитаних датованих сторінок не оновлювалась роками, і читач, і
    пошук, і асистент роблять той самий висновок — компанією більше не
    займаються.

    Судимо лише за датами, які сайт проставив сам у розмітці. Дату з
    видимого тексту не вгадуємо: «з 2019 року на ринку» — це не дата
    оновлення сторінки.
    """

    code = "llm.stale_content"
    module = Module.LLM_VISIBILITY
    severity = Severity.LOW
    weight = 2
    effort = Effort.MEDIUM
    confidence = Confidence.MEDIUM
    # Два формулювання однієї знахідки, а не два `variants`: проблема та
    # сама, різна лише міра, з якою ми маємо право узагальнювати. Через
    # це `issue_key` не змінюється й бали лишаються порівнянними.
    messages = ("llm.stale_content", "llm.stale_content.sparse")

    def run(self, ctx: SiteContext) -> Iterable[Issue]:
        # Вік вмісту питають у вмісту. Службовий маршрут із датою в
        # підвалі не робить сайт застарілим, а прочитаних сторінок для
        # частки береться стільки ж, скільки судилося.
        relevant = {p.url for p in applicability.pages_for(ctx, self.code)}
        dated = [pair for pair in _dated_pages(ctx) if pair[0] in relevant]
        if len(dated) < MIN_DATED_PAGES:
            return
        newest_url, newest = max(dated, key=lambda pair: pair[1])
        years = (datetime.now(UTC) - newest).days / 365.25
        if years < STALE_AFTER_YEARS:
            return
        read = len(relevant)
        coverage = len(dated) / read if read else 0.0
        # Дат мало — кажемо рівно те, що бачили: найновіший ДАТОВАНИЙ
        # вміст. Твердження про сайт лишається для випадку, коли дати
        # проставлені на більшості прочитаних сторінок.
        sparse = coverage < DATED_COVERAGE_FOR_SITE_CLAIM
        yield self.issue(
            msg="llm.stale_content.sparse" if sparse else "llm.stale_content",
            params={"years": int(years), "dated": len(dated), "read": read},
            evidence={
                "newest_date": newest.date().isoformat(),
                "newest_page": newest_url,
                "dated_pages": len(dated),
                "pages_read": read,
                "dated_coverage": round(coverage, 3),
                "claim_scope": "dated_pages_only" if sparse else "site",
            },
            confidence=Confidence.LOW if sparse else Confidence.MEDIUM,
        )


def _dated_pages(ctx: SiteContext) -> list[tuple[str, datetime]]:
    """Сторінки з датою в розмітці та найпізніша дата кожної."""
    found: list[tuple[str, datetime]] = []
    for page in ctx.ok_pages:
        dates = [
            parsed
            for node in page.jsonld
            for key in ("dateModified", "datePublished")
            if isinstance(node.get(key), str)
            and (parsed := _parse_date(str(node[key]))) is not None
        ]
        if dates:
            found.append((page.url, max(dates)))
    return found


def _parse_date(raw: str) -> datetime | None:
    """ISO-дата з розмітки. Формат буває з часовою зоною й без неї."""
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
