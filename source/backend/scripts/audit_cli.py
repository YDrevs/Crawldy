#!/usr/bin/env python3
"""Локальний запуск аудиту без БД і черги: python scripts/audit_cli.py https://example.com"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit.i18n import Locale
from app.audit.llm.models import MODEL_IDS
from app.audit.orchestrator import AuditOptions, rescore, run_audit
from app.audit.snapshot import dump as dump_snapshot
from app.audit.snapshot import load as load_snapshot
from app.audit.types import Strategy
from app.core.logging import configure_logging
from app.report import build_report, source_from_outcome
from app.report.docx import render_docx
from app.report.docx_owner import render_owner_docx
from app.report.owner_enrich import build_owner_extras

SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]


def _force_utf8_stdout() -> None:
    """Консоль Windows за замовчуванням у cp1251: українські рядки й '←' її валять."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            reconfigure(encoding="utf-8", errors="replace")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url", nargs="?", help="не потрібен разом із --from-snapshot")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--max-depth", type=int, default=1)
    parser.add_argument("--no-perf", action="store_true", help="пропустити performance-модуль")
    parser.add_argument("--json", action="store_true", help="сирий дамп issues")
    parser.add_argument("--report", action="store_true", help="повний JSON-звіт фази 1")
    parser.add_argument("--docx", metavar="PATH", help="зберегти Word-звіт у файл")
    parser.add_argument("--docx-owner", metavar="PATH", help="Word-звіт для власника")
    parser.add_argument(
        "--enrich", action="store_true", help="докласти пояснення від моделі у звіт власника"
    )
    parser.add_argument("--llms-txt", metavar="PATH", help="чернетка llms.txt")
    parser.add_argument("--lang", choices=[loc.value for loc in Locale], default=Locale.UK.value)
    parser.add_argument(
        "--llm-model", choices=list(MODEL_IDS), help="модель семантичного аналізу"
    )
    parser.add_argument("--no-llm", action="store_true", help="без семантичного аналізу")
    parser.add_argument(
        "--save-snapshot", metavar="PATH", help="зберегти зібране для перерахунку"
    )
    parser.add_argument(
        "--from-snapshot", metavar="PATH",
        help="перерахувати збережене замість краулу — без мережі",
    )
    args = parser.parse_args()

    _force_utf8_stdout()
    # У машинних режимах stdout має лишатися чистим JSON — логи йдуть у stderr.
    machine_output = args.json or args.report
    configure_logging(sys.stderr if machine_output else None)
    from app.audit.types import Module

    options = AuditOptions(
        max_pages=args.max_pages,
        max_depth=args.max_depth,
        strategies=[Strategy.MOBILE],
        # Прапорець вимикає рівно один модуль. Список тут був захардкоджений
        # ще до появи Module.TECH, і через це tech-чеки мовчки не виконувались
        # у кожному ручному прогоні з --no-perf.
        modules=set(Module) - {Module.PERFORMANCE} if args.no_perf else None,
        llm=False if args.no_llm else None,
        llm_model=args.llm_model,
    )
    if args.from_snapshot:
        # Перерахунок замість вимірювання: ті самі дані, нинішні правила.
        # Саме так порівнюються бали до і після зміни скорингу — інакше
        # різниця однаково пояснюється і сайтом, і нами.
        # CLI: читання файла нікого не блокує
        raw = Path(args.from_snapshot).read_text(encoding="utf-8")  # noqa: ASYNC240
        stored = json.loads(raw)
        outcome = rescore(load_snapshot(stored), options)
        args.url = outcome.context.entry_url
    else:
        if not args.url:
            parser.error("потрібен URL або --from-snapshot")
        outcome = await run_audit(args.url, options)

    if args.save_snapshot:
        Path(args.save_snapshot).write_text(  # noqa: ASYNC240
            json.dumps(dump_snapshot(outcome.context), ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        print(f"  знімок: {args.save_snapshot}", file=sys.stderr)

    locale = Locale(args.lang)
    if args.llms_txt:
        from app.report.llms_txt import build_llms_txt

        draft = build_llms_txt(outcome.context)
        Path(args.llms_txt).write_text(draft, encoding="utf-8")  # noqa: ASYNC240
        print(f"  llms.txt: {args.llms_txt} ({len(draft.splitlines())} рядків)")

    if args.docx or args.docx_owner:
        document = build_report(source_from_outcome(outcome, url=args.url), locale)
        # CLI: запис файлів перед виходом нікого не блокує
        if args.docx:
            Path(args.docx).write_bytes(render_docx(document, locale))  # noqa: ASYNC240
            print(f"  Word-звіт: {args.docx}")
        if args.docx_owner:
            extras = await build_owner_extras(document) if args.enrich else None
            if extras is not None and not extras.analysed:
                print(f"  розширення не вийшло: {extras.error}")
            Path(args.docx_owner).write_bytes(  # noqa: ASYNC240
                render_owner_docx(document, locale, extras)
            )
            print(f"  Звіт для власника: {args.docx_owner}")
        return 0

    if args.report:
        document = build_report(source_from_outcome(outcome, url=args.url), locale)
        print(json.dumps(document.to_json(), ensure_ascii=False, indent=2))
        return 0

    if args.json:
        print(json.dumps(
            {
                "overall": outcome.overall,
                "scores": outcome.scores,
                "issues": [
                    {
                        "code": i.code, "module": i.module.value, "severity": i.severity.value,
                        "title": i.title, "page": i.page_url,
                    }
                    for i in outcome.issues
                ],
                "degraded": [d.to_json() for d in outcome.degraded],
            },
            ensure_ascii=False, indent=2,
        ))
        return 0

    print(f"\n  {outcome.context.entry_url}")
    print(f"  Загальний скор: {outcome.overall}/100")
    for module, score in outcome.scores.items():
        print(f"    {module:<16} {score:>3}/100")
    print(f"  Сторінок: {len(outcome.context.pages)}   Проблем: {len(outcome.issues)}\n")

    ordered = sorted(outcome.issues, key=lambda i: SEVERITY_ORDER.index(i.severity.value))
    for issue in ordered[:40]:
        page = f"  ← {issue.page_url}" if issue.page_url else ""
        print(f"  [{issue.severity.value:<8}] {issue.module.value:<15} {issue.title}{page}")
    if len(ordered) > 40:
        print(f"  … ще {len(ordered) - 40}")
    if outcome.degraded:
        print(f"\n  Деградації: {'; '.join(str(d) for d in outcome.degraded)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
