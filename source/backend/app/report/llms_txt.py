"""Чернетка llms.txt за структурою сайту.

Не чек, а артефакт: файл, який клієнт кладе до себе на сайт. Чек лише
каже, що llms.txt немає; цінність — віддати готовий.

Структура береться з краулу, не з моделі. Заголовки розділів, перелік
сторінок і їхні описи — усе це вже зібрано, і для них LLM не потрібен.
Модель додає лише те, чого в HTML немає: одну фразу про те, чим
компанія займається. Без ключа файл виходить трохи сухішим, але
цілком робочим — це і є причина розділяти ці два джерела.
"""

from __future__ import annotations

from urllib.parse import urlparse

from app.audit.demo_content import detect as detect_demo_content
from app.audit.page_kinds import PageType
from app.audit.types import PageSignals, SiteContext

# Скільки сторінок перелічувати. llms.txt — це карта для моделі, а не
# повний sitemap: надто довгий список змушує її читати все підряд.
MAX_LINKS = 40
MAX_PER_SECTION = 12

# Розділи за першим сегментом шляху. Порядок навмисний: спершу те, що
# пояснює компанію, потім те, що продає, потім довідкове.
SECTION_ORDER = (
    ("about", "About"),
    ("services", "Services"),
    ("products", "Products"),
    ("solutions", "Solutions"),
    ("pricing", "Pricing"),
    ("docs", "Documentation"),
    ("blog", "Blog"),
    ("news", "News"),
    ("cases", "Case studies"),
    ("contact", "Contact"),
)
# «Other» доречне лише поруч з іншими розділами. Коли решти немає —
# а так виглядає кожен сайт, де всі сторінки лежать у корені, — це
# просто сторінки сайту, і називати їх «іншими» означає збрехати
# читачеві про їхню вагу.
OTHER_SECTION = "Other pages"
ONLY_SECTION = "Pages"


def build_llms_txt(ctx: SiteContext) -> str:
    """Готовий вміст llms.txt. Порожній рядок, якщо описувати нічого."""
    pages = [p for p in ctx.content_pages if p.title and _worth_showing(ctx, p)]
    if not pages:
        return ""

    home = ctx.home
    brief = ctx.brief
    name = (brief.name if brief and brief.analysed and brief.name else "") or _fallback_name(
        home, ctx.origin
    )

    lines = [f"# {name}", ""]

    summary = _summary(ctx, home)
    if summary:
        lines += [f"> {summary}", ""]

    if brief is not None and brief.analysed and brief.offerings:
        lines.append("## What we do")
        lines += [f"- {item}" for item in brief.offerings[:8]]
        lines.append("")

    for heading, section_pages in _sections(pages, ctx.origin):
        lines.append(f"## {heading}")
        for page in section_pages:
            lines.append(_link(page))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _worth_showing(ctx: SiteContext, page: PageSignals) -> bool:
    """Чи варто вести модель на цю сторінку.

    Файл, який клієнт кладе на сайт, не має вести ШІ ні на службові
    сторінки конструктора, ні на демо-команду з шаблону. На
    smartkp.com.ua генератор вносив у llms.txt Mark Liuw і Angela Kwang:
    ми не просто не помічали чужий шаблон, а складали з нього карту сайту
    для моделей.
    """
    kind = ctx.type_of(page)
    if kind in _NOT_FOR_LLMS:
        return False
    return page.url not in _demo_urls(ctx)


# Службове, юридичне й архіви моделі не потрібні: вони нічого не
# стверджують про компанію.
_NOT_FOR_LLMS = frozenset({PageType.SYSTEM, PageType.LEGAL, PageType.ARCHIVE})


def _demo_urls(ctx: SiteContext) -> set[str]:
    found = detect_demo_content(ctx)
    return {*found.template_pages, *found.foreign_person_pages}


def _summary(ctx: SiteContext, home: PageSignals | None) -> str:
    """Одна фраза про компанію: від моделі, інакше з опису головної.

    meta description головної — не ідеальна заміна, але вона написана
    людиною про цей самий сайт, і це краще за вигадану фразу.
    """
    brief = ctx.brief
    if brief is not None and brief.analysed:
        return brief.tagline or brief.description
    if home is not None and home.meta_description:
        return home.meta_description
    return ""


def _fallback_name(home: PageSignals | None, origin: str) -> str:
    """Назва з title головної: усе до першого роздільника.

    «Acme — доставка квітів» дає «Acme»; хвіст після тире майже завжди
    слоган або опис, а не назва.
    """
    if home is not None and home.title:
        for separator in ("|", "—", "–", " - ", "::", "»"):
            if separator in home.title:
                head = home.title.split(separator)[0].strip()
                if head:
                    return head
        return home.title.strip()
    return urlparse(origin).netloc or origin


def _sections(pages: list[PageSignals], origin: str) -> list[tuple[str, list[PageSignals]]]:
    buckets: dict[str, list[PageSignals]] = {}
    for page in pages:
        buckets.setdefault(_section_key(page, origin), []).append(page)

    ordered: list[tuple[str, list[PageSignals]]] = []
    budget = MAX_LINKS

    # Головна окремим розділом і першою: з неї модель починає читати.
    for key, heading in (("", "Main"), *SECTION_ORDER):
        found = buckets.pop(key, [])
        if not found:
            continue
        chunk = found[: min(MAX_PER_SECTION, budget)]
        if chunk:
            ordered.append((heading, chunk))
            budget -= len(chunk)

    leftovers = [page for rest in buckets.values() for page in rest]
    if leftovers and budget > 0:
        named = [entry for entry in ordered if entry[0] != "Main"]
        heading = OTHER_SECTION if named else ONLY_SECTION
        ordered.append((heading, leftovers[:budget]))
    return ordered


def _section_key(page: PageSignals, origin: str) -> str:
    path = urlparse(page.url).path.strip("/")
    if not path:
        return ""
    first = path.split("/")[0].lower()
    known = {key for key, _ in SECTION_ORDER}
    return first if first in known else "other"


def _link(page: PageSignals) -> str:
    """Рядок llms.txt: назва, адреса й пояснення, навіщо туди йти."""
    title = (page.title or page.url).strip()
    note = (page.meta_description or "").strip()
    if note:
        return f"- [{title}]({page.url}): {note}"
    return f"- [{title}]({page.url})"


__all__ = ["build_llms_txt"]
