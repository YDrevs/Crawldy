"""Хто з AI-систем ходить по вебу, під яким іменем і навіщо.

## Навіщо реєстр, а не список рядків

Попередником цього файлу був кортеж з одинадцяти рядків усередині
`site_context.py`. Він не казав ані звідки взялося ім'я, ані коли його
востаннє звіряли, ані — найважливіше — навіщо цей краулер ходить. Через
це блокування пошукового краулера й блокування навчального виглядали
однією знахідкою, хоча перше зазвичай випадкове й коштує видимості, а
друге — свідома політика власника.

Ціна була не теоретичною: у списку не було `Claude-SearchBot`. Anthropic
пише, що його вимкнення заважає індексувати вміст для пошуку, тобто може
знизити видимість і точність у результатах Claude, — і сайт, що блокував
його, не отримував жодної знахідки. Сильнішого висновку («вирішує, чи
цитуватиме Claude») вендор не дає, і ми його не робимо.

## Правило первинного джерела

Запис потрапляє сюди лише тоді, коли **вендор сам** документує і токен,
і призначення. Каталоги ботів, добірки на GitHub, статті в блогах і
бази сканерів для цього не годяться: вони відстають, суперечать одне
одному й не відповідають за семантику вендора. Вони можуть підказати,
що запис застарів, — але джерелом правди не стають.

Призначення не виводиться з назви. `Google-Extended` звучить як щось
про пошук, а керує навчанням Gemini і grounding, і Google прямо пише, що
на потрапляння в Пошук він не впливає взагалі.

Призначень у краулера буває кілька, і робота з robots.txt у них теж
різна: `Perplexity-User` вендор описує як агента, що зазвичай robots.txt
ігнорує. Заборона для нього — це намір власника, а не доведений
результат, і знахідкою вона не стає.

## Оновлення відбувається релізом, а не під час аудиту

Ніхто не ходить у документацію вендора в момент аудиту клієнта: аудит
не має залежати ані від чужої доступності, ані від чужої швидкості.
Реєстр оновлюється правкою цього файлу, а тест стежить, щоб дата
звірки не постаріла мовчки.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum

# Скільки днів звірка вважається свіжою. Вендори міняють ботів рідше, ніж
# раз на пів року, але й не настільки рідко, щоб про це можна було забути.
# Тест не падає від простроченої дати — він її називає; рішення, коли
# перезвіряти, лишається людині.
VERIFICATION_MAX_AGE_DAYS = 180


class CrawlerPurpose(StrEnum):
    """Навіщо краулер приходить. Три значення, і кожне з документації.

    Таксономія навмисно вузька. Четверте значення додається лише тоді,
    коли справжній запис не вкладається в наявні три, — а не тоді, коли
    здається, що колись знадобиться.
    """

    # Індексує сторінки, щоб система могла показати й процитувати їх у
    # відповіді. Блокування б'є саме по видимості.
    SEARCH = "search"
    # Ходить за конкретним посиланням на прохання людини, яка щойно про
    # це запитала. Блокування ламає сценарій «покажи мені цю сторінку».
    USER_INITIATED = "user_initiated"
    # Постачає вміст моделі в момент відповіді, щоб та спиралася на
    # факти. Блокування прибирає сайт із джерел відповіді — це втрата
    # видимості, але в асистенті, а не в пошуку.
    GROUNDING = "grounding"
    # Збирає матеріал для навчання моделей. Блокування — законна
    # позиція власника щодо своїх текстів, а не дефект.
    TRAINING = "training"


@dataclass(frozen=True, slots=True)
class AiCrawler:
    """Один краулер: як він зветься в robots.txt і чим підтверджений."""

    vendor: str
    # Точний токен product-token із robots.txt. Порівняння за RFC 9309
    # регістронезалежне, але зберігаємо так, як пише вендор.
    token: str
    # Призначень може бути кілька, і це не запас на майбутнє:
    # `Google-Extended` одним токеном керує і навчанням, і grounding.
    # Одне поле змусило б викинути половину сенсу.
    purposes: tuple[CrawlerPurpose, ...]
    # Сторінка вендора, з якої взято і токен, і призначення.
    source_url: str
    last_verified_at: date
    # Чи виконує цей агент robots.txt. `False` там, де вендор прямо пише,
    # що не виконує: тоді заборона в robots.txt не є доказом блокування,
    # і робити з неї знахідку означало б стверджувати те, що документація
    # вендора спростовує.
    obeys_robots: bool = True
    note: str = ""

    @property
    def key(self) -> str:
        return self.token.lower()

    def serves(self, purpose: CrawlerPurpose) -> bool:
        return purpose in self.purposes


AI_CRAWLERS: tuple[AiCrawler, ...] = (
    # ── OpenAI ────────────────────────────────────────────────────────
    AiCrawler(
        vendor="OpenAI",
        token="OAI-SearchBot",
        purposes=(CrawlerPurpose.SEARCH,),
        source_url="https://developers.openai.com/api/docs/bots",
        last_verified_at=date(2026, 8, 25),
        note="«surface websites in search results in ChatGPT's search features»",
    ),
    AiCrawler(
        vendor="OpenAI",
        token="ChatGPT-User",
        purposes=(CrawlerPurpose.USER_INITIATED,),
        source_url="https://developers.openai.com/api/docs/bots",
        last_verified_at=date(2026, 8, 25),
        note="«used for certain user actions in ChatGPT»",
    ),
    AiCrawler(
        vendor="OpenAI",
        token="GPTBot",
        purposes=(CrawlerPurpose.TRAINING,),
        source_url="https://developers.openai.com/api/docs/bots",
        last_verified_at=date(2026, 8, 25),
        note="«crawl content that may be used in training»",
    ),
    # ── Anthropic ─────────────────────────────────────────────────────
    AiCrawler(
        vendor="Anthropic",
        token="Claude-SearchBot",
        purposes=(CrawlerPurpose.SEARCH,),
        source_url=(
            "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-"
            "from-the-web-and-how-can-site-owners-block-the-crawler"
        ),
        last_verified_at=date(2026, 8, 25),
        note="«indexes web content to improve search result quality»",
    ),
    AiCrawler(
        vendor="Anthropic",
        token="Claude-User",
        purposes=(CrawlerPurpose.USER_INITIATED,),
        source_url=(
            "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-"
            "from-the-web-and-how-can-site-owners-block-the-crawler"
        ),
        last_verified_at=date(2026, 8, 25),
        note="«supports user-initiated web access when individuals query Claude»",
    ),
    AiCrawler(
        vendor="Anthropic",
        token="ClaudeBot",
        purposes=(CrawlerPurpose.TRAINING,),
        source_url=(
            "https://support.claude.com/en/articles/8896518-does-anthropic-crawl-data-"
            "from-the-web-and-how-can-site-owners-block-the-crawler"
        ),
        last_verified_at=date(2026, 8, 25),
        note="«collects web content for generative AI model training»",
    ),
    # ── Perplexity ────────────────────────────────────────────────────
    AiCrawler(
        vendor="Perplexity",
        token="PerplexityBot",
        purposes=(CrawlerPurpose.SEARCH,),
        source_url="https://docs.perplexity.ai/guides/bots",
        last_verified_at=date(2026, 8, 25),
        note="«surface and link websites in search results»; не для навчання",
    ),
    AiCrawler(
        vendor="Perplexity",
        token="Perplexity-User",
        purposes=(CrawlerPurpose.USER_INITIATED,),
        source_url="https://docs.perplexity.ai/guides/bots",
        last_verified_at=date(2026, 8, 25),
        obeys_robots=False,
        note=(
            "«supports user actions within Perplexity». Вендор прямо каже: "
            "«Since a user requested the fetch, this fetcher generally ignores "
            "robots.txt rules» — тому заборона в robots.txt не доводить, що "
            "цей агент не прийде, і знахідкою про блокування не стає"
        ),
    ),
    # ── Google ────────────────────────────────────────────────────────
    AiCrawler(
        vendor="Google",
        token="Google-Extended",
        # Два призначення одним токеном, і саме тому призначення — кортеж.
        # Назвати це лише навчанням означало б промовчати про те, що
        # справді коштує видимості: без grounding Gemini не бере вміст
        # сайту у відповідь.
        purposes=(CrawlerPurpose.GROUNDING, CrawlerPurpose.TRAINING),
        source_url=(
            "https://developers.google.com/search/docs/crawling-indexing/"
            "google-common-crawlers"
        ),
        last_verified_at=date(2026, 8, 25),
        note=(
            "«training future generations of Gemini models» ТА «grounding "
            "(providing content from the Google Search index to the model at "
            "prompt time)». Google окремо наголошує: «does not impact a "
            "site's inclusion in Google Search nor is it used as a ranking "
            "signal» — подавати це як проблему Пошуку не можна"
        ),
    ),
    # ── Meta ──────────────────────────────────────────────────────────
    AiCrawler(
        vendor="Meta",
        token="meta-webindexer",
        purposes=(CrawlerPurpose.SEARCH,),
        source_url=(
            "https://developers.facebook.com/docs/sharing/webmasters/web-crawlers"
        ),
        last_verified_at=date(2026, 8, 25),
        note="«improve Meta AI search result quality for users»",
    ),
    AiCrawler(
        vendor="Meta",
        token="meta-externalfetcher",
        purposes=(CrawlerPurpose.USER_INITIATED,),
        source_url=(
            "https://developers.facebook.com/docs/sharing/webmasters/web-crawlers"
        ),
        last_verified_at=date(2026, 8, 25),
        note="«fetches individual links at a user's request»",
    ),
    AiCrawler(
        vendor="Meta",
        token="meta-externalagent",
        purposes=(CrawlerPurpose.TRAINING,),
        source_url=(
            "https://developers.facebook.com/docs/sharing/webmasters/web-crawlers"
        ),
        last_verified_at=date(2026, 8, 25),
        note="«training foundation AI models or improving products by indexing»",
    ),
)


# Токени, які були в старому кортежі й до реєстру не потрапили. Список
# існує, щоб зняття запису лишалося рішенням із причиною, а не тихим
# зникненням, — і щоб наступний рефакторинг не повернув їх «для повноти».
RETIRED_TOKENS: dict[str, str] = {
    "claude-web": (
        "витіснений вендором: чинна документація Anthropic перелічує "
        "ClaudeBot, Claude-User і Claude-SearchBot, цього імені серед них немає"
    ),
    "anthropic-ai": (
        "витіснений вендором: у чинній документації Anthropic відсутній"
    ),
    "ccbot": (
        "Common Crawl описує себе як відкритий архів вебу, а не як пошуковий, "
        "користувацький чи навчальний краулер AI-вендора; жодне з трьох "
        "призначень первинним джерелом не підтверджується"
    ),
    "bytespider": (
        "первинного джерела немає: ByteDance не публікує доступної "
        "документації краулера, а всі наявні описи — вторинні каталоги ботів"
    ),
}


def tokens() -> frozenset[str]:
    """Усі відомі токени в нижньому регістрі — для швидкої перевірки."""
    return frozenset(c.key for c in AI_CRAWLERS)


def crawler_for(token: str) -> AiCrawler | None:
    key = token.strip().lower()
    return next((c for c in AI_CRAWLERS if c.key == key), None)


def registry_problems(*, today: date | None = None) -> list[str]:
    """Що не так із реєстром. Порожньо — все гаразд.

    Перевіряється те, чого не видно з очей: дубль токена, порожнє
    джерело, відсутня дата, прострочена звірка. Реєстр без провенансу
    нічим не кращий за кортеж, з якого він виріс.
    """
    now = today or date.today()
    problems: list[str] = []

    seen: dict[str, AiCrawler] = {}
    for crawler in AI_CRAWLERS:
        if crawler.key in seen:
            problems.append(f"дубль токена: {crawler.token}")
        seen[crawler.key] = crawler

        if not crawler.vendor.strip():
            problems.append(f"{crawler.token}: не вказано вендора")
        if not crawler.source_url.startswith("https://"):
            problems.append(f"{crawler.token}: джерело не є https-адресою")
        if not crawler.purposes:
            problems.append(f"{crawler.token}: не вказано жодного призначення")
        for purpose in crawler.purposes:
            if not isinstance(purpose, CrawlerPurpose):  # pragma: no cover
                problems.append(f"{crawler.token}: невідоме призначення {purpose!r}")
        if len(set(crawler.purposes)) != len(crawler.purposes):
            problems.append(f"{crawler.token}: призначення повторюється")

        age = (now - crawler.last_verified_at).days
        if age < 0:
            problems.append(f"{crawler.token}: дата звірки в майбутньому")
        elif age > VERIFICATION_MAX_AGE_DAYS:
            problems.append(
                f"{crawler.token}: звірку не оновлювали {age} днів "
                f"(межа {VERIFICATION_MAX_AGE_DAYS})"
            )

    for retired in RETIRED_TOKENS:
        if retired in seen:
            problems.append(f"{retired}: одночасно в реєстрі й у знятих")

    return problems


__all__ = [
    "AI_CRAWLERS",
    "RETIRED_TOKENS",
    "VERIFICATION_MAX_AGE_DAYS",
    "AiCrawler",
    "CrawlerPurpose",
    "crawler_for",
    "registry_problems",
    "tokens",
]
