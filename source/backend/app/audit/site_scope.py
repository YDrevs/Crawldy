"""Що вважається тим самим сайтом. Одне правило на весь краул.

## Навіщо окремий модуль

Правило «це той самий сайт» жило у двох місцях і в обох було
неправильним по-різному. Екстрактор порівнював `netloc` буквально, тож
`www.kernel.org` для `kernel.org` ставав чужим сайтом. Фронтир робив
`url.startswith(origin)` — тобто порівнював рядок зі схемою, і сторінка
`https://x/page` не проходила, коли вхід був `http://x`.

На нічному прогоні це зачепило 278 сайтів із 959. Найяскравіший випадок:
`hospitalsancarlos.cl` віддав 20 внутрішніх посилань, екстрактор визнав
їх внутрішніми, а фронтир відкинув усі — бо вхід був на `http://`, а
посилання на `https://`. Прочитано одну сторінку, `failed_urls` порожній.
Ззовні це виглядало як односторінковий сайт.

## Правило

**Той самий сайт** — це:

- **та сама назва хоста** з точністю до регістру й кінцевої крапки;
- **або кореневий/`www`-варіант тієї самої назви**: `example.com` і
  `www.example.com` — псевдоніми одне одного;
- **будь-яка зі схем http/https**: сайт, що переїхав на https, лишається
  тим самим сайтом, і навпаки;
- **той самий порт**, де типовий порт схеми (80/443) дорівнює його
  відсутності.

**Не той самий сайт**:

- довільний піддомен. `shop.example.com` не є `example.com`, і
  автоматично внутрішнім не стає. Це свідоме рішення: магазин, довідка
  чи блог на піддомені — окремі сайти з окремим бюджетом краулу, і
  вважати їх одним означало б тихо витрачати бюджет клієнта на сусідів;
- схожа назва. `example.com.evil.org` закінчується на потрібний рядок і
  не має до нього стосунку — саме тому порівнюються МІТКИ імені, а не
  підрядок;
- інший порт, крім типового для схеми.

## Чого тут немає

Реєстрованого домену (`publicsuffix`) тут немає навмисно. «Той самий
реєстрований домен» зробив би внутрішніми всі піддомени одразу — це
протилежна помилка тієї, яку лагодимо, і вона дорожча: краул пішов би в
чужі розділи й витратив бюджет там.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

CRAWLABLE_SCHEMES = ("http", "https")

_DEFAULT_PORTS = {"http": 80, "https": 443}


def _host_and_port(url: str) -> tuple[str, int | None]:
    """Імʼя хоста й порт, зведені до порівнюваного вигляду.

    `urlsplit` розбирає порт окремо, тож `example.com:8080` не
    перетворюється на рядок, який можна випадково порівняти з
    `example.com`. Саме на такому порівнянні й трималася помилка.
    """
    try:
        parts = urlsplit(url)
    except ValueError:
        return "", None
    scheme = (parts.scheme or "").lower()
    if scheme not in CRAWLABLE_SCHEMES:
        return "", None
    try:
        host = (parts.hostname or "").lower().rstrip(".")
        port = parts.port
    except ValueError:
        # Порт не число — адреса зламана, і жодного сайту вона не називає.
        return "", None
    if port is not None and port == _DEFAULT_PORTS.get(scheme):
        port = None
    return host, port


def _aliases(host: str) -> frozenset[str]:
    """Хост і його `www`-двійник.

    Рівно один рівень: `www.` знімається або додається. Через це
    `www.shop.example.com` лишається псевдонімом `shop.example.com`, а
    `shop.example.com` НЕ стає псевдонімом `example.com`.
    """
    if not host:
        return frozenset()
    if host.startswith("www."):
        return frozenset({host, host[4:]})
    return frozenset({host, f"www.{host}"})


@dataclass(frozen=True, slots=True)
class SiteScope:
    """Межа сайту, встановлена точкою входу.

    Створюється з адреси, на якій краул СПРАВДІ опинився — тобто після
    перенаправлень. Вхід `http://x`, що веде на `https://www.x`, задає
    межу навколо `www.x`, і обидві початкові адреси лишаються всередині
    неї як псевдоніми.
    """

    host: str
    port: int | None
    hosts: frozenset[str]

    @staticmethod
    def from_url(url: str) -> SiteScope:
        host, port = _host_and_port(url)
        return SiteScope(host=host, port=port, hosts=_aliases(host))

    @property
    def is_valid(self) -> bool:
        return bool(self.host)

    def contains(self, url: str) -> bool:
        """Чи належить адреса тому самому сайту.

        Схема свідомо не порівнюється: http і https — це один сайт.
        Схему все одно перевіряють окремо (`CRAWLABLE_SCHEMES`), бо
        `mailto:` і `javascript:` сайтом не є.
        """
        host, port = _host_and_port(url)
        if not host:
            return False
        return host in self.hosts and port == self.port


def same_site(url: str, origin: str) -> bool:
    """Коротка форма для місць, де тримати `SiteScope` ні до чого."""
    return SiteScope.from_url(origin).contains(url)


__all__ = ["CRAWLABLE_SCHEMES", "SiteScope", "same_site"]
