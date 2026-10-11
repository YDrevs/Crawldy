"""Покриття: чи репрезентує прочитане той живий сайт, який справді існує.

Питання не «скільки сторінок достатньо». Сайт-візитівка репрезентований
однією сторінкою повністю; односторінковий краул вікі на сотню статей не
репрезентований нічим. Тому рішення про site-level бал спирається не на
кількість прочитаного саму по собі, а на те, чи є ДОКАЗ живого вмісту,
якого ми не оглянули.

Два шари принципово різні й розділені:

* `CoverageEvidence` — самі факти: скільки сторінок прочитано, що каже
  robots, скільки адрес оголошує карта, скільки цілей ми не пробували.
  Жодного рішення тут немає.
* `assess()` — тлумачення цих фактів у один із трьох станів.

Три речі, які тут ніколи не відбуваються:

* 404/410 не зменшують покриття. Це оглянуті факти — сервер авторитетно
  сказав, що сторінки немає, і саме це живить `seo.broken_links`.
  Рахувати їх «недоступним вмістом» означало б тікати від оцінки тим
  успішніше, чим більше на сайті биті посилань (scikit-learn.org:
  11 сторінок прочитано без жодної помилки доступу, 14 биті посилання —
  і за це в нього забирали оцінку трьох напрямів).
* Вичерпаний бюджет краулу сам по собі не є доказом більшого сайту.
  Це наша власна межа, і вона пояснює, ЧОМУ відомі кандидати лишились
  непробуваними, — але не створює їх.
* Неперевірений надлишок карти сам по собі не притримує бал. Оголошення
  буває застарілим чи мертвим; надлишок стає доказом лише тоді, коли
  адреса підтверджена іншим сигналом — наприклад, збігається з живим
  непробуваним кандидатом із посилань.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import urlsplit

from app.audit.failures import blocks_evidence
from app.audit.types import SiteContext

# ── параметри політики ────────────────────────────────────────────────
# Скільки живих сторінок достатньо, щоб site-level бал мав на що
# спиратися. Слова навмисно НЕ входять у правило: на вибірці night3 вони
# змінювали рішення в 1.3% випадків, і саме там помилялися — каталоги й
# індексні сайти (jiuzhai.com: 25 сторінок, 135 слів, 176 посилань)
# малослівні за природою, а не через нашу сліпоту.
SUBSTANTIAL_PAGES = 3

# Коли збої доступу стають МАТЕРІАЛЬНИМ обмеженням. Один таймаут на 25
# прочитаних сторінок — шум вимірювання, а не обмеження: на night3 45%
# позначок припадало б на 1-2 збиті адреси (ubuntu.com: 25 прочитано,
# 1 збій). Частка робить правило незалежним від розміру бюджету.
MATERIAL_ACCESS_MIN = 3
MATERIAL_ACCESS_SHARE = 0.10

# Скільки чистих непробуваних кандидатів означає «є що читати ще».
# Семантику несе ФІЛЬТР, а не число: після відсіву медіа, службових дій
# і варіантів уже пробуваних адрес розподіл двогорбий — шум падає до
# нуля, справжні розділи сайту починаються від семи. Поріг лише
# підтверджує це.
UNTRIED_LIVE_MIN = 3

# ── фільтр кандидатів ─────────────────────────────────────────────────
# Це частина семантичного визначення, а не оптимізація. Без фільтра
# «непробувані кандидати» рахували зображення (splrr.com: усі 7 —
# jpg з wp-content), PDF-меню, кнопки поширення (?share=facebook) і
# схемні варіанти головної — тобто нашу неохайність, а не сайт.
_MEDIA = re.compile(
    r"\.(?:jpe?g|png|gif|webp|avif|svg|ico|pdf|zip|rar|7z|gz|mp[34]|avi|mov|webm"
    r"|woff2?|ttf|eot|docx?|xlsx?|pptx?|css|js|mjs|json|xml|txt)(?:$|\?)",
    re.I,
)
_ACTION_PARAMS = re.compile(
    r"[?&](?:action|veaction|oldid|printable|diff|share|print|replytocom)=", re.I
)
_SERVICE_PATHS = (
    "/special:",
    "/wp-login",
    "/wp-admin",
    "/login",
    "/signin",
    "/logout",
    "/cart",
    "/checkout",
)
# Адреси, які самі кажуть, що вмісту за ними немає.
_SELF_DECLARED_DEAD = ("redlink=1",)


def _normalized(url: str) -> str:
    """Одна форма для порівняння: без схеми, www і хвостового слеша.

    `http://selectbutton.jp` і `http://selectbutton.jp/` — та сама
    сторінка, і рахувати другу «непробуваним кандидатом» означало б
    вигадати сайту вміст із нашої ж адресної косметики.
    """
    parts = urlsplit(url)
    host = (parts.hostname or "").lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    query = f"?{parts.query}" if parts.query else ""
    return f"{host}{path}{query}"


def looks_like_content(url: str) -> bool:
    """Чи схожа адреса на сторінку з вмістом, а не на ресурс чи дію."""
    lowered = url.lower()
    if any(marker in lowered for marker in _SELF_DECLARED_DEAD):
        return False
    if any(marker in lowered for marker in _SERVICE_PATHS):
        return False
    if _MEDIA.search(lowered):
        return False
    return not _ACTION_PARAMS.search(lowered)


def clean_untried_candidates(ctx: SiteContext) -> list[str]:
    """Внутрішні адреси, які виглядають живими сторінками й не пробувані.

    Джерела — і статична розмітка, і рендер: адреса, яку домальовує
    скрипт, — такий самий кандидат. «Пробуване» — усе, що є в
    `ctx.pages` (включно з 4xx: ми там БУЛИ) та в `failed_urls`.
    """
    tried = {_normalized(page.url) for page in ctx.pages}
    tried.update(_normalized(url) for url in ctx.failed_urls)

    found: dict[str, str] = {}
    for page in ctx.ok_pages:
        for source in (page, ctx.as_seen(page)):
            for link in source.links:
                if not link.is_internal or not link.url:
                    continue
                if not looks_like_content(link.url):
                    continue
                key = _normalized(link.url)
                if key not in tried:
                    found.setdefault(key, link.url)
    return sorted(found.values())


# ── шар 1: факти ──────────────────────────────────────────────────────
@dataclass(slots=True)
class CoverageEvidence:
    """Що ми справді бачили. Жодних висновків."""

    analysed_pages: int
    access_failures: int
    observed_dead: int
    robots_restricted: bool
    sitemap_declared: int
    untried_live: int
    untried_examples: list[str] = field(default_factory=list)
    budget_exhausted: bool = False

    @property
    def attempted(self) -> int:
        """Скільки сторінок ми реально намагалися прочитати."""
        return self.analysed_pages + self.access_failures

    def to_json(self) -> dict[str, object]:
        return {
            "analysed_pages": self.analysed_pages,
            "access_failures": self.access_failures,
            "observed_dead": self.observed_dead,
            "robots_restricted": self.robots_restricted,
            "sitemap_declared": self.sitemap_declared,
            "untried_live": self.untried_live,
            "untried_examples": self.untried_examples[:5],
            "budget_exhausted": self.budget_exhausted,
        }


class CoverageState(StrEnum):
    SCORED = "scored"
    LIMITED = "scored_with_coverage_limitation"
    WITHHELD = "withheld"


# Причини — імена фактів, а не пороги. Клієнт читає «краул обмежено
# robots», а не «менше трьох сторінок»: внутрішні числа — не стандарти
# вебу, і подавати їх як такі не можна.
REASON_ROBOTS = "robots_restricted"
REASON_ACCESS = "access_failures"
REASON_UNTRIED = "untried_live_candidates"
REASON_SITEMAP = "sitemap_surplus_supported"
REASON_NO_MORE = "no_evidence_of_additional_live_content"


def collect_evidence(ctx: SiteContext, *, max_pages: int | None = None) -> CoverageEvidence:
    """Зібрати факти покриття із контексту. Без мережі."""
    access = sum(1 for reason in ctx.failed_urls.values() if blocks_evidence(reason))
    observed = sum(
        1
        for reason in ctx.failed_urls.values()
        if not blocks_evidence(reason) and str(reason).startswith(("HTTP 404", "HTTP 410"))
    )
    candidates = clean_untried_candidates(ctx)
    return CoverageEvidence(
        analysed_pages=len(ctx.ok_pages),
        access_failures=access,
        observed_dead=observed,
        robots_restricted=bool(ctx.robots.disallows_all),
        sitemap_declared=ctx.sitemap.url_count or 0,
        untried_live=len(candidates),
        untried_examples=candidates[:5],
        budget_exhausted=max_pages is not None and len(ctx.raw_pages) >= max_pages,
    )


def material_limitation(evidence: CoverageEvidence) -> list[str]:
    """Що МАТЕРІАЛЬНО завадило ширшому огляду.

    Пряма заборона в robots — властивість сайту, а не подія, тож вона
    матеріальна завжди. Збої доступу стають матеріальними від трьох і
    від десятої частки спроб: поодинокий таймаут — шум.
    """
    found = []
    if evidence.robots_restricted:
        found.append(REASON_ROBOTS)
    if (
        evidence.access_failures >= MATERIAL_ACCESS_MIN
        and evidence.access_failures / max(evidence.attempted, 1) >= MATERIAL_ACCESS_SHARE
    ):
        found.append(REASON_ACCESS)
    return found


def _evidence_of_more(evidence: CoverageEvidence) -> list[str]:
    """Докази живого вмісту, якого ми не оглянули. 404 сюди не входять."""
    found = []
    if evidence.robots_restricted:
        found.append(REASON_ROBOTS)
    if evidence.untried_live >= UNTRIED_LIVE_MIN:
        found.append(REASON_UNTRIED)
    if evidence.access_failures > 0:
        found.append(REASON_ACCESS)
    # Надлишок карти рахується лише ПІДТВЕРДЖЕНИЙ: оголошена адреса, що
    # збігається з живим кандидатом із посилань, уже полічена вище, а
    # сам-один рядок у карті буває застарілим чи мертвим. Робити з
    # одного неперевіреного рядка підставу забрати бал не можна — тож
    # окремої гілки для карти тут немає навмисно: вона лишається
    # контекстом у `CoverageEvidence`.
    return found


def assess(evidence: CoverageEvidence) -> tuple[CoverageState, list[str]]:
    """Три стани. Знахідки видимі в усіх — гейт стосується лише бала."""
    if evidence.analysed_pages >= SUBSTANTIAL_PAGES:
        material = material_limitation(evidence)
        if material:
            return CoverageState.LIMITED, material
        return CoverageState.SCORED, []
    more = _evidence_of_more(evidence)
    if more:
        return CoverageState.WITHHELD, more
    # Мало сторінок і жодного доказу, що є ще. Ми НЕ стверджуємо, що
    # сайт односторінковий, — лише що іншого живого вмісту не знайшли.
    return CoverageState.SCORED, [REASON_NO_MORE]


__all__ = [
    "MATERIAL_ACCESS_MIN",
    "MATERIAL_ACCESS_SHARE",
    "REASON_ACCESS",
    "REASON_NO_MORE",
    "REASON_ROBOTS",
    "REASON_SITEMAP",
    "REASON_UNTRIED",
    "SUBSTANTIAL_PAGES",
    "UNTRIED_LIVE_MIN",
    "CoverageEvidence",
    "CoverageState",
    "assess",
    "clean_untried_candidates",
    "collect_evidence",
    "looks_like_content",
    "material_limitation",
]
