"""Що вважати одним сайтом.

Правила навмисно синтаксичні: мережі тут немає й бути не може — цей код
працює у веб-процесі, а інваріант ядра забороняє йому ходити назовні.

Окремо від `audit.fetcher.origin_of` теж навмисно. Той нормалізує адресу
для краулера, і його правила можуть змінитися разом із краулером; ці
визначають, до якого сайту належить історія балів. Зміна правил краулу не
має розділяти чиюсь історію надвоє, тому це різні функції з різними
причинами існувати. Тест `test_sites_and_crawler_agree_on_simple_cases`
стежить, щоб вони не розійшлися там, де мусять збігатися.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

DEFAULT_PORTS = {"http": 80, "https": 443}

# Мітка доменного імені: букви, цифри, дефіс; не починається й не
# закінчується дефісом. Підкреслення дозволене навмисно — воно
# трапляється в піддоменах, і бути суворішими за реальність означає
# відмовляти клієнтам через букву.
_LABEL = re.compile(r"^[a-z0-9_]([a-z0-9_-]*[a-z0-9_])?$")


class InvalidSiteUrl(ValueError):
    """Адресу не можна перетворити на ідентичність сайту."""


def normalize_origin(raw: str) -> str:
    """Схема + хост (+ нестандартний порт). Усе інше відкидається.

    Що робиться:

    * хост у нижній регістр, кінцева крапка знімається;
    * стандартний порт знімається, нестандартний лишається;
    * IDN переводиться в punycode, щоб `düsseldorf.de` і
      `xn--dsseldorf-q9a.de` були одним сайтом, а не двома;
    * шлях, параметри й фрагмент відкидаються.

    Чого **не** робиться:

    * `http` не зводиться до `https`;
    * `www.` не знімається.

    Обидва «не» виглядають незручно й лишаються навмисно. Тихе злиття
    схоже на послугу рівно доти, доки два різні сайти на одному хості не
    змішають історію в одну криву, яку вже неможливо розділити. Якщо
    сайт справді редиректить, ми це побачимо після першого аудиту й
    запитаємо людину — рішення про злиття належить їй.
    """
    value = raw.strip()
    if not value:
        raise InvalidSiteUrl("порожня адреса")
    if "://" not in value:
        value = f"https://{value}"

    parsed = urlparse(value)
    if parsed.scheme not in DEFAULT_PORTS:
        raise InvalidSiteUrl(f"схема {parsed.scheme!r} не підтримується")

    host = (parsed.hostname or "").rstrip(".")
    if not host:
        raise InvalidSiteUrl("адреса без хоста")
    try:
        host = host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise InvalidSiteUrl(f"хост {host!r} не є коректним доменним ім'ям") from exc

    _assert_is_a_host(host)

    port = parsed.port
    if port is not None and port != DEFAULT_PORTS[parsed.scheme]:
        return f"{parsed.scheme}://{host}:{port}"
    return f"{parsed.scheme}://{host}"


def _assert_is_a_host(host: str) -> None:
    """Хост — це домен або IP-літерал, і нічого іншого.

    Перевірка потрібна, бо `str.encode("idna")` для чисто-ASCII рядка
    нічого не валідує: `not a url at all` спокійно проходив і ставав
    «сайтом» із пробілами в хості.

    Домен без крапки не приймаємо: продукт аудитує сайти в інтернеті, а
    односкладовий хост — це `localhost` або друкарська помилка. Помилку
    краще показати одразу, ніж через дві хвилини рядком «DNS не
    резолвиться» у звіті.
    """
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        return

    if "." not in host:
        raise InvalidSiteUrl(f"хост {host!r} без домену верхнього рівня")
    if len(host) > 253:
        raise InvalidSiteUrl("хост задовгий")
    for label in host.split("."):
        if not label or len(label) > 63 or not _LABEL.match(label):
            raise InvalidSiteUrl(f"хост {host!r} не є коректним доменним ім'ям")


def display_name_for(origin: str) -> str:
    """Назва за замовчуванням: хост без `www.` і без схеми.

    Тут `www.` прибрати можна — це підпис для людини, а не ідентичність.
    """
    host = urlparse(origin).hostname or origin
    return host.removeprefix("www.")


def looks_like_the_same_site(left: str, right: str) -> bool:
    """Чи схоже, що це один сайт у різних формах.

    Не використовується для автоматичного злиття — тільки щоб запитати
    людину. Різниця принципова: підказка може помилятися, ідентичність не
    має права.
    """
    if left == right:
        return True
    a, b = urlparse(left), urlparse(right)
    host_a = (a.hostname or "").removeprefix("www.")
    host_b = (b.hostname or "").removeprefix("www.")
    return host_a == host_b and bool(host_a)
