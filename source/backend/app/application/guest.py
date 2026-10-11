"""Анонімна воронка: сесія, запуск аудиту, розблокування, привласнення.

Правила, а не маршрути. Роутер лише перекладає доменні відмови на коди
відповіді.

## Гість — це організація без учасників

Власником у нас завжди є організація; це те, на чому тримається
розділення орендарів у кожному запиті. Анонімна воронка не робить
власника необовʼязковим — вона створює організацію, у якої поки немає
людини. Коли людина зʼявиться, її додає один рядок `Membership`, і
жоден виміряний факт не переписується.

## Спроможність предʼявляється, а не вгадується

Доступ дає токен сесії, а не ідентифікатор аудиту. Номер в адресі
нічого не відкриває: він лише називає ресурс, а право на нього
доводиться токеном, якого немає в базі у відкритому вигляді.

## Оплата не робиться браузером

`unlock_for_purchase` викликається з обробки **перевіреної** події
провайдера, і більше нізвідки. Повернення з каси — оформлення: воно
показує сторінку, але нічого не відкриває.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import collate, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.i18n import DEFAULT_LOCALE
from app.identity.enums import OrganizationKind, Role
from app.models.audit import Audit, AuditPage
from app.models.guest import AuditUnlock, GuestMerge, GuestMergeAudit, GuestSession
from app.models.identity import Membership, Organization, User
from app.models.purchase import OneOffPurchase

#: Скільки живе спроможність гостя. Довше за очікування результату й
#: похід до каси, коротше за зберігання аудиту: прострочена сесія
#: перестає бути ключем, але куплене не зникає.
SESSION_TTL = timedelta(days=7)

#: Довжина токена. Та сама, що в публічних посилань на звіт —
#: `secrets.token_urlsafe(32)` дає 43 символи й 256 біт ентропії.
TOKEN_BYTES = 32


def _now() -> datetime:
    return datetime.now(UTC)


def hash_token(token: str) -> str:
    """SHA-256 від токена. У базі лежить лише він."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_ip(ip: str, *, salt: str) -> str:
    """Адреса для лічильників зловживання — хешем, не сама.

    Сіль зі змінних середовища: без неї хеш адреси відновлюється
    перебором за пів секунди, і зберігати його було б тим самим, що
    зберігати адресу.
    """
    if not ip:
        return ""
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


class GuestError(Exception):
    """Доменна відмова анонімної воронки."""


class SessionExpired(GuestError):
    """Спроможність існувала, але вже недійсна."""


class AlreadyClaimed(GuestError):
    """Гостьову організацію вже привласнено. Стан кінцевий."""


@dataclass(frozen=True, slots=True)
class OpenedSession:
    """Створена сесія. Відкритий токен існує лише тут і більше ніде."""

    session: GuestSession
    organization: Organization
    token: str


async def open_session(db: AsyncSession, *, ip: str = "", ip_salt: str = "") -> OpenedSession:
    """Створити гостьову організацію й сесію до неї.

    Назва організації навмисно нічого не каже про людину: ми її не
    питали. `slug` не колізує з людськими — він завжди `guest-<hex>`.
    """
    token = secrets.token_urlsafe(TOKEN_BYTES)
    marker = uuid.uuid4().hex[:12]
    organization = Organization(
        name=f"Guest {marker}",
        slug=f"guest-{marker}",
        is_personal=False,
        kind=OrganizationKind.GUEST,
    )
    db.add(organization)
    await db.flush()

    session = GuestSession(
        organization_id=organization.id,
        token_hash=hash_token(token),
        expires_at=_now() + SESSION_TTL,
        ip_hash=hash_ip(ip, salt=ip_salt),
    )
    db.add(session)
    await db.flush()
    return OpenedSession(session=session, organization=organization, token=token)


async def resolve(db: AsyncSession, token: str) -> GuestSession:
    """Сесія за токеном. Прострочена — це відмова, а не None.

    Розрізняти «немає» і «прострочено» назовні не можна: перше сказало б
    сторонньому, що такого токена не існувало. Усередині різниця
    потрібна, тому тут виняток, а роутер зводить обидва до 404.
    """
    row = await db.scalar(select(GuestSession).where(GuestSession.token_hash == hash_token(token)))
    if row is None:
        raise GuestError("спроможність недійсна")
    if not row.is_live():
        raise SessionExpired("спроможність недійсна")
    row.last_seen_at = _now()
    return row


async def owns_audit(db: AsyncSession, *, session: GuestSession, audit_id: uuid.UUID) -> bool:
    """Чи має ця сесія право читати цей аудит.

    Єдина перевірка права на читання в анонімній воронці. Номер аудиту
    сам по собі не дає нічого — саме тому він може бути в адресі.

    Дві гілки, і обидві детерміновані:

    1. аудит досі належить організації сесії — звичайний випадок;
    2. аудит **перенесено** з організації сесії записаним злиттям у
       чужу — тоді право на читання лишається: людина за нього платила,
       і створення акаунта не має забирати куплене. Доводить це журнал
       злиття, а не збіг пошти й не належність до цільової організації:
       спроможність не отримує з цієї гілки нічого, крім рівно тих
       аудитів, які були її.
    """
    owner = await db.scalar(select(Audit.organization_id).where(Audit.id == audit_id))
    if owner is None:
        return False
    if owner == session.organization_id:
        return True
    moved = await db.scalar(
        select(GuestMergeAudit.id)
        .join(GuestMerge, GuestMerge.id == GuestMergeAudit.merge_id)
        .where(
            GuestMergeAudit.audit_id == audit_id,
            GuestMerge.guest_organization_id == session.organization_id,
            GuestMerge.destination_organization_id == owner,
        )
    )
    return moved is not None


async def ensure_active_guest(db: AsyncSession, session: GuestSession) -> None:
    """Сесія має право створювати нове лише поки організація гостьова.

    Після привласнення чи злиття організація більше не гостьова, а
    старий токен усе ще живий — і без цієї перевірки він лишався б
    чорним ходом: запускав би аудити в уже особистій організації,
    витрачаючи квоту тарифу людини, а з появою підписки — її оплачені
    аудити. Читання це не обмежує: куплене лишається доступним.
    """
    kind = await db.scalar(
        select(Organization.kind).where(Organization.id == session.organization_id)
    )
    if kind is not OrganizationKind.GUEST:
        raise AlreadyClaimed("гостьову організацію вже привласнено")


async def has_unlock_history(db: AsyncSession, audit_id: uuid.UUID) -> bool:
    """Чи був цей аудит колись розблокований. Історія, не право.

    Рядок AuditUnlock не зникає при поверненні коштів — він пояснює
    минуле. Право на повний вигляд СЬОГОДНІ рахує `is_unlocked`.
    """
    found = await db.scalar(select(AuditUnlock.id).where(AuditUnlock.audit_id == audit_id))
    return found is not None


# ── E-14: які сторінки аудит справді відкривав ────────────────────────────
#
# УСЯ політика переліку живе тут, у застосунковому шарі: DTO, межа, правило
# «прочитано», порядок, розвʼязання нічиїх, єдиний запит і повне число.
# Шар звіту про неї не знає й не повинен: варто йому володіти хоч однією з
# цих відповідей, і застосунковий шар почав би питати презентацію про те,
# що зберігає база.
#
# Полів `rendered` і `discovered_via` тут немає навмисно. `rendered` живе
# лише в `SiteContext.renders` під час прогону, а `discovered_via` є в
# `PageSignals`, але `to_json()` його не пише — отже, в `audit_pages.raw`
# його немає. Показати їх можна було б тільки вгадавши, а вгадане значення
# в оплаченому звіті гірше за відсутнє поле.

#: Скільки рядків віддаємо. Повний перелік у звіті на тисячу сторінок —
#: не звіт, а дамп; повне число лишається поруч окремим полем.
INSPECTED_PAGE_LIMIT = 100


def page_was_read(status: int | None) -> bool:
    """Чи вважається сторінка прочитаною — рівно за збереженим статусом.

    Те саме правило, що в `SiteContext.ok_pages`: двохсотий діапазон і
    нічого більше. Розмір тіла, тип вмісту й `raw` тут не беруть участі —
    друга відповідь на те саме питання рано чи пізно розійшлася б із
    першою, і саме це вже коштувало проєкту кілька знахідок.
    """
    return isinstance(status, int) and 200 <= status <= 299


@dataclass(frozen=True, slots=True)
class InspectedPageRow:
    """Одна відкрита сторінка, як її бачить решта застосунку.

    Навмисно НЕ ORM-обʼєкт: назовні йде маленький DTO з чотирма полями,
    які справді потрібні звіту. Віддати `AuditPage` означало б винести
    відкладене завантаження, сесію й усю решту схеми за межу шару, що цю
    межу й тримає.
    """

    url: str
    status: int | None
    depth: int
    read: bool


@dataclass(frozen=True, slots=True)
class InspectedPages:
    """Зріз переліку: самі рядки, повне число й чи показано не все.

    Трійка тримається разом тому, що поодинці кожне число бреше: сто
    рядків без `total` виглядають як увесь сайт, а `total` без ознаки
    обрізання не каже, чи варто про решту згадувати.
    """

    pages: tuple[InspectedPageRow, ...]
    total: int
    truncated: bool


#: Порядок сортування адрес задається ЯВНО, а не успадковується від бази.
#
# `ORDER BY url` без вказаної collation сортує за правилом сервера, і
# `en_US.UTF-8` ставить `_a` поруч із `a`, ігноруючи розділові знаки, тоді
# як `C` порівнює байти. Обидва детерміновані в межах однієї бази — і
# різні між базами, тож контракт «глибина, потім адреса» без цього рядка
# означав би різний перелік на різних серверах. `C` обрано тому, що воно
# є всюди й не залежить від локалі, встановленої в образі.
URL_COLLATION = "C"


async def pages_for(db: AsyncSession, audit_id: uuid.UUID) -> InspectedPages:
    """Перші сторінки цього аудиту у порядку звіту — і скільки їх усього.

    ОДИН запит, і в ньому все. Порядок, межа й повна кількість задані в
    SQL, бо саме там вони можуть бути узгоджені: другий запит `COUNT(*)`
    читав би ту саму таблицю вдруге й міг би побачити інший її стан, а
    пара (показано, усього) з двох різних станів не описує жодного.

    Порядок: глибина, адреса в байтовій collation, статус із явним
    місцем для `NULL`, і аж потім `id`.

    Третій ключ — виправлення, а не оздоба. Пара (`audit_id`, `url`)
    неунікальна за схемою, тож два рядки з однаковою глибиною й адресою
    цілком можливі — і з РІЗНИМИ статусами. Поки ключів було три,
    порядок таких рядків вирішував `id`, а він `uuid4`: та сама логічна
    таблиця, перезаписана вдруге, отримувала інші `id` і могла віддати
    `status` і `read` у іншому порядку. Стабільність між двома читаннями
    одного збереженого стану це давало; однаковість відповіді на
    однакових даних — ні, а обіцяли саме її.

    Тепер кожне ПУБЛІЧНЕ поле впорядковане власним ключем, тож `id`
    розводить лише рядки, у яких усі чотири поля збігаються, — а їхній
    серіалізований вигляд однаковий, і порядок між ними не
    спостерігається. `NULLS LAST` стоїть явно: дефолт залежить від
    діалекта, а мовчазний дефолт — це та сама невизначеність, від якої
    цей рядок і захищає.

    Ліниве `audit.pages` тут не годиться — сесія асинхронна, і звернення
    до відношення поза запитом падає.
    """
    total = func.count().over().label("total")
    statement = (
        select(AuditPage.url, AuditPage.status_code, AuditPage.depth, total)
        .where(AuditPage.audit_id == audit_id)
        .order_by(
            AuditPage.depth.asc(),
            collate(AuditPage.url, URL_COLLATION).asc(),
            AuditPage.status_code.asc().nulls_last(),
            AuditPage.id.asc(),
        )
        .limit(INSPECTED_PAGE_LIMIT)
    )
    rows = (await db.execute(statement)).all()
    pages = tuple(
        InspectedPageRow(url=row.url, status=row.status_code, depth=row.depth,
                         read=page_was_read(row.status_code))
        for row in rows
    )
    # `total` приходить із того самого проходу віконним рахунком. Порахувати
    # його тут неможливо в принципі: до нас доїхали щонайбільше сто рядків,
    # і `len(pages)` відповів би на інше питання.
    counted = int(rows[0].total) if rows else 0
    return InspectedPages(pages=pages, total=counted, truncated=counted > len(pages))


async def is_unlocked(db: AsyncSession, audit_id: uuid.UUID) -> bool:
    """Чи чинний платний доступ до повного вигляду цього аудиту.

    Дві умови, і обидві потрібні: розблокування колись сталося І досі
    існує оплачена покупка цього аудиту. Сам рядок AuditUnlock — не
    право, а історичний факт: після повернення коштів він лишається, а
    доступ — ні.

    Покупка перевіряється за аудитом, а не через unlock.purchase_id:
    unlock один на аудит і показує на ПЕРШУ покупку, а покупок може
    бути кілька (унікальності на audit_id у них немає). Повернення
    першої не має гасити доступ, поки друга лишається оплаченою.
    """
    from app.billing.enums import PurchaseStatus

    if not await has_unlock_history(db, audit_id):
        return False
    paid = await db.scalar(
        select(OneOffPurchase.id)
        .where(
            OneOffPurchase.audit_id == audit_id,
            OneOffPurchase.status == PurchaseStatus.PAID,
        )
        .limit(1)
    )
    return paid is not None


async def paid_content_denied(db: AsyncSession, audit_id: uuid.UUID) -> bool:
    """Чи закритий платний вміст цього аудиту після повернення коштів.

    Істина рівно в одному стані: розблокування було, а чинної оплати
    немає. Аудити без історії розблокування (оплачені квотою чи
    кредитами кабінету) не зачіпаються: у них платний вміст не існує як
    окреме поняття, і ця перевірка для них завжди хибна.

    Єдина точка правди для ВСІХ шляхів доступу — гостьового, платного
    посилання, кабінету після привласнення. Друга копія цього правила в
    маршруті означала б два різні поняття «повернено».
    """
    if not await has_unlock_history(db, audit_id):
        return False
    return not await is_unlocked(db, audit_id)


async def unlock_for_purchase(
    db: AsyncSession, *, purchase: OneOffPurchase, audit_id: uuid.UUID
) -> AuditUnlock:
    """Відкрити повний вигляд аудиту за покупкою. Ідемпотентно.

    Викликається **лише** з обробки перевіреної події провайдера.
    Повторна доставка тієї самої події не створює другого рядка: заважає
    унікальність `audit_id`, а не перевірка в Python — між `SELECT` і
    `INSERT` встигає інший процес.
    """
    unlock = AuditUnlock(audit_id=audit_id, purchase_id=purchase.id)
    try:
        # add — усередині savepoint: інакше відкат лишає обʼєкт у сесії
        # pending, і перший же autoflush пробує вставити його знову,
        # отруюючи транзакцію вже поза savepoint.
        async with db.begin_nested():
            db.add(unlock)
            await db.flush()
    except IntegrityError:
        existing = await db.scalar(select(AuditUnlock).where(AuditUnlock.audit_id == audit_id))
        if existing is None:  # pragma: no cover — суперечність можлива лише при гонці зі знесенням
            raise
        return existing
    return unlock


async def unprovisioned_purchases(
    db: AsyncSession, *, limit: int = 100
) -> list[OneOffPurchase]:
    """Оплачено, але доступ не видано.

    Той самий стан, який у конкурента виглядав тишею: гроші пройшли,
    права немає, і питання «чому» не мало відповіді в базі. Тут воно
    має її запитом — і саме тому цей стан має бути видимим в адмінці, а
    не виводитися з відсутності рядка деінде.
    """
    from app.billing.enums import PurchaseStatus

    rows = await db.scalars(
        select(OneOffPurchase)
        # Звʼязок за аудитом, а не за покупкою: питання тут — «чи має
        # цей аудит розблокування», а не «чи показує розблокування саме
        # на цей рядок». Одна оплата, доставлена двома транзакціями,
        # дає дві покупки й один unlock — і друга з них не є непровіженою.
        .outerjoin(AuditUnlock, AuditUnlock.audit_id == OneOffPurchase.audit_id)
        .where(
            OneOffPurchase.audit_id.is_not(None),
            OneOffPurchase.status == PurchaseStatus.PAID,
            AuditUnlock.id.is_(None),
        )
        .order_by(OneOffPurchase.created_at)
        .limit(limit)
    )
    return list(rows)


@dataclass(frozen=True, slots=True)
class Claimed:
    """Результат привласнення гостьової організації."""

    organization: Organization
    membership: Membership


async def claim_for_new_user(
    db: AsyncSession, *, session: GuestSession, user: User
) -> Claimed:
    """Гостьова організація стає особистою організацією цієї людини.

    Шлях нової людини, і тільки він. Аудит не рухається, його власник не
    змінюється, ідентичність лишається тією самою — змінюється лише те,
    що в організації тепер є учасник.

    Наявна людина зі своєю організацією цим шляхом не йде: там потрібне
    злиття, а воно окремою операцією з журналом і окремим рішенням.
    """
    organization = await db.get(Organization, session.organization_id)
    if organization is None:  # pragma: no cover — FK не дозволяє
        raise GuestError("організації сесії не існує")
    # Організація гостьової сесії починає життя як GUEST — інакше бути
    # не може, бо створює її лише open_session. Тож будь-який інший
    # kind означає одне: її вже привласнили.
    if organization.kind is not OrganizationKind.GUEST:
        raise AlreadyClaimed("гостьову організацію вже привласнено")

    organization.kind = OrganizationKind.PERSONAL
    organization.is_personal = True
    organization.name = (user.display_name or user.email.split("@")[0])[:200]

    membership = Membership(
        user_id=user.id,
        organization_id=organization.id,
        role=Role.OWNER,
        accepted_at=_now(),
    )
    db.add(membership)
    await db.flush()
    return Claimed(organization=organization, membership=membership)


async def create_user_and_claim(
    db: AsyncSession, *, session: GuestSession, email: str, password: str, display_name: str = ""
) -> Claimed:
    """Створити людину й віддати їй гостьову організацію.

    Шлях нової людини цілком: `register` тут не годиться, бо він створює
    **свою** організацію, і в людини одразу стало б дві — гостьова з
    купленим аудитом і порожня нова. Тому користувач створюється без
    організації, а організацією стає та, що вже є.

    Наслідок головний: аудит не рухається. Його `organization_id` той
    самий, ідентичність та сама, покупка вказує на нього ж. Змінюється
    лише те, що в організації тепер є учасник.
    """
    from app.identity import passwords
    from app.identity import service as identity
    from app.identity.enums import UserStatus

    organization = await db.get(Organization, session.organization_id)
    if organization is None:  # pragma: no cover — FK не дозволяє
        raise GuestError("організації сесії не існує")
    if organization.kind is not OrganizationKind.GUEST:
        raise AlreadyClaimed("гостьову організацію вже привласнено")

    normalized = identity.normalize_email(email)
    if await identity.find_user_by_email(db, normalized) is not None:
        # Наявна людина йде іншим шляхом: там потрібне злиття організацій,
        # а не привласнення порожньої. Цей маршрут його не робить.
        raise ExistingUser(normalized)

    user = User(
        email=normalized,
        password_hash=passwords.hash_password(password),
        display_name=display_name.strip()[:200],
        status=UserStatus.PENDING,
    )
    db.add(user)
    await db.flush()
    return await claim_for_new_user(db, session=session, user=user)


class ExistingUser(GuestError):
    """Пошта вже належить акаунту.

    Не помилка й не колізія: це інший сценарій. Наявна людина має свою
    організацію, і гостьові ресурси треба **зливати** з нею, а не
    привласнювати порожню. Злиття — окрема операція з журналом
    походження, і робиться воно не тут.
    """

    def __init__(self, email: str) -> None:
        super().__init__("акаунт із такою поштою вже існує")
        self.email = email


# ── проєкції звіту ─────────────────────────────────────────────────────────
#
# Живуть тут, а не в маршруті: api не звертається до шару звіту напряму.
# Це та сама межа, яку історичні маршрути звіту порушують як визнаний
# борг, — нові її не поглиблюють.


def short_view(audit: Any, *, unlocked: bool, locale: Any = None) -> dict[str, Any]:
    """Короткий вигляд завершеного аудиту. Другого краулу немає.

    Мова приходить ззовні, бо знає її лише сторінка. Без неї документ
    складався мовою за замовчуванням (англійською), і українець бачив
    український інтерфейс із англійськими знахідками всередині.
    """
    from app.report.short import to_short

    return to_short(
        _document_for(audit, locale), audit_id=str(audit.id), unlocked=unlocked
    ).to_json()


def full_view(audit: Any, *, locale: Any = None) -> dict[str, Any]:
    """Повний звіт для екрана. Викликач уже перевірив право.

    Мова — та сама, що на сторінці: короткий вигляд і повний звіт не
    мають говорити різними мовами про той самий аудит.

    Форма — та сама, що в кабінеті (`to_web` → AuditResultResponse):
    оплачений гість бачить рівно те подання, що й передплатник, бо
    екран у них один. Другий формат означав би другий звіт, і вони
    розійшлися б.

    Без ідентифікаторів знахідок і вердиктів: вони існують, щоб людина
    в кабінеті записала свою відповідь на знахідку, а гість не має ні
    акаунта, ні цього права.
    """
    from app.audit.i18n import FALLBACK_LOCALE
    from app.report.web import to_web

    response = to_web(
        _document_for(audit, locale),
        audit_id=audit.id,
        site_id=audit.site_id,
        status=audit.status.value,
        finished_at=audit.finished_at,
        fallback_locale=FALLBACK_LOCALE.value,
    )
    return response.model_dump(mode="json")


def _document_for(audit: Any, locale: Any = None) -> Any:
    from app.audit.i18n import DEFAULT_LOCALE
    from app.report.builder import build_report
    from app.services import report_service

    target = report_service.pick_target(audit, None)
    source = (
        report_service.source_from_target(audit, target)
        if target is not None
        else report_service.source_from_audit(audit)
    )
    return build_report(source, locale or DEFAULT_LOCALE)


# ── злиття в наявну організацію ────────────────────────────────────────────


class QuotaNotSettled(GuestError):
    """У гостя є аудит із незавершеним резервом квоти.

    Зливати не можна: `settle_quota` повертає квоту в організацію
    аудиту, і перенесений до розрахунку аудит повернув би її в
    лічильник цілі, який нічого не списував. Стан минущий — клієнт
    повторює запит, коли аудит дійде кінцевого стану.
    """


class CannotMergeInto(GuestError):
    """Ціль не годиться: гостьова, привласнена або та сама організація."""


@dataclass(frozen=True, slots=True)
class Merged:
    """Результат злиття: що й куди перенесено."""

    merge: GuestMerge
    audits_moved: int
    purchases_moved: int
    credits_moved: int


async def merge_into(
    db: AsyncSession,
    *,
    session: GuestSession,
    destination_organization_id: uuid.UUID,
    performed_by_user_id: uuid.UUID | None,
    reason: str = "",
) -> Merged:
    """Перенести все гостьове в наявну організацію. Вузько й одноразово.

    Це НЕ загальний перенос орендарів: джерелом може бути лише гостьова
    організація цієї сесії, і після злиття вона термінально CLAIMED.
    У звичайного завершеного аудиту власник незмінний — виняток існує
    рівно тут і рівно з журналом.

    ## Сайти не переїжджають ніколи

    `uq_site_org_origin` — недеферабельний UNIQUE: переїзд гостьового
    сайту в ціль із тим самим origin падає одразу, і відкласти перевірку
    неможливо без зміни констрейнта. Тому цільовий сайт знаходиться за
    origin або створюється, аудити перепризначаються на нього одним
    UPDATE разом із власником, а гостьовий сайт архівується на місці.
    Унікальність не порушується ані на мить, і `Site.organization_id`
    лишається незмінним — обидва інваріанти цілі.

    ## Порядок усередині однієї транзакції

    1. лок гостьової організації; не GUEST → AlreadyClaimed
    2. перевірка цілі: існує, не гостьова, не та сама
    3. guard квоти: жодного аудиту в RESERVED
    4. на кожен гостьовий сайт: ціль за (org, origin) або новий рядок;
       UPDATE аудитів (organization_id + site_id разом); SiteMerge;
       архівація джерела
    5. аудити без сайту: лише organization_id
    6. покупки й кредити → ціль
    7. журнал злиття + перелік перенесених аудитів
    8. kind = CLAIMED
    """
    from app.core.run_enums import QuotaState
    from app.models.purchase import AuditCredit
    from app.models.sites import Site, SiteMerge

    # Лок джерела. Паралельне злиття або привласнення серіалізується
    # тут: другий бачить CLAIMED і відмовляється, а не зливає вдруге.
    organization = await db.get(Organization, session.organization_id, with_for_update=True)
    if organization is None:  # pragma: no cover — FK не дозволяє
        raise GuestError("організації сесії не існує")
    if organization.kind is not OrganizationKind.GUEST:
        raise AlreadyClaimed("гостьову організацію вже привласнено")

    if destination_organization_id == organization.id:
        raise CannotMergeInto("організація не зливається сама в себе")
    destination = await db.get(Organization, destination_organization_id)
    if destination is None or destination.kind.is_guest_funnel:
        raise CannotMergeInto("ціль не є звичайною організацією")

    pending = await db.scalar(
        select(Audit.id)
        .where(
            Audit.organization_id == organization.id,
            Audit.quota_state == QuotaState.RESERVED,
        )
        .limit(1)
    )
    if pending is not None:
        raise QuotaNotSettled("аудит гостя ще не розрахований із квотою")

    now = _now()
    site_map: list[dict[str, Any]] = []
    moved_audit_ids: list[uuid.UUID] = []

    guest_sites = list(
        await db.scalars(select(Site).where(Site.organization_id == organization.id))
    )
    for source in guest_sites:
        target = await db.scalar(
            select(Site).where(
                Site.organization_id == destination_organization_id,
                Site.origin == source.origin,
            )
        )
        created = target is None
        if target is None:
            target = Site(
                organization_id=destination_organization_id,
                origin=source.origin,
                display_name=source.display_name,
                created_by_user_id=performed_by_user_id,
            )
            db.add(target)
            await db.flush()

        moved = await db.scalars(
            update(Audit)
            .where(
                Audit.organization_id == organization.id,
                Audit.site_id == source.id,
            )
            .values(organization_id=destination_organization_id, site_id=target.id)
            .returning(Audit.id)
        )
        ids = list(moved)
        moved_audit_ids.extend(ids)

        # Журнал сайтів — той самий SiteMerge, що пояснює будь-яку зміну
        # site_id. Сама функція sites.service.merge не викликається: її
        # передумова «обидва сайти в одній організації» тут хибна, і
        # розтягувати її означало б ослабити перевірку для всіх.
        db.add(
            SiteMerge(
                organization_id=destination_organization_id,
                source_site_id=source.id,
                target_site_id=target.id,
                source_origin=source.origin,
                target_origin=target.origin,
                audits_moved=len(ids),
                reason=f"злиття гостьової організації {organization.slug}",
                performed_by_user_id=performed_by_user_id,
            )
        )
        source.archived_at = now
        site_map.append(
            {
                "origin": source.origin,
                "source_site_id": str(source.id),
                "destination_site_id": str(target.id),
                "destination_created": created,
                "audits": len(ids),
            }
        )

    # Аудити без сайту (наприклад, CLI): переносяться без перепризначення.
    orphan = await db.scalars(
        update(Audit)
        .where(
            Audit.organization_id == organization.id,
            Audit.site_id.is_(None),
        )
        .values(organization_id=destination_organization_id)
        .returning(Audit.id)
    )
    moved_audit_ids.extend(orphan)

    purchases_moved = list(
        await db.scalars(
            update(OneOffPurchase)
            .where(OneOffPurchase.organization_id == organization.id)
            .values(organization_id=destination_organization_id)
            .returning(OneOffPurchase.id)
        )
    )
    credits_moved = list(
        await db.scalars(
            update(AuditCredit)
            .where(AuditCredit.organization_id == organization.id)
            .values(organization_id=destination_organization_id)
            .returning(AuditCredit.id)
        )
    )

    merge = GuestMerge(
        guest_organization_id=organization.id,
        destination_organization_id=destination_organization_id,
        performed_by_user_id=performed_by_user_id,
        audits_moved=len(moved_audit_ids),
        purchases_moved=len(purchases_moved),
        credits_moved=len(credits_moved),
        site_map=site_map,
        reason=reason.strip(),
    )
    db.add(merge)
    await db.flush()
    for audit_id in moved_audit_ids:
        db.add(GuestMergeAudit(merge_id=merge.id, audit_id=audit_id))

    organization.kind = OrganizationKind.CLAIMED
    await db.flush()

    return Merged(
        merge=merge,
        audits_moved=len(moved_audit_ids),
        purchases_moved=len(purchases_moved),
        credits_moved=len(credits_moved),
    )


async def issue_report_link(
    db: AsyncSession, *, audit_id: uuid.UUID, lang: str = DEFAULT_LOCALE.value
) -> tuple[str, uuid.UUID]:
    """Видати безстрокове посилання на куплений звіт. (токен, link_id).

    Мова заморожується в посиланні при видачі й далі авторитетна для
    всього, що ним відкривається: екран, Word і JSON читають її з
    одного місця — `link.lang`. Дефолт — той самий, яким живуть
    сесійні екрани гостя, тож куплений звіт не змінює мови між
    коротким виглядом, повним і файлами.

    Викликач уже довів право сесією і перевірив розблокування. Посилання
    привʼязується до розблокування, а не до сесії: сесія мине за сім
    днів, а куплений доступ — ні. Токен існує відкрито лише в цій
    відповіді.

    Повторний виклик видає нове посилання, і це не дефект: поки сесія
    жива, повторна видача — єдиний спосіб відновити загублений токен.
    Кожне видане відкликається окремо.
    """
    from app.services import link_service

    if not await is_unlocked(db, audit_id):
        # Розблокування без чинної оплати — теж відмова: після
        # повернення коштів нові посилання не видаються.
        raise GuestError("повний звіт не відкрито")
    unlock = await db.scalar(select(AuditUnlock).where(AuditUnlock.audit_id == audit_id))
    if unlock is None:  # pragma: no cover — is_unlocked щойно це перевірив
        raise GuestError("повний звіт не відкрито")
    link, token = await link_service.create_link(
        db, audit_id, lang=lang, ttl_days=None, unlock_id=unlock.id
    )
    return token, link.id


async def revoke_paid_links(db: AsyncSession, *, audit_id: uuid.UUID) -> int:
    """Відкликати платні посилання аудиту. Повертає кількість.

    Лише платні: `unlock_id` відрізняє їх від поділених з кабінету, і
    повернення коштів не має обривати посилання, якими власник ділився
    сам. Право (AuditUnlock) і історія покупки лишаються — токен не є
    правом, тож його відкликання нічого не стирає.
    """
    from app.models.audit import ReportLink

    now = _now()
    revoked = await db.scalars(
        update(ReportLink)
        .where(
            ReportLink.audit_id == audit_id,
            ReportLink.unlock_id.is_not(None),
            ReportLink.revoked_at.is_(None),
        )
        .values(revoked_at=now)
        .returning(ReportLink.id)
    )
    return len(list(revoked))
