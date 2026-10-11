"""Контактна форма: приймання, захист і межа обіцянок.

Головні твердження, які тут доводяться:

* успіх існує лише після того, як звернення СПРАВДІ збережене;
* приманка й антибот-токен перевіряються на СЕРВЕРІ, а не на клієнті;
* повтор того самого запиту не створює другого звернення;
* збій доставки ніколи не перетворюється на успіх;
* адреса одержувача й секрет провайдера не витікають у відповідь;
* лічильник контактної форми не торкається комерційних прав.
"""

from __future__ import annotations

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import contact as contact_app
from app.contact import antibot as antibot_module
from app.contact import delivery as delivery_module
from app.core.config import settings
from app.models.contact import ContactMessage
from app.models.purchase import AuditCredit

pytestmark = pytest.mark.asyncio

GOOD = {
    "name": "Сергій",
    "email": "owner@example.com",
    "message": "Маю питання про повний звіт і оплату для трьох сайтів.",
    "lang": "uk",
}


class _Accepting:
    """Антибот, який усе приймає. Для шляхів, де перевіряється не він."""

    name = "test"

    async def verify(self, token: str, *, remote_ip: str) -> antibot_module.Verification:
        return antibot_module.Verification(verdict=antibot_module.Verdict.OK)


class _Rejecting:
    name = "test"

    async def verify(self, token: str, *, remote_ip: str) -> antibot_module.Verification:
        return antibot_module.Verification(
            verdict=antibot_module.Verdict.REJECTED, codes=("invalid-input-response",)
        )


class _Collecting:
    """Транспорт, який запамʼятовує надіслане замість справжньої пошти."""

    name = "collecting"

    def __init__(self) -> None:
        self.sent: list[delivery_module.Outgoing] = []

    def available(self) -> bool:
        return True

    def send(self, outgoing: delivery_module.Outgoing) -> None:
        self.sent.append(outgoing)


class _Failing:
    name = "failing"

    def available(self) -> bool:
        return True

    def send(self, outgoing: delivery_module.Outgoing) -> None:
        raise RuntimeError("smtp down")


async def _submit(db: AsyncSession, **overrides: object) -> contact_app.Accepted:
    payload = {**GOOD, **overrides}
    submission = contact_app.Submission(
        name=str(payload["name"]),
        email=str(payload["email"]),
        site_url=str(payload.get("site_url", "")),
        message=str(payload["message"]),
        locale=str(payload.get("lang", "uk")),
        token="token",
        honeypot=str(payload.get("company", "")),
        ip="203.0.113.7",
    )
    return await contact_app.submit(
        db, submission, antibot=_Accepting(), transport=_Collecting()
    )


# ── 1–2. форма відкривається й приймає ─────────────────────────────────────


async def test_a_valid_message_is_stored_before_any_success_is_claimed(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    accepted = await _submit(db_session)
    await db_session.commit()

    row = (
        await db_session.execute(
            select(ContactMessage).where(ContactMessage.id == accepted.id)
        )
    ).scalar_one()
    assert row.email == "owner@example.com"
    assert row.status == "delivered"
    assert accepted.reference == row.id.hex[:8].upper()


async def test_the_endpoint_accepts_and_persists(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contact_app.antibot_module, "build_provider", _Accepting)
    transport = _Collecting()
    monkeypatch.setattr(
        contact_app.delivery_module, "build_transport", lambda: transport
    )

    response = await client.post("/v1/contact", json=GOOD)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["accepted"] is True and body["reference"]

    total = (
        await db_session.execute(select(func.count()).select_from(ContactMessage))
    ).scalar_one()
    assert total == 1
    assert transport.sent and transport.sent[0].email == "owner@example.com"


# ── 3–4. серверна валідація полів ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("name", "   ", contact_app.INVALID_NAME),
        ("email", "not-an-email", contact_app.INVALID_EMAIL),
        ("message", "коротко", contact_app.INVALID_MESSAGE),
        ("message", "x" * 6000, contact_app.INVALID_MESSAGE),
    ],
)
async def test_invalid_fields_are_refused_by_the_server(
    db_session: AsyncSession, field: str, value: str, reason: str
) -> None:
    with pytest.raises(contact_app.ContactError) as caught:
        await _submit(db_session, **{field: value})
    assert caught.value.reason == reason
    total = (
        await db_session.execute(select(func.count()).select_from(ContactMessage))
    ).scalar_one()
    assert total == 0


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("", ""),
        ("smartkp.com.ua", "https://smartkp.com.ua"),
        ("www.smartkp.com.ua", "https://www.smartkp.com.ua"),
        ("http://smartkp.com.ua", "http://smartkp.com.ua"),
        ("https://smartkp.com.ua/pricing", "https://smartkp.com.ua/pricing"),
    ],
)
async def test_the_optional_site_accepts_bare_domains(
    db_session: AsyncSession, raw: str, normalized: str
) -> None:
    accepted = await _submit(db_session, site_url=raw)
    row = (
        await db_session.execute(
            select(ContactMessage).where(ContactMessage.id == accepted.id)
        )
    ).scalar_one()
    assert row.site_url == normalized


async def test_a_broken_site_address_is_refused(db_session: AsyncSession) -> None:
    with pytest.raises(contact_app.ContactError) as caught:
        await _submit(db_session, site_url="не адреса взагалі")
    assert caught.value.reason == contact_app.INVALID_SITE


# ── 5–7. приманка й антибот ────────────────────────────────────────────────


async def test_a_filled_honeypot_is_refused_without_delivery(
    db_session: AsyncSession,
) -> None:
    transport = _Collecting()
    submission = contact_app.Submission(
        name="Bot", email="bot@example.com", site_url="",
        message="Купіть у нас посилання, дуже дешево, ось прайс.",
        locale="en", token="token", honeypot="Acme Inc", ip="203.0.113.9",
    )
    with pytest.raises(contact_app.ContactError) as caught:
        await contact_app.submit(
            db_session, submission, antibot=_Accepting(), transport=transport
        )
    assert caught.value.reason == contact_app.ANTIBOT_REJECTED
    assert transport.sent == []
    total = (
        await db_session.execute(select(func.count()).select_from(ContactMessage))
    ).scalar_one()
    assert total == 0


async def test_a_rejected_token_is_refused(db_session: AsyncSession) -> None:
    submission = contact_app.Submission(
        name="Bot", email="bot@example.com", site_url="",
        message="Автоматичне повідомлення без валідного токена челенджу.",
        locale="en", token="bad", honeypot="", ip="203.0.113.9",
    )
    with pytest.raises(contact_app.ContactError) as caught:
        await contact_app.submit(
            db_session, submission, antibot=_Rejecting(), transport=_Collecting()
        )
    assert caught.value.reason == contact_app.ANTIBOT_REJECTED


async def test_a_missing_token_is_rejected_by_the_real_provider() -> None:
    """Порожній токен — відмова, і провайдера для цього питати не треба."""
    provider = antibot_module.TurnstileProvider(secret="x")
    verification = await provider.verify("", remote_ip="203.0.113.1")
    assert verification.verdict is antibot_module.Verdict.REJECTED
    assert "missing-input-response" in verification.codes


async def test_an_unavailable_provider_is_not_a_rejection() -> None:
    """«Провайдер мовчить» і «ви бот» — різні відповіді, і плутати їх не можна."""
    verification = await antibot_module.DisabledProvider().verify("t", remote_ip="")
    assert verification.verdict is antibot_module.Verdict.UNAVAILABLE
    assert verification.ok is False


async def test_production_refuses_when_the_challenge_cannot_be_verified(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """У проді непідтверджений токен — відмова, а не мовчазний пропуск."""
    monkeypatch.setattr(settings, "app_env", "prod")
    submission = contact_app.Submission(
        name="Ім'я", email="a@example.com", site_url="",
        message="Достатньо довге повідомлення для перевірки поведінки.",
        locale="uk", token="t", honeypot="", ip="",
    )
    with pytest.raises(contact_app.ContactError) as caught:
        await contact_app.submit(
            db_session,
            submission,
            antibot=antibot_module.DisabledProvider(),
            transport=_Collecting(),
        )
    assert caught.value.reason == contact_app.ANTIBOT_UNAVAILABLE


# ── 8–9. лічильник і межа з комерцією ──────────────────────────────────────


async def test_the_rate_limit_stops_the_flood(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contact_app.antibot_module, "build_provider", _Accepting)
    monkeypatch.setattr(
        contact_app.delivery_module, "build_transport", lambda: _Collecting()
    )
    monkeypatch.setattr(settings, "contact_rate_limit", 2)

    seen = []
    for index in range(3):
        response = await client.post(
            "/v1/contact",
            json={**GOOD, "message": f"Повідомлення номер {index} з достатньою довжиною."},
        )
        seen.append(response.status_code)
    assert seen[:2] == [202, 202]
    assert seen[2] == 429
    assert "Retry-After" in (await client.post("/v1/contact", json=GOOD)).headers


async def test_contact_never_touches_commercial_entitlements(
    client: httpx.AsyncClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Звернення не списує ані аудитів, ані підписки — це інший шар."""
    monkeypatch.setattr(contact_app.antibot_module, "build_provider", _Accepting)
    monkeypatch.setattr(
        contact_app.delivery_module, "build_transport", lambda: _Collecting()
    )
    before = (
        await db_session.execute(select(func.count()).select_from(AuditCredit))
    ).scalar_one()

    assert (await client.post("/v1/contact", json=GOOD)).status_code == 202

    after = (
        await db_session.execute(select(func.count()).select_from(AuditCredit))
    ).scalar_one()
    assert after == before


# ── 10. походження запиту ──────────────────────────────────────────────────


async def test_a_foreign_origin_is_refused(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contact_app.antibot_module, "build_provider", _Accepting)
    response = await client.post(
        "/v1/contact", json=GOOD, headers={"Origin": "https://evil.example"}
    )
    assert response.status_code == 403
    assert response.json()["detail"]["reason"] == "contact.origin"


async def test_our_own_origin_passes(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contact_app.antibot_module, "build_provider", _Accepting)
    monkeypatch.setattr(
        contact_app.delivery_module, "build_transport", lambda: _Collecting()
    )
    response = await client.post(
        "/v1/contact", json=GOOD, headers={"Origin": settings.cors_origins[0]}
    )
    assert response.status_code == 202


# ── 11–12. повтори й збій доставки ─────────────────────────────────────────


async def test_a_retry_does_not_create_a_second_message(
    db_session: AsyncSession,
) -> None:
    first = await _submit(db_session)
    second = await _submit(db_session)
    assert first.id == second.id
    total = (
        await db_session.execute(select(func.count()).select_from(ContactMessage))
    ).scalar_one()
    assert total == 1


async def test_a_delivery_failure_never_becomes_success(
    db_session: AsyncSession,
) -> None:
    """Прийняли — зберегли. Але «доставлено» при збої не пишемо."""
    submission = contact_app.Submission(
        name="Ім'я", email="a@example.com", site_url="",
        message="Достатньо довге повідомлення для перевірки поведінки.",
        locale="uk", token="t", honeypot="", ip="",
    )
    accepted = await contact_app.submit(
        db_session, submission, antibot=_Accepting(), transport=_Failing()
    )
    assert accepted.delivered is False
    row = (
        await db_session.execute(
            select(ContactMessage).where(ContactMessage.id == accepted.id)
        )
    ).scalar_one()
    assert row.status == "failed"
    # Текст винятку поштової бібліотеки може нести адреси — зберігаємо тип.
    assert row.delivery_error == "RuntimeError"
    assert "smtp down" not in row.delivery_error


async def test_production_refuses_when_there_is_nowhere_to_deliver(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Кнопка, яка нікуди не доставляє, — обман. У проді це відмова."""
    monkeypatch.setattr(settings, "app_env", "prod")
    submission = contact_app.Submission(
        name="Ім'я", email="a@example.com", site_url="",
        message="Достатньо довге повідомлення для перевірки поведінки.",
        locale="uk", token="t", honeypot="", ip="",
    )
    with pytest.raises(contact_app.ContactError) as caught:
        await contact_app.submit(
            db_session,
            submission,
            antibot=_Accepting(),
            transport=delivery_module.NullTransport(),
        )
    assert caught.value.reason == contact_app.DELIVERY_UNAVAILABLE


# ── 13–15. секрети не витікають ────────────────────────────────────────────


async def test_the_config_endpoint_never_exposes_secrets(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "turnstile_site_key", "0x4AAAAAAA_site")
    monkeypatch.setattr(settings, "turnstile_secret_key", "0x4AAAAAAA_secret")
    monkeypatch.setattr(settings, "contact_recipient", "inbox@crawldy.internal")

    response = await client.get("/v1/contact/config")
    assert response.status_code == 200
    raw = response.text
    assert "0x4AAAAAAA_site" in raw
    # Ані секрету провайдера, ані адреси одержувача — вони серверні.
    assert "secret" not in raw
    assert "inbox@crawldy.internal" not in raw
    assert "crawldy.internal" not in raw


async def test_the_accept_response_carries_no_recipient(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contact_app.antibot_module, "build_provider", _Accepting)
    monkeypatch.setattr(
        contact_app.delivery_module, "build_transport", lambda: _Collecting()
    )
    monkeypatch.setattr(settings, "contact_recipient", "inbox@crawldy.internal")

    response = await client.post("/v1/contact", json=GOOD)
    assert "crawldy.internal" not in response.text
    assert set(response.json()) == {"accepted", "reference"}


async def test_the_stored_row_carries_no_recipient_and_no_raw_ip(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "contact_recipient", "inbox@crawldy.internal")
    accepted = await _submit(db_session)
    row = (
        await db_session.execute(
            select(ContactMessage).where(ContactMessage.id == accepted.id)
        )
    ).scalar_one()
    # Адреса одержувача не зберігається взагалі; адреса відвідувача — хешем.
    assert "crawldy.internal" not in f"{row.message}{row.email}{row.site_url}"
    assert row.ip_hash and row.ip_hash != "203.0.113.7"
    assert len(row.ip_hash) == 64


# ── 16–17. мова живе зі зверненням ─────────────────────────────────────────


@pytest.mark.parametrize("locale", ["en", "uk", "de", "es", "fr", "ru"])
async def test_every_public_locale_is_carried_through(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
    locale: str,
) -> None:
    """Відповідати людині треба її мовою — отже, мову треба зберегти."""
    monkeypatch.setattr(contact_app.antibot_module, "build_provider", _Accepting)
    transport = _Collecting()
    monkeypatch.setattr(
        contact_app.delivery_module, "build_transport", lambda: transport
    )
    response = await client.post(
        "/v1/contact",
        json={**GOOD, "lang": locale, "message": f"Питання мовою {locale}, достатньо довге."},
    )
    assert response.status_code == 202
    assert transport.sent[0].locale == locale


async def test_an_unknown_locale_falls_back_instead_of_failing(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(contact_app.antibot_module, "build_provider", _Accepting)
    transport = _Collecting()
    monkeypatch.setattr(
        contact_app.delivery_module, "build_transport", lambda: transport
    )
    response = await client.post("/v1/contact", json={**GOOD, "lang": "zz"})
    assert response.status_code == 202
    assert transport.sent[0].locale in {"uk", "en"}
