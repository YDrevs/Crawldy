"""Черга на перегляд людиною: приклади, а не висновки.

## Навіщо

Статистика каже, що чек спрацював на 96% сайтів. Вона не каже, чи це
правда. Відповідь дає лише погляд на приклади — і саме так уже двічі
ловилися дефекти: `perf.responsive_images` карав SVG-іконки, а «порожній
текст посилання» описував нашу власну дедуплікацію. Обидва виглядали як
нормальні числа.

## Що таке добра черга

Не «двадцять спрацювань поспіль». Для рішення потрібні три речі поруч:
де чек спрацював, де мовчав **маючи всі дані**, і де величина близька до
порога. Остання найцінніша: саме там поріг або виправдовує себе, або ні.

## Детермінованість

Вибір сталий: той самий прогін дає ту саму чергу. Інакше двоє людей
переглянуть різні приклади й не зможуть порівняти висновки.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any

# Скільки прикладів кожного роду. Більше людина не подивиться уважно, а
# неуважний перегляд гірший за жоден: він дає хибну впевненість.
PER_KIND = 8

# Детектори, які зʼявилися або змінилися у пунктах #2–#12 — саме їх і
# треба звірити з дійсністю перед калібруванням.
NEW_IN_COVERAGE = (
    "llm.ai_crawler_access",
    "seo.render_delta",
    "seo.hreflang_invalid",
    "seo.hreflang_reciprocity",
    "seo.hreflang_conflict",
    "seo.hreflang_broken",
    "seo.hreflang_missing",
    "seo.redirect_chain",
    "seo.redirect_loop",
    "seo.redirect_target",
    "seo.sitemap_consistency",
    "seo.broken_links",
    "seo.anchor_text",
    "seo.duplicate_content",
    "tech.mixed_content",
    "tech.transport",
)

# Де шукати величину, на якій стоїть поріг кожного детектора. Порожньо —
# межового випадку для нього не буває, лишаються спрацювання й тиша.
_BORDERLINE: dict[str, tuple[str, str]] = {
    "seo.anchor_text": ("anchor_text", "phrase_destinations"),
    "seo.duplicate_content": ("duplicates", "near_similarity"),
    "seo.redirect_chain": ("redirects", "lengths"),
    "seo.sitemap_consistency": ("sitemap", "checked"),
    "seo.render_delta": ("render_delta", "js_only_links"),
}


@dataclass(slots=True)
class Case:
    """Один приклад на перегляд."""

    detector: str
    kind: str  # fired | silent | borderline
    site_id: str
    url: str
    segment: str
    snapshot: str
    note: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "detector": self.detector,
            "kind": self.kind,
            "site_id": self.site_id,
            "url": self.url,
            "segment": self.segment,
            "snapshot": self.snapshot,
            "note": self.note,
            "evidence": self.evidence,
        }


def _order(site_id: str, detector: str) -> str:
    """Сталий, але не алфавітний порядок.

    Алфавіт дав би щоразу ті самі перші сайти корпусу — і перегляд
    описував би початок списку, а не корпус.
    """
    return hashlib.blake2b(f"{detector}|{site_id}".encode(), digest_size=8).hexdigest()


def _spread_by_segment(cases: list[Case], limit: int) -> list[Case]:
    """По черзі з кожного сегмента, поки не набереться потрібне число.

    Перегляд, що складається з десяти магазинів, нічого не каже про
    документацію — а різні типи сайтів саме там і розходяться.
    """
    buckets: dict[str, list[Case]] = {}
    for case in sorted(cases, key=lambda c: _order(c.site_id, c.detector)):
        buckets.setdefault(case.segment, []).append(case)
    chosen: list[Case] = []
    while len(chosen) < limit and any(buckets.values()):
        for segment in sorted(buckets):
            if not buckets[segment]:
                continue
            chosen.append(buckets[segment].pop(0))
            if len(chosen) >= limit:
                break
    return chosen


def build(rows: list[dict[str, Any]], *, detectors: tuple[str, ...] = NEW_IN_COVERAGE,
          per_kind: int = PER_KIND) -> dict[str, list[dict[str, Any]]]:
    """Черга на перегляд: спрацювання, тиша й межові випадки."""
    ok = [r for r in rows if r.get("outcome") == "ok"]
    queue: dict[str, list[dict[str, Any]]] = {}

    for detector in detectors:
        fired: list[Case] = []
        silent: list[Case] = []
        borderline: list[Case] = []

        for row in ok:
            hits = [f for f in (row.get("findings") or []) if f.get("code") == detector]
            case = Case(
                detector=detector,
                kind="fired",
                site_id=str(row["site_id"]),
                url=str(row.get("url") or ""),
                segment=str(row.get("segment") or "other"),
                snapshot=str(row.get("snapshot") or ""),
            )
            if hits:
                case.evidence = {
                    "issue_keys": sorted({str(h.get("issue_key")) for h in hits}),
                    "count": len(hits),
                    "sample": (hits[0].get("evidence") or {}),
                }
                fired.append(case)
                continue

            measured = row.get("measurements") or {}
            source = _BORDERLINE.get(detector)
            if source is not None:
                values = (measured.get(source[0]) or {}).get(source[1])
                if values not in (None, [], 0):
                    borderline.append(Case(
                        detector=detector, kind="borderline", site_id=case.site_id,
                        url=case.url, segment=case.segment, snapshot=case.snapshot,
                        note="величина є, але чек не спрацював",
                        evidence={source[1]: values},
                    ))
                    continue

            # Тиша варта перегляду лише там, де дані для висновку були.
            if (row.get("coverage") or {}).get("pages_ok"):
                silent.append(Case(
                    detector=detector, kind="silent", site_id=case.site_id, url=case.url,
                    segment=case.segment, snapshot=case.snapshot,
                    note="сторінки прочитано, чек мовчав",
                    evidence={"measurements": _relevant(measured, detector)},
                ))

        chosen = (
            _spread_by_segment(fired, per_kind)
            + _spread_by_segment(borderline, per_kind)
            + _spread_by_segment(silent, per_kind)
        )
        if chosen:
            queue[detector] = [c.as_dict() for c in chosen]
    return queue


def _relevant(measured: dict[str, Any], detector: str) -> dict[str, Any]:
    """Лише той шматок вимірювань, що стосується цього чека."""
    family = detector.split(".")[-1].split("_")[0]
    for key in (family, detector.split(".")[-1]):
        if key in measured:
            return {key: measured[key]}
    return {}


__all__ = ["NEW_IN_COVERAGE", "PER_KIND", "Case", "build"]
