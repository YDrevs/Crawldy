"""Класифікація невдач краулу: чи є в нас доказ, чи ми до цілі не дійшли.

Модель підключена до покриття через `app/audit/coverage.py`. Тести тут
тримають саму таксономію; поведінку станів покриття стереже
`tests/test_coverage.py`.
"""

from __future__ import annotations

import pytest

from app.audit.failures import FailureKind, blocks_evidence, classify, status_of


@pytest.mark.parametrize(
    ("reason", "kind"),
    [
        # Сервер сказав про сам ресурс — доказ у нас є.
        ("HTTP 404", FailureKind.OBSERVED),
        ("HTTP 410", FailureKind.OBSERVED),
        # Нас не пустили або не змогли обслужити.
        ("HTTP 401", FailureKind.ACCESS),
        ("HTTP 403", FailureKind.ACCESS),
        ("HTTP 407", FailureKind.ACCESS),
        ("HTTP 408", FailureKind.ACCESS),
        ("HTTP 429", FailureKind.ACCESS),
        ("HTTP 500", FailureKind.ACCESS),
        ("HTTP 502", FailureKind.ACCESS),
        ("HTTP 503", FailureKind.ACCESS),
        ("HTTP 509", FailureKind.ACCESS),
        # Відповіді не було взагалі.
        ("DNS не резолвиться: example.com", FailureKind.ACCESS),
        ("ReadTimeout: timed out", FailureKind.ACCESS),
        ("ConnectTimeout: ", FailureKind.ACCESS),
        ("ConnectError: [Errno 111]", FailureKind.ACCESS),
        ("RemoteProtocolError: peer closed", FailureKind.ACCESS),
        ("TooManyRedirects: exceeded", FailureKind.ACCESS),
        # Наш власний артефакт черги.
        ("порожній URL", FailureKind.OUR_SIDE),
        ("URL без хоста", FailureKind.OUR_SIDE),
        ("схема 'ftp' не підтримується", FailureKind.OUR_SIDE),
        ("хост x резолвиться у приватний IP 10.0.0.1", FailureKind.OUR_SIDE),
        # Чесно невідоме.
        ("HTTP 400", FailureKind.AMBIGUOUS),
        ("HTTP 405", FailureKind.AMBIGUOUS),
        ("HTTP 409", FailureKind.AMBIGUOUS),
        ("HTTP 451", FailureKind.AMBIGUOUS),
        ("", FailureKind.AMBIGUOUS),
        ("щось геть нове", FailureKind.AMBIGUOUS),
    ],
)
def test_classification(reason: str, kind: FailureKind) -> None:
    assert classify(reason) is kind


def test_an_observed_404_is_not_a_failure_to_obtain_evidence() -> None:
    """Головне твердження модуля.

    scikit-learn.org: 11 сторінок прочитано без єдиної помилки доступу,
    14 посилань віддали 404. Це знахідка, і саме вона живить
    `seo.broken_links`. Рахувати її як «до сайту не достукатись»
    означало б тікати від оцінки тим успішніше, чим більше на сайті
    биті посилань.
    """
    assert not blocks_evidence("HTTP 404")
    assert not blocks_evidence("HTTP 410")
    assert blocks_evidence("HTTP 403")
    assert blocks_evidence("DNS не резолвиться: example.com")


def test_the_unknown_does_not_silently_become_a_failure() -> None:
    """Невідоме значення не має забирати в сайту бал.

    Мовчазне віднесення до `ACCESS` перетворювало б наш недогляд у
    твердження про сайт — та сама помилка, що й із 404.
    """
    assert not blocks_evidence("HTTP 400")
    assert not blocks_evidence("щось геть нове")


def test_our_own_queue_artefact_is_not_the_site_being_unreachable() -> None:
    """SSRF-гард і порожня адреса — наші рішення, а не властивість сайту."""
    assert not blocks_evidence("порожній URL")
    assert not blocks_evidence("хост x резолвиться у приватний IP 10.0.0.1")


def test_status_of_reads_only_the_response_form() -> None:
    assert status_of("HTTP 404") == 404
    assert status_of("ReadTimeout: timed out") is None
    assert status_of("DNS не резолвиться: x") is None


def test_summarize_counts_every_category() -> None:
    from app.audit.failures import summarize

    counts = summarize(["HTTP 404", "HTTP 404", "HTTP 403", "порожній URL", "HTTP 400"])
    assert counts["observed"] == 2
    assert counts["access"] == 1
    assert counts["our_side"] == 1
    assert counts["ambiguous"] == 1
