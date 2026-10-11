"""Публічний каталог тарифів: що бачить той, хто ще не клієнт.

Головна перевірка тут — негативна: внутрішні ключі прав не мають ставати
контрактом маркетингової сторінки. Інакше перейменування ліміту в коді
ставало б зміною публічної сторінки, а сторінка диктувала б, як звати
поля в перевірках.

Тарифи тести сіють самі. Раніше вони спиралися на вітринні рівні
dev-сіда (free/starter/pro/agency), але міграція 0045 зняла ті рівні з
публічного каталогу: продукт продає кількість того самого аналізу, а не
рівні з відібраними можливостями. Порожній публічний каталог — законний
стан, і жоден тест більше не вимагає, щоб міграція щось вітринила.
"""

from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy import select

from app.billing.entitlements import KEYS
from app.models.billing import Plan, PlanPrice

# Права типового місячного тарифу — того самого класу, що продуктовий
# Monthly: кількість аналізів, обсяг сторінок, включені перевірки
# присутності. Без вітринних булевих можливостей — вони належали рівням.
_MONTHLY_ENTITLEMENTS: dict[str, Any] = {
    "audits_per_period": 10,
    "max_pages_per_audit": 50,
    "sites_limit": 3,
    "history_retention_days": 180,
    "presence_per_period": 2,
}


async def _seed_public_plan(
    db_session: Any,
    *,
    code: str,
    entitlements: dict[str, Any] | None = None,
) -> Plan:
    plan = Plan(
        code=code,
        name="Test Monthly",
        is_public=True,
        sort_order=50,
        entitlements=(
            dict(_MONTHLY_ENTITLEMENTS) if entitlements is None else entitlements
        ),
    )
    db_session.add(plan)
    await db_session.flush()
    return plan


@pytest.mark.asyncio
async def test_the_catalog_is_public(client, db_session):
    """Сторінка цін працює без входу — інакше вона не сторінка цін."""
    await _seed_public_plan(db_session, code="catalog-public")

    response = await client.get("/v1/plans")

    assert response.status_code == 200
    body = response.json()
    assert body["locale"] == "en"
    codes = {plan["code"] for plan in body["plans"]}
    assert "catalog-public" in codes


@pytest.mark.asyncio
async def test_legacy_tiers_stay_workable_but_hidden(client, db_session):
    """Рівні dev-сіда живі для резолвера прав і невидимі на вітрині.

    Це і є інваріант 0045: `free` лишається дефолтним тарифом нових
    організацій, але жоден із чотирьох рівнів не продається сторінкою цін.
    """
    rows = (
        (
            await db_session.execute(
                select(Plan).where(Plan.code.in_(["free", "starter", "pro", "agency"]))
            )
        )
        .scalars()
        .all()
    )
    assert {plan.code for plan in rows} == {"free", "starter", "pro", "agency"}
    assert all(not plan.is_public for plan in rows)

    body = (await client.get("/v1/plans")).json()
    public_codes = {plan["code"] for plan in body["plans"]}
    assert public_codes.isdisjoint({"free", "starter", "pro", "agency"})


@pytest.mark.asyncio
async def test_internal_entitlement_keys_never_reach_the_page(client, db_session):
    """Ні ключів, ні сирих значень — лише людські рядки.

    Перевірка структурна, а не пошуком підрядка. Перша версія цього тесту
    шукала `key in str(body)` і «знайшла» витік: `public_reports`
    міститься всередині `plan.feature.public_reports`. Це та сама пастка,
    на якій проєкт уже наступав у HTML і в адресах, — підрядок бреше.
    """
    await _seed_public_plan(db_session, code="keys-never-leak")
    body = (await client.get("/v1/plans")).json()
    assert body["plans"], "каталог має що показати — інакше обхід порожній"

    leaked: list[str] = []

    def walk(node: object, where: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in KEYS:
                    leaked.append(f"{where}.{key}")
                walk(value, f"{where}.{key}")
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{where}[{index}]")
        elif isinstance(node, str) and node in KEYS:
            leaked.append(f"{where} = {node!r}")

    walk(body, "plans")
    assert not leaked, f"внутрішні ключі прав протекли на сторінку цін: {leaked}"


@pytest.mark.asyncio
async def test_limits_are_words_not_numbers_in_a_dict(client, db_session):
    await _seed_public_plan(db_session, code="limits-are-words")
    body = (await client.get("/v1/plans")).json()
    plan = next(p for p in body["plans"] if p["code"] == "limits-are-words")

    labels = [line["label"] for line in plan["limits"]]
    assert any("pages per audit" in label for label in labels)
    assert all(line["label_key"].startswith("plan.") for line in plan["limits"])


@pytest.mark.asyncio
async def test_unlimited_is_words_not_zero(client, db_session):
    """`None` у ліміті означає «без обмеження», а не нуль.

    Плутанина коштувала б в обидва боки: «0 аудитів» на найдорожчому
    тарифі або «необмежено» на безкоштовному.
    """
    await _seed_public_plan(
        db_session,
        code="unlimited-history",
        entitlements={**_MONTHLY_ENTITLEMENTS, "history_retention_days": None},
    )
    body = (await client.get("/v1/plans")).json()
    plan = next(p for p in body["plans"] if p["code"] == "unlimited-history")

    history = next(line for line in plan["limits"] if "history" in line["label_key"])
    assert history["label_key"] == "plan.limit.history_unlimited"
    assert "0" not in history["label"]


@pytest.mark.asyncio
async def test_the_catalog_speaks_the_requested_language(client, db_session):
    await _seed_public_plan(db_session, code="speaks-languages")
    ukrainian = (await client.get("/v1/plans", params={"lang": "uk"})).json()
    english = (await client.get("/v1/plans", params={"lang": "en"})).json()

    assert ukrainian["locale"] == "uk"
    uk_plan = next(p for p in ukrainian["plans"] if p["code"] == "speaks-languages")
    en_plan = next(p for p in english["plans"] if p["code"] == "speaks-languages")
    assert uk_plan["limits"][0]["label"] != en_plan["limits"][0]["label"]
    # Ключі однакові: перекладається текст, а не структура.
    assert [line["label_key"] for line in uk_plan["limits"]] == [
        line["label_key"] for line in en_plan["limits"]
    ]


@pytest.mark.asyncio
async def test_a_browser_language_is_honoured_only_here(client):
    """Єдиний маршрут, де Accept-Language щось означає.

    У відвідувача без акаунта налаштувань немає, і мова браузера — усе, що
    ми про нього знаємо. Тому, хто мову обрав, її не має перебивати
    браузер — і на решті маршрутів заголовок не читається.
    """
    body = (await client.get("/v1/plans", headers={"Accept-Language": "uk"})).json()
    assert body["locale"] == "uk"


@pytest.mark.asyncio
async def test_a_price_without_an_amount_asks_to_get_in_touch(client, db_session):
    """Порожня ціна — не нуль. Намалювати нуль означало б назвати
    платний тариф безкоштовним."""
    await _seed_public_plan(db_session, code="price-on-request")
    body = (await client.get("/v1/plans")).json()
    plan = next(p for p in body["plans"] if p["code"] == "price-on-request")

    assert plan["prices"] == [], "цін не заводили"
    assert plan["cta_key"] == "plan.cta.contact"


@pytest.mark.asyncio
async def test_a_priced_plan_offers_to_subscribe(client, db_session):
    plan = await _seed_public_plan(db_session, code="priced-monthly")
    db_session.add(
        PlanPrice(
            plan_id=plan.id, provider="fake", provider_price_id="pri_public",
            currency="USD", interval="month", display_amount_minor=4900,
        )
    )
    await db_session.flush()

    body = (await client.get("/v1/plans")).json()
    priced = next(p for p in body["plans"] if p["code"] == "priced-monthly")

    assert priced["prices"][0]["amount_minor"] == 4900
    assert priced["prices"][0]["currency"] == "USD"
    assert priced["prices"][0]["exponent"] == 2, "долар має два знаки"
    assert priced["cta_key"] == "plan.cta.subscribe"
    assert priced["available"] is True


@pytest.mark.asyncio
async def test_a_currency_without_decimals_says_so(client, db_session):
    """4900 єн — це 4900 єн, а не 49.

    Показник іде разом із сумою саме тому: без нього клієнт ділив би на
    сто, і найдорожчий тариф виглядав би найдешевшим.
    """
    plan = await _seed_public_plan(db_session, code="yen-monthly")
    db_session.add(
        PlanPrice(
            plan_id=plan.id, provider="fake", provider_price_id="pri_jpy",
            currency="JPY", interval="month", display_amount_minor=4900,
        )
    )
    await db_session.flush()

    body = (await client.get("/v1/plans")).json()
    yen = next(p for p in body["plans"] if p["code"] == "yen-monthly")

    assert yen["prices"][0]["amount_minor"] == 4900
    assert yen["prices"][0]["exponent"] == 0
