"""Сторінка «про нас»: одне рішення для всіх, хто про неї питає (E-10).

Питання просте — чи є на сайті сторінка, яка каже, хто за ним стоїть, —
і саме тому воно роками вирішувалося неправильно. Доти три споживачі
(`llm.about_page`, вибір сторінки для `ai.schema.organization`,
`llm.brand_consistency`) кожен тримав власний список слів і шукав його
ПІДРЯДКОМ у адресі й заголовку: `/about-cookies` ставав сторінкою про
компанію, стаття про чужу команду — теж, `/de/ueber-uns` не ставав нею
ніколи, а посилання в меню, ціль якого ми не відкривали, зараховувалось
за прочитану сторінку.

Модель контракту (`contracts/e10-signals.json`) розводить два роди
ознак, і розводить їх суворо:

**Первинні** — ті, що ВИРАЖАЮТЬ намір «розповісти про себе»: точний
маршрут (P1), заголовок чи H1 (P2), пункт меню (P3), розмітка
`AboutPage` (P4). Кандидатом сторінка стає лише від них.

**Підтверджувальні** — те, що часто буває ПОРУЧ із такою сторінкою, але
є і всюди інде: розмітка Organization (C1), назва компанії (C2), «ми» й
«наша» (C3), слова про місію та історію (C4), згадка команди (C5), збіг
підрядка (C6). Вони посилюють кандидата й ніколи не створюють його. Це
не оптимізація, а суть: головна сторінка з Organization і «ми» — це
головна сторінка, а не сторінка про компанію.

**Довжини тут немає.** Претензія екзистенційна — сторінка є чи її немає, —
і коротка, але справжня сторінка «про нас» проходить. Що НЕ проходить,
мусить не проходити з доказом: не прочитали, оболонка без вмісту
(`is_content_shell` — той самий предикат, що й у всього двигуна), стіна
входу, заглушка перенаправлення. Жодного «замало слів» — ні прямо, ні
через кількість абзаців, полів чи бали якості.

Функція `detect` чиста: та сама відповідь для того самого контексту,
скільки б разів і в якому порядку її не питали. Оркестратор, застосовність,
чек і вибір сторінки для розмітки кличуть її кожен окремо й отримують
одне рішення — без спільного стану, який хтось міг би забути оновити.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.audit.applicability import ClaimVerdict, Coverage
from app.audit.enums import DegradationKind, Module
from app.audit.logical_pages import normalize
from app.audit.page_kinds import _route_chunks
from app.audit.site_scope import same_site
from app.audit.standards.schema_entities import is_identity_type
from app.audit.types import Degradation, PageSignals, SiteContext
from app.audit.vocab import words as _words
from app.audit.vocab.enums import ContentLanguage

CHECK = "llm.about_page"
NOTICE_UNREAD = "notice.about_page.candidate_unread"
NOTICE_UNREADABLE = "notice.about_page.candidate_unreadable"

# Стільки ж прикладів, скільки в доказі застосовності G4b: доказ має
# читатися, а не бути переліком сайту.
EXAMPLES = 5

# Ідентифікатори ознак — рівно ті, що в контракті. Вони йдуть у доказ і в
# тести, тож перейменування зламало б порівняння з фікстурами.
P1, P2, P3, P4 = ("P1_route_token", "P2_title_or_h1_intent", "P3_chrome_anchor",
                  "P4_aboutpage_schema")
C1, C2, C3, C4, C5, C6 = ("C1_organization_jsonld", "C2_organisation_name",
                          "C3_first_person_prose", "C4_company_prose", "C5_team_mention",
                          "C6_substring")

# Причини, з яких кандидат НЕ є доказом. Кожна — спостереження, і жодна —
# міра довжини. Документ помилки (4xx/5xx) — це невдале читання, і
# повідомлення називає його статус; окремої «ідентичності документа
# помилки» для сторінки з кодом 200 двигун не має: перевірка мʼяких 404
# (`tech.soft_404`) описує сайт, а не цю сторінку, і вигадувати її тут
# означало б назвати спостереженням те, чого не спостерігали.
FAILED_READ = "failed_read"
CONTENT_SHELL = "content_shell"
LOGIN_WALL = "login_wall"
REDIRECT_PLACEHOLDER = "redirect_placeholder"

# Те саме для читача — але його мовою. Причина йде в повідомлення слагом, а
# складається в речення при показі (`report.builder._reason_params` →
# `coverage.reason.<slug>`), рівно як причини покриття. Написати сюди готовий
# рядок означало б віддати клієнтові німецькою наше внутрішнє слово.
REASON_SLUG = {
    FAILED_READ: "about_page_failed_read",
    CONTENT_SHELL: "about_page_content_shell",
    LOGIN_WALL: "about_page_login_wall",
    REDIRECT_PLACEHOLDER: "about_page_redirect_placeholder",
}

# ── Важіль відкату ─────────────────────────────────────────────────────
# Канонічний відкат G5a (`contracts/groups.json → rollback`): «чек повертається
# до старого помічника; словник і ключі повідомлень прибираються». Словник і
# є важелем: без нього рішення немає, `detect` віддає None, і кожен, хто
# питає — оркестратор, застосовність, обидва чеки, — повертається до
# поведінки G4b без жодної правки в собі. Той самий устрій, що й
# `COMPATIBILITY_MODE` у застосовності: стан читається з канонічної
# таблиці, а не з окремого прапорця, який хтось міг би забути перемкнути.
ROUTE_TOKENS: dict[ContentLanguage, frozenset[str]] = getattr(_words, "ABOUT_ROUTE_TOKENS", {})
PHRASES: dict[ContentLanguage, tuple[str, ...]] = getattr(_words, "ABOUT_PHRASES", {})
BRAND_PREFIXES: dict[ContentLanguage, tuple[str, ...]] = getattr(
    _words, "ABOUT_BRAND_PREFIXES", {})
AVAILABLE = bool(ROUTE_TOKENS and PHRASES and BRAND_PREFIXES)

# Слова підтверджувальних ознак — з контракту, дослівно. Вони ніколи не
# вирішують, тож повнота списків не є питанням коректності.
_FIRST_PERSON = frozenset({"we", "our", "ми", "наша", "wir", "unser", "nous", "notre",
                           "nosotros", "nuestra", "мы"})
_COMPANY_PROSE = frozenset({"founded", "mission", "history", "values"})
_TEAM_MENTION = frozenset({"team", "company"})
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)


def _fold(text: str | None) -> str:
    """Регістр і форма Юнікоду — так само, як у словників маршрутів."""
    return unicodedata.normalize("NFC", (text or "").strip()).casefold()


def _begins_with(text: str, phrase: str) -> bool:
    """«Дорівнює або починається з фрази» — на межі слова, не підрядком.

    `about us` має збігатися з «About us — Crawldy», але не з «About
    useful things»: після фрази мусить стояти кінець рядка або не-літера.
    """
    if not text or not phrase:
        return False
    if text == phrase:
        return True
    if not text.startswith(phrase):
        return False
    return not text[len(phrase)].isalnum()


def _all_tokens() -> frozenset[str]:
    return frozenset(token for tokens in ROUTE_TOKENS.values() for token in tokens)


def _all_phrases() -> tuple[str, ...]:
    return tuple(_fold(p) for phrases in PHRASES.values() for p in phrases)


def _all_prefixes() -> tuple[str, ...]:
    return tuple(_fold(p) for prefixes in BRAND_PREFIXES.values() for p in prefixes)


def _h1(page: PageSignals) -> str:
    for level, text in page.headings:
        if level == 1:
            return text
    return ""


def brand_names(ctx: SiteContext) -> frozenset[str]:
    """Як сайт зве себе: факти сайту й вузли ідентичності в розмітці.

    Потрібно для форми «About <brand>»: без бренду «About cookies» став би
    сторінкою про компанію, а з ним — ні. Джерела навмисно лише ті, що не
    залежать від порядку обходу: назва головної сторінки — ні, бо «головна»
    для двигуна є перша сторінка, що відповіла, і доказ, який від цього
    залежить, не можна порівняти із самим собою між прогонами.
    """
    names: set[str] = set()
    known = getattr(ctx, "known", None)
    organization = _fold(getattr(known, "organization", "") or "")
    if organization:
        names.add(organization)
    for page in ctx.ok_pages:
        for node in _walk(page.jsonld):
            raw = node.get("@type")
            types = ([raw] if isinstance(raw, str)
                     else [t for t in (raw or []) if isinstance(t, str)])
            if any(is_identity_type(t) for t in types):
                name = _fold(str(node.get("name") or ""))
                if name:
                    names.add(name)
    return frozenset(names)


def _walk(nodes: Iterable[Any]) -> Iterable[dict[str, Any]]:
    """Усі словники розмітки, включно з вкладеними — так само, як `types_on`."""
    stack = list(nodes)
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            yield node
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)


def _jsonld_types(page: PageSignals) -> set[str]:
    found: set[str] = set()
    for node in _walk(page.jsonld):
        raw = node.get("@type")
        if isinstance(raw, str):
            found.add(raw)
        elif isinstance(raw, list):
            found.update(t for t in raw if isinstance(t, str))
    return found


def _intent_in(text: str, brands: frozenset[str]) -> bool:
    """Чи виражає заголовок або H1 намір «про нас» — за словником, не підрядком."""
    folded = _fold(text)
    if not folded:
        return False
    if any(_begins_with(folded, phrase) for phrase in _all_phrases()):
        return True
    return any(_begins_with(folded, f"{prefix} {brand}")
               for prefix in _all_prefixes() for brand in brands)


def _route_token(url: str, locales: Iterable[str]) -> str | None:
    """P1: останній сегмент шляху без мовного префікса дорівнює слову словника.

    Знімання префікса — те саме, що в G4a (`_route_chunks`): рівно один
    провідний сегмент, і лише коли сайт оголосив цю мову. Рівність
    сегмента, ніколи не підрядок. Розширення файлу відкидається так само,
    як у словах шляху (`page_kinds._words_of`): `/about.html` — той самий
    маршрут, що й `/about`, а `/about-cookies` — ні.
    """
    chunks, _locale, _basis = _route_chunks(url, locales)
    if not chunks:
        return None
    last = chunks[-1].rsplit(".", 1)[0]
    return last if last in _all_tokens() else None


def _substring_only(url: str, locales: Iterable[str]) -> bool:
    """C6: слово словника всередині довшого сегмента (`about-cookies`)."""
    chunks, _locale, _basis = _route_chunks(url, locales)
    tokens = _all_tokens()
    return any(token in chunk and chunk != token for chunk in chunks for token in tokens)


@dataclass(frozen=True, slots=True)
class AboutCandidate:
    """Одна адреса, про яку політика щось сказала.

    `anchor` — чим сайт на неї вказав: текст пункту меню, а для адреси,
    відомої лише з карти сайту, — слово маршруту.
    """

    url: str
    primary: tuple[str, ...]
    corroborating: tuple[str, ...]
    read: bool
    status_code: int | None
    readable: bool
    substitute: str | None
    conclusive: bool
    anchor: str = ""

    def as_evidence(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "primary": list(self.primary),
            "corroborating": list(self.corroborating),
            "read": self.read,
            "status": self.status_code,
            "readable_main_content": self.readable,
            "substitute_document": self.substitute,
            "conclusive": self.conclusive,
            **({"anchor": self.anchor} if self.anchor else {}),
        }


@dataclass(frozen=True, slots=True)
class AboutEvidence:
    """Рішення разом із тим, на чому воно тримається."""

    verdict: ClaimVerdict
    coverage: Coverage
    candidate: bool
    selected: str | None
    candidates: tuple[AboutCandidate, ...]
    also_seen: tuple[AboutCandidate, ...]
    unread: tuple[AboutCandidate, ...]
    corroborating_seen: tuple[str, ...]
    reason: str
    notice: tuple[str, dict[str, Any]] | None
    locales: tuple[str, ...] = ()

    @property
    def conclusive(self) -> bool:
        return self.verdict is ClaimVerdict.PASS

    @property
    def finding(self) -> bool:
        return self.verdict is ClaimVerdict.FAIL

    @property
    def module_partial(self) -> bool:
        return self.verdict is ClaimVerdict.NO_VERDICT

    @property
    def unread_applicable(self) -> int:
        """Скільки застосовного не прочитано — лише поки претензія не закрита."""
        return 0 if self.conclusive else len(self.unread)

    @property
    def unreadable(self) -> int:
        return sum(1 for c in self.candidates if c.read is False or c.substitute is not None)

    @property
    def selected_candidate(self) -> AboutCandidate | None:
        for candidate in (*self.candidates, *self.unread):
            if candidate.url == self.selected:
                return candidate
        return None

    def as_evidence(self) -> dict[str, Any]:
        chosen = self.selected_candidate
        return {
            "verdict": self.verdict.value,
            "coverage": self.coverage.value,
            "candidate": self.candidate,
            "selected": self.selected,
            "primary": list(chosen.primary) if chosen else [],
            "corroborating": (list(chosen.corroborating) if chosen
                              else list(self.corroborating_seen)),
            "reason": self.reason,
            "substitute_document": chosen.substitute if chosen else None,
            "status": chosen.status_code if chosen else None,
            "notice": {"key": self.notice[0], "params": self.notice[1]} if self.notice else None,
            "also_seen": [c.as_evidence() for c in self.also_seen[:EXAMPLES]],
            "unread_candidates": [c.url for c in self.unread[:EXAMPLES]],
            "candidates_total": len(self.candidates) + len(self.unread),
            "module_partial": self.module_partial,
            "finding": self.finding,
            "locales": list(self.locales),
        }


def _signals(page: PageSignals, locales: tuple[str, ...], brands: frozenset[str],
             chrome_targets: dict[str, str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Які ознаки несе ця сторінка: первинні окремо, підтверджувальні окремо."""
    primary: list[str] = []
    corroborating: list[str] = []
    if _route_token(page.url, locales):
        primary.append(P1)
    if _intent_in(page.title or "", brands) or _intent_in(_h1(page), brands):
        primary.append(P2)
    if normalize(page.url) in chrome_targets:
        primary.append(P3)
    types = _jsonld_types(page)
    if "AboutPage" in types:
        primary.append(P4)
    if any(is_identity_type(t) and t not in ("Person", "WebSite") for t in types):
        corroborating.append(C1)
    haystack = _fold(f"{page.title or ''} {_h1(page)} {page.text}")
    words = set(_WORD.findall(haystack))
    if brands and any(brand in haystack for brand in brands if brand):
        corroborating.append(C2)
    if words & _FIRST_PERSON:
        corroborating.append(C3)
    if words & _COMPANY_PROSE:
        corroborating.append(C4)
    if words & _TEAM_MENTION:
        corroborating.append(C5)
    if _substring_only(page.url, locales):
        corroborating.append(C6)
    return tuple(primary), tuple(corroborating)


def _substitute(page: PageSignals, read: bool, has_intent: bool) -> str | None:
    """Чому прочитаний документ — не сторінка «про нас». Лише спостереження."""
    if not read:
        return FAILED_READ
    if page.is_content_shell:
        return CONTENT_SHELL
    # Стіна входу: форма з паролем замість вмісту, і жодного наміру «про нас»
    # у заголовку чи H1. Сам по собі пароль не вирок — на сторінці про
    # компанію може стояти форма входу для клієнтів; вирішує ВІДСУТНІСТЬ
    # наміру поруч із нею.
    if not has_intent and any(form.has_password_field for form in page.forms):
        return LOGIN_WALL
    # Заглушка перенаправлення: документ, який лише відсилає далі. Так само —
    # `meta refresh` разом із відсутністю наміру, а не окремо.
    if not has_intent and page.meta_refresh:
        return REDIRECT_PLACEHOLDER
    return None


def _chrome_targets(ctx: SiteContext) -> dict[str, str]:
    """Усі внутрішні цілі меню й підвалу: адреса → підпис."""
    targets: dict[str, str] = {}
    for page in ctx.ok_pages:
        for link in page.links:
            if not link.in_chrome or not link.is_internal:
                continue
            label = link.anchor or link.label or link.image_alt
            key = normalize(link.url)
            # Один підпис на ціль, і той самий незалежно від порядку
            # сторінок: найменший за рядком, а не перший зустрінутий.
            targets[key] = min(label, targets.get(key, label))
    return targets


def _chrome_about_targets(chrome: dict[str, str], brands: frozenset[str]) -> dict[str, str]:
    """Цілі пунктів меню, чий текст — фраза «про нас» (P3): адреса → текст пункту."""
    return {key: label for key, label in chrome.items() if _intent_in(label, brands)}


def detect(ctx: SiteContext) -> AboutEvidence | None:
    """Рішення про сторінку «про нас» для цього контексту. Чиста функція.

    None — лише коли словника немає (важіль відкату): тоді рішення не
    існує, і споживачі поводяться так, як до цього детектора.
    """
    if not AVAILABLE:
        return None
    locales = tuple(ctx.declared_locales())
    brands = brand_names(ctx)
    chrome = _chrome_targets(ctx)
    chrome_targets = _chrome_about_targets(chrome, brands)
    fetched = {normalize(page.url): page for page in ctx.pages}
    rendered = {normalize(url) for url in getattr(ctx, "renders", {}) or {}}

    candidates: list[AboutCandidate] = []
    corroborating_seen: set[str] = set()
    for key, page in sorted(fetched.items()):
        primary, corroborating = _signals(page, locales, brands, chrome_targets)
        corroborating_seen.update(corroborating)
        if not primary:
            continue
        read = bool(page.status_code and 200 <= page.status_code < 300) or key in rendered
        has_intent = P2 in primary
        substitute = _substitute(page, read, has_intent)
        readable = read and bool(page.text.strip())
        candidates.append(AboutCandidate(
            url=page.url, primary=primary, corroborating=corroborating, read=read,
            status_code=page.status_code, readable=readable, substitute=substitute,
            conclusive=read and readable and substitute is None,
            anchor=chrome_targets.get(key, ""),
        ))

    # Кандидати, яких ми знаємо, але не відкривали — «relevant coverage»
    # контракту: ціль меню з фразою «про нас» (P3), ціль меню чи адреса карти
    # сайту з маршрутом «про нас» (P1). Саме вони роблять покриття неповним,
    # а не будь-яке непрочитане посилання. Непрочитаний кандидат несе
    # найсильнішу з побачених ознак: підпис самого сайту (P3), інакше маршрут.
    unread: list[AboutCandidate] = []
    for key, label in sorted(chrome.items()):
        if key in fetched:
            continue
        token = _route_token(key, locales)
        if key in chrome_targets:
            known_by: tuple[str, ...] = (P3,)
        elif token:
            known_by = (P1,)
        else:
            continue
        unread.append(AboutCandidate(url=key, primary=known_by, corroborating=(), read=False,
                                     status_code=None, readable=False, substitute=None,
                                     conclusive=False, anchor=label or token or ""))
    sitemap = getattr(getattr(ctx, "sitemap", None), "urls", None) or []
    for url in sitemap:
        # Карта може називати чужий хост, і чужа сторінка «про нас» не є
        # нашою. Питання «це той самий сайт» має в двигуні одну відповідь
        # (`site_scope.same_site`), і тут береться саме вона.
        if not same_site(url, ctx.origin):
            continue
        key = normalize(url)
        if key in fetched or any(c.url == key for c in unread):
            continue
        token = _route_token(url, locales)
        if token:
            unread.append(AboutCandidate(url=key, primary=(P1,), corroborating=(), read=False,
                                         status_code=None, readable=False, substitute=None,
                                         conclusive=False, anchor=token))

    def order(candidate: AboutCandidate) -> tuple[int, str]:
        chunks, _l, _b = _route_chunks(candidate.url, locales)
        return (len(chunks), candidate.url)

    conclusive = sorted((c for c in candidates if c.conclusive), key=order)
    if conclusive:
        chosen = conclusive[0]
        siblings = tuple(sorted((c for c in (*candidates, *unread) if c.url != chosen.url),
                                key=order))
        return AboutEvidence(
            verdict=ClaimVerdict.PASS, coverage=Coverage.COMPLETE, candidate=True,
            selected=chosen.url, candidates=tuple(sorted(candidates, key=order)),
            also_seen=siblings, unread=tuple(sorted(unread, key=order)),
            corroborating_seen=tuple(sorted(corroborating_seen)), reason="conclusive",
            notice=None, locales=locales,
        )
    if unread:
        chosen = sorted(unread, key=order)[0]
        return AboutEvidence(
            verdict=ClaimVerdict.NO_VERDICT, coverage=Coverage.PARTIAL, candidate=True,
            selected=chosen.url, candidates=tuple(sorted(candidates, key=order)),
            also_seen=(), unread=tuple(sorted(unread, key=order)),
            corroborating_seen=tuple(sorted(corroborating_seen)), reason="candidate_unread",
            notice=(NOTICE_UNREAD, {"url": chosen.url, "anchor": chosen.anchor}),
            locales=locales,
        )
    if candidates:
        chosen = sorted(candidates, key=order)[0]
        return AboutEvidence(
            verdict=ClaimVerdict.NO_VERDICT, coverage=Coverage.NOT_MEASURED, candidate=True,
            selected=chosen.url, candidates=tuple(sorted(candidates, key=order)),
            also_seen=(), unread=(), corroborating_seen=tuple(sorted(corroborating_seen)),
            reason=chosen.substitute or "unreadable",
            notice=(NOTICE_UNREADABLE,
                    {"url": chosen.url,
                     "reasons": [REASON_SLUG.get(chosen.substitute or "",
                                                 "about_page_failed_read")],
                     "status": chosen.status_code}),
            locales=locales,
        )
    return AboutEvidence(
        verdict=ClaimVerdict.FAIL, coverage=Coverage.COMPLETE, candidate=False, selected=None,
        candidates=(), also_seen=(), unread=(),
        corroborating_seen=tuple(sorted(corroborating_seen)), reason="no_candidate",
        notice=None, locales=locales,
    )


def degradation(evidence: AboutEvidence | None) -> Degradation | None:
    """Прогалина для `missing_data` — лише для станів без вердикту."""
    if evidence is None or evidence.notice is None:
        return None
    key, params = evidence.notice
    return Degradation(
        scope=CHECK,
        kind=DegradationKind.PARTIAL_DATA,
        reason=f"сторінка «про нас» не оцінена: {evidence.reason} ({params.get('url')})",
        affected_modules=[Module.LLM_VISIBILITY],
        reason_key=key,
        reason_params=dict(params),
    )


def selected_pages(ctx: SiteContext) -> list[PageSignals]:
    """Сторінка «про нас» для тих, хто судить розмітку, — лише коли претензію закрито.

    Без вердикту споживачі судять саму головну (контракт, §4): сторінка,
    якої не прочитали або яка виявилась заглушкою, не може бути місцем для
    розмітки організації — ми не бачили, що на ній є.
    """
    evidence = detect(ctx)
    if evidence is None or not evidence.conclusive:
        return []
    return [page for page in ctx.ok_pages if page.url == evidence.selected]


__all__ = [
    "AVAILABLE",
    "CHECK",
    "NOTICE_UNREAD",
    "NOTICE_UNREADABLE",
    "AboutCandidate",
    "AboutEvidence",
    "brand_names",
    "degradation",
    "detect",
    "selected_pages",
]
