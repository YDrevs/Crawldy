"""Калібрувальний прогін по набору сайтів різної якості.

Дає дві речі, яких не видно на одному сайті:

1. Розподіл оцінок. Якщо добре зроблені сайти й занедбані не
   розходяться, шкала не розрізняє якість — і її треба міняти.
2. Частоту спрацювання кожного чека. Чек, що спрацьовує майже скрізь,
   або тривіальна істина, або хибне спрацювання; в обох випадках він
   не несе інформації й підлягає перегляду.

Використання:
    python scripts/calibrate.py --out calibration.json
    python scripts/calibrate.py --sites my-list.txt --max-pages 8
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit.orchestrator import AuditOptions, run_audit
from app.audit.snapshot import dump as dump_snapshot
from app.audit.types import Module
from app.core.config import settings
from app.core.logging import configure_logging
from app.report import build_report, source_from_outcome

# Менше — і «спрацював на 100% сайтів» нічого не означає.
MIN_SAMPLE = 5

# Очікуваний рівень — це гіпотеза, а не істина. Розбіжність між ним і
# оцінкою — саме те, що варто дивитися руками.
DEFAULT_SITES: list[tuple[str, str]] = [
    ("https://www.gov.uk/", "високий"),
    ("https://web.dev/", "високий"),
    ("https://developer.mozilla.org/", "високий"),
    ("https://stripe.com/", "високий"),
    ("https://linear.app/", "високий"),
    ("https://openai.com/", "високий"),
    ("https://www.anthropic.com/", "високий"),
    ("https://dronehub.ai/", "високий"),
    ("https://www.python.org/", "середній"),
    ("https://fastapi.tiangolo.com/", "середній"),
    ("https://vercel.com/", "середній"),
    # Нижній якір. Без сайту, який має бути внизу, неможливо довести, що
    # шкала взагалі відрізняє добре зроблений сайт від занедбаного —
    # ламається вона саме на краях, а не в середині.
    ("https://1csmart.com.ua/", "низький"),
    ("https://crustula.com.ua/", "низький"),
]


def _force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


async def audit_one(
    url: str,
    max_pages: int,
    max_depth: int,
    llm: bool = False,
    snapshots: Path | None = None,
) -> dict | None:
    try:
        # Семантичний шар вимкнено: він платний, а калібрування дивиться на
        # частоту спрацювання чеків, з яких від нього залежить рівно один.
        # Прогін на 30 сайтів із увімкненим шаром коштує 60 викликів моделі
        # й нічого не додає до відповіді на питання «чи розводить шкала».
        outcome = await run_audit(
            url, AuditOptions(max_pages=max_pages, max_depth=max_depth, llm=llm)
        )
    except Exception as exc:  # noqa: BLE001 — один недоступний сайт не валить прогін
        print(f"  {url}: не вдалося — {exc}", file=sys.stderr)
        return None
    if snapshots is not None:
        # Знімок поруч зі звітом: без нього питання «це сайт змінився
        # чи ми» після кожного прогону лишається здогадом. З ним воно
        # закривається перерахунком тих самих даних новими правилами.
        name = re.sub(r"[^a-z0-9]+", "-", url.lower()).strip("-")[:80]
        (snapshots / f"{name}.json").write_text(
            json.dumps(dump_snapshot(outcome.context), ensure_ascii=False, default=str),
            encoding="utf-8",
        )
    return build_report(source_from_outcome(outcome, url=url)).to_json()


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sites", type=Path, help="файл зі списком URL, по одному на рядок")
    # Бюджет за замовчуванням дорівнює продуктовому (`crawl_max_pages`,
    # `crawl_max_depth`). Було 8 сторінок на глибину 1, і калібрування
    # міряло краул, якого ніхто не виконує: чек про непов'язані теми
    # потребує трьох сторінок одного розділу й за такого бюджету не міг
    # спрацювати в принципі. На вибірці він мовчав на всіх 31 сайті, а з
    # реальним бюджетом спрацьовує на кожному пʼятому — і правильно.
    parser.add_argument("--max-pages", type=int, default=settings.crawl_max_pages)
    parser.add_argument("--max-depth", type=int, default=settings.crawl_max_depth)
    parser.add_argument("--out", type=Path, default=Path("calibration.json"))
    parser.add_argument(
        "--snapshots", type=Path,
        help="тека для знімків: дозволяє перерахувати цей самий прогін новими правилами",
    )
    parser.add_argument(
        "--llm", action="store_true",
        help="увімкнути семантичний шар (платний; за замовчуванням вимкнено)",
    )
    args = parser.parse_args()

    _force_utf8()
    configure_logging(sys.stderr)

    if args.sites:
        lines = args.sites.read_text("utf-8").splitlines()
        sites = [
            (line.strip(), "?")
            for line in lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
    else:
        sites = DEFAULT_SITES

    if args.snapshots:
        args.snapshots.mkdir(parents=True, exist_ok=True)

    reports = []
    for url, expected in sites:
        print(f"  аудит {url} …", file=sys.stderr)
        report = await audit_one(
            url, args.max_pages, args.max_depth, llm=args.llm, snapshots=args.snapshots
        )
        if report is not None:
            report["_expected"] = expected
            reports.append(report)

    args.out.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")
    _print_summary(reports)
    return 0


def _print_summary(reports: list[dict]) -> None:
    print()
    print(f"{'сайт':<34}{'очікуємо':>10}{'загальн.':>10}", end="")
    for module in Module:
        print(f"{module.value[:8]:>10}", end="")
    print()

    # overall_score — None, коли покрито замало напрямів (сайт віддав ботам
    # 403). Такі йдуть у кінець списку: це не «нуль балів», а «невідомо».
    def rank(report: dict) -> tuple[bool, float]:
        score = report["overall_score"]
        return (score is None, -(score or 0))

    for report in sorted(reports, key=rank):
        host = report["target"]["origin"].replace("https://", "")[:32]
        raw = report["overall_score"]
        overall = "—" if raw is None else str(raw)
        print(f"{host:<34}{report['_expected']:>10}{overall:>10}", end="")
        for module in Module:
            field = {
                Module.PERFORMANCE: "speed_score",
                Module.SEO: "seo_score",
                Module.AI_READY: "ai_ready_score",
                Module.LLM_VISIBILITY: "llm_visibility_score",
                Module.TECH: "tech_score",
            }[module]
            value = report.get(field)
            print(f"{'—' if value is None else value:>10}", end="")
        print()

    print()
    total = len(reports)
    print(f"частота чеків (скільки сайтів зачепив, усього {total}):")
    fired = Counter(
        msg
        for report in reports
        for msg in {issue["msg"] for issue in report["issues"]}
    )
    for msg, count in fired.most_common():
        share = count / total
        # Спрацював майже скрізь — або тривіальна істина, або наша помилка;
        # у будь-якому разі такий чек не розрізняє сайти. На маленькій
        # вибірці позначку не ставимо: там 100% нічого не означає.
        mark = " ← перевірити" if share >= 0.9 and total >= MIN_SAMPLE else ""
        print(f"  {count:>2}/{total}  {share:>4.0%}  {msg}{mark}")


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
