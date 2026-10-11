"""Задача C: план виправлень — порядок, залежності й чесна сила твердження.

## Що показав пілот (v1 → v2)

Групування причин помʼякшувало свої висновки правильно («likely»,
«probably»), а план ті самі висновки подавав категорично. Найгірший
рядок пілота, web.dev:

    «Server response and third-party code (96% of the page) ARE THE
     UPSTREAM CAUSES of the measured mobile vitals»

Джерелом була група з `cause_confidence = likely`. План підвищив
гіпотезу до діагнозу — і саме цей текст побачив би клієнт у переліку
дій. Усі шість категоричних причинних фраз пілота знайшлися в планах,
жодної в групуванні.

## Як це припинено — структурою, а не словником

Кожен крок оголошує `causal_basis`, і валідація вимагає, щоб він **не
перевищував** впевненість груп, на які крок посилається. `unknown` у
джерелі означає, що крок не має права стверджувати причину взагалі.

Сканувати прозу на «caused by» було б хибним захистом: продукт працює
шістьма мовами, і чорний список англійських фраз не побачив би ані
німецького «verursacht durch», ані українського «спричинено». Сила
твердження мусить бути полем, а не інтонацією.

Назовні йде: refs знахідок, серйозність, детерміністичний ранг, id груп
із їхньою впевненістю, факти покриття. Внутрішніх ідентифікаторів немає.
"""

from __future__ import annotations

from typing import Any

from app.enrich.contracts import TaskType
from app.enrich.tasks.base import TaskSpec, require_keys

# v2: успадкування причинної впевненості від груп, факти покриття у вході.
SCHEMA_VERSION = "2"
PROMPT_VERSION = "2"
TASK_VERSION = "2"

# Сила причинного твердження кроку. `none` — крок нічого не стверджує про
# причину й спирається лише на спостережені знахідки.
CAUSAL_BASIS = ("supported", "likely", "possible", "none")

# Порядок сили: чим менше число, тим сильніша заявка. Використовується
# для перевірки «не сильніше за джерело».
_STRENGTH = {"supported": 3, "likely": 2, "possible": 1, "none": 0, "unknown": 0}

RemediationPlanSchema: dict[str, Any] = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    # `minimum` лишається в КАНОНІЧНІЙ схемі, навіть якщо
                    # чийсь структурний вихід його не приймає: обмеження —
                    # частина контракту Crawldy, а не побажання до чужого
                    # API. Переклад у діалект робить адаптер, а межу тримає
                    # `validate()` вже після відповіді.
                    "order": {"type": "integer", "minimum": 1},
                    "title": {"type": "string"},
                    "why_now": {
                        "type": "string",
                        "description": (
                            "Why this step sits at this position: dependencies on other "
                            "steps, shared work surface, what it unblocks. No effort "
                            "estimates, no cost, no outcome guarantees."
                        ),
                    },
                    "finding_refs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Input finding refs this step addresses.",
                    },
                    "group_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Cluster ids this step addresses.",
                    },
                    "causal_basis": {
                        "type": "string",
                        "enum": list(CAUSAL_BASIS),
                        "description": (
                            "How strongly this step may speak about a cause. It may never "
                            "exceed the cause_confidence of the clusters it references. "
                            "Use 'none' when the referenced clusters have no known cause — "
                            "then describe the work, not a diagnosis."
                        ),
                    },
                    "depends_on": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Orders of steps that should land first.",
                    },
                },
                "required": [
                    "order",
                    "title",
                    "why_now",
                    "finding_refs",
                    "group_ids",
                    "causal_basis",
                    "depends_on",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["steps"],
    "additionalProperties": False,
}

SYSTEM = (
    "You are given findings proven by a deterministic website audit, their deterministic "
    "priority ranks, clusters of related findings with an explicit cause confidence, and "
    "facts about how much of the site was actually read. Produce an ordered remediation "
    "plan.\n\n"
    "Grounding rules:\n"
    "- Every step must address findings or clusters from the input, referenced by their "
    "refs/ids. Never introduce a fix for a problem the input does not contain.\n"
    "- Never change or dispute the given severities.\n\n"
    "Causal honesty — this is the important part:\n"
    "- Each cluster arrives with a cause confidence: supported, likely, possible or "
    "unknown. Your step's causal_basis may never be stronger than the clusters it "
    "addresses.\n"
    "- supported: you may state the cause directly.\n"
    "- likely: write 'likely contributes', 'likely related'.\n"
    "- possible: write 'may contribute', 'a possible contributor'.\n"
    "- unknown: set causal_basis to 'none' and do NOT offer any causal explanation. "
    "Describe the work and what it addresses, and say plainly that the shared cause is "
    "not established.\n"
    "- A plan must never turn a hypothesis into a diagnosis.\n\n"
    "Coverage:\n"
    "- If only part of the site was read, do not turn incomplete coverage into a universal "
    "diagnosis, and keep the limitation visible where a step depends on it.\n\n"
    "Explain ordering through dependencies and shared work surfaces. Do not estimate "
    "engineering hours or money, and do not promise traffic, ranking or AI-visibility "
    "gains — none of that was measured."
)


def _coverage_line(payload: dict[str, Any]) -> str:
    cov = payload.get("coverage") or {}
    if not cov:
        return "Crawl coverage: not supplied."
    return (
        f"Crawl coverage: {cov.get('level')} — {cov.get('pages_read')} pages read of "
        f"{cov.get('pages_known')} known ({cov.get('pages_unread')} never read)."
    )


def render_prompt(payload: dict[str, Any]) -> str:
    findings = "\n".join(
        f"- ref={f['ref']} severity={f['severity']} priority_rank={f['rank']} :: {f['title']}"
        for f in payload["findings"]
    )
    groups = (
        "\n".join(
            f"- id={g['id']} cause_confidence={g.get('cause_confidence', 'unknown')} "
            f":: {g.get('cluster_summary', '')} :: refs={','.join(g['finding_refs'])}"
            for g in payload.get("groups", [])
        )
        or "(no clusters)"
    )
    site = payload.get("site") or "(no site context)"
    return (
        f"Site context: {site}\n{_coverage_line(payload)}\n\n"
        f"Findings:\n{findings}\n\nClusters:\n{groups}"
    )


def validate(output: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    """Незаземлений крок вилучається; впевненість не може зрости.

    Межі з канонічної схеми перевіряються ТУТ, а не покладаються на
    провайдера. Не кожен структурний вихід уміє `minimum` для цілих, і
    адаптер такого провайдера прибирає обмеження зі свого діалекту —
    отже локальна перевірка лишається єдиним місцем, де контракт справді
    тримається.
    """
    from app.enrich.contracts import TaskValidationError

    require_keys(output, ("steps",))
    known_refs = {f["ref"] for f in payload["findings"]}
    group_confidence = {
        g["id"]: str(g.get("cause_confidence", "unknown"))
        for g in payload.get("groups", [])
    }

    kept: list[dict[str, Any]] = []
    dropped = 0
    lowered = 0
    for step in output["steps"]:
        order = step.get("order")
        if not isinstance(order, int) or order < 1:
            raise TaskValidationError(f"крок із неприпустимим order: {order!r}")

        basis = str(step.get("causal_basis", "none"))
        if basis not in CAUSAL_BASIS:
            raise TaskValidationError(f"крок {order}: невідомий causal_basis «{basis}»")

        refs = [r for r in step.get("finding_refs", []) if r in known_refs]
        groups = [g for g in step.get("group_ids", []) if g in group_confidence]
        if not refs and not groups:
            dropped += 1
            continue

        # Стеля причинності: крок не сміє стверджувати впевненіше за
        # найсильнішу з груп, на які спирається. Без груп — без причини.
        ceiling = max((_STRENGTH[group_confidence[g]] for g in groups), default=0)
        if _STRENGTH[basis] > ceiling:
            allowed = next(b for b in CAUSAL_BASIS if _STRENGTH[b] == ceiling)
            basis = allowed
            lowered += 1

        kept.append(
            {**step, "finding_refs": refs, "group_ids": groups, "causal_basis": basis}
        )

    if not kept:
        raise TaskValidationError("жоден крок плану не спирається на відомі знахідки")

    kept.sort(key=lambda s: int(s["order"]))
    return {
        "steps": kept,
        "dropped_ungrounded_steps": dropped,
        # Скільки разів план намагався бути впевненішим за власне джерело.
        # Це метрика якості моделі, і ховати її не можна.
        "lowered_causal_basis": lowered,
    }


def dry_output(payload: dict[str, Any]) -> dict[str, Any]:
    """Детерміністичний пріоритет як є: заземлено й без причинних заявок."""
    return {
        "steps": [
            {
                "order": i,
                "title": f"Fix: {f['title']}",
                "why_now": "Порядок детерміністичного пріоритету (dry-run).",
                "finding_refs": [f["ref"]],
                "group_ids": [],
                "causal_basis": "none",
                "depends_on": [],
            }
            for i, f in enumerate(payload["findings"][:10], start=1)
        ]
    }


REMEDIATION_PLAN = TaskSpec(
    type=TaskType.REMEDIATION_PLAN,
    version=TASK_VERSION,
    prompt_version=PROMPT_VERSION,
    schema_version=SCHEMA_VERSION,
    system=SYSTEM,
    schema=RemediationPlanSchema,
    render_prompt=render_prompt,
    validate=validate,
    dry_output=dry_output,
)
