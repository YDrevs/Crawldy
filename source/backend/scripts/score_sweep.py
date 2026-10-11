#!/usr/bin/env python3
"""Перебір параметрів скорингу на вже зібраних даних.

Прогін калібрувальної вибірки коштує годину; перебір по її результату —
секунду. Знахідки в `calibration.json` містять `code`, `severity` і
модуль, а ваги лежать на самих чеках, тож бал перераховується під
будь-які параметри без жодного мережевого запиту.

Це єдиний спосіб не підганяти шкалу під один сайт: параметр видно одразу
на всій вибірці, а не на тому, що трапилось під руку. Саме так підібрано
`MAX_PENALTY_SHARE_OF_HALF` — і саме так виявилось, що множник до
`half_scale` порядку взагалі не міняє.

    python scripts/calibrate.py --sites scripts/samples/calibration.txt
    python scripts/score_sweep.py calibration.json

Рівні беруться з коментарів у файлі вибірки: рядок `# верх` вмикає
рівень для всіх адрес до наступного такого рядка.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit.checks import all_checks
from app.audit.scoring import (
    MAX_PENALTY_PER_KEY,
    MAX_PENALTY_SHARE_OF_HALF,
    MIN_COVERED_WEIGHT,
    MODULE_HALF_SCALE,
    MODULE_WEIGHT,
    SEVERITY_MULTIPLIER,
)
from app.audit.types import Module, Severity

WEIGHT = {check.code: check.weight for check in all_checks()}

# Рівень у файлі вибірки задається коментарем перед групою адрес.
TIER_MARKS = {"верх": 2, "середина": 1, "низ": 0}


def _force_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def read_tiers(path: Path) -> dict[str, int]:
    """{хост: рівень} із коментарів файлу вибірки."""
    tiers: dict[str, int] = {}
    current: int | None = None
    for line in path.read_text("utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            # «без рівня» скидає групу: сайти, які блокують агента, не
            # належать до жодного рівня — вони перевіряють інше, і
            # успадкувати попередній рівень означало б їх туди зарахувати.
            lowered = stripped.lower()
            if "без рівня" in lowered:
                current = None
                continue
            # Коментар, який рівня не називає, групує адреси всередині
            # нього. Скидання на будь-якому коментарі мовчки викидало
            # все, що стоїть після такого рядка.
            for mark, tier in TIER_MARKS.items():
                if mark in lowered:
                    current = tier
            continue
        if stripped and current is not None:
            host = stripped.split("://")[-1].split("/")[0]
            tiers[host] = current
    return tiers


def load(report_path: Path, tiers: dict[str, int]) -> list[dict]:
    sites = []
    for row in json.loads(report_path.read_text("utf-8")):
        host = str(row["target"].get("origin", "")).split("://")[-1].strip("/")
        tier = tiers.get(host)
        if tier is None or not row["issues"]:
            continue
        present = {
            Module(entry["module"])
            for entry in row["scores"]
            if not entry.get("excluded") and entry.get("score") is not None
        }
        sites.append({"host": host, "tier": tier, "issues": row["issues"], "present": present})
    return sites


def score(site: dict, *, share: float, cap: float, half_factor: float) -> float | None:
    """Той самий розрахунок, що в scoring.py, але з параметрами назовні."""
    half = {module: value * half_factor for module, value in MODULE_HALF_SCALE.items()}
    counted: dict[Module, dict[str, tuple[int, float]]] = {}
    for issue in site["issues"]:
        module = Module(issue["module"])
        value = WEIGHT.get(issue["code"], 2) * SEVERITY_MULTIPLIER[Severity(issue["severity"])]
        seen, _ = counted.setdefault(module, {}).get(issue["code"], (0, value))
        counted[module][issue["code"]] = (seen + 1, value)

    present = site["present"]
    covered = sum(MODULE_WEIGHT[module] for module in present)
    if covered < MIN_COVERED_WEIGHT:
        return None

    total = 0.0
    for module in present:
        penalty = 0.0
        for count, value in counted.get(module, {}).values():
            ceiling = max(value, half[module] * share)
            penalty += min(count * value, value * cap, ceiling)
        module_score = 100.0 * half[module] / (half[module] + penalty)
        total += module_score * (MODULE_WEIGHT[module] / covered)
    return total


def report(sites: list[dict], label: str, **params: float) -> None:
    scored = [(s["host"], s["tier"], score(s, **params)) for s in sites]  # type: ignore[arg-type]
    scored = [row for row in scored if row[2] is not None]
    low = [v for _, tier, v in scored if tier == 0]
    high = [v for _, tier, v in scored if tier == 2]
    if not low or not high:
        print(f"  {label:<38} у вибірці немає обох рівнів")
        return
    # Інверсія — «занедбаний сайт вище за добре зроблений». Саме її і
    # видно клієнту, коли він порівнює свій бал із чужим.
    inversions = sum(1 for lo in low for hi in high if lo > hi)
    spread = max(v for _, _, v in scored) - min(v for _, _, v in scored)
    print(
        f"  {label:<38} інверсій={inversions:>2}/{len(low) * len(high):<3} "
        f"розрив={min(high) - max(low):+6.1f}  діапазон={spread:5.1f}"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", type=Path, help="вихід scripts/calibrate.py")
    parser.add_argument("--sites", type=Path, default=Path("scripts/samples/calibration.txt"))
    args = parser.parse_args()

    _force_utf8()
    sites = load(args.report, read_tiers(args.sites))
    counts = {tier: sum(1 for s in sites if s["tier"] == tier) for tier in (2, 1, 0)}
    print(f"сайтів: {len(sites)}  (верх {counts[2]}, середина {counts[1]}, низ {counts[0]})\n")

    current = dict(share=MAX_PENALTY_SHARE_OF_HALF, cap=MAX_PENALTY_PER_KEY, half_factor=1.0)
    report(sites, "як зараз", **current)

    print("\n--- друга стеля: частка half_scale на один код")
    for share in (0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 99.0):
        name = "без другої стелі" if share > 1 else f"{share}·half_scale"
        report(sites, name, **{**current, "share": share})

    print("\n--- перша стеля: у скільки разів повторення дорожче за одну знахідку")
    for cap in (2.0, 3.0, 4.0, 6.0):
        report(sites, f"{cap}× від знахідки", **{**current, "cap": cap})

    print("\n--- рівень шкали (порядку не міняє, лише самі числа)")
    for factor in (0.5, 0.7, 1.0, 1.2):
        report(sites, f"half_scale × {factor}", **{**current, "half_factor": factor})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
