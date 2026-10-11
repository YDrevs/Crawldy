"""Політика повторів: що пробуємо ще раз і через скільки.

Чиста функція, тож і тести без бази й без черги. Це і є причина, чому
політика винесена окремо: правило, за яким клієнту повертають гроші й
витрачають ще один краул, має перевірятися за мілісекунди.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.application import retries
from app.audit.i18n import Locale
from app.core.run_enums import FailureClass


def test_our_own_failure_gets_a_second_chance():
    decision = retries.decide(failure=FailureClass.INTERNAL_ERROR, attempts=1)
    assert decision.retry is True
    assert decision.delay > timedelta(0)


def test_a_failure_that_repeats_is_not_ours_to_fix_by_repeating():
    """Друга така сама невдача означає, що вона детермінована."""
    decision = retries.decide(failure=FailureClass.INTERNAL_ERROR, attempts=2)
    assert decision.retry is False
    assert decision.reason_key == "notice.retry.exhausted"


@pytest.mark.parametrize("failure", [FailureClass.SITE_BLOCKED, FailureClass.CANCELLED])
def test_a_decision_of_the_site_is_not_argued_with(failure):
    """403 на все — рішення сайту, а не збій.

    Скасування тут із тієї ж причини з іншого боку: це теж рішення, і
    повторювати рішення нема сенсу.
    """
    decision = retries.decide(failure=failure, attempts=1)
    assert decision.retry is False
    assert decision.reason_key == "notice.retry.not_retryable"
    assert decision.reason_params == {"failure": failure.value}


def test_a_site_that_did_not_answer_is_asked_once_more():
    """Тридцять секунд збою хостингу не мають ставати результатом аудиту.

    Повтор тут майже безплатний: недосяжний сайт краулу не коштує, запит
    падає на з'єднанні. А ціна відмови від повтору — списана квота,
    порожній звіт і фальшивий провал у кривій.
    """
    assert retries.decide(failure=FailureClass.SITE_UNREACHABLE, attempts=1).retry is True
    assert retries.decide(failure=FailureClass.SITE_UNREACHABLE, attempts=2).retry is False


def test_the_reason_tells_apart_exhausted_from_never():
    """Два «ні» — різні відповіді клієнту, і ключі мусять це показувати."""
    exhausted = retries.decide(failure=FailureClass.INTERNAL_ERROR, attempts=99)
    never = retries.decide(failure=FailureClass.SITE_BLOCKED, attempts=1)
    assert exhausted.reason_key != never.reason_key


@pytest.mark.parametrize("locale", [Locale.EN, Locale.UK])
def test_the_reason_is_a_key_that_renders_in_the_readers_language(locale):
    """Політика тексту не пише — вона віддає ключ, як і чек.

    Поки вона повертала готове речення, воно з воркера потрапляло просто
    в журнал спроб і звідти клієнту — українською, хоч би якою мовою він
    читав решту сторінки.
    """
    decision = retries.decide(failure=FailureClass.INTERNAL_ERROR, attempts=1)
    rendered = decision.explain(locale)
    assert rendered != decision.reason_key, "ключ знайшовся в каталозі"
    assert "{" not in rendered, "усі параметри підставлені"


def test_an_unknown_locale_explains_itself_in_english():
    decision = retries.decide(failure=FailureClass.INTERNAL_ERROR, attempts=1)
    assert decision.explain(Locale.JA) == decision.explain(Locale.EN)


def test_the_pause_grows_and_stops_growing():
    """Зростання — щоб не добивати сервіс, стеля — щоб не чекати годину."""
    pauses = [retries.backoff(n) for n in range(1, 8)]
    assert pauses == sorted(pauses)
    assert pauses[0] == retries.FIRST_DELAY
    assert max(pauses) == retries.MAX_DELAY


def test_the_whole_retry_window_fits_inside_the_shortest_schedule():
    """Інакше повтори одного входження наклалися б на наступне.

    Найчастіший розклад — щодобовий; повтори мусять скінчитися задовго до
    того, як настане наступна дев'ята ранку, інакше два запуски того
    самого розкладу змагалися б за ту саму квоту.
    """
    longest = max(retries.MAX_ATTEMPTS.values())
    window = sum((retries.backoff(n) for n in range(1, longest + 1)), timedelta(0))
    assert window < timedelta(hours=24)


def test_an_unknown_failure_class_is_not_retried_by_accident():
    """Новий клас невдачі не має отримати повтори мовчки."""
    for failure in FailureClass:
        if failure not in retries.MAX_ATTEMPTS:
            assert retries.decide(failure=failure, attempts=1).retry is False


# ── дві речі, які мусять бути однозначними ─────────────────────────────────


def test_max_attempts_counts_the_first_try_too():
    """«Дві спроби» і «два повтори» звучать однаково, коштують по-різному.

    `MAX_ATTEMPTS[INTERNAL_ERROR] = 2` означає одну початкову спробу плюс
    рівно один повтор — а не початкову плюс два.
    """
    assert retries.MAX_ATTEMPTS[FailureClass.INTERNAL_ERROR] == 2
    assert retries.retries_allowed(FailureClass.INTERNAL_ERROR) == 1

    assert retries.decide(failure=FailureClass.INTERNAL_ERROR, attempts=1).retry is True
    assert retries.decide(failure=FailureClass.INTERNAL_ERROR, attempts=2).retry is False


def test_retries_allowed_is_one_less_than_attempts_for_every_class():
    for failure in FailureClass:
        total = retries.MAX_ATTEMPTS.get(failure, 1)
        assert retries.retries_allowed(failure) == total - 1


@pytest.mark.parametrize("failure", list(FailureClass))
def test_a_retry_never_comes_without_a_pause(failure):
    """Повтор без паузи — це гарячий цикл, а не повтор.

    Воркер узяв би завдання, впав, поставив наступне й одразу взяв його ж.
    Черга при цьому виглядає робочою, а сайт клієнта отримує шквал
    запитів за секунди.
    """
    for attempts in range(1, 11):
        decision = retries.decide(failure=failure, attempts=attempts)
        if decision.retry:
            assert decision.delay >= retries.FIRST_DELAY
            assert decision.delay_seconds > 0
        else:
            assert decision.delay == timedelta(0)


@pytest.mark.parametrize("failure", list(FailureClass))
def test_the_chain_of_retries_always_ends(failure):
    """Проганяємо політику так, як її проганяє воркер.

    Якщо десь у ній є стан, що дозволяє повтор нескінченно, цикл тут не
    завершиться — і це єдиний спосіб побачити таку ваду до продакшену.
    """
    attempts = 1
    taken = 0
    while retries.decide(failure=failure, attempts=attempts).retry:
        attempts += 1
        taken += 1
        assert taken <= 100, "політика не зупиняється"
    assert taken == retries.retries_allowed(failure)
