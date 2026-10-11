"""Ланцюг перенаправлень: із чого він складається і що з нього видно.

## Дані вже були

`FetchResult.redirects` збирався давно, `PageSignals.redirect_chain` теж —
і жоден чек їх не читав. Тут вони перетворюються на відповіді, а не
збираються заново: збір лишається там, де був.

## Дві речі, які довелося виправити при читанні

**`Location` буває відносним.** httpbin віддає `/relative-redirect/2`, і
це не виняток, а звичайна практика. Зберігали ми саме значення
заголовка, тож ланцюг треба розвʼязувати покроково: перший крок відносно
запитаної адреси, кожен наступний — відносно попереднього. Без цього
«куди нас відправили» читається як шлях без домену.

**Довжина рахується в нормалізованих адресах.** `/a` → `/a/` — це нуль
змістовних кроків, а не один: обидві адреси нормалізуються в одну
сторінку. Рахувати сирі стрибки означало б вигадувати клієнтові
складність, якої в нього немає.

## Чого тут немає і чому

Справжню нескінченну петлю довести неможливо. httpx кидає
`TooManyRedirects` на шостому кроці й **не віддає історії** — ми не
знаємо ані де крутилося, ані чи крутилося взагалі. Тому `repeated`
означає рівно те, що видно: адреса трапилась у ланцюзі двічі, а сам
ланцюг завершився. Випадок «не дійшли до кінця» лишається окремим
твердженням і петлею не називається.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin

from app.audit.logical_pages import normalize
from app.audit.types import PageSignals


@dataclass(frozen=True, slots=True)
class Hop:
    """Один крок: яким кодом нас відправили і куди."""

    status: int
    # Уже розвʼязана абсолютна адреса, а не значення заголовка.
    url: str


@dataclass(frozen=True, slots=True)
class Chain:
    """Шлях від запитаної адреси до тієї, що врешті відповіла."""

    source: str
    hops: tuple[Hop, ...]
    final_url: str
    final_status: int | None

    @property
    def steps(self) -> tuple[str, ...]:
        """Нормалізовані адреси шляху, від запитаної до кінцевої."""
        seq = [normalize(self.source), *(normalize(h.url) for h in self.hops)]
        seq.append(normalize(self.final_url))
        # Поспіль однакові — це та сама сторінка, записана двома
        # способами. Стискаємо: інакше `/a` → `/a/` виглядало б кроком.
        out: list[str] = []
        for item in seq:
            if not out or out[-1] != item:
                out.append(item)
        return tuple(out)

    @property
    def length(self) -> int:
        """Скільки змістовних переходів зробив браузер."""
        return max(0, len(self.steps) - 1)

    @property
    def repeated(self) -> tuple[str, ...]:
        """Адреси, які трапились у шляху більше одного разу.

        Доведене повторення, а не припущена петля: ланцюг завершився, і
        ми бачили обидва входження на власні очі.
        """
        seen: dict[str, int] = {}
        for step in self.steps:
            seen[step] = seen.get(step, 0) + 1
        return tuple(url for url, count in seen.items() if count > 1)

    @property
    def lands_badly(self) -> bool:
        """Шлях закінчився там, звідки сторінки не отримати."""
        return self.final_status is not None and self.final_status >= 400

    def as_evidence(self) -> dict[str, object]:
        return {
            "source": self.source,
            "hops": [{"status": h.status, "url": h.url} for h in self.hops],
            "final_url": self.final_url,
            "final_status": self.final_status,
            "redirects": self.length,
            # Нормалізований шлях поруч із сирим: із нього видно, чому
            # три сирі стрибки інколи є одним переходом.
            "path": list(self.steps),
        }


def chain_of(page: PageSignals) -> Chain | None:
    """Ланцюг сторінки, або None — якщо перенаправлень не було.

    `redirect_chain` після знімка приходить списками, а не кортежами,
    тож розпаковуємо позиційно й не покладаємось на тип.
    """
    raw = page.redirect_chain or ()
    if not raw:
        return None

    source = page.redirected_from or page.url
    hops: list[Hop] = []
    base = source
    for item in raw:
        status, target = item[0], item[1]
        resolved = urljoin(base, target)
        hops.append(Hop(status=int(status), url=resolved))
        base = resolved

    return Chain(
        source=source,
        hops=tuple(hops),
        final_url=page.url,
        final_status=page.status_code,
    )


def chains(pages: list[PageSignals]) -> list[Chain]:
    found = (chain_of(page) for page in pages)
    return [chain for chain in found if chain is not None]


__all__ = ["Chain", "Hop", "chain_of", "chains"]
