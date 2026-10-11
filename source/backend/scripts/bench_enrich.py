#!/usr/bin/env python3
"""Бенчмарк AI-збагачення на фіксованому корпусі знімків.

    python scripts/bench_enrich.py --manifest scripts/samples/enrich_bench.json
    python scripts/bench_enrich.py --manifest ... --live      # витрачає гроші

За замовчуванням — скриптований провайдер: увесь конвеєр (вхід →
маршрут → «виклик» → валідація → оцінка) без мережі й без рахунку.
`--live` іде до справжнього провайдера, і це окреме явне рішення: без
нього жоден батч грошей не витратить.

Корпус — ЗНІМКИ, а не живі краули. Два прогони по мережі — це два різні
сайти, і різницю не можна приписати моделі; ту саму пастку проєкт уже
проходив у калібруванні детекторів (CLAUDE.md: «Два калібрувальні
прогони порівнювати не можна»).

Порівняння провайдерів і моделей робиться прапорцями `--provider` і
`--model`, тобто маршрутизацією. Код задач при цьому не змінюється
жодним рядком — це й є доказ незалежності від провайдера.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.enrichment import (
    EnrichmentDenied,
    findings_payload,
    remediation_payload,
    site_understanding_payload,
)
from app.audit.orchestrator import rescore
from app.audit.snapshot import load as load_snapshot
from app.core.config import settings
from app.enrich.benchmark import DEFAULT_TASKS, score_case
from app.enrich.budgets import budget_for
from app.enrich.contracts import TaskType
from app.enrich.providers.registry import get_provider
from app.enrich.providers.scripted import ScriptedProvider
from app.enrich.routing import RouteCandidate, route_for
from app.enrich.runner import execute
from app.enrich.tasks import TASKS, build_request
from app.report import build_report, source_from_outcome


def payload_for(
    task: TaskType, snapshot: dict[str, Any], groups: list[dict[str, Any]]
) -> dict[str, Any]:
    """Той самий вхід, що збирає продукт, — зі знімка замість БД."""
    ctx = load_snapshot(snapshot)
    document = build_report(source_from_outcome(rescore(ctx), url=ctx.entry_url))
    if task is TaskType.SITE_UNDERSTANDING:
        return dict(site_understanding_payload(ctx, document))
    if task is TaskType.ROOT_CAUSE_GROUPING:
        return dict(findings_payload(document, with_site=True))
    return dict(remediation_payload(document, groups))


async def run_case(
    name: str,
    snapshot: dict[str, Any],
    tasks: tuple[TaskType, ...],
    *,
    live: bool,
    override: RouteCandidate | None,
) -> list[dict[str, Any]]:
    """Один сайт, усі задачі. Групи причин передаються далі в план."""
    rows: list[dict[str, Any]] = []
    groups: list[dict[str, Any]] = []

    for task in tasks:
        spec = TASKS[task]
        try:
            payload = payload_for(task, snapshot, groups)
        except EnrichmentDenied as exc:
            # Сайт, який не віддав вмісту, збагачувати нічим — і це
            # результат корпусу, а не збій харнеса. Заблокований краул у
            # вибірці стоїть саме заради цього рядка.
            rows.append(
                score_case(name, task, {}, None, f"denied:{exc.reason}").to_json()
            )
            continue
        request = build_request(spec, payload)

        if live:
            routes = {task: (override,)} if override else None
            factory = get_provider
        else:
            # Провайдер віддає детермінований вихід самої задачі: конвеєр
            # проходиться цілком, рахунок лишається нульовим.
            dry = ScriptedProvider("dry-run", lambda _call, s=spec, p=payload: s.dry_output(p))
            routes = {task: (RouteCandidate("dry-run", "dry-run-model"),)}
            factory = lambda _name, provider=dry: provider  # noqa: E731

        outcome = await execute(
            spec,
            request,
            routes=routes,
            provider_factory=factory,
            timeout_s=budget_for(task).timeout_s,
            max_attempts=settings.enrich_max_attempts,
            max_output_tokens=budget_for(task).max_output_tokens,
        )

        scored = score_case(name, task, payload, outcome.result, outcome.status.value)
        if outcome.attempts:
            last = outcome.attempts[-1]
            scored.provider = last.provider
            scored.model = last.model
            scored.latency_ms = last.latency_ms
            scored.input_tokens = last.input_tokens
            scored.output_tokens = last.output_tokens
            scored.cost_usd = last.cost_usd
            scored.validation_error = last.error
        if task is TaskType.ROOT_CAUSE_GROUPING and outcome.result:
            groups = list(outcome.result.get("groups", []))
        rows.append(scored.to_json())
    return rows


def load_corpus(manifest_path: str) -> list[tuple[str, dict[str, Any]]]:
    """Маніфест і знімки читаються до запуску циклу подій — це підготовка."""
    path = Path(manifest_path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    return [
        (case["name"], json.loads((path.parent / case["snapshot"]).read_text(encoding="utf-8")))
        for case in manifest["cases"]
    ]


async def main_async(
    args: argparse.Namespace, corpus: list[tuple[str, dict[str, Any]]]
) -> dict[str, Any]:
    tasks = tuple(TaskType(t) for t in args.tasks) if args.tasks else DEFAULT_TASKS
    override = (
        RouteCandidate(args.provider, args.model) if args.provider and args.model else None
    )

    if args.live:
        planned = override or route_for(tasks[0])[0]
        print(
            f"ЖИВИЙ прогін: {len(corpus)} сайтів × {len(tasks)} задач через "
            f"{planned.provider}/{planned.model} — це витратить гроші."
        )

    rows: list[dict[str, Any]] = []
    for name, snapshot in corpus:
        rows += await run_case(name, snapshot, tasks, live=args.live, override=override)
    return {"live": args.live, "cases": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description="бенчмарк AI-збагачення")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--tasks", nargs="*", choices=[t.value for t in TaskType])
    parser.add_argument("--out", help="куди зберегти JSON з оцінками")
    parser.add_argument(
        "--live", action="store_true", help="справжній провайдер: витрачає гроші"
    )
    parser.add_argument("--provider", help="перевизначити провайдера (лише з --live)")
    parser.add_argument("--model", help="перевизначити модель (лише з --live)")
    args = parser.parse_args()
    if (args.provider or args.model) and not args.live:
        parser.error("--provider/--model мають сенс лише разом з --live")
    if bool(args.provider) != bool(args.model):
        parser.error("--provider і --model задаються разом")

    corpus = load_corpus(args.manifest)
    report = asyncio.run(main_async(args, corpus))
    if args.out:
        Path(args.out).write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(json.dumps(report, ensure_ascii=False, indent=2)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
