"""Застосункові операції присутності, що сягають шару звітів.

`api` і `services` не імпортують `app.report` напряму (борг прямих
звернень до двигуна заморожений тестом меж) — рендер живе тут, поруч з
рештою збирачів звітів застосунку.

Видів документа два, як і в аудиті: загальний і технічний. Дані для
обох збираються ОДНИМ шляхом — інакше два документи про той самий
прогін могли б розійтися числами, і клієнт мав би рацію не вірити
жодному.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.presence import PresenceRun
from app.report.presence_docx import filename_for as presence_filename
from app.report.presence_docx import render_presence_docx
from app.report.presence_owner_docx import render_presence_owner_docx
from app.services import presence_service

# Вид документа → рендер. Невідомий вид сюди не доходить: маршрут
# звіряє його зі списком і відповідає 404, а не мовчки віддає інший.
KINDS = ("general", "technical")


async def export_docx(
    session: AsyncSession, run: PresenceRun, *, lang: str = "en", kind: str = "technical"
) -> bytes:
    """Word-експорт прогону з персистованого — без мережі й провайдерів."""
    payload = await _payload(session, run, lang=lang)
    if kind == "general":
        return render_presence_owner_docx(**payload)
    return render_presence_docx(**payload)


def export_filename(run: PresenceRun, lang: str, kind: str) -> str:
    """Назва файлу називає сайт і вид: чотири документи не перезаписують один одного."""
    return presence_filename(run.url, lang, kind=kind)


async def _payload(
    session: AsyncSession, run: PresenceRun, *, lang: str
) -> dict[str, Any]:
    computed = await presence_service.run_metrics(session, run)
    observations = await presence_service.observations_for(session, run.id)
    return {
        "run": {
            "url": run.url, "brand": run.brand, "status": run.status,
            "created_at": run.created_at, "finished_at": run.finished_at,
            "observations_total": run.observations_total,
            "observations_ok": run.observations_ok,
            "deliverable": run.deliverable,
            "prompt_set_version": run.prompt_set_version,
            # Мова ЗАПИТАНЬ, а не документа. Набір промптів живе не в
            # усіх шістьох мовах, тож німецький документ цілком може
            # описувати англомовний прогін — і мусить це сказати.
            "languages": sorted(
                {
                    str(prompt.get("language"))
                    for prompt in (run.prompts or [])
                    if prompt.get("language")
                }
            ),
        },
        "metrics": computed["metrics"],
        "coverage": computed["coverage"],
        "observations": [
            {
                "provider": o.provider, "model": o.model, "mode": o.mode,
                "prompt_text": o.prompt_text, "status": o.status,
                "searched": o.searched,
                "brand_mentioned": o.brand_mentioned,
                "domain_cited": o.domain_cited,
                "answer_excerpt": o.answer_excerpt,
            }
            for o in observations
        ],
        # Усі шість локалей звітів; невідома мова падає на англійську.
        "lang": lang,
    }


__all__ = ["KINDS", "export_docx", "export_filename"]
