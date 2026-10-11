"""Ідентичність на справжній базі: реєстрація, вхід, сесії, володіння.

Ці перевірки не мають сенсу без PostgreSQL. Унікальність по `lower(email)`,
частковий унікальний індекс на одного власника, каскади — усе це або
працює в базі, або не працює ніде: перевірка в коді переживає рівно до
першої гонки.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.identity import passwords, service
from app.identity.enums import Role, UserStatus
from app.identity.passwords import WeakPassword
from app.models.identity import Membership, Organization, Session, User

PASSWORD = "correct-horse-battery"


async def _register(db, email="sergii@example.com", **kwargs):
    reg = await service.register(db, email=email, password=PASSWORD, **kwargs)
    await db.flush()
    return reg


@pytest.mark.asyncio
async def test_registration_creates_a_personal_organization(db_session):
    reg = await _register(db_session, display_name="Сергій")

    assert reg.user.email == "sergii@example.com"
    assert reg.organization.is_personal is True
    assert reg.membership.role is Role.OWNER
    assert reg.membership.accepted_at is not None, "власник не запрошує сам себе"


@pytest.mark.asyncio
async def test_the_user_owns_nothing_directly(db_session):
    """Перевірка архітектурного рішення, а не поля.

    Усе, за що платять, належить організації. Якби сайти чи підписка
    висіли на користувачі, поява другого учасника означала б міграцію
    всіх бізнес-таблиць одночасно.
    """
    columns = {c.name for c in User.__table__.columns}

    assert not columns & {"organization_id", "plan", "subscription_id", "site_id"}


@pytest.mark.asyncio
async def test_email_is_normalized_before_it_is_stored(db_session):
    reg = await _register(db_session, email="  Sergii@Example.COM ")

    assert reg.user.email == "sergii@example.com"


@pytest.mark.asyncio
async def test_the_same_email_in_another_case_is_the_same_person(db_session):
    await _register(db_session, email="sergii@example.com")

    with pytest.raises(service.EmailTaken):
        await _register(db_session, email="SERGII@example.com")


@pytest.mark.asyncio
async def test_the_database_refuses_a_duplicate_even_past_the_domain(db_session):
    """Нормалізація в домені може мати помилку. База помилки мати не може."""
    await _register(db_session, email="sergii@example.com")

    # Порушення обмеження всередині savepoint: інакше відкат рве зовнішню
    # транзакцію фікстури, і прибирання після тесту скаржиться.
    async with db_session.begin_nested():
        db_session.add(
            User(email="SERGII@EXAMPLE.COM", password_hash="x", status=UserStatus.PENDING)
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_a_short_password_is_refused(db_session):
    with pytest.raises(WeakPassword):
        await service.register(db_session, email="a@example.com", password="short")


@pytest.mark.asyncio
@pytest.mark.parametrize("length", [10, 11])
async def test_registration_refuses_the_lengths_that_used_to_pass(db_session, length):
    """Десять і одинадцять символів проходили до 25 вересня 2026.

    Межу піднято до дванадцяти, і саме ці дві довжини відрізняють нове
    правило від старого — решта («short») відмовлялася й раніше.
    """
    with pytest.raises(WeakPassword):
        await service.register(
            db_session, email=f"len{length}@example.com", password="x" * length
        )


@pytest.mark.asyncio
async def test_registration_accepts_exactly_the_minimum(db_session):
    """Межа включна: дванадцять — це «достатньо», а не «майже»."""
    reg = await service.register(
        db_session,
        email="exactly-twelve@example.com",
        password="x" * passwords.MIN_LENGTH,
    )
    await db_session.flush()
    assert reg.user.id is not None


@pytest.mark.asyncio
async def test_an_account_older_than_the_policy_can_still_sign_in(db_session):
    """Підняття межі не замикає нікого. Це головне твердження зміни.

    Користувач із десятисимвольним паролем існує в базі й після того,
    як мінімум став дванадцять: політика стосується створення пароля, а
    не його перевірки.
    """
    legacy = User(
        email="legacy@example.com",
        password_hash=passwords.rehash_existing("short-pass"),  # 10 символів
        status=UserStatus.ACTIVE,
    )
    db_session.add(legacy)
    await db_session.flush()

    signed_in = await service.authenticate(
        db_session, email="legacy@example.com", password="short-pass"
    )

    assert signed_in is not None
    assert signed_in.id == legacy.id


@pytest.mark.asyncio
async def test_rehashing_on_sign_in_does_not_lock_out_a_legacy_password(
    db_session, monkeypatch
):
    """Пастка з відстроченням: вхід перехешовує пароль, коли параметри
    argon2 підняли — і робив це через `hash_password`, тобто ЩЕ Й
    перевіряв довжину.

    У день зміни параметрів людина з десятисимвольним паролем, ввівши
    його ПРАВИЛЬНО, дістала б `WeakPassword` із глибини входу: не
    «оновіть пароль», а помилка сервера на коректних даних. Тест
    відтворює саме той день — `needs_rehash` примусово каже «так».
    """
    original = passwords.rehash_existing("short-pass")
    legacy = User(
        email="legacy-rehash@example.com",
        password_hash=original,
        status=UserStatus.ACTIVE,
    )
    db_session.add(legacy)
    await db_session.flush()

    monkeypatch.setattr(passwords, "needs_rehash", lambda _hash: True)

    signed_in = await service.authenticate(
        db_session, email="legacy-rehash@example.com", password="short-pass"
    )

    assert signed_in is not None, "коректний пароль не пустив у власний акаунт"
    assert signed_in.password_hash != original, "перехешування не відбулося"
    assert passwords.verify(signed_in.password_hash, "short-pass") is True


@pytest.mark.asyncio
async def test_sign_in_with_the_right_password(db_session):
    await _register(db_session)

    user = await service.authenticate(db_session, email="sergii@example.com", password=PASSWORD)

    assert user is not None
    assert user.last_login_at is not None


@pytest.mark.asyncio
async def test_sign_in_with_the_wrong_password_gives_nothing(db_session):
    await _register(db_session)

    assert await service.authenticate(db_session, email="sergii@example.com", password="no") is None


@pytest.mark.asyncio
async def test_an_unknown_email_and_a_wrong_password_look_the_same(db_session):
    """Обидва — None. Розрізнити їх ззовні означало б безкоштовно
    перевіряти, чи зареєстрована конкретна адреса."""
    await _register(db_session)

    unknown = await service.authenticate(db_session, email="nobody@example.com", password=PASSWORD)
    wrong = await service.authenticate(db_session, email="sergii@example.com", password="nope-nope")

    assert unknown is None and wrong is None


@pytest.mark.asyncio
async def test_a_disabled_account_cannot_sign_in(db_session):
    reg = await _register(db_session)
    reg.user.status = UserStatus.DISABLED
    await db_session.flush()

    assert await service.authenticate(db_session, email=reg.user.email, password=PASSWORD) is None


# ── сесії ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_the_raw_token_never_reaches_the_database(db_session):
    reg = await _register(db_session)
    issued = await service.create_session(db_session, user=reg.user, user_agent="Firefox")

    stored = await db_session.scalar(select(Session.token_hash).where(Session.id == issued.session.id))

    assert stored != issued.token
    assert stored == service.hash_token(issued.token)


@pytest.mark.asyncio
async def test_a_valid_token_resolves_to_its_session(db_session):
    reg = await _register(db_session)
    issued = await service.create_session(db_session, user=reg.user)

    resolved = await service.resolve_session(db_session, issued.token)

    assert resolved is not None and resolved.user_id == reg.user.id


@pytest.mark.asyncio
async def test_a_revoked_session_stops_working_immediately(db_session):
    """Головна причина, з якої це сесія, а не JWT."""
    reg = await _register(db_session)
    issued = await service.create_session(db_session, user=reg.user)

    assert await service.revoke_session(db_session, issued.token) is True
    assert await service.resolve_session(db_session, issued.token) is None


@pytest.mark.asyncio
async def test_an_expired_session_stops_working(db_session):
    reg = await _register(db_session)
    issued = await service.create_session(
        db_session, user=reg.user, ttl=timedelta(seconds=-1)
    )

    assert await service.resolve_session(db_session, issued.token) is None


@pytest.mark.asyncio
async def test_changing_a_password_can_end_every_session(db_session):
    reg = await _register(db_session)
    first = await service.create_session(db_session, user=reg.user)
    second = await service.create_session(db_session, user=reg.user)

    assert await service.revoke_all_sessions(db_session, user_id=reg.user.id) == 2
    assert await service.resolve_session(db_session, first.token) is None
    assert await service.resolve_session(db_session, second.token) is None


@pytest.mark.asyncio
async def test_a_made_up_token_resolves_to_nothing(db_session):
    assert await service.resolve_session(db_session, "not-a-real-token") is None


# ── членство й володіння ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_an_organization_has_exactly_one_owner(db_session):
    """Обмеження живе в базі, бо перевірка в коді не переживе гонки.

    Тест заразом ловить пастку часткового індексу: предикат мусить
    збігатися з тим, що SQLAlchemy справді записує в колонку. Якщо в базі
    лежить `member`, а індекс шукає `MEMBER`, обмеження тихо не діє —
    і дізнатися про це можна було б лише з двох власників у продакшені.
    """
    reg = await _register(db_session)
    other = await _register(db_session, email="second@example.com")

    async with db_session.begin_nested():
        db_session.add(
            Membership(
                user_id=other.user.id,
                organization_id=reg.organization.id,
                role=Role.OWNER,
                accepted_at=datetime.now(UTC),
            )
        )
        with pytest.raises(IntegrityError):
            await db_session.flush()


@pytest.mark.asyncio
async def test_the_owner_index_predicate_matches_what_is_stored(db_session):
    """Пряма перевірка того самого, але явно й читано.

    Порівнюємо рядок у колонці з предикатом індексу. Розбіжність тут
    означає мовчазно вимкнене обмеження вище.
    """
    reg = await _register(db_session)

    stored = await db_session.scalar(
        text("SELECT role FROM memberships WHERE organization_id = :org").bindparams(
            org=reg.organization.id
        )
    )
    predicate = await db_session.scalar(
        text(
            "SELECT pg_get_expr(indpred, indrelid) FROM pg_index "
            "WHERE indexrelid = 'uq_membership_single_owner'::regclass"
        )
    )

    assert stored in predicate, f"у колонці {stored!r}, а індекс шукає {predicate!r}"


@pytest.mark.asyncio
async def test_a_second_member_joins_without_a_fight(db_session):
    reg = await _register(db_session)
    other = await _register(db_session, email="second@example.com")

    db_session.add(
        Membership(
            user_id=other.user.id,
            organization_id=reg.organization.id,
            role=Role.MEMBER,
            accepted_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    found = await service.membership_of(
        db_session, user_id=other.user.id, organization_id=reg.organization.id
    )
    assert found is not None and found.role is Role.MEMBER


@pytest.mark.asyncio
async def test_an_unaccepted_invitation_gives_no_access(db_session):
    """Запрошення без відповіді — це ще не членство."""
    reg = await _register(db_session)
    other = await _register(db_session, email="invited@example.com")

    db_session.add(
        Membership(
            user_id=other.user.id,
            organization_id=reg.organization.id,
            role=Role.MEMBER,
            invited_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    assert (
        await service.membership_of(
            db_session, user_id=other.user.id, organization_id=reg.organization.id
        )
        is None
    )


@pytest.mark.asyncio
async def test_a_stranger_is_not_a_member(db_session):
    reg = await _register(db_session)

    assert (
        await service.membership_of(
            db_session, user_id=uuid.uuid4(), organization_id=reg.organization.id
        )
        is None
    )


@pytest.mark.asyncio
async def test_ownership_transfers_without_leaving_two_owners(db_session):
    reg = await _register(db_session)
    other = await _register(db_session, email="second@example.com")
    db_session.add(
        Membership(
            user_id=other.user.id,
            organization_id=reg.organization.id,
            role=Role.ADMIN,
            accepted_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    await service.transfer_ownership(
        db_session, organization_id=reg.organization.id, to_user_id=other.user.id
    )

    roles = (
        await db_session.execute(
            select(Membership.user_id, Membership.role).where(
                Membership.organization_id == reg.organization.id
            )
        )
    ).all()
    by_user = dict(roles)
    assert by_user[other.user.id] is Role.OWNER
    assert by_user[reg.user.id] is Role.ADMIN


@pytest.mark.asyncio
async def test_ownership_cannot_go_to_someone_outside(db_session):
    reg = await _register(db_session)
    stranger = await _register(db_session, email="stranger@example.com")

    with pytest.raises(service.NotAMember):
        await service.transfer_ownership(
            db_session, organization_id=reg.organization.id, to_user_id=stranger.user.id
        )


@pytest.mark.asyncio
async def test_a_user_can_belong_to_several_organizations(db_session):
    """На запуску так майже ні в кого не буде — і саме тому це треба
    перевірити зараз, поки припущення «одна організація» ще не встигло
    просочитися в запити."""
    reg = await _register(db_session)
    team = Organization(name="Агенція", slug=await service.unique_slug(db_session, "Агенція"))
    db_session.add(team)
    await db_session.flush()
    db_session.add(
        Membership(
            user_id=reg.user.id,
            organization_id=team.id,
            role=Role.MEMBER,
            accepted_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    orgs = await service.organizations_of(db_session, user_id=reg.user.id)

    assert {o.id for o in orgs} == {reg.organization.id, team.id}


@pytest.mark.asyncio
async def test_slugs_do_not_collide(db_session):
    first = await _register(db_session, email="a@example.com", display_name="Crawldy")
    second = await _register(db_session, email="b@example.com", display_name="Crawldy")

    assert first.organization.slug != second.organization.slug
