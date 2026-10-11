"""Заявлені мовні версії сторінок: три механізми, одна модель.

## Чому механізмів три і жоден не головніший

Google приймає `hreflang` у трьох місцях — `<link>` у HTML, заголовок
HTTP `Link` і `xhtml:link` у карті сайту — і прямо називає їх
рівноцінними. Практично це означає, що перевіряти можна тільки їхнє
обʼєднання: сайт, який зробив усе правильно в карті, при перевірці
самого HTML виглядає так, ніби не оголосив нічого, і отримує зауваження
за чужу помилку.

Тому модель одна, а джерело — поле анотації. Джерело потрібне не для
скора, а для поради: «виправте значення `de-DE`» без вказівки, у якому
з трьох місць воно лежить, відправляє клієнта шукати навмання.

## Що тут є і чого свідомо немає

Тут — збір, нормалізація й факти, які видно з даних: чи є самопосилання,
чи відповіли взаємністю прочитані нами адреси, чи не конфліктують
оголошення між собою. Тут немає жодного судження про серйозність і
жодного рядка для клієнта: це робота чеків і каталогу.

Взаємність — єдине місце, де межа нашого краулу впливає на висновок.
Сторінка B може посилатися назад ідеально, а ми її просто не відкривали;
тому `Reciprocity` окремо несе, скільки цілей ми змогли перевірити, і
мовчання про решту — не «все гаразд», а «не дивилися».
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from urllib.parse import urljoin

from app.audit import logical_pages, page_kinds
from app.audit.standards import language_tags
from app.audit.standards.language_tags import LanguageTag
from app.audit.types import HreflangRef, PageSignals


class Source(StrEnum):
    """Де саме сайт оголосив версію. Для поради, не для оцінки."""

    HTML = "html"
    HTTP_HEADER = "http_header"
    SITEMAP = "sitemap"


# Порядок для показу: спершу те, що клієнт побачить, відкривши сторінку.
_SOURCE_ORDER = (Source.HTML, Source.HTTP_HEADER, Source.SITEMAP)


@dataclass(frozen=True, slots=True)
class Annotation:
    """Одна заявлена версія після нормалізації.

    Та сама пара «мова + адреса», оголошена і в HTML, і в карті, — це
    одна анотація з двома джерелами, а не дві. Інакше кожен сайт, який
    свідомо дублює оголошення (а так роблять, щоб пережити зміну CMS),
    виглядав би сайтом із подвійними оголошеннями.
    """

    tag: LanguageTag
    # Нормалізована абсолютна адреса цілі.
    target: str
    # Як воно було написано: у доказ іде саме це.
    raw_href: str
    sources: tuple[Source, ...]
    # Google вимагає повну адресу. Відносну ми розберемо, але запамʼятаємо.
    relative: bool = False

    @property
    def key(self) -> str:
        """Чим анотація відрізняється від іншої: значення й ціль."""
        return f"{self.tag.normalized or self.tag.raw}|{self.target}"

    def as_evidence(self) -> dict[str, Any]:
        return {
            **self.tag.as_evidence(),
            "href": self.raw_href,
            "target": self.target,
            "sources": [s.value for s in self.sources],
            "relative": self.relative,
        }


@dataclass(frozen=True, slots=True)
class Declaration:
    """Усе, що одна сторінка заявила про свої мовні версії."""

    url: str
    annotations: tuple[Annotation, ...] = ()

    @property
    def declared(self) -> bool:
        return bool(self.annotations)

    @property
    def sources(self) -> tuple[Source, ...]:
        used = {s for a in self.annotations for s in a.sources}
        return tuple(s for s in _SOURCE_ORDER if s in used)

    @property
    def invalid(self) -> tuple[Annotation, ...]:
        return tuple(a for a in self.annotations if not a.tag.valid)

    @property
    def targets(self) -> tuple[str, ...]:
        """Куди сторінка посилається, крім себе самої."""
        return tuple(dict.fromkeys(a.target for a in self.annotations if a.target != self.url))

    def self_reference(self) -> Annotation | None:
        """Анотація, що вказує на саму сторінку.

        `x-default` нею не рахується: він означає «сюди, якщо нічого не
        збіглося», а не «ця сторінка такою мовою». Сторінка, у якої з
        оголошень лише `x-default` на себе, самопосилання не має.
        """
        for a in self.annotations:
            if a.target == self.url and not a.tag.x_default:
                return a
        return None

    def as_evidence(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "declared_versions": len(self.annotations),
            "sources": [s.value for s in self.sources],
            "annotations": [a.as_evidence() for a in self.annotations],
        }


@dataclass(frozen=True, slots=True)
class Conflict:
    """Два оголошення, які не можуть бути правдою одночасно."""

    # duplicate | x_default
    kind: str
    value: str
    targets: tuple[str, ...]

    def as_evidence(self) -> dict[str, Any]:
        return {"kind": self.kind, "value": self.value, "targets": list(self.targets)}


@dataclass(frozen=True, slots=True)
class Reciprocity:
    """Чи відповіли взаємністю ті цілі, які ми справді відкривали."""

    # Цілі, на які ми дивилися й повернення не знайшли.
    missing: tuple[str, ...] = ()
    # Скільки цілей вдалося перевірити й скільки їх оголошено всього.
    checked: int = 0
    declared: int = 0

    @property
    def complete(self) -> bool:
        """Чи бачили ми всі цілі. Від цього залежить формулювання."""
        return self.checked == self.declared

    def as_evidence(self) -> dict[str, Any]:
        return {
            "missing_return": list(self.missing),
            "targets_checked": self.checked,
            "targets_declared": self.declared,
            # Твердження про решту ми не робимо — і кажемо про це прямо.
            "coverage_complete": self.complete,
        }


@dataclass(slots=True)
class Map:
    """Оголошення всього сайту й похідні від них факти."""

    by_page: dict[str, Declaration] = field(default_factory=dict)
    # Скільки адрес анотовано в карті сайту цілком, а не в нашому зрізі.
    sitemap_annotated: int = 0

    @property
    def declaring(self) -> list[Declaration]:
        return [d for d in self.by_page.values() if d.declared]

    @property
    def used(self) -> bool:
        """Чи оголосив сайт хоч щось хоч десь.

        Одномовний сайт не оголошує нічого, і це не дефект. Уся родина
        чеків мовчить, поки ця відповідь `False`.
        """
        return bool(self.declaring) or self.sitemap_annotated > 0

    def declaration(self, url: str) -> Declaration | None:
        return self.by_page.get(logical_pages.normalize(url))

    def conflicts(self, declaration: Declaration) -> list[Conflict]:
        """Одне значення, дві різні цілі — сайт сам собі суперечить.

        Google у такому разі ігнорує весь набір анотацій сторінки, тож
        це не косметика: сторінка лишається без hreflang узагалі.
        """
        targets: dict[str, list[str]] = defaultdict(list)
        for a in declaration.annotations:
            if not a.tag.valid:
                continue
            targets[a.tag.normalized].append(a.target)
        found = []
        for value, seen in targets.items():
            unique = tuple(dict.fromkeys(seen))
            if len(unique) > 1:
                kind = "x_default" if value == language_tags.X_DEFAULT else "duplicate"
                found.append(Conflict(kind=kind, value=value, targets=unique))
        return found

    def reciprocity(self, declaration: Declaration) -> Reciprocity:
        """Взаємність — лише про цілі, які ми відкривали самі.

        Google вимагає зворотного посилання, але «його немає» ми можемо
        стверджувати тільки про сторінку, яку прочитали. Про решту
        мовчимо, і `checked` проти `declared` каже, наскільки це мовчання
        широке.
        """
        missing = []
        checked = 0
        for target in declaration.targets:
            other = self.by_page.get(target)
            if other is None:
                continue
            checked += 1
            if declaration.url not in {a.target for a in other.annotations}:
                missing.append(target)
        return Reciprocity(
            missing=tuple(missing),
            checked=checked,
            declared=len(declaration.targets),
        )


def _annotations(page_url: str, refs: list[HreflangRef]) -> tuple[Annotation, ...]:
    """Сирі посилання → нормалізовані анотації зі злитими джерелами."""
    merged: dict[str, dict[str, Any]] = {}
    for ref in refs:
        href = (ref.href or "").strip()
        if not href:
            continue
        tag = language_tags.parse(ref.value)
        absolute = urljoin(page_url, href)
        target = logical_pages.normalize(absolute)
        key = f"{tag.normalized or tag.raw}|{target}"
        entry = merged.setdefault(
            key,
            {
                "tag": tag,
                "target": target,
                "raw_href": href,
                "sources": [],
                "relative": absolute != href,
            },
        )
        source = Source(ref.source)
        if source not in entry["sources"]:
            entry["sources"].append(source)
    return tuple(
        Annotation(
            tag=e["tag"],
            target=e["target"],
            raw_href=e["raw_href"],
            sources=tuple(s for s in _SOURCE_ORDER if s in e["sources"]),
            relative=bool(e["relative"]),
        )
        for e in merged.values()
    )


def _refs_for(ctx: Any, page: PageSignals) -> list[HreflangRef]:
    """Три джерела однієї сторінки в один список.

    Статична відповідь дає HTML і заголовок; відрендерена — лише HTML,
    бо синтетичний `FetchResult` рендеру заголовків не має. Обидві
    беруться навмисно: Google виконує JS, тож анотація, дописана
    скриптом, для нього існує, а заголовок при цьому нікуди не зникає.
    """
    refs = list(page.hreflang)
    rendered = ctx.rendered(page.url) if hasattr(ctx, "rendered") else None
    if rendered is not None:
        refs.extend(rendered.hreflang)
    sitemap = getattr(ctx, "sitemap", None)
    if sitemap is not None:
        refs.extend(sitemap.hreflang.get(page.url, []))
    return refs


def collect(ctx: Any) -> Map:
    """Оголошення всіх прочитаних сторінок в одну модель."""
    sitemap = getattr(ctx, "sitemap", None)
    result = Map(sitemap_annotated=getattr(sitemap, "hreflang_url_count", 0) or 0)
    for page in ctx.ok_pages:
        url = logical_pages.normalize(page.url)
        annotations = _annotations(page.url, _refs_for(ctx, page))
        result.by_page[url] = Declaration(url=url, annotations=annotations)
    return result


# Як називається джерело оголошення в доказі. Рядки стабільні: на них
# спираються звіт і леджер A/B, а не лише читач.
_EVIDENCE_BY_SOURCE = {
    Source.HTML.value: "hreflang_html",
    Source.HTTP_HEADER.value: "hreflang_header",
    Source.SITEMAP.value: "sitemap_alternate",
}


def _supported_language(value: str) -> str | None:
    """Базова мова тега — якщо тег дійсний і мова є мовою запуску.

    `de-DE` → `de`: регіон не робить іншої мови, і сайт, який оголосив
    `de-AT` та `de-CH`, оголосив німецьку один раз, а не двічі.

    Не є оголошенням: `x-default` (це «сюди, якщо нічого не збіглося», а не
    мова), недійсний тег (оголошення, якого не прийме Google, не доказ і для
    нас) і мова поза межами запуску — словника для неї в нас однаково немає.
    """
    tag = language_tags.parse(value)
    if not tag.valid or tag.x_default or tag.language is None:
        return None
    return tag.language if tag.language in page_kinds.SUPPORTED_LOCALES else None


def declared_locale_evidence(ctx: Any) -> dict[str, list[str]]:
    """Мова → чим саме сайт її оголосив.

    Три джерела, усі рівноцінні й усі вже зібрані краулом: значення
    `<html lang>` прочитаних сторінок, анотації hreflang (HTML і заголовок
    `Link`) і мовні альтернативи в карті сайту.

    Сегмент шляху джерелом НЕ є і бути не може. Дві літери в адресі — це
    здогад, а E-12 будується на тому, що сайт сказав про себе сам.
    """
    found: dict[str, set[str]] = defaultdict(set)

    for page in list(getattr(ctx, "ok_pages", []) or []):
        rendered = ctx.rendered(page.url) if hasattr(ctx, "rendered") else None
        for version in (page, rendered):
            if version is None:
                continue
            code = _supported_language(getattr(version, "lang", None) or "")
            if code:
                found[code].add("html_lang")
        for ref in _refs_for(ctx, page):
            code = _supported_language(ref.value)
            if code:
                found[code].add(_EVIDENCE_BY_SOURCE.get(ref.source, "hreflang_html"))

    # Карта сайту оголошує й за ті сторінки, яких ми не відкривали. Це
    # оголошення сайту, а не наша вибірка, тож воно рахується цілком.
    sitemap = getattr(ctx, "sitemap", None)
    for refs in (getattr(sitemap, "hreflang", None) or {}).values():
        for ref in refs:
            code = _supported_language(ref.value)
            if code:
                found[code].add("sitemap_alternate")

    return {code: sorted(found[code]) for code in sorted(found)}


def declared_locales(ctx: Any) -> list[str]:
    """Оголошені мови запуску, за абеткою.

    Порядок стабільний навмисно: список їде у знімок і в докази, а знімок,
    порядок якого залежить від обходу словника, не порівняти з ним самим.
    """
    return sorted(declared_locale_evidence(ctx))


__all__ = [
    "Annotation",
    "Conflict",
    "Declaration",
    "Map",
    "Reciprocity",
    "Source",
    "collect",
    "declared_locale_evidence",
    "declared_locales",
]
