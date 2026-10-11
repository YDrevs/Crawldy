"""Сирі величини детекторів — навіть коли жоден чек не спрацював.

## Навіщо

Знахідка каже, що поріг пройдено. Калібруванню потрібне те, чого в
знахідці немає: розподіл величини по всьому корпусу, включно з тими
сайтами, де поріг **не** пройдено. Інакше питання «чи правильний поріг»
не має даних — видно лише те, що поріг уже пропустив.

Саме на цьому будувалися рішення пунктів #9 і #11: близькі дублікати не
випущені, бо розподіл показав, де починаються хиби; поріг двозначності
підписів обрано за умовою, а не за бажаною кількістю спрацювань. Обидва
рішення були б неможливі без сирих чисел.

## Межа

Тут не робиться жодного висновку. Модуль повертає числа; що вони
означають — питання аналізу й людини.
"""

from __future__ import annotations

from typing import Any


def _safe(name: str, fn: Any) -> Any:
    """Одна невдала величина не має валити збір усіх інших."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 — це діагностика, а не продукт
        return {"error": f"{type(exc).__name__}: {exc}"}


def collect(ctx: Any) -> dict[str, Any]:
    """Величини всіх детекторів, які їх дешево віддають."""
    from app.audit import (
        anchor_text,
        duplicates,
        hreflang,
        link_evidence,
        mixed_content,
        redirects,
        render_diff,
        sitemap_audit,
        transport,
    )

    out: dict[str, Any] = {}

    out["crawl"] = _safe("crawl", lambda: {
        "pages_ok": len(ctx.ok_pages),
        "pages_total": len(ctx.pages),
        "urls_crawled": ctx.urls_crawled,
        "failed_urls": len(ctx.failed_urls),
        "rendered": len(ctx.renders),
        "renders_ok": sum(1 for r in ctx.renders.values() if r.rendered),
        "discovered_via": _provenance(ctx),
        "redirect_limited": len(ctx.redirect_limited),
    })

    out["render_delta"] = _safe("render_delta", lambda: _render_delta(ctx, render_diff))
    out["hreflang"] = _safe("hreflang", lambda: _hreflang(ctx, hreflang))
    out["sitemap"] = _safe("sitemap", lambda: _sitemap(ctx, sitemap_audit))
    out["redirects"] = _safe("redirects", lambda: _redirects(ctx, redirects))
    out["links"] = _safe("links", lambda: _links(ctx, link_evidence))
    out["anchor_text"] = _safe("anchor_text", lambda: _anchors(ctx, anchor_text))
    out["mixed_content"] = _safe("mixed_content", lambda: _mixed(ctx, mixed_content))
    out["duplicates"] = _safe("duplicates", lambda: _duplicates(ctx, duplicates))
    out["transport"] = _safe("transport", lambda: transport.analyse(ctx).coverage())
    return out


def _provenance(ctx: Any) -> dict[str, int]:
    found: dict[str, int] = {}
    for page in ctx.ok_pages:
        for source in page.discovered_via or ["unknown"]:
            found[source] = found.get(source, 0) + 1
    return dict(sorted(found.items()))


def _render_delta(ctx: Any, render_diff: Any) -> dict[str, Any]:
    diffs = render_diff.compare_all(ctx)
    comparable = [d for d in diffs if d.comparable]
    return {
        "compared": len(comparable),
        "not_comparable": len(diffs) - len(comparable),
        "reasons": sorted({d.reason for d in diffs if not d.comparable}),
        "changed": sum(1 for d in comparable if d.changed),
        "js_only_links": sum(len(d.links.only_after_render) for d in comparable),
        "fields_changed": sorted({f.field for d in comparable for f in d.fields}),
    }


def _hreflang(ctx: Any, hreflang: Any) -> dict[str, Any]:
    site = hreflang.collect(ctx)
    return {
        "observed": bool(ctx.hreflang_observed),
        "used": site.used,
        "declaring_pages": len(site.declaring),
        "annotations": sum(len(d.annotations) for d in site.declaring),
        "invalid": sum(len(d.invalid) for d in site.declaring),
        "sitemap_annotated": site.sitemap_annotated,
    }


def _sitemap(ctx: Any, sitemap_audit: Any) -> dict[str, Any]:
    audit = sitemap_audit.collect(ctx)
    return {
        **audit.coverage(),
        "by_reason": {r.value: len(e) for r, e in audit.by_reason().items()},
    }


def _redirects(ctx: Any, redirects: Any) -> dict[str, Any]:
    chains = redirects.chains(ctx.pages)
    return {
        "chains": len(chains),
        "lengths": sorted(c.length for c in chains),
        "repeated": sum(1 for c in chains if c.repeated),
        "landing_badly": sum(1 for c in chains if c.lands_badly),
    }


def _links(ctx: Any, link_evidence: Any) -> dict[str, Any]:
    destinations = link_evidence.collect(ctx)
    states: dict[str, int] = {}
    for destination in destinations.values():
        states[destination.state.value] = states.get(destination.state.value, 0) + 1
    return {
        "destinations": len(destinations),
        "observations": sum(d.links for d in destinations.values()),
        "by_state": dict(sorted(states.items())),
        "broken_with_sources": sum(
            1 for d in destinations.values() if d.broken and d.sources
        ),
    }


def _anchors(ctx: Any, anchor_text: Any) -> dict[str, Any]:
    analysis = anchor_text.analyse(ctx)
    return {
        **analysis.coverage(),
        "weak": len(analysis.weak),
        # Скільки різних цілей на фразу — величина, на якій стоїть поріг.
        "phrase_destinations": sorted(
            int(row["destinations"]) for row in analysis.by_phrase(limit=50)
        ),
    }


def _mixed(ctx: Any, mixed_content: Any) -> dict[str, Any]:
    analysis = mixed_content.analyse(ctx)
    handling: dict[str, int] = {}
    for reference in analysis.references:
        handling[reference.handling.value] = handling.get(reference.handling.value, 0) + 1
    return {
        **analysis.coverage(),
        "references": len(analysis.references),
        "by_handling": dict(sorted(handling.items())),
        "third_party": sum(1 for r in analysis.references if r.third_party),
    }


def _duplicates(ctx: Any, duplicates: Any) -> dict[str, Any]:
    analysis = duplicates.analyse(ctx)
    return {
        **analysis.coverage(),
        "exact_clusters": len(analysis.clusters),
        "cluster_sizes": sorted(len(c.members) for c in analysis.clusters),
        # Розподіл подібності — саме те, чого бракувало, щоб вирішити про
        # поріг близьких дублікатів. Лишається вимірюванням.
        "near_similarity": sorted((round(s, 3) for _a, _b, s in analysis.near),
                                  reverse=True)[:50],
    }


__all__ = ["collect"]
