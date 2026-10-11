"""Текст внутрішніх посилань: що з нього видно, а що судити не можна.

## Це евристика, а не стандарт

Реєстру порожніх фраз ніхто не веде. Перелік нижче — наш, зібраний за
прикладами з документації Google, яка називає слабким текстом на зразок
«click here», «read more», «website» і «article». Тому він і лежить тут,
поруч із логікою, а не в `standards/`: там речі з зовнішнім джерелом і
датою звірки, і вдавати таке джерело для власної добірки було б
підробкою провенансу.

Приклад із документації — не універсальне правило. Ми не стверджуємо, що
загальний текст сам собою знижує позиції: Google цього не каже, а ми не
міряли. Твердження вужче й перевірне: за таким посиланням не видно, куди
воно веде.

## Що вважається текстом посилання

Google пише прямо: якщо посилання — це зображення, текстом посилання
працює його `alt`. Тому порожнім вважається лише те, у чого немає ані
видимого тексту, ані `alt` картинки всередині, ані доступної назви
(`aria-label`/`title`). Іконка з `aria-label` порожньою не є, і карати за
неї означало б карати за правильну розмітку.

## Де ми не судимо

**Меню, підвал, хлібні крихти.** `in_chrome` відсіює спільну обвʼязку
сайту: повторюване «Ціни» в шапці — осмислений орієнтир, а не дефект, і
знахідка про нього була б шумом на кожній сторінці.

**Мова, якої ми не знаємо.** Прогнати англійський перелік по німецькій
сторінці означало б вигадати знахідки. Якщо мову сторінки визначити не
вдалося або переліку для неї немає, лишається тільки те, що від мови не
залежить, — порожній текст.

**Довжина.** Порогу, який можна захистити, ми не знайшли, тож чека про
задовгий текст тут немає. Це записано як питання до фази калібрування, а
не зроблено навмання.

**Порожній текст.** Його теж немає в знахідках, і причина не в тому, що
він нешкідливий. `_extract_links` лишає **перше** посилання на кожну
адресу й відкидає решту, а найпоширеніша картка виглядає так:

    <a href="/product"><img …></a>
    <h3><a href="/product">Місячний пиріг</a></h3>

Текст стоїть у другому `<a>`, і до нас він не доходить узагалі. На
вибірці це давало 524 «порожніх» посилання на aldg.org і 240 на
crustula.com.ua — тобто третину й дві третини всіх контекстних. Це наша
сліпота, а не дефект сайтів, і випускати з неї знахідку означало б
звинувачувати клієнта у власній ваді. Кандидати рахуються (`unnamed`) і
записані до фази калібрування; полагодити це можна лише зміною дедуплікації
в екстракторі, а вона рухає пріоритет краулу й два ваговиті чеки.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.audit.link_evidence import Observation, Seen
from app.audit.logical_pages import normalize
from app.audit.standards import language_tags

# Фрази, за якими не видно, куди веде посилання. Мова → нормалізовані
# варіанти. Перелік свідомо консервативний: короткий, але осмислений
# текст («Ціни», «Доставка») сюди не потрапляє й потрапити не повинен.
GENERIC_ANCHORS: dict[str, frozenset[str]] = {
    "en": frozenset({
        "click here", "click", "here", "read more", "read on", "more", "learn more",
        "see more", "view more", "find out more", "continue reading", "this link",
        "link", "this page", "website", "web site", "article", "more info",
        "more information", "full story", "go", "go here",
    }),
    "uk": frozenset({
        "натисніть тут", "натискайте тут", "тут", "детальніше", "докладніше",
        "читати далі", "читати більше", "дізнатися більше", "дізнайтеся більше",
        "більше", "посилання", "за посиланням", "сайт", "стаття", "перейти",
        "читати", "детальна інформація",
    }),
    "de": frozenset({
        "hier", "hier klicken", "klicken sie hier", "mehr", "mehr erfahren",
        "weiterlesen", "weitere informationen", "mehr lesen", "mehr dazu", "link",
        "artikel", "webseite", "website", "zur website", "weiter",
    }),
    "es": frozenset({
        "aquí", "aqui", "haga clic aquí", "clic aquí", "pincha aquí", "más",
        "mas", "leer más", "saber más", "más información", "mas informacion",
        "ver más", "enlace", "artículo", "articulo", "sitio web", "seguir leyendo",
    }),
    "fr": frozenset({
        "ici", "cliquez ici", "cliquer ici", "en savoir plus", "plus",
        "lire la suite", "en lire plus", "voir plus", "lien", "article",
        "site web", "site", "continuer la lecture",
    }),
    "ru": frozenset({
        "здесь", "нажмите здесь", "кликните здесь", "тут", "подробнее",
        "подробности", "читать далее", "читать дальше", "узнать больше", "больше",
        "ссылка", "по ссылке", "сайт", "статья", "перейти", "далее",
    }),
}

# Хвостики, які нічого не додають: стрілки, три крапки, розділові знаки.
_TRIM = re.compile(r"^[\s\"'«»„“”\-–—>»›]+|[\s\"'«»„“”\-–—<«‹.!…:;,]+$")


class Reason(StrEnum):
    """Чому текст посилання не допомагає читачеві.

    Клас один. «Порожній текст» був другим і не пережив перевірки на
    живих сайтах — пояснення в докстрингу модуля.
    """

    # Текст є, але за ним не видно, куди веде посилання.
    GENERIC = "generic"


def canonical(text: str) -> str:
    """Текст посилання в порівнянну форму."""
    return _TRIM.sub("", " ".join((text or "").split()).lower())


@dataclass(frozen=True, slots=True)
class Weak:
    """Одне посилання, текст якого не пояснює призначення."""

    reason: Reason
    source: str
    target: str
    anchor: str
    seen_in: Seen
    language: str | None = None

    def as_evidence(self) -> dict[str, Any]:
        return {
            "from": self.source,
            "to": self.target,
            "anchor": self.anchor,
            "seen_in": self.seen_in.value,
            "language": self.language,
        }


@dataclass(slots=True)
class Analysis:
    """Слабкі тексти посилань і межі, у яких ми їх шукали."""

    weak: list[Weak] = field(default_factory=list)
    # Скільки контекстних посилань узагалі розглянуто.
    considered: int = 0
    # Скільки пропущено як меню/підвал — це не дефект, а обвʼязка сайту.
    in_chrome: int = 0
    # Посилання, у яких не знайшлося ані тексту, ані `alt`, ані доступної
    # назви. Знахідкою не стають: див. докстринг модуля — здебільшого це
    # картка, де текст лежить у сусідньому `<a>`, якого екстрактор не
    # зберігає. Число лишається для фази калібрування.
    unnamed: int = 0
    # Посилання, які ми пропустили, бо мову сторінки не встановили.
    pages_without_language: int = 0
    languages: set[str] = field(default_factory=set)

    def by_reason(self) -> dict[Reason, list[Weak]]:
        out: dict[Reason, list[Weak]] = {}
        for item in self.weak:
            out.setdefault(item.reason, []).append(item)
        return out

    def by_phrase(self, limit: int = 6, examples: int = 3) -> list[dict[str, Any]]:
        """Фрази, а не окремі посилання.

        Клієнтові тут одна робота на фразу, а не сорок робіт на сорок
        посилань. Скільки різних цілей ховається за тим самим текстом —
        головне число: саме воно каже, що за посиланням не видно, куди
        воно веде. Порядок сталий, урізане назване урізаним.
        """
        grouped: dict[str, list[Weak]] = {}
        for item in self.weak:
            grouped.setdefault(canonical(item.anchor), []).append(item)

        rows = []
        for phrase, items in grouped.items():
            targets = {i.target for i in items}
            shown = sorted(items, key=lambda i: (i.source, i.target))[:examples]
            row: dict[str, Any] = {
                "anchor": phrase,
                "links": len(items),
                "destinations": len(targets),
                "source_pages": len({i.source for i in items}),
                "language": items[0].language,
                "examples": [i.as_evidence() for i in shown],
            }
            if len(shown) < len(items):
                row["examples_truncated"] = True
            rows.append(row)

        rows.sort(key=lambda r: (-int(r["links"]), str(r["anchor"])))
        if len(rows) > limit:
            return rows[:limit]
        return rows

    def coverage(self) -> dict[str, Any]:
        return {
            "contextual_links": self.considered,
            "navigation_links_skipped": self.in_chrome,
            "links_without_any_text": self.unnamed,
            "pages_without_language": self.pages_without_language,
            "languages": sorted(self.languages),
        }


def _anchor_of(observation: Observation, link: Any) -> tuple[str, bool]:
    """Текст посилання за правилом Google і чи він узагалі є.

    Порядок джерел: видимий текст, потім `alt` картинки всередині, потім
    доступна назва. Перше непорожнє й перемагає.
    """
    for value in (observation.anchor, getattr(link, "image_alt", ""),
                  getattr(link, "label", "")):
        if (value or "").strip():
            return value.strip(), True
    return "", False


def _language_of(page: Any) -> str | None:
    """Базова мова сторінки або None, якщо впевненості немає."""
    tag = language_tags.parse(getattr(page, "lang", "") or "")
    return tag.language if tag.valid else None


def analyse(ctx: Any) -> Analysis:
    """Слабкі тексти внутрішніх посилань серед контекстних.

    Спостереження беруться з `link_evidence`: другого представлення
    «звідки → куди → яким текстом» у продукті бути не повинно.
    """
    from app.audit import link_evidence

    result = Analysis()
    by_page = {normalize(p.url): p for p in ctx.ok_pages}
    seen_pairs: set[tuple[str, str]] = set()

    for destination in link_evidence.collect(ctx).values():
        for observation in destination.observations:
            page = by_page.get(observation.source_key)
            if page is None:
                continue
            link = _link_on(ctx, page, observation.target_key)
            if link is None:
                continue
            if link.in_chrome:
                result.in_chrome += 1
                continue

            pair = (observation.source_key, observation.target_key)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            result.considered += 1

            text, present = _anchor_of(observation, link)
            if not present:
                result.unnamed += 1
                continue

            language = _language_of(page)
            if language is None:
                result.pages_without_language += 1
                continue
            result.languages.add(language)
            phrases = GENERIC_ANCHORS.get(language)
            if phrases is None:
                # Мова відома, переліку для неї немає. Мовчимо: вигадати
                # знахідку простіше, ніж її потім спростувати.
                continue
            if canonical(text) in phrases:
                result.weak.append(
                    Weak(reason=Reason.GENERIC, source=observation.source,
                         target=destination.url, anchor=text,
                         seen_in=observation.seen_in, language=language)
                )
    return result


def _link_on(ctx: Any, page: Any, target_key: str) -> Any:
    """Сам `LinkRef` — за ним лежать `in_chrome`, `alt` і доступна назва.

    Дивимось і у відповідь сервера, і у відрендерену версію: посилання,
    домальоване скриптом, теж треба полагодити.
    """
    render = ctx.renders.get(page.url) if hasattr(ctx, "renders") else None
    sources = [page]
    if render is not None and getattr(render, "signals", None) is not None:
        sources.append(render.signals)
    for signals in sources:
        for link in signals.links:
            if link.is_internal and normalize(link.url) == target_key:
                return link
    return None


def phrases_for(language: str | None) -> frozenset[str]:
    return GENERIC_ANCHORS.get(language or "", frozenset())


__all__ = ["GENERIC_ANCHORS", "Analysis", "Reason", "Weak", "analyse", "canonical",
           "phrases_for"]
