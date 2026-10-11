#!/usr/bin/env python3
"""Перерахунок похідної телеметрії збереженого бенчмарку. Без мережі.

    python scripts/backfill_bench_costs.py benchmark/v2-model-comparison/results-live.json

Навіщо. Перший живий виклик OpenAI повернув датований знімок моделі
(`gpt-5.4-mini-2026-03-17`), якого немає в ціннику, і вартість записалась
`None` при цілком відомій ціні. Дефект був у розвʼязанні ціни, а не в
генерації: сам вихід моделі валідний і перевикликати його немає підстав —
це коштувало б грошей і підмінило б спостереження іншим.

Тому тут перераховується ЛИШЕ похідне: вартість із уже збережених
токенів і автоматичні оцінки детекторів. Вміст, згенерований моделлю,
не редагується; сирі докази (токени, затримка, фактична модель)
лишаються як були. Факт перерахунку записується в сам артефакт.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.enrich.benchmark import score_case
from app.enrich.contracts import TaskType
from app.enrich.routing import PRICING_VERSION, cost_estimate, pricing_key_for


def _payload_of(row: dict[str, Any]) -> dict[str, Any]:
    """Канонічний вхід клітинки — з замороженого знімка, як у прогоні."""
    from scripts.bench_v2 import MANIFEST, payload_for

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    case = next(c for c in manifest["cases"] if c["name"] == row["site"])
    snapshot = json.loads((MANIFEST.parent / case["snapshot"]).read_text(encoding="utf-8"))
    return payload_for(TaskType(row["task"]), snapshot, [])


def recalc(path: Path) -> int:
    report = json.loads(path.read_text(encoding="utf-8"))
    changed = 0

    for row in report["rows"]:
        requested = row.get("model_key")
        for attempt in row["attempts"]:
            actual = attempt.get("model")
            # Запитана модель — з маршруту бенчмарку, а не з відповіді.
            from app.enrich.routing import BENCHMARK_MODELS

            asked = BENCHMARK_MODELS[requested].model if requested in BENCHMARK_MODELS else actual
            key = pricing_key_for(asked, actual)
            cost, version = cost_estimate(
                key or "",
                attempt.get("input_tokens"),
                attempt.get("output_tokens"),
                attempt.get("cache_write_tokens"),
                attempt.get("cache_read_tokens"),
            )
            before = attempt.get("cost_usd")
            attempt["requested_model"] = asked
            attempt["pricing_key"] = key
            attempt["cost_usd"] = cost
            attempt["pricing_version"] = version or PRICING_VERSION
            if before != cost:
                changed += 1
                print(f"  {requested:14} {row['task']:20} {before} → {cost}")

        # Автоматичні оцінки теж похідні: детектор `guarantees` виправлено.
        #
        # Вхід відновлюється з того самого замороженого знімка тим самим
        # збирачем, що й у прогоні: без нього детектор не має з чим
        # звіряти цитати, і переказ чужої гарантії знову виглядав би
        # вигадкою.
        if row.get("result"):
            payload_note = row.get("scoring", {})
            payload = _payload_of(row)
            scored = score_case(
                row["site"], TaskType(row["task"]), payload, row["result"], row["status"]
            )
            # Зберігаємо людські поля, якщо їх уже заповнювали.
            merged: dict[str, Any] = scored.to_json()
            for human in ("plausibility", "usefulness", "ordering_usefulness",
                          "cluster_quality", "cause_discipline", "coverage_respect",
                          "generic_restatement", "reviewer_note"):
                if payload_note.get(human):
                    merged[human] = payload_note[human]
            # Провенанс спроби лишається в attempts; тут лише оцінки.
            for field in ("provider", "model", "latency_ms", "input_tokens",
                          "output_tokens", "cost_usd", "validation_error"):
                merged[field] = payload_note.get(field)
            merged["cost_usd"] = row["attempts"][-1].get("cost_usd")
            row["scoring"] = merged

    report.setdefault("corrections", []).append(
        {
            "at": datetime.now(UTC).isoformat(),
            "what": "derived telemetry recalculated from stored raw usage",
            "why": "pricing resolution did not handle dated provider model snapshots; "
                   "benchmark detector flagged source-grounded guarantees",
            "model_outputs_regenerated": False,
            "provider_calls_made": 0,
            "pricing_version": PRICING_VERSION,
        }
    )
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return changed


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        r = getattr(stream, "reconfigure", None)
        if r is not None:
            r(encoding="utf-8", errors="replace")
    target = Path(sys.argv[1])
    print(f"перерахунок похідного в {target.name} (мережі не буде):")
    changed = recalc(target)
    print(f"оновлено значень вартості: {changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
