"""Розподіл пулу кандидатів — до відбору, а не після.

## Навіщо дивитися на пул окремо

Джерело — це спосіб знайти сайти, а не модель того, яким буває веб.
Wikidata знає організації, про які написали статтю, тож її природний
розподіл тягне в бік шкіл, громад і музеїв. Якщо мовчки взяти з пулу
перші тисячу, корпус успадкує перекіс джерела й видасть його за
властивість вебу.

Тому пул спершу міряють, і лише потім із нього **навмисно** відбирають.
Перекіс пулу — не вирок: він стає вироком тільки тоді, коли в
недопредставленому сегменті бракує кандидатів на квоту.

## Що тут не рахується

Нічого не добудовується здогадом. Сайт без країни рахується в «невідомо»,
а не розподіляється за доменною зоною: `.com` не означає США, `.io` не
означає нічого. Невідоме лишається невідомим і в числах теж.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


def _tld(url: str) -> str:
    host = url.split("//")[-1].split("/")[0].split(":")[0]
    return host.rsplit(".", 1)[-1] if "." in host else ""


def summarise(joined: list[dict[str, Any]]) -> dict[str, Any]:
    """Пул → числа. `joined` — кандидат плюс його перевірка."""
    from scripts.samples.segments import segment_for

    for row in joined:
        # Сегмент береться з таблиці відображення, а не з того, що
        # записав збирач. Інакше виправлення таксономії довелося б
        # робити повторним збором — тобто новими запитами до джерела.
        if row.get("source") != "curated":
            row["segment"] = segment_for(row.get("klass", ""), row.get("segment", "other"))
    alive = [r for r in joined if r.get("alive")]
    return {
        "candidates": len(joined),
        "alive": len(alive),
        "dead": len(joined) - len(alive),
        "sources": dict(Counter(r.get("source", "?") for r in alive).most_common()),
        "segments": dict(Counter(r.get("segment", "other") for r in alive).most_common()),
        "classes": dict(Counter(r.get("klass", "?") for r in alive).most_common(24)),
        "countries": dict(
            Counter(r.get("country") or "невідомо" for r in alive).most_common(28)
        ),
        "languages": dict(
            Counter((r.get("lang") or "невідомо").split("-")[0] for r in alive).most_common(24)
        ),
        "tlds": dict(Counter(_tld(r.get("url", "")) for r in alive).most_common(24)),
        "tags": dict(Counter(t for r in alive for t in (r.get("tags") or [])).most_common(24)),
        "untagged": sum(1 for r in alive if not r.get("tags")),
        "unknown_country": sum(1 for r in alive if not r.get("country")),
        "unknown_lang": sum(1 for r in alive if not r.get("lang")),
        "with_sitemap": sum(1 for r in alive if r.get("has_sitemap")),
        "redirected": sum(1 for r in alive if r.get("redirected")),
        "excluded_adult": sum(
            1 for r in joined if r.get("excluded_reason") == "adult_content"
        ),
        "dead_reasons": dict(
            Counter(
                str(r.get("error") or r.get("status") or "?")
                for r in joined
                if not r.get("alive") and not r.get("excluded_reason")
            ).most_common(14)
        ),
    }


def concentration(summary: dict[str, Any], field: str, limit: float = 0.30) -> list[str]:
    """Де одна категорія зʼїдає забагато пулу."""
    total = max(1, summary["alive"])
    return [
        f"{field}: {name} = {count / total:.0%} пулу"
        for name, count in summary.get(field, {}).items()
        if count / total > limit
    ]


def lines(summary: dict[str, Any], title: str = "ПУЛ КАНДИДАТІВ") -> list[str]:
    out = [
        f"== {title} ==",
        f"кандидатів {summary['candidates']}, живих {summary['alive']}, "
        f"мертвих {summary['dead']}",
        f"з картою сайту: {summary['with_sitemap']} | після перенаправлень: "
        f"{summary['redirected']}",
        "",
    ]

    def block(name: str, key: str, width: int = 16, top: int = 100) -> None:
        out.append(f"{name}:")
        for label, count in list(summary.get(key, {}).items())[:top]:
            out.append(f"  {label[:width]:{width}} {count}")
        out.append("")

    block("джерела", "sources", 26)
    block("сегменти (з джерела)", "segments")
    block("країни (з джерела)", "countries", 16, 18)
    block("мови (з <html lang>)", "languages", 16, 16)
    block("зони", "tlds", 16, 16)
    block("теґи (побачені)", "tags", 16, 16)
    out += [
        f"без теґів      : {summary['untagged']}",
        f"країна невідома: {summary['unknown_country']}",
        f"мова невідома  : {summary['unknown_lang']}",
    ]
    return out


__all__ = ["concentration", "lines", "summarise"]
