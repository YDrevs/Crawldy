"""Політика строків: хто скільки живе і хто це вирішує.

Чисті функції — тести без бази. Механізм чистки перевіряється окремо,
в інтеграційних; тут — правила, від яких залежить, що взагалі можна
втратити.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.application import retention_policy as policy
from app.application.retention_policy import DataClass, NeverExpires, RetentionPolicy

NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def test_the_record_class_cannot_expire_even_by_mistake():
    """Виняток, а не None: «немає обмеження» і «чистити все» надто схожі.

    Постійність запису має бути неможливо зламати помилкою в одному
    рядку — саме тому спроба спитати його строк падає, а не повертає
    щось, що можна сплутати з відповіддю.
    """
    rules = policy.DEFAULT
    with pytest.raises(NeverExpires):
        rules.cutoff(DataClass.RECORD, now=NOW)
    with pytest.raises(NeverExpires):
        rules.cutoff(DataClass.DERIVED, now=NOW)


def test_raw_data_expires_before_findings():
    """Порядок класів — це і є модель: найдорожче живе найменше."""
    rules = policy.DEFAULT
    raw = rules.cutoff(DataClass.RAW, now=NOW)
    findings = rules.cutoff(DataClass.FINDINGS, now=NOW)
    assert raw is not None and findings is not None
    assert raw > findings, "межа сирих даних ближча до сьогодні"


def test_a_plan_may_extend_but_never_shorten():
    """Продуктова межа — підлога, а не значення за замовчуванням.

    Якби тариф міг укоротити строк, пониження тарифу на місяць знищувало
    б рік історії безповоротно. Приховане повертається, знищене — ні.
    """
    extended = policy.resolve({"raw_retention_days": 3650})
    assert extended.raw_days == 3650

    shortened = policy.resolve({"raw_retention_days": 1})
    assert shortened.raw_days == policy.RAW_FLOOR_DAYS

    negative = policy.resolve({"raw_retention_days": -5, "findings_retention_days": 0})
    assert negative.raw_days == policy.DEFAULT_RAW_DAYS
    assert negative.findings_days == policy.DEFAULT_FINDINGS_DAYS


def test_findings_can_be_kept_forever_but_raw_cannot():
    """None у знахідках — «зберігати завжди»; у сирих даних такого немає.

    Вічні знімки означали б, що вартість зберігання росте лінійно з віком
    акаунта й ніколи не спадає.
    """
    keeper = policy.resolve({"findings_retention_days": None})
    assert keeper.findings_days is None
    assert keeper.cutoff(DataClass.FINDINGS, now=NOW) is None
    assert keeper.cutoff(DataClass.RAW, now=NOW) is not None


def test_empty_entitlements_mean_the_product_defaults():
    rules = policy.resolve(None)
    assert rules.raw_days == policy.DEFAULT_RAW_DAYS
    assert rules.findings_days == policy.DEFAULT_FINDINGS_DAYS


def test_the_floors_are_sane_relative_to_each_other():
    """Знахідки живуть довше за сирі дані навіть на мінімумах."""
    assert policy.FINDINGS_FLOOR_DAYS > policy.RAW_FLOOR_DAYS
    assert policy.DEFAULT_FINDINGS_DAYS > policy.DEFAULT_RAW_DAYS


def test_cutoff_moves_with_time():
    rules = RetentionPolicy(raw_days=30, findings_days=365)
    early = rules.cutoff(DataClass.RAW, now=NOW)
    later = rules.cutoff(DataClass.RAW, now=NOW + timedelta(days=1))
    assert later is not None and early is not None
    assert later - early == timedelta(days=1)


def test_extending_raw_extends_findings_with_it():
    """Інакше строки перевертаються: знімок є, а знахідок уже немає.

    Аудит «перераховуваний, але нечитаний» — абсурдний стан, і політика
    робить його недосяжним: хто подовжив знімки, подовжив і те, що з них
    рахують.
    """
    rules = policy.resolve({"raw_retention_days": 100_000})
    assert rules.findings_days is not None
    assert rules.findings_days >= rules.raw_days
