"""Контрольований Vertex-смок google-провайдера присутності.

Внутрішній шлях (без організації і клієнтського права), один промпт,
одне natural-спостереження, твердий бюджет прогону $0.50, довговічна
книга на живій базі. Жодного іншого провайдера.

Передумови (дії власника, разово):
  1. gcloud auth application-default login
  2. gcloud services enable aiplatform.googleapis.com --project=<PROJECT>
  3. echo GOOGLE_VERTEX_PROJECT=<PROJECT> >> backend/.env

Запуск:  python scripts/presence_vertex_smoke.py
База:    SMOKE_DATABASE_URL або postgresql+asyncpg://seo:seo@localhost:5432/seo
Артефакт: SMOKE_ARTIFACT або google-vertex-smoke.json у поточній теці
"""

from __future__ import annotations

import asyncio
import json
import os
import pathlib
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app.ai import catalog as ai_catalog
from app.core.config import settings
from app.models.presence import (
    PresenceAttempt,
    PresenceObservation,
    PresenceRun,
)
from app.presence import policy as presence_policy
from app.presence.prompts import PromptFacts, build_prompt_set
from app.services import presence_service

DB = os.environ.get(
    "SMOKE_DATABASE_URL", "postgresql+asyncpg://seo:seo@localhost:5432/seo")
OUT = pathlib.Path(os.environ.get(
    "SMOKE_ARTIFACT", "google-vertex-smoke.json"))


async def main() -> dict:
    if not settings.google_vertex_project:
        raise SystemExit(
            "GOOGLE_VERTEX_PROJECT не задано — див. передумови в шапці")

    policy = presence_policy.PresencePolicy(
        enabled=True,
        providers={"google": presence_policy.ProviderPolicy(
            enabled=True, model="gemini-2.5-flash", backend="vertex_ai")},
        runs_per_prompt=1, max_prompts=1, retry_limit=0,
        budget_usd_total=0.50, budget_usd_per_provider=0.50,
        raw_retention_days=30, concurrency=1,
        modes=("natural",),
    )
    errors = presence_policy.validate(policy)
    assert not errors, errors

    facts = PromptFacts(
        brand="Ka-Dent", brand_aliases=("Ka Dent",),
        domain="ka-dent.kiev.ua", category="dental clinic",
        services=("implants",), location="Kyiv", language="en",
    )
    prompt_set = build_prompt_set(facts)
    prompt = prompt_set.prompts[0]  # небрендовий категорійний промпт

    engine = create_async_engine(DB)
    make = async_sessionmaker(engine, expire_on_commit=False)
    async with make() as session:
        run = PresenceRun(
            organization_id=None,  # внутрішній шлях: без клієнтських прав
            url="https://ka-dent.kiev.ua", origin="https://ka-dent.kiev.ua",
            brand="Ka-Dent", brand_aliases=["Ka-Dent", "Ka Dent"],
            prompt_set_version=prompt_set.version,
            prompts=[{
                "prompt_id": prompt.prompt_id, "text": prompt.text,
                "category": prompt.category.value,
                "segment": prompt.segment.value,
                "language": prompt.language,
            }],
            policy_snapshot={
                **presence_policy.to_stored(policy),
                "pricing_version": ai_catalog.pricing_version(),
                "vertex": {
                    "project": settings.google_vertex_project,
                    "location": settings.google_vertex_location,
                },
            },
            status="queued",
            entitlement_source="internal",
        )
        session.add(run)
        await session.commit()
        run_id = run.id

        result = await presence_service.execute(session, run_id)
        await session.commit()

        observations = (await session.execute(
            select(PresenceObservation)
            .where(PresenceObservation.run_id == run_id)
        )).scalars().all()
        attempts = (await session.execute(
            select(PresenceAttempt)
            .where(PresenceAttempt.run_id == run_id)
        )).scalars().all()

        report = {
            "run_id": str(run_id),
            "run_status": result.status,
            "run_error": result.error,
            "cost_usd": result.cost_usd,
            "pricing_version": ai_catalog.pricing_version(),
            "vertex_project": settings.google_vertex_project,
            "vertex_location": settings.google_vertex_location,
            "observations": [{
                "provider": o.provider, "model": o.model,
                "tool_version": o.tool_version, "mode": o.mode,
                "status": o.status, "searched": o.searched,
                "search_queries": o.search_queries,
                "cited_domains": o.cited_domains,
                "brand_mentioned": o.brand_mentioned,
                "input_tokens": o.input_tokens,
                "output_tokens": o.output_tokens,
                "searches": o.searches,
                "cost_usd": o.cost_usd,
                "duration_ms": o.duration_ms,
            } for o in observations],
            "attempts": [{
                "state": a.state, "attempt_no": a.attempt_no,
                "reserved_max_usd": str(a.reserved_max_usd),
                "actual_cost_usd": (str(a.actual_cost_usd)
                                    if a.actual_cost_usd is not None
                                    else None),
                "pricing_version": a.pricing_version,
                "provider_request_id": a.provider_request_id,
            } for a in attempts],
        }

        # Доказ твердого бюджету: факт сів НИЖЧЕ резерву, і жодної
        # нерозвʼязаної резервації не лишилось.
        for a in attempts:
            assert a.state not in ("reserved", "dispatched"), (
                "нерозвʼязана резервація", a.state)
            if a.state == "settled":
                assert a.actual_cost_usd is not None
                assert a.actual_cost_usd < a.reserved_max_usd

    await engine.dispose()
    return report


if __name__ == "__main__":
    smoke_report = asyncio.run(main())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(smoke_report, ensure_ascii=False, indent=1),
                   encoding="utf-8")
    print(json.dumps(smoke_report, ensure_ascii=False, indent=1))
