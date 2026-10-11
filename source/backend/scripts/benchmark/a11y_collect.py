"""Збір знаменника доступності по замороженому корпусу.

Дослідницька інфраструктура. Продуктового шляху тут немає й не буде:
жоден маршрут API сюди не веде, аудит цього коду не викликає, а
результат нікуди, крім каталогу прогону, не потрапляє.

Питання, на яке збираються дані: бал доступності Lighthouse — це середнє
по ЗАСТОСОВНИХ перевірках, і без їх кількості він не читається. madpc.gr
має 37 при 3 провалах з 4 застосовних, web.dev — 90 при тих самих 3
провалах з 29. Щоб вирішити, коли ми маємо право підсумовувати, а коли
лише перелічувати знайдене, потрібен виміряний розподіл знаменника.

Чому не повний аудит: лічильники цілком походять з однієї відповіді PSI.
Ані краул, ані рендер, ані чеки, ані скоринг у них не беруть участі —
тож нічна вибірка коштувала б ніч заради даних, які беруться за годину.

Чому власний HTTP-виклик, а не `PsiProvider.measure()`: провайдер віддає
`PerformanceResult`, а нам потрібен ще й `fetchTime` із сирої відповіді —
єдине, чим свіжий вимір відрізняється від кешованого повтору. Логіка
ПІДРАХУНКУ при цьому не дублюється: рахує той самий
`_parse_accessibility`, що й у продукті. Розійтися з продуктом у тому,
що саме вважається застосовним, було б найдорожчою помилкою цього збору.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.audit.performance.psi import ENDPOINT, _parse_accessibility
from app.audit.types import PerformanceResult, Strategy
from app.core.config import settings
from scripts.benchmark import guard, manifest
from scripts.benchmark.manifest import Manifest, Site
from scripts.benchmark.results import ResultStore, SiteResult

# Паралельність зумисне скромна. Квота PSI дозволяє 240 запитів на
# хвилину, ми беремо близько 25 — бо межа, у яку ми впираємось, не
# квота, а чужі сервери й власний канал. Урок корпусної проби: при
# паралельності 24 вимірювався наш власний канал, а не сайти.
CONCURRENCY = 8
TIMEOUT_S = 120.0
MAX_ATTEMPTS = 3

# Збої, які бувають тимчасовими. 400 на непідтримувану адресу від
# повторення не полагодиться, і повторювати його означає лише довше
# чекати на той самий результат.
RETRIABLE = frozenset({"transport", "http_429", "http_500", "http_502", "http_503"})

# Правило вибірки для повторного виміру. Не `random.sample`: воно
# залежить від реалізації RNG. Хеш від сталої солі й `site_id` дає ту
# саму сотню з половиною на будь-якій машині й будь-якій версії Python,
# доки не змінився склад корпусу — а його зміну ловить `fingerprint()`.
REPEAT_SALT = "crawldy.a11y.repeat.v1"
REPEAT_SIZE = 150


def repeat_sample(sites: list[Site], size: int = REPEAT_SIZE) -> list[Site]:
    """Детермінований підкорпус для оцінки повторюваності."""
    ordered = sorted(
        sites,
        key=lambda s: hashlib.blake2b(
            f"{REPEAT_SALT}:{s.site_id}".encode(), digest_size=16
        ).hexdigest(),
    )
    return ordered[:size]


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _commit() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        )
        return out.stdout.strip()[:12]
    except OSError:
        return ""


async def _measure(site: Site, client: httpx.AsyncClient, attempt: int) -> SiteResult:
    """Один вимір одного сайту. Порожнеча лишається порожнечею."""
    result = SiteResult(
        site_id=site.site_id,
        url=site.url,
        run_id="",
        segment=site.segment,
        tags=list(site.tags),
        started_at=_now(),
        attempt=attempt,
    )
    params: dict[str, Any] = {
        "url": site.url,
        "strategy": Strategy.MOBILE.value,
        "category": ["accessibility"],
    }
    if settings.psi_api_key:
        params["key"] = settings.psi_api_key

    began = time.monotonic()
    try:
        response = await client.get(ENDPOINT, params=params)
    except (httpx.HTTPError, ValueError) as exc:
        result.outcome, result.failure = "failed", "transport"
        result.failure_detail = f"{type(exc).__name__}: {exc}"[:300]
        result.finished_at = _now()
        result.duration_s = round(time.monotonic() - began, 2)
        return result

    if response.status_code != 200:
        result.outcome = "failed"
        result.failure = f"http_{response.status_code}"
        result.failure_detail = response.text[:300]
        result.finished_at = _now()
        result.duration_s = round(time.monotonic() - began, 2)
        return result

    try:
        payload = response.json()
    except ValueError as exc:
        result.outcome, result.failure = "failed", "bad_json"
        result.failure_detail = str(exc)[:300]
        result.finished_at = _now()
        result.duration_s = round(time.monotonic() - began, 2)
        return result

    measured = PerformanceResult(provider="psi", strategy=Strategy.MOBILE, url=site.url)
    _parse_accessibility(payload, measured)
    lighthouse = payload.get("lighthouseResult") or {}

    # Категорії немає у відповіді — це не нуль перевірок, це відсутність
    # даних. Лічильники лишаються None, і аналіз мусить це побачити.
    if measured.accessibility_score is None:
        result.outcome = "failed"
        result.failure = "no_accessibility_category"

    result.measurements = {
        "accessibility_audits_total": measured.accessibility_audits_total,
        "accessibility_applicable": measured.accessibility_applicable,
        "accessibility_passed": measured.accessibility_passed,
        "accessibility_failed": measured.accessibility_failed,
        "accessibility_score": measured.accessibility_score,
        "accessibility_failures": measured.accessibility_failures,
        # Єдине, чим свіжий вимір відрізняється від кешованого повтору.
        "fetch_time": lighthouse.get("fetchTime"),
        "lighthouse_version": lighthouse.get("lighthouseVersion"),
        "requested_url": lighthouse.get("requestedUrl"),
        "final_url": lighthouse.get("finalUrl") or lighthouse.get("finalDisplayedUrl"),
        "strategy": Strategy.MOBILE.value,
        "categories": ["accessibility"],
    }
    result.finished_at = _now()
    result.duration_s = round(time.monotonic() - began, 2)
    return result


async def collect(
    sites: list[Site], store: ResultStore, run_id: str, provenance: dict[str, Any]
) -> dict[str, Any]:
    """Пройти корпус, продовжуючи з того місця, де зупинилися."""
    done = store.completed()
    attempts = store.attempts()
    pending = [s for s in sites if s.site_id not in done]
    if not pending:
        print("  усе вже зібрано")
        return {"planned": len(sites), "pending": 0, "ok": 0, "failed": 0}

    print(f"  до збору: {len(pending)} із {len(sites)} (готово: {len(done)})")
    semaphore = asyncio.Semaphore(CONCURRENCY)
    counters = {"ok": 0, "failed": 0}
    began = time.monotonic()

    async with httpx.AsyncClient(timeout=TIMEOUT_S) as client:

        async def one(site: Site) -> None:
            async with semaphore:
                attempt = attempts.get(site.site_id, 0) + 1
                result = await _measure(site, client, attempt)
                while (
                    result.outcome == "failed"
                    and result.failure in RETRIABLE
                    and attempt < MAX_ATTEMPTS
                ):
                    await asyncio.sleep(2.0 * attempt)
                    attempt += 1
                    result = await _measure(site, client, attempt)
                result.run_id = run_id
                result.provenance = provenance
                store.append(result)
                counters["ok" if result.outcome == "ok" else "failed"] += 1
                total = counters["ok"] + counters["failed"]
                if total % 50 == 0:
                    rate = total / (time.monotonic() - began) * 60
                    left = (len(pending) - total) / max(rate, 0.1)
                    print(
                        f"    {total}/{len(pending)}  {rate:.0f}/хв  "
                        f"лишилось ~{left:.0f} хв  збоїв {counters['failed']}"
                    )

        await asyncio.gather(*(one(site) for site in pending))

    wall = time.monotonic() - began
    print(f"  готово за {wall / 60:.1f} хв: {counters['ok']} ок, {counters['failed']} збоїв")
    return {
        "planned": len(sites),
        "pending": len(pending),
        **counters,
        "wall_s": round(wall, 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Збір знаменника доступності")
    parser.add_argument("--corpus", default="scripts/samples/corpus1000.yaml")
    parser.add_argument("--out", required=True, help="каталог прогону")
    parser.add_argument("--pass-name", default="pass1")
    parser.add_argument(
        "--repeat-sample",
        action="store_true",
        help="лише детермінований підкорпус на 150 сайтів",
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)

    blocked = guard.install()
    print(f"гард платних викликів: {', '.join(blocked) or 'нічого не підмінено'}")

    loaded: Manifest = manifest.load(args.corpus)
    for problem in loaded.problems[:10]:
        print(f"  корпус: {problem}")
    sites = loaded.active
    corpus_hash = loaded.fingerprint()
    print(f"корпус: {len(sites)} сайтів, відбиток {corpus_hash}")

    if args.repeat_sample:
        sites = repeat_sample(sites)
        print(f"підкорпус повторюваності: {len(sites)} сайтів, сіль {REPEAT_SALT}")
    if args.limit:
        sites = sites[: args.limit]
        print(f"обмежено до {len(sites)}")

    if not settings.psi_api_key:
        print("  УВАГА: ключа PSI немає — квота анонімна, буде 429")

    store = ResultStore(Path(args.out))
    run_id = f"a11y-{corpus_hash}-{args.pass_name}"
    provenance = {
        "commit": _commit(),
        "corpus_hash": corpus_hash,
        "corpus": str(args.corpus),
        "pass": args.pass_name,
        "endpoint": ENDPOINT,
        "categories": ["accessibility"],
        "strategy": Strategy.MOBILE.value,
        "concurrency": CONCURRENCY,
        "repeat_salt": REPEAT_SALT if args.repeat_sample else None,
        "started_at": _now(),
    }
    store.write_meta(
        {"run_id": run_id, "provenance": provenance, "sites_planned": len(sites)}
    )
    summary = asyncio.run(collect(sites, store, run_id, provenance))
    meta = store.read_meta()
    meta["summary"] = summary
    meta["finished_at"] = _now()
    store.write_meta(meta)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
