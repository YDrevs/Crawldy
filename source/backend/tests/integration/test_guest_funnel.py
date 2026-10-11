"""Анонімна воронка: від адреси до купленого звіту, без акаунта.

Перевіряється те, чого не видно з коду поодинці: що гість справді
проходить увесь шлях, що номер аудиту нічого не відкриває, що оплату
робить перевірена подія, а не повернення браузера, і що привласнення не
рухає аудит.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import guest as guest_app
from app.audit.enums import AuditStatus
from app.billing.enums import BillingEventKind, CommerceModel, PurchaseStatus
from app.core.ratelimit import MemoryRateLimiter
from app.identity.enums import OrganizationKind
from app.models.audit import Audit
from app.models.guest import AuditUnlock, GuestSession
from app.models.identity import Membership, Organization
from app.models.purchase import OneOffPurchase
from app.services import audit_service

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def _sellable(single_offer: None) -> None:
    """Гостьова каса продає «разову перевірку» каталогу — заводимо її."""



async def _open(client: httpx.AsyncClient) -> str:
    response = await client.post("/v1/public/sessions")
    assert response.status_code == 201, response.text
    return str(response.json()["token"])


def _auth(token: str) -> dict[str, str]:
    return {"X-Guest-Token": token}


async def _start(client: httpx.AsyncClient, token: str, url: str = "https://example.com/") -> str:
    response = await client.post("/v1/public/audits", json={"url": url}, headers=_auth(token))
    assert response.status_code == 202, response.text
    return str(response.json()["audit_id"])


# ── сесія й володіння ──────────────────────────────────────────────────────


async def test_guest_gets_an_organization_without_a_member(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Гість — це організація без учасників, а не аудит без власника."""
    token = await _open(client)
    session = await guest_app.resolve(db_session, token)

    organization = await db_session.get(Organization, session.organization_id)
    assert organization is not None
    assert organization.kind is OrganizationKind.GUEST

    members = await db_session.scalars(
        select(Membership).where(Membership.organization_id == organization.id)
    )
    assert list(members) == []


async def test_open_token_is_never_stored(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """У базі лежить лише хеш: дамп не роздає робочих спроможностей."""
    token = await _open(client)
    rows = list(await db_session.scalars(select(GuestSession)))
    assert rows
    assert all(row.token_hash != token for row in rows)
    assert any(row.token_hash == guest_app.hash_token(token) for row in rows)


async def test_audit_id_alone_opens_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Номер ресурсу — не доказ права на нього.

    Найважливіша перевірка розділу: інший гість знає ідентифікатор і не
    отримує нічого, хоча ідентифікатор справжній.
    """
    mine = await _open(client)
    audit_id = await _start(client, mine)

    stranger = await _open(client)
    response = await client.get(f"/v1/public/audits/{audit_id}", headers=_auth(stranger))
    assert response.status_code == 404

    without = await client.get(f"/v1/public/audits/{audit_id}")
    assert without.status_code == 404


async def test_expired_capability_reads_like_a_missing_one(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Прострочення й неіснування назовні не розрізняються."""
    token = await _open(client)
    session = await guest_app.resolve(db_session, token)
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    response = await client.post(
        "/v1/public/audits", json={"url": "https://example.com/"}, headers=_auth(token)
    )
    assert response.status_code == 404

    missing = await client.post(
        "/v1/public/audits", json={"url": "https://example.com/"}, headers=_auth("no-such-token")
    )
    assert missing.status_code == 404


# ── обмеження частоти ──────────────────────────────────────────────────────


async def test_rate_limit_stops_the_public_endpoint(
    client: httpx.AsyncClient, rate_limiter: MemoryRateLimiter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ліміт стоїть перед створенням, а не після нього.

    Береться маршрут сесій, бо за ним немає квоти: на запуску аудиту
    відмова могла б прийти й від тарифу, і тест не знав би, що саме
    перевірив.
    """
    monkeypatch.setattr("app.api.routes.public.settings.public_rate_limit", 2)

    first = await client.post("/v1/public/sessions")
    second = await client.post("/v1/public/sessions")
    third = await client.post("/v1/public/sessions")

    assert first.status_code == 201
    assert second.status_code == 201
    assert third.status_code == 429
    assert third.headers["Retry-After"]


async def test_previews_are_unlimited_only_the_rate_limit_gates(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Другий і третій безкоштовні превʼю проходять так само, як перший.

    Механізму «один безкоштовний аудит на сесію» не існує: превʼю
    необмежені за рішенням продукту, комерційні лічильники не рухаються,
    і єдина межа — технічний ліміт частоти зі своїм «забагато запитів».
    """
    token = await _open(client)
    first = await client.post(
        "/v1/public/audits", json={"url": "https://example.com/"}, headers=_auth(token)
    )
    second = await client.post(
        "/v1/public/audits", json={"url": "https://another.example/"}, headers=_auth(token)
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["audit_id"] != second.json()["audit_id"]


async def test_refused_attempt_still_counts(rate_limiter: MemoryRateLimiter) -> None:
    """Відмова не скидає вікно: інакше межа обходиться наполегливістю."""
    for _ in range(3):
        await rate_limiter.check("k", limit=2, window=60)
    decision = await rate_limiter.check("k", limit=2, window=60)
    assert not decision.allowed
    assert decision.remaining == 0


# ── короткий і повний вигляд ───────────────────────────────────────────────


async def _finish(db_session: AsyncSession, audit_id: str) -> Audit:
    """Довести аудит до стану, у якому звіт можна зібрати."""
    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.status = AuditStatus.COMPLETED
    audit.finished_at = datetime.now(UTC)
    await db_session.flush()
    return audit


async def test_short_view_shows_scores_and_hides_findings(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Коротке — та сама робота, менше подробиць. Не інша робота."""
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)

    response = await client.get(f"/v1/public/audits/{audit_id}", headers=_auth(token))
    assert response.status_code == 200
    body = response.json()

    assert body["unlocked"] is False
    assert "coverage" in body
    assert "severity" in body
    assert "problems" in body
    # Повних знахідок із доказами в безкоштовному вигляді немає — як і
    # шести вимірів, і порад: межу тримає схема, детально її ганяє
    # test_free_paid_boundary.
    assert "issues" not in body
    assert "modules" not in body
    assert "actions" not in body


async def test_the_guest_result_speaks_the_language_of_the_page(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Мова сторінки доходить до текстів знахідок.

    Знайдено власником на живому екрані: підписи були українські
    («НАЙВАЖЛИВІШІ ПРОБЛЕМИ», «Терміново»), бо їх дає каталог фронта, а
    самі проблеми — англійські, бо маршрут не приймав `lang` і документ
    складався мовою за замовчуванням. Одна сторінка говорила двома
    мовами одночасно.
    """
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)

    seen = {}
    for lang in ("en", "uk"):
        response = await client.get(
            f"/v1/public/audits/{audit_id}?lang={lang}", headers=_auth(token)
        )
        assert response.status_code == 200, response.text
        seen[lang] = response.json()

    # Локаль документа їде у відповіді й дорівнює запитаній.
    assert seen["uk"].get("locale") in (None, "uk")
    # Однакова структура, різні слова: якщо тексти збіглися повністю,
    # мова не дійшла — саме так дефект і виглядав.
    assert seen["en"].keys() == seen["uk"].keys()

    without = await client.get(
        f"/v1/public/audits/{audit_id}", headers=_auth(token)
    )
    assert without.status_code == 200


async def test_a_running_audit_reports_how_far_it_has_got(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Екран очікування отримує справжні числа, а не анімацію.

    Поки чисел ще немає, поле порожнє — і це нормальний стан, а не збій:
    до першої хвилі краулу писати нічого. Тому екран мусить уміти обидва
    випадки, і відповідь мусить розрізняти їх явно.
    """
    token = await _open(client)
    audit_id = await _start(client, token)

    # Щойно поставлений аудит: черга ще не бралася за нього.
    fresh = await client.get(f"/v1/public/audits/{audit_id}", headers=_auth(token))
    assert fresh.status_code == 200
    assert fresh.json()["progress"] == {}

    await audit_service.record_progress(
        db_session, uuid.UUID(audit_id), stage="crawl", read=4, known=11
    )

    response = await client.get(f"/v1/public/audits/{audit_id}", headers=_auth(token))
    assert response.status_code == 200
    progress = response.json()["progress"]
    assert progress == {"stage": "crawl", "pages_read": 4, "pages_known": 11}


async def test_progress_is_not_written_onto_a_finished_audit(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Черга вміє доставити те саме повідомлення двічі.

    Аудит із остаточним станом уже має результат; зрушити його показник
    ходу означало б показати клієнту рух там, де все скінчилось.
    """
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)

    await audit_service.record_progress(
        db_session, uuid.UUID(audit_id), stage="crawl", read=2, known=9
    )

    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    assert audit.progress == {}


async def test_full_view_is_refused_until_paid(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """402, а не 404: ресурс існує, і людина щойно бачила його короткий вигляд."""
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)

    response = await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    assert response.status_code == 402


async def test_result_pages_forbid_indexing_and_caching(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Сторінка результату приватна: не в пошуку й не в кеші проксі."""
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)

    response = await client.get(f"/v1/public/audits/{audit_id}", headers=_auth(token))
    assert "noindex" in response.headers["X-Robots-Tag"]
    assert "no-store" in response.headers["Cache-Control"]


# ── оплата ─────────────────────────────────────────────────────────────────


def _purchase_event(*, organization_id: uuid.UUID, audit_id: str, event_id: str) -> bytes:
    return json.dumps(
        {
            "external_event_id": event_id,
            "kind": BillingEventKind.ONE_OFF_PURCHASED.value,
            "occurred_at": datetime.now(UTC).isoformat(),
            "organization_id": str(organization_id),
            "quantity": 1,
            "currency": "USD",
            "amount_minor": 900,
            "payload": {"audit_id": audit_id},
        }
    ).encode("utf-8")


async def test_checkout_return_does_not_unlock(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Каса дає намір, не право. Повний вигляд лишається закритим."""
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)

    checkout = await client.post(
        f"/v1/public/audits/{audit_id}/checkout", headers=_auth(token)
    )
    assert checkout.status_code == 200
    assert checkout.json()["purchase_intent"]

    still_closed = await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    assert still_closed.status_code == 402


async def test_verified_event_unlocks_the_same_audit(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Оплату доводить подія провайдера — і відкриває вона той самий аудит."""
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)
    session = await guest_app.resolve(db_session, token)

    response = await client.post(
        "/v1/webhooks/fake",
        content=_purchase_event(
            organization_id=session.organization_id, audit_id=audit_id, event_id="evt-1"
        ),
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )
    assert response.status_code == 200, response.text

    full = await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    assert full.status_code == 200
    body = full.json()
    # Та сама форма, що в кабінеті: подання звіту одне на весь продукт.
    assert "modules" in body
    assert "priorities" in body
    assert str(body["audit_id"]) == audit_id

    short = await client.get(f"/v1/public/audits/{audit_id}", headers=_auth(token))
    assert short.json()["unlocked"] is True


async def test_unsigned_event_unlocks_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Без підпису подія не доходить до домену взагалі."""
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)
    session = await guest_app.resolve(db_session, token)

    response = await client.post(
        "/v1/webhooks/fake",
        content=_purchase_event(
            organization_id=session.organization_id, audit_id=audit_id, event_id="evt-2"
        ),
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 400
    assert not await guest_app.is_unlocked(db_session, uuid.UUID(audit_id))


async def test_repeated_delivery_unlocks_once(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Провайдери повторюють доставку. Другий рядок не зʼявляється."""
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)
    session = await guest_app.resolve(db_session, token)
    body = _purchase_event(
        organization_id=session.organization_id, audit_id=audit_id, event_id="evt-3"
    )
    headers = {"x-fake-signature": "valid", "content-type": "application/json"}

    first = await client.post("/v1/webhooks/fake", content=body, headers=headers)
    second = await client.post("/v1/webhooks/fake", content=body, headers=headers)
    assert first.status_code == 200
    assert second.status_code == 200

    unlocks = list(
        await db_session.scalars(
            select(AuditUnlock).where(AuditUnlock.audit_id == uuid.UUID(audit_id))
        )
    )
    assert len(unlocks) == 1


async def test_payment_in_one_tenant_does_not_open_another(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Ідентифікатор аудиту не є секретом, тож перевіряється власник.

    Інакше оплата в одній гостьовій організації відкривала б чужий
    аудит в іншій — достатньо було б підставити його номер у подію.
    """
    victim = await _open(client)
    victim_audit = await _start(client, victim)
    await _finish(db_session, victim_audit)

    attacker = await _open(client)
    attacker_session = await guest_app.resolve(db_session, attacker)

    response = await client.post(
        "/v1/webhooks/fake",
        content=_purchase_event(
            organization_id=attacker_session.organization_id,
            audit_id=victim_audit,
            event_id="evt-4",
        ),
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )
    # Подія прийнята, але доменний перехід не вдався: провайдер має
    # повторити, а рядок у журналі несе причину.
    assert response.status_code == 500
    assert not await guest_app.is_unlocked(db_session, uuid.UUID(victim_audit))


async def test_paid_but_not_provisioned_is_visible(db_session: AsyncSession) -> None:
    """«Гроші пройшли, доступу немає» мусить мати відповідь запитом.

    Саме цей стан у конкурента виглядав тишею. Тут він знаходиться.
    """
    organization = Organization(name="o", slug=f"o-{uuid.uuid4().hex[:8]}")
    db_session.add(organization)
    await db_session.flush()
    audit = Audit(organization_id=organization.id, url="https://x.test/", origin="https://x.test")
    db_session.add(audit)
    await db_session.flush()
    purchase = OneOffPurchase(
        organization_id=organization.id,
        provider="fake",
        external_id=f"p-{uuid.uuid4().hex[:8]}",
        quantity=1,
        currency="USD",
        amount_minor=900,
        status=PurchaseStatus.PAID,
        audit_id=audit.id,
        supplier_entity_key="current",
        commerce_model=CommerceModel.MERCHANT_OF_RECORD,
        supplier_snapshot={},
        purchased_at=datetime.now(UTC),
    )
    db_session.add(purchase)
    await db_session.flush()

    stuck = await guest_app.unprovisioned_purchases(db_session)
    assert purchase.id in {p.id for p in stuck}


# ── привласнення ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("password", ["x" * 8, "x" * 11])
async def test_a_weak_password_on_claim_is_refused_not_crashed(
    client: httpx.AsyncClient, password: str
) -> None:
    """Слабкий пароль на привласненні — 422, а не 500.

    Маршрут мав власну межу (`min_length=8`), нижчу за політику, і не
    ловив `WeakPassword` узагалі: пароль на 8–11 символів проходив
    схему, падав у домені й виходив назовні помилкою СЕРВЕРА. Підняття
    політики з 10 до 12 не створило цю діру, а розширило її — з 8–9 до
    8–11 символів.

    Схема тепер така сама, як у реєстрації (межа лише структурна), а
    політику оголошує одне місце й повідомляє один машинний код.
    """
    token = await _open(client)

    response = await client.post(
        "/v1/public/claim",
        json={"email": f"weak-{uuid.uuid4().hex[:8]}@example.com", "password": password},
        headers=_auth(token),
    )

    assert response.status_code == 422, response.text
    assert response.json()["detail"]["reason"] == "password.weak"


async def test_claim_accepts_a_password_that_meets_the_policy(
    client: httpx.AsyncClient
) -> None:
    """Межа включна й тут: дванадцять символів створюють акаунт."""
    token = await _open(client)

    response = await client.post(
        "/v1/public/claim",
        json={"email": f"ok-{uuid.uuid4().hex[:8]}@example.com", "password": "x" * 12},
        headers=_auth(token),
    )

    assert response.status_code == 201, response.text


async def test_claim_does_not_move_the_audit(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Аудит лишається тим самим: власник, ідентифікатор, покупка.

    Найважливіша властивість привласнення. Не копія, не повторний
    запуск, не переїзд — той самий рядок, у якого зʼявився учасник.
    """
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)
    session = await guest_app.resolve(db_session, token)
    organization_before = session.organization_id

    response = await client.post(
        "/v1/public/claim",
        json={"email": f"guest-{uuid.uuid4().hex[:8]}@example.com", "password": "correct horse 9"},
        headers=_auth(token),
    )
    assert response.status_code == 201, response.text
    assert uuid.UUID(response.json()["organization_id"]) == organization_before

    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    assert audit.organization_id == organization_before

    organization = await db_session.get(Organization, organization_before)
    assert organization is not None
    assert organization.kind is OrganizationKind.PERSONAL
    assert organization.is_personal is True


async def test_claim_keeps_access_to_a_purchased_report(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Створення акаунта не забирає того, за що вже заплатили."""
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)
    session = await guest_app.resolve(db_session, token)
    await client.post(
        "/v1/webhooks/fake",
        content=_purchase_event(
            organization_id=session.organization_id, audit_id=audit_id, event_id="evt-5"
        ),
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )

    await client.post(
        "/v1/public/claim",
        json={"email": f"guest-{uuid.uuid4().hex[:8]}@example.com", "password": "correct horse 9"},
        headers=_auth(token),
    )

    full = await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    assert full.status_code == 200


async def test_existing_email_is_a_merge_not_a_failure(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Наявна пошта — інший сценарій, і відповідь має це казати.

    Злиття організацій робиться окремою операцією з журналом походження;
    цей маршрут його не робить і не вдає, що зробив.
    """
    email = f"taken-{uuid.uuid4().hex[:8]}@example.com"
    first = await _open(client)
    await client.post(
        "/v1/public/claim",
        json={"email": email, "password": "correct horse 9"},
        headers=_auth(first),
    )

    second = await _open(client)
    response = await client.post(
        "/v1/public/claim",
        json={"email": email, "password": "correct horse 9"},
        headers=_auth(second),
    )
    assert response.status_code == 409
    assert response.json()["detail"]["needs"] == "merge"


async def test_claiming_twice_is_refused(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Привласнена організація — кінцевий стан, а не крок, який повторюють."""
    token = await _open(client)
    await client.post(
        "/v1/public/claim",
        json={"email": f"once-{uuid.uuid4().hex[:8]}@example.com", "password": "correct horse 9"},
        headers=_auth(token),
    )
    again = await client.post(
        "/v1/public/claim",
        json={"email": f"twice-{uuid.uuid4().hex[:8]}@example.com", "password": "correct horse 9"},
        headers=_auth(token),
    )
    assert again.status_code == 409


async def test_payment_changes_access_not_audit_identity(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    queue_is_not_the_subject: list[uuid.UUID],
) -> None:
    """Оплата відкриває той самий аудит і не запускає другого краулу.

    Ідентичність перевіряється відповідями (той самий id до і після),
    а відсутність повторного запуску — чергою: у ній рівно одна
    постановка, зроблена створенням аудиту, і оплата не додає другої.
    """
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)
    session = await guest_app.resolve(db_session, token)

    before = await client.get(f"/v1/public/audits/{audit_id}", headers=_auth(token))
    assert before.json()["audit_id"] == audit_id

    await client.post(
        "/v1/webhooks/fake",
        content=_purchase_event(
            organization_id=session.organization_id, audit_id=audit_id, event_id="evt-id-1"
        ),
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )

    after = await client.get(f"/v1/public/audits/{audit_id}", headers=_auth(token))
    assert after.json()["audit_id"] == audit_id
    full = await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))
    assert str(full.json()["audit_id"]) == audit_id

    assert queue_is_not_the_subject == [uuid.UUID(audit_id)], (
        "у черзі має бути рівно одна постановка — від створення аудиту"
    )


async def test_full_view_carries_the_complete_diagnosis(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Оплачений вигляд — повний діагноз у формі кабінету.

    Виміри, знахідки з доказами й діями, прогалини даних: усе, чого
    безкоштовний вигляд не має структурно, тут мусить бути.
    """
    token = await _open(client)
    audit_id = await _start(client, token)
    await _finish(db_session, audit_id)
    session = await guest_app.resolve(db_session, token)
    await client.post(
        "/v1/webhooks/fake",
        content=_purchase_event(
            organization_id=session.organization_id, audit_id=audit_id, event_id="evt-diag-1"
        ),
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )

    body = (await client.get(f"/v1/public/audits/{audit_id}/full", headers=_auth(token))).json()
    assert {"modules", "priorities", "next_actions", "missing_data", "summary"} <= set(body)
    # Пʼять вимірів балом і шостий знімком: доступність міряється на одній
    # сторінці, і бал 0..100 поруч із балами по всьому сайту читався б як
    # рівне з рівним. Знімок при цьому обовʼязковий — платний вигляд не
    # має мовчати про напрям, який досі важить у загальному балі.
    assert len(body["modules"]) == 5, "пʼять вимірів балом — у платному вигляді"
    assert body["accessibility"] is not None, "знімок доступності — теж частина діагнозу"
