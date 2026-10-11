#!/usr/bin/env python3
"""Внутрішній тригер AI-збагачення. Єдиний спосіб запустити фазу 1.

    python scripts/enrich_cli.py <audit-id> --task root_cause_grouping --dry-run
    python scripts/enrich_cli.py <audit-id> --task site_understanding --live

Клієнтських шляхів, які вмикають збагачення, не існує: жоден маршрут API
не передає `experimental=True`, і жоден із них не читає збережені
результати. Поки бенчмарк не затверджений, запустити шар може лише
людина цією командою.

`--dry-run` (за замовчуванням) проганяє ВЕСЬ конвеєр — збірка входу,
маршрут, «виклик», валідація, запис журналу — на скриптованому
провайдері, без мережі й без грошей. `--live` іде до справжнього
провайдера й витрачає гроші; саме тому це окремий явний прапорець.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application import enrichment
from app.core.db import SessionLocal
from app.enrich.contracts import TaskType
from app.enrich.providers.registry import register_provider
from app.enrich.providers.scripted import ScriptedProvider
from app.enrich.routing import RouteCandidate
from app.enrich.tasks import TASKS
from app.models import Audit


async def run(audit_id: uuid.UUID, task: TaskType, live: bool) -> int:
    async with SessionLocal() as session:
        try:
            run_row = await enrichment.start_run(session, audit_id, task, experimental=True)
        except enrichment.EnrichmentDenied as exc:
            print(f"відмовлено: {exc.reason}")
            return 2
        run_id = run_row.id
        audit = await session.get(Audit, audit_id)
        assert audit is not None  # start_run уже впав би
        payload = await enrichment.build_task_input(session, audit, task)
        await session.commit()

    routes = None
    if not live:
        spec = TASKS[task]
        register_provider(
            "dry-run",
            lambda: ScriptedProvider("dry-run", lambda _call: spec.dry_output(payload)),
        )
        routes = {task: (RouteCandidate("dry-run", "dry-run-model"),)}

    async with SessionLocal() as session:
        done = await enrichment.execute_run(session, run_id, routes=routes)
        status = done.status.value
        result = dict(done.result)
        attempts = [
            {
                "n": a.number,
                "provider": a.provider,
                "model": a.model,
                "outcome": a.outcome,
                "latency_ms": a.latency_ms,
                "in": a.input_tokens,
                "out": a.output_tokens,
                "cost_usd": a.cost_usd,
                "error": a.error,
            }
            for a in done.attempts
        ]
        await session.commit()

    print(f"run={run_id} status={status}")
    print(json.dumps({"attempts": attempts}, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False, indent=2)[:4000])
    return 0 if status == "completed" else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="внутрішній тригер AI-збагачення")
    parser.add_argument("audit_id")
    parser.add_argument(
        "--task",
        required=True,
        choices=[t.value for t in TaskType],
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="без мережі й без грошей (за замовчуванням)",
    )
    mode.add_argument(
        "--live",
        action="store_true",
        help="справжній провайдер: витрачає гроші",
    )
    args = parser.parse_args()
    return asyncio.run(run(uuid.UUID(args.audit_id), TaskType(args.task), args.live))


if __name__ == "__main__":
    raise SystemExit(main())
