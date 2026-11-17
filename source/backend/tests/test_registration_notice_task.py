"""Задача сповіщення: лист лише справжньому активному власнику, його мовою."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.audit.i18n import Locale
from app.identity.enums import UserStatus
from app.mail.registration_notice import LOCALES, registration_attempt_letter
from app.worker import registration_notice_task as task


class _Session:
    async def __aenter__(self) -> _Session:
        return self

    async def __aexit__(self, *_: object) -> None:
        return None


def _patch(monkeypatch: pytest.MonkeyPatch, user: Any) -> list[Any]:
    sent: list[Any] = []

    async def find(_session: object, _email: str) -> Any:
        return user

    async def deliver(message: Any) -> str:
        sent.append(message)
        return "sent"

    monkeypatch.setattr(task, "SessionLocal", _Session)
    monkeypatch.setattr(task.service, "find_user_by_email", find)
    monkeypatch.setattr(task, "_deliver", deliver)
    return sent


async def test_unknown_address_gets_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _patch(monkeypatch, None)
    assert (await task.send_registration_notice_task({}, "x@example.com"))["status"] == "no_account"
    assert sent == []


async def test_disabled_account_gets_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _patch(monkeypatch, SimpleNamespace(status=UserStatus.DISABLED, locale="uk"))
    assert (await task.send_registration_notice_task({}, "x@example.com"))["status"] == "no_account"
    assert sent == []


async def test_owner_gets_a_letter_in_their_language(monkeypatch: pytest.MonkeyPatch) -> None:
    sent = _patch(monkeypatch, SimpleNamespace(status=UserStatus.ACTIVE, locale="uk"))
    assert (await task.send_registration_notice_task({}, "x@example.com"))["status"] == "sent"
    (message,) = sent
    assert message.to == "x@example.com"
    assert "Crawldy" in message.subject
    assert "/login?lang=uk" in message.text
    assert "/forgot?lang=uk" in message.text


@pytest.mark.parametrize("locale", LOCALES)
def test_every_language_renders(locale: Locale) -> None:
    letter = registration_attempt_letter(locale=locale, login="https://l", reset="https://r")
    assert "https://l" in letter.text and "https://r" in letter.text
    assert "{" not in letter.text
