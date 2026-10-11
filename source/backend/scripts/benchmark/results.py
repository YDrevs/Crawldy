"""Результат одного сайту й сховище результатів прогону.

## Чому не тільки знахідки

Знахідка каже, що чек спрацював. Калібруванню потрібне протилежне: на
скількох сайтах він **міг** спрацювати й не спрацював, і з якими
значеннями. Тому поруч зі знахідками пишуться сирі величини — довжина
ланцюгів перенаправлень, частка карти сайту, схожість сторінок,
розподіл кодувань, — навіть коли жоден чек із них не зробив висновку.

Без цього питання «чи правильний поріг» не має даних для відповіді:
видно лише те, що поріг уже пропустив.

## Формат

JSONL, по рядку на сайт. Дописування — атомарна операція на рівні рядка,
тож перерваний прогін лишає файл читаним, а не наполовину записаним
обʼєктом. Аналіз читає його потоково й не тримає корпус у памʼяті.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class SiteResult:
    """Усе, що прогін дізнався про один сайт."""

    site_id: str
    url: str
    run_id: str
    segment: str = "other"
    tags: list[str] = field(default_factory=list)

    started_at: str = ""
    finished_at: str = ""
    duration_s: float = 0.0
    attempt: int = 1

    # ok | failed
    outcome: str = "ok"
    failure: str = ""
    failure_detail: str = ""

    provenance: dict[str, Any] = field(default_factory=dict)
    config: dict[str, Any] = field(default_factory=dict)

    status: str = ""
    overall: int | None = None
    scores: dict[str, Any] = field(default_factory=dict)
    # Модулі — окремими полями, а не всередині `scores`: там лежать
    # бали, і аналіз рахує по них розподіли. Перелік імен серед чисел
    # тримався б лише на тому, що читач додумається його відфільтрувати.
    skipped_modules: list[str] = field(default_factory=list)
    partial_modules: list[str] = field(default_factory=list)
    coverage: dict[str, Any] = field(default_factory=dict)
    degraded: list[dict[str, Any]] = field(default_factory=list)
    findings: list[dict[str, Any]] = field(default_factory=list)
    # Сирі величини детекторів — див. docstring модуля.
    measurements: dict[str, Any] = field(default_factory=dict)
    snapshot: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ResultStore:
    """JSONL-сховище одного прогону з підтримкою продовження."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.results_path = self.directory / "results.jsonl"
        self.meta_path = self.directory / "run.json"
        self.snapshots = self.directory / "snapshots"
        self.snapshots.mkdir(exist_ok=True)

    # ── читання ───────────────────────────────────────────────────────────

    def rows(self) -> list[dict[str, Any]]:
        """Усі записані рядки. Пошкоджені пропускаються, а не валять читання.

        Обірваний рядок буває рівно один — останній, якщо процес убили
        посеред запису. Кидати через нього весь набір даних було б
        найдорожчим способом обробити найдешевшу помилку.
        """
        if not self.results_path.exists():
            return []
        found: list[dict[str, Any]] = []
        with self.results_path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    found.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return found

    def latest(self) -> list[dict[str, Any]]:
        """По одному рядку на сайт — останню спробу.

        `rows()` — це журнал, і повторна спроба лишається в ньому назавжди:
        інакше не видно, що сайт довелося повторювати. Але аналіз рахує
        сайти, а не спроби. Поки він читав журнал, повторений сайт
        потрапляв і в успішні, і в збійні: на шести сайтах виходило
        «8 рядків, 5 успішних, 3 збої», а на тисячі з повторами частка
        збоїв була б завищена рівно на кількість повторів.
        """
        found: dict[str, dict[str, Any]] = {}
        for row in self.rows():
            found[str(row["site_id"])] = row
        return list(found.values())

    def completed(self) -> set[str]:
        """Сайти, які вже пройшли успішно: їх повторювати не треба."""
        return {r["site_id"] for r in self.rows() if r.get("outcome") == "ok"}

    def failed(self) -> dict[str, dict[str, Any]]:
        """Сайти, які впали. Останній запис перемагає."""
        found: dict[str, dict[str, Any]] = {}
        for row in self.rows():
            if row.get("outcome") == "ok":
                found.pop(row["site_id"], None)
            else:
                found[row["site_id"]] = row
        return found

    def attempts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for row in self.rows():
            site = row["site_id"]
            counts[site] = max(counts.get(site, 0), int(row.get("attempt") or 1))
        return counts

    # ── запис ─────────────────────────────────────────────────────────────

    def append(self, result: SiteResult) -> None:
        line = json.dumps(result.as_dict(), ensure_ascii=False, default=str)
        with self.results_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
            handle.flush()

    def write_meta(self, meta: dict[str, Any]) -> None:
        self.meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )

    def read_meta(self) -> dict[str, Any]:
        if not self.meta_path.exists():
            return {}
        try:
            return dict(json.loads(self.meta_path.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            return {}

    def snapshot_path(self, site_id: str) -> Path:
        """Знімок лежить усередині прогону — походження не губиться.

        Знімки різних прогонів у спільній теці неможливо розрізнити, а
        порівнювати їх не можна: це різні правила й різні краули.
        """
        return self.snapshots / f"{site_id}.json"

    def disk_bytes(self) -> int:
        return sum(f.stat().st_size for f in self.directory.rglob("*") if f.is_file())


__all__ = ["ResultStore", "SiteResult"]
