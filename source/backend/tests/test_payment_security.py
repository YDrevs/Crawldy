"""Межі, які тримають гроші й доступ. Аудит §25 у виконуваній формі.

Кожне твердження тут — те, що інакше довелося б перевіряти очима перед
кожним релізом. Очі це роблять один раз.

Файл навмисно читає **справжні файли проєкту**, а не імітує їх: питання
«чи не потрапив ключ у фронтенд» не має відповіді в моці.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.api.routes.public import CheckoutConfigOut, CheckoutOut, PaymentStateOut
from app.billing.providers import UnhandledEvent
from app.billing.providers.paddle import CUSTOM_PURCHASE_KEY, PaddleProvider
from app.core import logging as log_module
from app.core.config import Settings

BACKEND = Path(__file__).resolve().parents[1]
FRONTEND = BACKEND.parent / "frontend"

# Секрети, які не мають перетинати межу браузера ні в якому вигляді.
SERVER_ONLY_SETTINGS = ("paddle_api_key", "paddle_webhook_secret")


def _frontend_sources() -> list[Path]:
    if not FRONTEND.exists():  # pragma: no cover — фронтенд поруч завжди
        pytest.skip("фронтенд не поруч")
    return [
        path
        for path in FRONTEND.rglob("*.ts*")
        if "node_modules" not in path.parts and ".next" not in path.parts
    ]


# ── секрети не перетинають межу браузера ───────────────────────────────────


def test_the_api_key_and_webhook_secret_are_not_named_in_frontend_code() -> None:
    """Найдешевший спосіб віддати ключ браузеру — згадати його там.

    Перевіряється саме назва змінної: значення в код і не потрапляє, а
    от `process.env.PADDLE_API_KEY` у клієнтському компоненті Next
    вшиває значення у збірку мовчки.
    """
    forbidden = ("PADDLE_API_KEY", "PADDLE_WEBHOOK_SECRET")
    offenders = [
        f"{path.relative_to(FRONTEND)}: {name}"
        for path in _frontend_sources()
        for name in forbidden
        if name in path.read_text(encoding="utf-8", errors="replace")
    ]
    assert offenders == [], f"секрет названий у фронтенді: {offenders}"


def test_the_checkout_response_carries_no_server_only_secret() -> None:
    """Відповідь каси йде в браузер цілком, тож її поля — це межа."""
    fields = set(CheckoutOut.model_fields)
    assert "client_token" in fields, "публічний токен провайдера потрібен"
    for secret in ("api_key", "webhook_secret", "secret", "password"):
        assert not any(secret in field for field in fields), (
            f"поле з {secret!r} у відповіді каси"
        )


def test_the_public_checkout_config_carries_only_browser_safe_values() -> None:
    """Сторінка default payment link відкрита всім, тож її вхід — це межа.

    Клієнтський токен Paddle сам призначив для браузера; оточення видно
    з адрес, куди той браузер ходить. Ключ API і секрет вебхука тут
    означали б віддати їх кожному, хто відкриє сторінку оплати.
    """
    assert set(CheckoutConfigOut.model_fields) == {
        "provider",
        "environment",
        "client_token",
    }


def test_the_payment_state_response_says_nothing_about_money_it_should_not() -> None:
    """Стан оплати — чотири поля. Ані сум, ані реквізитів, ані посилань.

    `charged` — так/ні/невідомо про факт списання, без суми й без
    транзакції: екрану треба розвести «передумав» і «заплатив», а не
    показати рахунок.
    """
    assert set(PaymentStateOut.model_fields) == {
        "audit_id",
        "state",
        "unlocked",
        "charged",
    }


# ── секрети не потрапляють у логи ──────────────────────────────────────────


@pytest.mark.parametrize(
    "line",
    [
        "GET /transactions Authorization: Bearer pdl_sdbx_apikey_0123456789abcdef",
        "PaddleNotConfigured: ключ pdl_live_apikey_0123456789abcdef не підійшов",
        "webhook secret pdl_ntfset_0123456789abcdef rejected",
        "https://api.example.com/v5/runPagespeed?key=AIzaSyTOTALLYSECRET",
    ],
)
def test_a_secret_shaped_string_never_survives_the_log_filter(line: str) -> None:
    cleaned = log_module.redact(line)
    for fragment in ("pdl_sdbx_", "pdl_live_", "pdl_ntfset_", "AIzaSyTOTALLYSECRET"):
        assert fragment not in cleaned or cleaned.endswith("***"), cleaned
    assert "***" in cleaned


def test_redaction_does_not_eat_ordinary_text() -> None:
    """Сітка, що ловить усе, робить логи марними."""
    line = "purchase 3f1b7c9a-0000-4000-8000-000000000001 became paid"
    assert log_module.redact(line) == line


# ── ідентифікатори не є повноваженням ──────────────────────────────────────


def test_the_provider_learns_our_purchase_id_and_nothing_else() -> None:
    """Мінімум довільних даних: один ключ, і той непрозорий.

    Усе, що ми віддамо провайдеру, повернеться до нас із чужого боку —
    тож обсяг відданого дорівнює обсягу того, що можна підробити.
    """
    assert CUSTOM_PURCHASE_KEY == "crawldy_purchase_id"


def test_the_domain_never_learns_a_price_identifier_from_code() -> None:
    """Прайс живе в конфігурації. `pri_…` у коді — це зміна ціни релізом."""
    sources = [
        path
        for path in (BACKEND / "app").rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    hardcoded = [
        str(path.relative_to(BACKEND))
        for path in sources
        if re.search(r"\bpri_[a-z0-9]{6,}", path.read_text(encoding="utf-8"))
    ]
    assert hardcoded == [], f"ідентифікатор прайсу в коді: {hardcoded}"



# ── оточення неможливо переплутати ─────────────────────────────────────────


def test_production_is_not_the_default_anywhere() -> None:
    """Пісочниця за замовчуванням: помилка конфігурації має коштувати нуль."""
    defaults = Settings.model_fields
    assert defaults["paddle_env"].default == "sandbox"
    assert defaults["paddle_api_key"].default is None
    assert defaults["paddle_webhook_secret"].default is None


def test_the_fake_provider_exists_only_locally() -> None:
    """Фейк приймає будь-який вебхук із заголовком `x-fake-signature`.

    Поза локальним стендом це не тестовий інструмент, а спосіб отримати
    платний звіт одним curl — і staging тут не виняток: він доступний
    ззовні. Гейт у реєстрі, і перевіряється він читанням реєстру, а не
    довірою до коментаря.
    """
    source = (BACKEND / "app/billing/registry.py").read_text(encoding="utf-8")
    assert '_FAKE_ALLOWED = settings.app_env == "local"' in source
    assert "if _FAKE_ALLOWED:\n    _PROVIDERS[FAKE_NAME] = _FAKE" in source.replace("\r\n", "\n")
    assert "if _FAKE_ALLOWED:\n    _PUBLISHERS[FAKE_NAME] = _FAKE_PRICES" in source.replace(
        "\r\n", "\n"
    )


# ── подія без підпису не існує ─────────────────────────────────────────────


def test_a_webhook_without_a_configured_secret_accepts_nothing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Поки секрета немає, ендпойнт закритий — а не «поки що відкритий»."""
    from app.billing.providers import InvalidWebhook
    from app.core.config import settings

    monkeypatch.setattr(settings, "paddle_webhook_secret", None)
    with pytest.raises(InvalidWebhook):
        PaddleProvider().verify_webhook(
            headers={"paddle-signature": "ts=1;h1=00"}, body=b"{}"
        )


def test_ignoring_an_event_and_rejecting_it_are_different_answers() -> None:
    """Різні коди відповіді, тож і різні типи. Один тип дав би одну дію."""
    from app.billing.providers import InvalidWebhook

    assert not issubclass(UnhandledEvent, InvalidWebhook)
    assert not issubclass(InvalidWebhook, UnhandledEvent)


def test_reopening_your_own_checkout_is_not_rate_limited_like_new_work() -> None:
    """Повторне відкриття власної каси нічого не створює.

    Десятка на годину — норма для дій, що додають роботи: новий аудит,
    нова гостьова сесія. Для «відкрити ту саму касу» вона означала б, що
    людина, яка закрила вікно оплати кілька разів, не може заплатити ще
    годину. Скільки КАС узагалі заведе одна адреса, обмежує ліміт на
    відкриття сесії — без нової організації нової каси не буде.
    """
    from app.api.routes.public import _limit_for
    from app.core.config import settings

    assert _limit_for("/v1/public/orders") == settings.checkout_rate_limit
    assert settings.checkout_rate_limit > settings.public_rate_limit
    # Решта публічних дій лишається на спільній нормі.
    for path in ("/v1/public/sessions", "/v1/public/audits",
                 "/v1/public/orders/abc/audit"):
        assert _limit_for(path) == settings.public_rate_limit
