"""Реєстр систем вимірювання: хто це, за яким правилом і наскільки доведено.

Правила жили підрядками в трьох таблицях екстрактора, і кожна з них помилялась
по-своєму. `/v1/p` без хоста зараховував наш власний `/v1/plans` за Segment, а
заразом `/youtubei/v1/player` і Wix `/v1/tags`. Токен `analytics` будь-де в
адресі робив «власним лічильником» і маршрут `/admin/analytics`, і чужий
`sandbox-checkout-analytics.paddle.com`. Звідси один реєстр із явними
правилами й чотирма видами спостережень (E-11a/b/c).

Чотири види, і кожне спостереження — рівно один із них:

* `VERIFIED_VENDOR` — правило, привʼязане до хоста вендора, або задокументоване
  проксі на власному походженні РАЗОМ із сигналом того самого вендора;
* `VERIFIED_CO_SIGNAL` — inline-маркер або глобальний обʼєкт, специфічний
  настільки, що називає вендора без мережевого запиту;
* `UNIDENTIFIED_MEASUREMENT` — вимірювання видно, вендора назвати не можна;
* `NONE` — жодного сліду вимірювання.

Хости порівнюються за мітками імені, а не підрядком: `notsegment.io`,
`segment.io.example.com` і `google-analytics.com.evil.example` не вендорські.
Регістр, кінцева крапка, порт і userinfo на висновок не впливають.

Тут немає жодного мережевого виклику й жодної залежності, яка б їх робила.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from app.audit.site_scope import SiteScope

# Скільки спостережень потрапляє в докази. Решта лишається у висновку:
# доказ має пояснювати класифікацію, а не перевозити журнал мережі.
EVIDENCE_CAP = 12
# Скільки символів адреси зберігаємо. Запит без параметрів — саме тому:
# у query живуть ідентифікатори відвідувача, і доказу вони не потрібні.
SIGNAL_CAP = 160


class Kind(StrEnum):
    VERIFIED_VENDOR = "VERIFIED_VENDOR"
    VERIFIED_CO_SIGNAL = "VERIFIED_CO_SIGNAL"
    UNIDENTIFIED_MEASUREMENT = "UNIDENTIFIED_MEASUREMENT"
    NONE = "NONE"


class Channel(StrEnum):
    """Звідки сигнал. Канал — частина доказу, а не оформлення."""

    SOURCE = "source"
    INLINE = "inline_marker"
    REQUEST = "request"
    RUNTIME = "runtime_global"
    LEGACY_PAGE = "legacy_page_marker"
    LEGACY_RUNTIME = "legacy_runtime_marker"


VERIFIED_KINDS = (Kind.VERIFIED_VENDOR, Kind.VERIFIED_CO_SIGNAL)
_KIND_ORDER = {
    Kind.VERIFIED_VENDOR: 0,
    Kind.VERIFIED_CO_SIGNAL: 1,
    Kind.UNIDENTIFIED_MEASUREMENT: 2,
    Kind.NONE: 3,
}


@dataclass(frozen=True, slots=True)
class Observation:
    """Один сигнал: що бачили, яким правилом і що це доводить."""

    kind: Kind
    rule_id: str
    channel: Channel
    signal: str
    vendor: str = ""
    legacy: bool = False

    @property
    def verified(self) -> bool:
        return self.kind in VERIFIED_KINDS

    def to_json(self) -> dict[str, str]:
        row = {
            "kind": self.kind.value,
            "rule_id": self.rule_id,
            "channel": self.channel.value,
            "signal": self.signal,
        }
        if self.vendor:
            row["vendor"] = self.vendor
        if self.legacy:
            row["legacy"] = "true"
        return row

    @staticmethod
    def from_json(row: dict[str, str]) -> Observation | None:
        """Спостереження зі знімка. Незнайомий рядок — не спостереження."""
        try:
            kind = Kind(row["kind"])
            channel = Channel(row["channel"])
        except (KeyError, ValueError):
            return None
        return Observation(
            kind=kind,
            rule_id=str(row.get("rule_id", "")),
            channel=channel,
            signal=str(row.get("signal", "")),
            vendor=str(row.get("vendor", "")),
            legacy=row.get("legacy") == "true",
        )


@dataclass(frozen=True, slots=True)
class HostRule:
    """Хости й шляхи, за якими вони належать саме цьому вендорові.

    Вендор буває гостем на чужому хості: `googletagmanager.com/gtag/js` —
    завантажувач Google Analytics, хоча саме імʼя хоста належить Tag
    Manager, який роздає звідти ж `gtm.js`.
    """

    hosts: tuple[str, ...]
    paths: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Vendor:
    """Оголошення вендора. Дані, а не логіка.

    * `hosts` — імена, які належать вендорові; збіг за мітками;
    * `host_paths` — коли на тому самому хості живе не лише цей вендор
      (`googletagmanager.com` роздає і gtag.js, і gtm.js);
    * `extra_host_rules` — хости з власними шляхами, окремо від основних:
      так GA забирає `/gtag/js` у Tag Manager, не забираючи всього хоста;
    * `loaders` — файл, який називає вендора сам, де б він не лежав
      (самостійно піднятий Matomo, Umami, Vercel);
    * `inline` / `globals` — співсигнали, специфічні для вендора;
    * `proxy_paths` — задокументовані проксі на ВЛАСНОМУ походженні: вони
      доводять вендора лише разом із його співсигналом.
    """

    name: str
    measurement: bool = True
    hosts: tuple[str, ...] = ()
    host_paths: tuple[str, ...] = ()
    extra_host_rules: tuple[HostRule, ...] = ()
    loaders: tuple[str, ...] = ()
    own_origin_loaders: tuple[str, ...] = ()
    inline: tuple[str, ...] = ()
    globals: tuple[str, ...] = ()
    proxy_paths: tuple[str, ...] = ()


# Вендори. `measurement=False` — інструмент поведінки чи реклами: він
# впізнається й потрапляє в докази, але сам по собі не є відповіддю на
# питання «чи міряє сайт відвідування» (`CORE_ANALYTICS` у tech.py).
VENDORS: tuple[Vendor, ...] = (
    Vendor(
        name="google_analytics",
        hosts=("google-analytics.com", "analytics.google.com"),
        # `gtag/js` лежить на хості Tag Manager, але це завантажувач GA4 —
        # так його зараховував і попередній детектор, і так його називає
        # сам Google. Тому хост забирається рівно одним шляхом.
        extra_host_rules=(HostRule(("googletagmanager.com",), ("/gtag/js",)),),
        inline=("gtag(",),
        globals=("gtag", "ga"),
        proxy_paths=("/g/collect", "/j/collect"),
    ),
    Vendor(
        name="google_tag_manager",
        hosts=("googletagmanager.com",),
        host_paths=("/gtm.js", "/ns.html"),
        globals=("google_tag_manager",),
    ),
    Vendor(name="microsoft_clarity", measurement=False, hosts=("clarity.ms",),
           inline=("clarity(",), globals=("clarity",)),
    Vendor(
        name="matomo",
        hosts=("matomo.cloud",),
        loaders=("/matomo.js", "/piwik.js", "/matomo.php", "/piwik.php"),
        inline=("_paq",),
        globals=("_paq", "Matomo"),
    ),
    Vendor(
        name="plausible",
        hosts=("plausible.io",),
        loaders=("/plausible.js",),
        inline=("window.plausible", "plausible.init"),
        globals=("plausible",),
        proxy_paths=("/api/event",),
    ),
    Vendor(name="meta_pixel", measurement=False, hosts=("connect.facebook.net",), inline=("fbq(",)),
    Vendor(name="segment", hosts=("segment.io", "segment.com"), inline=("analytics.load(",)),
    Vendor(name="amplitude", hosts=("amplitude.com",), inline=("amplitude.getinstance",),
           globals=("amplitude",)),
    Vendor(name="mixpanel", hosts=("mxpnl.com", "mixpanel.com"), inline=("mixpanel.init",),
           globals=("mixpanel",)),
    Vendor(name="heap", hosts=("heapanalytics.com", "heap-api.com"), inline=("heap.load(",),
           globals=("heap",)),
    Vendor(
        name="posthog",
        hosts=("posthog.com",),
        inline=("posthog.init",),
        globals=("posthog",),
        proxy_paths=("/ingest/", "/array/", "/decide/", "/e/"),
    ),
    Vendor(name="hotjar", measurement=False, hosts=("hotjar.com", "hotjar.io"), globals=("hj",)),
    Vendor(name="fullstory", measurement=False, hosts=("fullstory.com",), inline=("fs.identify(",),
           globals=("FS",)),
    Vendor(name="logrocket", measurement=False, hosts=("logrocket.io", "logrocket.com",
                                                       "lr-ingest.io", "lr-in.com"),
           inline=("logrocket.init",), globals=("LogRocket",)),
    Vendor(name="pendo", measurement=False, hosts=("pendo.io",), inline=("pendo.initialize",),
           globals=("pendo",)),
    Vendor(name="adobe_analytics", hosts=("adobedtm.com", "omtrdc.net")),
    Vendor(name="hubspot", hosts=("hs-scripts.com", "hs-analytics.net"),
           inline=("hubspotonwebflow",)),
    Vendor(name="yandex_metrika", hosts=("mc.yandex.ru", "mc.yandex.com"),
           host_paths=("/metrika", "/watch"), globals=("ym",)),
    Vendor(name="cloudflare_analytics", hosts=("cloudflareinsights.com",)),
    Vendor(name="vercel_analytics",
           own_origin_loaders=("/_vercel/insights", "/_vercel/speed-insights"),
           globals=("va", "__VERCEL_INSIGHTS")),
    Vendor(name="fathom", hosts=("usefathom.com",), globals=("fathom",)),
    Vendor(name="umami", hosts=("umami.is",), loaders=("/umami.js", "/umami/script.js"),
           globals=("umami",), proxy_paths=("/api/send",)),
    Vendor(name="snowplow", hosts=("snowplowanalytics.com",), loaders=("/snowplow.js",)),
)

BY_NAME: dict[str, Vendor] = {vendor.name: vendor for vendor in VENDORS}
VENDOR_NAMES: frozenset[str] = frozenset(BY_NAME)
MEASUREMENT_VENDORS: tuple[str, ...] = tuple(
    sorted(vendor.name for vendor in VENDORS if vendor.measurement)
)

# Глобальні обʼєкти живої сторінки. Рендерер віддає їх із префіксом
# `global:`, тож голий рядок у знімку — завжди спадщина, а не свіже
# спостереження. `dataLayer` і `analytics.track` вендора не називають:
# перший створюють банери згоди без GTM, другий — будь-яка бібліотека
# з методом `track` (E11-d1).
GLOBAL_PREFIX = "global:"
REQUEST_PREFIX = "request:"
GENERIC_GLOBALS: dict[str, str] = {
    "dataLayer": "generic.runtime.data_layer",
    "analytics.track": "generic.runtime.analytics_track",
}
RUNTIME_GLOBALS: tuple[str, ...] = tuple(
    dict.fromkeys(
        [name for vendor in VENDORS for name in vendor.globals] + list(GENERIC_GLOBALS)
    )
)

# Загальні ознаки вимірювання на ВЛАСНОМУ походженні: сегмент шляху або
# мітка власного піддомену. Сегмент, а не підрядок: `/collections/` — не
# `/collect`, а `google-analytics-dashboard-for-wp` — не `analytics`.
MEASUREMENT_SEGMENTS: frozenset[str] = frozenset(
    {"analytics", "telemetry", "collect", "beacon", "metrics", "stats", "ingest"}
)
MEASUREMENT_HOST_LABELS: frozenset[str] = frozenset(
    {"analytics", "telemetry", "metrics", "stats", "beacon", "insights", "matomo", "piwik",
     "plausible", "umami", "posthog"}
)
# Маршрут застосунку й статичний ресурс — не кінцева точка вимірювання.
# `/admin/analytics` та його чанк Next.js саме такі (E-11b).
_APP_SECTIONS: frozenset[str] = frozenset(
    {"admin", "dashboard", "account", "app", "panel", "user", "users", "wp-admin", "settings",
     "docs", "blog", "help", "support"}
)
_ASSET_PREFIXES: tuple[str, ...] = (
    "/_next/", "/static/", "/assets/", "/wp-content/", "/wp-includes/", "/cdn/", "/build/",
    "/dist/", "/_nuxt/", "/_astro/",
)
_ASSET_SUFFIXES: tuple[str, ...] = (
    ".js", ".mjs", ".cjs", ".css", ".map", ".json", ".png", ".jpg", ".jpeg", ".gif", ".svg",
    ".webp", ".avif", ".ico", ".woff", ".woff2", ".ttf", ".eot", ".mp4", ".webm", ".pdf",
)


def _host_of(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower().rstrip(".")
    except ValueError:
        return ""


def _path_of(url: str) -> str:
    try:
        return (urlsplit(url).path or "/").lower()
    except ValueError:
        return "/"


def on_host(host: str, names: Sequence[str]) -> bool:
    """Хост вендора або його справжній піддомен — за мітками імені."""
    return any(host == name or host.endswith("." + name) for name in names)


def site_root(origin: str) -> str:
    """Корінь сайту за прийнятим правилом межі: імʼя хоста без `www.`."""
    scope = SiteScope.from_url(origin)
    host = scope.host
    return host[4:] if host.startswith("www.") else host


def owns_host(url: str, origin: str) -> bool:
    """Чи належить хост тому самому власникові — ЛИШЕ для аналітики.

    Дозволено рівно три випадки: та сама назва хоста, її прийнятий
    `www`-псевдонім і справжній піддомен кореня сайту за межами міток
    (`analytics.python.org` для `python.org`). Реєстрованого домену тут
    немає: `analytics.python.org.evil.example` не збігається, а сусід під
    ширшим доменом власним не стає.

    Ця відповідь не доводить вендора, не створює пройденої перевірки й не
    розширює межі краулу — вона лише дозволяє назвати вимірювання
    невпізнаним замість того, щоб оголосити його відсутнім.
    """
    scope = SiteScope.from_url(origin)
    if not scope.is_valid:
        return False
    if scope.contains(url):
        return True
    host = _host_of(url)
    root = site_root(origin)
    return bool(host) and bool(root) and host.endswith("." + root)


def redacted(url: str) -> str:
    """Адреса без параметрів, фрагмента й userinfo — рівно те, що доводить."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url[:SIGNAL_CAP]
    host = (parts.hostname or "").lower().rstrip(".")
    if parts.port:
        host = f"{host}:{parts.port}"
    scheme = f"{parts.scheme}://" if parts.scheme else ""
    return f"{scheme}{host}{parts.path}"[:SIGNAL_CAP]


def _looks_like_asset(path: str) -> bool:
    return path.startswith(_ASSET_PREFIXES) or path.endswith(_ASSET_SUFFIXES)


def _app_route(segments: Sequence[str]) -> bool:
    """Сегмент вимірювання всередині маршруту застосунку — це маршрут."""
    return bool(segments) and segments[0] in _APP_SECTIONS


def vendor_by_host(url: str) -> tuple[Vendor, str] | None:
    """Вендор, чий хост і шлях збіглися. Правило повертається разом із ним."""
    host, path = _host_of(url), _path_of(url)
    if not host:
        return None
    for vendor in VENDORS:
        # Спершу гостьові правила: `/gtag/js` на хості Tag Manager належить
        # Google Analytics, і без цього кроку його забрав би власник хоста.
        for rule in vendor.extra_host_rules:
            if on_host(host, rule.hosts) and (
                not rule.paths or any(path.startswith(prefix) for prefix in rule.paths)
            ):
                return vendor, f"{vendor.name}.host"
        if not vendor.hosts or not on_host(host, vendor.hosts):
            continue
        if vendor.host_paths and not any(path.startswith(p) for p in vendor.host_paths):
            continue
        return vendor, f"{vendor.name}.host"
    return None


def vendor_by_loader(url: str, *, own_origin: bool) -> tuple[Vendor, str] | None:
    """Файл, який називає вендора сам: `matomo.js`, `/_vercel/insights`."""
    path = _path_of(url)
    for vendor in VENDORS:
        if any(path.endswith(loader) for loader in vendor.loaders):
            return vendor, f"{vendor.name}.loader"
        if own_origin and any(path.startswith(p) for p in vendor.own_origin_loaders):
            return vendor, f"{vendor.name}.own_loader"
    return None


def vendor_by_proxy(url: str) -> tuple[Vendor, str] | None:
    """Задокументоване проксі на власному походженні. Без співсигналу — не вендор."""
    path = _path_of(url)
    for vendor in VENDORS:
        for proxy in vendor.proxy_paths:
            if path.startswith(proxy) or path == proxy.rstrip("/"):
                return vendor, f"{vendor.name}.proxy"
    return None


def generic_measurement(url: str) -> str | None:
    """Ознака вимірювання без вендора на власному походженні — або нічого.

    Хост перевіряється ПЕРШИМ: `analytics.python.org/js/script.js` — це
    вимірювальний вузол сайту, і те, що він роздає `.js`, нічого не
    спростовує. А от `/admin/analytics/page-0a1b.js` у чанку застосунку —
    саме ресурс маршруту, і слово в шляху про вимірювання не свідчить.
    """
    label = _host_of(url).split(".")[0]
    if label in MEASUREMENT_HOST_LABELS:
        return "generic.measurement_host"
    path = _path_of(url)
    if _looks_like_asset(path):
        return None
    segments = [segment for segment in path.split("/") if segment]
    if _app_route(segments):
        return None
    if any(segment in MEASUREMENT_SEGMENTS for segment in segments):
        return "generic.measurement_path"
    return None


def inline_signals(text: str) -> list[tuple[Vendor, str]]:
    """Inline-маркери, специфічні для вендора. Текст сторінки сюди не входить."""
    lowered = text.lower()
    found: list[tuple[Vendor, str]] = []
    for vendor in VENDORS:
        for marker in vendor.inline:
            if marker.lower() in lowered:
                found.append((vendor, marker))
                break
    return found


def vendor_by_global(name: str) -> tuple[Vendor, str] | None:
    for vendor in VENDORS:
        if name in vendor.globals:
            return vendor, f"{vendor.name}.global"
    return None


def observe_source(url: str, *, origin: str) -> Observation:
    """Адреса ресурсу сторінки або її запиту → рівно одне спостереження."""
    own = owns_host(url, origin)
    match = vendor_by_host(url) or vendor_by_loader(url, own_origin=own)
    if match is not None:
        vendor, rule = match
        return Observation(Kind.VERIFIED_VENDOR, rule, Channel.SOURCE, redacted(url), vendor.name)
    if own:
        proxy = vendor_by_proxy(url)
        if proxy is not None:
            vendor, rule = proxy
            return Observation(
                Kind.UNIDENTIFIED_MEASUREMENT, f"{rule}.unconfirmed", Channel.SOURCE,
                redacted(url), vendor.name,
            )
        rule_id = generic_measurement(url)
        if rule_id is not None:
            return Observation(
                Kind.UNIDENTIFIED_MEASUREMENT, rule_id, Channel.SOURCE, redacted(url)
            )
    return Observation(Kind.NONE, "none", Channel.SOURCE, redacted(url))


def observe_page(*, origin: str, sources: Iterable[str], inline: str) -> list[Observation]:
    """Спостереження однієї сторінки: її ресурси й inline-маркери."""
    found: list[Observation] = []
    for source in sources:
        observation = observe_source(source, origin=origin)
        if observation.kind is not Kind.NONE:
            found.append(observation)
    for vendor, marker in inline_signals(inline):
        found.append(
            Observation(Kind.VERIFIED_CO_SIGNAL, f"{vendor.name}.inline", Channel.INLINE,
                        marker, vendor.name)
        )
    return dedupe(found)


def observe_runtime(identifiers: Iterable[str]) -> list[Observation]:
    """Ідентифікатори живої сторінки: `global:<імʼя>` свіжі, голі — спадщина."""
    found: list[Observation] = []
    for identifier in identifiers:
        if identifier.startswith(REQUEST_PREFIX):
            # Запити класифікуються зі свого сирого переліку; тут вони були б
            # другим записом того самого факту.
            continue
        if identifier.startswith(GLOBAL_PREFIX):
            name = identifier[len(GLOBAL_PREFIX):]
            match = vendor_by_global(name)
            if match is not None:
                vendor, rule = match
                found.append(
                    Observation(Kind.VERIFIED_CO_SIGNAL, rule, Channel.RUNTIME, name, vendor.name)
                )
            elif name in GENERIC_GLOBALS:
                found.append(
                    Observation(Kind.UNIDENTIFIED_MEASUREMENT, GENERIC_GLOBALS[name],
                                Channel.RUNTIME, name)
                )
            continue
        found.extend(legacy_observations([identifier], Channel.LEGACY_RUNTIME))
    return dedupe(found)


def observe_requests(
    urls: Iterable[str], *, origin: str, co_signals: Iterable[str]
) -> list[Observation]:
    """Запити живої сторінки. Проксі стає вендором лише з його співсигналом."""
    verified_vendors = set(co_signals)
    found: list[Observation] = []
    for url in urls:
        own = owns_host(url, origin)
        match = vendor_by_host(url) or vendor_by_loader(url, own_origin=own)
        if match is not None:
            vendor, rule = match
            found.append(
                Observation(Kind.VERIFIED_VENDOR, rule, Channel.REQUEST, redacted(url), vendor.name)
            )
            continue
        if not own:
            continue
        proxy = vendor_by_proxy(url)
        if proxy is not None:
            vendor, rule = proxy
            if vendor.name in verified_vendors:
                found.append(
                    Observation(Kind.VERIFIED_VENDOR, rule, Channel.REQUEST, redacted(url),
                                vendor.name)
                )
            else:
                found.append(
                    Observation(Kind.UNIDENTIFIED_MEASUREMENT, f"{rule}.unconfirmed",
                                Channel.REQUEST, redacted(url), vendor.name)
                )
            continue
        rule_id = generic_measurement(url)
        if rule_id is not None:
            found.append(
                Observation(Kind.UNIDENTIFIED_MEASUREMENT, rule_id, Channel.REQUEST, redacted(url))
            )
    return dedupe(found)


def legacy_observations(strings: Iterable[str], channel: Channel) -> list[Observation]:
    """Рядки зі старого знімка: розмітки й глобальних обʼєктів там уже немає.

    Вендорський маркер лишається доказом — але саме як спадщина, без
    вигаданої адреси. Два винятки названі власником: `first_party`
    вендором не був ніколи, а голий `segment` міг народитися зі старого
    збігу `/v1/p` або з generic `analytics.track`.
    """
    found: list[Observation] = []
    for raw in strings:
        name = raw.strip()
        if not name or name.startswith((GLOBAL_PREFIX, REQUEST_PREFIX)):
            continue
        if name == "first_party":
            found.append(
                Observation(Kind.UNIDENTIFIED_MEASUREMENT, "legacy.first_party", channel, name,
                            legacy=True)
            )
        elif name == "segment":
            # Голий `segment` не свідчить ні про що. Стара умова спрацьовувала
            # на будь-якій адресі з `/v1/p` — зокрема на нашому власному
            # `/v1/plans`, — тож це не «вимірювання без вендора», а взагалі не
            # доказ. Рядок лишається у провенансі: читач має бачити, звідки
            # взявся старий висновок (E-11a). Справжній Segment у тому самому
            # знімку впізнається зі збережених запитів на його хост.
            found.append(
                Observation(Kind.NONE, "legacy.segment.unverified", channel, name, legacy=True)
            )
        elif name in VENDOR_NAMES:
            found.append(
                Observation(Kind.VERIFIED_CO_SIGNAL, f"legacy.{name}", channel, name, name,
                            legacy=True)
            )
    return dedupe(found)


def dedupe(observations: Iterable[Observation]) -> list[Observation]:
    """Без повторів і в одному порядку: вид, вендор, правило, сигнал."""
    unique = dict.fromkeys(observations)
    return sorted(
        unique,
        key=lambda o: (_KIND_ORDER[o.kind], o.vendor, o.rule_id, o.channel.value, o.signal),
    )


def vendors_of(observations: Iterable[Observation]) -> list[str]:
    """Впізнані вендори — лише з доведених спостережень, упорядковано."""
    return sorted({o.vendor for o in observations if o.verified and o.vendor})


def load_observations(rows: Iterable[dict[str, str]]) -> list[Observation]:
    return [o for o in (Observation.from_json(row) for row in rows) if o is not None]


@dataclass(frozen=True, slots=True)
class Classification:
    """Висновок про сайт: що доведено, що лишилось невпізнаним."""

    observations: tuple[Observation, ...]
    rendered: bool

    @property
    def verified(self) -> list[str]:
        return vendors_of(self.observations)

    @property
    def measurement(self) -> list[str]:
        """Вендори, які відповідають на питання чека про вимірювання."""
        return [name for name in self.verified if BY_NAME[name].measurement]

    @property
    def unidentified(self) -> list[Observation]:
        return [o for o in self.observations if o.kind is Kind.UNIDENTIFIED_MEASUREMENT]

    @property
    def kind(self) -> Kind:
        """Вид доказу, на якому тримається відповідь про вимірювання.

        Вендор поведінки чи реклами (`measurement=False`) у переліку
        впізнаних лишається, але на це питання не відповідає: сайт із самим
        лише піксельом реклами не міряє відвідування, і вид тут `NONE`.
        """
        measured = set(self.measurement)
        if measured:
            for observation in self.observations:
                if observation.vendor in measured and observation.kind is Kind.VERIFIED_VENDOR:
                    return Kind.VERIFIED_VENDOR
            return Kind.VERIFIED_CO_SIGNAL
        return Kind.UNIDENTIFIED_MEASUREMENT if self.unidentified else Kind.NONE

    @property
    def verdict(self) -> str:
        if self.measurement:
            return "PASS"
        if self.unidentified:
            return "NO_VERDICT"
        return "FAIL"

    @property
    def coverage(self) -> str:
        """Неповне лише тоді, коли рендер міг би ще показати лічильник."""
        if self.measurement or self.unidentified or self.rendered:
            return "COMPLETE"
        return "PARTIAL"

    @property
    def unresolved(self) -> bool:
        """Висновок відкритий: або вимірювання без вендора, або неповний огляд."""
        return not self.measurement and (bool(self.unidentified) or not self.rendered)

    def evidence(self) -> list[dict[str, str]]:
        return [o.to_json() for o in self.observations[:EVIDENCE_CAP]]

    def unidentified_evidence(self) -> list[dict[str, str]]:
        return [o.to_json() for o in self.unidentified[:EVIDENCE_CAP]]

    def endpoints(self, limit: int = 3) -> list[str]:
        """Назвати неоднозначний доказ — вимога стану NO_VERDICT + COMPLETE."""
        return [o.signal for o in self.unidentified[:limit]]


def classify(observations: Iterable[Observation], *, rendered: bool) -> Classification:
    """Спостереження сайту → висновок. Проксі вже вирішені викликачем."""
    return Classification(tuple(dedupe(observations)), rendered)


__all__ = [
    "BY_NAME",
    "EVIDENCE_CAP",
    "GLOBAL_PREFIX",
    "MEASUREMENT_VENDORS",
    "REQUEST_PREFIX",
    "RUNTIME_GLOBALS",
    "VENDORS",
    "VENDOR_NAMES",
    "Channel",
    "Classification",
    "Kind",
    "Observation",
    "Vendor",
    "classify",
    "dedupe",
    "generic_measurement",
    "inline_signals",
    "legacy_observations",
    "load_observations",
    "observe_page",
    "observe_requests",
    "observe_runtime",
    "observe_source",
    "owns_host",
    "redacted",
    "site_root",
    "vendor_by_global",
    "vendor_by_host",
    "vendor_by_loader",
    "vendor_by_proxy",
    "vendors_of",
]
