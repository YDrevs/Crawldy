"""Семантичний шар: те, чого не можна перевірити правилом.

ЦЕ LEGACY-ШЛЯХ, І ВІН ВИМКНЕНИЙ. Не плутати з `app/enrich/`.

Різниця принципова, а не історична: цей шар стоїть ДО скора й може
створити знахідку (`llm.unstated_facts`), тобто змінити бал. Шар
збагачення (`app/enrich/`) стоїть ПІСЛЯ детерміністичної правди й не
може змінити ані знахідку, ані бал — там це властивість контракту, а не
обіцянка.

Стан: `LLM_ENABLED=false`, вмикати досі не можна. Окремий майбутній
експеримент має спершу порівняти цей шлях із детерміністичною правдою —
питання «чи не звинувачує модель сайт у тому, що на ньому є» лишається
відкритим. Спільного коду з `app/enrich/` немає навмисно: новий шлюз не
має жодного способу випадково активувати старий шлях.

Усі попередні модулі детерміністичні — на однаковому HTML вони дають
однаковий результат. Цей ні, і тому він відокремлений: його висновки
позначені окремо, він вимикається одним прапорцем, а без ключа API
аудит проходить без нього, як без PSI чи без браузера.

Друге обмеження — гроші. Кожен виклик коштує, тому бюджет на сторінки
тут не оптимізація, а частина контракту.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(slots=True)
class PageInsight:
    """Що модель зрозуміла зі сторінки.

    `summary` — не наш переказ, а те, як сторінку перекаже мовна модель
    клієнту, який спитає про цю компанію. Розбіжність між ним і тим, що
    компанія насправді робить, — і є проблема, яку правилом не спіймати.
    """

    url: str
    analysed: bool = False
    error: str | None = None
    summary: str = ""
    main_query: str = ""
    answers_query: bool = True
    missing: list[str] = field(default_factory=list)
    entities: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SiteBrief:
    """Стисле уявлення про сайт у цілому — основа для llms.txt."""

    analysed: bool = False
    error: str | None = None
    # Аналізу не було, бо шар вимкнули, а не бо він зламався. Причин
    # мовчання чотири — вимкнено / немає пакета / немає ключа / невідома
    # модель, — і лише перша є вибором. Прапорець, а не розбір рядка
    # `error`: зіставляти текст мовою — шукати халепи.
    disabled: bool = False
    name: str = ""
    tagline: str = ""
    description: str = ""
    offerings: list[str] = field(default_factory=list)
    audience: str = ""


@dataclass(slots=True)
class Fact:
    """Один факт про компанію: сказано його на сайті чи ні.

    `quote` і `page_url` — не прикраса: без них твердження «цього немає»
    неможливо перевірити, а саме воно потрапляє клієнту в звіт.
    """

    key: str
    stated: bool
    quote: str = ""
    page_url: str = ""


@dataclass(slots=True)
class SiteFacts:
    """Чи каже сайт те, без чого його не можна порекомендувати.

    Питання тут навмисно на рівні сайту, а не сторінки. Домашня сторінка
    Stripe теж не називає ціни — і це нормально, бо вони на /pricing.
    Проблема починається там, де факту немає ніде.

    `serves_an_area` і `sells_listed_items` — не оцінки, а спостереження
    про тип бізнесу. Рішення, що з ними робити, приймає чек: глобальному
    SaaS вулиця не потрібна, стоматології — потрібна.
    """

    analysed: bool = False
    error: str | None = None
    facts: list[Fact] = field(default_factory=list)
    serves_an_area: bool = False
    sells_listed_items: bool = False
    read_pages: list[str] = field(default_factory=list)

    def missing(self) -> list[Fact]:
        return [f for f in self.facts if not f.stated]


@dataclass(slots=True)
class OwnerNotes:
    """Те, що звіт для власника не може написати сам.

    Каталог повідомлень пише про проблему взагалі: «покупець іде до
    конкурента». Тут вона переказана про цей конкретний бізнес — а це
    єдине, чого шаблон не вміє.

    Нових фактів модель не додає: вона переказує наші ж знахідки. Звіт,
    у якому зʼявився факт без доказу, перестає бути аудитом.
    """

    analysed: bool = False
    error: str | None = None
    opening: str = ""
    notes: dict[str, str] = field(default_factory=dict)


class LlmAnalyst(Protocol):
    name: str

    async def read_page(self, url: str, title: str, text: str) -> PageInsight: ...

    async def brief(self, origin: str, pages: list[tuple[str, str]]) -> SiteBrief: ...

    async def facts(self, origin: str, pages: list[tuple[str, str, str]]) -> SiteFacts: ...

    async def owner_notes(
        self, business: str, band: str, problems: list[tuple[str, str]]
    ) -> OwnerNotes: ...


class NullAnalyst:
    """Каже, чому аналізу не було. Мовчазний пропуск гірший за відмову."""

    name = "null"

    def __init__(self, reason: str, *, disabled: bool = False) -> None:
        self.reason = reason
        self.disabled = disabled

    async def read_page(self, url: str, title: str, text: str) -> PageInsight:
        return PageInsight(url=url, analysed=False, error=self.reason)

    async def brief(self, origin: str, pages: list[tuple[str, str]]) -> SiteBrief:
        return SiteBrief(analysed=False, error=self.reason, disabled=self.disabled)

    async def facts(self, origin: str, pages: list[tuple[str, str, str]]) -> SiteFacts:
        return SiteFacts(analysed=False, error=self.reason)

    async def owner_notes(
        self, business: str, band: str, problems: list[tuple[str, str]]
    ) -> OwnerNotes:
        return OwnerNotes(analysed=False, error=self.reason)
