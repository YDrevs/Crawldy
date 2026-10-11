"""Метрики присутності: чисельник, знаменник, N — і жодного зведеного бала.

Кожна метрика каже, з чого складається і чого НЕ означає. Збійні
клітинки виключені зі знаменників («не спостережено» ≠ «нуль»), брендові
й небрендові промпти не змішуються, родина доказу — synthetic — стоїть
у кожній відповіді явно.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.presence.contracts import (
    LIST_CATEGORIES,
    EvidenceFamily,
    Mode,
    ObservationStatus,
    Segment,
)

# Мінімум спостережень, щоб поруч зі співвідношенням зʼявилася частка у
# відсотках. Нижче — лише «x із N»: відсоток на пʼятьох клітинках був би
# фальшивою точністю. Це ДЕФОЛТ: політика домену може його змінити, і
# тоді число приходить параметром.
MIN_OBSERVATIONS_FOR_RATE = 20


@dataclass(slots=True)
class MetricValue:
    key: str
    numerator: int
    denominator: int
    rate: float | None            # None, поки спостережень замало
    unavailable: int              # клітинок поза знаменником
    provider_scope: list[str]
    prompt_scope: str             # unbranded | branded | list_prompts
    not_meaning: str              # ключ рядка «чого це не означає»

    def to_json(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "numerator": self.numerator,
            "denominator": self.denominator,
            "rate": self.rate,
            "unavailable": self.unavailable,
            "provider_scope": self.provider_scope,
            "prompt_scope": self.prompt_scope,
            "not_meaning": self.not_meaning,
            "evidence_family": EvidenceFamily.SYNTHETIC.value,
        }


def _rate(numerator: int, denominator: int, minimum: int) -> float | None:
    if denominator < minimum:
        return None
    return round(numerator / denominator, 2)


def _mode_of(row: dict[str, Any]) -> str:
    # Старі P0-рядки режиму не мають: тоді існував лише natural.
    return str(row.get("mode") or Mode.NATURAL.value)


def build_metrics(
    rows: list[dict[str, Any]], *,
    min_observations: int = MIN_OBSERVATIONS_FOR_RATE,
) -> dict[str, Any]:
    """Метрики з рядків спостережень (словники з БД чи записів раннера).

    Режими вимірювання НЕ змішуються: у кожного свій блок зі своїми
    знаменниками. Усередині режиму — метрики по кожному провайдеру
    окремо і зведення разом, плюс перелік спостережених доменів.
    Жодного «AI-балу» тут немає і не буде: одна непрозора цифра обіцяла
    б те, чого ми не міряли.
    """
    providers = sorted({r["provider"] for r in rows})
    modes_present = sorted({_mode_of(r) for r in rows}) or [Mode.NATURAL.value]

    by_mode: dict[str, Any] = {}
    for mode in modes_present:
        mode_rows = [r for r in rows if _mode_of(r) == mode]
        by_mode[mode] = {
            "per_provider": {
                name: _provider_metrics(
                    [r for r in mode_rows if r["provider"] == name],
                    [name], min_observations,
                )
                for name in providers
            },
            "combined": _provider_metrics(mode_rows, providers, min_observations),
        }

    domains: dict[str, int] = {}
    for r in rows:
        if r["status"] != ObservationStatus.OK.value:
            continue
        for host in r.get("observed_domains") or []:
            domains[host] = domains.get(host, 0) + 1
    observed = sorted(domains.items(), key=lambda kv: (-kv[1], kv[0]))

    return {
        "evidence_family": EvidenceFamily.SYNTHETIC.value,
        "providers": providers,
        "modes": by_mode,
        # Зворотна сумісність читачів P0: блоки верхнього рівня — це
        # режим natural (єдиний, що існував у P0).
        "per_provider": by_mode.get(Mode.NATURAL.value, {}).get("per_provider", {}),
        "combined": by_mode.get(Mode.NATURAL.value, {}).get("combined", {}),
        "observed_domains": [
            {"domain": host, "citations": count} for host, count in observed[:50]
        ],
        "min_observations_for_rate": min_observations,
    }


def _provider_metrics(
    rows: list[dict[str, Any]], scope: list[str], minimum: int
) -> dict[str, Any]:
    ok = [r for r in rows if r["status"] == ObservationStatus.OK.value]
    unavailable = len(rows) - len(ok)
    unbranded = [r for r in ok if r["segment"] == Segment.UNBRANDED.value]
    branded = [r for r in ok if r["segment"] == Segment.BRANDED.value]
    list_rows = [
        r for r in unbranded
        if r["category"] in {c.value for c in LIST_CATEGORIES}
    ]

    def metric(key: str, numerator: int, rows_in: list[dict[str, Any]],
               prompt_scope: str, not_meaning: str) -> dict[str, Any]:
        return MetricValue(
            key=key, numerator=numerator, denominator=len(rows_in),
            rate=_rate(numerator, len(rows_in), minimum),
            unavailable=unavailable, provider_scope=scope,
            prompt_scope=prompt_scope, not_meaning=not_meaning,
        ).to_json()

    return {
        "mention_presence": metric(
            "mention_presence",
            sum(1 for r in unbranded if r["brand_mentioned"]),
            unbranded, "unbranded",
            "not_consumer_ui_not_ranking",
        ),
        "citation_presence": metric(
            "citation_presence",
            sum(1 for r in unbranded if r["domain_cited"]),
            unbranded, "unbranded",
            "not_traffic_not_impressions",
        ),
        # Пряме посилання в тексті — окреме від цитати провайдера.
        "link_presence": metric(
            "link_presence",
            sum(1 for r in unbranded if r.get("domain_linked")),
            unbranded, "unbranded",
            "text_link_not_provider_citation",
        ),
        "recommendation_presence": metric(
            "recommendation_presence",
            sum(1 for r in list_rows if r.get("recommended")),
            list_rows, "list_prompts",
            "not_endorsement_not_position",
        ),
        "branded_citation": metric(
            "branded_citation",
            sum(1 for r in branded if r["domain_cited"]),
            branded, "branded",
            "branded_segment_separate",
        ),
        "searched_share": metric(
            "searched_share",
            sum(1 for r in ok if r["searched"]),
            ok, "all_observed",
            "provider_choice_not_site_property",
        ),
    }


def coverage(rows: list[dict[str, Any]], *, providers_configured: int,
             prompts_declared: int) -> dict[str, Any]:
    """Покриття прогону: скільки з замовленого справді спостережено."""
    ok = [r for r in rows if r["status"] == ObservationStatus.OK.value]
    return {
        "providers_observed": len({r["provider"] for r in ok}),
        "providers_configured": providers_configured,
        "prompts_observed": len({r["prompt_id"] for r in ok}),
        "prompts_declared": prompts_declared,
        "observations_total": len(rows),
        "observations_ok": len(ok),
        "unavailable_by_status": _status_counts(rows),
    }


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in rows:
        if r["status"] != ObservationStatus.OK.value:
            counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts
