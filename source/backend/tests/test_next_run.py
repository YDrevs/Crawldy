"""Коли розклад спрацює наступного разу.

Чиста логіка, тож і тести чисті: момент завжди передається явно. Саме це
робить можливими перевірки про перехід на літній час — а без них вони й
не з'явилися б, бо двічі на рік ніхто не дивиться.
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.scheduling.enums import Cadence
from app.scheduling.next_run import UnknownTimezone, compute, interval_hours

KYIV = ZoneInfo("Europe/Kyiv")


def _local(moment: datetime, tz: ZoneInfo = KYIV) -> str:
    return moment.astimezone(tz).strftime("%Y-%m-%d %H:%M")


def test_daily_picks_today_if_the_hour_has_not_come_yet():
    after = datetime(2026, 8, 22, 6, 0, tzinfo=UTC)  # 09:00 за Києвом

    moment = compute(
        cadence=Cadence.DAILY, timezone_name="Europe/Kyiv", hour_local=12, after=after
    )

    assert _local(moment) == "2026-08-22 12:00"


def test_daily_moves_to_tomorrow_if_the_hour_has_passed():
    after = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)  # 15:00 за Києвом

    moment = compute(
        cadence=Cadence.DAILY, timezone_name="Europe/Kyiv", hour_local=9, after=after
    )

    assert _local(moment) == "2026-08-23 09:00"


def test_the_next_run_is_strictly_after_the_moment_given():
    """Інакше запуск, який щойно відбувся, знову потрапляє у вибірку — і
    планувальник крутиться на місці."""
    exactly_nine = datetime(2026, 8, 22, 6, 0, tzinfo=UTC)

    moment = compute(
        cadence=Cadence.DAILY, timezone_name="Europe/Kyiv", hour_local=9, after=exactly_nine
    )

    assert moment > exactly_nine
    assert _local(moment) == "2026-08-23 09:00"


# ── перехід на літній час ──────────────────────────────────────────────────


def test_nine_in_the_morning_stays_nine_across_the_spring_change():
    """Головна перевірка модуля.

    Зберігати одразу UTC означало б, що двічі на рік звіт починає
    приходити на годину раніше або пізніше, і ніхто не зрозуміє чому.
    """
    before = compute(
        cadence=Cadence.DAILY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
        after=datetime(2027, 3, 26, 12, 0, tzinfo=UTC),
    )
    after_change = compute(
        cadence=Cadence.DAILY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
        after=datetime(2027, 3, 29, 12, 0, tzinfo=UTC),
    )

    assert _local(before) == "2027-03-27 09:00"
    assert _local(after_change) == "2027-03-30 09:00"
    assert before.hour != after_change.hour, "у UTC це різні години — і має бути так"


def test_a_local_time_that_does_not_exist_is_shifted_forward():
    """Навесні година зникає: 03:30 за Києвом 28 березня не існує.

    Пропустити день гірше, ніж виконати трохи пізніше, тож зсуваємо
    вперед до першого моменту, який справді існує.
    """
    moment = compute(
        cadence=Cadence.DAILY,
        timezone_name="Europe/Kyiv",
        hour_local=3,
        minute_local=30,
        after=datetime(2027, 3, 27, 12, 0, tzinfo=UTC),
    )

    local = moment.astimezone(KYIV)
    assert local.date().isoformat() == "2027-03-28"
    assert local.hour == 4, "неіснуючу годину зсунуто вперед"


def test_an_ambiguous_local_time_takes_the_earlier_one():
    """Восени година повторюється. Беремо перше входження: розклад радше
    спрацює на годину раніше, ніж на годину пізніше."""
    moment = compute(
        cadence=Cadence.DAILY,
        timezone_name="Europe/Kyiv",
        hour_local=3,
        minute_local=30,
        after=datetime(2027, 10, 30, 12, 0, tzinfo=UTC),
    )

    assert _local(moment) == "2027-10-31 03:30"
    assert moment == datetime(2027, 10, 31, 0, 30, tzinfo=UTC), "раніше з двох входжень"


# ── тиждень ────────────────────────────────────────────────────────────────


def test_weekly_finds_the_next_matching_weekday():
    # 22 серпня 2026 — субота.
    after = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)

    moment = compute(
        cadence=Cadence.WEEKLY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
        day_of_week=0,  # понеділок
        after=after,
    )

    assert _local(moment) == "2026-08-24 09:00"


def test_weekly_on_today_but_the_hour_has_passed_waits_a_week():
    """Однотижневого вікна пошуку тут замало — і це найлегше пропустити."""
    # 24 серпня 2026 — понеділок, 15:00 за Києвом.
    after = datetime(2026, 8, 24, 12, 0, tzinfo=UTC)

    moment = compute(
        cadence=Cadence.WEEKLY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
        day_of_week=0,
        after=after,
    )

    assert _local(moment) == "2026-08-31 09:00"


# ── місяць ─────────────────────────────────────────────────────────────────


def test_monthly_picks_the_requested_day():
    after = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)

    moment = compute(
        cadence=Cadence.MONTHLY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
        day_of_month=25,
        after=after,
    )

    assert _local(moment) == "2026-08-25 09:00"


def test_the_thirty_first_in_february_is_the_last_day_not_a_skipped_month():
    """Пропускати місяць виглядає «строгіше» й означає, що клієнт із
    розкладом на 31-ше не отримає звіту вісім разів на рік."""
    after = datetime(2027, 2, 1, 12, 0, tzinfo=UTC)

    moment = compute(
        cadence=Cadence.MONTHLY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
        day_of_month=31,
        after=after,
    )

    assert _local(moment) == "2027-02-28 09:00"


def test_monthly_rolls_over_the_year():
    after = datetime(2026, 12, 20, 12, 0, tzinfo=UTC)

    moment = compute(
        cadence=Cadence.MONTHLY,
        timezone_name="Europe/Kyiv",
        hour_local=9,
        day_of_month=15,
        after=after,
    )

    assert _local(moment) == "2027-01-15 09:00"


# ── зони й межі ────────────────────────────────────────────────────────────


def test_an_unknown_timezone_is_refused_loudly():
    """Тихий фолбек на UTC означав би звіти о четвертій ранку без жодного
    сліду про причину."""
    with pytest.raises(UnknownTimezone):
        compute(
            cadence=Cadence.DAILY,
            timezone_name="Europe/Kyyiv",  # друкарська помилка
            hour_local=9,
            after=datetime(2026, 8, 22, tzinfo=UTC),
        )


@pytest.mark.parametrize(
    ("zone_name", "expected_hour_utc"),
    [("UTC", 9), ("Europe/Kyiv", 6), ("America/New_York", 13)],
)
def test_the_same_local_hour_is_different_moments_in_different_zones(zone_name, expected_hour_utc):
    moment = compute(
        cadence=Cadence.DAILY,
        timezone_name=zone_name,
        hour_local=9,
        after=datetime(2026, 8, 22, 0, 0, tzinfo=UTC),
    )

    assert moment.hour == expected_hour_utc


def test_interval_reflects_the_cadence_not_its_name():
    """Тариф обмежує частоту, а не назву періоду."""
    assert interval_hours(Cadence.DAILY) == 24
    assert interval_hours(Cadence.WEEKLY) == 168
    assert interval_hours(Cadence.MONTHLY) >= 24 * 28
