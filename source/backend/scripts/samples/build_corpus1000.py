"""Складання `corpus1000.yaml` з перевірених кандидатів.

## Ланцюг

    harvest_corpus.py  → кандидати (Wikidata P856: чий це сайт, який клас, яка країна)
    probe_corpus.py    → перевірка (чи живий, куди веде, на чому зроблений)
    build_corpus1000.py → відбір рівно 1000 і запис YAML із походженням

Кожна мітка в корпусі приходить з одного з двох місць: із джерела
(сегмент, країна) або з побаченої відповіді (теґи, мова). Третього
джерела — здогаду за виглядом домену — тут немає, і це не стилістична
вимога: одна вигадана мітка робить увесь зріз за нею брехнею.

## Відбір

Квоти на сегменти нерівні навмисно. Рівні купи виглядали б охайно й
брехали б про веб: локальних сайтів, шкіл і газет у природі значно
більше, ніж документації розробника.

Усередині сегмента порядок — сталий хеш канонічного хоста. Не алфавіт
(він збирає докупи один домен верхнього рівня) і не порядок джерела (він
кладе першими найпомітніших). Стеля на країну не дає жодному регіону
зʼїсти сегмент.

## Що робить `curated`

Wikidata майже не знає сайтів документації та вебзастосунків: у них
рідко буває стаття. Такі записи додані переліком і **перевірені тим
самим probe**, а в полі `source` стоїть `curated`, щоб зріз за джерелом
було видно й можна було переглянути.
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Запускається і як модуль, і як скрипт: у другому випадку корінь репо
# сам собою в `sys.path` не потрапляє.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.samples.segments import (
    CLASS_TO_SEGMENT,
    MAPPING_VERSION,
    NOTES,
    QUOTAS,
    segment_for,
)

CORPUS_SCHEMA = "crawldy.corpus/1"

# Скільки записів у якому сегменті. Сума — рівно 1000.

# Стеля на КЛАС усередині сегмента. Без неї «освіта» стає музеями й
# бібліотеками: у пулі Wikidata їх найбільше, і сегмент успадкував би
# перекіс джерела замість того, щоб описувати інституційні сайти взагалі.
CLASS_CAP_PER_SEGMENT = 34

# Не більше стількох сайтів однієї країни в одному сегменті. Без стелі
# природний розподіл Wikidata віддає сегмент США й Британії.
COUNTRY_CAP_PER_SEGMENT = 15

# Сайти, яких Wikidata не знає: документація, вебзастосунки, кілька
# випадків із димової вибірки. Перевіряються тим самим probe.
CURATED: tuple[tuple[str, str, str], ...] = (
    # (url, segment, note-hint)
    ("https://auditlensapp.com", "saas", "вебзастосунок із клієнтським рендерингом"),
    ("https://dronehub.ai", "corporate", "B2B-корпоративний сайт"),
    ("https://microtechia.com", "local", "малий бізнес"),
    ("https://crustula.com.ua", "ecommerce", "магазин"),
    ("https://ka-dent.com.ua", "local", "локальна клініка"),
    ("https://www.aldg.org", "other", "невелика організація"),
    ("https://www.python.org", "documentation", "сайт мови програмування"),
    ("https://fastapi.tiangolo.com", "documentation", "документація фреймворку"),
    ("https://about.gitlab.com", "corporate", "корпоративний сайт"),
    ("https://www.mozilla.org", "other", "сайт некомерційної організації"),
    ("https://web.dev", "documentation", "контентний сайт для розробників"),
    ("https://docs.djangoproject.com", "documentation", "документація фреймворку"),
    ("https://flask.palletsprojects.com", "documentation", "документація бібліотеки"),
    ("https://docs.python-requests.org", "documentation", "документація бібліотеки"),
    ("https://numpy.org", "documentation", "сайт наукової бібліотеки"),
    ("https://pandas.pydata.org", "documentation", "документація бібліотеки"),
    ("https://scikit-learn.org", "documentation", "документація бібліотеки"),
    ("https://matplotlib.org", "documentation", "документація бібліотеки"),
    ("https://jquery.com", "documentation", "сайт бібліотеки"),
    ("https://vuejs.org", "documentation", "документація фреймворку"),
    ("https://svelte.dev", "documentation", "документація фреймворку"),
    ("https://astro.build", "documentation", "документація фреймворку"),
    ("https://gohugo.io", "documentation", "документація генератора"),
    ("https://jekyllrb.com", "documentation", "документація генератора"),
    ("https://www.gnu.org", "documentation", "старий великий сайт проєкту"),
    ("https://www.kernel.org", "documentation", "сайт проєкту"),
    ("https://httpd.apache.org", "documentation", "документація сервера"),
    ("https://nginx.org", "documentation", "документація сервера"),
    ("https://www.postgresql.org", "documentation", "документація СКБД"),
    ("https://sqlite.org", "documentation", "документація СКБД"),
    ("https://redis.io", "documentation", "документація сховища"),
    ("https://curl.se", "documentation", "сайт інструмента"),
    ("https://www.vim.org", "documentation", "старий сайт інструмента"),
    ("https://www.gimp.org", "documentation", "сайт відкритої програми"),
    ("https://inkscape.org", "documentation", "сайт відкритої програми"),
    ("https://www.blender.org", "documentation", "сайт відкритої програми"),
    ("https://www.libreoffice.org", "documentation", "сайт відкритої програми"),
    ("https://www.debian.org", "documentation", "багатомовний сайт дистрибутива"),
    ("https://www.archlinux.org", "documentation", "сайт дистрибутива"),
    ("https://ubuntu.com", "documentation", "сайт дистрибутива"),
    ("https://fedoraproject.org", "documentation", "сайт дистрибутива"),
    ("https://www.opensuse.org", "documentation", "сайт дистрибутива"),
    ("https://www.freebsd.org", "documentation", "старий сайт проєкту"),
    ("https://www.openbsd.org", "documentation", "мінімалістичний старий сайт"),
)

# Пояснення, чому сайт у корпусі. Пишеться за сегментом і класом
# джерела — тобто описує ПРИЧИНУ ВІДБОРУ, а не властивості сайту, яких
# ми не міряли.


@dataclass
class Entry:
    url: str
    segment: str
    tags: list[str] = field(default_factory=list)
    note: str = ""
    source: str = ""
    country: str = ""
    lang: str = ""
    klass: str = ""

    @property
    def key(self) -> str:
        from urllib.parse import urlparse

        from scripts.samples.probe_corpus import canonical_key

        return canonical_key(urlparse(self.url).netloc)


def _order(key: str) -> str:
    """Сталий, але не алфавітний порядок відбору."""
    return hashlib.blake2b(key.encode(), digest_size=8).hexdigest()


def corpus_hash(entries: list[Entry]) -> str:
    """Відбиток складу корпусу: ті самі сайти — той самий рядок."""
    payload = "\n".join(sorted(e.key for e in entries))
    return hashlib.blake2b(payload.encode(), digest_size=16).hexdigest()


def select(
    candidates: list[dict[str, Any]],
    probes: dict[str, dict[str, Any]],
    *,
    quotas: dict[str, int] = QUOTAS,
    country_cap: int = COUNTRY_CAP_PER_SEGMENT,
    class_cap: int = CLASS_CAP_PER_SEGMENT,
) -> tuple[list[Entry], dict[str, Any]]:
    """Відібрати рівно стільки, скільки просять квоти."""
    stats = Counter[str]()
    pools: dict[str, list[Entry]] = {}
    seen: set[str] = set()

    for candidate in candidates:
        probe = probes.get(candidate["url"])
        if probe is None:
            stats["не перевірено"] += 1
            continue
        if not probe["alive"]:
            stats[f"мертвий:{probe['error'] or probe['status']}"] += 1
            continue
        key = probe["canonical_host"]
        if not key:
            stats["без канонічного хоста"] += 1
            continue
        if key in seen:
            stats["дублікат після перенаправлень"] += 1
            continue
        seen.add(key)
        segment = (
            candidate["segment"] if candidate.get("source") == "curated"
            else segment_for(candidate.get("klass", ""), candidate["segment"])
        )
        entry = Entry(
            url=f"https://{probe['canonical_host']}"
            if probe["final_url"].startswith("https")
            else f"http://{probe['canonical_host']}",
            segment=segment,
            tags=list(probe["tags"]),
            note=NOTES.get(segment, NOTES["other"]),
            source=candidate.get("source", ""),
            country=candidate.get("country", ""),
            lang=probe.get("lang", ""),
            klass=candidate.get("klass", ""),
        )
        pools.setdefault(entry.segment, []).append(entry)

    chosen: list[Entry] = []
    taken: set[str] = set()

    # Спершу — записи, відібрані вручну: сайти димової вибірки й ті, яких
    # Wikidata не знає. Вони рахуються в квоту свого сегмента й проходять
    # аудит нарівні з усіма; закріплена лише ПРИСУТНІСТЬ. Без цього
    # fastapi.tiangolo.com, web.dev і microtechia.com випадали з корпусу
    # через порядок хешу — тобто наступність із димовим прогоном
    # трималася б на випадковості.
    pinned: dict[str, list[Entry]] = {}
    for segment, pool in pools.items():
        for entry in pool:
            if entry.source == "curated" and entry.key not in taken:
                taken.add(entry.key)
                chosen.append(entry)
                pinned.setdefault(segment, []).append(entry)
    stats["закріплено curated"] = len(chosen)

    for segment, quota in quotas.items():
        pool = sorted(pools.get(segment, []), key=lambda e: _order(e.key))
        per_country = Counter[str]()
        per_class = Counter[str]()
        picked = len(pinned.get(segment, []))
        # Два проходи: спершу зі стелями на країну й клас, потім добираємо
        # без стель, якщо квота не набралась. Стеля має розрівнювати
        # вибірку, а не робити сегмент меншим за замовлений.
        for strict in (True, False):
            for entry in pool:
                if picked >= quota:
                    break
                if entry.key in taken:
                    continue
                if strict and entry.country and per_country[entry.country] >= country_cap:
                    continue
                if strict and entry.klass and per_class[entry.klass] >= class_cap:
                    continue
                taken.add(entry.key)
                per_country[entry.country] += 1
                per_class[entry.klass] += 1
                chosen.append(entry)
                picked += 1
        stats[f"квота {segment}"] = picked
        stats[f"пул {segment}"] = len(pool)

    # Недобір одного сегмента добираємо з найбільших залишків, щоб вийшло
    # рівно 1000. Це видно в звіті: фактичний розподіл ≠ квотам.
    target = sum(quotas.values())
    if len(chosen) < target:
        leftovers = sorted(
            (e for pool in pools.values() for e in pool if e.key not in taken),
            key=lambda e: _order(e.key),
        )
        for entry in leftovers:
            if len(chosen) >= target:
                break
            taken.add(entry.key)
            chosen.append(entry)

    return chosen[:target], dict(stats)


def to_yaml(entries: list[Entry], provenance: dict[str, Any]) -> str:
    lines = [
        "# Корпус для нічного спостережного прогону Crawldy.",
        "#",
        "# ЗГЕНЕРОВАНО scripts/samples/build_corpus1000.py — руками не правити.",
        "# Ланцюг: harvest_corpus.py -> probe_corpus.py -> build_corpus1000.py",
        "#",
        "# Кожна мітка приходить або з джерела (segment, country), або з",
        "# побаченої відповіді (tags, lang). Здогадів за виглядом домену немає.",
        "#",
        "# provenance:",
    ]
    for key, value in provenance.items():
        lines.append(f"#   {key}: {value}")
    lines.append("sites:")
    for entry in entries:
        lines.append(f"  - url: {entry.url}")
        lines.append(f"    segment: {entry.segment}")
        if entry.tags:
            lines.append(f"    tags: [{', '.join(entry.tags)}]")
        lines.append(f"    note: {entry.note}")
    return "\n".join(lines) + "\n"


def provenance_for(entries, payload, probe_rows):
    """Усе, що потрібно, щоб відтворити й оскаржити цей відбір."""
    from scripts.samples import adult_filter, probe_corpus

    by_source = Counter(e.source for e in entries)
    return {
        "schema": CORPUS_SCHEMA,
        "created_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "count": len(entries),
        "corpus_hash": corpus_hash(entries),
        "what_this_is": (
            "Навмисно різнорідний стратифікований спостережний корпус із "
            "заземленими мітками там, де джерело їх дає. Це НЕ статистично "
            "репрезентативна вибірка вебу: ані генеральної сукупності, ані "
            "ймовірності потрапляння тут не визначено. Частки сегментів — "
            "рішення людини, а не виміряна структура вебу."
        ),
        "sources": {
            "wikidata_p856": {
                "endpoint": payload["sources"]["wikidata"]["endpoint"],
                "property": "P856 (official website)",
                "queries": payload["sources"]["wikidata"]["queries"],
                "failed_queries": payload["sources"]["wikidata"]["problems"],
                "gives": "segment (via entity class) and country",
            },
            "wikidata_software_supplement": payload["sources"].get("wikidata_docs", {}),
            "tranco": payload["sources"]["tranco"],
            "curated": payload["sources"]["curated"],
            "selected_per_source": dict(by_source),
        },
        "class_to_segment": {
            "mapping_version": MAPPING_VERSION,
            "table": CLASS_TO_SEGMENT,
            "note": (
                "Сегмент — наше рішення поверх класу джерела. Сайти "
                "поодинці не перемічуються: лагодиться таблиця."
            ),
        },
        "probe": {
            "concurrency": probe_corpus.CONCURRENCY,
            "request_timeout_s": probe_corpus.TIMEOUT_S,
            "max_bytes_read": probe_corpus.MAX_BYTES,
            "user_agent": probe_corpus.USER_AGENT,
            "rows": len(probe_rows),
            "transport_failure_reprobe": (
                "Перший прохід на паралельності 24 з межею 12 с дав 1876 "
                "таймаутів. Повторна перевірка 60 з них на паралельності 3 "
                "показала 63% живих: міряли насичення власного каналу, а не "
                "сайти. Усі 2995 транспортних збоїв перевірено вдруге на "
                "паралельності 8 з межею 20 с — врятовано 1672 живих сайти. "
                "HTTP-статуси (403, 404, 5xx) вдруге не перевірялись: це "
                "відповідь сайту, а не наша межа."
            ),
        },
        "canonicalization": {
            "unit": "сайт, а не адреса",
            "rules": [
                "схема відкидається; шлях і запит відкидаються",
                "хост у нижньому регістрі, без кінцевої крапки",
                "префікс www. знімається",
                "ключем є хост ПІСЛЯ перенаправлень",
                "приватні адреси, localhost і .local/.internal відкидаються",
            ],
        },
        "adult_exclusion": {
            "policy": (
                "Виключається лише порнографічний вміст. Занедбані, старі, "
                "негарні та погано зроблені сайти ЛИШАЮТЬСЯ: заради них "
                "корпус і збирається."
            ),
            "decisive_alone": ["RTA label", "meta rating=adult/mature"],
            "needs_two_signals": ["title", "meta description/keywords", "domain token"],
            "terms_deliberately_absent": ["sex", "adult"],
            "why": "sexauer.de — прізвище; essex.gov.uk містить sex",
            "strong_terms": list(adult_filter.STRONG_TERMS),
            "domain_tokens": list(adult_filter.DOMAIN_TOKENS),
            "excluded_count": sum(
                1 for p in probe_rows if p.get("excluded_reason") == "adult_content"
            ),
        },
        "selection": {
            "quotas": QUOTAS,
            "ordering": "blake2b(canonical_host) — сталий, але не алфавітний",
            "country_target_per_segment": COUNTRY_CAP_PER_SEGMENT,
            "class_target_per_segment": CLASS_CAP_PER_SEGMENT,
            "targets_are_soft": (
                "Це цілі, а не гарантовані межі: другий прохід добирає "
                "квоту без них, тож фактичну концентрацію треба читати з "
                "виміряних часток, а не з цих чисел."
            ),
            "curated_pinned": (
                "Записи curated закріплені: вони рахуються в квоту свого "
                "сегмента й проходять аудит нарівні з усіма, закріплена "
                "лише присутність. Інакше сайти димової вибірки випадали з "
                "корпусу через порядок хешу."
            ),
        },
        "unknown": {
            "segment_other": sum(1 for e in entries if e.segment == "other"),
            "country": sum(1 for e in entries if not e.country),
            "language": sum(1 for e in entries if not e.lang),
            "untagged": sum(1 for e in entries if not e.tags),
            "policy": "невідоме лишається невідомим; за зоною домену не добудовується",
        },
        "limitations": [
            "Wikidata дає більшість корпусу, бо це єдине джерело із "
            "заземленим сегментом; Tranco наповнює лише other.",
            "Wikidata знає організації, про які написали статтю, тож "
            "справді безіменний малий бізнес представлений слабше.",
            "Сегменти saas і ecommerce набрані з тонкого пулу.",
            "Класифікація football club як travel/дозвілля — слабке місце.",
            "Мова відома лише там, де сайт оголосив <html lang>.",
            "Це не випадкова вибірка: висновки про «веб узагалі» з неї "
            "робити не можна.",
        ],
    }


def build(candidates_path, probes_path, out,
          provenance_path=None, exclusions_path=None):
    payload = json.loads(candidates_path.read_text(encoding="utf-8"))
    probe_rows = json.loads(probes_path.read_text(encoding="utf-8"))
    probes = {p["given"]: p for p in probe_rows}

    candidates = list(payload["candidates"])
    known = {c["url"] for c in candidates}
    for url, segment, hint in CURATED:
        if url not in known:
            candidates.append({
                "url": url, "segment": segment, "klass": "curated",
                "country": "", "label": hint, "source": "curated",
            })

    entries, stats = select(candidates, probes)
    provenance = provenance_for(entries, payload, probe_rows)
    out.write_text(to_yaml(entries, provenance), encoding="utf-8")

    if provenance_path:
        provenance_path.write_text(
            json.dumps({**provenance, "selection_stats": stats},
                       ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    if exclusions_path:
        exclusions_path.write_text(
            json.dumps(
                [
                    {
                        "url": p["given"],
                        "canonical_host": p.get("canonical_host", ""),
                        "title": p.get("title", ""),
                        "excluded_reason": p["excluded_reason"],
                        "evidence": p.get("excluded_evidence", []),
                    }
                    for p in probe_rows if p.get("excluded_reason")
                ],
                ensure_ascii=False, indent=1,
            ),
            encoding="utf-8",
        )
    return {"provenance": provenance, "stats": stats, "entries": entries}


if __name__ == "__main__":
    root = Path("benchmark")
    result = build(
        root / "all_candidates.json",
        root / "probes.json",
        Path("scripts/samples/corpus1000.yaml"),
        provenance_path=Path("scripts/samples/corpus1000.provenance.json"),
        exclusions_path=Path("scripts/samples/corpus1000.exclusions.json"),
    )
    print(json.dumps(result["provenance"], ensure_ascii=False, indent=2))
    print("\nвідбір:")
    for key, value in sorted(result["stats"].items()):
        print(f"  {key:38} {value}")
