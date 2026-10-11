#!/usr/bin/env python3
"""Перерахунок теки знімків нинішніми правилами: python scripts/rescore_dir.py snaps/

Навіщо це, коли є `calibrate.py`. Два калібрувальні прогони — це два
різні краули, а розкид між ними більший за більшість змін, які ми
оцінюємо: на 29 сайтах медіанний зсув бала становив 2, у тринадцяти
випадках 3 і більше, максимум 7. Джерело — Lighthouse: його вага 0.22, а
числа між викликами гуляють. Порівнюючи два прогони, ми читаємо шум і
приписуємо його своїй правці.

Знімок цю проблему прибирає повністю: дані ті самі, змінюються лише
правила. Порядок такий — прогнати цей скрипт до зміни, зробити зміну,
прогнати ще раз. Різниця в таблиці належить правці, і більше нікому.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit.orchestrator import rescore
from app.audit.snapshot import load as load_snapshot
from app.core.logging import configure_logging

TIERS = ("верх", "середина", "низ")


def _force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def read_tiers(path: Path) -> dict[str, str]:
    """Рівень сайту з коментарів у файлі вибірки. Гіпотеза, не істина.

    Коментар, що називає рівень, вмикає його; «без рівня» вимикає;
    решта коментарів нічого не змінюють — вони групують адреси всередині
    рівня. Обидві межі не теоретичні: без першої openai.com і aequo.ua,
    які блокують агента й мають давати None, зараховувались у нижній
    рівень; без другої групувальний коментар мовчки викидав усе, що
    стоїть після нього.
    """
    out: dict[str, str] = {}
    tier: str | None = None
    for line in path.read_text("utf-8").splitlines():
        text = line.strip()
        if text.startswith("#"):
            low = text.lower()
            if "без рівня" in low:
                tier = None
            else:
                for name in TIERS:
                    if name[:4] in low:
                        tier = name
        elif text and tier:
            out[text.rstrip("/")] = tier
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("snapshots", type=Path, help="тека зі знімками від calibrate.py")
    parser.add_argument(
        "--sites", type=Path, default=Path("scripts/samples/calibration.txt"),
        help="файл вибірки: з його коментарів беруться рівні",
    )
    parser.add_argument("--json", action="store_true", help="сирі бали замість таблиці")
    args = parser.parse_args()

    _force_utf8()
    configure_logging(sys.stderr)

    tiers = read_tiers(args.sites)
    scored: list[tuple[str, str | None, int | None]] = []
    for path in sorted(args.snapshots.glob("*.json")):
        ctx = load_snapshot(json.loads(path.read_text(encoding="utf-8")))
        outcome = rescore(ctx)
        url = ctx.entry_url.rstrip("/")
        scored.append((url, tiers.get(url), outcome.overall))

    if args.json:
        print(json.dumps(
            {url: score for url, _, score in scored}, ensure_ascii=False, indent=2
        ))
        return 0

    _print_tiers(scored)
    return 0


def _print_tiers(scored: list[tuple[str, str | None, int | None]]) -> None:
    by: dict[str, list[tuple[int, str]]] = {name: [] for name in TIERS}
    for url, tier, score in scored:
        if tier in by and score is not None:
            by[tier].append((score, url))

    print(f"\nперераховано зі знімків: {len(scored)}")
    for name in TIERS:
        values = sorted(score for score, _ in by[name])
        if values:
            print(
                f"  {name:<9} n={len(values):<3} мін={values[0]:<3} "
                f"медіана={statistics.median(values):<5} макс={values[-1]}"
            )

    top = [s for s, _ in by["верх"]]
    bottom = [s for s, _ in by["низ"]]
    if not (top and bottom):
        return
    inversions = [
        (low_url, low, high_url, high)
        for low, low_url in by["низ"]
        for high, high_url in by["верх"]
        if low > high
    ]
    print(f"  розрив верх/низ: {min(top) - max(bottom)}   інверсій: {len(inversions)}")
    for low_url, low, high_url, high in inversions[:6]:
        print(f"    {low_url} {low} > {high_url} {high}")


if __name__ == "__main__":
    raise SystemExit(main())
