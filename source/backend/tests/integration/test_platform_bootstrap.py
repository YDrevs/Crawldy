"""Перший адміністратор нової інсталяції.

До 25 вересня 2026 способу не існувало взагалі: `platform_role` ніде в
коді не присвоювалась, і дві службові ролі у власника з'явилися ручним
SQL. Для передачі продукту це блокер — отримувач розгортає все
правильно й не може відкрити адмінку, а адмінка є єдиним підтриманим
місцем, де заводять тарифи, пропозиції та ціни.

Перевіряється не лише те, що роль видається, а й ЧОГО механізм не
робить: не створює людину, не задає пароля, не має маршруту в API.
Скрипт, який заводить «адміністратора за замовчуванням» із відомим
паролем, — бекдор, що переживає розгортання й лягає в резервні копії.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity import service
from app.identity.authz import ActorContext, Forbidden
from app.identity.enums import PlatformRole
from tests.integration.conftest import PASSWORD

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "grant_platform_role.py"


def _module():
    spec = importlib.util.spec_from_file_location("grant_platform_role", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def grant(db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch):
    """Скрипт, під'єднаний до тестової транзакції.

    Він бере сесію з `SessionLocal` сам — окремий процес, узяти її нема
    в кого. Тому підміняється сама фабрика, а `commit` стає `flush`,
    щоб зовнішня транзакція фікстури дожила до відкоту.
    """
    module = _module()
    original = db_session.commit
    db_session.commit = db_session.flush  # type: ignore[method-assign]

    class _Borrowed:
        async def __aenter__(self) -> AsyncSession:
            return db_session

        async def __aexit__(self, *_: object) -> bool:
            return False

    monkeypatch.setattr(module, "SessionLocal", _Borrowed)
    yield module
    db_session.commit = original  # type: ignore[method-assign]


async def _register(db: AsyncSession, email: str):
    registration = await service.register(db, email=email, password=PASSWORD)
    await db.flush()
    return registration


@pytest.mark.asyncio
async def test_a_fresh_installation_has_nobody_on_the_team(db_session: AsyncSession) -> None:
    """Порожня роль — стан за замовчуванням, і саме тому вісь безпечна."""
    registration = await _register(db_session, "plain@example.com")

    assert registration.user.platform_role is None
    assert (
        await service.platform_role_of(db_session, user_id=registration.user.id) is None
    )


@pytest.mark.asyncio
async def test_an_unknown_address_is_refused_and_creates_nobody(
    grant, db_session: AsyncSession
) -> None:
    """Відмова, а не мовчазне створення користувача.

    Створити людину тут означало б створити акаунт, пароля до якого не
    знає ніхто, — і лишити його в базі назавжди.
    """
    code = await grant.run("ghost@example.com", PlatformRole.ADMIN, False)

    assert code == 1
    assert await service.find_user_by_email(db_session, "ghost@example.com") is None


@pytest.mark.asyncio
async def test_granting_promotes_an_existing_person(grant, db_session: AsyncSession) -> None:
    registration = await _register(db_session, "owner@example.com")

    code = await grant.run("owner@example.com", PlatformRole.ADMIN, False)
    await db_session.flush()

    assert code == 0
    assert (
        await service.platform_role_of(db_session, user_id=registration.user.id)
        == PlatformRole.ADMIN
    )


@pytest.mark.asyncio
async def test_the_address_is_matched_case_insensitively(
    grant, db_session: AsyncSession
) -> None:
    """Пошта вже зберігається нормалізованою; підвищення мусить це знати."""
    registration = await _register(db_session, "mixed@example.com")

    assert await grant.run("MIXED@EXAMPLE.COM", PlatformRole.STAFF, False) == 0
    await db_session.flush()
    assert (
        await service.platform_role_of(db_session, user_id=registration.user.id)
        == PlatformRole.STAFF
    )


@pytest.mark.asyncio
async def test_granting_twice_changes_nothing(grant, db_session: AsyncSession) -> None:
    registration = await _register(db_session, "twice@example.com")

    assert await grant.run("twice@example.com", PlatformRole.STAFF, False) == 0
    await db_session.flush()
    assert await grant.run("twice@example.com", PlatformRole.STAFF, False) == 0
    await db_session.flush()

    assert (
        await service.platform_role_of(db_session, user_id=registration.user.id)
        == PlatformRole.STAFF
    )


@pytest.mark.asyncio
async def test_a_role_can_be_taken_away(grant, db_session: AsyncSession) -> None:
    """Помилкове підвищення мусить мати дорогу назад."""
    registration = await _register(db_session, "demote@example.com")
    await grant.run("demote@example.com", PlatformRole.ADMIN, False)
    await db_session.flush()

    assert await grant.run("demote@example.com", None, False) == 0
    await db_session.flush()

    assert (
        await service.platform_role_of(db_session, user_id=registration.user.id) is None
    )


@pytest.mark.asyncio
async def test_showing_a_role_changes_nothing(grant, db_session: AsyncSession) -> None:
    registration = await _register(db_session, "peek@example.com")

    assert await grant.run("peek@example.com", PlatformRole.ADMIN, True) == 0
    await db_session.flush()

    assert (
        await service.platform_role_of(db_session, user_id=registration.user.id) is None
    )


@pytest.mark.asyncio
async def test_the_granted_role_is_what_the_admin_routes_require(
    grant, db_session: AsyncSession
) -> None:
    """Підвищення має відкривати саме ті двері, заради яких воно є.

    Інакше скрипт писав би значення, якого ніхто не питає, і перший
    адміністратор далі не міг би зайти.
    """
    registration = await _register(db_session, "staffer@example.com")
    await grant.run("staffer@example.com", PlatformRole.ADMIN, False)
    await db_session.flush()

    role = await service.platform_role_of(db_session, user_id=registration.user.id)
    actor = ActorContext(
        organization_id=registration.organization.id,
        role=registration.membership.role,
        auth="session",
        user_id=registration.user.id,
        platform_role=role,
    )

    actor.require_platform(PlatformRole.STAFF)
    actor.require_platform(PlatformRole.ADMIN)


@pytest.mark.asyncio
async def test_a_plain_client_is_still_refused(db_session: AsyncSession) -> None:
    registration = await _register(db_session, "client@example.com")
    actor = ActorContext(
        organization_id=registration.organization.id,
        role=registration.membership.role,
        auth="session",
        user_id=registration.user.id,
        platform_role=None,
    )

    with pytest.raises(Forbidden):
        actor.require_platform(PlatformRole.STAFF)


def test_the_bootstrap_creates_no_credential() -> None:
    """Найважливіше твердження набору — про те, чого скрипт не робить.

    Він не хешує, не генерує й не приймає пароля, і не створює
    користувача. Перевіряється текстом, бо йдеться саме про відсутність
    коду: виклику, якого немає, не спіймати виконанням.
    """
    source = SCRIPT.read_text(encoding="utf-8")

    for forbidden in (
        "hash_password",
        "password=",
        "secrets.token",
        "User(",
        "session.add",
        "db.add",
    ):
        assert forbidden not in source, f"скрипт заводить облікові дані: {forbidden}"


def test_no_http_route_assigns_a_platform_role() -> None:
    """Підвищення до персоналу через HTTP — поверхня атаки, потрібна
    рівно один раз за життя інсталяції.

    Шукається ПРИСВОЄННЯ атрибута (`щось.platform_role = ...`), а не
    підрядок `platform_role=`. Маршрути законно ЧИТАЮТЬ роль, збираючи
    відповідь (`platform_role=view.platform_role`), і перша версія цієї
    перевірки ловила саме їх — той самий клас помилки, що й пошук
    підрядка замість розбору.
    """
    import ast

    routes = Path(__file__).resolve().parents[2] / "app" / "api" / "routes"
    offenders: list[str] = []
    for path in sorted(routes.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            targets: list[ast.expr] = []
            if isinstance(node, ast.Assign):
                targets = list(node.targets)
            elif isinstance(node, ast.AnnAssign):
                targets = [node.target]
            for target in targets:
                if isinstance(target, ast.Attribute) and target.attr == "platform_role":
                    offenders.append(f"{path.name}:{node.lineno}")
    assert not offenders, f"маршрут присвоює платформну роль: {offenders}"
