"""Коли розклад має спрацювати наступного разу.

Чистий модуль: ні бази, ні мережі, ні поточного часу за замовчуванням —
момент завжди передається явно. Інакше тести про перехід на літній час
неможливі, а саме там і живуть помилки цього коду.

Головне рішення: **розклад зберігає локальний настінний час, а не UTC.**
«Щодня о 9:00» означає 9:00 у зоні клієнта — і в березні, і в жовтні,
хоча в UTC це різні моменти. Зберігати одразу UTC означало б, що двічі
на рік звіт починає приходити на годину раніше або пізніше, і ніхто не
зрозуміє чому.
"""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.scheduling.enums import Cadence


class UnknownTimezone(ValueError):
    """Такої зони немає в базі IANA."""


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise UnknownTimezone(name) from exc


def _to_utc(local_naive: datetime, tz: ZoneInfo) -> datetime:
    """Локальний настінний час → UTC, з обробкою обох дір переходу.

    Навесні година зникає: 02:30 не існує взагалі. `fold` тут не
    допомагає — Python поверне момент, якого не було, і аудит запуститься
    зі зсувом. Тому неіснуючий час зсуваємо вперед до першого, що існує.

    Восени година повторюється: 02:30 буває двічі. Беремо перше
    входження (`fold=0`) — це раніший момент, тобто розклад радше
    спрацює на годину раніше, ніж на годину пізніше. Пропустити день
    гірше, ніж виконати трохи раніше.
    """
    candidate = local_naive.replace(tzinfo=tz, fold=0)
    # Ознака неіснуючого часу: перетворення туди-назад не збігається.
    back = candidate.astimezone(UTC).astimezone(tz)
    if back.replace(tzinfo=None) != local_naive:
        # Зсуваємо на годину вперед і беремо той момент, що існує.
        shifted = (local_naive + timedelta(hours=1)).replace(tzinfo=tz, fold=0)
        return shifted.astimezone(UTC)
    return candidate.astimezone(UTC)


def _clamp_day(year: int, month: int, day: int) -> date:
    """31 число в лютому — це останній день лютого, а не помилка.

    Альтернатива — пропускати місяць — виглядає «строгіше» й означає, що
    клієнт із розкладом на 31-ше не отримає звіту вісім разів на рік.
    """
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last))


def compute(
    *,
    cadence: Cadence,
    timezone_name: str,
    hour_local: int,
    minute_local: int = 0,
    day_of_week: int | None = None,
    day_of_month: int | None = None,
    after: datetime,
) -> datetime:
    """Найближчий момент **строго після** `after`, у UTC.

    «Строго після» важливе: інакше запуск, який щойно відбувся, знову
    потрапляє в вибірку — і планувальник крутиться на місці.
    """
    tz = zone(timezone_name)
    local_now = after.astimezone(tz)
    wanted = time(hour=hour_local, minute=minute_local)

    if cadence is Cadence.DAILY:
        candidate_date = local_now.date()
        for _ in range(3):
            moment = _to_utc(datetime.combine(candidate_date, wanted), tz)
            if moment > after:
                return moment
            candidate_date += timedelta(days=1)
        raise AssertionError("щоденний розклад не знайшов наступного дня")

    if cadence is Cadence.WEEKLY:
        target = 0 if day_of_week is None else day_of_week % 7
        candidate_date = local_now.date()
        # Двотижневе вікно: одного тижня замало, коли сьогодні потрібний
        # день, але година вже минула.
        for _ in range(15):
            if candidate_date.weekday() == target:
                moment = _to_utc(datetime.combine(candidate_date, wanted), tz)
                if moment > after:
                    return moment
            candidate_date += timedelta(days=1)
        raise AssertionError("тижневий розклад не знайшов наступного дня")

    target_day = 1 if day_of_month is None else day_of_month
    year, month = local_now.year, local_now.month
    for _ in range(14):
        moment = _to_utc(datetime.combine(_clamp_day(year, month, target_day), wanted), tz)
        if moment > after:
            return moment
        month += 1
        if month > 12:
            month, year = 1, year + 1
    raise AssertionError("місячний розклад не знайшов наступного місяця")


def interval_hours(cadence: Cadence) -> int:
    """Мінімальний проміжок, який дає ця періодичність.

    Потрібен для перевірки права `schedule_min_interval_hours`: тариф
    обмежує частоту, а не назву періоду.
    """
    return {Cadence.DAILY: 24, Cadence.WEEKLY: 24 * 7, Cadence.MONTHLY: 24 * 28}[cadence]
