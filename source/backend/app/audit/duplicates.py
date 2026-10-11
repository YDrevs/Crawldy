"""Сторінки, вміст яких збігається, — і межа того, що з цього можна казати.

## Що вимірюється

Не «дублікатний вміст» у сенсі покарання. Google прямо пише, що
дублікати — звичайна річ і порушенням правил не є; він групує схожі
сторінки й обирає представника сам, і який саме — ми не знаємо й не
беремося вгадувати. Тут інше твердження, перевірне й вузьке: **ось ці
адреси віддають однаковий вміст**.

## Чому текст доводиться чистити

`PageSignals.text` — це вміст `<main>`, а якщо його немає, то всього
`<body>`. Меню, підвал і бічна панель туди потрапляють. Порівнювати таке
безпосередньо означало б оголосити дублікатами всі сторінки будь-якого
сайту з великою навігацією.

Тому шинґли, які трапляються більш ніж на `BOILERPLATE_SHARE` сторінок
сайту, вважаються обвʼязкою й відкидаються. Це не виділення головного
вмісту — це його наближення з наявних даних, і воно має відому межу
(див. нижче).

## Чому близькі дублікати не стали знахідкою

Вимірювання на 51 сайті вибірки: 24 пари з подібністю ≥ 0.7 після
чистки, і серед них — `fastapi.tiangolo.com/about/` проти
`/newsletter/` з 0.944. Це не дублікати: обидві сторінки майже порожні,
а їхній `text` — це бічна панель документації. Чистка її не впізнала,
бо сайт багатомовний: англійська панель трапляється лише на двох
сторінках із двадцяти чотирьох, тобто нижче будь-якого розумного порога.

Механізм узагальнюється на будь-який багатомовний сайт із великою
навігацією, а нижче 0.7 хибні спрацювання вже очевидні: у вибірці
`hubspot.com/services/…` проти сторінки біографії людини дало 0.62.

Отже, поки головний вміст не виділяється надійно, поріг подібності
означав би не «однакові сторінки», а «однакова навігація». Близька
подібність тут рахується й лишається в доказі як вимірювання; знахідкою
стають лише точні збіги, де порога немає взагалі.

## Складність

Порівнювати всі пари не можна: на 500 сторінках це 125 тисяч порівнянь.
Кандидати добираються MinHash + LSH — сигнатура фіксованої довжини на
сторінку, потім смуги в кошики, і рахуються лише пари, що потрапили в
один кошик. Час лінійний за кількістю сторінок, а не квадратичний.
"""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.audit import applicability
from app.audit.logical_pages import normalize
from app.audit.types import PageSignals

# Довжина шинґла у словах. Пʼять — звичний вибір для порівняння
# документів: коротші збігаються випадково, довші пропускають правки.
SHINGLE_WORDS = 5

# Частка сторінок сайту, з якої шинґл вважається обвʼязкою. Береться
# частка, а не число: на сайті з чотирьох сторінок і на сайті з двохсот
# «спільне для всіх» означає різні абсолютні величини.
BOILERPLATE_SHARE = 0.6

# Скільки власних шинґлів має лишитись після чистки, щоб про сторінку
# взагалі можна було щось сказати. Це не «мінімум слів для SEO», а межа,
# нижче якої вимірювання втрачає сенс: на вибірці саме вона відсіяла
# оболонку SPA, чиї чотири адреси віддають той самий каркас.
MIN_OWN_SHINGLES = 20

# MinHash: скільки перестановок і як їх розкласти на смуги. 64 = 16×4 —
# компроміс, за якого пара з подібністю близько 0.8 майже напевно
# потрапляє в спільний кошик, а зовсім різні сторінки — майже ніколи.
MINHASH_PERMS = 64
LSH_BANDS = 16
LSH_ROWS = MINHASH_PERMS // LSH_BANDS

_MERSENNE = (1 << 61) - 1


class Indexability(StrEnum):
    """Чи претендує сторінка на місце в пошуку."""

    INDEXABLE = "indexable"
    NOINDEX = "noindex"
    REDIRECTED = "redirected"
    NOT_FOR_SEARCH = "not_for_search"


class Consolidation(StrEnum):
    """Що сайт сам каже про те, яка з однакових адрес головна."""

    # Усі учасники вказують на одного — саме так це й має виглядати.
    CONSISTENT = "consistent"
    # Кожен називає головним себе.
    ALL_SELF = "all_self"
    # Учасники суперечать одне одному або вказують поза кластер.
    CONFLICTING = "conflicting"
    # Canonical не оголошено ніде.
    ABSENT = "absent"


def canonical_text(text: str) -> str:
    return " ".join((text or "").lower().split())


def shingles(text: str, size: int = SHINGLE_WORDS) -> set[str]:
    words = canonical_text(text).split()
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def _hash(value: str) -> int:
    return int.from_bytes(hashlib.blake2b(value.encode(), digest_size=8).digest(), "big")


def _minhash(items: set[str]) -> tuple[int, ...]:
    """Сигнатура сталої довжини. Детермінована: без випадкових зерен."""
    if not items:
        return tuple([0] * MINHASH_PERMS)
    hashes = [_hash(item) for item in items]
    signature = []
    for seed in range(MINHASH_PERMS):
        a = 2 * seed + 1
        b = seed * seed + 17
        signature.append(min(((a * h + b) % _MERSENNE) for h in hashes))
    return tuple(signature)


def jaccard(a: set[str], b: set[str]) -> float:
    union = len(a | b)
    return len(a & b) / union if union else 0.0


@dataclass(frozen=True, slots=True)
class Member:
    """Одна сторінка в кластері однакового вмісту."""

    url: str
    key: str
    indexability: Indexability
    canonical: str | None
    # Скільки шинґлів лишилось після чистки від обвʼязки.
    own_shingles: int
    # Як ми читали сторінку: відповідь сервера чи вже відрендерена.
    representation: str
    similarity: float = 1.0

    def as_evidence(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "indexability": self.indexability.value,
            "canonical": self.canonical,
            "similarity": round(self.similarity, 3),
            "own_shingles": self.own_shingles,
            "read_as": self.representation,
        }


@dataclass(slots=True)
class Cluster:
    """Група адрес з однаковим вмістом."""

    members: list[Member]
    exact: bool = True

    @property
    def representative(self) -> Member:
        """Представник для показу — і правило, за яким його обрано.

        Спершу той, на кого вказують canonical інших: це вибір самого
        сайту. Якщо такого немає — найкоротша нормалізована адреса,
        далі за абеткою. Жодного стосунку до того, що обере пошук: цього
        ми не знаємо.
        """
        targets = {normalize(m.canonical) for m in self.members if m.canonical}
        named = [m for m in self.members if m.key in targets]
        pool = named or list(self.members)
        return min(pool, key=lambda m: (len(m.key), m.key))

    @property
    def consolidation(self) -> Consolidation:
        canonicals = [m.canonical for m in self.members]
        if all(c is None for c in canonicals):
            return Consolidation.ABSENT
        keys = {m.key for m in self.members}
        targets = {normalize(c) for c in canonicals if c}
        if len(targets) == 1 and targets <= keys:
            only = next(iter(targets))
            if all(c is not None for c in canonicals):
                # Усі вказали на одного учасника — консолідація свідома.
                return Consolidation.CONSISTENT if len(keys) > 1 or only else Consolidation.ALL_SELF
        if all(c is not None and normalize(c) == m.key
               for c, m in zip(canonicals, self.members, strict=True)):
            return Consolidation.ALL_SELF
        return Consolidation.CONFLICTING

    @property
    def indexable_members(self) -> list[Member]:
        return [m for m in self.members if m.indexability is Indexability.INDEXABLE]

    def as_evidence(self, limit: int = 6) -> dict[str, Any]:
        shown = sorted(self.members, key=lambda m: m.key)[:limit]
        evidence: dict[str, Any] = {
            "cluster": self.identifier,
            "size": len(self.members),
            "exact": self.exact,
            "representative": self.representative.url,
            "consolidation": self.consolidation.value,
            "indexable_members": len(self.indexable_members),
            "members": [m.as_evidence() for m in shown],
            "members_shown": len(shown),
        }
        if len(shown) < len(self.members):
            evidence["members_truncated"] = True
        return evidence

    @property
    def identifier(self) -> str:
        """Сталий ідентифікатор: два прогони дають той самий рядок."""
        joined = "|".join(sorted(m.key for m in self.members))
        return hashlib.blake2b(joined.encode(), digest_size=6).hexdigest()


@dataclass(slots=True)
class Analysis:
    """Кластери однакового вмісту й межі цього вимірювання."""

    clusters: list[Cluster] = field(default_factory=list)
    # Пари з високою подібністю, які знахідкою не стають. Вимірювання
    # для фази калібрування — див. docstring модуля.
    near: list[tuple[str, str, float]] = field(default_factory=list)
    compared: int = 0
    candidate_pairs: int = 0
    boilerplate_shingles: int = 0
    skipped_thin: int = 0
    # Сторінок, у яких тексту немає взагалі: висновку про них не робимо.
    without_text: int = 0

    def coverage(self) -> dict[str, Any]:
        return {
            "pages_compared": self.compared,
            "candidate_pairs": self.candidate_pairs,
            "boilerplate_shingles": self.boilerplate_shingles,
            "pages_below_content_floor": self.skipped_thin,
            "pages_without_text": self.without_text,
        }


def _indexability(ctx: Any, page: PageSignals) -> Indexability:
    if page.redirected_from and normalize(page.redirected_from) != normalize(page.url):
        return Indexability.REDIRECTED
    if "noindex" in (ctx.as_seen(page).meta_robots or "").lower():
        return Indexability.NOINDEX
    # Службовість питається в застосовності, а не в типу сторінки: сторінка
    # з формою воронки, яку сайт індексує, службовою не є, і однаковий вміст
    # на двох таких адресах лишається звичайним дублікатом.
    if applicability.service_shaped(ctx, page):
        return Indexability.NOT_FOR_SEARCH
    return Indexability.INDEXABLE


def _hreflang_pairs(ctx: Any) -> set[frozenset[str]]:
    """Пари, які сайт сам оголосив мовними версіями одна одної.

    Регіональні варіанти однією мовою законно бувають майже однакові, і
    Google прямо радить розводити їх canonical разом із hreflang. Такі
    пари в кластери не потрапляють: це налаштування, а не недогляд.
    """
    from app.audit import hreflang

    out: set[frozenset[str]] = set()
    site = hreflang.collect(ctx)
    for declaration in site.declaring:
        for annotation in declaration.annotations:
            if annotation.target != declaration.url:
                out.add(frozenset({declaration.url, annotation.target}))
    return out


def analyse(ctx: Any) -> Analysis:
    """Кластери однакового вмісту серед прочитаних сторінок.

    Порівнюємо окремо відповіді сервера й окремо відрендерені сторінки.
    Змішувати не можна: відповідь однієї сторінки проти DOM іншої — це
    порівняння двох різних речей, і збіг чи розбіжність там пояснюються
    рендером, а не сайтом. Бюджет рендеру малий, тож більшу групу завжди
    складають відповіді; відрендерена група лише додає до неї.
    """
    result = Analysis()
    response = [(p, p.text or "") for p in ctx.ok_pages]
    rendered = [
        (p, (ctx.as_seen(p).text or ""))
        for p in ctx.ok_pages
        if ctx.as_seen(p) is not p
    ]
    result.without_text = sum(1 for _p, text in response if not text.strip())

    seen_clusters: set[str] = set()
    for label, group in (("response", response), ("rendered", rendered)):
        for cluster in _clusters_in(ctx, group, label, result):
            if cluster.identifier in seen_clusters:
                continue
            seen_clusters.add(cluster.identifier)
            result.clusters.append(cluster)
    result.clusters.sort(key=lambda c: (-len(c.members), c.identifier))
    return result


def _clusters_in(
    ctx: Any,
    group: list[tuple[PageSignals, str]],
    label: str,
    result: Analysis,
) -> list[Cluster]:
    """Кластери всередині однієї репрезентації."""
    readable = [(page, text, label) for page, text in group if text.strip()]
    if len(readable) < 2:
        return []

    sets = {normalize(p.url): shingles(text) for p, text, _ in readable}

    # Обвʼязка рахується за РІЗНИМИ вмістами, а не за сторінками. Інакше
    # дублікати стирають самі себе: три однакові сторінки з чотирьох —
    # це 75% сторінок, тож їхній спільний текст виглядав би шаблоном і
    # зникав саме тоді, коли він і є знахідкою. Однаковий вміст рахуємо
    # один раз, і тоді «спільне для багатьох» знову означає меню й підвал.
    distinct: dict[str, set[str]] = {}
    for page, text, _label in readable:
        distinct.setdefault(
            hashlib.sha256(canonical_text(text).encode()).hexdigest(),
            sets[normalize(page.url)],
        )
    counts = Counter(s for value in distinct.values() for s in value)
    cutoff = max(3, int(len(distinct) * BOILERPLATE_SHARE))
    boilerplate = {s for s, n in counts.items() if n >= cutoff}
    result.boilerplate_shingles = max(result.boilerplate_shingles, len(boilerplate))
    own = {key: value - boilerplate for key, value in sets.items()}

    pairs = _hreflang_pairs(ctx)
    usable: dict[str, tuple[PageSignals, str, str]] = {}
    for page, text, representation in readable:
        key = normalize(page.url)
        if len(own[key]) < MIN_OWN_SHINGLES:
            if label == "response":
                result.skipped_thin += 1
            continue
        usable[key] = (page, text, representation)
    result.compared = max(result.compared, len(usable))

    def member(key: str, similarity: float = 1.0) -> Member:
        page, _text, representation = usable[key]
        seen = ctx.as_seen(page)
        return Member(
            url=page.url,
            key=key,
            indexability=_indexability(ctx, page),
            canonical=(seen.canonical or None),
            own_shingles=len(own[key]),
            representation=representation,
            similarity=similarity,
        )

    # ── точні збіги: порога немає, тож і судити нема чого ──────────────
    by_hash: dict[str, list[str]] = defaultdict(list)
    for key, (_page, text, _r) in usable.items():
        by_hash[hashlib.sha256(canonical_text(text).encode()).hexdigest()].append(key)

    found: list[Cluster] = []
    for keys in by_hash.values():
        if len(keys) < 2:
            continue
        if any(frozenset({a, b}) in pairs for a in keys for b in keys if a != b):
            continue
        found.append(Cluster(members=[member(k) for k in sorted(keys)], exact=True))

    # ── близька подібність: рахуємо, але знахідкою не робимо ───────────
    result.near.extend(_near_pairs(own, usable, pairs, result))
    return found


def _near_pairs(
    own: dict[str, set[str]],
    usable: dict[str, tuple[PageSignals, str, str]],
    pairs: set[frozenset[str]],
    result: Analysis,
) -> list[tuple[str, str, float]]:
    """Кандидати через MinHash + LSH, потім точний Жаккар лише на них."""
    buckets: dict[tuple[int, tuple[int, ...]], list[str]] = defaultdict(list)
    for key in usable:
        signature = _minhash(own[key])
        for band in range(LSH_BANDS):
            slice_ = signature[band * LSH_ROWS : (band + 1) * LSH_ROWS]
            buckets[(band, slice_)].append(key)

    candidates: set[frozenset[str]] = set()
    for members in buckets.values():
        if len(members) < 2:
            continue
        for i, a in enumerate(members):
            for b in members[i + 1 :]:
                candidates.add(frozenset({a, b}))

    result.candidate_pairs += len(candidates)
    found = []
    for pair in candidates:
        a, b = sorted(pair)
        if frozenset({a, b}) in pairs:
            continue
        score = jaccard(own[a], own[b])
        if score >= 0.7:
            found.append((a, b, round(score, 3)))
    return sorted(found, key=lambda row: (-row[2], row[0], row[1]))


__all__ = [
    "BOILERPLATE_SHARE",
    "MIN_OWN_SHINGLES",
    "Analysis",
    "Cluster",
    "Consolidation",
    "Indexability",
    "Member",
    "analyse",
    "canonical_text",
    "jaccard",
    "shingles",
]
