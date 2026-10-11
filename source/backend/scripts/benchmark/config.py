"""Конфігурація прогону і його походження.

## Навіщо походження

Два прогони можна порівнювати лише тоді, коли їх рахували однаково. У
цьому проєкті вже є свідчення, наскільки це серйозно: зміна стелі штрафу
зсунула бали всієї вибірки, не змінивши жодного сайту. Тому коміт,
`scoring_version` і `detector_version` записуються з кожним рядком
результату — не в шапку файлу, а поруч із кожним сайтом, щоб зведення
двох датасетів не могло тихо змішати різні правила.

## Навіщо фіксована конфігурація

Бюджет краулу змінює те, що видно. `seo.topic_islands` не міг спрацювати
на восьми сторінках і спрацьовує на двадцяти пʼяти — і «0 із 31» тоді
описував бюджет, а не чек. Тож конфігурація фіксується на весь прогін і
зберігається разом із ним.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from typing import Any


def git_commit() -> str:
    """Коміт, на якому рахували. Без нього результат ні з чим не звірити."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    return out.stdout.strip() or "unknown"


def git_dirty() -> bool:
    """Чи є незакомічені зміни. Прогін із брудного дерева не відтворити."""
    try:
        out = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(out.stdout.strip())


@dataclass(frozen=True, slots=True)
class Provenance:
    """Чим саме пораховано цей рядок."""

    commit: str
    dirty: bool
    scoring_version: str
    detector_version: str

    @staticmethod
    def current() -> Provenance:
        from app.audit.versions import detector_version, scoring_version

        return Provenance(
            commit=git_commit(),
            dirty=git_dirty(),
            scoring_version=scoring_version(),
            detector_version=detector_version(),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class RunConfig:
    """Налаштування аудиту, однакові для всього корпусу.

    Значення за замовчуванням навмисно збігаються з продуктовими: якщо
    міряти іншим бюджетом, ніж працює продукт, вимірюється не продукт.
    """

    max_pages: int = 25
    max_depth: int = 2
    render: bool = True
    render_max_pages: int = 3
    # Швидкість УВІМКНЕНА, бо продукт її міряє, а бенчмарк має міряти
    # продукт: модуль важить 0.22, і без нього `overall` — інша величина,
    # ніж бачить клієнт.
    #
    # Прапорець довго стояв `False` і не працював: `perf_provider="none"`
    # не збігається з жодним `case` у фабриці провайдерів, тож усі прогони
    # мовчки йшли через `AutoProvider`. Конфігурація казала «вимкнено», а
    # PSI викликався на кожен сайт. Тепер вимикання робиться фільтром
    # модулів — єдиним механізмом, який продукт справді має.
    #
    # Шум Lighthouse між прогонами реальний (див. CLAUDE.md), але зміни
    # правил оцінюють перерахунком тих самих знімків, а не порівнянням
    # двох прогонів, — тож на A/B він не впливає.
    performance: bool = True
    # Платні шари вимкнені завжди й окремо від гарда: гард ловить те, що
    # прослизне повз конфігурацію, а не замінює її.
    llm: bool = False
    # Скільки сайтів одночасно. Кожен тягне власний браузер, тож більше
    # не означає швидше.
    concurrency: int = 3
    # Скільки часу дозволено одному сайту, включно з рендером.
    #
    # Дорівнює `settings.audit_timeout_s`: у продукті кожен аудит
    # обгорнутий рівно в цю межу (`app/worker/tasks.py`). Поки тут стояло
    # 300, бенчмарк обривав би сайти, які продукт дочитує, — і «збій»
    # описував би нашу межу, а не сайт. Літерал, а не читання з
    # налаштувань, — щоб `run_id` не залежав від оточення; за розходженням
    # стежить тест.
    site_timeout_s: int = 600
    # Скільки разів повторюємо сайт, який упав із мережевої причини.
    max_attempts: int = 2

    def fingerprint(self) -> str:
        payload = json.dumps(asdict(self), sort_keys=True)
        return hashlib.blake2b(payload.encode(), digest_size=8).hexdigest()

    def deviations(self) -> list[str]:
        """Чим цей прогін відрізняється від бюджету продукту.

        Мовчазне відхилення вже коштувало проєкту хибного висновку:
        калібрування ходило на 8 сторінок замість 25, і «жодного
        спрацювання» описувало бюджет, а не чек. Урізаний бюджет
        законний для перевірки самої інфраструктури й недопустимий
        для висновків про правила — різницю має бачити той, хто читає
        результат, а не той, хто памʼятає команду запуску.

        Судимо лише поля, що змінюють побачене. `concurrency` і
        `max_attempts` міняють швидкість прогону, а не спостереження.
        `site_timeout_s` — навпаки: обрізаний час перетворює прочитаний
        сайт на збій, тобто змінює саме дані.
        """
        product = RunConfig()
        watched = ("max_pages", "max_depth", "render", "render_max_pages",
                   "performance", "llm", "site_timeout_s")
        return [
            f"{name}={getattr(self, name)} (продукт: {getattr(product, name)})"
            for name in watched
            if getattr(self, name) != getattr(product, name)
        ]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    def audit_options(self) -> Any:
        """Опції аудиту для цього прогону."""
        from app.audit.enums import Module
        from app.audit.orchestrator import AuditOptions

        # Вимкнення швидкості — через фільтр модулів, а не через імʼя
        # провайдера: `_measure_performance` виходить одразу, коли модуля
        # немає в наборі, тобто зовнішній виклик не робиться взагалі.
        # Рядка «none» фабрика провайдерів не знає й тихо дає `auto`.
        modules = None if self.performance else {
            m for m in Module if m is not Module.PERFORMANCE
        }
        return AuditOptions(
            max_pages=self.max_pages,
            max_depth=self.max_depth,
            render=self.render,
            render_max_pages=self.render_max_pages,
            modules=modules,
            llm=self.llm,
        )


@dataclass(frozen=True, slots=True)
class RunId:
    """Ідентифікатор прогону — детермінований за складом і правилами.

    Той самий корпус, та сама конфігурація й той самий коміт дають той
    самий рядок, тож перезапуск продовжує роботу, а не починає новий
    набір даних. Змінилося будь-що з трьох — це вже інший прогін, і
    змішувати їх не можна.
    """

    corpus: str
    config: str
    commit: str
    label: str = ""

    @property
    def value(self) -> str:
        base = f"{self.commit[:12]}-{self.corpus}-{self.config}"
        return f"{self.label}-{base}" if self.label else base

    @staticmethod
    def build(corpus_fingerprint: str, config: RunConfig, provenance: Provenance,
              label: str = "") -> RunId:
        return RunId(
            corpus=corpus_fingerprint,
            config=config.fingerprint(),
            commit=provenance.commit,
            label=label,
        )


@dataclass(slots=True)
class RunMeta:
    """Шапка прогону: усе, що потрібно, щоб зрозуміти набір даних."""

    run_id: str
    started_at: str
    corpus_path: str
    corpus_sites: int
    config: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    guard: list[str] = field(default_factory=list)
    deviations: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "corpus_path": self.corpus_path,
            "corpus_sites": self.corpus_sites,
            "config": self.config,
            "provenance": self.provenance,
            "paid_ai_guard": self.guard,
            "deviates_from_product": self.deviations,
        }


__all__ = ["Provenance", "RunConfig", "RunId", "RunMeta", "git_commit", "git_dirty"]
