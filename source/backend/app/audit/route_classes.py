"""Вісім канонічних класів маршруту для застосовності перевірок (E-05).

Це НЕ те саме, що `page_kinds.type_of`. Той відповідає «що це за сторінка»
— стаття, товар, контакти. Тут питання інше й вужче: **чи взагалі
стосується цього маршруту твердження, яке збирається зробити чек**.

Різниця не косметична. Сторінка входу має цілком конкретний тип, і саме
тому `noindex` на ній доречний; але вимагати від неї title заради пошуку
означає судити її правилом, якого вона не стосується. v1.2 мала широкий
конверт `STRUCTURE`, і через нього відсутній title, суперечливий canonical
та великі літери в адресі рахувались як SEO-штраф на `/login` і
`/checkout`. v1.3 розводить вісім класів явно.

## Намір доводиться, а не вгадується

Маршрут вважається **відомо непошуковим** лише тоді, коли збігається двоє:
його клас — воронка, кабінет, адмінка чи помилка, І спостережений
`noindex` або заборона в robots.txt це підтверджує.

Воронкоподібний маршрут, який індексується й не заборонений, лишається
публічним вмістом і оцінюється як публічний вміст. Причина проста:
`/checkout`, відкритий для пошуку, — це рішення власника, і мовчки
звільнити його від правил означало б вирішити за нього. Такий випадок
записується кодом A-11 `funnel_shaped_but_indexable` — саме записується,
а не змінює оцінку.

## Чому класифікація окремо від застосовності

Клас маршруту — факт про сторінку. Застосовність — політика: «чи
стосується claim-клас X маршруту класу Y». Тримати їх в одному місці
означало б, що зміна політики вимагає правки класифікатора, а зміна
словника маршрутів мовчки рухає політику. Політика живе в
`applicability.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import urlparse

from app.audit.page_kinds import Basis, PageType, classify


class RouteClass(StrEnum):
    """Вісім класів `contracts/route-classes.json`, тими самими іменами."""

    PUBLIC_INDEXABLE_CONTENT = "public_indexable_content"
    PUBLIC_NOINDEX_INFORMATIONAL = "public_noindex_informational"
    PUBLIC_SHAREABLE_CONTENT = "public_shareable_content"
    KNOWN_NON_SEARCH_FUNNEL = "known_non_search_funnel"
    AUTHENTICATED_ACCOUNT = "authenticated_account"
    PRIVATE_ADMIN_SYSTEM = "private_admin_system"
    ERROR_TRANSIENT = "error_transient"
    UNKNOWN_UNCLASSIFIED = "unknown_unclassified"


@dataclass(frozen=True, slots=True)
class RouteAttributes:
    """Ознаки класу. `None` означає «не визначено», а не «ні»."""

    public: bool | None
    shareable: bool | None
    search_target: bool | None
    authenticated: bool | None


# Таблиця ознак — копія `contracts/route-classes.json`. Її читає
# `applicability`, коли питання стосується ознаки, а не самого класу:
# соціальне прев'ю застосовне рівно там, де `shareable` істинний.
ATTRIBUTES: dict[RouteClass, RouteAttributes] = {
    RouteClass.PUBLIC_INDEXABLE_CONTENT: RouteAttributes(True, True, True, False),
    RouteClass.PUBLIC_NOINDEX_INFORMATIONAL: RouteAttributes(True, True, False, False),
    RouteClass.PUBLIC_SHAREABLE_CONTENT: RouteAttributes(True, True, False, False),
    RouteClass.KNOWN_NON_SEARCH_FUNNEL: RouteAttributes(True, False, False, False),
    RouteClass.AUTHENTICATED_ACCOUNT: RouteAttributes(False, False, False, True),
    RouteClass.PRIVATE_ADMIN_SYSTEM: RouteAttributes(False, False, False, True),
    RouteClass.ERROR_TRANSIENT: RouteAttributes(True, False, False, False),
    RouteClass.UNKNOWN_UNCLASSIFIED: RouteAttributes(None, None, None, None),
}

# Класи, чий намір треба ПІДТВЕРДИТИ спостереженою неіндексованістю.
# Без підтвердження воронкоподібний маршрут лишається публічним вмістом.
INTENT_CONFIRMED_CLASSES = frozenset({
    RouteClass.KNOWN_NON_SEARCH_FUNNEL,
    RouteClass.AUTHENTICATED_ACCOUNT,
    RouteClass.PRIVATE_ADMIN_SYSTEM,
})

# Слова маршруту, узяті з `examples_crawldy` самого контракту.
# `page_kinds` зводить усе це в один `PageType.SYSTEM`; тут потрібні три
# різні класи, бо політика для них різна: воронка публічна й неспільна,
# кабінет і адмінка — непублічні.
_FUNNEL_WORDS = frozenset({
    "login", "signin", "sign-in", "logout", "signout", "register", "signup",
    "auth", "callback", "oauth",
    "buy", "checkout", "cart", "basket", "koshyk", "payment", "pay", "billing",
    "order", "result", "success", "cancel",
})
_ACCOUNT_WORDS = frozenset({
    "app", "account", "my-account", "dashboard", "kabinet", "profile", "settings",
})
_ADMIN_WORDS = frozenset({
    "admin", "wp-admin", "wp-login", "api", "report", "internal", "system",
    "phpmyadmin", "console",
})
# Юридичне й інформаційне, яке власник свідомо тримає поза пошуком.
_INFORMATIONAL_TYPES = frozenset({PageType.LEGAL})
# Тимчасові стани: сторінка існує, поки операція триває.
_TRANSIENT_WORDS = frozenset({"processing", "pending", "running", "wait", "progress"})


@dataclass(frozen=True, slots=True)
class RouteVerdict:
    """Клас маршруту разом із тим, на чому він тримається."""

    route_class: RouteClass
    page_type: PageType
    # Чи спостерігали ми неіндексованість: `None` — не дивилися.
    noindex_observed: bool | None
    robots_disallowed: bool | None
    status_code: int | None
    # A-11: маршрут виглядає воронкою, але індексується. Запис, не оцінка.
    funnel_shaped_but_indexable: bool = False
    # На що маршрут СХОЖИЙ — до підтвердження наміру. Зберігається окремо
    # від класу, бо два питання різні й відповіді на них розходяться: клас
    # каже, чим маршрут ДОВЕДЕНО є, форма — на що він схожий. Споживачі,
    # яким намір власника не потрібен (дублікати, звірка карти), питають
    # саме форму; той, кому потрібен (посилання на закрите), — клас.
    shape: RouteClass | None = None
    # Підстава класифікації E-12 (мовний префікс знято / не оголошено).
    locale_basis: Basis = Basis.NO_LOCALE_SEGMENT

    @property
    def attributes(self) -> RouteAttributes:
        return ATTRIBUTES[self.route_class]

    def as_evidence(self) -> dict[str, Any]:
        return {
            "route_class": self.route_class.value,
            "page_type": self.page_type.value,
            "noindex_observed": self.noindex_observed,
            "robots_disallowed": self.robots_disallowed,
            "status_code": self.status_code,
            "funnel_shaped_but_indexable": self.funnel_shaped_but_indexable,
            "shape": self.shape.value if self.shape is not None else None,
            "locale_basis": self.locale_basis.value,
        }


def _words(url: str, locales: tuple[str, ...]) -> set[str]:
    """Слова маршруту після зняття оголошеної мови (E-12)."""
    from app.audit.page_kinds import path_words

    return path_words(url, locales)


def _shape(url: str, page_type: PageType, locales: tuple[str, ...]) -> RouteClass | None:
    """Клас, на який маршрут СХОЖИЙ, ще без підтвердження наміру."""
    words = _words(url, locales)
    # Тимчасовий стан перевіряється ПЕРШИМ, і це не дрібниця порядку.
    # `/payment-processing` контракт називає перехідним станом прямо, а
    # слово `payment` є і в словнику воронки: перевір воронку раніше — і
    # сторінка, що живе лише поки триває операція, стала б маршрутом
    # покупки, від якого чекають підтвердження наміру.
    if words & _TRANSIENT_WORDS:
        return RouteClass.ERROR_TRANSIENT
    if words & _ADMIN_WORDS:
        return RouteClass.PRIVATE_ADMIN_SYSTEM
    if words & _ACCOUNT_WORDS:
        return RouteClass.AUTHENTICATED_ACCOUNT
    if words & _FUNNEL_WORDS:
        return RouteClass.KNOWN_NON_SEARCH_FUNNEL
    if page_type in _INFORMATIONAL_TYPES:
        return RouteClass.PUBLIC_NOINDEX_INFORMATIONAL
    return None


def _noindex(meta_robots: str | None) -> bool:
    return "noindex" in (meta_robots or "").lower()


def classify_route(
    url: str,
    *,
    page_type: PageType | None = None,
    title: str = "",
    schema_types: tuple[str, ...] = (),
    locales: tuple[str, ...] = (),
    meta_robots: str | None = None,
    status_code: int | None = None,
    robots_disallowed: bool | None = None,
    locale_basis: Basis | None = None,
) -> RouteVerdict:
    """Клас маршруту за класифікацією E-12, статусом і спостереженою індексованістю.

    Порядок навмисний. Помилка сервера перекриває будь-який слоґ: сторінка,
    що відповіла 404, є документом помилки, хоч би що було в її адресі —
    ми бачили відповідь на власні очі, а слоґ лише припускає.

    Далі — форма маршруту, і аж потім підтвердження наміру. Маршрут, який
    ВИГЛЯДАЄ воронкою, але індексується й не заборонений, лишається
    публічним вмістом: див. A-11.
    """
    found = classify(url, title, schema_types, locales)
    page_type = page_type or found.page_type
    basis = locale_basis or found.basis
    noindex = _noindex(meta_robots) if meta_robots is not None else None

    shape = _shape(url, page_type, locales)

    def verdict(route_class: RouteClass, *, a11: bool = False) -> RouteVerdict:
        return RouteVerdict(
            route_class=route_class,
            page_type=page_type,
            noindex_observed=noindex,
            robots_disallowed=robots_disallowed,
            status_code=status_code,
            funnel_shaped_but_indexable=a11,
            shape=shape,
            locale_basis=basis,
        )

    # Спостережена помилка головніша за слоґ.
    if status_code is not None and status_code >= 400:
        return verdict(RouteClass.ERROR_TRANSIENT)

    if shape in INTENT_CONFIRMED_CLASSES:
        confirmed = bool(noindex) or bool(robots_disallowed)
        if confirmed:
            return verdict(shape)
        # Форма воронки без підтвердження: публічний вміст, запис A-11.
        if noindex is None and robots_disallowed is None:
            # Про індексованість нічого не спостерігали — вирішувати нема з чого.
            return verdict(RouteClass.UNKNOWN_UNCLASSIFIED)
        return verdict(RouteClass.PUBLIC_INDEXABLE_CONTENT, a11=True)

    if shape is RouteClass.ERROR_TRANSIENT:
        return verdict(RouteClass.ERROR_TRANSIENT)

    if shape is RouteClass.PUBLIC_NOINDEX_INFORMATIONAL:
        # Юридична сторінка, яку НЕ тримають поза пошуком, — звичайний
        # публічний вміст: клас описує намір власника, а не жанр тексту.
        return verdict(shape if noindex else RouteClass.PUBLIC_INDEXABLE_CONTENT)

    # Неоголошений мовний префікс робить маршрут невизначеним лише тоді,
    # коли й слоґ нічого не каже. Контракт вимагає обох умов одразу: «no
    # declared locale to strip, NO RECOGNISED SLUG, no observed
    # indexability signal». Перша версія цієї умови питала лише про
    # префікс — і на innopolis.ru знімала судження з двадцяти сторінок
    # послуг, тип яких класифікатор упізнав правильно. Двозначним там був
    # префікс, а не призначення сторінки.
    if page_type is PageType.OTHER and basis is Basis.LOCALE_NOT_DECLARED:
        return verdict(RouteClass.UNKNOWN_UNCLASSIFIED)

    if noindex or robots_disallowed:
        # Публічна сторінка, яку тримають поза пошуком: спільна, але не
        # ціль. Заборона в robots.txt важить тут стільки ж, скільки
        # `noindex`, і контракт каже це прямо: публічний індексований
        # вміст — це сторінка, у якої «no noindex, NOT DISALLOWED».
        # Поки перевірявся лише теґ, сторінка під `Disallow:` лишалась
        # «призначеною для пошуку» — тобто клас суперечив власному
        # означенню, а претензії про індекс судили адресу, якої пошуковик
        # не має права навіть завантажити.
        # Інформаційне від кампанійного відрізняє тип, а не адреса.
        return verdict(RouteClass.PUBLIC_NOINDEX_INFORMATIONAL if page_type in _INFORMATIONAL_TYPES
                       else RouteClass.PUBLIC_SHAREABLE_CONTENT)

    if noindex is None and robots_disallowed is None and page_type is PageType.OTHER:
        return verdict(RouteClass.UNKNOWN_UNCLASSIFIED)

    return verdict(RouteClass.PUBLIC_INDEXABLE_CONTENT)


def _robots_answered_absent(status: int | None) -> bool:
    """Чи сервер ВІДПОВІВ, що правил немає.

    404 і 410 кажуть це прямо. 2xx тут теж: розбору не сталося, тобто
    тіло або порожнє, або виявилось HTML-сторінкою помилки, — правил
    однаково немає. Мовчання (`None`), 403 і 5xx відповіддю не є: там ми
    не знаємо, що написано у файлі, і вигадувати «дозволено все» означало
    б стверджувати про чужий сервер те, чого він не казав.
    """
    if status is None:
        return False
    return status in (404, 410) or 200 <= status < 300


def classify_page(ctx: Any, page: Any) -> RouteVerdict:
    """Клас маршруту прочитаної сторінки, з усіма сигналами контексту."""
    robots = getattr(ctx, "robots", None)
    parsed = getattr(robots, "parsed", None)
    disallowed: bool | None = None
    if parsed is not None:
        try:
            disallowed = not parsed.evaluate("*", urlparse(page.url).path or "/").allowed
        except Exception:  # noqa: BLE001 — robots.txt чужий, і його розбір не має валити аудит
            disallowed = None
    elif _robots_answered_absent(getattr(robots, "status_code", None)):
        # RFC 9309: файлу немає — не заборонено нічого, і це ВІДПОВІДЬ, а
        # не мовчання. Розрізняти обовʼязково: без цього кожна сторінка
        # сайту без robots.txt — тобто саме малого сайту — виглядала б
        # маршрутом, про індексованість якого ми нічого не знаємо, і
        # справжні знахідки на ній притримувались би мовчки.
        disallowed = False
    locales = tuple(ctx.declared_locales()) if hasattr(ctx, "declared_locales") else ()
    from app.audit.types import _schema_types

    # Директива береться з тієї версії, яку бачить пошук: Google виконує
    # JS, і `noindex`, дописаний скриптом, — така сама директива, як у
    # відповіді сервера.
    seen = ctx.as_seen(page) if hasattr(ctx, "as_seen") else page
    # `or ""` тут навмисне, і воно несе весь сенс різниці між цією
    # функцією і `classify_route`.
    #
    # `None` у контракті означає «сигналу індексованості немає», і модель
    # станів каже прямо: застосовність вирішується з ЗАВАНТАЖЕНИХ фактів,
    # а там, де не завантажено нічого, вердикту немає. Саме такий маршрут
    # і є `unknown_unclassified`: адреса, про яку ми знаємо з карти чи з
    # посилання, але яку не відкривали. Її класифікує `classify_route` з
    # порожніми спостереженнями.
    #
    # Тут інший випадок: сторінку ми ЗАВАНТАЖИЛИ й розібрали. Відсутність
    # теґа robots на ній — спостереження, а не прогалина. Поки сюди
    # передавалось голе `page.meta_robots`, кожна прочитана сторінка з
    # невпізнаним слоґом на сайті, чий robots.txt не відповів, ставала
    # маршрутом невідомого призначення — і ВСІ пошукові знахідки на ній
    # мовчки зникали. Один невдалий запит по `/robots.txt` знеголошував би
    # більшу частину звіту; це гірша вада за ту, яку E-05 виправляє.
    return classify_route(
        page.url,
        title=page.title or "",
        schema_types=tuple(_schema_types(page)),
        locales=locales,
        meta_robots=(seen.meta_robots or ""),
        status_code=page.status_code,
        robots_disallowed=disallowed,
    )


__all__ = [
    "ATTRIBUTES",
    "INTENT_CONFIRMED_CLASSES",
    "RouteAttributes",
    "RouteClass",
    "RouteVerdict",
    "classify_page",
    "classify_route",
]
