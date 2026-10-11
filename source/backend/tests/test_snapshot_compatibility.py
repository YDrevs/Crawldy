"""Знімок, збережений старим кодом, читається новим.

Це контракт, від якого залежить історія балів. Коли методологія
змінюється, чесне порівняння двох аудитів можливе рівно одним способом:
перерахувати старий знімок нинішніми правилами. Якщо старий знімок
перестане завантажуватися, історія втратить єдиний спосіб лишитися
порівнянною — і дізнаємось ми про це на живих даних клієнта.

`snapshot.load()` робить `SiteContext(**data["site"])` без фільтрації
ключів. Напрямок «старий → новий» працює доти, доки кожне нове поле має
дефолт; напрямок «новий → старий» не працює взагалі й не має. Досі це
трималося на уважності: під час валідації фази 3 новий знімок у старий
код не завантажився саме через це.

Фікстури в `tests/fixtures/snapshots/` — справжні знімки, обрізані до
кількох сторінок. Вони **не оновлюються** разом з кодом: у цьому й сенс.
Фікстура, яку переписують під нову схему, перевіряє, що новий код читає
новий формат, тобто нічого.
"""

from __future__ import annotations

import json
from dataclasses import MISSING
from pathlib import Path

import pytest

from app.audit.orchestrator import rescore
from app.audit.snapshot import load as load_snapshot
from app.audit.types import PageSignals, SiteContext

FIXTURES = Path(__file__).parent / "fixtures" / "snapshots"


def _snapshots() -> list[Path]:
    return sorted(FIXTURES.glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_fixtures_exist():
    """Порожня тека фікстур зробила б увесь файл тестом, що завжди зелений."""
    assert _snapshots(), "немає жодного знімка в tests/fixtures/snapshots/"


@pytest.mark.parametrize("path", _snapshots(), ids=lambda p: p.stem)
def test_old_snapshot_loads_in_current_code(path: Path):
    ctx = load_snapshot(_load(path))

    assert ctx.entry_url
    assert ctx.origin
    assert isinstance(ctx.pages, list)


@pytest.mark.parametrize("path", _snapshots(), ids=lambda p: p.stem)
def test_old_snapshot_can_still_be_rescored(path: Path):
    """Завантажити мало — знімок має пройти через чеки й скоринг.

    Саме це робить `POST /targets/{id}/rescore` і саме на це спирається
    «порівняння виправляється перерахунком» в історії.
    """
    outcome = rescore(load_snapshot(_load(path)))

    assert outcome.scores, "перерахунок не дав жодного модульного бала"
    assert outcome.overall is None or 0 <= outcome.overall <= 100


def test_every_new_field_has_a_default():
    """Поле без дефолта ламає старі знімки мовчки й одразу.

    Знімок бере всі поля дата-класу автоматично, а старий файл нових
    полів не містить. Дефолт — це і є контракт сумісності, тож перевіряти
    його треба на самому класі, не чекаючи, поки фікстура застаріє.
    """
    for klass in (SiteContext, PageSignals):
        required = [
            name
            for name, field in klass.__dataclass_fields__.items()
            if field.default is field.default_factory is MISSING
        ]
        assert required == _EXPECTED_REQUIRED[klass.__name__], (
            f"{klass.__name__}: змінився набір полів без дефолта — {required}. "
            "Нове поле без дефолта зробить старі знімки незавантажуваними."
        )


# Поля, які знімок зобов'язаний нести завжди. Список навмисно жорсткий:
# його розширення — це свідома зміна контракту, і вона має проходити через
# правку тесту, а не через мовчазне додавання колонки.
_EXPECTED_REQUIRED = {
    "SiteContext": ["entry_url", "origin"],
    "PageSignals": ["url"],
}


def test_a_snapshot_with_an_unknown_field_is_a_known_limitation():
    """Новий знімок у старий код не завантажується — і це задокументовано.

    Перевіряємо не сумісність (її немає), а те, що поведінка передбачувана:
    зайвий ключ дає TypeError, а не тихо ігнорується. Тиха відмова була б
    гіршою: знімок завантажився б неповним, і перерахунок дав би число,
    яке ніхто не зміг би пояснити.
    """
    raw = _load(_snapshots()[0])
    raw["site"]["field_from_the_future"] = 1

    with pytest.raises(TypeError):
        load_snapshot(raw)


# ── E-12: оголошені мови переживають знімок ───────────────────────────────


@pytest.mark.parametrize("path", _snapshots(), ids=lambda p: p.stem)
def test_a_snapshot_taken_before_declared_locales_still_loads(path: Path):
    """Старий знімок про це поле не знає — і не повинен.

    `None` тут не дрібниця форми: порожній список означав би «сайт не
    оголосив жодної мови», тобто твердження, якого ніхто не робив. `None`
    означає «ще не рахували», і перше ж питання це рахує з тих самих
    сторінок, що лежать у знімку.
    """
    raw = _load(path)
    assert "locales_declared" not in raw["site"]

    ctx = load_snapshot(raw)

    assert ctx.locales_declared is None
    assert isinstance(ctx.declared_locales(), list)
    assert ctx.locales_declared is not None


def test_declared_locales_survive_a_round_trip():
    """Поле JSON-придатне, тож загальний серіалізатор несе його без правок.

    Саме тому `snapshot.py` міняти не довелося: `dump` бере всі поля
    дата-класу, які не є дата-класами, а `load` віддає їх конструктору.
    """
    from app.audit.snapshot import dump as dump_snapshot

    ctx = load_snapshot(_load(_snapshots()[0]))
    ctx.locales_declared = ["de", "en"]

    again = load_snapshot(json.loads(json.dumps(dump_snapshot(ctx))))

    assert again.locales_declared == ["de", "en"]


# ── E-15: видимий слід крихт переживає знімок ─────────────────────────────


@pytest.mark.parametrize("path", _snapshots(), ids=lambda p: p.stem)
def test_a_snapshot_taken_before_breadcrumb_ui_still_loads(path: Path):
    """Знімок, старший за поле, не знає про нього — і не мусить.

    `False` тут означає рівно те, що означало досі: ми цього не бачили.
    Порожнеча старого знімка описує наш формат зберігання, а не сайт, і
    саме тому дефолт мусить збігатися з «не спостерігали»: будь-яке інше
    значення перетворило б мовчання на твердження.
    """
    raw = _load(path)
    for page in raw.get("pages", []):
        assert "breadcrumb_ui" not in page

    ctx = load_snapshot(raw)

    assert ctx.pages
    assert all(page.breadcrumb_ui is False for page in ctx.pages)


@pytest.mark.parametrize("path", _snapshots(), ids=lambda p: p.stem)
def test_a_snapshot_without_the_field_behaves_exactly_as_false(path: Path):
    """Відсутнє поле й записане `False` мають давати ТОЙ САМИЙ результат.

    Не «схожий», а той самий: класифікація, вердикт, покриття й знахідки.
    Інакше «поле має дефолт» означало б лише, що знімок завантажився, а
    не що він рахується так само.
    """
    from app.audit import hierarchy

    raw = _load(path)
    explicit = _load(path)
    for page in explicit.get("pages", []):
        page["breadcrumb_ui"] = False

    missing_ctx, explicit_ctx = load_snapshot(raw), load_snapshot(explicit)
    left, right = hierarchy.classify(missing_ctx), hierarchy.classify(explicit_ctx)

    assert (left is None) is (right is None)
    if left is not None and right is not None:
        assert left.as_evidence() == right.as_evidence()

    left_issues = sorted(i.issue_key for i in rescore(missing_ctx).issues)
    right_issues = sorted(i.issue_key for i in rescore(explicit_ctx).issues)
    assert left_issues == right_issues


def test_breadcrumb_ui_survives_a_round_trip():
    """`True` мусить пережити збереження й читання.

    Дефолт рятує старі знімки; без збереження самого факту нові знімки
    втрачали б його мовчки, і перерахунок відповідав би інакше, ніж
    живий аудит на тих самих даних.
    """
    from app.audit.snapshot import dump as dump_snapshot

    ctx = load_snapshot(_load(_snapshots()[0]))
    assert ctx.pages
    ctx.pages[0].breadcrumb_ui = True

    again = load_snapshot(json.loads(json.dumps(dump_snapshot(ctx))))

    assert again.pages[0].breadcrumb_ui is True
    assert all(page.breadcrumb_ui is False for page in again.pages[1:])


def test_the_new_field_needs_no_migration():
    """Поле JSON-придатне й має дефолт, тож `snapshot.py` не змінювався.

    `dump` бере всі поля дата-класу, які не є дата-класами, а `load`
    віддає їх конструктору. Перевіряється саме це: поле в схемі є, воно
    булеве, і дефолт у нього `False`.
    """
    field = PageSignals.__dataclass_fields__["breadcrumb_ui"]

    assert field.default is False
    assert field.default_factory is MISSING
    assert PageSignals(url="https://example.com/").breadcrumb_ui is False


# ── E-16: порядок заголовків має провенанс, а не здогад ───────────────
#
# Групований знімок не зберігає порядку читання взагалі: `h1,h3,h3,h2` лежить
# у ньому як `1,2,3,3`. Відновити з нього послідовність неможливо, тож єдина
# чесна відповідь — «не знаємо», і саме це означає `False`. Знімок, який
# мовчки прочитали б як упорядкований, дав би знахідку про сайт із нашої
# власної прогалини — рівно те, чого не має робити перерахунок.


def _ordered_page(levels: str = "1332"):
    """Сторінка, щойно видобута з HTML: порядок справжній і позначений."""
    from tests.factories import page_from_html

    body = "".join(f"<h{ch}>Заголовок {n}</h{ch}>" for n, ch in enumerate(levels, start=1))
    return page_from_html(
        f"<html><head><title>Сторінка</title></head><body><main>{body}"
        f"<p>{'слово ' * 120}</p></main></body></html>"
    )


def _as_legacy_row(page) -> dict:
    """Той самий документ, яким його зберіг би код ДО E-16.

    Легасі-знімок роблять дві речі, і обидві застосовані тут: заголовки в
    ньому згруповані за рівнем, бо саме так їх видобував тодішній
    екстрактор, — і ключа провенансу в ньому немає взагалі, бо поля ще не
    існувало. Зняти лише ключ означало б перевіряти знімок, якого ніколи
    не було.
    """
    from app.audit.snapshot import _dump

    row = _dump(page)
    row.pop("headings_in_document_order", None)
    row["headings"] = [list(h) for h in sorted(row["headings"], key=lambda h: h[0])]
    return row


def _order_issues(page):
    from app.audit.checks.seo import HeadingHierarchyCheck
    from tests.factories import context

    return list(HeadingHierarchyCheck().run(context(page)))


def test_absent_order_field_loads_exactly_like_explicit_false():
    from app.audit.snapshot import _load_page

    row = _as_legacy_row(_ordered_page())
    absent = _load_page(row)
    explicit = _load_page({**row, "headings_in_document_order": False})

    assert absent.headings_in_document_order is False
    assert absent.headings_in_document_order == explicit.headings_in_document_order
    assert absent.headings == explicit.headings


def test_e16_f2_grouped_snapshot_gains_no_order_finding():
    """E16-f2: той самий документ, що й E16-f1, але як старий знімок → PASS."""
    from app.audit.snapshot import _load_page

    fresh = _ordered_page("1332")
    assert len(_order_issues(fresh)) == 1, "E16-f1 має спрацювати на свіжій сторінці"

    legacy = _load_page(_as_legacy_row(fresh))
    assert [level for level, _t in legacy.headings] == [1, 2, 3, 3]
    assert _order_issues(legacy) == []


def test_a_grouped_snapshot_is_not_read_as_ordered_even_if_it_looks_ordered():
    """Порядок беруть з провенансу, а не з вигляду списку.

    Тут заголовки лежать у порядку документа, але прапорця немає. Спокуса
    «вони ж очевидно впорядковані» — це і є вигадування порядку, якого
    знімок не зберігав; правило мусить мовчати.
    """
    from app.audit.snapshot import _dump, _load_page

    row = _dump(_ordered_page("1332"))
    row.pop("headings_in_document_order")
    page = _load_page(row)

    assert [level for level, _t in page.headings] == [1, 3, 3, 2]
    assert page.headings_in_document_order is False
    assert _order_issues(page) == []


def test_a_level_absent_everywhere_still_fires_from_a_grouped_snapshot():
    """Прийнята поведінка не зрушила: відсутній рівень — факт про множину.

    Він доводиться будь-яким представленням, тож старий знімок мусить і далі
    давати цю знахідку. Інакше E-16 мовчки забрав би в перерахунку те, що в
    ньому вже було.
    """
    from app.audit.snapshot import _load_page

    legacy = _load_page(_as_legacy_row(_ordered_page("133")))

    assert [level for level, _t in legacy.headings] == [1, 3, 3]
    issues = _order_issues(legacy)
    assert len(issues) == 1
    assert issues[0].params == {"previous": 1, "level": 3}
    assert "in_document_order" not in issues[0].evidence


def test_true_and_false_both_survive_a_snapshot_round_trip():
    from app.audit.snapshot import dump as dump_snapshot
    from tests.factories import context

    ordered = _ordered_page("1332")
    ctx = context(ordered)
    ctx.entry_url = ordered.url
    ctx.origin = "https://example.com"

    again = load_snapshot(json.loads(json.dumps(dump_snapshot(ctx))))
    assert again.pages[0].headings_in_document_order is True
    assert [level for level, _t in again.pages[0].headings] == [1, 3, 3, 2]

    ctx.pages[0].headings_in_document_order = False
    back = load_snapshot(json.loads(json.dumps(dump_snapshot(ctx))))
    assert back.pages[0].headings_in_document_order is False


@pytest.mark.parametrize("path", _snapshots(), ids=lambda p: p.stem)
def test_accepted_snapshots_carry_no_order_provenance(path: Path):
    """Кожен збережений знімок старший за поле, тож усі його сторінки — `False`."""
    ctx = load_snapshot(_load(path))

    assert ctx.pages
    assert all(page.headings_in_document_order is False for page in ctx.pages)


def test_the_order_field_needs_no_migration():
    field = PageSignals.__dataclass_fields__["headings_in_document_order"]

    assert field.default is False
    assert field.default_factory is MISSING
    assert PageSignals(url="https://example.com/").headings_in_document_order is False


def test_the_detector_generation_moved_so_the_two_sides_stay_comparable():
    """Перерахунок до і після E-16 мусить бути відрізнюваним за відбитком.

    Саме на цьому тримається вся сумісність знімків: старий аудит можна
    чесно порівняти з новим лише тоді, коли видно, що правила змінилися.
    E-16 змінює УМОВУ спрацювання `seo.heading_hierarchy` на свіжому краулі,
    не чіпаючи жодного оголошення чека, — а `detector_version()` бачить саме
    оголошення. Без ручного покоління обидва боки назвалися б однаково, і
    різниця в знахідках виглядала б зміною сайту.
    """
    from app.audit import versions

    assert versions.DETECTOR_RULES != "10", (
        "покоління детектора лишилось тим, що ним був G5b / E-15"
    )
    assert int(versions.DETECTOR_RULES) > 10

    outcome = rescore(load_snapshot(_load(_snapshots()[0])))
    assert outcome.versions["detector"] == versions.detector_version()
    # Покоління скорингу — 5 від G6 (E-07): чек вилучено зі скорингу, і
    # межа мусить бути видимою. Формула й ваги при цьому не рухались.
    assert versions.SCORING_RULES == "5"
    assert outcome.versions["scoring"] == versions.scoring_version()
