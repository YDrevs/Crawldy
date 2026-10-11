"""Командний рядок бенчмарку: run, resume, retry, analyze, review.

    python scripts/benchmark/cli.py run     --corpus scripts/samples/corpus.yaml
    python scripts/benchmark/cli.py run     --corpus … --limit 5
    python scripts/benchmark/cli.py retry   --corpus …
    python scripts/benchmark/cli.py analyze --run runs/<run_id>
    python scripts/benchmark/cli.py review  --run runs/<run_id> --out review.json

`run` без прапорців продовжує вже початий прогін: ідентифікатор
детермінований за складом корпусу, конфігурацією й комітом.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.benchmark import analyzer, corpus_check, manifest, review
from scripts.benchmark.config import RunConfig
from scripts.benchmark.results import ResultStore
from scripts.benchmark.runner import Runner

DEFAULT_ROOT = Path("benchmark/runs")


def _config(args: argparse.Namespace) -> RunConfig:
    return RunConfig(
        max_pages=args.max_pages,
        render=not args.no_render,
        render_max_pages=args.render_max_pages,
        concurrency=args.concurrency,
        site_timeout_s=args.site_timeout,
    )


def _use_scratch(directory: str) -> str:
    """Перенести тимчасові файли процесу в задану теку.

    Знімки й результати кладе `--root`, а Playwright пише профілі й дампи
    в системний TEMP — тобто на зовсім інший том. Прогін, налаштований на
    просторий диск, усе одно заповнив би системний, і зупинився б не там,
    де його вимірювали.

    Ставиться до першого імпорту рушія: `tempfile` кешує теку при першому
    зверненні, а Playwright успадковує оточення процесу.
    """
    import os
    import tempfile

    path = Path(directory).resolve()
    path.mkdir(parents=True, exist_ok=True)
    for name in ("TMPDIR", "TEMP", "TMP"):
        os.environ[name] = str(path)
    tempfile.tempdir = str(path)
    return str(path)


def _runner(args: argparse.Namespace) -> Runner:
    corpus = manifest.load(args.corpus)
    for problem in corpus.problems:
        print(f"корпус: {problem}", file=sys.stderr)
    if not corpus.active:
        raise SystemExit("у корпусі немає жодного увімкненого сайту")
    return Runner(
        corpus,
        _config(args),
        Path(args.root),
        label=args.label,
        min_free=args.min_free_gb * 1024**3,
    )


def _report(store: ResultStore, known: list[str] | None) -> analyzer.Analysis:
    return analyzer.analyse(store.latest(), known_codes=known)


def _known_codes() -> list[str]:
    from app.audit.checks import all_checks

    return sorted({c.code for c in all_checks()})


def _locate(run: str, root: Path) -> Path:
    """Знайти теку прогону за ідентифікатором або шляхом.

    `ResultStore` створює теку, якої немає, — це правильно для запису й
    небезпечно для читання: аналіз за ідентифікатором мовчки робив
    порожню теку й повідомляв «немає рядків», тобто описував себе, а не
    прогін. Тут шлях мусить існувати, інакше помилка з переліком того,
    що є насправді.
    """
    for candidate in (Path(run), root / run):
        if (candidate / "results.jsonl").exists():
            return candidate
    known = sorted(p.name for p in root.glob("*") if (p / "results.jsonl").exists())
    tail = (
        "відомі прогони:\n" + "\n".join(f"  {name}" for name in known)
        if known
        else f"у {root} немає жодного прогону з результатами"
    )
    raise SystemExit(f"прогону «{run}» немає ні за шляхом, ні в {root}.\n{tail}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Прогін і аналіз корпусу Crawldy")
    sub = parser.add_subparsers(dest="command", required=True)

    for name in ("run", "retry"):
        p = sub.add_parser(name)
        p.add_argument("--corpus", required=True)
        p.add_argument("--root", default=str(DEFAULT_ROOT))
        p.add_argument("--label", default="")
        p.add_argument("--limit", type=int, default=None)
        p.add_argument("--max-pages", type=int, default=25)
        p.add_argument("--render-max-pages", type=int, default=3)
        p.add_argument("--no-render", action="store_true")
        p.add_argument("--concurrency", type=int, default=3)
        p.add_argument("--site-timeout", type=int, default=600)
        p.add_argument(
            "--scratch",
            default="",
            help="тека для тимчасових файлів (Playwright, профілі браузера). "
                 "Без неї вони йдуть у системний TEMP — і на тому, де мало "
                 "місця, прогін заповнить його повз --root",
        )
        p.add_argument("--min-free-gb", type=int, default=20,
                       help="запас вільного місця на томі прогону")

    v = sub.add_parser("validate")
    v.add_argument("--corpus", required=True)
    v.add_argument("--expect", type=int, default=None,
                   help="скільки записів має бути; без нього кількість не перевіряється")
    v.add_argument("--out", default="")

    for name in ("analyze", "review"):
        p = sub.add_parser(name)
        p.add_argument("--run", required=True, help="ідентифікатор прогону або шлях до теки")
        p.add_argument("--root", default=str(DEFAULT_ROOT))
        p.add_argument("--out", default="")

    args = parser.parse_args()

    if args.command == "validate":
        corpus = manifest.load(args.corpus)
        for problem in corpus.problems:
            print(f"корпус: {problem}", file=sys.stderr)
        report = corpus_check.check(corpus.active, expected=args.expect)
        print("\n".join(corpus_check.lines(report)))
        if args.out:
            Path(args.out).write_text(
                json.dumps(report.as_dict(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        # Ненульовий код — щоб перевірку можна було поставити перед
        # запуском у скрипті й не читати очима.
        return 0 if report.ok else 1

    if args.command in ("run", "retry"):
        if args.scratch:
            print(f"тимчасові файли: {_use_scratch(args.scratch)}", flush=True)
        runner = _runner(args)
        summary = asyncio.run(
            runner.run(retry_failed=args.command == "retry", limit=args.limit)
        )
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0

    store = ResultStore(_locate(args.run, Path(args.root)))
    if args.command == "analyze":
        found = _report(store, _known_codes())
        print("\n".join(analyzer.summary_lines(found)))
        target = Path(args.out) if args.out else store.directory / "analysis.json"
        target.write_text(
            json.dumps(found.as_dict(), ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        print(f"\nповні дані: {target}")
        return 0

    queue = review.build(store.latest())
    target = Path(args.out) if args.out else store.directory / "review.json"
    target.write_text(
        json.dumps(queue, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    total = sum(len(v) for v in queue.values())
    print(f"черга на перегляд: {total} прикладів по {len(queue)} детекторах -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
