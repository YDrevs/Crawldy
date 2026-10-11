"""Корпус: перелік сайтів із сегментами й теґами.

## Чому теґи, а не одна категорія

Сайт буває водночас SaaS, багатомовним і SPA. Одна категорія змусила б
вибирати, яка з трьох «справжня», і аналіз за сегментом почав би
відповідати на питання про класифікатор, а не про продукт.

## Чому наміри, а не факти

`segment` і `tags` — це **гіпотеза людини**, яка складала корпус, а не
виміряна властивість сайту. Вивести їх з домену не можна: `.io` не
означає SaaS, а `/blog/` у назві не робить сайт видавцем. Тому вони
приходять із файлу й нікуди більше не потрапляють, крім розрізу в
аналізі; жоден чек їх не бачить.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Сегменти, які ми свідомо хочемо розрізняти. Це ЄДИНИЙ перелік:
# `scripts/samples/segments.py` розкладає класи джерела саме в ці назви,
# і тест не дає двом словникам розійтися.
#
# Раніше тут стояли `publisher` і `enterprise`, а таксономія корпусу
# називала те саме `publishing` і `corporate`. Два словники на одне
# поняття — це та сама помилка, що й два ідентифікатори на одну знахідку:
# розходження тихе, а зріз за сегментом після нього нічого не означає.
KNOWN_SEGMENTS = (
    "local",
    "corporate",
    "publishing",
    "ecommerce",
    "travel",
    "education",
    "institutional",
    "saas",
    "documentation",
    "other",
)

# Технічні ознаки двох різних родів, і плутати їх не можна.
#
# ГІПОТЕЗИ людини — «ми думаємо, що це SPA»; прогін має підтвердити або
# спростувати. СПОСТЕРЕЖЕННЯ — те, що `probe_corpus` побачив у відповіді
# (`wp-content`, `<meta generator>`). Перелік мусить містити обидва:
# закритий список для спостережень означав би викидати побачений доказ
# лише тому, що його не передбачили заздалегідь.
KNOWN_TAGS = (
    # гіпотези
    "multilingual", "spa", "ssr", "static", "docs-platform", "cdn",
    # спостережені платформи — імена збігаються з `probe_corpus._MARKERS`
    "wordpress", "woocommerce", "shopify", "wix", "squarespace", "drupal",
    "joomla", "typo3", "bitrix", "tilda", "nextjs", "nuxt", "gatsby",
    "opencart", "prestashop", "mkdocs", "docusaurus", "hugo", "jekyll",
    "webflow",
)

_SLUG = re.compile(r"[^a-z0-9]+")


def site_id_for(url: str) -> str:
    """Сталий ідентифікатор сайту.

    Слаґ домену плюс короткий хеш повної адреси: слаґ читається очима в
    іменах файлів, хеш розводить `example.com` і `example.com/uk`, які
    інакше злилися б в один рядок результатів.
    """
    cleaned = url.strip().rstrip("/")
    host = re.sub(r"^https?://", "", cleaned, flags=re.I)
    slug = _SLUG.sub("-", host.lower()).strip("-")[:48]
    digest = hashlib.blake2b(cleaned.encode(), digest_size=4).hexdigest()
    return f"{slug}-{digest}"


@dataclass(frozen=True, slots=True)
class Site:
    """Один сайт корпусу."""

    url: str
    site_id: str
    segment: str = "other"
    tags: tuple[str, ...] = ()
    enabled: bool = True
    note: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "site_id": self.site_id,
            "url": self.url,
            "segment": self.segment,
            "tags": list(self.tags),
            "enabled": self.enabled,
            "note": self.note,
        }


@dataclass(slots=True)
class Manifest:
    """Корпус цілком плюс те, що з ним не так."""

    sites: list[Site] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    path: Path | None = None

    @property
    def active(self) -> list[Site]:
        return [s for s in self.sites if s.enabled]

    def by_segment(self) -> dict[str, list[Site]]:
        found: dict[str, list[Site]] = {}
        for site in self.active:
            found.setdefault(site.segment, []).append(site)
        return dict(sorted(found.items()))

    def fingerprint(self) -> str:
        """Відбиток складу корпусу — входить у визначення прогону.

        Береться від увімкнених сайтів: додати вимкнений рядок не
        повинно робити прогін іншим.
        """
        joined = "|".join(sorted(s.site_id for s in self.active))
        return hashlib.blake2b(joined.encode(), digest_size=8).hexdigest()


def _one(raw: Any, index: int, problems: list[str]) -> Site | None:
    if isinstance(raw, str):
        raw = {"url": raw}
    if not isinstance(raw, dict):
        problems.append(f"рядок {index}: очікувався рядок або словник")
        return None

    url = str(raw.get("url") or "").strip()
    if not url:
        problems.append(f"рядок {index}: немає url")
        return None
    if not url.lower().startswith(("http://", "https://")):
        url = f"https://{url}"

    segment = str(raw.get("segment") or "other").strip().lower()
    if segment not in KNOWN_SEGMENTS:
        # Не помилка: корпус має право назвати свій сегмент. Але сказати
        # про це варто — часто це друкарська помилка.
        problems.append(f"{url}: незнайомий сегмент {segment!r}")

    tags = tuple(
        sorted({str(t).strip().lower() for t in (raw.get("tags") or []) if str(t).strip()})
    )
    for tag in tags:
        if tag not in KNOWN_TAGS:
            problems.append(f"{url}: незнайомий теґ {tag!r}")

    return Site(
        url=url,
        site_id=str(raw.get("site_id") or site_id_for(url)),
        segment=segment,
        tags=tags,
        enabled=bool(raw.get("enabled", True)),
        note=str(raw.get("note") or ""),
    )


def load(path: str | Path) -> Manifest:
    """Прочитати корпус із YAML або JSON.

    Формат навмисно поблажливий на вході: рядок з адресою — валідний
    запис. Корпус на тисячу сайтів починається як список адрес, і
    вимагати повну структуру одразу означало б заважати його зібрати.
    """
    file = Path(path)
    problems: list[str] = []
    if not file.exists():
        return Manifest(problems=[f"файл корпусу не знайдено: {file}"], path=file)

    try:
        raw = yaml.safe_load(file.read_text(encoding="utf-8")) or []
    except yaml.YAMLError as exc:
        return Manifest(problems=[f"не розібрати {file}: {exc}"], path=file)

    if isinstance(raw, dict):
        raw = raw.get("sites") or []
    if not isinstance(raw, list):
        return Manifest(problems=[f"{file}: очікувався список сайтів"], path=file)

    sites: list[Site] = []
    seen: dict[str, str] = {}
    for index, item in enumerate(raw, start=1):
        site = _one(item, index, problems)
        if site is None:
            continue
        if site.site_id in seen:
            problems.append(
                f"{site.url}: той самий site_id, що в {seen[site.site_id]} — пропущено"
            )
            continue
        seen[site.site_id] = site.url
        sites.append(site)

    return Manifest(sites=sites, problems=problems, path=file)


__all__ = ["KNOWN_SEGMENTS", "KNOWN_TAGS", "Manifest", "Site", "load", "site_id_for"]
