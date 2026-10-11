"""Друге джерело кандидатів: Tranco — звичайний веб без міток.

## Навіщо друге джерело

Wikidata знає організації, про які хтось написав статтю. Через це її
природний розподіл тягне в бік інституцій: шкіл, громад, музеїв,
бібліотек. Для корпусу, який має представляти звичайний виробничий веб,
цього замало — і компенсувати перекіс вигаданими мітками не можна.

Tranco — впорядкований перелік доменів, зведений із кількох джерел
трафіку. Він дає рівно те, чого бракує Wikidata: буденні комерційні
сайти, яких немає в жодній енциклопедії.

## Чим Tranco НЕ є

Він не каже, що це за сайт. Ні сегмента, ні країни, ні галузі — лише
домен і місце в переліку. Тому кожен запис звідси йде з `segment: other`
і порожньою країною, і так і лишається: **невідоме лишається невідомим**.
Мова візьметься з `<html lang>` під час перевірки, бо це заява сайту, а
не наш здогад.

Спокуса тут очевидна — дописати сегмент «на око» за назвою домену. Саме
це правило корпусу й забороняє: одна вигадана мітка робить брехнею весь
зріз за нею.

## Чому не з початку переліку

Перші тисячі — це глобальні платформи, CDN і великі технологічні
компанії, тобто рівно те зміщення, від якого ми тікаємо. Беремо вікно
глибше й рівним кроком по ньому: там живе звичайний веб.
"""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import csv
import io
import json
import zipfile
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

API = "https://tranco-list.eu/api/lists/date/latest"
def _user_agent() -> str:
    """Рядок представлення з НАЛАШТОВАНИМ контактом, або відмова.

    Wikidata і Tranco просять того, хто тягне з них масово, назвати
    себе. Раніше тут стояла особиста адреса власника прямо в коді — і
    їхала в кожну копію репозиторію. Тепер контакт приходить із
    `CRAWLER_CONTACT`, а без нього скрипт спиняється.

    Підставити заглушку було б гірше за відмову: фальшивий контакт
    виглядає як справжній, і той, кого ми просимо про безкоштовний
    сервіс, пише в нікуди. Та сама причина, з якої `USER_AGENT` самого
    аудиту не несе адреси взагалі.
    """
    contact = settings.crawler_contact.strip()
    if not contact:
        raise SystemExit(
            "CRAWLER_CONTACT не задано.\n"
            "Ці скрипти масово звертаються до чужого безкоштовного "
            "сервісу, який просить назвати себе.\n"
            "Вкажіть робочу адресу у backend/.env: CRAWLER_CONTACT=..."
        )
    return (
        "CrawldyBenchmarkCorpus/1.0 (internal audit-engine benchmark corpus; "
        f"contact {contact})"
    )


# Вікно рангів, з якого беремо. Початок пропускаємо навмисно (глобальні
# платформи), і найглибший хвіст теж: там більшає припаркованих доменів
# і хостів, які взагалі не є сайтами.
RANK_FROM = 20_000
RANK_TO = 600_000


def latest_list() -> tuple[str, str]:
    """Ідентифікатор і адреса свіжого переліку. Записується в походження."""
    response = httpx.get(API, headers={"User-Agent": _user_agent()},
                         timeout=60, follow_redirects=True)
    response.raise_for_status()
    payload = response.json()
    if not payload.get("available"):
        raise RuntimeError("Tranco каже, що перелік ще не готовий")
    return str(payload["list_id"]), str(payload["download"])


def download(url: str, cache: Path) -> list[tuple[int, str]]:
    """Завантажити (або взяти з кешу) перелік «ранг, домен»."""
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", url, headers={"User-Agent": _user_agent()},
                          timeout=300, follow_redirects=True) as response:
            response.raise_for_status()
            cache.write_bytes(b"".join(response.iter_bytes()))

    raw = cache.read_bytes()
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            name = archive.namelist()[0]
            text = archive.read(name).decode("utf-8", "replace")
    else:
        text = raw.decode("utf-8", "replace")

    rows: list[tuple[int, str]] = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2:
            continue
        try:
            rows.append((int(row[0]), row[1].strip().lower()))
        except ValueError:
            continue
    return rows


def sample(rows: list[tuple[int, str]], take: int,
           rank_from: int = RANK_FROM, rank_to: int = RANK_TO) -> list[tuple[int, str]]:
    """Рівний крок по вікну рангів — не його початок."""
    window = [r for r in rows if rank_from <= r[0] <= rank_to]
    if take >= len(window):
        return window
    step = len(window) / take
    return [window[int(i * step)] for i in range(take)]


def harvest(take: int, cache: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    list_id, url = latest_list()
    rows = download(url, cache)
    chosen = sample(rows, take)
    source = f"tranco:{list_id}"
    candidates = [
        {
            # Схему пробуємо https; probe піде за перенаправленням, якщо
            # сайт живе на http.
            "url": f"https://{domain}",
            # Сегмент НЕ вигадуємо: Tranco про нього нічого не знає.
            "segment": "other",
            "klass": "tranco rank",
            "country": "",
            "label": f"rank {rank}",
            "source": source,
        }
        for rank, domain in chosen
    ]
    meta = {
        "source": source,
        "download": url,
        "rows_total": len(rows),
        "window": [RANK_FROM, RANK_TO],
        "sampled": len(candidates),
    }
    return candidates, meta


if __name__ == "__main__":
    import sys

    take = int(sys.argv[1]) if len(sys.argv) > 1 else 1500
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "benchmark/tranco_candidates.json")
    got, meta = harvest(take, Path("benchmark/tranco-top1m.zip"))
    out.write_text(
        json.dumps({"meta": meta, "candidates": got}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    print(f"-> {out}")
