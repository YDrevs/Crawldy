"""Перевірка корпусу ДО прогону, а не після.

## Навіщо

Помилка в складі корпусу коштує стільки, скільки коштує прогін, у якому
її знайшли. Виявити на 900-му сайті, що двісті записів були тим самим
сайтом під різними адресами, означає викинути ніч роботи — і, що гірше,
всі зведені числа, бо частота спрацювання рахувалась по сайтах.

## Що тут структурна помилка, а що ні

**Структурна** — та, що робить набір даних неправильним: не та кількість,
однакові `site_id`, однакові нормалізовані адреси, зламані URL. На таких
перевірка падає.

**Неповнота міток** — не помилка. Невідома країна чи порожні теґи означають
рівно те, що написано: джерело не сказало, ми не побачили. Валити на цьому
перевірку означало б заохочувати вигадувати мітки, аби вона позеленіла, —
а це найдорожча з можливих поразок.

Концентрацію показуємо, але не забороняємо: «половина корпусу в одній
зоні» — це привід подивитися, а не автоматичний вирок.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

# Вище цієї частки в одному сегменті/зоні варто подивитися очима.
CONCENTRATION = 0.35


def normalize(url: str) -> str:
    """Адреса → канонічний ключ сайту.

    `http://Example.com/`, `https://www.example.com` і
    `https://example.com/about` — той самий сайт. Ключ не містить ані
    схеми, ані `www.`, ані шляху: одиниця бенчмарку — сайт, і саме за цим
    ключем шукаються дублікати.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return ""
    host = (parsed.netloc or "").split("@")[-1].strip().lower().rstrip(".")
    if not host or " " in host:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def is_malformed(url: str) -> bool:
    host = normalize(url)
    if not host:
        return True
    bare = host.split(":")[0]
    if "." not in bare:
        return True
    return bare in ("localhost",) or bare.endswith((".local", ".internal", ".invalid"))


def tld_of(url: str) -> str:
    host = normalize(url).split(":")[0]
    return host.rsplit(".", 1)[-1] if "." in host else ""


@dataclass
class Report:
    total: int = 0
    unique: int = 0
    expected: int | None = None
    duplicate_urls: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)
    malformed: list[str] = field(default_factory=list)
    segments: dict[str, int] = field(default_factory=dict)
    tags: dict[str, int] = field(default_factory=dict)
    tlds: dict[str, int] = field(default_factory=dict)
    untagged: int = 0
    unknown_segment: int = 0
    schemes: dict[str, int] = field(default_factory=dict)
    concentration: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        from dataclasses import asdict

        return {**asdict(self), "ok": self.ok}


def check(sites: list[Any], *, expected: int | None = None) -> Report:
    """Перевірити склад корпусу. `sites` — записи `manifest.Site`."""
    report = Report(total=len(sites), expected=expected)

    keys = Counter(normalize(s.url) for s in sites)
    report.unique = sum(1 for key, n in keys.items() if key and n >= 1)
    report.duplicate_urls = sorted(k for k, n in keys.items() if k and n > 1)

    ids = Counter(s.site_id for s in sites)
    report.duplicate_ids = sorted(i for i, n in ids.items() if n > 1)

    report.malformed = sorted(s.url for s in sites if is_malformed(s.url))
    report.segments = dict(sorted(Counter(s.segment for s in sites).items()))
    report.unknown_segment = sum(1 for s in sites if s.segment in ("", "other"))
    report.untagged = sum(1 for s in sites if not s.tags)
    report.tags = dict(Counter(t for s in sites for t in s.tags).most_common())
    report.tlds = dict(Counter(tld_of(s.url) for s in sites).most_common())
    report.schemes = dict(Counter(
        urlparse(s.url if "://" in s.url else "https://" + s.url).scheme for s in sites
    ))

    total = max(1, len(sites))
    for name, count in report.segments.items():
        if count / total > CONCENTRATION:
            report.concentration.append(
                f"сегмент {name}: {count / total:.0%} корпусу — подивитись очима"
            )
    for name, count in list(report.tlds.items())[:5]:
        if count / total > CONCENTRATION:
            report.concentration.append(
                f"зона .{name}: {count / total:.0%} корпусу — подивитись очима"
            )

    # ── структурні помилки: лише те, що робить набір неправильним ──────
    if expected is not None and len(sites) != expected:
        report.errors.append(f"записів {len(sites)}, а має бути {expected}")
    if report.duplicate_urls:
        report.errors.append(
            f"однакові нормалізовані адреси: {len(report.duplicate_urls)} "
            f"({', '.join(report.duplicate_urls[:5])})"
        )
    if report.duplicate_ids:
        report.errors.append(f"однакові site_id: {len(report.duplicate_ids)}")
    if report.malformed:
        report.errors.append(
            f"зламані адреси: {len(report.malformed)} "
            f"({', '.join(report.malformed[:5])})"
        )
    return report


def lines(report: Report) -> list[str]:
    out = [
        f"записів        : {report.total}"
        + (f" (очікувано {report.expected})" if report.expected else ""),
        f"унікальних     : {report.unique}",
        f"дублікатів URL : {len(report.duplicate_urls)}",
        f"дублікатів id  : {len(report.duplicate_ids)}",
        f"зламаних       : {len(report.malformed)}",
        f"схеми          : {report.schemes}",
        "",
        "сегменти:",
    ]
    out += [f"  {name:14} {count}" for name, count in report.segments.items()]
    out.append(f"\nбез сегмента або 'other': {report.unknown_segment}")
    out.append(f"без теґів               : {report.untagged}")
    if report.tags:
        out.append("\nтеґи (побачені, не вигадані):")
        out += [f"  {name:14} {count}" for name, count in list(report.tags.items())[:18]]
    out.append("\nдомени верхнього рівня (топ 15):")
    out += [f"  .{name:10} {count}" for name, count in list(report.tlds.items())[:15]]
    if report.concentration:
        out += ["", "КОНЦЕНТРАЦІЯ:"] + [f"  ? {c}" for c in report.concentration]
    out += ["", "ПОМИЛКИ:"] + (
        [f"  ! {e}" for e in report.errors] if report.errors else ["  немає"]
    )
    return out


__all__ = ["CONCENTRATION", "Report", "check", "is_malformed", "lines", "normalize", "tld_of"]
