"""Секрети не мають потрапляти в логи.

PSI приймає ключ лише в query-рядку, а httpx на INFO пише повний URL —
без цього запобіжника ключ лягає у stdout воркера відкритим текстом.
"""

from __future__ import annotations

import logging

import pytest

from app.core.logging import RedactSecrets, _redact_event, redact

PSI_URL = (
    "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    "?url=https%3A%2F%2Fexample.com&strategy=mobile&key=AIzaSyABCDEF1234567890"
)


def test_psi_key_is_removed_from_a_url():
    cleaned = redact(PSI_URL)

    assert "AIzaSyABCDEF1234567890" not in cleaned
    assert "key=***" in cleaned
    assert "strategy=mobile" in cleaned, "решта параметрів має лишитися читабельною"


@pytest.mark.parametrize(
    "param", ["key", "api_key", "apikey", "access_token", "token", "password", "secret"]
)
def test_every_known_secret_parameter_is_covered(param: str):
    assert "s3cret" not in redact(f"https://x/y?{param}=s3cret&a=1")


def test_redaction_is_case_insensitive():
    assert "s3cret" not in redact("https://x/y?KEY=s3cret")


def test_urls_without_secrets_are_untouched():
    url = "https://example.com/page?utm_source=news&page=2"
    assert redact(url) == url


def test_filter_rewrites_the_record_that_httpx_emits():
    record = logging.LogRecord(
        name="httpx",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg='HTTP Request: GET %s "HTTP/1.1 200 OK"',
        args=(PSI_URL,),
        exc_info=None,
    )
    RedactSecrets().filter(record)

    assert "AIzaSyABCDEF1234567890" not in record.getMessage()
    assert "key=***" in record.getMessage()


def test_structlog_event_values_are_redacted_too():
    event = _redact_event(None, "info", {"url": PSI_URL, "status": 200})

    assert "AIzaSyABCDEF1234567890" not in event["url"]
    assert event["status"] == 200, "нерядкові поля не чіпаємо"


def test_a_reset_token_never_reaches_an_access_log(monkeypatch):
    """Журнал доступу uvicorn — окремий логер, і він пише повний запит.

    Перевірка посилання відновлення — це `GET …/password/reset?token=…`,
    тож у журнал доступу йшов ключ від акаунта відкритим текстом. Фільтр
    для цього існував, але вішався лише на обробники КОРЕНЕВОГО логера,
    а `uvicorn.access` має власний обробник і `propagate = False`: його
    записи до кореня не доходять ніколи.

    Тест відтворює саме цю конфігурацію, бо загальна перевірка фільтра
    її не бачить — фільтр як такий працював правильно, не працювало
    його встановлення.
    """
    import io

    from app.core.logging import _install_redaction

    captured = io.StringIO()
    access = logging.getLogger("uvicorn.access")
    monkeypatch.setattr(access, "handlers", [logging.StreamHandler(captured)])
    monkeypatch.setattr(access, "propagate", False)
    monkeypatch.setattr(access, "filters", [])
    access.setLevel(logging.INFO)

    _install_redaction()
    access.info(
        '127.0.0.1 - "GET /v1/auth/password/reset?token=SECRET-RESET-TOKEN HTTP/1.1" 204'
    )

    written = captured.getvalue()
    assert "SECRET-RESET-TOKEN" not in written, "токен відновлення потрапив у журнал доступу"
    assert "token=***" in written
