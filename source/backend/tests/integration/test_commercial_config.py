"""Комерційна конфігурація — джерело правди, яке редагує адмін.

Закони цього файлу:

* MONTHLY повністю конфігурується без коду: назва, видимість, прайси,
  ліміт краулів (число або безліміт), ліміт присутності — це PUT
  адміністратора, а клієнтський каталог читає результат одразу;
* присутність безлімітною не буває — конфігурація з None відхиляється;
* покупка зберігає зліпок умов: редагування каталогу не переписує ні
  того, що людина вже купила, ні того, за що вона саме зараз платить;
* наділ поточного періоду підписки знімкований: зміна тарифу посеред
  періоду не чіпає виданого, наступний період бере нові значення;
* сесію порталу платежів створює POST і ніщо її не зберігає.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy import update as sa_update

from app.application import billing as pipeline
from app.billing import quota as billing_quota
from app.billing import service as billing_service
from app.billing.enums import BillingEventKind
from app.billing.providers.fake import FakeBillingProvider
from app.identity.enums import PlatformRole
from app.models.billing import BillingCustomer, Subscription
from app.models.identity import Organization, User
from app.models.purchase import AuditCredit, OneOffPurchase
from tests.integration.conftest import register

pytestmark = pytest.mark.asyncio

# Прайс тарифу карбує ПУБЛІКАЦІЯ (фейковий публікатор: `fake_<код>_<період>`);
# значення з тіла PUT сервер ігнорує. Події підписки мусять називати саме
# опублікований прайс — так їх зіставляє конвеєр.
PRO_FAKE_PRICE = "fake_pro_month"


@pytest_asyncio.fixture
async def staff(client, db_session):
    """Клієнт зі службовою роллю: реєстрація + підняття platform_role."""
    body = (await register(client, f"cfg-staff-{uuid.uuid4().hex[:8]}@example.com")).json()
    await db_session.execute(
        sa_update(User)
        .where(User.id == uuid.UUID(body["user"]["id"]))
        .values(platform_role=PlatformRole.STAFF)
    )
    await db_session.commit()
    return client


async def _org_of(db_session) -> uuid.UUID:
    return (await db_session.execute(
        select(Organization.id).order_by(Organization.created_at.desc()).limit(1)
    )).scalar_one()


def _plan_payload(**overrides) -> dict:
    """Повний PUT тарифу: заміна, а не патч — як і працює ендпойнт."""
    payload = {
        "code": "pro",
        "name": "Pro",
        "description": "",
        "is_public": True,
        "sort_order": 2,
        "entitlements": {
            "audits_per_period": 100,
            "presence_per_period": 10,
            "max_pages_per_audit": 50,
            "report_download": True,
        },
        "prices": [{
            "provider": "fake",
            "provider_price_id": PRO_FAKE_PRICE,
            "currency": "USD",
            "interval": "month",
            "display_amount_minor": 4900,
        }],
    }
    payload.update(overrides)
    return payload


async def _subscribe_to_pro(db_session, org: uuid.UUID) -> FakeBillingProvider:
    """Активувати підписку на «pro» через справжній конвеєр подій."""
    fake = FakeBillingProvider()
    result = await pipeline.ingest(
        db_session, fake.activate(organization_id=org, price_ref=PRO_FAKE_PRICE)
    )
    assert result.outcome == "processed", result.error
    return fake


# ── MONTHLY конфігурується без коду ──────────────────────────────────


async def test_monthly_plan_is_reconfigured_by_put_not_by_release(staff, db_session):
    """«$49 → $79», нова назва, «500 → 1000» — це PUT, і каталог бачить
    результат наступним же запитом."""
    saved = await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        name="Pro Max",
        entitlements={
            "audits_per_period": 1000,
            "presence_per_period": 10,
            "max_pages_per_audit": 50,
        },
        prices=[{
            "provider": "fake", "provider_price_id": PRO_FAKE_PRICE,
            "currency": "USD", "interval": "month",
            "display_amount_minor": 7900,
        }],
    ))
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["name"] == "Pro Max"
    assert body["entitlements"]["audits_per_period"] == 1000
    assert body["prices"][0]["display_amount_minor"] == 7900

    public = (await staff.get("/v1/plans")).json()
    pro = next(p for p in public["plans"] if p["code"] == "pro")
    assert pro["name"] == "Pro Max"
    assert pro["prices"][0]["amount_minor"] == 7900


async def test_limited_crawl_quantity_is_pure_configuration(staff, db_session):
    await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        entitlements={"audits_per_period": 3, "presence_per_period": 0},
    ))
    org = await _org_of(db_session)
    await _subscribe_to_pro(db_session, org)
    ent = await billing_service.for_organization(db_session, organization_id=org)
    assert ent.limit("audits_per_period") == 3


async def test_monthly_switches_to_unlimited_through_configuration(staff, db_session):
    """`null` в audits_per_period — законний безліміт, без жодної правки коду."""
    await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        entitlements={"audits_per_period": None, "presence_per_period": 5},
    ))
    org = await _org_of(db_session)
    await _subscribe_to_pro(db_session, org)
    ent = await billing_service.for_organization(db_session, organization_id=org)
    assert ent.limit("audits_per_period") is None

    account = (await staff.get("/v1/account")).json()
    assert account["usage"]["audits_limit"] is None, "клієнт бачить безліміт"
    assert account["usage"]["audits_remaining"] is None


async def test_presence_quantity_is_independent_and_never_unlimited(staff, db_session):
    saved = await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        entitlements={"audits_per_period": 100, "presence_per_period": 25},
    ))
    assert saved.json()["entitlements"] == {
        "audits_per_period": 100, "presence_per_period": 25,
    }

    unlimited = await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        entitlements={"audits_per_period": 100, "presence_per_period": None},
    ))
    assert unlimited.status_code == 422, "безлімітної присутності не існує"
    assert "presence_per_period" in json.dumps(unlimited.json())


async def test_hidden_plan_leaves_the_public_catalog(staff, db_session):
    await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(is_public=False))
    codes = [p["code"] for p in (await staff.get("/v1/plans")).json()["plans"]]
    assert "pro" not in codes

    await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(is_public=True))
    codes = [p["code"] for p in (await staff.get("/v1/plans")).json()["plans"]]
    assert "pro" in codes


async def test_the_body_cannot_choose_the_provider_price(staff, db_session):
    """Провайдера й прайс пише публікація: що б не стояло в тілі, запис
    отримує чинного провайдера каси й опублікований у нього прайс."""
    response = await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        prices=[{
            "provider": "paddle", "provider_price_id": "price_12345",
            "currency": "USD", "interval": "month",
            "display_amount_minor": 4900,
        }],
    ))
    assert response.status_code == 200, response.text
    price = response.json()["prices"][0]
    assert price["provider"] == "fake"
    assert price["provider_price_id"] == PRO_FAKE_PRICE

    response = await staff.put("/v1/admin/commerce/offers/cfg-shape", json={
        "code": "cfg-shape", "offer_type": "pack", "display_name": "Pack",
        "provider": "paddle", "provider_price_ref": "not-a-price",
        "display_amount_minor": 2900, "audit_credits": 5,
    })
    assert response.status_code == 200, response.text
    assert response.json()["provider"] == "fake"
    assert response.json()["provider_price_ref"] == "fake_cfg-shape"


# ── PACK: живий каталог і незмінна історія ───────────────────────────


async def _seed_pack(staff, *, credits: int, code: str = "cfg-pack") -> None:
    saved = await staff.put(f"/v1/admin/commerce/offers/{code}", json={
        "code": code, "offer_type": "pack", "display_name": "Pack",
        "provider": "fake", "provider_price_ref": f"fake_{code}",
        "display_amount_minor": 2900, "audit_credits": credits,
    })
    assert saved.status_code == 200, saved.text


async def test_pack_quantity_changes_reach_new_buyers_immediately(staff, db_session):
    await _seed_pack(staff, credits=10)
    first = (await staff.get("/v1/offers")).json()
    assert next(o for o in first if o["code"] == "cfg-pack")["audit_credits"] == 10

    await _seed_pack(staff, credits=20)
    second = (await staff.get("/v1/offers")).json()
    assert next(o for o in second if o["code"] == "cfg-pack")["audit_credits"] == 20


async def test_the_offer_api_carries_everything_the_page_renders(staff, db_session):
    """Жодної константи на клієнті: сума, валюта, ПОКАЗНИК валюти,
    кількості — все з відповіді."""
    await _seed_pack(staff, credits=10)
    offer = next(
        o for o in (await staff.get("/v1/offers")).json()
        if o["code"] == "cfg-pack"
    )
    assert offer["display_amount_minor"] == 2900
    assert offer["currency"] == "USD"
    assert offer["exponent"] == 2, "клієнт не має вгадувати ділення на сто"
    assert offer["audit_credits"] == 10


async def _pay(client, purchase_id: str, provider_ref: str) -> None:
    delivered = await client.post(
        "/v1/webhooks/fake",
        content=json.dumps({
            "external_event_id": f"evt-{uuid.uuid4().hex[:8]}",
            "kind": BillingEventKind.ONE_OFF_PURCHASED.value,
            "occurred_at": datetime.now(UTC).isoformat(),
            "quantity": 1, "currency": "USD", "amount_minor": 2900,
            "payload": {"purchase_ref": purchase_id,
                        "provider_transaction_id": provider_ref},
        }).encode(),
        headers={"x-fake-signature": "valid",
                 "content-type": "application/json"},
    )
    assert delivered.status_code == 200, delivered.text


async def test_a_paid_purchase_keeps_its_snapshot_after_catalog_edits(staff, db_session):
    """Куплені 10 лишаються десятьма, хай пакет тепер двадцять."""
    await _seed_pack(staff, credits=10)
    opened = (await staff.post("/v1/offers/checkout",
                               json={"offer_code": "cfg-pack"})).json()
    await _pay(staff, opened["purchase_id"], opened["provider_ref"])

    await _seed_pack(staff, credits=20)

    purchase = await db_session.get(OneOffPurchase, uuid.UUID(opened["purchase_id"]))
    assert purchase.offer_snapshot["audit_credits"] == 10
    granted = (await db_session.execute(
        select(AuditCredit).where(AuditCredit.purchase_id == purchase.id)
    )).scalars().all()
    assert len(granted) == 10, "історія не переписується услід за каталогом"


async def test_a_pending_checkout_grants_what_the_buyer_saw(staff, db_session):
    """Каса відкрита на 10, каталог змінено на 20 ДО оплати — видача 10:
    людина платила за екран, який бачила."""
    await _seed_pack(staff, credits=10, code="cfg-race")
    opened = (await staff.post("/v1/offers/checkout",
                               json={"offer_code": "cfg-race"})).json()
    await _seed_pack(staff, credits=20, code="cfg-race")
    await _pay(staff, opened["purchase_id"], opened["provider_ref"])

    granted = (await db_session.execute(
        select(AuditCredit).where(
            AuditCredit.purchase_id == uuid.UUID(opened["purchase_id"])
        )
    )).scalars().all()
    assert len(granted) == 10


async def test_checkout_records_the_exact_price_reference_it_used(staff, db_session):
    """Показане й проданe звʼязує зліпок: який прайс пішов у касу —
    записано в покупці, і звірити його з каталогом можна завжди."""
    await _seed_pack(staff, credits=10, code="cfg-price")
    opened = (await staff.post("/v1/offers/checkout",
                               json={"offer_code": "cfg-price"})).json()
    purchase = await db_session.get(OneOffPurchase, uuid.UUID(opened["purchase_id"]))
    assert purchase.offer_snapshot["provider_price_ref"] == "fake_cfg-price"
    assert purchase.offer_snapshot["display_amount_minor"] == 2900


# ── MONTHLY: наділ періоду знімковано ────────────────────────────────


async def test_plan_edits_do_not_rewrite_the_active_period(staff, db_session):
    await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        entitlements={"audits_per_period": 3, "presence_per_period": 2},
    ))
    org = await _org_of(db_session)
    await _subscribe_to_pro(db_session, org)

    # Посеред періоду адміністратор урізає тариф. Виданого це не чіпає.
    await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        entitlements={"audits_per_period": 1, "presence_per_period": 1},
    ))
    ent = await billing_service.for_organization(db_session, organization_id=org)
    assert ent.limit("audits_per_period") == 3, "наділ періоду вже виданий"
    assert ent.limit("presence_per_period") == 2

    subscription = (await db_session.execute(
        select(Subscription).where(Subscription.organization_id == org)
    )).scalars().one()
    period = billing_quota.period_for(subscription)
    for _ in range(3):
        decision = await billing_quota.consume(
            db_session, organization_id=org, period=period, limit=ent.limit("audits_per_period"))
        assert decision.allowed
    fourth = await billing_quota.consume(
        db_session, organization_id=org, period=period, limit=ent.limit("audits_per_period"))
    assert not fourth.allowed, "і рахується він за старим лімітом"


async def test_the_next_period_takes_the_new_configuration(staff, db_session):
    await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        entitlements={"audits_per_period": 3, "presence_per_period": 2},
    ))
    org = await _org_of(db_session)
    fake = await _subscribe_to_pro(db_session, org)
    started_ref = (await db_session.execute(
        select(Subscription.provider_subscription_id)
        .where(Subscription.organization_id == org)
    )).scalar_one()

    await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        entitlements={"audits_per_period": 1, "presence_per_period": 1},
    ))
    from datetime import timedelta
    renewal = await pipeline.ingest(
        db_session, fake.renew(started_ref, at=datetime.now(UTC) + timedelta(seconds=1))
    )
    assert renewal.outcome == "processed", renewal.error

    ent = await billing_service.for_organization(db_session, organization_id=org)
    assert ent.limit("audits_per_period") == 1, "новий період — нові умови"
    assert ent.limit("presence_per_period") == 1


async def test_account_usage_names_the_limited_mode(staff, db_session):
    await staff.put("/v1/admin/commerce/plans/pro", json=_plan_payload(
        entitlements={"audits_per_period": 5, "presence_per_period": 2},
    ))
    org = await _org_of(db_session)
    await _subscribe_to_pro(db_session, org)
    usage = (await staff.get("/v1/account")).json()["usage"]
    assert usage["audits_limit"] == 5
    assert usage["audits_remaining"] == 5
    assert usage["presence_limit"] == 2
    assert usage["presence_remaining"] == 2


# ── портал платежів ──────────────────────────────────────────────────


async def test_portal_session_is_created_by_post_and_not_stored(staff, db_session):
    """Свіжа сесія — дія, тож POST; посилання ніде не осідає, і GET
    старої адреси більше не існує."""
    org = await _org_of(db_session)
    db_session.add(BillingCustomer(
        organization_id=org, provider="fake",
        provider_customer_id="ctm_cfg_01",
    ))
    await db_session.commit()

    created = await staff.post("/v1/account/portal-session")
    assert created.status_code == 201, created.text
    assert created.json()["url"].startswith("https://fake.portal/")

    again = await staff.post("/v1/account/portal-session")
    assert again.status_code == 201, "кожен виклик — нова сесія провайдера"

    legacy = await staff.get("/v1/account/portal")
    assert legacy.status_code in (404, 405), "старої GET-адреси немає"


async def test_portal_without_a_billing_profile_is_an_honest_404(staff, db_session):
    response = await staff.post("/v1/account/portal-session")
    assert response.status_code == 404


async def test_public_catalog_never_advertises_scheduled_audits(staff, db_session):
    """Запланованих аудитів немає в затвердженому першому випуску:
    навіть коли право `scheduled_audits` сконфігуроване в тарифі,
    публічний каталог (він же сторінка цін усіма шістьма мовами) не
    рекламує його рядком ліміту. Право при цьому лишається у відповіді
    адмінки — вітрина і механіка розділені."""
    payload = _plan_payload()
    payload["entitlements"]["scheduled_audits"] = 5
    await staff.put("/v1/admin/commerce/plans/pro", json=payload)

    for lang in ("en", "de", "es", "fr", "ru", "uk"):
        plans = (await staff.get(f"/v1/plans?lang={lang}")).json()["plans"]
        pro = next(p for p in plans if p["code"] == "pro")
        keys = [line["label_key"] for line in pro["limits"]]
        assert "plan.limit.schedules" not in keys, lang


# ── клієнтський текст шістьма мовами ─────────────────────────────────

SIX_NAMES = {
    "en": "Pack of 10", "uk": "Пакет із 10", "de": "Zehnerpaket",
    "es": "Paquete de 10", "fr": "Pack de 10", "ru": "Пакет из 10",
}


async def _seed_localized_pack(staff, *, code: str = "cfg-i18n",
                               active: bool = True,
                               names: dict | None = None) -> object:
    return await staff.put(f"/v1/admin/commerce/offers/{code}", json={
        "code": code, "offer_type": "pack", "display_name": "Pack of 10",
        "active": active,
        "provider": "fake", "provider_price_ref": f"fake_{code}",
        "display_amount_minor": 2900, "audit_credits": 10,
        "display_name_i18n": SIX_NAMES if names is None else names,
    })


async def test_offers_serve_the_locale_the_visitor_asked_for(staff, db_session):
    """Кожна мова отримує СВОЮ сконфігуровану назву; німецька ніколи не
    бачить українську, коли німецька існує."""
    saved = await _seed_localized_pack(staff)
    assert saved.status_code == 200, saved.text

    for lang, expected in SIX_NAMES.items():
        listing = (await staff.get(f"/v1/offers?lang={lang}")).json()
        row = next(o for o in listing if o["code"] == "cfg-i18n")
        assert row["display_name"] == expected, lang

    german = (await staff.get("/v1/offers?lang=de")).json()
    row = next(o for o in german if o["code"] == "cfg-i18n")
    assert row["display_name"] != SIX_NAMES["uk"]

    # Accept-Language працює так само, як на /v1/plans: відвідувач без
    # акаунта має мову браузера — і лише її.
    header = (await staff.get(
        "/v1/offers", headers={"accept-language": "fr-FR,fr;q=0.9"},
    )).json()
    row = next(o for o in header if o["code"] == "cfg-i18n")
    assert row["display_name"] == SIX_NAMES["fr"]


async def test_legacy_offer_without_i18n_keeps_its_universal_name(staff, db_session):
    """Порожня мапа — явний вибір універсальної назви: старий запис
    показує display_name всіма мовами, і жодних вигаданих перекладів."""
    await _seed_pack(staff, credits=5, code="cfg-legacy")
    for lang in ("en", "de", "uk", "ru"):
        listing = (await staff.get(f"/v1/offers?lang={lang}")).json()
        row = next(o for o in listing if o["code"] == "cfg-legacy")
        assert row["display_name"] == "Pack"


async def test_active_offer_with_partial_i18n_is_refused(staff, db_session):
    """Часткова локалізація активної пропозиції — це майбутній мовчазний
    фолбек на чужу мову. Вона не зберігається, і помилка називає мови."""
    partial = await _seed_localized_pack(
        staff, code="cfg-part", names={"de": "Zehnerpaket"})
    assert partial.status_code == 422
    for missing in ("en", "es", "fr", "ru", "uk"):
        assert missing in partial.json()["detail"]

    # Чернетка (неактивна) заповнюється поступово — це дозволено.
    draft = await _seed_localized_pack(
        staff, code="cfg-draft", active=False, names={"de": "Zehnerpaket"})
    assert draft.status_code == 200, draft.text


async def test_admin_listing_exposes_the_localization_maps(staff, db_session):
    await _seed_localized_pack(staff, code="cfg-vis")
    rows = (await staff.get("/v1/admin/commerce/offers")).json()
    row = next(o for o in rows if o["code"] == "cfg-vis")
    assert row["display_name_i18n"] == SIX_NAMES
    assert row["description_i18n"] == {}


async def test_localized_text_never_touches_numbers_or_the_price_ref(staff, db_session):
    """Локалізується лише напис: суми, кількості, порядок і прайс
    провайдера — одне джерело правди для всіх мов, і каса відкривається
    тим самим посиланням."""
    await _seed_localized_pack(staff)
    seen = {}
    for lang in ("de", "uk"):
        listing = (await staff.get(f"/v1/offers?lang={lang}")).json()
        seen[lang] = next(o for o in listing if o["code"] == "cfg-i18n")
    for field in ("display_amount_minor", "currency", "audit_credits",
                  "presence_credits", "promo_eligible", "exponent"):
        assert seen["de"][field] == seen["uk"][field], field

    opened = (await staff.post("/v1/offers/checkout",
                               json={"offer_code": "cfg-i18n"})).json()
    purchase = await db_session.get(
        OneOffPurchase, uuid.UUID(opened["purchase_id"]))
    assert purchase.offer_snapshot["provider_price_ref"] == "fake_cfg-i18n", (
        "каса йде тим самим прайс-посиланням незалежно від мови вітрини")


async def test_i18n_edits_do_not_rewrite_purchase_snapshots(staff, db_session):
    """Переклад назви — не зміна купленого: зліпок покупки, видані
    одиниці й посилання провайдера лишаються, як у момент оплати."""
    await _seed_pack(staff, credits=10, code="cfg-snap")
    opened = (await staff.post("/v1/offers/checkout",
                               json={"offer_code": "cfg-snap"})).json()
    await _pay(staff, opened["purchase_id"], opened["provider_ref"])

    renamed = await staff.put("/v1/admin/commerce/offers/cfg-snap", json={
        "code": "cfg-snap", "offer_type": "pack",
        "display_name": "Pack (renamed)",
        "provider": "fake", "provider_price_ref": "fake_cfg-snap",
        "display_amount_minor": 2900, "audit_credits": 10,
        "display_name_i18n": SIX_NAMES,
    })
    assert renamed.status_code == 200, renamed.text

    purchase = await db_session.get(
        OneOffPurchase, uuid.UUID(opened["purchase_id"]))
    # Зліпок фіксує УМОВИ покупки — код, прайс-посилання, кількості —
    # і жодне редагування назв (та й будь-що в каталозі) їх не рухає.
    assert purchase.offer_snapshot["offer_code"] == "cfg-snap"
    assert purchase.offer_snapshot["provider_price_ref"] == "fake_cfg-snap"
    assert purchase.offer_snapshot["audit_credits"] == 10
    granted = (await db_session.execute(
        select(AuditCredit).where(AuditCredit.purchase_id == purchase.id)
    )).scalars().all()
    assert len(granted) == 10


async def test_public_plan_names_resolve_per_locale_and_partial_is_refused(
    staff, db_session,
):
    payload = _plan_payload()
    payload["name_i18n"] = {
        "en": "Pro", "uk": "Про", "de": "Pro-Tarif",
        "es": "Plan Pro", "fr": "Formule Pro", "ru": "Про-тариф",
    }
    saved = await staff.put("/v1/admin/commerce/plans/pro", json=payload)
    assert saved.status_code == 200, saved.text

    for lang, expected in payload["name_i18n"].items():
        plans = (await staff.get(f"/v1/plans?lang={lang}")).json()["plans"]
        pro = next(p for p in plans if p["code"] == "pro")
        assert pro["name"] == expected, lang

    partial = _plan_payload()
    partial["name_i18n"] = {"de": "Pro-Tarif"}
    refused = await staff.put("/v1/admin/commerce/plans/pro", json=partial)
    assert refused.status_code == 422
    assert "uk" in refused.json()["detail"]

    # Прихований тариф — чернетка: часткова мапа дозволена.
    hidden = _plan_payload(is_public=False)
    hidden["name_i18n"] = {"de": "Pro-Tarif"}
    ok = await staff.put("/v1/admin/commerce/plans/pro", json=hidden)
    assert ok.status_code == 200, ok.text


# ── структуровані величини картки цін і мова кабінету ────────────────


async def test_public_plan_carries_structured_purchase_values(staff, db_session):
    """Картка цін читає ЧИСЛА, а не рядки лімітів: скільки перевірок на
    місяць (або безліміт) і скільки перевірок Actual AI Presence
    включено. Джерело — ті самі entitlements, без другої копії."""
    limited = _plan_payload()
    limited["entitlements"]["audits_per_period"] = 50
    limited["entitlements"]["presence_per_period"] = 10
    await staff.put("/v1/admin/commerce/plans/pro", json=limited)
    plans = (await staff.get("/v1/plans?lang=en")).json()["plans"]
    pro = next(pl for pl in plans if pl["code"] == "pro")
    assert pro["analyses_per_month"] == 50
    assert pro["analyses_unlimited"] is False
    assert pro["presence_checks_per_month"] == 10

    unlimited = _plan_payload()
    unlimited["entitlements"]["audits_per_period"] = None
    unlimited["entitlements"]["presence_per_period"] = 10
    await staff.put("/v1/admin/commerce/plans/pro", json=unlimited)
    plans = (await staff.get("/v1/plans?lang=en")).json()["plans"]
    pro = next(pl for pl in plans if pl["code"] == "pro")
    assert pro["analyses_per_month"] is None
    assert pro["analyses_unlimited"] is True
    assert pro["presence_checks_per_month"] == 10


async def test_account_plan_name_follows_the_cabinet_locale(staff, db_session):
    """Англійський кабінет не бачить української назви тарифу: /v1/account
    розвʼязує name_i18n мовою кабінету, з дефолтним полем як фолбеком
    для універсальних назв."""
    from app.models.billing import Plan

    plan = (await db_session.execute(
        select(Plan).where(Plan.code == "free")
    )).scalar_one_or_none()
    if plan is None:
        plan = Plan(code="free", name="Безкоштовний")
        db_session.add(plan)
    plan.name = "Безкоштовний"
    plan.name_i18n = {"en": "Free", "uk": "Безкоштовний", "de": "Kostenlos",
                      "es": "Gratis", "fr": "Gratuit", "ru": "Бесплатный"}
    await db_session.commit()

    english = (await staff.get("/v1/account?lang=en")).json()
    assert english["plan"]["name"] == "Free"
    ukrainian = (await staff.get("/v1/account?lang=uk")).json()
    assert ukrainian["plan"]["name"] == "Безкоштовний"
