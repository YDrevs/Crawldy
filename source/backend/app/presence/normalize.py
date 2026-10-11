"""Тлумачення відповіді: одне для всіх провайдерів.

Адаптер віддає механіку (текст, адреси, чи був пошук) — тут вона стає
твердженнями: бренд згадано, домен процитовано, сторінку процитовано,
включено в рекомендацію. Правила спільні навмисно: те, що вважається
«згадкою» в Anthropic, мусить вважатися згадкою і в OpenAI, інакше
метрики порівнюють провайдерів різними лінійками.

Власний домен звіряється спільним правилом сайту (`site_scope`) — не
префіксом рядка: www, схема й мітки імені вже вирішені там одним
способом на весь продукт.
"""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from app.audit.site_scope import same_site
from app.presence.contracts import (
    LIST_CATEGORIES,
    Mode,
    ObservationRecord,
    ObservationStatus,
    PresencePrompt,
    ProviderAnswer,
)

# Версія правил тлумачення. Зміна збігу аліасів, фільтра адрес чи
# виявлення прямих посилань — нова версія: два спостереження з різними
# версіями тлумачились різними лінійками, і запис мусить це казати.
NORMALIZE_VERSION = "n2"

# Скільки символів відповіді зберігається назавжди. Повний текст живе в
# raw за політикою утримання; уривка досить, щоб людина впізнала контекст.
_EXCERPT_CHARS = 500

# Цитати приймаються лише за безпечними схемами: javascript:/data: у
# клієнтському інтерфейсі — не джерело, а вектор.
_SAFE_SCHEMES = frozenset({"http", "https"})

# Адреси прямо в тексті відповіді — «пряме посилання», окреме від цитати.
_URL_IN_TEXT = re.compile(r"https?://[^\s<>()\[\]{}\"']+", re.IGNORECASE)


def safe_cited_urls(urls: list[str]) -> list[str]:
    """Лише http/https-адреси; решта не потрапляє в довічний запис."""
    out: list[str] = []
    for url in urls:
        scheme = urlsplit(url).scheme.lower()
        if scheme in _SAFE_SCHEMES and url not in out:
            out.append(url)
    return out


def observed_domain(url: str) -> str | None:
    """Нормалізований хост цитати: нижній регістр, без www і крапки."""
    host = urlsplit(url).hostname
    if not host:
        return None
    host = host.lower().rstrip(".")
    return host.removeprefix("www.") or None


def _fold(text: str) -> str:
    """Юнікод-нормалізація перед збігом: NFKC + casefold.

    «Сrustula» з кириличною С і повноширинні латинські форми мусять
    збігатися з брендом так само, як звичайний регістр.
    """
    return unicodedata.normalize("NFKC", text).casefold()


def _alias_patterns(aliases: tuple[str, ...]) -> list[re.Pattern[str]]:
    # Межі слова через lookaround по \w: працюють і для кирилиці, і для
    # брендів із дефісом; голий пошук підрядка бреше (урок `cheaper`/`heap`).
    return [
        re.compile(rf"(?<!\w){re.escape(_fold(a))}(?!\w)")
        for a in aliases if a
    ]


def interpret(
    answer: ProviderAnswer,
    *,
    prompt: PresencePrompt,
    prompt_set_version: str,
    provider: str,
    tool_version: str,
    run_index: int,
    country: str | None,
    origin: str,
    brand_aliases: tuple[str, ...],
    cost_usd: float,
    mode: Mode = Mode.NATURAL,
    sent_text: str = "",
    retries: int = 0,
    duration_ms: int = 0,
) -> ObservationRecord:
    """Повний запис спостереження з успішної відповіді."""
    folded_text = _fold(answer.text)
    matched: str | None = None
    for pattern, alias in zip(
        _alias_patterns(brand_aliases), [a for a in brand_aliases if a], strict=True
    ):
        if pattern.search(folded_text):
            matched = alias
            break

    cited_urls = safe_cited_urls(answer.cited_urls)
    pages_cited = [u for u in cited_urls if same_site(u, origin)]
    domains = []
    for url in cited_urls:
        host = observed_domain(url)
        if host and host not in domains:
            domains.append(host)

    # Пряме посилання: власна адреса стоїть у ТЕКСТІ відповіді. Це не
    # цитата провайдера — і твердження в метриках у нього окреме.
    linked_urls = [
        u for u in _URL_IN_TEXT.findall(answer.text)
        if same_site(u.rstrip(".,;:!?"), origin)
    ]

    # «Згадано» — суворо про текст відповіді; цитата без назви бренду
    # лишається цитатою. «Включено» на промптах-переліках визнає обидва
    # шляхи: перелік може посилатися на сайт, не називаючи бренду.
    mentioned = matched is not None
    included = mentioned or bool(pages_cited)
    return ObservationRecord(
        provider=provider,
        model=answer.model,
        tool_version=tool_version,
        prompt=prompt,
        prompt_set_version=prompt_set_version,
        run_index=run_index,
        country=country,
        status=ObservationStatus.OK,
        mode=mode,
        sent_text=sent_text or prompt.text,
        searched=answer.searched,
        search_queries=list(answer.search_queries),
        answer_excerpt=answer.text[:_EXCERPT_CHARS],
        cited_urls=cited_urls,
        cited_domains=domains,
        brand_mentioned=mentioned,
        matched_alias=matched,
        domain_cited=bool(pages_cited),
        pages_cited=pages_cited,
        domain_linked=bool(linked_urls),
        linked_urls=linked_urls[:20],
        # «Включено в рекомендацію» — твердження лише про промпти-переліки.
        recommended=(included if prompt.category in LIST_CATEGORIES else None),
        observed_domains=domains,
        usage=answer.usage,
        cost_usd=cost_usd,
        retries=retries,
        duration_ms=duration_ms,
        normalize_version=NORMALIZE_VERSION,
        raw=answer.raw,
    )


def failure(
    status: ObservationStatus,
    detail: str,
    *,
    prompt: PresencePrompt,
    prompt_set_version: str,
    provider: str,
    model: str,
    tool_version: str,
    run_index: int,
    country: str | None,
    cost_usd: float = 0.0,
    mode: Mode = Mode.NATURAL,
    retries: int = 0,
    duration_ms: int = 0,
) -> ObservationRecord:
    """Збійна клітинка: не спостережено, а не нульова присутність."""
    return ObservationRecord(
        provider=provider,
        model=model,
        tool_version=tool_version,
        prompt=prompt,
        prompt_set_version=prompt_set_version,
        run_index=run_index,
        country=country,
        status=status,
        mode=mode,
        error=detail[:500],
        cost_usd=cost_usd,
        retries=retries,
        duration_ms=duration_ms,
        normalize_version=NORMALIZE_VERSION,
    )
