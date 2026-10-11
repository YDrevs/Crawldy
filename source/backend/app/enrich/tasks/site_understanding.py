"""Задача A: розуміння сайту — структурний контекст, не знахідки.

Що це за бізнес, що він продає, кому, і які ролі відіграють прочитані
сторінки. Вихід — контекст для решти збагачення та для людини, що читає
звіт; він не створює знахідок, не має балів і не торкається скорингу.

Промпт і схема ведуть родовід від legacy `brief` (той самий принцип
«описуй лише написане, нічого не вигадуй»), але живуть окремо: спільний
код зшив би новий шлюз зі старим шляхом, який мусить лишатися вимкненим
і незачепленим. Розширення проти brief: тип сайту, ролі сторінок і
обовʼязкові посилання на джерела — кожне твердження вказує, звідки воно.

Назовні йде: origin, публічні URL, назви й обрізаний текст сторінок.
Нічого облікового, платіжного чи внутрішнього.
"""

from __future__ import annotations

from typing import Any

from app.enrich.contracts import TaskType
from app.enrich.tasks.base import TaskSpec, require_keys

# Бюджет входу — частина контракту, а не оптимізація: сайт на двадцять
# сторінок не має коштувати вдвадцятеро більше за сайт на одну.
MAX_PAGES = 8
MAX_PAGE_CHARS = 2500

# Схема виходу не мінялась — мінявся канонічний вхід (додано факти
# покриття) і промпт. Версії піднімаються рівно ті, що змінилися.
SCHEMA_VERSION = "1"
PROMPT_VERSION = "2"
TASK_VERSION = "2"

SiteUnderstandingSchema: dict[str, Any] = {
    "type": "object",
    "properties": {
        "site_kind": {
            "type": "string",
            "description": "What kind of site this is: e-commerce, SaaS, local service, "
            "portfolio, publisher, community, other — in your own words.",
        },
        "name": {"type": "string"},
        "tagline": {"type": "string", "description": "One line: what this company does."},
        "description": {"type": "string", "description": "Two or three sentences."},
        "offerings": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concrete products or services, as the site names them.",
        },
        "audience": {
            "type": "string",
            "description": "Who this is for, only if the pages state or clearly imply it.",
        },
        "page_roles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "One of the supplied page URLs."},
                    "role": {
                        "type": "string",
                        "description": "What this page does for a visitor, one phrase.",
                    },
                },
                "required": ["url", "role"],
                "additionalProperties": False,
            },
        },
        "source_urls": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The supplied page URLs this description is based on.",
        },
    },
    "required": [
        "site_kind",
        "name",
        "tagline",
        "description",
        "offerings",
        "audience",
        "page_roles",
        "source_urls",
    ],
    "additionalProperties": False,
}

SYSTEM = (
    "You are given several pages from one public website, plus facts about how much of "
    "the site was actually read. Describe the company exactly as these pages present it, "
    "using their own terms for products and services. "
    "Invent nothing: if the pages never say who the audience is, say so plainly. "
    "Every url you mention must be one of the supplied page URLs. "
    "Do not add claims about the business that the supplied text does not support.\n\n"
    "Coverage discipline:\n"
    "- Describe only what the pages you were given support.\n"
    "- When coverage is partial or insufficient, do not write as though you have seen the "
    "whole site, and do not imply the offering list or the audience is complete.\n"
    "- Distinguish 'observed on the pages read' from 'site-wide'. Never claim the latter "
    "unless every known page was read.\n"
    "- Where partial coverage materially limits a conclusion, say so in that conclusion "
    "rather than stating it with full confidence."
)


def _coverage_line(payload: dict[str, Any]) -> str:
    cov = payload.get("coverage") or {}
    if not cov:
        return "Crawl coverage: not supplied."
    return (
        f"Crawl coverage: {cov.get('level')} — {cov.get('pages_read')} pages read of "
        f"{cov.get('pages_known')} known ({cov.get('pages_unread')} never read, "
        f"{cov.get('pages_failed')} failed)."
    )


def render_prompt(payload: dict[str, Any]) -> str:
    pages = payload["pages"]
    joined = "\n\n".join(
        f"=== {page['url']}\n{page['title'] or '(no title)'}\n{page['text']}"
        for page in pages
    )
    return f"Site: {payload['origin']}\n{_coverage_line(payload)}\n\nPages:\n{joined}"


def validate(output: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Вигадана адреса — провал: контекст мусить бути простежуваним."""
    from app.enrich.contracts import TaskValidationError

    require_keys(output, tuple(SiteUnderstandingSchema["required"]))
    known = {page["url"] for page in payload["pages"]}

    for role in output.get("page_roles", []):
        if role.get("url") not in known:
            raise TaskValidationError(
                f"page_roles посилається на невідому адресу: {role.get('url')}"
            )
    unknown_sources = [url for url in output.get("source_urls", []) if url not in known]
    if unknown_sources:
        raise TaskValidationError(f"source_urls поза входом: {unknown_sources[:3]}")
    return output


def dry_output(payload: dict[str, Any]) -> dict[str, Any]:
    pages = payload["pages"]
    first_title = str(pages[0]["title"] or payload["origin"]) if pages else payload["origin"]
    return {
        "site_kind": "other",
        "name": first_title.split("—")[0].split("|")[0].strip(),
        "tagline": "dry-run: опис не генерувався",
        "description": "Детермінований вихід без виклику моделі.",
        "offerings": [],
        "audience": "не визначалась",
        "page_roles": [{"url": p["url"], "role": "page"} for p in pages[:3]],
        "source_urls": [p["url"] for p in pages],
    }


SITE_UNDERSTANDING = TaskSpec(
    type=TaskType.SITE_UNDERSTANDING,
    version=TASK_VERSION,
    prompt_version=PROMPT_VERSION,
    schema_version=SCHEMA_VERSION,
    system=SYSTEM,
    schema=SiteUnderstandingSchema,
    render_prompt=render_prompt,
    validate=validate,
    dry_output=dry_output,
)
