"""Безкоштовне превʼю — необмежене, і це рішення продукту.

Рішення власника 2026-09-03: превʼю (обмежений результат) може
запускати будь-хто скільки завгодно — і гість, і зареєстрований без
покупки. Безкоштовних ПОВНИХ аудитів при цьому не існує: наділ
безкоштовного стану — нуль, а «1 of 1 audits» був хибним правилом.
Від зловживання боронить технічний ліміт частоти — окремий від
комерційних прав шар зі своєю відповіддю «забагато запитів».
"""

from __future__ import annotations

import uuid

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.run_enums import QuotaSource, QuotaState
from app.models.audit import Audit
from app.models.presence import PresenceRun
from app.models.purchase import AuditCredit
from app.models.usage import Usage

pytestmark = pytest.mark.asyncio


async def _open(client: httpx.AsyncClient) -> str:
    response = await client.post("/v1/public/sessions")
    assert response.status_code == 201, response.text
    return str(response.json()["token"])


def _auth(token: str) -> dict[str, str]:
    return {"X-Guest-Token": token}


async def _preview(client: httpx.AsyncClient, token: str, url: str) -> str:
    response = await client.post(
        "/v1/public/audits", json={"url": url}, headers=_auth(token)
    )
    assert response.status_code == 202, response.text
    return str(response.json()["audit_id"])


async def test_one_session_runs_many_previews(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Та сама анонімна сесія — кілька превʼю поспіль, різні адреси.

    Жодного «квоту вичерпано»: механізм «один безкоштовний аудит на
    сесію» прибраний, а не перекладений.
    """
    token = await _open(client)
    first = await _preview(client, token, "https://one.example/")
    second = await _preview(client, token, "https://two.example/")
    third = await _preview(client, token, "https://three.example/")

    assert len({first, second, third}) == 3


async def test_a_preview_touches_no_commercial_counters(
    client: httpx.AsyncClient, db_session: AsyncSession
) -> None:
    """Превʼю не списує ані квоти періоду, ані куплених одиниць.

    І не викликає провайдерів присутності: Actual AI Presence живе лише
    за явним платним запуском, превʼю його не торкається.
    """
    token = await _open(client)
    audit_id = await _preview(client, token, "https://example.com/")

    audit = await db_session.get(Audit, uuid.UUID(audit_id))
    assert audit is not None
    assert audit.quota_source is QuotaSource.FREE_PREVIEW
    # Резерву не було — і повертати нічого: доля закрита одразу.
    assert audit.quota_state is QuotaState.CONSUMED

    used = await db_session.scalar(
        select(func.coalesce(func.sum(Usage.used), 0)).where(
            Usage.organization_id == audit.organization_id
        )
    )
    assert used == 0, "лічильник періоду не рухався"

    credits = await db_session.scalar(
        select(func.count()).select_from(AuditCredit).where(
            AuditCredit.organization_id == audit.organization_id
        )
    )
    assert credits == 0, "куплених одиниць не існує і не зʼявилось"

    presence = await db_session.scalar(
        select(func.count()).select_from(PresenceRun).where(
            PresenceRun.organization_id == audit.organization_id
        )
    )
    assert presence == 0, "превʼю не робить жодного виклику присутності"


async def test_a_signed_in_visitor_previews_too(
    client: httpx.AsyncClient,
) -> None:
    """Зареєстрований без покупки так само запускає превʼю без ліміту.

    Вхід в акаунт не забирає безкоштовного шляху: гостьова спроможність
    живе поруч із сесією кабінету й на неї не зважає.
    """
    register = await client.post(
        "/v1/auth/register",
        json={"email": "previews@example.com", "password": "a-long-password-1"},
    )
    assert register.status_code in (200, 201), register.text

    token = await _open(client)
    first = await _preview(client, token, "https://one.example/")
    second = await _preview(client, token, "https://two.example/")
    assert first != second


async def test_an_unpaid_account_has_zero_full_audits(
    client: httpx.AsyncClient,
) -> None:
    """Безкоштовний стан акаунта не дарує повного аудиту.

    Перший же запуск із кабінету — 402: повний звіт існує лише купленим.
    Превʼю лишається доступним окремим шляхом (тест вище).
    """
    register = await client.post(
        "/v1/auth/register",
        json={"email": "unpaid@example.com", "password": "a-long-password-1"},
    )
    assert register.status_code in (200, 201), register.text

    response = await client.post("/v1/audits", json={"url": "https://example.com"})
    assert response.status_code == 402
    assert response.json()["detail"]["limit"] == 0

    account = await client.get("/v1/account")
    usage = account.json()["usage"]
    assert usage["audits_limit"] == 0, "жодного вигаданого «1 of 1»"
    assert usage["audits_used"] == 0


async def test_the_rate_limit_speaks_traffic_not_commerce(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Технічний ліміт відповідає «забагато запитів», не «квоту вичерпано».

    Межа зловживання — властивість маршруту, а не прав: у відповіді
    немає ані quota, ані запрошення створити акаунт.
    """
    monkeypatch.setattr("app.api.routes.public.settings.public_rate_limit", 1)

    first = await client.post("/v1/public/sessions")
    second = await client.post("/v1/public/sessions")
    assert first.status_code == 201
    assert second.status_code == 429
    detail = str(second.json()["detail"])
    assert "quota" not in detail
    assert second.headers["Retry-After"]
