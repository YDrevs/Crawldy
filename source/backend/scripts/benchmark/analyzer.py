"""Статистика по завершеному прогону — без повторного краулу.

## Що тут є і чого немає

Є розподіли: частота спрацювання, серйозність, впевненість, бали,
покриття, збої, зрізи за сегментом, спільна поява знахідок, викиди за
часом. Немає жодного рішення: аналіз показує, що чек спрацював на 96%
сайтів, і не називає це дефектом. Так уже було двічі — `seo.render_delta`
спрацьовує на кожному SPA й це правда, а `perf.responsive_images` на 23
сайтах із 29 було хибним спрацюванням. Розрізнити їх може лише людина,
яка подивиться приклади.

## Змішувати правила не можна

Рядки з різними `scoring_version` або `detector_version` описують різні
продукти. Аналіз перевіряє це першим і каже вголос: два прогони по
різні боки зміни правил не порівнюються, і мовчазне зведення тут було б
найдорожчою з можливих помилок.
"""

from __future__ import annotations

import statistics
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

# Частка, вище якої чек уже нічого не розрізняє. Не вирок — привід
# подивитися очима: «спрацював у всіх» буває і правдою, і вадою.
UBIQUITOUS = 0.9
# Частка, нижче якої на цьому корпусі про чек нічого не відомо.
RARE = 0.02
# Менше — і відсотки не мають сенсу.
MIN_SAMPLE = 5


@dataclass(slots=True)
class Analysis:
    """Зведення по прогону."""

    run_id: str = ""
    rows: int = 0
    ok: int = 0
    failed: int = 0
    provenance: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    failures: dict[str, int] = field(default_factory=dict)
    our_failures: int = 0
    retried: int = 0
    scores: dict[str, Any] = field(default_factory=dict)
    modules: dict[str, Any] = field(default_factory=dict)
    coverage: dict[str, Any] = field(default_factory=dict)
    detectors: dict[str, Any] = field(default_factory=dict)
    variants: dict[str, int] = field(default_factory=dict)
    severities: dict[str, int] = field(default_factory=dict)
    confidences: dict[str, int] = field(default_factory=dict)
    segments: dict[str, Any] = field(default_factory=dict)
    co_occurrence: list[dict[str, Any]] = field(default_factory=list)
    runtime: dict[str, Any] = field(default_factory=dict)
    attention: list[str] = field(default_factory=list)
    silent_detectors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return asdict(self)


def _spread(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    return {
        "n": len(ordered),
        "min": round(ordered[0], 2),
        "p25": round(ordered[len(ordered) // 4], 2),
        "median": round(statistics.median(ordered), 2),
        "p75": round(ordered[(3 * len(ordered)) // 4], 2),
        "max": round(ordered[-1], 2),
        "mean": round(statistics.fmean(ordered), 2),
    }


def _known_fields(config: dict[str, Any]) -> dict[str, Any]:
    """Лише ті поля конфігурації, які `RunConfig` справді має.

    Рядок, знятий іншою версією інструмента, не повинен валити аналіз
    старих даних: зайве поле означає «тоді міряли ще й це», а не помилку.
    """
    from dataclasses import fields

    from scripts.benchmark.config import RunConfig

    allowed = {f.name for f in fields(RunConfig)}
    return {k: v for k, v in config.items() if k in allowed}


def analyse(rows: list[dict[str, Any]], *, known_codes: list[str] | None = None) -> Analysis:
    """Порахувати все, що можна порахувати з рядків результату."""
    result = Analysis(rows=len(rows))
    if not rows:
        result.warnings.append("немає рядків для аналізу")
        return result

    result.run_id = str(rows[0].get("run_id") or "")

    # ── провенанс: перше, що перевіряємо ──────────────────────────────
    scoring = {str((r.get("provenance") or {}).get("scoring_version")) for r in rows}
    detector = {str((r.get("provenance") or {}).get("detector_version")) for r in rows}
    commits = {str((r.get("provenance") or {}).get("commit")) for r in rows}
    result.provenance = {
        "scoring_version": sorted(scoring),
        "detector_version": sorted(detector),
        "commits": sorted(commits),
    }
    if len(scoring) > 1:
        result.warnings.append(
            f"РІЗНІ scoring_version у одному наборі: {sorted(scoring)} — "
            f"ці рядки описують різні правила й разом не читаються"
        )
    if len(detector) > 1:
        result.warnings.append(
            f"різні detector_version: {sorted(detector)} — набір чеків відрізнявся"
        )
    if any((r.get("provenance") or {}).get("dirty") for r in rows):
        result.warnings.append("частина рядків знята з брудного дерева")

    # Бюджет краулу — теж правило: він вирішує, що взагалі можна побачити.
    # Застереження стоїть тут, а не лише в шапці прогону, бо аналіз читають
    # окремо від запуску й через місяці після нього.
    from scripts.benchmark.config import RunConfig

    for deviation in sorted({
        d for r in rows for d in RunConfig(**_known_fields(r.get("config") or {})).deviations()
    }):
        result.warnings.append(
            f"бюджет прогону відрізняється від продуктового ({deviation}) — "
            f"висновки про чеки з цих даних робити не можна"
        )

    ok = [r for r in rows if r.get("outcome") == "ok"]
    bad = [r for r in rows if r.get("outcome") != "ok"]
    result.ok, result.failed = len(ok), len(bad)
    # Повтори — властивість прогону, а не сайтів: сайт, який пройшов лише
    # з другої спроби, у статистиці нічим не відрізняється від того, хто
    # пройшов одразу, і це приховує нестабільність вимірювання.
    result.retried = sum(1 for r in rows if int(r.get("attempt") or 1) > 1)

    # ── збої ──────────────────────────────────────────────────────────
    from scripts.benchmark.failures import Failure, ours

    counts = Counter(str(r.get("failure") or "unknown") for r in bad)
    result.failures = dict(sorted(counts.items()))
    for name, n in counts.items():
        try:
            if ours(Failure(name)):
                result.our_failures += n
        except ValueError:
            result.our_failures += n
    if result.our_failures:
        result.warnings.append(
            f"{result.our_failures} збоїв на нашому боці — це дефекти прогону, "
            f"а не властивість сайтів"
        )

    if not ok:
        return result

    # ── бали й покриття ───────────────────────────────────────────────
    result.scores = _spread([float(r["overall"]) for r in ok if r.get("overall") is not None])
    modules: dict[str, list[float]] = {}
    for row in ok:
        for name, value in (row.get("scores") or {}).items():
            if isinstance(value, int | float):
                modules.setdefault(name, []).append(float(value))
    result.modules = {name: _spread(values) for name, values in sorted(modules.items())}

    result.coverage = {
        "pages_ok": _spread([float((r.get("coverage") or {}).get("pages_ok") or 0) for r in ok]),
        "rendered": _spread([float((r.get("coverage") or {}).get("rendered") or 0) for r in ok]),
        "render_success_rate": round(
            sum((r.get("coverage") or {}).get("renders_ok") or 0 for r in ok)
            / max(1, sum((r.get("coverage") or {}).get("rendered") or 0 for r in ok)), 3
        ),
    }
    result.runtime = _spread([float(r.get("duration_s") or 0) for r in rows])
    slowest = sorted(rows, key=lambda r: -float(r.get("duration_s") or 0))[:5]
    result.runtime["slowest"] = [
        {"url": r.get("url"), "seconds": r.get("duration_s")} for r in slowest
    ]

    # ── детектори ─────────────────────────────────────────────────────
    per_site: dict[str, set[str]] = {}
    severities: Counter[str] = Counter()
    confidences: Counter[str] = Counter()
    variants: Counter[str] = Counter()
    for row in ok:
        site = str(row["site_id"])
        for finding in row.get("findings") or []:
            code = str(finding.get("code"))
            per_site.setdefault(code, set()).add(site)
            severities[str(finding.get("severity"))] += 1
            confidences[str(finding.get("confidence"))] += 1
            variants[str(finding.get("issue_key"))] += 1

    result.severities = dict(sorted(severities.items()))
    result.confidences = dict(sorted(confidences.items()))
    result.variants = dict(sorted(variants.items(), key=lambda kv: -kv[1]))

    total = len(ok)
    result.detectors = {
        code: {"sites": len(sites), "share": round(len(sites) / total, 3)}
        for code, sites in sorted(per_site.items(), key=lambda kv: -len(kv[1]))
    }

    if total >= MIN_SAMPLE:
        for code, stats in result.detectors.items():
            if stats["share"] >= UBIQUITOUS:
                result.attention.append(
                    f"{code}: спрацював на {stats['share']:.0%} сайтів — подивитись очима"
                )
            elif stats["share"] <= RARE:
                result.attention.append(
                    f"{code}: спрацював на {stats['share']:.0%} — на цьому корпусі "
                    f"про нього нічого не відомо"
                )

    if known_codes:
        result.silent_detectors = sorted(set(known_codes) - set(per_site))

    # ── зрізи за сегментом ────────────────────────────────────────────
    by_segment: dict[str, list[dict[str, Any]]] = {}
    for row in ok:
        by_segment.setdefault(str(row.get("segment") or "other"), []).append(row)
    result.segments = {
        name: {
            "sites": len(group),
            "score": _spread(
                [float(r["overall"]) for r in group if r.get("overall") is not None]
            ),
        }
        for name, group in sorted(by_segment.items())
    }

    # ── спільна поява ─────────────────────────────────────────────────
    codes = [c for c, s in per_site.items() if len(s) >= MIN_SAMPLE]
    pairs: list[dict[str, Any]] = []
    for i, first in enumerate(codes):
        for second in codes[i + 1 :]:
            both = per_site[first] & per_site[second]
            union = per_site[first] | per_site[second]
            if not union:
                continue
            score = len(both) / len(union)
            if score >= 0.7:
                pairs.append({"codes": [first, second], "jaccard": round(score, 3),
                              "together": len(both)})
    result.co_occurrence = sorted(pairs, key=lambda p: -float(p["jaccard"]))[:20]
    return result


def summary_lines(analysis: Analysis) -> list[str]:
    """Коротке зведення для очей. Первинні дані лишаються в JSON."""
    out = [
        f"прогін     : {analysis.run_id}",
        f"сайтів     : {analysis.rows} (успішних {analysis.ok}, збоїв {analysis.failed}"
        + (f", з повтору {analysis.retried}" if analysis.retried else "")
        + ")",
        f"scoring    : {', '.join(analysis.provenance.get('scoring_version') or [])}",
        f"бал        : {analysis.scores}",
        f"час, с     : n={analysis.runtime.get('n')} median={analysis.runtime.get('median')} "
        f"max={analysis.runtime.get('max')}",
    ]
    if analysis.failures:
        out.append(f"збої       : {analysis.failures}")
    if analysis.warnings:
        out += ["", "ЗАСТЕРЕЖЕННЯ:"] + [f"  ! {w}" for w in analysis.warnings]
    if analysis.attention:
        out += ["", "ПОДИВИТИСЬ ОЧИМА:"] + [f"  ? {a}" for a in analysis.attention]
    if analysis.silent_detectors:
        out += ["", f"жодного разу не спрацювали ({len(analysis.silent_detectors)}):"]
        out += [f"  - {c}" for c in analysis.silent_detectors[:20]]
    return out


__all__ = ["MIN_SAMPLE", "RARE", "UBIQUITOUS", "Analysis", "analyse", "summary_lines"]
