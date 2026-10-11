"""Внутрішні типи пайплайну аудиту (не залежать від ORM і від FastAPI)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.audit.enums import Confidence, DegradationKind, Effort, Module, Severity


class Strategy(StrEnum):
    MOBILE = "mobile"
    DESKTOP = "desktop"


# Префікс у текстовому представленні деградації — історичний формат,
# який лишається в audits.error і в CLI.
_SCOPE_PREFIX: dict[DegradationKind, str] = {DegradationKind.CHECK_FAILED: "check "}


# Scope деградацій, повʼязаних із читанням сайту. Це константи, а не рядки
# на місці, бо на них зав'язані рішення в трьох різних шарах: яке
# пояснення показати власнику, які твердження лишити в звіті й чи вважати
# аудит виконаним. Різниця між ними змістовна:
#
#   CRAWL_BLIND    — ми не отримали нічого. Про вміст сайту невідомо все.
#   CRAWL_FAILURES — прочитали меншість адрес. Про прочитані знаємо.
#   CRAWL_EMPTY    — сторінки отримали, тексту в них немає навіть після
#                    виконання скриптів. Не бачить ніхто.
#   CRAWL_EMPTY_STATIC — текст є, але лише після виконання скриптів.
#                    Пошук бачить, асистенти здебільшого ні. Виключає
#                    лише модулі, які судять статичну відповідь.
#   CRAWL_SHALLOW  — прочитали лише головну, хоча з неї вели посилання.
#   ENTRY_ERROR    — вхідна адреса відповіла помилкою, міряли не те, що просили.
#
# `CRAWL_BLIND` і `CRAWL_SHALLOW` довго ділили рядок «crawl», хоча
# означають протилежне: «жодної сторінки» проти «рівно одна сторінка».
# Це та сама помилка, що й дві різні проблеми під одним кодом чека, — і
# вона стає небезпечною, щойно на scope починає спиратися рішення.
CRAWL_BLIND = "crawl"
CRAWL_FAILURES = "crawl.failures"
# Стани покриття нового зразка. Старі CRAWL_* лишаються читабельними для
# збережених аудитів; нові аудити віддають стан плюс названі причини.
COVERAGE_WITHHELD = "coverage.withheld"
COVERAGE_LIMITED = "coverage.limited"
CRAWL_EMPTY = "crawl.empty"
CRAWL_EMPTY_STATIC = "crawl.empty_static"
CRAWL_SHALLOW = "crawl.shallow"
ENTRY_ERROR = "entry"


@dataclass(slots=True)
class Degradation:
    """Частина аудиту, яка не виконалася. Джерело для missing_data у звіті.

    Інваріант 5: якщо даних немає — ми це показуємо, а не домальовуємо.
    """

    scope: str  # "sitemap" | "seo.title" | "performance"
    kind: DegradationKind
    reason: str
    affected_modules: list[Module] = field(default_factory=list)
    # Той самий текст ключем каталогу. Поле `reason` лишається: у ньому
    # технічний слід (текст винятку, адреса, статус), і воно є в усіх
    # збережених аудитах — викинути його означало б зробити їх нечитаними.
    #
    # Причина поділу та сама, що й у знахідок: `reason` народжується в
    # двигуні одним рядком однією мовою й потрапляє прямо в звіт. Поки
    # так було, деградації лишались єдиним місцем, де двигун писав текст
    # для клієнта — при тому, що жоден чек цього не робить.
    #
    # **Після** `affected_modules`, а не перед: деградації конструюють
    # позиційно, і нове поле в середині мовчки перехопило б четвертий
    # аргумент. Саме так це й сталося при першій спробі.
    reason_key: str = ""
    reason_params: dict[str, Any] = field(default_factory=dict)

    @property
    def is_failure(self) -> bool:
        """Вимкнене користувачем — не збій.

        Аудит, який виконав рівно те, що просили, має бути completed,
        а не partial: інакше статус нічого не означає. Неповні дані —
        теж не збій сам по собі, вони описуються окремо в missing_data.

        `LAYER_DISABLED` тут із тієї ж причини, що й `MODULE_EXCLUDED`, і
        додано пізніше через ту саму помилку в іншому місці: вимкнений
        семантичний шар писався як «провайдер недоступний», тож кожен
        аудит у штатній конфігурації ставав partial.
        """
        return self.kind not in {
            DegradationKind.MODULE_EXCLUDED,
            DegradationKind.LAYER_DISABLED,
            DegradationKind.PARTIAL_DATA,
        }

    def __str__(self) -> str:
        return f"{_SCOPE_PREFIX.get(self.kind, '')}{self.scope}: {self.reason}"

    def to_json(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "kind": self.kind.value,
            "reason": self.reason,
            "affected_modules": [m.value for m in self.affected_modules],
        }

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Degradation:
        return cls(
            scope=str(data.get("scope", "")),
            kind=DegradationKind(data.get("kind", DegradationKind.CHECK_FAILED)),
            reason=str(data.get("reason", "")),
            affected_modules=[Module(m) for m in data.get("affected_modules", [])],
        )


@dataclass(slots=True)
class Issue:
    code: str
    module: Module
    severity: Severity
    title: str
    description: str = ""
    recommendation: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    weight: int = 1
    page_url: str | None = None
    # Наскільки твердо ми це стверджуємо. За замовчуванням висока: більшість
    # чеків читають розмітку й заголовки, де помилитися ніде.
    confidence: Confidence = Confidence.HIGH

    # Ключ у каталозі i18n і його параметри. title/description/recommendation
    # вище — це вже відрендерена дефолтна локаль; msg дозволяє шару звіту
    # перерендерити те саме іншою мовою, зокрема для давно збереженого аудиту.
    #
    # `msg` — presentation layer. Він може змінитися через переформулювання
    # тексту, тому ідентифікатором проблеми не є й бути не може.
    msg: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    # Яку саме проблему з тих, що розрізняє чек, описує ця знахідка.
    # Порожньо — чек знає лише одну проблему, і нею є він сам.
    key: str = ""

    @property
    def issue_key(self) -> str:
        """Стабільний ідентифікатор конкретної проблеми.

        Три різні речі, які довго були двома:

        * `code` — категорія детектора. `perf.core_web_vitals` означає
          «чек, що читає Core Web Vitals», і лишається стабільною, поки
          існує сам чек.
        * `issue_key` — конкретна проблема: `perf.core_web_vitals:lcp`.
          На ній тримається стеля повторень і групування рекомендацій.
        * `msg` — рядок каталогу, тобто те, як проблему видно клієнту.

        Поки стеля рахувалася за `code`, LCP і INP ділили один ліміт, і
        друга провалена метрика коштувала нуль: сайт із однією критичною
        метрикою й сайт із трьома отримували однакові 60 балів модуля.
        Стеля існує, щоб приборкати **повторення однієї** проблеми, а не
        щоб зробити другу безкоштовною.
        """
        return f"{self.code}:{self.key}" if self.key else self.code


@dataclass(slots=True)
class LinkRef:
    url: str
    anchor: str
    rel: str
    is_internal: bool
    # Посилання зі спільної обв'язки сайту — `<nav>` або `<footer>`. Воно
    # є на кожній сторінці й тому нічого не каже про цю. Без цієї межі
    # «на сторінці є посилання на контакти» правда завжди, а отже
    # марна: меню з контактами має будь-який сайт.
    in_chrome: bool = False
    # `alt` картинки всередині посилання. Google каже прямо: якщо
    # посилання — це зображення, його `alt` і є текстом посилання.
    # Окремим полем, а не в `anchor`: на `anchor` тримаються пріоритет
    # краулу й два ваговиті чеки, і зрушити його означало б зрушити
    # бали сайтів, знятих раніше.
    image_alt: str = ""
    # `aria-label` або `title` самого посилання: доступна назва там,
    # де видимого тексту немає — іконка, стрілка, кнопка-svg.
    label: str = ""


@dataclass(slots=True)
class InsecureRef:
    """Підресурс, який сторінка просить по `http://`.

    Зберігається адреса, а не лише хост: у `third_party_hosts` схема
    втрачалась, і питання «чи є на сайті змішаний вміст» не мало
    відповіді з розмітки взагалі.

    `kind` — тег, у якому це знайдено (`script`, `link`, `iframe`,
    `img`, `source`, `video`, `audio`, `embed`, `object`, `download`).
    Клас поведінки браузера з нього виводить `mixed_content`, а не
    екстрактор: розбір не має знати про стандарти.
    """

    url: str
    kind: str
    # Знайдено в `srcset`, а не в `src`. Потрібне окремо: набір
    # кандидатів поводиться інакше за одну адресу.
    in_srcset: bool = False


@dataclass(slots=True)
class HreflangRef:
    """Одна заявлена мовна версія сторінки.

    Google приймає три рівноцінні способи це оголосити — HTML, заголовок
    HTTP і карту сайту, — і прямо каже, що вони «equivalent from Google's
    perspective». Тому джерело зберігається полем, а не окремим типом:
    правила однакові, а от порада клієнту «шукайте не там» без джерела
    неможлива.
    """

    value: str
    href: str
    # html | http_header | sitemap
    source: str = "html"


@dataclass(slots=True)
class FormSignals:
    """Форма й ознаки її захисту. Саму відправку ми не пробуємо.

    `protections` і `honeypots` несуть **що саме побачено**, а не лише
    факт «щось є»: звіт мусить назвати провайдера, інакше клієнт не
    може ані перевірити висновок, ані зрозуміти, про що він.

    `scanned` розводить «дивилися й не знайшли» від «не дивилися». Без
    нього знімок, зроблений до появи цих полів, свідчив би про
    відсутність захисту — тобто описував би нашу прогалину як стан
    сайту. Той самий клас, що й `hreflang_observed`.
    """

    method: str = "get"
    # Чи автор написав `method` сам. Браузер поводиться однаково — форма
    # без атрибута робить GET, — але доказ мусить розрізняти написане й
    # взяте за замовчуванням. `None` — знімок, знятий до появи поля: він
    # не бачив нічого й свідчити не має.
    method_declared: bool | None = None
    action: str = ""
    field_count: int = 0
    has_captcha: bool = False
    has_honeypot: bool = False
    has_email_field: bool = False
    # Чи є у формі поле пароля. Сам по собі цей факт нічого не вирішує:
    # він потрібен E-10, щоб відрізнити стіну входу від сторінки «про
    # нас», і лише разом із відсутністю наміру в заголовку чи H1.
    has_password_field: bool = False
    # Безпечний селектор форми для доказу: `form#id`, `form[name=…]`
    # або порядковий номер на сторінці. Значень полів тут немає ніколи.
    identity: str = ""
    # Слаги провайдерів, чиї маркери видно в атрибутах САМОЇ форми.
    protections: tuple[str, ...] = ()
    # Назви полів-приманок, які видно й приховані від людини.
    honeypots: tuple[str, ...] = ()
    # Пари «провайдер:маркер» — рівно те, що збіглося, для доказу.
    protection_markers: tuple[str, ...] = ()
    scanned: bool = False


@dataclass(slots=True)
class PageSignals:
    """Детерміністично витягнуті сигнали однієї сторінки."""

    url: str
    depth: int = 0
    status_code: int | None = None
    content_type: str | None = None
    html_bytes: int = 0
    response_ms: int = 0
    redirected_from: str | None = None
    # Ланцюг перенаправлень: пари «код → куди». Порожньо — прямої
    # відповіді, один крок — звичайний редирект.
    #
    # Сигнал уже приходив із мережі й викидався на етапі витягування, а
    # `redirected_from` зберігав лише факт «нас кудись перекинуло».
    # Ланцюг із трьох стрибків, редирект у 404 і послідовність
    # http → https → www від цього не відрізнити. Детектора поки немає;
    # тут лежить те, з чого його можна буде зробити, не переробляючи збір.
    redirect_chain: tuple[tuple[int, str], ...] = ()
    # Транспорт цієї відповіді. Порожньо — знімок старший за поле або
    # запит не вдався; це «невідомо», а не «HTTP/1.1».
    http_version: str = ""
    accept_encoding: str = ""

    title: str | None = None
    meta_description: str | None = None
    meta_robots: str | None = None
    # `<meta http-equiv="refresh">` — вміст атрибута, якщо є. Документ, який
    # лише відсилає далі, не є сторінкою, за яку себе видає; E-10 читає
    # це разом із відсутністю наміру, а не окремо.
    meta_refresh: str | None = None
    canonical: str | None = None
    lang: str | None = None
    # Заявлені мовні версії цієї сторінки, з усіх трьох механізмів.
    hreflang: list[HreflangRef] = field(default_factory=list)
    # Звідки ми дізналися про цю адресу: entry | response | sitemap |
    # render. Список, а не одне значення: та сама сторінка буває і в
    # карті, і в меню. Порожньо — знімок старший за це поле, і мовчання
    # тут означає «невідомо», а не «зі статичного HTML».
    discovered_via: list[str] = field(default_factory=list)
    # Підресурси, запитані по `http://`. Порожньо на сторінці, яка
    # сама по http: змішаного вмісту там не буває за визначенням, і
    # про незахищений документ говорить окремий чек.
    insecure_refs: list[InsecureRef] = field(default_factory=list)
    viewport: str | None = None
    charset: str | None = None

    h1: list[str] = field(default_factory=list)
    headings: list[tuple[int, str]] = field(default_factory=list)
    # Чи стоять заголовки в порядку документа — провенанс, а не здогад.
    #
    # До E-16 екстрактор обходив `h1`…`h6` рівень за рівнем, тож послідовність
    # приходила відсортованою: `h1,h3,h3,h2` зберігалось як `1,2,3,3`. За таким
    # списком пропуск рівня В ПОРЯДКУ ЧИТАННЯ недосяжний — його там просто
    # немає, — і відновити його зі згрупованого списку неможливо.
    #
    # Дефолт `False` тримає сумісність знімків: у знімку, знятому до появи поля,
    # ключа немає взагалі, і `False` там означає рівно те, що має означати, —
    # порядок ми не доводили. Прапорець ставить лише сам екстрактор, побачивши
    # документ; жоден споживач не має права вивести його з самих заголовків.
    headings_in_document_order: bool = False
    text: str = ""
    word_count: int = 0

    links: list[LinkRef] = field(default_factory=list)
    images_total: int = 0
    images_without_alt: int = 0
    images_without_dimensions: int = 0
    images_by_format: dict[str, int] = field(default_factory=dict)
    lazy_images: int = 0

    # Видимий слід «хлібних крихт» у розмітці: `nav[aria-label=breadcrumb]`,
    # `ol.breadcrumb` тощо. Збережений факт, а НЕ заміна `BreadcrumbList`:
    # намальований слід бачить людина, а структуровані дані читає машина, і
    # перше не доводить другого. E-15 бере його двічі — як доказ, і як
    # зʼєднувальну згадку, коли слід дитини веде на її ж батька.
    #
    # Дефолт `False` тримає сумісність знімків: у знімку, знятому до появи
    # поля, ключа немає взагалі, і `False` там означає рівно те, що
    # означало досі, — ми цього не бачили.
    breadcrumb_ui: bool = False

    jsonld: list[dict[str, Any]] = field(default_factory=list)
    jsonld_errors: list[str] = field(default_factory=list)
    microdata_types: list[str] = field(default_factory=list)
    opengraph: dict[str, str] = field(default_factory=dict)
    twitter_card: dict[str, str] = field(default_factory=dict)

    render_blocking_scripts: int = 0
    render_blocking_styles: int = 0
    inline_script_bytes: int = 0

    # Заголовки відповіді в нижньому регістрі: з них читаються security-заголовки
    # й кешування, які інакше зі статичного HTML не видно.
    headers: dict[str, str] = field(default_factory=dict)

    third_party_hosts: list[str] = field(default_factory=list)
    font_hosts: list[str] = field(default_factory=list)
    analytics: list[str] = field(default_factory=list)
    # З чого склався перелік вище: вид доказу, правило, канал і безпечно
    # врізаний сигнал. Порожньо — знімок старший за класифікацію, і тоді
    # рядки `analytics` читаються як спадщина: вендорський маркер лишається
    # доказом, а мітка `first_party` — ні (E-11). Прості словники, а не
    # вкладений dataclass: знімок відновлює лише те, що вміє назвати.
    analytics_observations: list[dict[str, str]] = field(default_factory=list)
    verifications: list[str] = field(default_factory=list)
    # Бібліотеки анти-абюзу, підключені скриптами САМОЇ СТОРІНКИ. Вони не
    # доводять, що конкретна форма ними користується, — але саме так
    # виглядає невидима reCAPTCHA v3, тож твердження «видимого захисту
    # немає» при них недоведене.
    protection_libraries: list[str] = field(default_factory=list)
    # Чи дивилися ми на форми цієї сторінки взагалі. Прапорець живе на
    # СТОРІНЦІ, а не на формі: сторінка без форм не має де його нести, і
    # без нього «форм немає» не відрізнити від «не шукали». Знімок,
    # знятий до появи сканування, лишається False і не свідчить.
    forms_scanned: bool = False

    forms: list[FormSignals] = field(default_factory=list)
    images_with_srcset: int = 0
    preloads: list[str] = field(default_factory=list)
    mailto_addresses: list[str] = field(default_factory=list)
    tel_links: list[str] = field(default_factory=list)
    # Скільки з них стоять поза `<nav>` і `<footer>` — тобто в самій
    # сторінці, а не в обвʼязці, спільній для всього сайту.
    body_contacts: int = 0
    # Написи на кнопках у тілі сторінки. Заклик до дії на сучасних сайтах
    # часто не посилання, а `<button>`, і чек, який дивиться лише на `<a>`,
    # оголошував би сторінки Moz і HubSpot такими, що не ведуть нікуди.
    body_buttons: list[str] = field(default_factory=list)

    # Інші адреси тієї самої логічної сторінки: `site` і `site/`,
    # варіанти з параметрами, canonical-дублі. Порожньо, поки сторінка
    # трапилася одна. Йде в докази: клієнт має бачити, що ми не рахували
    # одну сторінку кілька разів.
    url_variants: list[str] = field(default_factory=list)

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    @property
    def is_content_shell(self) -> bool:
        """Багато розмітки, майже немає тексту — вміст приходить скриптом.

        Такі сторінки не можна судити за вмістом: ми його просто не
        отримали. Інакше одна причина породжує вервечку наслідків —
        «немає H1», «замало тексту», «немає прямої відповіді».
        """
        if self.html_bytes < 5000:
            return False
        return self.word_count < 100 and len(self.text) / self.html_bytes < 0.05

    def to_json(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "meta_description": self.meta_description,
            "meta_robots": self.meta_robots,
            "canonical": self.canonical,
            "lang": self.lang,
            "h1": self.h1,
            "headings": self.headings,
            "word_count": self.word_count,
            "images": {
                "total": self.images_total,
                "without_alt": self.images_without_alt,
                "without_dimensions": self.images_without_dimensions,
                "by_format": self.images_by_format,
                "lazy": self.lazy_images,
            },
            "jsonld_types": [t for p in self.jsonld for t in _types_of(p)],
            "jsonld_errors": self.jsonld_errors,
            "opengraph": self.opengraph,
            "twitter_card": self.twitter_card,
            "url_variants": self.url_variants,
            "links_total": len(self.links),
            "links_internal": sum(1 for link in self.links if link.is_internal),
            "third_party_hosts": self.third_party_hosts,
            "analytics": self.analytics,
            "forms": len(self.forms),
        }


def _schema_types(page: PageSignals) -> list[str]:
    return [t for node in page.jsonld for t in _types_of(node)]


def _types_of(node: dict[str, Any]) -> list[str]:
    raw = node.get("@type")
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [t for t in raw if isinstance(t, str)]
    return []


@dataclass(slots=True)
class RobotsInfo:
    exists: bool = False
    status_code: int | None = None
    content: str = ""
    disallows_all: bool = False
    sitemaps: list[str] = field(default_factory=list)
    crawl_delay: float | None = None
    # Кого з відомих AI-краулерів не пускають на корінь сайту.
    blocked_ai_agents: list[str] = field(default_factory=list)
    # Розібраний файл, щоб детектор міг питати про конкретні шляхи, а не
    # перерозбирати текст. `Any`, бо `types` не імпортує розбирач:
    # напрямок залежностей лишається одним.
    parsed: Any = None


@dataclass(slots=True)
class SitemapInfo:
    exists: bool = False
    status_code: int | None = None
    url: str | None = None
    url_count: int = 0
    urls: list[str] = field(default_factory=list)
    parse_error: str | None = None
    # Без lastmod пошук не бачить, що після перебудови сайту щось змінилося.
    has_lastmod: bool = False
    # Анотації `xhtml:link` з карти: адреса → її заявлені версії.
    # Сайт із карти-єдиного джерела hreflang інакше виглядав би так,
    # ніби не оголосив нічого.
    hreflang: dict[str, list[HreflangRef]] = field(default_factory=dict)
    # Скільки адрес карти анотовано взагалі — до нашого зрізу.
    hreflang_url_count: int = 0
    # Адреса → файл карти, у якому вона стоїть. Порожньо на знімках,
    # старших за це поле: там походження не «одне», а невідоме, і
    # плутати ці стани не можна.
    sources: dict[str, str] = field(default_factory=dict)
    # Медіа, причеплені до записів карти: адреса сторінки → ресурси.
    # Зберігаються для майбутньої роботи з вертикальними картами;
    # жодного чека на них немає.
    images: dict[str, list[str]] = field(default_factory=dict)
    # Чи є верхній файл індексом і яку дитину ми з нього прочитали.
    # Читаємо поки одну — решта лишається невідкритою, а не порожньою.
    is_index: bool = False
    children_read: list[str] = field(default_factory=list)
    children_total: int = 0
    # Чи прочитано індекс цілком. Хибно — погляд вибірковий, і
    # жодне твердження не сміє звучати як про всю карту.
    index_complete: bool = True


@dataclass(slots=True)
class LlmsTxtInfo:
    exists: bool = False
    status_code: int | None = None
    content: str = ""
    has_h1: bool = False
    section_count: int = 0
    link_count: int = 0


@dataclass(slots=True)
class MetricValue:
    value: float | None
    unit: str
    rating: str | None = None  # good | needs-improvement | poor


@dataclass(slots=True)
class PerformanceResult:
    provider: str
    strategy: Strategy
    url: str
    fetched: bool = False
    error: str | None = None
    lab: dict[str, MetricValue] = field(default_factory=dict)
    field_data: dict[str, MetricValue] = field(default_factory=dict)
    lighthouse_score: float | None = None
    opportunities: list[dict[str, Any]] = field(default_factory=list)

    # Доступність приходить тим самим запитом до PSI: Lighthouse усередині
    # використовує axe-core, тож окремий движок нам не потрібен. None —
    # категорію не запитували або відповіді не було; це не те саме, що
    # «проблем немає».
    accessibility_score: float | None = None
    # Те, що бачать ЧЕКИ: без дублів наших власних перевірок. Міняти цей
    # склад не можна — на ньому стоїть бал модуля.
    accessibility_failures: list[dict[str, Any]] = field(default_factory=list)
    # Те, що бачить КЛІЄНТ у знімку доступності: усе, що Lighthouse
    # справді провалив. Фільтр дублів — рішення про ШТРАФ, а не про
    # правду: на 150 перевірених сайтів придушена вада мала свій
    # відповідник на тій самій сторінці лише в 24.7% випадків для
    # `heading-order` і 51.4% для `image-alt`. На чотирьох сайтах
    # придушене не було покрито ніде, і клієнт бачив «проблем немає»
    # там, де Lighthouse знайшов справжню ваду.
    accessibility_failures_all: list[dict[str, Any]] = field(default_factory=list)

    # Скільки перевірок доступності Lighthouse СПРАВДІ зробив на цій
    # сторінці. Бал категорії — це середнє по застосовних перевірках, тож
    # без знаменника він не читається: madpc.gr має 37 при 3 провалах з 4
    # застосовних, web.dev — 90 при тих самих 3 провалах з 29. Різниця
    # цілком у знаменнику, і без нього обидва числа виглядають як оцінка
    # того самого.
    #
    # `failed` рахує провали ДО фільтра `_A11Y_NOISE`: той прибирає
    # дублікати наших власних чеків із клієнтського переліку, і для
    # питання «скільки Lighthouse перевірив» він не має значення.
    #
    # None означає «не збирали» — знімок, знятий до появи цих полів, не
    # сміє свідчити нулем, що перевірок не було. Нуль тут — це вимір.
    accessibility_audits_total: int | None = None
    accessibility_applicable: int | None = None
    accessibility_passed: int | None = None
    accessibility_failed: int | None = None

    def metric(self, name: str) -> MetricValue | None:
        """Field-дані пріоритетніші за lab: це реальні користувачі."""
        return self.field_data.get(name) or self.lab.get(name)


@dataclass(slots=True)
class ResourceLoad:
    """Один ресурс, який сторінка справді завантажила.

    Кількість зовнішніх хостів — слабкий сигнал: вісім легких скриптів
    нешкідливі, а один важкий зʼїдає секунду. Байти й час відповідають
    на питання «скільки це коштує», а не «скільки їх».
    """

    url: str
    host: str
    resource_type: str
    bytes: int = 0
    duration_ms: int = 0
    is_third_party: bool = False


@dataclass(slots=True)
class RenderResult:
    """Сторінка після виконання JS — поруч зі своєю статичною версією.

    Обидві потрібні одночасно: цінність не в самому HTML після рендеру,
    а в різниці між ним і тим, що віддав сервер. Саме ця різниця каже,
    чи побачить сторінку той, хто JS не виконує, — а таких серед тих,
    хто нас цікавить, більшість.
    """

    url: str
    rendered: bool = False
    error: str | None = None
    # Рендеру не було, бо його вимкнули, а не бо він зламався. Те саме
    # розрізнення, що й у SiteBrief.disabled, і з тієї ж причини: вибір
    # користувача не має робити аудит partial.
    disabled: bool = False
    html: str = ""
    # Скільки часу браузер витратив до події networkidle.
    elapsed_ms: int = 0
    # Консольні помилки сторінки: часта причина того, що контент не
    # зʼявився, і водночас те, чого статичний краулер не бачить узагалі.
    console_errors: list[str] = field(default_factory=list)
    # Той самий розбір, що й у статичної версії. Різниця між signals і
    # PageSignals тієї ж сторінки — це і є SSR-дельта.
    signals: PageSignals | None = None
    # Лічильники, знайдені за глобальними обʼєктами живої сторінки.
    # Ловить тих, хто підключений класичним скриптом; SDK, доданий через
    # import, глобальної змінної не створює й сюди не потрапляє.
    runtime_analytics: list[str] = field(default_factory=list)
    # Усі мережеві звернення сторінки. Це і є найнадійніший слід: подію
    # лічильник мусить кудись надіслати, хай навіть через власний домен.
    requests: list[str] = field(default_factory=list)
    resources: list[ResourceLoad] = field(default_factory=list)

    def third_party_bytes(self) -> int:
        return sum(r.bytes for r in self.resources if r.is_third_party)

    def total_bytes(self) -> int:
        return sum(r.bytes for r in self.resources)


@dataclass(slots=True)
class InfraInfo:
    """Те, що видно лише окремими пробами, а не з краулу.

    Дві додаткові вимоги: неіснуючий URL має віддавати 404, а не 200 із
    гарною сторінкою; і www/non-www мають зводитися до одного хоста.
    """

    not_found_checked: bool = False
    not_found_status: int | None = None
    not_found_is_soft: bool = False

    alt_host_checked: bool = False
    alt_host: str | None = None
    alt_host_status: int | None = None
    alt_host_redirects_home: bool = False


@dataclass(slots=True)
class SiteContext:
    """Все, що зібрано про сайт; вхід для всіх чеків."""

    entry_url: str
    origin: str
    is_https: bool = False
    hsts: bool = False
    # Сайт відкрився тільки з вимкненою перевіркою сертифіката: HTTPS у нього
    # формально є, але браузер показує відвідувачу попередження.
    tls_error: str | None = None
    robots: RobotsInfo = field(default_factory=RobotsInfo)
    sitemap: SitemapInfo = field(default_factory=SitemapInfo)
    llms_txt: LlmsTxtInfo = field(default_factory=LlmsTxtInfo)
    infra: InfraInfo = field(default_factory=InfraInfo)
    pages: list[PageSignals] = field(default_factory=list)
    # Сторінки до зведення в логічні — по одній на прочитану адресу.
    # Потрібні, бо краул іде хвилями: сторінка другої хвилі буває
    # варіантом сторінки першої, і побачити це можна лише разом.
    raw_pages: list[PageSignals] = field(default_factory=list)
    # Скільки адрес приніс краул до зведення у логічні сторінки. Різниця
    # між цим числом і len(pages) — і є те, що ми не порахували двічі.
    urls_crawled: int = 0
    # Чи взагалі був у нас шанс побачити оголошені мовні версії.
    # Живий краул завжди дивиться; знімок, зроблений до появи поля,
    # не дивився — і його порожнеча описує нас, а не сайт.
    hreflang_observed: bool = True
    # Мови, які сайт оголосив про себе: `<html lang>`, анотації hreflang і
    # мовні альтернативи карти сайту. На них — і лише на них — тримається
    # право зняти мовний префікс зі шляху (E-12, OD-05).
    #
    # `None` означає «ще не рахували», а не «жодної». Різниця істотна: у
    # знімку, знятому до появи поля, ключа немає взагалі, і порожній список
    # там був би твердженням, якого ніхто не робив. Рахується один раз, при
    # першому питанні, і лягає сюди — тож знімок несе вже пораховане.
    locales_declared: list[str] | None = None
    performance: list[PerformanceResult] = field(default_factory=list)
    failed_urls: dict[str, str] = field(default_factory=dict)
    # Адреси, чий ланцюг перенаправлень не дійшов до кінця. Окремо від
    # `failed_urls`, бо там причина лежить рядком чужої бібліотеки.
    redirect_limited: list[str] = field(default_factory=list)
    # Що зрозуміла модель. None означає, що семантичного аналізу не було —
    # і це не те саме, що «аналіз нічого не знайшов».
    brief: Any = None
    facts: Any = None
    # Факти, зведені з розмітки й посилань усіх сторінок. Заповнюються
    # ДО семантичного шару: модель не має вгадувати те, що краулер уже
    # точно встановив.
    known: Any = None
    # Граф внутрішніх посилань. Заповнюється після краулу: з нього
    # береться важливість сторінки для пріоритезації.
    links: Any = None
    # Відрендерені версії — лише для частини сторінок: рендер бюджетований.
    # Ключ — той самий URL, що й у PageSignals, тож чек завжди може взяти
    # обидві версії однієї сторінки й порівняти.
    renders: dict[str, RenderResult] = field(default_factory=dict)

    @property
    def home(self) -> PageSignals | None:
        """Вхідна сторінка — але лише якщо вона відповіла.

        `pages[0]` — це те, що ми просили завантажити, і `_ordered()`
        гарантує, що вона перша. Гарантії, що вона віддала сторінку,
        немає: `bosch.com/this-page-does-not-exist/` повернув 404, краул
        пішов за посиланнями з error-сторінки й прочитав справжній сайт,
        а головною лишалася неіснуюча адреса. Її title, H1 і розмітку
        чеки судили як головну сторінку компанії.

        Тому беремо першу, яка справді відповіла. Фолбек на `pages[0]`
        лишається для сайту, де не відповіла жодна: там 403-відповідь —
        єдине, що ми маємо, і чеки про заголовки мають її бачити.
        """
        for page in self.pages:
            if page.status_code and 200 <= page.status_code < 300:
                return page
        return self.pages[0] if self.pages else None

    @property
    def ok_pages(self) -> list[PageSignals]:
        return [p for p in self.pages if p.status_code and 200 <= p.status_code < 300]

    @property
    def content_pages(self) -> list[PageSignals]:
        """Сторінки, вміст яких ми справді бачили.

        Для чеків, що судять текст і заголовки. Сторінка-оболонка сюди не
        потрапляє: сам факт, що вмісту немає в HTML, повідомляє окремий
        чек, і дублювати його симптомами не треба.
        """
        return [p for p in self.ok_pages if not p.is_content_shell]

    def primary_performance(self) -> PerformanceResult | None:
        """Вимір, за яким судимо швидкість: мобільний, якщо він є.

        Google ранжує за мобільною версією, і більшість відвідувачів
        теж із телефона. Судити за десктопом означало б хвалити сайт
        за те, чого його клієнти не бачать.
        """
        fetched = [r for r in self.performance if r.fetched]
        for result in fetched:
            if result.strategy is Strategy.MOBILE:
                return result
        return fetched[0] if fetched else None

    def performance_for(self, strategy: Strategy) -> PerformanceResult | None:
        for result in self.performance:
            if result.fetched and result.strategy is strategy:
                return result
        return None

    def rendered(self, url: str) -> PageSignals | None:
        """Сигнали сторінки після виконання JS, якщо її рендерили."""
        result = self.renders.get(url)
        return result.signals if result is not None and result.rendered else None

    def declared_locales(self) -> list[str]:
        """Мови запуску, які сайт оголосив про себе. Рахується один раз.

        Ліниво навмисно. Оголошення виводяться зі сторінок, а сторінки
        приходять хвилями: порахувати їх під час побудови контексту означало
        б порахувати по неповних даних. Перше питання приходить уже після
        краулу, коли все зібрано.
        """
        if self.locales_declared is None:
            from app.audit import hreflang

            self.locales_declared = hreflang.declared_locales(self)
        return self.locales_declared

    def type_of(self, page: PageSignals) -> Any:
        """Що це за сторінка — для правил, які залежать від її призначення.

        Типи розмітки віддаються класифікатору першими: якщо сайт сам
        заявив Product або BlogPosting, це твердження сайту, а не наш
        здогад із адреси.

        Без цього одне правило застосовувалось однаково до головної, до
        сторінки входу в адмінку й до категорії товарів — звідси критична
        знахідка про noindex на wp-login.php і вимога дописати прози до
        каталогу меблів.

        Оголошені мови передаються класифікатору, щоб `/de/preise` судився
        як сторінка цін, а не як невпізнана тека. Неоголошена мова префікса
        не знімає: дві літери в шляху — здогад, а не доказ.
        """
        from app.audit.page_kinds import type_of

        return type_of(page.url, page.title or "", _schema_types(page), self.declared_locales())

    def classify(self, page: PageSignals) -> Any:
        """Тип сторінки разом із підставою: що сталося з мовним префіксом.

        Потрібно там, де висновок треба подати з його якістю, а не самим
        значенням: шлях, що починається схожим на мову сегментом без
        оголошення цієї мови, класифікується, але не є певним.
        """
        from app.audit.page_kinds import classify

        return classify(page.url, page.title or "", _schema_types(page), self.declared_locales())

    def as_seen(self, page: PageSignals) -> PageSignals:
        """Сторінка очима Google: після виконання JS, якщо ми її рендерили.

        Лише для SEO-модуля, і це не дрібниця вибору, а різні читачі.
        Google виконує JS, тож заголовок, доданий скриптом, він бачить, і
        писати йому «немає H1» — брехня, яку клієнт спростує за десять
        секунд, відкривши власну сторінку.

        Асистенти здебільшого JS не виконують. Тому чеки AI-готовності й
        видимості для моделей навмисно лишаються на статичній версії: для
        них розмітка, якої немає у відповіді сервера, не існує. Один і той
        самий факт коштує різного різним читачам, і зводити їх до спільної
        відповіді означало б помилитися для обох.
        """
        return self.rendered(page.url) or page

    def pages_as_seen(self, pages: list[PageSignals]) -> list[PageSignals]:
        return [self.as_seen(page) for page in pages]

    def home_as_seen(self) -> PageSignals | None:
        """Головна найповнішою версією. Її рендерять завжди — вона перша
        в бюджеті, — тож судити її розмітку по статичному HTML немає
        підстав."""
        home = self.home
        return None if home is None else self.as_seen(home)

    def was_rendered(self, page: PageSignals) -> bool:
        return self.rendered(page.url) is not None

    def visible_without_js(self, page: PageSignals) -> float | None:
        """Частка тексту, доступна без JS: 1.0 — весь, 0.0 — нічого.

        None означає, що сторінку не рендерили й вимірювання немає, —
        це не те саме, що «видно все». Чек, який їх сплутає, каратиме
        сайти за брак наших даних.
        """
        after = self.rendered(page.url)
        if after is None or after.word_count == 0:
            return None
        return min(page.word_count / after.word_count, 1.0)

    def third_party_weight(self) -> tuple[int, int, list[tuple[str, int]]] | None:
        """(байти сторонніх, усього байтів, топ хостів) — або None без рендеру.

        Міряється на головній сторінці: саме її бачить більшість людей,
        і саме на ній сидить увесь маркетинговий обвіс.
        """
        home = self.home
        if home is None:
            return None
        result = self.renders.get(home.url)
        if result is None or not result.rendered or not result.resources:
            return None

        by_host: dict[str, int] = {}
        for load in result.resources:
            if load.is_third_party:
                by_host[load.host] = by_host.get(load.host, 0) + load.bytes
        top = sorted(by_host.items(), key=lambda item: -item[1])[:10]
        return result.third_party_bytes(), result.total_bytes(), top

    def _page_analytics(self, page: PageSignals) -> list[Any]:
        """Спостереження сторінки: свіжі з класифікатора або спадщина зі знімка.

        У знімку, знятому до класифікації, лишились самі рядки. Вендорський
        маркер там досі доказ — але саме як спадщина, без вигаданої адреси;
        мітка `first_party` доказом вендора не була ніколи (E-11).
        """
        from app.audit.standards import analytics_vendors as registry

        if page.analytics_observations:
            return registry.load_observations(page.analytics_observations)
        return registry.legacy_observations(page.analytics, registry.Channel.LEGACY_PAGE)

    def analytics_classification(self) -> Any:
        """Чим сайт доводить вимірювання — і наскільки це доведено.

        Три джерела, і жодне окремо не досить: розмітка обох версій
        сторінки, глобальні обʼєкти живої сторінки й адреси її запитів.
        Запити класифікуються ОСТАННІМИ, бо задокументоване проксі на
        власному домені (`/api/event`, `/ingest/`) стає вендором лише разом
        із його співсигналом: інакше порядок джерел вирішував би, чи
        впізнано вендора.
        """
        from app.audit.standards import analytics_vendors as registry

        observations: list[Any] = []
        confirmed = False
        for page in self.ok_pages:
            observations.extend(self._page_analytics(page))
            after = self.rendered(page.url)
            if after is None:
                continue
            confirmed = True
            observations.extend(self._page_analytics(after))
        for result in self.renders.values():
            observations.extend(registry.observe_runtime(result.runtime_analytics))

        requests = [url for result in self.renders.values() for url in result.requests]
        co_signals = registry.vendors_of(observations)
        from_requests = registry.observe_requests(
            requests, origin=self.origin, co_signals=co_signals
        )
        wider = registry.vendors_of([*observations, *from_requests])
        if set(wider) != set(co_signals):
            # Лоадер вендора міг прийти самим запитом — тоді проксі, яке
            # першим проходом лишилось невпізнаним, уже має співсигнал.
            from_requests = registry.observe_requests(
                requests, origin=self.origin, co_signals=wider
            )
        return registry.classify([*observations, *from_requests], rendered=confirmed)

    def analytics_found(self) -> tuple[set[str], bool]:
        """Впізнані вендори й чи підтверджено це рендером.

        Другий елемент важливіший за перший. Без рендеру «не знайшли
        лічильника» означає лише те, що його немає в статичному HTML —
        а Vercel вставляє свій після гідрації. З рендером це вже
        твердження про сайт, а не про межі нашого зору.

        Сумісна форма для читачів, яким потрібні лише імена: вид доказу,
        стан і самі спостереження дає `analytics_classification`.
        """
        state = self.analytics_classification()
        return set(state.verified), state.rendered

    def measured_rating(self, metric: str) -> str | None:
        """Оцінка реально виміряної метрики, якщо провайдер її дав.

        Потрібна, щоб евристика поступалася вимірюванню: карати за
        «зображення без width/height», коли виміряний CLS дорівнює нулю, —
        це карати за передвісник проблеми, якої немає.
        """
        for result in self.performance:
            if not result.fetched:
                continue
            value = result.metric(metric)
            if value is not None and value.rating:
                return value.rating
        return None


CheckResult = list[Issue]

__all__ = [
    "Confidence",
    "Degradation",
    "DegradationKind",
    "Effort",
    "FormSignals",
    "InfraInfo",
    "Issue",
    "LinkRef",
    "LlmsTxtInfo",
    "MetricValue",
    "Module",
    "PageSignals",
    "PerformanceResult",
    "RobotsInfo",
    "Severity",
    "SiteContext",
    "SitemapInfo",
    "Strategy",
]
