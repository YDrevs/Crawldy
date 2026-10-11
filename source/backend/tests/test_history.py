"""Історія скорів: чи знає порівняння, коли йому не можна вірити."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.report.history import ScorePoint, compare, needs_recompute, timeline

WHEN = datetime(2026, 1, 1, tzinfo=UTC)
RULES = {"detector": "aaa", "scoring": "bbb", "config": "ccc"}


def _point(day: int, overall: int | None, versions=None, *, snapshot=False, **scores):
    return ScorePoint(
        audit_id=f"a{day}",
        at=WHEN + timedelta(days=day),
        overall=overall,
        scores=scores or {"seo": 50, "tech": 50},
        versions=versions if versions is not None else dict(RULES),
        has_snapshot=snapshot,
    )


def test_same_rules_make_the_difference_belong_to_the_site():
    result = compare(_point(0, 50), _point(30, 62))
    assert result.comparable is True
    assert result.overall_delta == 12
    assert result.changed_in_us == []
    assert result.days == 30


def test_changed_scoring_makes_the_difference_ours_not_the_sites():
    """Двічі в цьому проєкті зміна стелі зсувала бали всієї вибірки."""
    later = _point(30, 62, {**RULES, "scoring": "інша"})
    result = compare(_point(0, 50), later)
    assert result.comparable is False
    assert result.changed_in_us == ["scoring"]
    # Число все одно показуємо: ховати його безглуздо, воно є у двох звітах.
    assert result.overall_delta == 12


def test_a_new_check_is_also_a_change_in_us():
    later = _point(30, 44, {**RULES, "detector": "інший"})
    assert compare(_point(0, 50), later).changed_in_us == ["detector"]


def test_a_different_crawl_budget_does_not_invalidate_the_comparison():
    """`config` каже, що ми міряли, а не як рахували."""
    later = _point(30, 62, {**RULES, "config": "інша"})
    assert compare(_point(0, 50), later).comparable is True


def test_recomputed_comparison_is_honest_despite_different_versions():
    later = _point(30, 62, {**RULES, "scoring": "інша"})
    result = compare(_point(0, 50), later, rebased=True)
    assert result.comparable is True
    assert result.rebased is True
    assert result.changed_in_us == []


def test_missing_overall_gives_no_delta_instead_of_zero():
    """Нуль означав би «не змінилося», а ми просто не знаємо."""
    assert compare(_point(0, None), _point(30, 62)).overall_delta is None


def test_module_deltas_skip_modules_absent_from_one_side():
    before = _point(0, 50, seo=50, tech=50)
    after = _point(30, 60, seo=64, accessibility=90)
    assert compare(before, after).by_module == {"seo": 14}


def test_timeline_compares_each_audit_with_the_previous_one():
    points = [_point(60, 70), _point(0, 50), _point(30, 62)]
    steps = timeline(points)
    assert [c.overall_delta for c in steps] == [12, 8]


def test_only_comparisons_with_a_stored_snapshot_can_be_fixed():
    """Без знімка перерахувати нічим, і робити вигляд не можна."""
    changed = {**RULES, "scoring": "інша"}
    with_snapshot = compare(_point(0, 50, snapshot=True), _point(30, 62, changed))
    without = compare(_point(0, 50), _point(30, 62, changed))
    assert needs_recompute([with_snapshot, without]) == [with_snapshot]
