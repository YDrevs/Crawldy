"""Вибірка для порівняння з AuditLens: що взято й чому саме воно.

Класи навмисно нерівні за розміром. Верхній рівень великий, бо на ньому
міряється хибне спрацювання: продукт, який знаходить роботу там, де її
мало, псує довіру швидше за той, що пропускає знахідку. Крайні випадки
представлені по одному, бо кожен із них перевіряє окрему поведінку, і
другий сайт того самого класу нічого не додає.

Список AuditLens зафіксований Сергієм 2026-08-23: пʼятнадцять сайтів,
по одному представнику класу. Він менший за наш свідомо — кожен прогін
конкурента коштує грошей, — і стратифікований, а не зменшений
випадково. Розширювати його варто лише тоді, коли порівняння покаже
питання, на яке одного сайту класу замало.

Підміняти сайти в ньому не можна навіть тоді, коли один із них незручний
для нас: вибірка, з якої прибрали невдалий випадок, міряє вже не
продукт, а наш вибір.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Site:
    url: str
    site_class: str
    why: str
    in_auditlens_set: bool = False


#: Класи, з яких складається вибірка. Порядок — від найкращих до тих,
#: яких фактично немає: саме в такому порядку читається підсумкова
#: таблиця, і саме в ньому зростає роль чесної відмови від оцінки.
CLASSES = (
    "exemplary",
    "healthy",
    "ordinary",
    "issue_rich",
    "js_heavy",
    "large_sampled",
    "partial_crawl",
    "contradictory",
    "entry_404",
    "performance_severe",
    "broken",
    "dead",
    "zero_pages",
    "blocked",
    "competitor",
)

CORPUS: tuple[Site, ...] = (
    # ── взірцеві: міряють хибне спрацювання, а не вміння знаходити ──
    Site("https://stripe.com/", "exemplary",
         "Контроль хибних спрацювань. Мало що зламано, тож кожна знахідка тут "
         "має доводити себе."),
    Site("https://web.dev/", "exemplary",
         "Технічний контроль: сайт, який сам публікує ці правила. Знахідка тут "
         "або справжня, або показує узагальнене правило без контексту.",
         in_auditlens_set=True),
    Site("https://docs.stripe.com/", "exemplary",
         "Документація на піддомені: перевіряє, чи не вимагає продукт від "
         "довідки авторства й розмітки статті."),
    Site("https://developer.mozilla.org/", "exemplary",
         "Велика довідка, зразковий технічний стан."),
    Site("https://www.gov.uk/", "exemplary", "Державний сайт: доступність і простота як вимога."),
    Site("https://developers.cloudflare.com/", "exemplary",
         "Документація великого постачальника."),
    Site("https://www.cloudflare.com/", "exemplary",
         "Маркетинговий сайт того самого постачальника."),
    Site("https://www.anthropic.com/", "exemplary", "Сучасний маркетинговий сайт."),
    Site("https://supabase.com/docs", "exemplary", "Документація на JS-фреймворку."),
    Site("https://huggingface.co/", "exemplary", "Великий каталог із користувацьким вмістом."),
    Site("https://www.shopify.com/", "exemplary", "Платформа електронної торгівлі."),
    Site("https://www.mintlify.com/docs", "exemplary", "Документація як продукт."),
    Site("https://dronehub.ai/", "exemplary",
         "Контроль верхнього рівня: невеликий сайт, зроблений професійно. "
         "Взірцевість тут не походить від розміру команди.",
         in_auditlens_set=True),
    Site("https://ahrefs.com/", "healthy", "Конкурент у SEO: сам себе аудитує."),
    Site("https://www.semrush.com/", "healthy", "Те саме, більший і важчий."),
    Site("https://moz.com/", "js_heavy",
         "Кнопки домальовує скрипт: перевіряє, чи розрізняє продукт статичну "
         "версію й відрендерену."),
    Site("https://www.hubspot.com/", "js_heavy", "Те саме на важчому стеку."),
    Site("https://linear.app/", "js_heavy",
         "SPA: у статичному HTML майже немає вмісту. Головний випадок для "
         "порівняння того, що продукт справді спостерігав.", in_auditlens_set=True),

    # ── звичайні: працюють, але без зусиль у наших вимірах ──
    Site("https://www.python.org/", "ordinary", "Опорна точка калібрування."),
    Site("https://fastapi.tiangolo.com/", "ordinary", "Документація на генераторі статики."),
    Site("https://vercel.com/", "ordinary", "Маркетинг на власному хостингу."),
    Site("https://backlinko.com/", "ordinary", "Контентний сайт про SEO."),
    Site("https://searchengineland.com/", "ordinary", "Видання з рекламою й лічильниками."),
    Site("https://www.searchenginejournal.com/", "ordinary", "Те саме, важче."),
    Site("https://www.jasper.ai/blog", "ordinary", "Блог продукту."),
    Site("https://ka-dent.com.ua/", "ordinary",
         "Малий бізнес, який доглядають. Перевіряє, чи не карає продукт "
         "невеликий сайт за те, що він невеликий.", in_auditlens_set=True),

    # ── багаті на проблеми: малий бізнес без обслуговування ──
    Site("https://rightpricerooter.com/", "issue_rich",
         "Типовий занедбаний сайт послуг: перевіряє порядок рекомендацій, коли "
         "зламано багато що одразу.", in_auditlens_set=True),
    Site("https://24hourplumberdfw.com/", "issue_rich", "Сантехніка, той самий клас."),
    Site("https://www.risingsonplumbing.com/", "issue_rich", "Сантехніка."),
    Site("https://hvac-oc.com/", "issue_rich", "Кондиціонування."),
    Site("https://www.airtechsolutionsinc.com/", "issue_rich", "Кондиціонування."),
    Site("https://seversonheating.com/", "issue_rich", "Опалення."),
    Site("https://perryairebuilders.com/", "issue_rich", "Будівництво."),
    Site("https://www.twohillsaccounting.com/", "issue_rich",
         "Бухгалтерія; редирект на інший хост."),
    Site("https://www.norwood-dental.net/", "issue_rich", "Стоматологія."),
    Site("https://www.aldg.org/", "issue_rich", "Громадська організація."),
    Site("https://crustula.com.ua/", "issue_rich", "Український малий бізнес."),
    Site("https://1csmart.com.ua/", "issue_rich", "Редиректить на smartkp."),
    Site("https://smartkp.com.ua/", "issue_rich", "Кінцевий хост попереднього."),
    Site("https://americanhps.wixsite.com/americanhps", "issue_rich",
         "Конструктор сайтів: машинно читабельніший за складний SPA, "
         "і це не збій шкали."),
    Site("https://clouddimension.in/", "issue_rich", "Невелика ІТ-компанія."),
    Site("https://www.microtechia.com/", "issue_rich", "Невелика ІТ-компанія."),
    Site("https://powertronglobal.com/", "issue_rich", "Невелика ІТ-компанія."),
    Site("https://anchoredgetechno.com/", "issue_rich", "Невелика ІТ-компанія."),

    # ── крайні випадки: кожен перевіряє окрему поведінку ──
    Site("https://www.gocplumbing.com/", "partial_crawl",
         "Сім адрес з одинадцяти не відповіли. Чи зізнається продукт у "
         "прогалині — чи видасть упевнений бал за меншістю сторінок.",
         in_auditlens_set=True),
    Site("https://oldetownhall.com/", "dead",
         "Акаунт у хостера призупинено: єдина сторінка на чотирнадцять слів. "
         "Раніше отримував 68 балів.", in_auditlens_set=True),
    Site("https://kendanielscpa.com/", "zero_pages",
         "Не віддав жодної сторінки: має давати overall=None.", in_auditlens_set=True),
    Site("https://www.twelvestrike.com/", "contradictory",
         "Редиректить на creativecustomcutouts.weebly.com: вхідний хост не "
         "дорівнює кінцевому.", in_auditlens_set=True),
    Site("https://openai.com/", "blocked",
         "403 нашому агенту за власним рішенням сайту. Бал не відтворюється "
         "між прогонами — це властивість вимірювання, а не регресія."),
    Site("https://aequo.ua/", "blocked", "403 без заглушки в User-Agent: свідомий захист."),

    # ── випадки з CLAUDE.md, яких у калібрувальному файлі не було ──
    Site("https://www.unilever.com/", "blocked",
         "403 на все. Бал чесно None, але поруч раніше стояло тринадцять "
         "тверджень про сайт, якого ми не бачили.", in_auditlens_set=True),
    Site("https://asana.com/", "large_sampled",
         "Двадцять адрес із 3407. Перевіряє, чи стоїть покриття поруч із балом.",
         in_auditlens_set=True),
    Site("https://www.furniturerow.com/", "large_sampled",
         "8147 адрес у карті сайту, початок зайнятий товарними GUID. "
         "Перевіряє рівномірність вибірки."),
    Site("https://calendly.com/", "performance_severe",
         "LCP 5204 мс та INP 652 мс — обидві критичні. Перевіряє, чи коштує "
         "друга провалена метрика бодай чогось.", in_auditlens_set=True),
    Site("https://www.bosch.com/this-page-does-not-exist/", "entry_404",
         "Вхідна адреса віддає 404, краул іде за посиланнями зі сторінки "
         "помилки. Перевіряє, що судиться справжня головна, а не 404.",
         in_auditlens_set=True),
    Site("https://auditlensapp.com/", "competitor",
         "Самоаудит конкурента: чи проходить продукт власну перевірку.",
         in_auditlens_set=True),
)


def auditlens_set() -> tuple[Site, ...]:
    """Стратифікована вибірка для платних прогонів конкурента."""
    return tuple(site for site in CORPUS if site.in_auditlens_set)


def by_class() -> dict[str, list[Site]]:
    grouped: dict[str, list[Site]] = {}
    for site in CORPUS:
        grouped.setdefault(site.site_class, []).append(site)
    return grouped
