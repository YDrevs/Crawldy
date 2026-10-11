"""Прогін корпусу: з продовженням, з межами, без падінь через один сайт.

## Що тут головне

**Один сайт не спиняє тисячу.** Кожен аудит загорнутий у таймаут і в
перехоплення винятків; збій стає рядком результату з класом причини, а
не кінцем прогону. На тисячі сайтів кількасот збоїв — норма, і прогін,
який від них падає, не доживе до перших даних.

**Продовження, а не перезапуск.** Ідентифікатор прогону детермінований
за складом корпусу, конфігурацією й комітом. Той самий трійник — той
самий каталог, і вже пройдені сайти пропускаються. Змінилося будь-що —
це інший прогін, і змішувати їх не можна.

**Межі, а не швидкість.** Паралельність мала навмисно: кожен аудит тягне
свій браузер. Прискорювати прогін агресивнішим краулом не можна — тоді
міряється не той продукт, який працює в проді.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.benchmark import guard, measurements
from scripts.benchmark.config import Provenance, RunConfig, RunId, RunMeta
from scripts.benchmark.failures import Failure, classify, retryable
from scripts.benchmark.manifest import Manifest, Site
from scripts.benchmark.results import ResultStore, SiteResult

# Скільки місця прогін має право зайняти, перш ніж спинитися сам.
# Тисяча знімків по кілька мегабайтів — це десятки гігабайтів, і краще
# спинитися свідомо, ніж заповнити диск.
DEFAULT_DISK_BUDGET_BYTES = 20 * 1024**3

# Скільки вільного місця лишити на томі. Це ІНША величина, ніж бюджет:
# бюджет міряє, скільки зайняв прогін, і на томі з 13 ГБ вільного він не
# спрацював би ніколи — диск закінчився б першим. Реальна безпека — саме
# запас вільного місця, бо поруч пише не лише прогін: тимчасові файли
# браузера, профілі Playwright, своп.
DEFAULT_MIN_FREE_BYTES = 20 * 1024**3


def _now() -> str:
    return datetime.now(UTC).isoformat()


class Runner:
    """Проганяє корпус справжнім рушієм аудиту."""

    def __init__(
        self,
        manifest: Manifest,
        config: RunConfig,
        root: Path,
        *,
        label: str = "",
        disk_budget: int = DEFAULT_DISK_BUDGET_BYTES,
        min_free: int = DEFAULT_MIN_FREE_BYTES,
        on_event: Callable[[str], None] | None = None,
    ) -> None:
        self.manifest = manifest
        self.config = config
        self.provenance = Provenance.current()
        self.run_id = RunId.build(
            manifest.fingerprint(), config, self.provenance, label
        ).value
        self.store = ResultStore(Path(root) / self.run_id)
        self.disk_budget = disk_budget
        self.min_free = min_free
        self._say = on_event or (lambda message: print(message, flush=True))
        self._stopping = False

    def free_bytes(self) -> int:
        """Скільки вільного місця на томі, де лежить прогін."""
        import shutil

        return shutil.disk_usage(self.store.directory).free

    # ── вибір роботи ──────────────────────────────────────────────────────

    def pending(self, *, retry_failed: bool = False) -> list[Site]:
        """Кого ще треба пройти.

        За замовчуванням — тих, кого не проходили. `retry_failed` додає
        тих, хто впав із причини, яка буває тимчасовою: 403 і приватний
        IP другого разу не зміняться, і повторювати їх — марна робота.
        """
        done = self.store.completed()
        attempts = self.store.attempts()
        failed = self.store.failed()

        chosen: list[Site] = []
        for site in self.manifest.active:
            if site.site_id in done:
                continue
            row = failed.get(site.site_id)
            if row is not None:
                if not retry_failed:
                    continue
                if attempts.get(site.site_id, 0) >= self.config.max_attempts:
                    continue
                if not retryable(Failure(row.get("failure") or "unknown")):
                    continue
            chosen.append(site)
        return chosen

    # ── прогін ────────────────────────────────────────────────────────────

    async def run(self, *, retry_failed: bool = False, limit: int | None = None) -> dict[str, Any]:
        blocked = guard.install()
        if not guard.is_installed():
            raise RuntimeError(
                "гард платних викликів не став — прогін зупинено, щоб не "
                "витратити кредит"
            )

        free = self.free_bytes()
        if free < self.min_free:
            raise RuntimeError(
                f"на томі прогону вільно {free / 1024**3:.1f} ГБ при запасі "
                f"{self.min_free / 1024**3:.0f} ГБ. Візьміть --root на іншому "
                f"томі: нічний прогін не має спинятися через місце на диску"
            )

        todo = self.pending(retry_failed=retry_failed)
        if limit is not None:
            todo = todo[:limit]

        meta = RunMeta(
            run_id=self.run_id,
            started_at=_now(),
            corpus_path=str(self.manifest.path or ""),
            corpus_sites=len(self.manifest.active),
            config=self.config.as_dict(),
            provenance=self.provenance.as_dict(),
            guard=blocked,
            deviations=self.config.deviations(),
        )
        existing = self.store.read_meta()
        # Шапка пишеться один раз: продовження не має переписувати час
        # початку, інакше тривалість прогону стає невідновною.
        self.store.write_meta(existing or meta.as_dict())

        self._say(
            f"прогін {self.run_id}: {len(todo)} сайтів до роботи "
            f"з {len(self.manifest.active)} у корпусі"
        )
        if self.provenance.dirty:
            self._say("УВАГА: дерево брудне — результат не відтворити комітом")
        for deviation in self.config.deviations():
            self._say(
                f"УВАГА: {deviation} — прогін міряє не той краул, який виконує "
                f"продукт; для висновків про правила це недопустимо"
            )

        semaphore = asyncio.Semaphore(self.config.concurrency)
        counters = {"ok": 0, "failed": 0}
        lock = asyncio.Lock()

        async def one(site: Site) -> None:
            if self._stopping:
                return
            async with semaphore:
                if self._stopping:
                    return
                result = await self._audit(site)
                async with lock:
                    self.store.append(result)
                    counters["ok" if result.outcome == "ok" else "failed"] += 1
                    done = counters["ok"] + counters["failed"]
                    mark = "OK " if result.outcome == "ok" else f"!! {result.failure}"
                    self._say(
                        f"[{done}/{len(todo)}] {mark} {site.url} "
                        f"({result.duration_s:.0f}с)"
                    )
                    if self.store.disk_bytes() > self.disk_budget:
                        self._stopping = True
                        self._say("бюджет диска вичерпано — спиняюсь свідомо")
                    free = self.free_bytes()
                    if free < self.min_free:
                        self._stopping = True
                        self._say(
                            f"вільного місця лишилось {free / 1024**3:.1f} ГБ "
                            f"при запасі {self.min_free / 1024**3:.0f} ГБ — "
                            f"спиняюсь, поки том не заповнений"
                        )

        try:
            await asyncio.gather(*(one(site) for site in todo))
        except (KeyboardInterrupt, asyncio.CancelledError):
            # Перерваний прогін лишає повні рядки на диску: наступний
            # запуск із тим самим ідентифікатором просто продовжить.
            self._say("перервано — уже записане збережено, запусти знову для продовження")
            raise

        return {
            "run_id": self.run_id,
            "directory": str(self.store.directory),
            "attempted": len(todo),
            **counters,
            "remaining": len(self.pending(retry_failed=retry_failed)),
        }

    # ── один сайт ─────────────────────────────────────────────────────────

    async def _audit(self, site: Site) -> SiteResult:
        from app.audit.orchestrator import run_audit
        from app.audit.snapshot import dump as dump_snapshot

        result = SiteResult(
            site_id=site.site_id,
            url=site.url,
            run_id=self.run_id,
            segment=site.segment,
            tags=list(site.tags),
            started_at=_now(),
            attempt=self.store.attempts().get(site.site_id, 0) + 1,
            provenance=self.provenance.as_dict(),
            config=self.config.as_dict(),
        )
        started = time.perf_counter()
        try:
            outcome = await asyncio.wait_for(
                run_audit(site.url, self.config.audit_options()),
                timeout=self.config.site_timeout_s,
            )
        except TimeoutError:
            result.outcome = "failed"
            result.failure = Failure.SITE_TIMEOUT.value
            result.failure_detail = f"понад {self.config.site_timeout_s} с"
        except Exception as exc:  # noqa: BLE001 — один сайт не валить прогін
            result.outcome = "failed"
            result.failure = classify(exc).value
            result.failure_detail = f"{type(exc).__name__}: {exc}"[:400]
        else:
            self._absorb(result, outcome, dump_snapshot)
        result.duration_s = round(time.perf_counter() - started, 2)
        result.finished_at = _now()
        return result

    def _absorb(self, result: SiteResult, outcome: Any, dump_snapshot: Any) -> None:
        """Успішний аудит → рядок результату плюс знімок."""
        import json

        ctx = outcome.context
        # Статусу окремим полем в `AuditOutcome` немає — він виводиться з
        # деградацій, і саме `is_failure` розводить справжній збій від
        # свідомо вимкненого модуля.
        #
        # Правило дослівно те саме, що в `app/report/source.py` і
        # `app/services/audit_service.py`. Свою версію тут заводити не
        # можна: прогін, який рахує статус інакше за продукт, міряє себе.
        # Спільної функції в продукті немає — це вже третя копія, і
        # винести її варто окремою зміною, а не в інфраструктурній.
        failures = [d for d in outcome.degraded if d.is_failure]
        result.status = "partial" if failures else "completed"
        result.overall = outcome.overall
        result.scores = dict(outcome.scores)
        result.degraded = [d.to_json() for d in outcome.degraded]
        result.skipped_modules = sorted(m.value for m in outcome.skipped_modules)
        result.partial_modules = sorted(m.value for m in outcome.partial_modules)
        # Версії, які порахував сам аудит, — поруч із нашими: якщо вони
        # розійдуться, це видно одразу, а не через місяць в аналізі.
        result.provenance = {**result.provenance, "audit_versions": dict(outcome.versions)}
        result.findings = [
            {
                "code": issue.code,
                "issue_key": issue.issue_key,
                "module": issue.module.value,
                "severity": issue.severity.value,
                "confidence": getattr(issue.confidence, "value", None),
                "page_url": issue.page_url,
                "evidence": issue.evidence,
            }
            for issue in outcome.issues
        ]
        result.measurements = measurements.collect(ctx)
        result.coverage = dict(result.measurements.get("crawl") or {})

        if not ctx.ok_pages:
            # Аудит завершився, але дивитися нема на що. Для статистики
            # це окремий стан, а не успіх: інакше «сайт не пустив» і
            # «сайт прочитано» злилися б в один рядок.
            result.outcome = "failed"
            result.failure = Failure.EMPTY_CRAWL.value
            result.failure_detail = "краул не приніс жодної сторінки"

        path = self.store.snapshot_path(result.site_id)
        path.write_text(
            json.dumps(dump_snapshot(ctx), ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        result.snapshot = path.name


def sites_for(manifest: Manifest, *, segments: Sequence[str] | None = None,
              tags: Sequence[str] | None = None) -> list[Site]:
    """Зріз корпусу за сегментом або теґом — для пілотів і перевірок."""
    chosen = manifest.active
    if segments:
        wanted = {s.lower() for s in segments}
        chosen = [s for s in chosen if s.segment in wanted]
    if tags:
        needed = {t.lower() for t in tags}
        chosen = [s for s in chosen if needed & set(s.tags)]
    return chosen


__all__ = [
    "DEFAULT_DISK_BUDGET_BYTES",
    "DEFAULT_MIN_FREE_BYTES",
    "Runner",
    "sites_for",
]
