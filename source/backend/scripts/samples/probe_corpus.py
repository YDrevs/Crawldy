"""Жива перевірка кандидатів: що відповідає, куди веде, на чому зроблене.

## Навіщо окремий крок

Wikidata знає, кому належить адреса. Вона не знає, чи адреса сьогодні
відповідає, чи вона переїхала на інший домен і чи це взагалі окремий
сайт. Корпус, зібраний без цієї перевірки, доводиться латати посеред
нічного прогону — тобто рівно тоді, коли ніхто не дивиться.

## Що саме перевіряється

**Існування.** Немає відповіді — немає запису. Кандидат, який не
відповів, не потрапляє в корпус; ми не наповнюємо вибірку мертвими
доменами заради збоїв.

**Канонічність.** Одиниця бенчмарку — сайт, а не адреса. `example.com`,
`www.example.com`, `http://example.com` і `example.com/about` — це один
сайт, і в корпусі він має бути один раз. Ключем стає хост ПІСЛЯ
перенаправлень: два різні домени, що ведуть на третій, — теж дублікат, і
побачити це можна лише запитом.

**Теґи технологій — тільки побачені.** `wordpress` ставиться, коли у
відповіді є `wp-content` або сайт сам сказав це в `<meta generator>`.
Здогадів за виглядом домену тут немає: правило «не вигадувати метадані»
означає, що мітка або спирається на доказ, або її немає.

Мова береться з `<html lang>` — теж заява сайту про себе, а не наша
здогадка за доменною зоною: `.de` буває англомовним, `.com` — німецьким.
"""

from __future__ import annotations

import asyncio
import ipaddress
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

# Запускається і як модуль, і як скрипт: у другому випадку корінь репо
# сам собою в `sys.path` не потрапляє.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.samples import adult_filter

USER_AGENT = (
    "Mozilla/5.0 (compatible; CrawldyBenchmarkCorpus/1.0; "
    "+benchmark corpus validation)"
)

# Обидва числа підібрані не «щоб швидше», а щоб міряти сайти, а не себе.
#
# Перша перевірка йшла на 24 паралельних запитах із межею 12 с і дала
# 1876 таймаутів. Повторна перевірка вибірки з них на паралельності 3
# показала, що 63% із них ЖИВІ: ми міряли насичення власного каналу й
# записували його як властивість чужих сайтів. Корпус із такої перевірки
# складався б переважно зі швидких сайтів — тобто саме з тих, у яких
# найменше проблем.
TIMEOUT_S = 20.0
CONCURRENCY = 8
# Скільки HTML читаємо задля ознак. Маркери живуть у <head> і в перших
# екранах; тягнути мегабайти заради них — марно.
MAX_BYTES = 220_000

_GENERATOR = re.compile(
    rb"""<meta[^>]+name=["']generator["'][^>]+content=["']([^"']{0,120})["']""",
    re.IGNORECASE,
)
_LANG = re.compile(rb"""<html[^>]*\slang=["']([a-zA-Z-]{2,12})["']""", re.IGNORECASE)
_TITLE = re.compile(rb"<title[^>]*>(.{0,300}?)</title>", re.IGNORECASE | re.DOTALL)

# Ознаки платформ. Кожна — рядок, який ставить сама платформа; це доказ,
# а не схожість назви.
_MARKERS: tuple[tuple[str, tuple[bytes, ...]], ...] = (
    ("wordpress", (b"wp-content", b"wp-includes", b"wp-json")),
    ("shopify", (b"cdn.shopify.com", b"shopify.js", b"/cdn/shop/")),
    ("wix", (b"static.wixstatic.com", b"wix.com/website-builder")),
    ("squarespace", (b"squarespace.com", b"static1.squarespace.com")),
    ("drupal", (b"sites/default/files", b"/core/misc/drupal.js")),
    ("joomla", (b"/media/jui/", b"/media/system/js/")),
    ("typo3", (b"typo3temp", b"typo3conf")),
    ("bitrix", (b"bitrix/js", b"bitrix/templates")),
    ("tilda", (b"tildacdn.com",)),
    ("nextjs", (b"__NEXT_DATA__", b"/_next/static")),
    ("nuxt", (b"__NUXT__", b"/_nuxt/")),
    ("gatsby", (b"___gatsby", b"/page-data/")),
    ("opencart", (b"index.php?route=", b"catalog/view/theme")),
    ("prestashop", (b"prestashop", b"/modules/ps_")),
    ("woocommerce", (b"woocommerce",)),
    ("mkdocs", (b'name="generator" content="mkdocs',)),
    ("docusaurus", (b"docusaurus", b"__docusaurus")),
)


@dataclass
class Probe:
    """Що ми справді побачили, звернувшись за адресою."""

    given: str
    origin: str = ""
    alive: bool = False
    status: int | None = None
    final_url: str = ""
    canonical_host: str = ""
    redirected: bool = False
    server: str = ""
    generator: str = ""
    lang: str = ""
    tags: list[str] = field(default_factory=list)
    robots_sitemap: bool = False
    has_sitemap: bool = False
    bytes_read: int = 0
    title: str = ""
    error: str = ""
    # Виключення записується, а не робиться мовчки: тихо викинуті сайти
    # змінюють склад корпусу так, що цього ніхто не помітить.
    excluded_reason: str = ""
    excluded_evidence: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def to_origin(url: str) -> str:
    """Адреса → походження сайту.

    Одиниця бенчмарку — сайт, тож шлях відкидається: у Wikidata
    трапляється `lublin.eu/rady-dzielnic/dzielnice/slawinek/`, і це той
    самий сайт, що `lublin.eu`. Без цього кроку корпус набрав би
    «дублікатів на рівні шляху», яких постановка прямо не хоче.
    """
    raw = (url or "").strip()
    if not raw:
        return ""
    if "://" not in raw:
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    host = parsed.netloc.split("@")[-1].strip().rstrip(".").lower()
    if not host or " " in host:
        return ""
    return f"{parsed.scheme}://{host}"


def canonical_key(host: str) -> str:
    """Ключ, за яким два записи вважаються тим самим сайтом."""
    host = (host or "").lower().strip().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def is_public(host: str) -> bool:
    """Відсіяти localhost, приватні адреси й неповні імена."""
    bare = host.split(":")[0]
    if bare in ("localhost", "") or bare.endswith(".local") or bare.endswith(".internal"):
        return False
    try:
        return not ipaddress.ip_address(bare).is_private
    except ValueError:
        pass
    return "." in bare and not bare.endswith(".test") and not bare.endswith(".invalid")


def _read_markers(body: bytes, probe: Probe) -> None:
    lowered = body.lower()
    found = [name for name, needles in _MARKERS if any(n in lowered for n in needles)]
    generator = _GENERATOR.search(body)
    if generator:
        probe.generator = generator.group(1).decode("utf-8", "replace")[:120]
        low = probe.generator.lower()
        for name in ("wordpress", "drupal", "joomla", "typo3", "mkdocs",
                     "hugo", "jekyll", "docusaurus", "wix", "shopify"):
            if name in low and name not in found:
                found.append(name)
    lang = _LANG.search(body)
    if lang:
        probe.lang = lang.group(1).decode("ascii", "replace").lower()[:12]
    title = _TITLE.search(body)
    if title:
        probe.title = " ".join(
            title.group(1).decode("utf-8", "replace").split()
        )[:160]
    probe.tags = sorted(set(found))


async def probe_one(client: httpx.AsyncClient, given: str) -> Probe:
    probe = Probe(given=given)
    origin = to_origin(given)
    if not origin:
        probe.error = "malformed"
        return probe
    probe.origin = origin
    host = urlparse(origin).netloc
    if not is_public(host):
        probe.error = "not_public"
        return probe

    try:
        response = await client.get(origin, follow_redirects=True)
    except Exception as exc:  # noqa: BLE001 — класифікуємо, а не падаємо
        probe.error = type(exc).__name__
        return probe

    probe.status = response.status_code
    probe.final_url = str(response.url)
    probe.canonical_host = canonical_key(response.url.host or "")
    probe.redirected = canonical_key(host) != probe.canonical_host
    probe.server = (response.headers.get("server") or "")[:60]
    body = response.content[:MAX_BYTES]
    probe.bytes_read = len(body)
    _read_markers(body, probe)
    # 4xx/5xx — сайт існує, але нам не відповідає вмістом. Для корпусу це
    # не годиться: аудит такого сайту описував би нашу відмову.
    probe.alive = 200 <= response.status_code < 400 and probe.bytes_read > 0

    # Дорослий вміст виключається за доказом зі сторінки. Робиться це
    # ПІСЛЯ читання тіла й до всього іншого: рішення спирається на те, що
    # сайт сказав про себе, а не на вигляд домену.
    if probe.alive:
        verdict = adult_filter.classify(host, body)
        if verdict.excluded:
            probe.alive = False
            probe.excluded_reason = verdict.reason
            probe.excluded_evidence = verdict.evidence
            return probe

    if probe.alive:
        try:
            robots = await client.get(f"{origin}/robots.txt", follow_redirects=True)
            if robots.status_code == 200 and "sitemap:" in robots.text[:20000].lower():
                probe.robots_sitemap = True
                probe.has_sitemap = True
        except Exception:  # noqa: BLE001 — відсутній robots не є бідою
            pass
        if not probe.has_sitemap:
            try:
                sm = await client.get(f"{origin}/sitemap.xml", follow_redirects=True)
                ctype = (sm.headers.get("content-type") or "").lower()
                probe.has_sitemap = sm.status_code == 200 and "xml" in ctype
            except Exception:  # noqa: BLE001
                pass
    return probe


async def probe_all(urls: list[str], *, concurrency: int = CONCURRENCY,
                    request_timeout: float = TIMEOUT_S,
                    on_event: Any = None) -> list[Probe]:
    say = on_event or (lambda m: print(m, flush=True))
    semaphore = asyncio.Semaphore(concurrency)
    done = {"n": 0}
    limits = httpx.Limits(max_connections=concurrency * 2, max_keepalive_connections=20)

    async with httpx.AsyncClient(
        timeout=request_timeout, limits=limits, follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en;q=0.9,*;q=0.5"},
        verify=False,
    ) as client:                # усе одно існує; ми його класифікуємо, а не довіряємо
        async def run(url: str) -> Probe:
            async with semaphore:
                result = await probe_one(client, url)
                done["n"] += 1
                if done["n"] % 100 == 0:
                    say(f"  перевірено {done['n']} із {len(urls)}")
                return result

        return list(await asyncio.gather(*(run(u) for u in urls)))


def save(probes: list[Probe], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([p.as_dict() for p in probes], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )


if __name__ == "__main__":
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "benchmark/candidates.json")
    target = Path(sys.argv[2] if len(sys.argv) > 2 else "benchmark/probes.json")
    payload = json.loads(source.read_text(encoding="utf-8"))
    urls = [c["url"] for c in payload["candidates"]]
    print(f"перевіряю {len(urls)} кандидатів...")
    results = asyncio.run(probe_all(urls))
    save(results, target)
    alive = sum(1 for p in results if p.alive)
    print(f"живих {alive} із {len(results)} -> {target}")
