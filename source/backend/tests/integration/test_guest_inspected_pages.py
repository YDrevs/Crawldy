"""Перелік відкритих сторінок проти СПРАВЖНЬОГО PostgreSQL.

Порядок, межа й повне число живуть у SQL, тому модульний тест може довести
лише те, що потрібні речі стоять у запиті. Що вони РОБЛЯТЬ — властивість
бази, і саме вона перевіряється тут: на живому сервері, справжньою схемою з
міграцій, справжніми типами колонок і справжнім правилом сортування.

Запити рахуються не обгорткою навколо сесії, а подією рівня зʼєднання
(`before_cursor_execute`), тож у тесті видно ТОЙ САМИЙ текст SQL, який пішов
у базу. Обгортка довела б лише те, скільки разів викликали метод.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import event, text

from app.application import guest
from app.audit.enums import AuditStatus
from app.models.audit import Audit, AuditPage, AuditTarget
from app.models.identity import Organization

pytestmark = pytest.mark.asyncio


class _Statements:
    """Кожен SQL-текст, який справді пішов у зʼєднання."""

    def __init__(self) -> None:
        self.sql: list[str] = []

    def __call__(self, _conn, _cursor, statement, _params, _context, _many) -> None:
        self.sql.append(statement)

    @property
    def page_queries(self) -> list[str]:
        return [s for s in self.sql if "audit_pages" in s]


async def _watch(session):
    """Слухати зʼєднання цієї сесії; повертає лічильник і як його зняти.

    Слухається СИНХРОННИЙ engine: подія `before_cursor_execute` живе саме
    там, під асинхронною обгорткою. `get_bind()` віддає то зʼєднання, то
    engine залежно від того, як зібрана сесія, тож потрібний обʼєкт
    дістається, а не припускається.
    """
    spy = _Statements()
    bind = session.get_bind()
    engine = getattr(bind, "engine", bind)
    target = getattr(engine, "sync_engine", engine)
    event.listen(target, "before_cursor_execute", spy)
    return spy, lambda: event.remove(target, "before_cursor_execute", spy)


async def _audit(session, *, url: str = "https://example.com/") -> tuple[uuid.UUID, uuid.UUID]:
    org = Organization(id=uuid.uuid4(), name="inspected-pages",
                       slug=f"ip-{uuid.uuid4().hex[:10]}")
    session.add(org)
    await session.flush()
    audit = Audit(id=uuid.uuid4(), organization_id=org.id, url=url,
                  origin="https://example.com", status=AuditStatus.COMPLETED)
    session.add(audit)
    await session.flush()
    target = AuditTarget(id=uuid.uuid4(), audit_id=audit.id, url=url,
                         origin="https://example.com")
    session.add(target)
    await session.flush()
    return audit.id, target.id


async def _pages(session, audit_id, target_id, rows, *, ids=None):
    """rows: iterable of (url, depth, status_code) — вставляються як подано.

    `ids` дозволяє задати `AuditPage.id` явно. Це потрібно рівно одному
    тестові — тому, що доводить: порядок публічних полів не залежить від
    `id`. Із випадковими `uuid4` така перевірка була б імовірнісною
    (виміряно: протилежний порядок випадає приблизно в половині
    прогонів), а імовірнісний тест на детермінізм — це не тест.
    """
    for index, (url, depth, status_code) in enumerate(rows):
        session.add(AuditPage(
            id=(ids[index] if ids is not None else uuid.uuid4()),
            audit_id=audit_id, target_id=target_id,
            url=url, depth=depth, status_code=status_code, raw={}))
    await session.flush()


def _plain(i: int) -> str:
    """Адреса, порядок якої однаковий у будь-якому розкладі сортування."""
    return f"https://example.com/p{i:05d}"


# ── розмір вибірки: нуль, одна, рівно сто, більше за сто ──────────────────


@pytest.mark.parametrize(("count", "expect_rows", "expect_truncated"),
                         [(0, 0, False), (1, 1, False), (100, 100, False),
                          (101, 100, True), (250, 100, True)])
async def test_the_cap_and_the_total_hold_at_every_size(
    db_session, count, expect_rows, expect_truncated
):
    """Чотири розміри з інструкції плюс запас: межа, число й ознака обрізання."""
    audit_id, target_id = await _audit(db_session)
    await _pages(db_session, audit_id, target_id,
                 [(_plain(i), i % 4, 200) for i in range(count)])

    result = await guest.pages_for(db_session, audit_id)

    assert len(result.pages) == expect_rows
    assert result.total == count, "повне число рахується ДО обрізання"
    assert result.truncated is expect_truncated
    assert len(result.pages) <= guest.INSPECTED_PAGE_LIMIT


async def test_the_total_is_measured_before_the_cap_not_after_it(db_session):
    """Сто на руках і чотири тисячі в базі — саме та пара, заради якої це поле є."""
    audit_id, target_id = await _audit(db_session)
    await _pages(db_session, audit_id, target_id,
                 [(_plain(i), 0, 200) for i in range(4096)])

    result = await guest.pages_for(db_session, audit_id)

    assert result.total == 4096
    assert len(result.pages) == 100
    assert result.truncated is True
    assert result.total != len(result.pages), "довжина зрізу — не відповідь на «скільки їх»"


# ── порядок ───────────────────────────────────────────────────────────────


async def test_the_cap_is_applied_after_sorting_not_before(db_session):
    """Обрізати до сортування означало б різні сто сторінок на тих самих даних.

    Рядки вставляються у ВИПАДКОВОМУ фізичному порядку, а очікується рівно
    перша сотня за правилом сортування. Якби межа спрацьовувала першою,
    повернулися б сто випадкових.
    """
    audit_id, target_id = await _audit(db_session)
    made = [(_plain(i), 0, 200) for i in range(150)]
    shuffled = made[75:] + made[:75]
    await _pages(db_session, audit_id, target_id, shuffled)

    result = await guest.pages_for(db_session, audit_id)

    assert [p.url for p in result.pages] == [u for u, _d, _s in made[:100]]
    assert result.total == 150
    assert result.truncated is True


async def test_depth_comes_first_and_url_second(db_session):
    """Публічне правило — глибина, потім адреса."""
    audit_id, target_id = await _audit(db_session)
    await _pages(db_session, audit_id, target_id, [
        ("https://example.com/b", 2, 200),
        ("https://example.com/a", 2, 200),
        ("https://example.com/z", 0, 200),
        ("https://example.com/m", 1, 404),
    ])

    result = await guest.pages_for(db_session, audit_id)

    assert [(p.depth, p.url) for p in result.pages] == [
        (0, "https://example.com/z"),
        (1, "https://example.com/m"),
        (2, "https://example.com/a"),
        (2, "https://example.com/b"),
    ]


async def test_mixed_case_and_unicode_sort_by_bytes_under_the_explicit_collation(db_session):
    """Регістр і не-ASCII впорядковані ЯВНОЮ collation, а не правилом сервера.

    Тут є пастка, і вона варта того, щоб її назвати. Цей контейнер —
    `postgres:16-alpine`, його база створена з `en_US.utf8`, але на musl
    це правило збігається з байтовим: `ORDER BY url` і
    `ORDER BY url COLLATE "C"` дають на ньому ОДНЕ Й ТЕ САМЕ. Тобто
    порівняння результату з очікуваним байтовим порядком тут не довело б
    нічого — прибери `COLLATE "C"` із запиту, і тест усе одно був би
    зелений.

    Тому тверджень два, і вони різні:

    * порядок справді байтовий (нижче);
    * і «яка саме collation» на ЦЬОМУ сервері змінює відповідь — що
      доводиться окремо, знайденою на ньому collation, під якою той самий
      корпус упорядковується інакше. Без цього пін collation виглядав би
      косметикою.

    Те, що ловить саме ВИДАЛЕННЯ `COLLATE "C"`, — перевірка тексту
    запиту у `test_exactly_one_bounded_query_reaches_the_database`.
    """
    audit_id, target_id = await _audit(db_session)
    tails = ["a", "B", "c", "Z", "_", "0", "9", "ä", "я"]
    urls = [f"https://example.com/{tail}" for tail in tails]
    await _pages(db_session, audit_id, target_id,
                 [(u, 0, 200) for u in reversed(urls)])

    result = await guest.pages_for(db_session, audit_id)
    assert [p.url for p in result.pages] == sorted(urls), (
        "порядок не байтовий — схоже, явну collation прибрано або змінено"
    )

    # Чи є на цьому сервері collation, під якою відповідь була б іншою?
    rows = (await db_session.execute(
        text("SELECT collname FROM pg_collation WHERE collprovider = 'i' "
             "AND collname NOT LIKE 'C.%' ORDER BY collname"))).scalars().all()
    differing = []
    for collname in rows:
        ordered = (await db_session.execute(
            text("SELECT u.s FROM unnest(CAST(:urls AS text[])) AS u(s) "
                 f'ORDER BY u.s COLLATE "{collname}"'), {"urls": urls})).scalars().all()
        if list(ordered) != sorted(urls):
            differing.append((collname, list(ordered)))
            break

    assert differing, (
        "на цьому сервері жодна доступна collation не впорядковує корпус інакше, "
        "тож поведінковий бік цього твердження тут непровірюваний; лишається "
        "перевірка тексту запиту"
    )
    collname, other = differing[0]
    assert [p.url for p in result.pages] != other, (
        f"перелік пішов за {collname}, а не за явною {guest.URL_COLLATION}"
    )


async def test_the_same_rows_inserted_differently_come_back_identically(db_session):
    """Детермінізм: фізичний порядок вставки не впливає на відповідь."""
    made = [(f"https://example.com/{t}/p{i:04d}", i % 5, 200)
            for i, t in enumerate(["a", "B", "c", "Z", "_"] * 40)]
    shapes = []
    for rotation in (0, 37, 91):
        audit_id, target_id = await _audit(db_session)
        rotated = made[rotation:] + made[:rotation]
        await _pages(db_session, audit_id, target_id, rotated)
        result = await guest.pages_for(db_session, audit_id)
        shapes.append([(p.depth, p.url) for p in result.pages])

    assert shapes[0] == shapes[1] == shapes[2]
    assert len(shapes[0]) == guest.INSPECTED_PAGE_LIMIT


async def test_duplicate_url_and_depth_with_different_statuses_order_by_status(db_session):
    """Однакові адреса й глибина, РІЗНІ статуси — і відповідь одна й та сама.

    Це те, чого бракувало. Сусідній тест вставляє ті самі рядки в різному
    фізичному порядку, але з унікальними адресами, тож нічиєї не буває
    взагалі; тест нижче має дублікати, але всі зі статусом 200, тож
    порядок між ними не спостерігається й будь-який зійде. Жоден із двох
    не міг побачити дефект.

    Дефект такий: поки `id` був єдиним ключем після адреси, порядок
    рядків із однаковою парою (глибина, адреса) вирішував `uuid4`. Те
    саме логічне наповнення, записане вдруге, отримувало інші `id` — і
    могло віддати `status` та `read` у іншому порядку. Стабільність двох
    читань одного збереженого стану це давало; однаковість відповіді на
    однакових даних — ні.

    Тому `id` тут задані ЯВНО і в порядку, зворотному до потрібного:
    якщо прибрати `status_code` з `order_by`, тест падає щоразу, а не
    приблизно в половині прогонів.
    """
    url = "https://example.com/same"
    statuses = [500, 404, 200]

    shapes = []
    for physical in ([0, 1, 2], [2, 1, 0], [1, 2, 0]):
        audit_id, target_id = await _audit(db_session)
        # Свіжі `id` на кожну ітерацію: `audit_pages.id` — первинний ключ
        # таблиці, а не пари з аудитом, тож ті самі значення вдруге не
        # вставляться. Властивість, яка тут потрібна, не в конкретних
        # значеннях, а в їхньому ПОРЯДКУ: `id` за зростанням роздані
        # статусам за спаданням, тож сортування самим лише `id` дало б
        # 500, 404, 200 — протилежне до правильного.
        ordered_ids = sorted(uuid.uuid4() for _ in statuses)
        rows = [(url, 1, statuses[i]) for i in physical]
        ids = [ordered_ids[i] for i in physical]
        await _pages(db_session, audit_id, target_id, rows, ids=ids)
        result = await guest.pages_for(db_session, audit_id)
        # Повні серіалізовані кортежі, а не лише (глибина, адреса).
        shapes.append([(p.url, p.status, p.depth, p.read) for p in result.pages])

    assert shapes[0] == shapes[1] == shapes[2], "фізичний порядок вставки змінив відповідь"
    assert shapes[0] == [
        (url, 200, 1, True),
        (url, 404, 1, False),
        (url, 500, 1, False),
    ], "публічні поля мають бути впорядковані статусом, а не id"


async def test_null_statuses_have_an_explicit_place_in_the_order(db_session):
    """`NULL` не «десь наприкінці за замовчуванням», а на названому місці.

    Тут ДВА твердження, і друге існує тому, що першого не досить.

    Поведінка: `NULL` іде останнім. Але дефолт PostgreSQL для `ASC` — і є
    `NULLS LAST`, тож на ЦЬОМУ сервері прибирання явного `.nulls_last()`
    нічого не змінює, і сама лише поведінка відрізнити явне від неявного
    не може. Виміряно: мутація, яка знімає цей виклик, проходила тест.

    Саме тому поруч стоїть твердження про SQL, який РЕАЛЬНО пішов у
    зʼєднання. Дефолт розміщення `NULL` належить діалектові; контракт
    обіцяє порядок, а не «той порядок, який цей сервер обирає мовчки»,
    і перевірити цю обіцянку можна лише в тексті запиту.

    Та сама пастка, що з `COLLATE "C"`: збіг дефолту з бажаним робить
    поведінковий тест зеленим і порожнім.
    """
    url = "https://example.com/mixed"
    audit_id, target_id = await _audit(db_session)
    ids = sorted(uuid.uuid4() for _ in range(3))
    await _pages(db_session, audit_id, target_id,
                 [(url, 0, None), (url, 0, 404), (url, 0, 200)],
                 ids=[ids[0], ids[1], ids[2]])

    spy, stop = await _watch(db_session)
    try:
        result = await guest.pages_for(db_session, audit_id)
    finally:
        stop()

    assert [(p.status, p.read) for p in result.pages] == [
        (200, True), (404, False), (None, False),
    ]
    sql = " ".join(spy.page_queries)
    assert "NULLS LAST" in sql.upper(), "розміщення NULL має бути в запиті, а не в дефолті"
    assert "STATUS_CODE ASC NULLS LAST" in sql.upper(), sql


async def test_equal_depth_and_url_are_broken_deterministically(db_session):
    """Однакові глибина й адреса — і все одно один і той самий порядок.

    Пара (`audit_id`, `url`) неунікальна за схемою, тож такі рядки
    можливі. Без третього ключа база вільна повертати їх як завгодно, і
    два виклики на тих самих даних могли б розійтися.
    """
    audit_id, target_id = await _audit(db_session)
    await _pages(db_session, audit_id, target_id,
                 [("https://example.com/same", 1, 200)] * 12
                 + [("https://example.com/other", 1, 200)])

    first = await guest.pages_for(db_session, audit_id)
    second = await guest.pages_for(db_session, audit_id)

    assert first.total == 13
    # Стабільність між викликами — і є твердження. Який саме з дванадцяти
    # однакових рядків стоїть першим, контракт не обіцяє й обіцяти не може;
    # він обіцяє, що відповідь та сама.
    assert [(p.depth, p.url) for p in first.pages] == [(p.depth, p.url) for p in second.pages]
    urls = [p.url for p in first.pages]
    assert urls[0] == "https://example.com/other", "адреса все ще впорядкована перед нічиєю"
    assert urls[1:] == ["https://example.com/same"] * 12


# ── правило «прочитано» ───────────────────────────────────────────────────


async def test_read_is_false_for_null_and_for_non_success_statuses(db_session):
    """`None`, 199, 300 і 404 — не прочитано."""
    audit_id, target_id = await _audit(db_session)
    await _pages(db_session, audit_id, target_id, [
        ("https://example.com/a", 0, None),
        ("https://example.com/b", 0, 199),
        ("https://example.com/c", 0, 300),
        ("https://example.com/d", 0, 404),
    ])

    result = await guest.pages_for(db_session, audit_id)

    assert [(p.url[-1], p.status, p.read) for p in result.pages] == [
        ("a", None, False), ("b", 199, False), ("c", 300, False), ("d", 404, False)]


async def test_read_is_true_across_the_whole_success_range(db_session):
    """200, 204 і 299 — прочитано."""
    audit_id, target_id = await _audit(db_session)
    await _pages(db_session, audit_id, target_id, [
        ("https://example.com/a", 0, 200),
        ("https://example.com/b", 0, 204),
        ("https://example.com/c", 0, 299),
    ])

    result = await guest.pages_for(db_session, audit_id)

    assert all(p.read for p in result.pages)
    assert [p.status for p in result.pages] == [200, 204, 299]


# ── ізоляція й форма запиту ───────────────────────────────────────────────


async def test_a_neighbouring_audit_never_appears(db_session):
    """Сусідній аудит із сотнями сторінок не потрапляє у вибірку взагалі."""
    mine, my_target = await _audit(db_session)
    theirs, their_target = await _audit(db_session)
    await _pages(db_session, mine, my_target,
                 [(_plain(i), 0, 200) for i in range(5)])
    await _pages(db_session, theirs, their_target,
                 [(f"https://other.example/{i:05d}", 0, 200) for i in range(400)])

    result = await guest.pages_for(db_session, mine)

    assert result.total == 5, "повне число рахує лише мій аудит"
    assert len(result.pages) == 5
    assert all(p.url.startswith("https://example.com/") for p in result.pages)


async def test_exactly_one_bounded_query_reaches_the_database(db_session):
    """Один запит, і в ньому все: предикат, порядок, collation, межа, рахунок.

    Перевіряється текст, який СПРАВДІ пішов у зʼєднання, а не той, що
    міг би зібратися: другий `COUNT(*)` або втрачена collation тут видно.
    """
    audit_id, target_id = await _audit(db_session)
    await _pages(db_session, audit_id, target_id,
                 [(_plain(i), i % 3, 200) for i in range(120)])

    spy, stop = await _watch(db_session)
    try:
        result = await guest.pages_for(db_session, audit_id)
    finally:
        stop()

    assert len(spy.page_queries) == 1, (
        f"очікувався один запит по audit_pages, а пішло {len(spy.page_queries)}")
    sql = spy.page_queries[0]
    assert "WHERE audit_pages.audit_id =" in sql
    assert "ORDER BY" in sql and "audit_pages.depth" in sql
    assert 'COLLATE "C"' in sql, "явну collation прибрано з запиту"
    assert "count(*) OVER ()" in sql, "повне число більше не віконне"
    assert "LIMIT" in sql
    assert sql.index("ORDER BY") < sql.index("LIMIT")
    assert sql.upper().count("SELECT") == 1, "у запиті зʼявився підзапит або другий рахунок"
    assert result.total == 120
