"""Вимкнений чи видалений користувач не продовжує діяти чинною сесією.

Вхід перевіряв `status.can_sign_in`, а `resolve_session` — лише сесію:
вимкнути людину означало заборонити їй НАСТУПНИЙ вхід, тоді як уже
видана cookie лишалась дійсною до свого терміну (тижні).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.identity.enums import UserStatus
from app.models.identity import User
from tests.integration.conftest import register


async def _user(db, email: str) -> User:
    db.expire_all()
    return (await db.scalars(select(User).where(User.email == email))).one()


@pytest.mark.asyncio
async def test_a_disabled_user_loses_the_session(client, db_session):
    await register(client, "who@example.com")
    assert (await client.get("/v1/auth/me")).status_code == 200

    user = await _user(db_session, "who@example.com")
    user.status = UserStatus.DISABLED
    await db_session.commit()

    assert (await client.get("/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_a_deleted_user_loses_the_session(client, db_session):
    await register(client, "gone@example.com")

    user = await _user(db_session, "gone@example.com")
    user.deleted_at = datetime.now(UTC)
    await db_session.commit()

    assert (await client.get("/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_an_active_user_keeps_the_session(client, db_session):
    await register(client, "fine@example.com")

    assert (await client.get("/v1/auth/me")).status_code == 200
