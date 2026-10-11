"""Персистентність адмін-політик AI-доменів.

Чисті правила політик живуть у пакетах доменів (`enrich.policy`,
`presence.policy`); тут — лише читання/запис рядка `ai_domain_settings`.
Два домени, два рядки, нуль спільного стану.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.enrich import policy as analysis_policy
from app.models.ai_settings import AiDomainSettings


async def load_analysis(session: AsyncSession) -> analysis_policy.AnalysisPolicy:
    row = await session.get(AiDomainSettings, analysis_policy.DOMAIN)
    return analysis_policy.from_stored(row.policy if row else None)


async def save_analysis(
    session: AsyncSession, policy_json: dict[str, Any]
) -> tuple[analysis_policy.AnalysisPolicy, list[str]]:
    policy = analysis_policy.from_stored(policy_json)
    errors = analysis_policy.validate(policy)
    if errors:
        return policy, errors
    row = await session.get(AiDomainSettings, analysis_policy.DOMAIN)
    if row is None:
        row = AiDomainSettings(domain=analysis_policy.DOMAIN)
        session.add(row)
    row.policy = analysis_policy.to_stored(policy)
    await session.flush()
    return policy, []
