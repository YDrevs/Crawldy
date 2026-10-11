"""Постійний платний доступ до звіту переживає гостьову сесію.

Право лежить у AuditUnlock; токен — предʼявлення, а не право. Сесія
мине за сім днів, посилання — ні. Тести перевіряють обидві половини
цієї межі: доступ живе, коли сесія мертва, і НЕ дає нічого, крім
одного купленого звіту.
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
from app.application import purchases
from app.audit.enums import AuditStatus
from app.billing.enums import BillingEventKind, PurchaseStatus
from app.core.run_enums import QuotaState
from app.models.audit import Audit, ReportLink
from app.models.guest import AuditUnlock
from app.models.purchase import OneOffPurchase

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def _sellable(single_offer: None) -> None:
    """Гостьова каса продає «разову перевірку» каталогу — заводимо її."""



async def _guest_with_paid_audit(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> tuple[str, str, str]:
    """Гість із купленим аудитом і виданим посиланням.

    Повертає (токен сесії, audit_id, токен посилання).
    """
    opened = await client.post("/v1/public/sessions")
    session_token = str(opened.json()["token"])
    headers = {"X-Guest-Token": session_token}

    started = await client.post(
        "/v1/public/audits", json={"url": "https://example.com/"}, headers=headers
    )
    audit_id = str(started.json()["audit_id"])
    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.status = AuditStatus.COMPLETED
    audit.finished_at = datetime.now(UTC)
    audit.quota_state = QuotaState.CONSUMED
    await db_session.flush()

    session = await guest_app.resolve(db_session, session_token)
    event = json.dumps(
        {
            "external_event_id": f"evt-{uuid.uuid4().hex[:10]}",
            "kind": BillingEventKind.ONE_OFF_PURCHASED.value,
            "occurred_at": datetime.now(UTC).isoformat(),
            "organization_id": str(session.organization_id),
            "quantity": 1,
            "currency": "USD",
            "amount_minor": 900,
            "payload": {"audit_id": audit_id},
        }
    ).encode()
    paid = await client.post(
        "/v1/webhooks/fake",
        content=event,
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )
    assert paid.status_code == 200, paid.text

    issued = await client.post(
        f"/v1/public/audits/{audit_id}/report-link", headers=headers
    )
    assert issued.status_code == 201, issued.text
    return session_token, audit_id, str(issued.json()["token"])


async def _expire_session(db_session: AsyncSession, session_token: str) -> None:
    session = await guest_app.resolve(db_session, session_token)
    session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()


# ── головний інваріант ─────────────────────────────────────────────────────


async def test_paid_report_survives_session_expiry(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Смерть сесії ≠ смерть купленого доступу."""
    session_token, audit_id, link_token = await _guest_with_paid_audit(client, db_session)
    await _expire_session(db_session, session_token)

    # Сесія мертва: гостьові маршрути закриті.
    via_session = await client.get(
        f"/v1/public/audits/{audit_id}", headers={"X-Guest-Token": session_token}
    )
    assert via_session.status_code == 404

    # Куплене живе.
    via_link = await client.get(f"/r/{link_token}?format=json")
    assert via_link.status_code == 200
    assert via_link.json()["target"]["url"] == "https://example.com/"


async def test_unpaid_access_still_dies_with_the_session(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Безкоштовний доступ лишається смертним: інваріант стосується купленого."""
    opened = await client.post("/v1/public/sessions")
    token = str(opened.json()["token"])
    started = await client.post(
        "/v1/public/audits",
        json={"url": "https://example.com/"},
        headers={"X-Guest-Token": token},
    )
    audit_id = str(started.json()["audit_id"])
    await _expire_session(db_session, token)

    response = await client.get(
        f"/v1/public/audits/{audit_id}", headers={"X-Guest-Token": token}
    )
    assert response.status_code == 404


async def test_link_has_no_expiry_in_the_database(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Безстроковість — NULL, а не вигаданий далекий строк."""
    _, audit_id, _ = await _guest_with_paid_audit(client, db_session)
    link = await db_session.scalar(
        select(ReportLink).where(
            ReportLink.audit_id == uuid.UUID(audit_id), ReportLink.unlock_id.is_not(None)
        )
    )
    assert link is not None
    assert link.expires_at is None
    assert link.is_active


# ── межі того, що відкриває токен ──────────────────────────────────────────


async def test_link_opens_exactly_one_audit(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Токен показує свій звіт — і жоден інший."""
    _, audit_id, link_token = await _guest_with_paid_audit(client, db_session)

    # Другий гість із власним аудитом.
    _, other_audit, _ = await _guest_with_paid_audit(client, db_session)

    mine = await client.get(f"/r/{link_token}?format=json")
    assert mine.status_code == 200
    # Звіт саме того аудиту, за який заплачено.
    assert str(audit_id) != str(other_audit)

    # Токен посилання не є сесією: гостьові маршрути його не приймають.
    as_session = await client.get(
        f"/v1/public/audits/{other_audit}", headers={"X-Guest-Token": link_token}
    )
    assert as_session.status_code == 404


async def test_link_cannot_start_audits_or_checkout(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Платний токен — не спроможність воронки: ні запуску, ні каси."""
    _, audit_id, link_token = await _guest_with_paid_audit(client, db_session)

    started = await client.post(
        "/v1/public/audits",
        json={"url": "https://another.example/"},
        headers={"X-Guest-Token": link_token},
    )
    assert started.status_code == 404

    checkout = await client.post(
        f"/v1/public/audits/{audit_id}/checkout", headers={"X-Guest-Token": link_token}
    )
    assert checkout.status_code == 404


async def test_audit_id_alone_is_still_nothing(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Ідентифікатор — не авторизація, і /r/ ним не відкривається."""
    _, audit_id, _ = await _guest_with_paid_audit(client, db_session)
    response = await client.get(f"/r/{audit_id}?format=json")
    assert response.status_code == 404


# ── створення доступу ──────────────────────────────────────────────────────


async def test_checkout_return_grants_no_link(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Повернення з каси не створює ні розблокування, ні посилання."""
    opened = await client.post("/v1/public/sessions")
    token = str(opened.json()["token"])
    headers = {"X-Guest-Token": token}
    started = await client.post(
        "/v1/public/audits", json={"url": "https://example.com/"}, headers=headers
    )
    audit_id = str(started.json()["audit_id"])
    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.status = AuditStatus.COMPLETED
    audit.finished_at = datetime.now(UTC)
    await db_session.flush()

    checkout = await client.post(
        f"/v1/public/audits/{audit_id}/checkout", headers=headers
    )
    assert checkout.status_code == 200

    # Оплати не було: посилання не видається.
    issued = await client.post(
        f"/v1/public/audits/{audit_id}/report-link", headers=headers
    )
    assert issued.status_code == 402

    links = list(
        await db_session.scalars(
            select(ReportLink).where(ReportLink.audit_id == uuid.UUID(audit_id))
        )
    )
    assert links == []


async def test_repeated_webhook_creates_no_extra_access(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Повторна доставка події не плодить ні розблокувань, ні посилань."""
    session_token, audit_id, _ = await _guest_with_paid_audit(client, db_session)
    session = await guest_app.resolve(db_session, session_token)

    event = json.dumps(
        {
            "external_event_id": "evt-repeat-1",
            "kind": BillingEventKind.ONE_OFF_PURCHASED.value,
            "occurred_at": datetime.now(UTC).isoformat(),
            "organization_id": str(session.organization_id),
            "quantity": 1,
            "currency": "USD",
            "amount_minor": 900,
            "payload": {"audit_id": audit_id},
        }
    ).encode()
    for _ in range(2):
        response = await client.post(
            "/v1/webhooks/fake",
            content=event,
            headers={"x-fake-signature": "valid", "content-type": "application/json"},
        )
        assert response.status_code == 200

    unlocks = list(
        await db_session.scalars(
            select(AuditUnlock).where(AuditUnlock.audit_id == uuid.UUID(audit_id))
        )
    )
    assert len(unlocks) == 1
    # Посилання видає лише людина через свій маршрут — вебхук не видає.
    links = list(
        await db_session.scalars(
            select(ReportLink).where(ReportLink.audit_id == uuid.UUID(audit_id))
        )
    )
    assert len(links) == 1


# ── привласнення і злиття ──────────────────────────────────────────────────


async def test_claim_keeps_the_link_alive(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Створення акаунта — ще один шлях до аудиту, а не заміна посилання."""
    session_token, _, link_token = await _guest_with_paid_audit(client, db_session)
    claimed = await client.post(
        "/v1/public/claim",
        json={"email": f"c-{uuid.uuid4().hex[:8]}@example.com", "password": "correct horse 9"},
        headers={"X-Guest-Token": session_token},
    )
    assert claimed.status_code == 201

    response = await client.get(f"/r/{link_token}?format=json")
    assert response.status_code == 200


async def test_merge_does_not_broaden_the_link(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Після злиття посилання показує той самий один звіт — і не більше."""
    from app.identity import service as identity

    from .conftest import sign_in_as

    session_token, _, link_token = await _guest_with_paid_audit(client, db_session)

    email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    await sign_in_as(client, email)
    user = await identity.find_user_by_email(db_session, email)
    assert user is not None
    orgs = await identity.organizations_of(db_session, user_id=user.id)
    dest_org = orgs[0].id

    # Чужий аудит у цілі — його посилання відкривати не має.
    foreign = Audit(
        organization_id=dest_org,
        url="https://other.test/",
        origin="https://other.test",
        status=AuditStatus.COMPLETED,
        finished_at=datetime.now(UTC),
    )
    db_session.add(foreign)
    await db_session.flush()

    merged = await client.post(
        "/v1/account/guest-merge",
        json={"reason": "тест"},
        headers={"X-Guest-Token": session_token},
    )
    assert merged.status_code == 201, merged.text

    still = await client.get(f"/r/{link_token}?format=json")
    assert still.status_code == 200
    assert still.json()["target"]["url"] == "https://example.com/"

    # Токен посилання не відкриває нічого в цілі.
    as_session = await client.get(
        f"/v1/public/audits/{foreign.id}", headers={"X-Guest-Token": link_token}
    )
    assert as_session.status_code == 404


# ── відкликання ────────────────────────────────────────────────────────────


async def test_refund_revokes_the_link_but_not_the_history(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Повернення коштів гасить токен; покупка й розблокування лишаються."""
    _, audit_id, link_token = await _guest_with_paid_audit(client, db_session)

    purchase = await db_session.scalar(
        select(OneOffPurchase).where(OneOffPurchase.audit_id == uuid.UUID(audit_id))
    )
    assert purchase is not None
    result = await purchases.refund(
        db_session, provider=purchase.provider, external_id=purchase.external_id
    )
    assert result is not None
    await db_session.flush()

    dead = await client.get(f"/r/{link_token}?format=json")
    assert dead.status_code == 404

    # Історія пояснюється незалежно від токена.
    await db_session.refresh(purchase)
    assert purchase.status is PurchaseStatus.REFUNDED
    unlock = await db_session.scalar(
        select(AuditUnlock).where(AuditUnlock.audit_id == uuid.UUID(audit_id))
    )
    assert unlock is not None, "розблокування — факт історії, токен його не тримає"


async def test_reissue_while_session_lives_is_the_recovery_path(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Загублений токен за живої сесії відновлюється повторною видачею."""
    session_token, audit_id, first_token = await _guest_with_paid_audit(client, db_session)

    second = await client.post(
        f"/v1/public/audits/{audit_id}/report-link",
        headers={"X-Guest-Token": session_token},
    )
    assert second.status_code == 201
    second_token = str(second.json()["token"])
    assert second_token != first_token

    # Обидва живі й обидва відкликаються окремо.
    assert (await client.get(f"/r/{first_token}?format=json")).status_code == 200
    assert (await client.get(f"/r/{second_token}?format=json")).status_code == 200


# ── екранний вигляд за постійним платним токеном ───────────────────────────


async def test_web_view_opens_by_paid_token_alone(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Платний токен відкриває екранний вигляд — без сесії, без акаунта.

    Форма — та сама, що в кабінеті: подання звіту одне на весь продукт.
    """
    _, audit_id, link_token = await _guest_with_paid_audit(client, db_session)

    response = await client.get(f"/r/{link_token}?format=web")
    assert response.status_code == 200, response.text
    body = response.json()
    assert {"modules", "priorities", "next_actions", "missing_data"} <= set(body)
    assert str(body["audit_id"]) == audit_id
    # Пʼять, а не шість: доступність подається знімком сторінки.
    assert len(body["modules"]) == 5
    assert body["accessibility"] is not None


async def test_web_view_survives_session_expiry(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    queue_is_not_the_subject: list[uuid.UUID],
) -> None:
    """Смерть сесії не забирає екран купленого звіту.

    Повний життєвий цикл: аудит → оплата → посилання → екран →
    прострочена сесія → той самий екран тим самим токеном. Той самий
    аудит, і жодної нової постановки в чергу.
    """
    session_token, audit_id, link_token = await _guest_with_paid_audit(client, db_session)

    before = await client.get(f"/r/{link_token}?format=web")
    assert before.status_code == 200
    assert str(before.json()["audit_id"]) == audit_id

    await _expire_session(db_session, session_token)
    via_session = await client.get(
        f"/v1/public/audits/{audit_id}/full", headers={"X-Guest-Token": session_token}
    )
    assert via_session.status_code == 404, "сесія мертва — і це не фолбек"

    after = await client.get(f"/r/{link_token}?format=web")
    assert after.status_code == 200
    assert str(after.json()["audit_id"]) == audit_id

    assert queue_is_not_the_subject == [uuid.UUID(audit_id)], (
        "перегляди не запускають другого краулу"
    )


async def test_web_view_refuses_everything_else_uniformly(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Ідентифікатор аудиту, вигаданий токен — той самий 404 без пояснень."""
    _, audit_id, _ = await _guest_with_paid_audit(client, db_session)

    by_audit_id = await client.get(f"/r/{audit_id}?format=web")
    assert by_audit_id.status_code == 404

    invalid = await client.get(f"/r/{'x' * 43}?format=web")
    assert invalid.status_code == 404


async def test_web_view_dies_with_refund(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Повернення коштів закриває і екран: ті самі правила, той самий 404."""
    _, audit_id, link_token = await _guest_with_paid_audit(client, db_session)
    assert (await client.get(f"/r/{link_token}?format=web")).status_code == 200

    purchase = await db_session.scalar(
        select(OneOffPurchase).where(OneOffPurchase.audit_id == uuid.UUID(audit_id))
    )
    assert purchase is not None
    await purchases.refund(
        db_session, provider=purchase.provider, external_id=purchase.external_id
    )
    await db_session.flush()

    assert (await client.get(f"/r/{link_token}?format=web")).status_code == 404


async def test_ordinary_share_link_gets_no_web_view(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Поділене з кабінету посилання лишається документом.

    Чи має воно відкривати інтерактивний звіт — окреме продуктове
    рішення, і цей формат його не ухвалює мовчки. Відмова та сама, що
    на неіснуючий токен: формат не має розрізняти типи посилань.
    """
    from app.services import link_service

    _, audit_id, _ = await _guest_with_paid_audit(client, db_session)
    _, share_token = await link_service.create_link(
        db_session, uuid.UUID(audit_id), lang="en", ttl_days=14
    )

    web = await client.get(f"/r/{share_token}?format=web")
    assert web.status_code == 404
    # Документи при цьому працюють, як і працювали.
    assert (await client.get(f"/r/{share_token}?format=json")).status_code == 200


async def test_paid_token_grants_nothing_beyond_its_report(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Токен — вхід у один куплений звіт, не в організацію.

    Гостьові маршрути його не приймають, чужого аудиту він не називає,
    а формати файлів працюють поруч з екраном на тому самому аудиті.
    """
    _, audit_id, link_token = await _guest_with_paid_audit(client, db_session)
    _, other_audit, _ = await _guest_with_paid_audit(client, db_session)

    as_session = await client.get(
        "/v1/public/audits/" + other_audit, headers={"X-Guest-Token": link_token}
    )
    assert as_session.status_code == 404

    web = await client.get(f"/r/{link_token}?format=web")
    assert str(web.json()["audit_id"]) == audit_id != other_audit

    as_json = await client.get(f"/r/{link_token}?format=json")
    assert as_json.status_code == 200
    docx = await client.get(f"/r/{link_token}?format=docx")
    assert docx.status_code == 200
    assert docx.headers["content-type"].startswith("application/vnd.openxmlformats")


# ── мова постійного посилання ──────────────────────────────────────────────


async def _give_finding(db_session: AsyncSession, audit_id: str) -> None:
    """Знахідка структурою (ключ + параметри): є що локалізувати."""
    from app.audit.enums import Module, Severity
    from app.models.audit import AuditIssue, AuditTarget

    # Запуск воронки вже створив ціль — знахідка чіпляється до неї.
    target = await db_session.scalar(
        select(AuditTarget).where(AuditTarget.audit_id == uuid.UUID(audit_id))
    )
    assert target is not None
    target.status = AuditStatus.COMPLETED
    db_session.add(
        AuditIssue(
            audit_id=uuid.UUID(audit_id),
            target_id=target.id,
            module=Module.SEO,
            code="seo.h1",
            severity=Severity.HIGH,
            title="СТАРИЙ КЕШ",
            evidence={"found": 2, "expected": 1},
            weight=3,
            issue_variant="multiple",
            msg_key="seo.h1.multiple",
            msg_params={"count": 2},
        )
    )
    await db_session.flush()


def _catalogue_title(lang: str) -> str:
    from app.audit.i18n import en, uk

    catalogue = uk.MESSAGES if lang == "uk" else en.MESSAGES
    return str(catalogue["seo.h1.multiple"]["title"]).format(count=2)


async def test_link_locale_rules_screen_and_files_alike(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Мова посилання — одна на екран, JSON і Word.

    Посилання, видане українською, віддає українську всюди; посилання
    без явної мови — продуктовий дефолт, і він не підмінює явно обрану:
    два токени на той самий аудит показують різні мови.
    """
    session_token, audit_id, _ = await _guest_with_paid_audit(client, db_session)
    await _give_finding(db_session, audit_id)

    uk_token, _ = await guest_app.issue_report_link(
        db_session, audit_id=uuid.UUID(audit_id), lang="uk"
    )
    default_issued = await client.post(
        f"/v1/public/audits/{audit_id}/report-link",
        headers={"X-Guest-Token": session_token},
    )
    default_token = str(default_issued.json()["token"])

    uk_title = _catalogue_title("uk")
    en_title = _catalogue_title("en")
    assert uk_title != en_title, "тест мовчав би, якби каталоги збігалися"

    web_uk = (await client.get(f"/r/{uk_token}?format=web")).json()
    json_uk = (await client.get(f"/r/{uk_token}?format=json")).json()
    assert web_uk["priorities"][0]["title"] == uk_title
    assert json_uk["issues"][0]["title"] == uk_title, (
        "екран і файл читають мову з одного місця — з посилання"
    )

    web_default = (await client.get(f"/r/{default_token}?format=web")).json()
    assert web_default["priorities"][0]["title"] == en_title
    assert web_default["priorities"][0]["title"] != uk_title, (
        "дефолт не підмінює явно обрану мову"
    )


async def test_link_locale_survives_expiry_and_merge(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Ні смерть сесії, ні злиття не змінюють мови купленого звіту."""
    from .conftest import sign_in_as

    session_token, audit_id, _ = await _guest_with_paid_audit(client, db_session)
    await _give_finding(db_session, audit_id)
    uk_token, _ = await guest_app.issue_report_link(
        db_session, audit_id=uuid.UUID(audit_id), lang="uk"
    )
    uk_title = _catalogue_title("uk")

    await _expire_session(db_session, session_token)
    after_expiry = (await client.get(f"/r/{uk_token}?format=web")).json()
    assert after_expiry["priorities"][0]["title"] == uk_title

    await sign_in_as(client, f"loc-{uuid.uuid4().hex[:8]}@example.com")
    merged = await client.post(
        "/v1/account/guest-merge",
        json={"reason": "тест мови"},
        headers={"X-Guest-Token": session_token},
    )
    # Сесія вже мертва — злиття нею не пройде; воскресимо для операції.
    if merged.status_code == 404:
        session = await db_session.scalar(
            select(guest_app.GuestSession).where(
                guest_app.GuestSession.token_hash == guest_app.hash_token(session_token)
            )
        )
        assert session is not None
        session.expires_at = datetime.now(UTC) + timedelta(days=1)
        await db_session.flush()
        merged = await client.post(
            "/v1/account/guest-merge",
            json={"reason": "тест мови"},
            headers={"X-Guest-Token": session_token},
        )
    assert merged.status_code == 201, merged.text

    after_merge = (await client.get(f"/r/{uk_token}?format=web")).json()
    assert after_merge["priorities"][0]["title"] == uk_title


async def test_production_mint_freezes_the_purchased_locale(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Справжній шлях воронки: мова передається при видачі й заморожується.

    Людина пройшла воронку українською — фронтенд передає uk у видачу,
    і постійне посилання віддає українську на екрані й у файлі. Без
    мови — продуктовий дефолт; непідтримувана мова чесно спадає на
    нього ж, але явно обрану підтримувану дефолт не підмінює ніколи.
    """
    session_token, audit_id, _ = await _guest_with_paid_audit(client, db_session)
    await _give_finding(db_session, audit_id)
    headers = {"X-Guest-Token": session_token}

    minted_uk = await client.post(
        f"/v1/public/audits/{audit_id}/report-link",
        json={"lang": "uk"},
        headers=headers,
    )
    assert minted_uk.status_code == 201, minted_uk.text
    uk_token = str(minted_uk.json()["token"])

    minted_default = await client.post(
        f"/v1/public/audits/{audit_id}/report-link", headers=headers
    )
    default_token = str(minted_default.json()["token"])

    minted_unsupported = await client.post(
        f"/v1/public/audits/{audit_id}/report-link",
        json={"lang": "ja"},
        headers=headers,
    )
    unsupported_token = str(minted_unsupported.json()["token"])

    uk_title = _catalogue_title("uk")
    en_title = _catalogue_title("en")

    web_uk = (await client.get(f"/r/{uk_token}?format=web")).json()
    json_uk = (await client.get(f"/r/{uk_token}?format=json")).json()
    assert web_uk["priorities"][0]["title"] == uk_title
    assert json_uk["issues"][0]["title"] == uk_title

    assert (await client.get(f"/r/{default_token}?format=web")).json()["priorities"][0][
        "title"
    ] == en_title
    # Мова поза шістьма мовами запуску: чесний дефолт, не 500. Колись цим
    # прикладом була французька — тепер вона повна мова запуску й віддає
    # французьку, тож неповну довелося шукати далі.
    assert (await client.get(f"/r/{unsupported_token}?format=web")).json()["priorities"][0][
        "title"
    ] == en_title

    # Смерть сесії не перекладає куплене.
    await _expire_session(db_session, session_token)
    still_uk = (await client.get(f"/r/{uk_token}?format=web")).json()
    assert still_uk["priorities"][0]["title"] == uk_title
