#!/usr/bin/env python3
"""Порівняння моделей на задачах Phase-1 v2. Два сайти, три моделі.

    python scripts/bench_v2.py                      # сухий прогін, нуль витрат
    python scripts/bench_v2.py --plan               # лише кошторис і склад
    python scripts/bench_v2.py --live --confirm-spend   # платний прогін

Три речі, які цей скрипт зобовʼязаний робити правильно.

**Не витрачати гроші випадково.** Живий прогін вимагає ДВОХ прапорців:
`--live` і `--confirm-spend`. Одного замало навмисно — `--live` легко
дописати за звичкою з інших скриптів проєкту. Без обох іде скриптований
провайдер: увесь конвеєр, нульовий рахунок.

**Показати кошторис до першого виклику.** Скільки викликів, якими
моделями, за яким цінником і яка стеля витрат. Оцінка песимістична:
занижена перед платним прогоном гірша за відсутню.

**Порівнювати моделі, а не конфігурації.** Усі три отримують ті самі
канонічні входи, ті самі версії задач і ту саму локаль. Відрізняється
рівно один рядок — маршрут.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.enrich.benchmark import score_case
from app.enrich.budgets import budget_for, budgets_provenance
from app.enrich.contracts import TaskType
from app.enrich.providers.registry import get_provider
from app.enrich.providers.scripted import ScriptedProvider
from app.enrich.routing import (
    BENCHMARK_MODELS,
    CURRENCY,
    PRICING,
    PRICING_VERSION,
    ROUTING_VERSION,
    benchmark_routes,
    estimate_upper_bound,
)
from app.enrich.runner import execute
from app.enrich.tasks import TASKS, build_request

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmark" / "v2-model-comparison" / "manifest.json"
OUT_DIR = ROOT / "benchmark" / "v2-model-comparison"

ORDER = (TaskType.SITE_UNDERSTANDING, TaskType.ROOT_CAUSE_GROUPING, TaskType.REMEDIATION_PLAN)

# Стеля входу для кошторису. Береться з найбільшого входу пілота з
# запасом: точне число до прогону невідоме, а занижувати не можна.
ASSUMED_MAX_INPUT_TOKENS = 12_000


def _utf8_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


def payload_for(
    task: TaskType, snapshot: dict[str, Any], groups: list[dict[str, Any]]
) -> dict[str, Any]:
    """Той самий збирач входу, що в продукті — зі знімка замість БД."""
    from app.application.enrichment import (
        findings_payload,
        remediation_payload,
        site_understanding_payload,
    )
    from app.audit.orchestrator import rescore
    from app.audit.snapshot import load as load_snapshot
    from app.report import build_report, source_from_outcome

    ctx = load_snapshot(snapshot)
    document = build_report(source_from_outcome(rescore(ctx), url=ctx.entry_url))
    if task is TaskType.SITE_UNDERSTANDING:
        return dict(site_understanding_payload(ctx, document))
    if task is TaskType.ROOT_CAUSE_GROUPING:
        return dict(findings_payload(document, with_site=True))
    return dict(remediation_payload(document, groups))


# Дозволена стеля витрат на весь бенчмарк. Перевищення — привід спинитись
# і спитати, а не тихо розширити конверт.
SPEND_CEILING = 2.00


def _completed_cells() -> set[tuple[str, str, str]]:
    """Клітинки, які вже мають валідний успішний вихід."""
    out = OUT_DIR / "results-live.json"
    if not out.exists():
        return set()
    report = json.loads(out.read_text(encoding="utf-8"))
    return {
        (r["model_key"], r["site"], r["task"])
        for r in report.get("rows", [])
        if r.get("status") == "completed"
    }


def _already_spent() -> float:
    out = OUT_DIR / "results-live.json"
    if not out.exists():
        return 0.0
    report = json.loads(out.read_text(encoding="utf-8"))
    return sum(
        (a.get("cost_usd") or 0.0)
        for r in report.get("rows", [])
        for a in r.get("attempts", [])
    )


def _pending_cells(manifest: dict[str, Any]) -> dict[TaskType, dict[str, list[str]]]:
    """Що лишилось виконати: задача → сайт → моделі."""
    done = _completed_cells()
    pending: dict[TaskType, dict[str, list[str]]] = {}
    for task in ORDER:
        per_site: dict[str, list[str]] = {}
        for case in manifest["cases"]:
            models = [
                m for m in manifest["models"]
                if (m, case["name"], task.value) not in done
            ]
            if models:
                per_site[case["name"]] = models
        pending[task] = per_site
    return pending


def show_plan(manifest: dict[str, Any], live: bool) -> None:
    """Склад і кошторис. Друкується завжди, і перед живим прогоном теж."""
    cases = manifest["cases"]
    models = manifest["models"]
    calls = len(cases) * len(ORDER)
    print("── ПЛАН ПОРІВНЯННЯ ───────────────────────────────────────────")
    print(f"  режим:        {'ЖИВИЙ (витрачає гроші)' if live else 'СУХИЙ (нуль витрат)'}")
    print(f"  сайти:        {', '.join(c['name'] for c in cases)}")
    print(f"  задачі:       {', '.join(t.value for t in ORDER)}")
    print(f"  маршрутизація v{ROUTING_VERSION} | цінник {PRICING_VERSION} ({CURRENCY})")
    print(f"  логічних викликів: {calls} × {len(models)} моделі = {calls * len(models)}")
    print()
    # Кошторис по-задачно: єдина стеля 8000 на всі задачі завищувала б
    # оцінку `site_understanding`, у якої бюджет 3000, і кошторис
    # спрацьовував би як хибна тривога.
    pending = _pending_cells(manifest)
    pending_count = sum(len(m) for sites in pending.values() for m in sites.values())
    done = calls * len(models) - pending_count
    if done:
        print(f"  вже виконано клітинок: {done} із {calls * len(models)}"
              f" (перевикликати не будемо), лишилось {pending_count}")
        print(f"  вже витрачено: ${_already_spent():.4f}")
        print()

    total: float | None = 0.0
    for key in models:
        candidate = BENCHMARK_MODELS[key]
        price = PRICING.get(candidate.model)
        if price is None:
            print(f"  {key:14} {candidate.provider}/{candidate.model:18} ЦІНИ НЕМАЄ")
            total = None
            continue
        bound = 0.0
        for task, sites in pending.items():
            per_cell = estimate_upper_bound(
                key, 1, ASSUMED_MAX_INPUT_TOKENS, budget_for(task).max_output_tokens
            )
            bound += (per_cell or 0.0) * len([s for s in sites if key in sites[s]])
        print(
            f"  {key:14} {candidate.provider}/{candidate.model:18} "
            f"in ${price.input_}/M out ${price.output}/M  →  стеля ≈ ${bound:.2f}"
        )
        if total is not None:
            total += bound
    print()
    if total is None:
        print("  СТЕЛЯ ВИТРАТ: невідома — для якоїсь моделі немає цінової бази")
    else:
        print(f"  СТЕЛЯ ВИТРАТ УСЬОГО: ≈ ${total:.2f} (песимістично: весь вхід")
        budgets = ", ".join(
            f"{t.value.split(chr(95))[0]}={budget_for(t).max_output_tokens}" for t in ORDER
        )
        print(f"     некешований, вихід по стелі задачі: {budgets})")
    if total is not None and total + _already_spent() > SPEND_CEILING:
        print(f"  УВАГА: разом із витраченим це перевищує стелю ${SPEND_CEILING:.2f}")
    print("──────────────────────────────────────────────────────────────")


def _stored_groups(model_key: str, site: str) -> list[dict[str, Any]]:
    """Кластери з уже збереженої клітинки — щоб план спирався на них.

    Без цього пропущене групування лишало б план без груп, і причинна
    стеля обвалилася б до `none` штучно.
    """
    out = OUT_DIR / "results-live.json"
    if not out.exists():
        return []
    report = json.loads(out.read_text(encoding="utf-8"))
    for row in report.get("rows", []):
        if (
            row["model_key"] == model_key
            and row["site"] == site
            and row["task"] == TaskType.ROOT_CAUSE_GROUPING.value
            and row.get("result")
        ):
            return list(row["result"].get("groups", []))
    return []


async def run_model(
    model_key: str,
    cases: list[tuple[str, dict[str, Any]]],
    live: bool,
    only_tasks: tuple[TaskType, ...] = ORDER,
) -> list[dict[str, Any]]:
    done = _completed_cells()
    rows: list[dict[str, Any]] = []
    for name, snapshot in cases:
        groups: list[dict[str, Any]] = []
        print(f"\n  {model_key} / {name}")
        for task in only_tasks:
            # Успішна клітинка — завершене спостереження. Перевиклик
            # коштував би грошей і підмінив би її іншим випадковим
            # виходом, тобто зіпсував би те, що вже маємо.
            if (model_key, name, task.value) in done:
                print(f"    {task.value:22} вже є — пропуск")
                if task is TaskType.ROOT_CAUSE_GROUPING:
                    groups = _stored_groups(model_key, name)
                continue
            spec = TASKS[task]
            payload = payload_for(task, snapshot, groups)
            request = build_request(spec, payload)

            if live:
                routes = benchmark_routes(model_key, ORDER)
                factory = get_provider
            else:
                dry = ScriptedProvider(
                    "dry-run", lambda _c, s=spec, p=payload: s.dry_output(p)
                )
                routes = benchmark_routes(model_key, ORDER)
                factory = lambda _n, provider=dry: provider  # noqa: E731

            outcome = await execute(
                spec,
                request,
                routes=routes,
                provider_factory=factory,
                timeout_s=budget_for(task).timeout_s,
                # Один кандидат на модель: fallback перекривав би те, що
                # ми міряємо.
                max_attempts=1,
                max_output_tokens=budget_for(task).max_output_tokens,
            )

            scored = score_case(name, task, payload, outcome.result, outcome.status.value)
            if outcome.attempts:
                a = outcome.attempts[-1]
                scored.provider, scored.model = a.provider, a.model
                scored.latency_ms = a.latency_ms
                scored.input_tokens, scored.output_tokens = a.input_tokens, a.output_tokens
                scored.cost_usd = a.cost_usd
                scored.validation_error = a.error
            if task is TaskType.ROOT_CAUSE_GROUPING and outcome.result:
                groups = list(outcome.result.get("groups", []))

            rows.append(
                {
                    "model_key": model_key,
                    "site": name,
                    "task": task.value,
                    "task_version": spec.version,
                    "prompt_version": spec.prompt_version,
                    "schema_version": spec.schema_version,
                    "input_hash": request.input_hash,
                    "status": outcome.status.value,
                    "attempts": [
                        {**asdict(x), "outcome": x.outcome.value} for x in outcome.attempts
                    ],
                    "result": outcome.result,
                    "scoring": scored.to_json(),
                }
            )
            print(f"    {task.value:22} {outcome.status.value}")
    return rows


async def main_async(args: argparse.Namespace) -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    show_plan(manifest, args.live)
    if args.plan:
        return 0

    if args.live and not args.confirm_spend:
        print("\nВІДМОВА: живий прогін потребує ще й --confirm-spend.")
        print("Одного --live замало навмисно: його легко дописати за звичкою.")
        return 2

    cases = [
        (c["name"], json.loads((MANIFEST.parent / c["snapshot"]).read_text(encoding="utf-8")))
        for c in manifest["cases"]
    ]
    if args.site:
        cases = [c for c in cases if c[0] in args.site]
    models = [m for m in manifest["models"] if not args.model or m in args.model]
    only_tasks = tuple(TaskType(t) for t in args.task) if args.task else ORDER

    rows: list[dict[str, Any]] = []
    for model_key in models:
        rows += await run_model(model_key, cases, args.live, only_tasks)

    report = {
        "manifest": manifest["name"],
        "live": args.live,
        "generated_at": datetime.now(UTC).isoformat(),
        "routing_version": ROUTING_VERSION,
        "pricing_version": PRICING_VERSION,
        # Бюджет виконання — частина умов експерименту: два прогони
        # однієї задачі під різними стелями непорівнянні.
        "execution_budgets": budgets_provenance(),
        "rows": rows,
    }
    suffix = "live" if args.live else "dry"
    out = OUT_DIR / f"results-{suffix}.json"

    # Поетапний прогін дописує клітинки, а не стирає попередні: перші
    # три виклики — теж результати бенчмарку, і платити за них двічі
    # немає підстав.
    if out.exists():
        previous = json.loads(out.read_text(encoding="utf-8"))
        seen = {(r["model_key"], r["site"], r["task"]) for r in rows}
        kept = [
            r
            for r in previous.get("rows", [])
            if (r["model_key"], r["site"], r["task"]) not in seen
        ]
        report["rows"] = kept + rows
        print(f"\nдописано до наявних {len(kept)} клітинок")

    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"записано: {out.relative_to(ROOT)}  ({len(report['rows'])} виходів усього)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="порівняння моделей на задачах v2")
    parser.add_argument("--plan", action="store_true", help="лише кошторис, нічого не виконувати")
    parser.add_argument("--live", action="store_true", help="справжні провайдери")
    parser.add_argument(
        "--confirm-spend",
        action="store_true",
        help="друге явне підтвердження витрат; без нього --live відмовляє",
    )
    # Поетапність: спершу одна задача на всіх моделях, і лише потім решта.
    parser.add_argument("--site", action="append", help="обмежити сайтами")
    parser.add_argument("--task", action="append", choices=[t.value for t in TaskType])
    parser.add_argument("--model", action="append", help="обмежити моделями")
    _utf8_console()
    return asyncio.run(main_async(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
