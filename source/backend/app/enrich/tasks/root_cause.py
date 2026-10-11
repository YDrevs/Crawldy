"""Задача B: кластери знахідок і — окремо — гіпотеза про причину.

## Чому кластер і причина розділені (v2)

Пілот на пʼяти сайтах дав 34 групи. Причина була **доведена рівно в
чотирьох**: там, де знахідки говорили про те саме значення (один телефон
у розмітці й на сторінці) або про ту саму відповідь сервера (кілька
відсутніх заголовків). Решта тридцять були корисними кластерами з
правдоподібним припущенням — але контракт v1 вимагав поля `hypothesis`
завжди, тож модель мусила вигадати причину, щоб заповнити схему.

Найяскравіше це видно на трьох групах доступності (web.dev, ka-dent,
linear.app): кластер там справжній і корисний — ці дефекти розумно
робити одним заходом, — а причина («спільні компоненти дизайн-системи»)
трималась лише на тому, що знахідки прийшли з одного запуску Lighthouse.
Спільний інструмент вимірювання не є спільною причиною.

Тому тепер:

- `cluster_summary` — що спостережено спільного. Тверджень про причину
  тут немає за визначенням.
- `cause_confidence` — `supported` / `likely` / `possible` / `unknown`.
- `cause_hypothesis` — обовʼязково порожня при `unknown`.
- `cause_evidence` — знахідки, що підтримують саме ПРИЧИНУ, окремо від
  тих, що утворюють кластер. Для `supported` вона не може бути порожня.

`unknown` — це повноцінна правильна відповідь, а не поразка.

## Покриття

Вхід несе канонічні факти покриття краулу. Без них модель на
gocplumbing.com написала «site-wide», прочитавши 3 сторінки з 10: вона
не знала, що сім не відповіли, бо ми їй цього не казали.

Назовні йде: issue_key, серйозність, модуль, кількість сторінок,
публічні URL прикладів, стислий доказ, факти покриття. Внутрішні
ідентифікатори не надсилаються.
"""

from __future__ import annotations

from typing import Any

from app.enrich.contracts import TaskType
from app.enrich.tasks.base import TaskSpec, require_keys

MAX_FINDINGS = 60
MAX_EVIDENCE_CHARS = 300

# v2: кластер відокремлено від причини, додано факти покриття у вхід.
SCHEMA_VERSION = "2"
PROMPT_VERSION = "2"
TASK_VERSION = "2"

# Порядок має значення: на ньому тримається правило, що план виправлень
# не може стверджувати причину впевненіше за її джерело.
CAUSE_CONFIDENCE = ("supported", "likely", "possible", "unknown")

RootCauseSchema: dict[str, Any] = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "description": "Short stable slug you assign."},
                    "cluster_summary": {
                        "type": "string",
                        "description": (
                            "What these findings demonstrably have in common, as observed "
                            "in the supplied evidence. State the pattern, not a cause."
                        ),
                    },
                    "finding_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "minItems": 1,
                        "description": "Refs copied exactly from the input findings.",
                    },
                    "cluster_evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Subset of this group's refs whose supplied evidence shows the "
                            "shared pattern itself."
                        ),
                    },
                    "cause_confidence": {
                        "type": "string",
                        "enum": list(CAUSE_CONFIDENCE),
                        "description": (
                            "supported = the supplied evidence directly shows one shared "
                            "source, value, response or mechanism. likely = strong inference, "
                            "cause not directly observed. possible = plausible, little causal "
                            "evidence. unknown = useful cluster, no responsible cause."
                        ),
                    },
                    "cause_hypothesis": {
                        "type": "string",
                        "description": (
                            "Why these findings may share a cause. MUST be an empty string "
                            "when cause_confidence is unknown. Never invent one to fill "
                            "this field."
                        ),
                    },
                    "cause_evidence": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Subset of this group's refs whose evidence supports the CAUSE "
                            "specifically, not merely the cluster. Empty when unknown."
                        ),
                    },
                },
                "required": [
                    "id",
                    "cluster_summary",
                    "finding_refs",
                    "cluster_evidence",
                    "cause_confidence",
                    "cause_hypothesis",
                    "cause_evidence",
                ],
                "additionalProperties": False,
            },
        },
        "ungrouped_refs": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Input refs that share no observable pattern with anything else.",
        },
    },
    "required": ["groups", "ungrouped_refs"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are given findings already proven by a deterministic website audit, plus facts "
    "about how much of the site was actually read.\n\n"
    "Your job has two separate parts, and you must not merge them.\n\n"
    "PART 1 — CLUSTER. Group findings that demonstrably share an observable pattern: the "
    "same pages, the same value, the same server response, the same asset class. Describe "
    "only what the supplied evidence shows. Grouping findings is valuable on its own, even "
    "when nobody knows why they occur together.\n\n"
    "PART 2 — CAUSE. Only then ask whether a shared cause is actually supported.\n"
    "- supported: the evidence itself shows one shared source, value, response or mechanism.\n"
    "- likely: strong inference from the evidence, but the cause was not directly observed.\n"
    "- possible: plausible, with little causal evidence.\n"
    "- unknown: you have a useful cluster and no responsible explanation.\n\n"
    "Rules you must follow:\n"
    "- Co-occurrence is NOT causality. Findings appearing together prove nothing about why.\n"
    "- Coming from the same detector, the same module or the same audit/Lighthouse run is "
    "NOT evidence of a shared cause. It only means one tool measured them together.\n"
    "- 'A shared template/CMS/theme causes this' is a hypothesis unless the supplied "
    "evidence directly shows it — for example the same field missing on every page read.\n"
    "- Prefer returning cause_confidence=unknown with an empty hypothesis over inventing a "
    "weak cause. An honest unknown is a correct answer, not a failure.\n"
    "- Never reference a finding that is not in the input. Never invent a finding.\n"
    "- Respect coverage: if only part of the site was read, do not describe anything as "
    "site-wide, and let partial coverage lower your confidence in broad causes.\n"
    "- Say 'on the pages read' rather than 'site-wide' whenever coverage is not full."
)


def _coverage_line(payload: dict[str, Any]) -> str:
    cov = payload.get("coverage") or {}
    if not cov:
        return "Crawl coverage: not supplied."
    return (
        f"Crawl coverage: {cov.get('level')} — {cov.get('pages_read')} pages read of "
        f"{cov.get('pages_known')} known ({cov.get('pages_unread')} never read, "
        f"{cov.get('pages_failed')} failed). Statements may only describe pages that were read."
    )


def render_prompt(payload: dict[str, Any]) -> str:
    lines = []
    for f in payload["findings"]:
        examples = ", ".join(f.get("examples", [])[:3])
        lines.append(
            f"- ref={f['ref']} module={f['module']} severity={f['severity']} "
            f"pages={f['pages']} scope={f.get('scope', 'unknown')} :: {f['title']}"
            + (f" :: examples: {examples}" if examples else "")
            + (f" :: evidence: {f['evidence']}" if f.get("evidence") else "")
        )
    site = payload.get("site") or "(no site context)"
    return (
        f"Site context: {site}\n{_coverage_line(payload)}\n\nFindings:\n" + "\n".join(lines)
    )


def validate(output: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Кластер мусить бути заземлений, причина — або доведена, або відсутня.

    Невідоме посилання валить валідацію цілком, а не мовчки викидається:
    мовчазне чищення сховало б від журналу саме те, заради чого існує
    бенчмарк.
    """
    from app.enrich.contracts import TaskValidationError

    require_keys(output, ("groups", "ungrouped_refs"))
    known = {f["ref"] for f in payload["findings"]}

    clean_groups: list[dict[str, Any]] = []
    for group in output["groups"]:
        gid = group.get("id")
        refs = list(group.get("finding_refs", []))
        unknown = [r for r in refs if r not in known]
        if unknown:
            raise TaskValidationError(
                f"група «{gid}» посилається на неіснуючі знахідки: {unknown[:3]}"
            )
        if not refs:
            raise TaskValidationError(f"група «{gid}» без жодної знахідки")

        confidence = group.get("cause_confidence")
        if confidence not in CAUSE_CONFIDENCE:
            raise TaskValidationError(f"група «{gid}»: невідома впевненість «{confidence}»")

        in_group = set(refs)
        for field in ("cluster_evidence", "cause_evidence"):
            stray = [r for r in group.get(field, []) if r not in in_group]
            if stray:
                raise TaskValidationError(
                    f"група «{gid}»: {field} посилається поза власні знахідки: {stray[:3]}"
                )

        hypothesis = str(group.get("cause_hypothesis", "")).strip()
        cause_evidence = list(group.get("cause_evidence", []))

        if confidence == "unknown":
            # Головне правило v2: не вигадувати причину заради поля.
            if hypothesis:
                raise TaskValidationError(
                    f"група «{gid}»: причина невідома, але гіпотезу все одно написано"
                )
            if cause_evidence:
                raise TaskValidationError(
                    f"група «{gid}»: причина невідома, але доказ причини наведено"
                )
        else:
            if not hypothesis:
                raise TaskValidationError(
                    f"група «{gid}»: заявлено впевненість «{confidence}» без гіпотези"
                )
            if confidence == "supported" and not cause_evidence:
                raise TaskValidationError(
                    f"група «{gid}»: «supported» без жодного доказу самої причини"
                )

        clean_groups.append(
            {
                **group,
                # Відсутня причина зберігається як null, а не порожній
                # рядок: артефакт мусить читатися однозначно.
                "cause_hypothesis": hypothesis or None,
                "cause_evidence": cause_evidence,
            }
        )

    unknown_loose = [ref for ref in output["ungrouped_refs"] if ref not in known]
    if unknown_loose:
        raise TaskValidationError(f"ungrouped_refs поза входом: {unknown_loose[:3]}")

    return {"groups": clean_groups, "ungrouped_refs": list(output["ungrouped_refs"])}


def dry_output(payload: dict[str, Any]) -> dict[str, Any]:
    """Групування за модулем: заземлене, і причину чесно не називає."""
    by_module: dict[str, list[str]] = {}
    for f in payload["findings"]:
        by_module.setdefault(str(f["module"]), []).append(str(f["ref"]))
    groups = [
        {
            "id": f"module-{module}",
            "cluster_summary": f"Знахідки модуля {module} (детермінований прогін).",
            "finding_refs": refs,
            "cluster_evidence": [],
            # Спільний модуль — не причина, і сухий прогін це підтверджує.
            "cause_confidence": "unknown",
            "cause_hypothesis": "",
            "cause_evidence": [],
        }
        for module, refs in by_module.items()
        if len(refs) > 1
    ]
    grouped = {ref for g in groups for ref in g["finding_refs"]}
    return {
        "groups": groups,
        "ungrouped_refs": [f["ref"] for f in payload["findings"] if f["ref"] not in grouped],
    }


ROOT_CAUSE_GROUPING = TaskSpec(
    type=TaskType.ROOT_CAUSE_GROUPING,
    version=TASK_VERSION,
    prompt_version=PROMPT_VERSION,
    schema_version=SCHEMA_VERSION,
    system=SYSTEM,
    schema=RootCauseSchema,
    render_prompt=render_prompt,
    validate=validate,
    dry_output=dry_output,
)
