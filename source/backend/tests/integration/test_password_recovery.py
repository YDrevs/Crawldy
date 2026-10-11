"""Відновлення пароля крізь HTTP і базу.

Те, що перевіряється без бази — каталог листів, повтори SMTP, правила
конфігурації — лежить у `tests/test_password_recovery.py`.

Тут доводиться головне: відома й невідома адреса проходять ОДИН І ТОЙ
САМИЙ шлях. Не «схожий» і не «майже однаковий» — той самий: однакове
тіло, однаковий статус, однакові заголовки, однакова постановка в чергу
й однакова відмова, коли черги немає.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.identity import recovery, service
from app.models.identity import PasswordReset, User
from app.worker import recovery_task
from tests.integration.conftest import PASSWORD, register

NEW_PASSWORD = "totally-different-passphrase"
UNKNOWN = "nobody-at-all@example.com"


async def _account(client: httpx.AsyncClient) -> str:
    """Свіжий акаунт із випадковою адресою. Тести не ділять користувачів."""
    email = f"recovery-{uuid.uuid4().hex[:10]}@example.com"
    response = await register(client, email)
    assert response.status_code == 201, response.text
    return email


async def _live_reset(db: AsyncSession, email: str) -> PasswordReset:
    user = await service.find_user_by_email(db, email)
    assert user is not None
    stmt = select(PasswordReset).where(
        PasswordReset.user_id == user.id,
        PasswordReset.used_at.is_(None),
        PasswordReset.superseded_at.is_(None),
    )
    record = (await db.execute(stmt)).scalar_one_or_none()
    assert record is not None, "живого запиту на відновлення немає"
    return record


# ── відповідь не розрізняє відому й невідому адресу ────────────────────


@pytest.mark.asyncio
async def test_known_and_unknown_addresses_get_identical_responses(
    client: httpx.AsyncClient,
) -> None:
    """Інакше форма «забули пароль» стає перевіряльником, хто тут є."""
    known = await _account(client)

    first = await client.post("/v1/auth/password/forgot", json={"email": known})
    second = await client.post("/v1/auth/password/forgot", json={"email": UNKNOWN})

    assert first.status_code == second.status_code == 202
    assert first.json() == second.json() == {"accepted": True}
    assert first.headers["cache-control"] == second.headers["cache-control"] == "no-store"


@pytest.mark.asyncio
async def test_both_addresses_follow_the_same_queue_path(
    client: httpx.AsyncClient, recovery_queue: list[tuple[str, str]]
) -> None:
    """Однакової відповіді замало — однаковим має бути й шлях.

    Поки маршрут шукав акаунт сам, невідома адреса поверталась одразу, а
    відома — після запиту в базу й зʼєднання з чужим SMTP. Тіло було
    ідентичне, а час — ні. Тепер обидві дають рівно одну постановку в
    чергу, і відрізнити їх ззовні нема за чим.
    """
    known = await _account(client)
    recovery_queue.clear()

    await client.post("/v1/auth/password/forgot", json={"email": known, "lang": "uk"})
    await client.post("/v1/auth/password/forgot", json={"email": UNKNOWN, "lang": "uk"})

    assert len(recovery_queue) == 2
    assert recovery_queue[0] == (known, "uk")
    assert recovery_queue[1] == (UNKNOWN, "uk")


@pytest.mark.asyncio
async def test_the_request_path_never_touches_the_reset_table(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Маршрут не видає токена: це робота воркера.

    Якби видавав — для відомої адреси зʼявився б рядок, для невідомої ні,
    і різниця в роботі знову стала б різницею в часі відповіді.
    """
    known = await _account(client)
    before = len((await db_session.execute(select(PasswordReset))).all())

    await client.post("/v1/auth/password/forgot", json={"email": known})

    after = len((await db_session.execute(select(PasswordReset))).all())
    assert after == before, "маршрут створив запит на відновлення сам"


@pytest.mark.asyncio
async def test_the_address_is_normalised_before_it_reaches_the_queue(
    client: httpx.AsyncClient, recovery_queue: list[tuple[str, str]]
) -> None:
    """Велика літера в адресі не має заводити другого шляху."""
    known = await _account(client)
    recovery_queue.clear()

    await client.post("/v1/auth/password/forgot", json={"email": known.upper()})

    assert recovery_queue == [(known.lower(), "")]


@pytest.mark.asyncio
async def test_an_unavailable_queue_fails_the_same_way_for_both(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """503 однаковий для обох адрес — і він чесніший за фальшивий 202.

    Прикидатися, що лист прийнято, коли його нікому передати, означало б
    залишити людину чекати на те, чого не буде.
    """
    known = await _account(client)

    async def _broken(**_: object) -> None:
        raise ConnectionError("redis недоступний")

    monkeypatch.setattr("app.api.routes.auth.enqueue_password_reset", _broken)

    first = await client.post("/v1/auth/password/forgot", json={"email": known})
    second = await client.post("/v1/auth/password/forgot", json={"email": UNKNOWN})

    assert first.status_code == second.status_code == 503
    assert first.json() == second.json() == {"detail": {"reason": "recovery.unavailable"}}


@pytest.mark.asyncio
async def test_too_many_requests_are_refused_with_a_retry_hint(
    client: httpx.AsyncClient,
) -> None:
    """Обмежувач є, і він рахує саме відновлення, а не всі запити.

    Ділити лічильник із контактною формою не можна: спам у неї не має
    закривати людині вхід до власного акаунта.
    """
    from app.core.config import settings

    codes = [
        (
            await client.post(
                "/v1/auth/password/forgot", json={"email": f"flood-{n}@example.com"}
            )
        ).status_code
        for n in range(settings.recovery_rate_limit + 2)
    ]

    assert codes[: settings.recovery_rate_limit] == [202] * settings.recovery_rate_limit
    assert codes[-1] == 429

    refused = await client.post(
        "/v1/auth/password/forgot", json={"email": "flood-x@example.com"}
    )
    assert refused.json() == {"detail": {"reason": "recovery.too_many"}}
    assert int(refused.headers["retry-after"]) > 0


@pytest.mark.asyncio
async def test_one_address_cannot_be_flooded_from_many_addresses(
    client: httpx.AsyncClient,
) -> None:
    """Друге відро — за адресою.

    Без нього зловмисник, міняючи IP, завалив би чужу скриньку листами.
    Ключ у відрі хешований: лічильник не має ставати переліком адрес,
    які хтось намагався відновити.
    """
    from app.core.config import settings

    victim = await _account(client)
    codes = [
        (
            await client.post("/v1/auth/password/forgot", json={"email": victim})
        ).status_code
        for _ in range(settings.recovery_rate_limit + 1)
    ]
    assert codes[-1] == 429


# ── токен: зберігання, строк, одноразовість ────────────────────────────


@pytest.mark.asyncio
async def test_only_a_hash_of_the_token_reaches_the_database(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """У базі лежить SHA-256, а не сам токен.

    Копія бази — це не доступ до акаунтів: щоб скористатися посиланням,
    потрібен сирий токен, а він існує лише в памʼяті задачі та в листі.
    """
    email = await _account(client)
    issued = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    assert issued is not None
    await db_session.flush()

    record = await _live_reset(db_session, email)
    assert record.token_hash != issued.token
    assert record.token_hash == service.hash_token(issued.token)
    assert len(record.token_hash) == 64

    rows = (await db_session.execute(select(PasswordReset))).scalars().all()
    for row in rows:
        assert issued.token not in row.token_hash


@pytest.mark.asyncio
async def test_an_expired_token_is_indistinguishable_from_a_made_up_one(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Прострочений, використаний, скасований і вигаданий дають той самий 404.

    Розрізняти їх означало б підказувати, що такий токен колись існував.
    """
    email = await _account(client)
    issued = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    assert issued is not None
    issued.record.expires_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.flush()

    expired = await client.get(f"/v1/auth/password/reset?token={issued.token}")
    invented = await client.get("/v1/auth/password/reset?token=never-existed")

    assert expired.status_code == invented.status_code == 404
    assert expired.json() == invented.json()


@pytest.mark.asyncio
async def test_a_token_works_exactly_once(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    email = await _account(client)
    issued = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    assert issued is not None
    await db_session.flush()

    first = await client.post(
        "/v1/auth/password/reset",
        json={"token": issued.token, "password": NEW_PASSWORD},
    )
    second = await client.post(
        "/v1/auth/password/reset",
        json={"token": issued.token, "password": NEW_PASSWORD},
    )

    assert first.status_code == 204
    assert second.status_code == 404


@pytest.mark.asyncio
async def test_a_new_request_kills_the_previous_link(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Людина, що натиснула «надішліть ще раз», очікує саме цього."""
    email = await _account(client)
    first = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    second = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    assert first is not None and second is not None
    await db_session.flush()

    stale = await client.get(f"/v1/auth/password/reset?token={first.token}")
    fresh = await client.get(f"/v1/auth/password/reset?token={second.token}")

    assert stale.status_code == 404
    assert fresh.status_code == 204


@pytest.mark.asyncio
async def test_a_weak_password_does_not_burn_the_token(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Інакше помилка при введенні замикала б людину назовсім.

    Порядок у `consume` навмисний: політика пароля перевіряється ДО
    атомарного споживання токена.
    """
    email = await _account(client)
    issued = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    assert issued is not None
    await db_session.flush()

    rejected = await client.post(
        "/v1/auth/password/reset", json={"token": issued.token, "password": "short"}
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["reason"] == "password.weak"

    still_alive = await client.get(f"/v1/auth/password/reset?token={issued.token}")
    assert still_alive.status_code == 204, "слабкий пароль спалив посилання"

    accepted = await client.post(
        "/v1/auth/password/reset",
        json={"token": issued.token, "password": NEW_PASSWORD},
    )
    assert accepted.status_code == 204


@pytest.mark.asyncio
async def test_checking_a_token_does_not_consume_it(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Екран має право спитати «чи ще чинне» до того, як щось вводити."""
    email = await _account(client)
    issued = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    assert issued is not None
    await db_session.flush()

    for _ in range(3):
        assert (
            await client.get(f"/v1/auth/password/reset?token={issued.token}")
        ).status_code == 204

    assert (
        await client.post(
            "/v1/auth/password/reset",
            json={"token": issued.token, "password": NEW_PASSWORD},
        )
    ).status_code == 204


# ── наслідки зміни пароля ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_reset_revokes_every_session_and_the_old_password(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    email = await _account(client)
    issued = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    assert issued is not None
    await db_session.flush()

    await client.post(
        "/v1/auth/password/reset",
        json={"token": issued.token, "password": NEW_PASSWORD},
    )

    assert (await client.get("/v1/auth/me")).status_code == 401
    old = await client.post(
        "/v1/auth/login", json={"email": email, "password": PASSWORD}
    )
    assert old.status_code == 401
    new = await client.post(
        "/v1/auth/login", json={"email": email, "password": NEW_PASSWORD}
    )
    assert new.status_code == 200


@pytest.mark.asyncio
async def test_a_reset_unlocks_an_account_locked_by_failed_logins(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Людина довела володіння поштою — тримати її замкненою безглуздо."""
    email = await _account(client)
    user = await service.find_user_by_email(db_session, email)
    assert user is not None
    user.failed_login_count = 9
    user.locked_until = datetime.now(UTC) + timedelta(hours=1)
    await db_session.flush()

    issued = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    assert issued is not None
    await db_session.flush()
    await client.post(
        "/v1/auth/password/reset",
        json={"token": issued.token, "password": NEW_PASSWORD},
    )

    refreshed = await db_session.get(User, user.id)
    assert refreshed is not None
    assert refreshed.locked_until is None
    assert refreshed.failed_login_count == 0


@pytest.mark.asyncio
async def test_changing_a_password_requires_the_current_one(
    client: httpx.AsyncClient,
) -> None:
    """Навіть для вже автентифікованої людини.

    Інакше вкрадена сесія перетворюється на вкрадений акаунт.
    """
    await _account(client)

    wrong = await client.post(
        "/v1/auth/password/change",
        json={"current_password": "not-the-one", "new_password": NEW_PASSWORD},
    )
    assert wrong.status_code == 403
    assert wrong.json()["detail"]["reason"] == "password.wrong_current"
    assert (await client.get("/v1/auth/me")).status_code == 200, "сесія вціліла"


@pytest.mark.asyncio
async def test_changing_a_password_revokes_the_session_that_did_it(
    client: httpx.AsyncClient,
) -> None:
    """Включно з тією, якою прийшов цей запит."""
    email = await _account(client)

    changed = await client.post(
        "/v1/auth/password/change",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert changed.status_code == 204
    assert (await client.get("/v1/auth/me")).status_code == 401

    back = await client.post(
        "/v1/auth/login", json={"email": email, "password": NEW_PASSWORD}
    )
    assert back.status_code == 200


@pytest.mark.asyncio
async def test_a_weak_new_password_is_refused_on_change(
    client: httpx.AsyncClient,
) -> None:
    await _account(client)
    response = await client.post(
        "/v1/auth/password/change",
        json={"current_password": PASSWORD, "new_password": "short"},
    )
    assert response.status_code == 422
    assert (await client.get("/v1/auth/me")).status_code == 200


@pytest.mark.asyncio
async def test_changing_a_password_needs_a_session(
    client: httpx.AsyncClient,
) -> None:
    await client.post("/v1/auth/logout")
    response = await client.post(
        "/v1/auth/password/change",
        json={"current_password": PASSWORD, "new_password": NEW_PASSWORD},
    )
    assert response.status_code == 401


# ── воркер проти справжньої бази ───────────────────────────────────────


@pytest.mark.asyncio
async def test_the_worker_issues_a_working_link_for_a_known_account(
    client: httpx.AsyncClient, worker_session: AsyncSession, monkeypatch
) -> None:
    """Наскрізно: задача → токен → лист → робоче посилання.

    Посилання беремо з ЛИСТА, а не з бази: саме так його отримує людина,
    і саме так перевіряється, що в листі справді робочий токен.
    """
    from app.mail import transport as mail

    email = await _account(client)
    mailer = mail.CaptureMailer()
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)

    result = await recovery_task.send_password_reset_task({}, email, "uk")

    assert result == {"status": "sent"}
    assert len(mailer.sent) == 1
    assert mailer.sent[0].to == email

    token = mailer.sent[0].text.split("token=")[1].split("&")[0].strip()
    assert (
        await client.get(f"/v1/auth/password/reset?token={token}")
    ).status_code == 204


@pytest.mark.asyncio
async def test_the_worker_writes_nothing_for_an_unknown_account(
    worker_session: AsyncSession, monkeypatch
) -> None:
    from app.mail import transport as mail

    mailer = mail.CaptureMailer()
    monkeypatch.setattr(recovery_task.mail, "build_mailer", lambda: mailer)
    before = len((await worker_session.execute(select(PasswordReset))).all())

    result = await recovery_task.send_password_reset_task({}, UNKNOWN, "uk")

    assert result == {"status": "no_account"}
    assert mailer.sent == []
    after = len((await worker_session.execute(select(PasswordReset))).all())
    assert after == before


@pytest.mark.asyncio
async def test_a_failed_delivery_leaves_the_link_alive(
    client: httpx.AsyncClient, worker_session: AsyncSession, monkeypatch
) -> None:
    """Таймаут SMTP не доводить, що лист не пішов.

    Скасування токена зробило б мертвим посилання, яке людина, можливо,
    вже тримає в пошті. Хай краще застаріє саме.
    """
    import smtplib

    from app.mail import transport as mail

    email = await _account(client)

    class _Dead:
        name = "dead"

        def available(self) -> bool:
            return True

        def send(self, message: mail.Message) -> None:
            raise smtplib.SMTPServerDisconnected("обрив")

    async def _no_waiting(_seconds: float) -> None:
        return None

    monkeypatch.setattr(recovery_task.mail, "build_mailer", _Dead)
    monkeypatch.setattr(recovery_task.asyncio, "sleep", _no_waiting)

    result = await recovery_task.send_password_reset_task({}, email, "uk")

    assert result == {"status": "failed"}
    record = await _live_reset(worker_session, email)
    assert record.used_at is None
    assert record.superseded_at is None


@pytest.mark.asyncio
async def test_a_disabled_account_gets_no_link(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Новий пароль не дав би входу, тож лист лише збив би з пантелику."""
    email = await _account(client)
    user = await service.find_user_by_email(db_session, email)
    assert user is not None
    user.deleted_at = datetime.now(UTC)
    await db_session.flush()

    issued = await recovery.request_reset(db_session, email=email, ttl_minutes=60)
    assert issued is None
