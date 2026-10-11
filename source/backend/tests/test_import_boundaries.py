"""Напрям залежностей між шарами — перевіркою, а не домовленістю.

Інваріант «`app/audit/` не імпортує ні FastAPI, ні SQLAlchemy» записаний
у CLAUDE.md з першого дня й тримався на тому, що про нього пам'ятають.
Цей проєкт уже двічі втрачав інваріант саме так — не через незгоду, а
через те, що застаріле речення в документі пережило своє спростування.

Фаза 4 додає до ядра сім нових пакетів, і кожен з них — нова нагода
випадково імпортувати білінг у двигун аудиту. Тому межа перевіряється
читанням AST: тест бачить не наміри, а рядки `import`.

Правила описані в PHASE4_ARCHITECTURE.md, §2. Тут вони виконувані.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

APP = Path(__file__).resolve().parents[1] / "app"

# Що кожен пакет НЕ має права імпортувати. Порожній набір означає, що
# пакет поки не існує — тест на нього мовчить, але правило вже записане,
# і в день появи пакета воно почне діяти без окремої правки.
FORBIDDEN: dict[str, set[str]] = {
    # ── пошта ──────────────────────────────────────────────────────────
    # Адаптер, а не домен. Знає SMTP і формат листа й більше нічого: ані
    # хто адресат у нашій моделі, ані чому йому пишуть. Саме тому його
    # можна замінити на іншого провайдера, не торкаючись відновлення
    # пароля, — і саме тому він не має права тягнути домен за собою.
    "mail": {
        "fastapi",
        "sqlalchemy",
        "alembic",
        "arq",
        "app.models",
        "app.api",
        "app.services",
        "app.worker",
        "app.identity",
        "app.billing",
        "app.sites",
        "app.scheduling",
        "app.application",
        "app.report",
        "app.contact",
    },
    # ── заморожене ядро ────────────────────────────────────────────────
    # Двигун аудиту знає тільки: ось валідний запит — виконай його. Хто
    # цей користувач, чи оплачений тариф, як називається продукт — не
    # його питання й ніколи ним не стане.
    "audit": {
        "fastapi",
        "sqlalchemy",
        "alembic",
        "arq",
        "app.models",
        "app.api",
        "app.services",
        "app.worker",
        "app.identity",
        "app.billing",
        "app.sites",
        "app.scheduling",
        "app.application",
        "app.report",
    },
    # Звіт будується з результату аудиту й теж лишається чистим шаром:
    # той самий білдер обслуговує і свіжий аудит, і рядки з БД.
    "report": {
        "fastapi",
        "sqlalchemy",
        "app.models",
        "app.api",
        "app.services",
        "app.worker",
        "app.identity",
        "app.billing",
        "app.application",
    },
    # Збагачення — чистий шар міркування над готовою правдою аудиту: на
    # вході зібраний запит, на виході структурний результат. Персистує
    # його application, викликає воркер; сам пакет про них не знає.
    #
    # `app.audit` і `app.report` тут заборонені навмисно, хоч стрілка й
    # дивилася б за течією: вхід задачі збирає application і передає
    # звичайним dict. Так шар збагачення фізично не має доступу до
    # знахідок і скора — не лише не користується ним.
    "enrich": {
        "fastapi",
        "sqlalchemy",
        "arq",
        "app.models",
        "app.api",
        "app.services",
        "app.worker",
        "app.application",
        "app.identity",
        "app.billing",
        "app.audit",
        "app.report",
    },
    # Контактна форма — два адаптери: перевірка антибот-токена й
    # доставка звернення. Той самий контракт, що в білінгу: домен знає
    # «надіслати», а не назву провайдера.
    #
    # `app.audit` і `app.report` заборонені навмисно. Спокуса є —
    # детектор захисту форм говорить про те саме явище, — але це різні
    # напрями: тут ми ЗАХИЩАЄМО власну форму, там ЧИТАЄМО чужу. Спільний
    # код звʼязав би вхідний трафік сайту з двигуном аудиту.
    "contact": {
        "fastapi",
        "sqlalchemy",
        "app.models",
        "app.api",
        "app.services",
        "app.worker",
        "app.application",
        "app.audit",
        "app.report",
        "app.billing",
    },
    # ── продуктові контексти ──────────────────────────────────────────
    "identity": {"app.audit", "app.report", "app.billing", "app.api", "app.scheduling"},
    # Найважливіше ребро всієї фази: білінг ніколи не викликає двигун.
    # Вебхук міняє стан підписки; аудит із цього не запускається.
    "billing": {"app.audit", "app.report", "app.api", "app.scheduling", "app.application"},
    "sites": {"app.audit", "app.report", "app.billing", "app.api"},
    "scheduling": {"app.audit", "app.report", "app.billing", "app.api"},
    # Application оркеструє все, крім себе, — але не залежить від того,
    # хто його викликав. Інакше mobile-клієнт вимагав би змін тут.
    "application": {"app.api", "app.worker"},
    # ── наявні пакети ─────────────────────────────────────────────────
    # API не виконує роботу: він приймає запит, перевіряє право й ставить
    # задачу. Імпорт виконавця задач звідси означав би краул у веб-процесі.
    "api": {"app.worker.tasks", "app.models", "app.scheduling", "app.billing.providers"},
    # Присутність — чистий шар спостережень: політика+раннер+адаптери.
    # Персистує сервіс, викликає воркер; у скоринг аудиту шляху немає.
    "presence": {
        "fastapi",
        "sqlalchemy",
        "app.models",
        "app.api",
        "app.services",
        "app.worker",
        "app.audit.scoring",
        "app.report",
    },
    # Спільний каталог можливостей AI: лише довідка, жодних політик і
    # персистентності.
    "ai": {
        "fastapi",
        "sqlalchemy",
        "app.models",
        "app.api",
        "app.services",
        "app.worker",
        "app.audit",
        "app.report",
        "app.enrich",
        "app.presence",
    },
    # Шар доступу до даних не знає, що над ним HTTP.
    "services": {"app.api", "fastapi"},
    # Воркер живе окремим процесом і не має залежати від веб-застосунку.
    "worker": {"app.api", "fastapi"},
    # Моделі — представлення персистентності. Логіки в них немає.
    "models": {
        "app.audit",
        "app.report",
        "app.api",
        "app.application",
        "app.identity",
        "app.billing",
        "app.sites",
        "app.scheduling",
        "fastapi",
    },
}

# Винятки з правил. Кожен має жити з причиною поруч, інакше через рік
# ніхто не відрізнить свідоме рішення від забутої тимчасовості.
ALLOWED: dict[tuple[str, str], str] = {
    ("report", "app.audit"): "звіт будується з типів аудиту — це напрям за течією",
    # CLAUDE.md, інваріант 1: enum'и живуть в app/audit/enums.py саме для
    # того, щоб моделі їх не дублювали. Це листовий модуль без залежностей,
    # і стрілка дивиться в правильний бік — двигун про моделі не знає.
    # Моделі мають право на спільний словник будь-якого контексту й на
    # нього одного. `*.enums` — листові модулі без залежностей, і стрілка
    # дивиться в правильний бік: контекст про таблиці не знає.
    ("models", "app.audit"): "спільний словник статусів і модулів, не логіка",
    ("models", "app.identity"): "спільний словник ролей і станів, не логіка",
    ("models", "app.enrich"): "спільний словник типів задач і статусів, не логіка",
    ("application", "app.audit"): "application збирає AuditRequest для двигуна",
    ("application", "app.report"): "application віддає готовий звіт",
    ("application", "app.models"): "application працює з персистентністю",
    ("application", "app.services"): "шар доступу до даних, поки він не переїхав у контексти",
    ("application", "app.schemas"): "схеми запиту поки що правлять за команди",
}


# Прямі звернення до двигуна й до збірки звіту з шару API.
#
# Це борг, а не задум: продуктового шару поки немає, тож маршрут сам
# збирає звіт і сам знає про orchestrator. PHASE4_ARCHITECTURE.md, C5.
#
# Реєстр існує не для того, щоб виправдати борг, а щоб він не ріс: тест
# нижче падає на новому такому імпорті. Кожен блок фази 4, який переносить
# use case в application/, викреслює звідси рядок.
LEGACY_DIRECT_ENGINE_USE: set[tuple[str, str]] = {
    ('api', 'app.audit.enums'),
    ('api', 'app.audit.fetcher'),
    ('api', 'app.audit.i18n'),
    ('api', 'app.report.builder'),
    ('api', 'app.report.docx'),
    ('api', 'app.report.docx_owner'),
    ('api', 'app.report.history'),
    ('api', 'app.report.owner_enrich'),
    # Мапер ReportDocument → контракт веб-інтерфейсу. Той самий борг, що
    # й решта report-модулів у цьому переліку: маршрут звіту історично
    # збирає документ сам. Виносити його в application варто разом з
    # усіма сімома, а не поодинці.
    ('api', 'app.report.web'),
    ('services', 'app.audit.enums'),
    ('services', 'app.audit.fetcher'),
    ('services', 'app.audit.orchestrator'),
    ('services', 'app.audit.snapshot'),
    ('services', 'app.audit.types'),
    ('services', 'app.report.benchmark'),
    ('services', 'app.report.builder'),
    ('services', 'app.report.history'),
    ('services', 'app.report.types'),
}

#: Куди саме `app/application/guest.py` дивиться в шар звіту — поіменно.
#
# Пін СПЕЦИФІЧНИЙ для цього модуля, а не для пакета. Загальне правило
# `FORBIDDEN["application"] |= {"app.report"}` неможливе: на прийнятому
# комміті таких ребер сім, у трьох файлах, і воно зламало б сам прийнятий
# комміт. Загальний поіменний реєстр на весь пакет теж не годиться —
# він падає на чужій незакоміченій роботі, яка до E-13/E-14 стосунку не
# має, і перетворює архітектурний інваріант на чергу до чужого релізу.
#
# Тут пін рівно на те, що цей блок і зобовʼязався тримати: модуль, у
# якому живе політика переліку відкритих сторінок. Три рядки нижче —
# збирання презентації, яке фаза 4 ще не перенесла; вони прийшли з
# прийнятого комміту без змін.
#
# Додати сюди рядок можна лише разом із новою залежністю в коді, і тест
# нижче падає саме на цьому. Викреслити — лише коли залежність справді
# піде з продукту, окремою авторизованою зміною.
GUEST_REPORT_IMPORTS: frozenset[str] = frozenset({
    "app.report.builder",
    "app.report.short",
    "app.report.web",
})

#: Те, що E-14 приніс у цей модуль. Жодне з цих імен не сміє ані
#: імпортувати `app.report`, ані посилатися на щось із нього.
INSPECTED_PAGE_POLICY: tuple[str, ...] = (
    "INSPECTED_PAGE_LIMIT",
    "URL_COLLATION",
    "page_was_read",
    "InspectedPageRow",
    "InspectedPages",
    "pages_for",
)

WATCHED_PREFIXES = ("app.audit.", "app.report.")


def _modules(package: str) -> list[Path]:
    root = APP / package
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _imports(path: Path) -> set[str]:
    """Усі імпортовані імена модуля — і `import x`, і `from x import y`.

    Відносні імпорти (`from . import y`) розгортаються в повне ім'я
    пакета: інакше `from ..billing import x` пройшов би повз перевірку.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    package = path.relative_to(APP.parent).with_suffix("").parts

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package[: len(package) - node.level]
                found.add(".".join((*base, node.module) if node.module else base))
            elif node.module:
                found.add(node.module)
    return found


def _violations(package: str) -> list[tuple[str, str]]:
    banned = FORBIDDEN[package]
    out = []
    for path in _modules(package):
        for name in _imports(path):
            # Словник контексту — не його логіка. Дозволено лише моделям.
            if package == "models" and name.endswith(".enums"):
                continue
            for forbidden in banned:
                if name == forbidden or name.startswith(forbidden + "."):
                    if ALLOWED.get((package, forbidden)):
                        continue
                    out.append((str(path.relative_to(APP)), name))
    return out


@pytest.mark.parametrize("package", sorted(FORBIDDEN))
def test_package_does_not_import_what_it_must_not(package: str) -> None:
    violations = _violations(package)
    assert not violations, "заборонені імпорти: " + "; ".join(
        f"{where} → {what}" for where, what in violations
    )


def test_the_engine_stays_free_of_the_product():
    """Окремо й голосно — це головна межа проєкту.

    Двигун можна переписати, не торкаючись білінгу, рівно доти, доки він
    про білінг не знає.
    """
    assert not _violations("audit")


def test_billing_never_reaches_the_audit_engine():
    """Друга головна межа: вебхук не запускає краул.

    Подія провайдера міняє стан підписки. Що з цього випливає для
    аудитів, вирішує application layer — і робить це окремим кроком.
    """
    assert not _violations("billing")


def test_the_debt_of_direct_engine_use_does_not_grow():
    """Борг зафіксований поіменно й не має поповнюватися.

    Поки продуктового шару немає, маршрути й сервіси звертаються до
    двигуна напряму. Заборонити це сьогодні означало б зламати робочий
    код; лишити без нагляду — означало б, що до кінця фази 4 таких місць
    стане вдвічі більше, і переносити доведеться вже не десяток.
    """
    found = {
        (package, name)
        for package in ("api", "services")
        for path in _modules(package)
        for name in _imports(path)
        if name.startswith(WATCHED_PREFIXES)
    }
    new = found - LEGACY_DIRECT_ENGINE_USE
    assert not new, (
        "нові прямі звернення до двигуна в обхід application: "
        + ", ".join(f"{p} → {n}" for p, n in sorted(new))
    )


def test_the_debt_ledger_has_no_stale_entries():
    """Викреслений із коду імпорт має зникнути й з реєстру.

    Інакше реєстр перетворюється на список того, що колись було, і
    перестає що-небудь означати.
    """
    found = {
        (package, name)
        for package in ("api", "services")
        for path in _modules(package)
        for name in _imports(path)
        if name.startswith(WATCHED_PREFIXES)
    }
    stale = LEGACY_DIRECT_ENGINE_USE - found
    assert not stale, "у реєстрі лишились викреслені рядки: " + ", ".join(
        f"{p} → {n}" for p, n in sorted(stale)
    )



GUEST_MODULE = APP / "application" / "guest.py"


def _guest_tree() -> ast.Module:
    return ast.parse(GUEST_MODULE.read_text(encoding="utf-8"), filename=str(GUEST_MODULE))


def _report_imports_of(tree: ast.AST) -> set[str]:
    """Кожен модуль `app.report*`, який цей AST імпортує.

    Береться саме AST, а не пошук підрядка: `# from app.report import x`
    у коментарі не є імпортом, а `from app.report.web import to_web`
    усередині функції — є. Підрядковий пошук помилявся б в обидва боки.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "app.report" or node.module.startswith("app.report."):
                found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names
                         if a.name == "app.report" or a.name.startswith("app.report."))
    return found


def _names_bound_from_report(tree: ast.AST) -> set[str]:
    """Локальні імена, під якими в модуль потрапило щось із `app.report`.

    Саме їх не можна згадувати всередині політики E-14: імпорт можна
    зробити деінде, а скористатися ним тут — і підрядковий пошук
    `app.report` цього не побачив би взагалі.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and (
                node.module == "app.report" or node.module.startswith("app.report.")):
            bound.update(a.asname or a.name for a in node.names)
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "app.report" or a.name.startswith("app.report."):
                    bound.add(a.asname or a.name.split(".")[0])
    return bound


def _policy_nodes(tree: ast.Module) -> dict[str, ast.AST]:
    """Вузли верхнього рівня, з яких складається політика переліку сторінок."""
    found: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if node.name in INSPECTED_PAGE_POLICY:
                found[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in INSPECTED_PAGE_POLICY:
                    found[target.id] = node
    return found


def test_guest_gains_no_new_report_import():
    """`app/application/guest.py` не додає залежностей від шару звіту.

    Це той самий вид ребра, що тримає борговий реєстр вище, але пін тут
    вузький навмисно: інваріант належить цьому блоку, а не всьому
    пакетові, і не має падати через чужу роботу в сусідніх модулях.

    Політика, яку застосунковий шар оголосив своєю, не сміє наполовину
    жити в презентації: інакше на питання «скільки сторінок показувати»
    відповідали б двоє, і рано чи пізно по-різному.
    """
    new = _report_imports_of(_guest_tree()) - GUEST_REPORT_IMPORTS
    assert not new, (
        "нові імпорти шару звіту в app/application/guest.py: " + ", ".join(sorted(new))
    )


def test_the_guest_report_pin_has_no_stale_entries():
    """Викреслений із коду імпорт має зникнути й з піна.

    Інакше пін стає списком того, що колись було, і перестає що-небудь
    означати. Прибрати рядок звідси можна лише разом зі справжнім
    прибиранням залежності з продукту.
    """
    stale = GUEST_REPORT_IMPORTS - _report_imports_of(_guest_tree())
    assert not stale, "у піні лишились викреслені рядки: " + ", ".join(sorted(stale))


def test_the_inspected_page_policy_is_present_and_owned_here():
    """Уся політика переліку живе в застосунковому шарі — і саме в цьому модулі."""
    from app.application import guest

    for name in INSPECTED_PAGE_POLICY:
        assert hasattr(guest, name), f"застосунковий шар не володіє {name}"
    found = _policy_nodes(_guest_tree())
    missing = [n for n in INSPECTED_PAGE_POLICY if n not in found]
    assert not missing, f"не оголошено на верхньому рівні guest.py: {missing}"


def test_the_inspected_page_policy_never_resolves_through_the_report_layer():
    """Жодна частина E-14 не імпортує шар звіту й не згадує нічого з нього.

    Перевіряється не текст, а дерево: усередині кожного вузла політики не
    має бути ані імпорту `app.report*`, ані імені, яке в цей модуль
    прийшло з `app.report`. Друге важливіше за перше — імпорт може стояти
    деінде, а скористатися ним тут, і підрядковий пошук `app.report`
    такого не побачив би взагалі.
    """
    tree = _guest_tree()
    bound = _names_bound_from_report(tree)
    assert bound, "у модулі немає жодного імені з app.report — пін застарів"

    for name, node in _policy_nodes(tree).items():
        assert not _report_imports_of(node), f"{name} імпортує шар звіту"
        for inner in ast.walk(node):
            if isinstance(inner, ast.Name):
                assert inner.id not in bound, f"{name} посилається на {inner.id} з app.report"
            elif isinstance(inner, ast.Attribute):
                root = inner
                while isinstance(root, ast.Attribute):
                    root = root.value
                if isinstance(root, ast.Name):
                    assert root.id not in bound, (
                        f"{name} звертається до {root.id} з app.report")


def test_the_inspected_page_policy_did_not_move_into_the_report_layer():
    """Зворотний бік тієї самої помилки: політика, що переїхала в презентацію.

    Пін вище ловить НОВИЙ імпорт сюди. Перенести константу в `app.report`
    і імпортувати її назад — два різні рухи, і кожен окремо проходив би
    повз один із тестів.
    """
    for path in sorted((APP / "report").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for name in INSPECTED_PAGE_POLICY:
            assert name not in text, f"{path.name} знає про {name}: політика роздвоїлась"

def test_rules_cover_every_package_that_exists():
    """Новий пакет без правила — діра, яку ніхто не помітить.

    Тест падає в день, коли в app/ з'являється пакет, для якого межі не
    описані. Це навмисно незручно: описати межу дешевше, ніж потім
    шукати, звідки взялася залежність.
    """
    known = set(FORBIDDEN) | {"core", "schemas", "i18n"}
    present = {
        p.name
        for p in APP.iterdir()
        if p.is_dir() and p.name != "__pycache__" and (p / "__init__.py").exists()
    }
    assert present <= known, f"пакети без опису меж: {sorted(present - known)}"
