"""Злиття гостьової організації в наявну — і закритий чорний хід.

Найважливіше тут не «злиття працює», а межі: сайт ніколи не змінює
власника, старий токен після злиття читає рівно своє й не створює
нічого, квота з незавершеним резервом зупиняє операцію, а загального
шляху перенести завершений аудит між організаціями не існує.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application import guest as guest_app
from app.audit.enums import AuditStatus
from app.billing.enums import BillingEventKind
from app.core.run_enums import QuotaState
from app.identity.enums import OrganizationKind
from app.models.audit import Audit
from app.models.guest import GuestMerge, GuestMergeAudit
from app.models.identity import Organization
from app.models.purchase import AuditCredit, OneOffPurchase
from app.models.sites import Site, SiteMerge

from .conftest import sign_in_as

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture(autouse=True)
async def _sellable(single_offer: None) -> None:
    """Гостьова каса продає «разову перевірку» каталогу — заводимо її."""



# ── будівельні блоки ───────────────────────────────────────────────────────


async def _guest_with_audit(
    client: httpx.AsyncClient,
    db_session: AsyncSession,
    url: str = "https://example.com/",
) -> tuple[str, str]:
    """Гість із завершеним аудитом. Повертає (токен, audit_id)."""
    opened = await client.post("/v1/public/sessions")
    token = str(opened.json()["token"])
    started = await client.post(
        "/v1/public/audits", json={"url": url}, headers={"X-Guest-Token": token}
    )
    assert started.status_code == 202, started.text
    audit_id = str(started.json()["audit_id"])

    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.status = AuditStatus.COMPLETED
    audit.finished_at = datetime.now(UTC)
    # Квота розрахована: звичайний стан завершеного аудиту.
    audit.quota_state = QuotaState.CONSUMED
    await db_session.flush()
    return token, audit_id


async def _paid(client: httpx.AsyncClient, db_session: AsyncSession, token: str, audit_id: str) -> None:
    """Оплатити повний вигляд перевіреною подією провайдера."""
    session = await guest_app.resolve(db_session, token)
    body = json.dumps(
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
    response = await client.post(
        "/v1/webhooks/fake",
        content=body,
        headers={"x-fake-signature": "valid", "content-type": "application/json"},
    )
    assert response.status_code == 200, response.text


async def _owner(client: httpx.AsyncClient, db_session: AsyncSession) -> tuple[str, uuid.UUID]:
    """Зареєстрований власник організації. Повертає (email, org_id)."""
    email = f"owner-{uuid.uuid4().hex[:8]}@example.com"
    response = await sign_in_as(client, email)
    assert response.status_code in (200, 201), response.text
    from app.identity import service as identity

    user = await identity.find_user_by_email(db_session, email)
    assert user is not None
    orgs = await identity.organizations_of(db_session, user_id=user.id)
    return email, orgs[0].id


async def _merge(
    client: httpx.AsyncClient, token: str, reason: str = "тест"
) -> httpx.Response:
    return await client.post(
        "/v1/account/guest-merge",
        json={"reason": reason},
        headers={"X-Guest-Token": token},
    )


# ── сам переніс ────────────────────────────────────────────────────────────


async def test_merge_into_org_that_already_has_the_site(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Колізія origin — звичайний випадок, і сайт НЕ переїжджає.

    Людина зливає гостя саме тому, що аудитувала свій сайт анонімно, —
    тож цільова організація майже завжди вже має цей origin. Аудит
    перепризначається на наявний сайт цілі; гостьовий рядок лишається
    в гостя, заархівований.
    """
    token, audit_id = await _guest_with_audit(client, db_session, "https://example.com/")
    guest_session = await guest_app.resolve(db_session, token)
    guest_org = guest_session.organization_id

    _, dest_org = await _owner(client, db_session)
    existing = Site(
        organization_id=dest_org, origin="https://example.com", display_name="мій сайт"
    )
    db_session.add(existing)
    await db_session.flush()

    response = await _merge(client, token)
    assert response.status_code == 201, response.text
    assert response.json()["audits_moved"] == 1

    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    assert audit.organization_id == dest_org
    assert audit.site_id == existing.id

    # Сайт-джерело не змінив власника — лише заархівований.
    guest_site = await db_session.scalar(
        select(Site).where(Site.organization_id == guest_org)
    )
    assert guest_site is not None
    assert guest_site.archived_at is not None

    # У цілі рівно один сайт із цим origin: унікальність жила весь час.
    count = await db_session.scalar(
        select(Site.id).where(
            Site.organization_id == dest_org, Site.origin == "https://example.com"
        )
    )
    assert count == existing.id


async def test_merge_creates_the_site_when_destination_lacks_it(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Без колізії ціль отримує новий рядок сайту — не гостьовий."""
    token, audit_id = await _guest_with_audit(client, db_session)
    guest_session = await guest_app.resolve(db_session, token)
    guest_site = await db_session.scalar(
        select(Site).where(Site.organization_id == guest_session.organization_id)
    )
    assert guest_site is not None

    _, dest_org = await _owner(client, db_session)
    response = await _merge(client, token)
    assert response.status_code == 201, response.text

    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    created = await db_session.get(Site, audit.site_id)
    assert created is not None
    assert created.organization_id == dest_org
    assert created.id != guest_site.id
    assert created.origin == guest_site.origin

    # Site.organization_id незмінний: гостьовий рядок досі в гостя.
    await db_session.refresh(guest_site)
    assert guest_site.organization_id == guest_session.organization_id


async def test_purchases_credits_and_unlock_survive_the_merge(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Покупка й кредити переїжджають; ланцюг purchase → audit → unlock цілий."""
    token, audit_id = await _guest_with_audit(client, db_session)
    await _paid(client, db_session, token, audit_id)
    _, dest_org = await _owner(client, db_session)

    response = await _merge(client, token)
    assert response.status_code == 201
    body = response.json()
    assert body["purchases_moved"] == 1
    assert body["credits_moved"] >= 1

    purchase = await db_session.scalar(
        select(OneOffPurchase).where(OneOffPurchase.audit_id == uuid.UUID(audit_id))
    )
    assert purchase is not None
    assert purchase.organization_id == dest_org

    credit = await db_session.scalar(
        select(AuditCredit).where(AuditCredit.purchase_id == purchase.id)
    )
    assert credit is not None
    assert credit.organization_id == dest_org

    # Розблокування привʼязане до аудиту — воно переїхало без запиту.
    assert await guest_app.is_unlocked(db_session, uuid.UUID(audit_id))


async def test_journal_explains_the_merge(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Журнал: хто, звідки, куди, які аудити, які сайти, чому."""
    token, audit_id = await _guest_with_audit(client, db_session)
    guest_session = await guest_app.resolve(db_session, token)
    _, dest_org = await _owner(client, db_session)

    response = await _merge(client, token, reason="аудитував свій сайт гостем")
    merge_id = uuid.UUID(response.json()["merge_id"])

    merge = await db_session.get(GuestMerge, merge_id)
    assert merge is not None
    assert merge.guest_organization_id == guest_session.organization_id
    assert merge.destination_organization_id == dest_org
    assert merge.performed_by_user_id is not None
    assert merge.reason == "аудитував свій сайт гостем"
    assert merge.site_map and merge.site_map[0]["origin"]

    moved = await db_session.scalar(
        select(GuestMergeAudit).where(GuestMergeAudit.merge_id == merge_id)
    )
    assert moved is not None
    assert moved.audit_id == uuid.UUID(audit_id)

    # Зміну site_id пояснює той самий журнал, що й обʼєднання сайтів.
    site_merge = await db_session.scalar(
        select(SiteMerge).where(SiteMerge.organization_id == dest_org)
    )
    assert site_merge is not None
    assert site_merge.audits_moved == 1

    # Джерело — термінальний CLAIMED.
    organization = await db_session.get(Organization, guest_session.organization_id)
    assert organization is not None
    assert organization.kind is OrganizationKind.CLAIMED


# ── доступ старої спроможності після злиття ────────────────────────────────


async def test_old_capability_still_reads_its_purchased_report(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Створення акаунта не забирає куплене — навіть після злиття."""
    token, audit_id = await _guest_with_audit(client, db_session)
    await _paid(client, db_session, token, audit_id)
    await _owner(client, db_session)
    await _merge(client, token)

    full = await client.get(
        f"/v1/public/audits/{audit_id}/full", headers={"X-Guest-Token": token}
    )
    assert full.status_code == 200
    short = await client.get(
        f"/v1/public/audits/{audit_id}", headers={"X-Guest-Token": token}
    )
    assert short.status_code == 200


async def test_old_capability_reads_nothing_else_in_the_destination(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Спроможність не успадковує організацію — лише свої аудити."""
    token, _ = await _guest_with_audit(client, db_session)
    _, dest_org = await _owner(client, db_session)

    # Чужий аудит, що вже жив у цілі до злиття.
    foreign = Audit(
        organization_id=dest_org,
        url="https://other.test/",
        origin="https://other.test",
        status=AuditStatus.COMPLETED,
        finished_at=datetime.now(UTC),
    )
    db_session.add(foreign)
    await db_session.flush()

    await _merge(client, token)

    response = await client.get(
        f"/v1/public/audits/{foreign.id}", headers={"X-Guest-Token": token}
    )
    assert response.status_code == 404


async def test_old_capability_cannot_start_audits_after_merge(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Чорний хід закритий: нове створює лише гостьова організація."""
    token, _ = await _guest_with_audit(client, db_session)
    await _owner(client, db_session)
    await _merge(client, token)

    started = await client.post(
        "/v1/public/audits",
        json={"url": "https://another.example/"},
        headers={"X-Guest-Token": token},
    )
    assert started.status_code == 409
    assert started.json()["detail"]["reason"] == "already.claimed"


async def test_old_capability_cannot_checkout_after_merge(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    token, audit_id = await _guest_with_audit(client, db_session)
    await _owner(client, db_session)
    await _merge(client, token)

    checkout = await client.post(
        f"/v1/public/audits/{audit_id}/checkout", headers={"X-Guest-Token": token}
    )
    assert checkout.status_code == 409
    assert checkout.json()["detail"]["reason"] == "already.claimed"


async def test_new_user_claim_also_closes_the_back_door(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Той самий захист на шляху нової людини, не лише на злитті."""
    token, audit_id = await _guest_with_audit(client, db_session)
    claimed = await client.post(
        "/v1/public/claim",
        json={"email": f"new-{uuid.uuid4().hex[:8]}@example.com", "password": "correct horse 9"},
        headers={"X-Guest-Token": token},
    )
    assert claimed.status_code == 201

    started = await client.post(
        "/v1/public/audits",
        json={"url": "https://another.example/"},
        headers={"X-Guest-Token": token},
    )
    assert started.status_code == 409

    checkout = await client.post(
        f"/v1/public/audits/{audit_id}/checkout", headers={"X-Guest-Token": token}
    )
    assert checkout.status_code == 409

    # Читання при цьому живе: org не змінювалась.
    short = await client.get(
        f"/v1/public/audits/{audit_id}", headers={"X-Guest-Token": token}
    )
    assert short.status_code == 200


# ── quota guard ────────────────────────────────────────────────────────────


async def test_merge_refused_while_quota_is_reserved(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Незавершений резерв зупиняє злиття відновлюваним 409.

    Інакше settle_quota повернув би квоту в лічильник цілі, який нічого
    не списував.
    """
    token, audit_id = await _guest_with_audit(client, db_session)
    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.quota_state = QuotaState.RESERVED
    await db_session.flush()
    await _owner(client, db_session)

    response = await _merge(client, token)
    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail["reason"] == "quota.pending"
    assert detail["retryable"] is True

    # Джерело НЕ стало CLAIMED: операція не почалась.
    session = await guest_app.resolve(db_session, token)
    organization = await db_session.get(Organization, session.organization_id)
    assert organization is not None
    assert organization.kind is OrganizationKind.GUEST


async def test_merge_succeeds_after_quota_settles(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Той самий гість, той самий запит — після розрахунку проходить."""
    token, audit_id = await _guest_with_audit(client, db_session)
    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    audit.quota_state = QuotaState.RESERVED
    await db_session.flush()
    await _owner(client, db_session)

    refused = await _merge(client, token)
    assert refused.status_code == 409

    audit.quota_state = QuotaState.CONSUMED
    await db_session.flush()

    retried = await _merge(client, token)
    assert retried.status_code == 201


# ── ідемпотентність і межі ─────────────────────────────────────────────────


async def test_retry_after_success_is_terminal(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Повтор після успіху нічого не робить і не дублює журналу."""
    token, _ = await _guest_with_audit(client, db_session)
    await _owner(client, db_session)

    first = await _merge(client, token)
    assert first.status_code == 201
    second = await _merge(client, token)
    assert second.status_code == 409
    assert second.json()["detail"]["reason"] == "already.claimed"

    merges = list(await db_session.scalars(select(GuestMerge)))
    assert len(merges) == 1


async def test_merge_after_new_user_claim_is_rejected(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Привласнене новою людиною не зливається вдруге."""
    token, _ = await _guest_with_audit(client, db_session)
    await client.post(
        "/v1/public/claim",
        json={"email": f"c-{uuid.uuid4().hex[:8]}@example.com", "password": "correct horse 9"},
        headers={"X-Guest-Token": token},
    )
    await _owner(client, db_session)
    response = await _merge(client, token)
    assert response.status_code == 409


async def test_history_stays_where_it_happened(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Події білінгу й лічильники квоти лишаються за гостем.

    Вони описують минуле: кому подія була адресована на момент доставки
    й чий період спожив аудит. Переписати їх означало б зробити вигляд,
    що покупка від початку належала цілі.
    """
    from app.models.billing import BillingEvent
    from app.models.usage import Usage

    token, audit_id = await _guest_with_audit(client, db_session)
    await _paid(client, db_session, token, audit_id)
    guest_session = await guest_app.resolve(db_session, token)
    guest_org = guest_session.organization_id
    await _owner(client, db_session)
    await _merge(client, token)

    event = await db_session.scalar(
        select(BillingEvent).where(BillingEvent.organization_id == guest_org)
    )
    assert event is not None, "подія доставки лишається адресованою гостю"

    # Превʼю квоти не торкається взагалі (безкоштовні перевірки
    # необмежені), тож лічильника періоду немає НІ в кого — і злиття
    # не мало чого переписувати.
    usage = await db_session.scalar(select(Usage))
    assert usage is None, "превʼю не породжує лічильників квоти"


async def test_no_generic_transfer_path_exists(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Джерелом злиття буває лише гостьова організація.

    Це і є запобіжник проти «загального переносу аудитів»: звичайна
    організація ніколи не проходить перевірку kind, а іншого шляху
    змінити власника завершеного аудиту в кодовій базі немає.
    """
    _, org_a = await _owner(client, db_session)
    # Звичайна організація зі звичайним аудитом.
    audit = Audit(
        organization_id=org_a,
        url="https://mine.test/",
        origin="https://mine.test",
        status=AuditStatus.COMPLETED,
        finished_at=datetime.now(UTC),
    )
    db_session.add(audit)
    await db_session.flush()

    # Гостьова сесія, силоміць привʼязана до звичайної організації, —
    # єдиний спосіб дістатися merge_into повз воронку.
    from app.models.guest import GuestSession as GS

    fake = GS(
        organization_id=org_a,
        token_hash=guest_app.hash_token("forced"),
        expires_at=datetime.now(UTC) + guest_app.SESSION_TTL,
    )
    db_session.add(fake)
    await db_session.flush()

    with pytest.raises(guest_app.AlreadyClaimed):
        await guest_app.merge_into(
            db_session,
            session=fake,
            destination_organization_id=org_a,
            performed_by_user_id=None,
        )


async def test_merge_requires_both_proofs(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Без токена гостя — 404; без автентифікації — 401."""
    token, _ = await _guest_with_audit(client, db_session)
    await _owner(client, db_session)

    without_token = await client.post("/v1/account/guest-merge", json={"reason": ""})
    assert without_token.status_code == 404

    await client.post("/v1/auth/logout")
    without_auth = await client.post(
        "/v1/account/guest-merge", json={"reason": ""}, headers={"X-Guest-Token": token}
    )
    assert without_auth.status_code == 401
