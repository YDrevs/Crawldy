#!/usr/bin/env python3
"""Пілот AI-збагачення на пʼяти сайтах. Разовий затверджений експеримент.

    python scripts/pilot_enrich.py --site web.dev --live
    python scripts/pilot_enrich.py --all --live

Відрізняється від `bench_enrich.py` тим, що зобовʼязаний довести
незмінність детерміністичної правди: базовий стан знімається ДО
збагачення, звіряється ПІСЛЯ, і розбіжність зупиняє пілот.

Живий прогін — лише з `--live`. Без нього йде скриптований провайдер:
можна перевірити весь конвеєр, не витративши нічого.

Кожен сайт пишеться окремим артефактом одразу після завершення, щоб
обрив на третьому сайті не забрав перші два.
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

from app.audit.orchestrator import rescore
from app.audit.snapshot import load as load_snapshot
from app.core.config import settings
from app.enrich.benchmark import score_case
from app.enrich.budgets import budget_for
from app.enrich.contracts import TaskType
from app.enrich.providers.registry import get_provider
from app.enrich.providers.scripted import ScriptedProvider
from app.enrich.routing import (
    CURRENCY,
    DEFAULT_ROUTES,
    PRICING,
    PRICING_VERSION,
    ROUTING_VERSION,
    RouteCandidate,
)
from app.enrich.runner import execute
from app.enrich.tasks import TASKS, build_request
from app.report import build_report, source_from_outcome


def _utf8_console() -> None:
    """Консоль Windows за замовчуванням у cp1251 і валиться на «×» та кирилиці."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


SNAPSHOTS = Path(__file__).resolve().parents[1] / "benchmark" / "snapshots"
OUT_DIR = Path(__file__).resolve().parents[1] / "benchmark" / "pilot"

# Пʼять сайтів, затверджених для пілота. Заміни не передбачено.
CORPUS: dict[str, tuple[str, str]] = {
    "web.dev": ("https-web-dev.json", "сильний / технічно чистий контроль"),
    "rightpricerooter.com": ("https-rightpricerooter-com.json", "SMB із багатьма знахідками"),
    "ka-dent.com.ua": ("https-ka-dent-com-ua.json", "звичайний доглянутий SMB"),
    "linear.app": ("https-linear-app.json", "JS-важкий продуктовий сайт"),
    "gocplumbing.com": ("https-www-gocplumbing-com.json", "частковий краул"),
}

ORDER = (TaskType.SITE_UNDERSTANDING, TaskType.ROOT_CAUSE_GROUPING, TaskType.REMEDIATION_PLAN)


def deterministic_baseline(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Знімок правди аудиту: усе, що збагачення не сміє зрушити.

    Рахується з тих самих даних тим самим шляхом, що й у продукті, і
    звіряється після прогону побайтово (через канонічний JSON).
    """
    ctx = load_snapshot(snapshot)
    outcome = rescore(ctx)
    document = build_report(source_from_outcome(outcome, url=ctx.entry_url))
    return {
        "overall_score": document.overall_score,
        "overall_band": document.overall_band,
        "module_scores": dict(sorted((document.module_scores or {}).items())),
        "findings_count": len(document.recommendations),
        "finding_keys": sorted(r.issue_key for r in document.recommendations),
        "severities": sorted(
            f"{r.issue_key}={r.severity.value}" for r in document.recommendations
        ),
        "evidence_refs": sorted(
            f"{r.issue_key}:{','.join(sorted(r.evidence))}" for r in document.recommendations
        ),
        "coverage": dict(sorted((document.summary.get("coverage") or {}).items())),
        "missing_data": sorted(m.scope for m in document.missing_data),
    }


def payload_for(
    task: TaskType, snapshot: dict[str, Any], groups: list[dict[str, Any]]
) -> dict[str, Any]:
    """Той самий збирач входу, що в продукті (`app/application/enrichment`)."""
    from app.application.enrichment import (
        findings_payload,
        remediation_payload,
        site_understanding_payload,
    )

    ctx = load_snapshot(snapshot)
    document = build_report(source_from_outcome(rescore(ctx), url=ctx.entry_url))
    if task is TaskType.SITE_UNDERSTANDING:
        return dict(site_understanding_payload(ctx, document))
    if task is TaskType.ROOT_CAUSE_GROUPING:
        return dict(findings_payload(document, with_site=True))
    return dict(remediation_payload(document, groups))


async def run_site(name: str, live: bool) -> dict[str, Any]:
    snapshot_file, klass = CORPUS[name]
    snapshot = json.loads((SNAPSHOTS / snapshot_file).read_text(encoding="utf-8"))

    before = deterministic_baseline(snapshot)
    record: dict[str, Any] = {
        "site": name,
        "class": klass,
        "snapshot": snapshot_file,
        "started_at": datetime.now(UTC).isoformat(),
        "baseline_before": before,
        "tasks": [],
    }

    groups: list[dict[str, Any]] = []
    for task in ORDER:
        spec = TASKS[task]
        payload = payload_for(task, snapshot, groups)
        request = build_request(spec, payload)

        if live:
            routes = None  # налаштований основний маршрут, без підміни
            factory = get_provider
        else:
            dry = ScriptedProvider("dry-run", lambda _c, s=spec, p=payload: s.dry_output(p))
            routes = {task: (RouteCandidate("dry-run", "dry-run-model"),)}
            factory = lambda _n, provider=dry: provider  # noqa: E731

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
        record["tasks"].append(
            {
                "task": task.value,
                "task_version": spec.version,
                "prompt_version": spec.prompt_version,
                "schema_version": spec.schema_version,
                "routing_version": ROUTING_VERSION,
                "locale": request.locale,
                "input_hash": request.input_hash,
                "status": outcome.status.value,
                "error": outcome.error,
                # Кожна спроба, включно з невдалими: fallback не ховається.
                "attempts": [
                    {**asdict(a), "outcome": a.outcome.value} for a in outcome.attempts
                ],
                "input_summary": _input_summary(task, payload),
                "result": outcome.result,
                "automatic_scoring": scored.to_json(),
            }
        )

        if task is TaskType.ROOT_CAUSE_GROUPING and outcome.result:
            groups = list(outcome.result.get("groups", []))

        print(
            f"  {task.value:22} {outcome.status.value:11} "
            f"attempts={len(outcome.attempts)} "
            f"tok={_tok(outcome)} cost={_cost(outcome)}"
        )

    after = deterministic_baseline(snapshot)
    record["baseline_after"] = after
    record["deterministic_unchanged"] = json.dumps(before, sort_keys=True) == json.dumps(
        after, sort_keys=True
    )
    record["finished_at"] = datetime.now(UTC).isoformat()
    return record


def _input_summary(task: TaskType, payload: dict[str, Any]) -> dict[str, Any]:
    """Що саме пішло назовні — без самого тексту сторінок."""
    if task is TaskType.SITE_UNDERSTANDING:
        return {
            "origin": payload["origin"],
            "pages": [p["url"] for p in payload["pages"]],
            "chars_sent": sum(len(p["text"]) for p in payload["pages"]),
        }
    return {
        "findings": len(payload.get("findings", [])),
        "groups": len(payload.get("groups", [])),
        "site_context_chars": len(str(payload.get("site", ""))),
    }


def _tok(outcome: Any) -> str:
    ok = [a for a in outcome.attempts if a.total_tokens]
    return str(sum(a.total_tokens for a in ok)) if ok else "—"


def _cost(outcome: Any) -> str:
    ok = [a for a in outcome.attempts if a.cost_usd is not None]
    return f"${sum(a.cost_usd for a in ok):.4f}" if ok else "—"


async def main_async(sites: list[str], live: bool) -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    route = DEFAULT_ROUTES[TaskType.SITE_UNDERSTANDING][0]

    print(f"{'ЖИВИЙ' if live else 'СУХИЙ'} прогін пілота: {len(sites)} сайтів × {len(ORDER)} задач")
    if live:
        priced = PRICING.get(route.model)
        print(f"  провайдер/модель: {route.provider} / {route.model}")
        print(f"  маршрутизація:    v{ROUTING_VERSION}")
        print(f"  цінник:           {PRICING_VERSION} ({CURRENCY}), {priced}")
        if priced is None:
            print("  ЗУПИНКА: цінової бази для моделі немає")
            return 2

    for name in sites:
        print(f"\n{name}")
        record = await run_site(name, live)
        path = OUT_DIR / f"{name.replace('.', '-')}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        mark = "OK" if record["deterministic_unchanged"] else "ЗМІНИЛАСЬ"
        print(f"  детерміністична правда: {mark}  → {path.name}")
        if not record["deterministic_unchanged"]:
            print("  ЗУПИНКА ПІЛОТА: збагачення зрушило правду аудиту")
            return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="пілот AI-збагачення на пʼяти сайтах")
    parser.add_argument("--site", action="append", choices=sorted(CORPUS))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--live", action="store_true", help="справжній провайдер: витрачає гроші")
    _utf8_console()
    args = parser.parse_args()
    sites = sorted(CORPUS) if args.all else (args.site or [])
    if not sites:
        parser.error("вкажіть --site або --all")
    return asyncio.run(main_async(sites, args.live))


if __name__ == "__main__":
    raise SystemExit(main())
