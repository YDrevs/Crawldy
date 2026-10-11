"""Пошук кандидатів у корпус: Wikidata, а не памʼять моделі.

## Чому не список з голови

Перша спроба складала корпус із адрес, які модель памʼятає. Памʼять
добре тримає помітне — університети, музеї, національні медіа — і майже
не тримає звичайного малого бізнесу, заради якого корпус і потрібен.
Гірше: правдоподібний домен, якого не існує, з памʼяті виходить так само
впевнено, як справжній. Тисяча таких рядків — це не корпус, а вигадка,
яку ніхто не помітить, поки прогін не почне падати.

## Чому саме Wikidata

Властивість P856 — «офіційний сайт» сутності. Це не цитата в статті й не
здогад: хтось звірив, що ця адреса належить цій організації. Разом із
нею беремо `P31` (чим сутність є) і `P17` (країна) — тобто **сегмент і
географія приходять із джерела**, а не з нашої інтуїції. Саме цього
вимагає правило «не вигадувати метадані»: у корпусі мітка означає, що
так сказало джерело, і його видно в `source`.

Вибірка бере не початок списку: `ORDER BY ?site` і рівний крок по всій
довжині. Початок будь-якого впорядкування — це найстаріші й найпомітніші
сутності, тобто рівно те зміщення, від якого ми тікаємо. Та сама
причина, що й у `_spread` для карт сайту.

## Що цей модуль НЕ робить

Не перевіряє, що сайт живий, і не ставить теґи технологій. Wikidata
знає, кому належить адреса, і не знає, чи вона сьогодні відповідає й на
чому зроблена. Це робота `probe_corpus.py`, і поки вона не зроблена,
кандидат лишається кандидатом.
"""

from __future__ import annotations

import sys
from pathlib import Path as _Path

sys.path.insert(0, str(_Path(__file__).resolve().parents[2]))

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from app.core.config import settings

ENDPOINT = "https://query.wikidata.org/sparql"

# Wikidata просить представлятися. Анонімний масовий запит — привід для
# блокування, і по заслузі.
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


# Скільки рядків тягнемо на один клас, перш ніж проріджувати. Більше за
# потрібне навмисно: частина адрес мертва, частина веде на той самий сайт.
FETCH_LIMIT = 700

# Пауза між запитами. WDQS — безкоштовний спільний сервіс, і вичавлювати
# його на повну ми не маємо права.
PAUSE_S = 0.6


@dataclass(frozen=True, slots=True)
class Klass:
    """Клас сутностей Wikidata і сегмент, у який він лягає.

    Сегмент — це наше рішення, але воно спирається на клас джерела, а не
    на вигляд домену. У корпусі поруч лишається `source`, щоб рішення
    можна було перевірити або переглянути.
    """

    qid: str
    segment: str
    label: str
    subclasses: bool = True


# Класи підібрані так, щоб покрити перелічені сегменти РЕАЛЬНИМИ
# сутностями, а не тими, які приємно бачити у вибірці.
CLASSES: tuple[Klass, ...] = (
    # локальний бізнес і послуги
    Klass("Q11707", "local", "restaurant"),
    Klass("Q27686", "travel", "hotel"),
    Klass("Q131734", "local", "brewery"),
    Klass("Q1414144", "travel", "winery"),
    Klass("Q613142", "local", "law firm"),
    Klass("Q4260475", "local", "medical clinic"),
    Klass("Q1639378", "local", "theatre company"),
    # торгівля
    Klass("Q507619", "ecommerce", "retail chain"),
    Klass("Q194195", "ecommerce", "department store"),
    Klass("Q180846", "ecommerce", "supermarket"),
    Klass("Q1373919", "ecommerce", "bookstore"),
    # софт і SaaS
    Klass("Q1058914", "saas", "software company"),
    Klass("Q18388277", "saas", "technology company"),
    # корпоративне й промислове
    Klass("Q4830453", "corporate", "business"),
    Klass("Q13235160", "corporate", "manufacturer"),
    Klass("Q249556", "corporate", "engineering company"),
    # медіа й видавництва
    Klass("Q11032", "publishing", "newspaper"),
    Klass("Q41298", "publishing", "magazine"),
    Klass("Q2085381", "publishing", "publisher"),
    Klass("Q14350", "publishing", "radio station"),
    Klass("Q1616075", "publishing", "television station"),
    # освіта, культура, інституції
    Klass("Q3918", "education", "university"),
    Klass("Q9826", "education", "high school"),
    Klass("Q7075", "education", "library"),
    Klass("Q33506", "education", "museum"),
    Klass("Q16917", "education", "hospital"),
    Klass("Q79913", "education", "NGO"),
    Klass("Q43229", "education", "organization", subclasses=False),
    Klass("Q15284", "education", "municipality"),
    # подорожі й дозвілля
    Klass("Q43501", "travel", "zoo"),
    Klass("Q2416723", "travel", "theme park"),
    Klass("Q41176", "travel", "tourist attraction", subclasses=False),
    Klass("Q476028", "travel", "football club"),
)

# Країни, для яких робимо окремі запити. Без цього природний розподіл
# Wikidata дає переважно США й Британію — тобто той самий регіональний
# перекіс, який заборонено в постановці.
COUNTRIES: tuple[tuple[str, str], ...] = (
    ("Q30", "US"), ("Q145", "GB"), ("Q183", "DE"), ("Q142", "FR"),
    ("Q29", "ES"), ("Q38", "IT"), ("Q55", "NL"), ("Q31", "BE"),
    ("Q36", "PL"), ("Q212", "UA"), ("Q213", "CZ"), ("Q214", "SK"),
    ("Q28", "HU"), ("Q218", "RO"), ("Q219", "BG"), ("Q34", "SE"),
    ("Q20", "NO"), ("Q35", "DK"), ("Q33", "FI"), ("Q39", "CH"),
    ("Q40", "AT"), ("Q45", "PT"), ("Q41", "GR"), ("Q43", "TR"),
    ("Q16", "CA"), ("Q408", "AU"), ("Q664", "NZ"), ("Q17", "JP"),
    ("Q884", "KR"), ("Q668", "IN"), ("Q155", "BR"), ("Q96", "MX"),
    ("Q414", "AR"), ("Q298", "CL"), ("Q258", "ZA"), ("Q191", "EE"),
    ("Q37", "LT"), ("Q211", "LV"), ("Q224", "HR"), ("Q215", "SI"),
    ("Q27", "IE"), ("Q189", "IS"),
)


@dataclass
class Candidate:
    """Кандидат до перевірки. Ще не член корпусу."""

    url: str
    segment: str
    klass: str
    country: str
    label: str
    source: str = "wikidata:P856"

    def as_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "segment": self.segment,
            "klass": self.klass,
            "country": self.country,
            "label": self.label,
            "source": self.source,
        }


@dataclass
class Harvest:
    """Зібране з джерела, з журналом того, що не вийшло."""

    candidates: list[Candidate] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    queries: int = 0


def _sparql(klass: Klass, country_qid: str | None, limit: int) -> str:
    path = "wdt:P31/wdt:P279*" if klass.subclasses else "wdt:P31"
    country = f"    ?item wdt:P17 wd:{country_qid} .\n" if country_qid else ""
    # ORDER BY ?site — не за QID: початок за QID це найстаріші й
    # найпомітніші сутності, тобто саме те зміщення, від якого тікаємо.
    return f"""
SELECT ?item ?itemLabel ?site ?countryLabel WHERE {{
  ?item {path} wd:{klass.qid} ;
        wdt:P856 ?site .
{country}  OPTIONAL {{ ?item wdt:P17 ?country . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en,de,fr,es,uk". }}
}}
ORDER BY ?site
LIMIT {limit}
"""


def _spread(rows: list[Any], take: int) -> list[Any]:
    """Рівний крок по всій довжині, а не перші N.

    Та сама причина, що й у розборі карт сайту: початок будь-якого
    впорядкування — це не вибірка, а його початок.
    """
    if take >= len(rows):
        return rows
    step = len(rows) / take
    return [rows[int(i * step)] for i in range(take)]


def fetch(
    klass: Klass,
    country_qid: str | None = None,
    country_code: str = "",
    limit: int = FETCH_LIMIT,
    take: int | None = None,
    client: httpx.Client | None = None,
) -> tuple[list[Candidate], str]:
    """Один запит до WDQS. Повертає кандидатів і опис проблеми, якщо була."""
    owned = client is None
    client = client or httpx.Client(timeout=90)
    try:
        response = client.get(
            ENDPOINT,
            params={"query": _sparql(klass, country_qid, limit), "format": "json"},
            headers={
                "User-Agent": _user_agent(),
                "Accept": "application/sparql-results+json",
            },
        )
        if response.status_code != 200:
            return [], f"{klass.label}/{country_code or 'global'}: HTTP {response.status_code}"
        rows = response.json()["results"]["bindings"]
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return [], f"{klass.label}/{country_code or 'global'}: {type(exc).__name__}: {exc}"
    finally:
        if owned:
            client.close()

    chosen = _spread(rows, take) if take else rows
    found = []
    for row in chosen:
        site = row.get("site", {}).get("value", "")
        if not site:
            continue
        found.append(
            Candidate(
                url=site,
                segment=klass.segment,
                klass=klass.label,
                country=country_code or row.get("countryLabel", {}).get("value", ""),
                label=row.get("itemLabel", {}).get("value", "")[:90],
            )
        )
    return found, ""


def harvest(
    *,
    per_country: int = 12,
    per_global: int = 90,
    countries: tuple[tuple[str, str], ...] = COUNTRIES,
    classes: tuple[Klass, ...] = CLASSES,
    on_event: Any = None,
) -> Harvest:
    """Зібрати кандидатів по класах і країнах."""
    say = on_event or (lambda m: print(m, flush=True))
    result = Harvest()
    seen: set[str] = set()

    with httpx.Client(timeout=90) as client:
        # 1. Глобально по кожному класу — щоб узяти й ті країни, яких
        #    немає в списку нижче.
        for klass in classes:
            found, problem = fetch(
                klass, None, "", take=per_global, client=client
            )
            result.queries += 1
            if problem:
                result.problems.append(problem)
            for candidate in found:
                if candidate.url not in seen:
                    seen.add(candidate.url)
                    result.candidates.append(candidate)
            say(f"  {klass.label:22} глобально: +{len(found)} (всього {len(result.candidates)})")
            time.sleep(PAUSE_S)

        # 2. По країнах — лише для класів, яких у світі багато. Питати
        #    Wikidata про зоопарки Ісландії — марно витрачати її час.
        wide = [k for k in classes if k.label in {
            "restaurant", "hotel", "newspaper", "museum", "high school",
            "business", "municipality", "library",
        }]
        for country_qid, code in countries:
            before = len(result.candidates)
            for klass in wide:
                found, problem = fetch(
                    klass, country_qid, code, limit=200, take=per_country, client=client
                )
                result.queries += 1
                if problem:
                    result.problems.append(problem)
                for candidate in found:
                    if candidate.url not in seen:
                        seen.add(candidate.url)
                        result.candidates.append(candidate)
                time.sleep(PAUSE_S)
            say(f"  {code}: +{len(result.candidates) - before} (всього {len(result.candidates)})")

    return result


def save(harvest_result: Harvest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "source": "Wikidata Query Service, property P856 (official website)",
                "endpoint": ENDPOINT,
                "queries": harvest_result.queries,
                "problems": harvest_result.problems,
                "candidates": [c.as_dict() for c in harvest_result.candidates],
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    import sys

    out = Path(sys.argv[1] if len(sys.argv) > 1 else "benchmark/candidates.json")
    got = harvest()
    save(got, out)
    print(f"\nкандидатів: {len(got.candidates)} за {got.queries} запитів -> {out}")
    if got.problems:
        print(f"проблем: {len(got.problems)}")
        for p in got.problems[:10]:
            print(f"  {p}")
