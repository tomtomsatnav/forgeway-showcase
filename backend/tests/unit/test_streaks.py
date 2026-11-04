from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st

from lattice.domain.progression import (
    Streak,
    current_streak,
    local_day,
    longest_streak,
    streak_of,
)

TODAY = date(2026, 10, 25)

# Zones chosen for their awkward edges: both ends of the date line, half-hour offsets and
# half-hour DST, DST at midnight, and DST that is suspended for a month.
ZONES = [
    "UTC",
    "Europe/London",
    "America/New_York",
    "America/Sao_Paulo",
    "Africa/Casablanca",
    "Asia/Kolkata",
    "Australia/Lord_Howe",
    "Pacific/Auckland",
    "Pacific/Kiritimati",  # UTC+14
    "Pacific/Pago_Pago",  # UTC-11
]
zones = st.sampled_from(ZONES).map(ZoneInfo)
instants = st.datetimes(
    min_value=datetime(2020, 1, 1), max_value=datetime(2031, 1, 1), timezones=st.just(UTC)
)


def days_back(*offsets: int) -> set[date]:
    return {TODAY - timedelta(days=n) for n in offsets}


def test_no_days_means_no_streak():
    assert streak_of(set(), TODAY) == Streak(current=0, longest=0)


def test_a_streak_ending_today_or_yesterday_is_live():
    assert current_streak(days_back(0, 1, 2), TODAY) == 3
    assert current_streak(days_back(1, 2, 3), TODAY) == 3


def test_missing_a_whole_day_ends_the_streak():
    assert current_streak(days_back(2, 3, 4), TODAY) == 0
    assert longest_streak(days_back(2, 3, 4)) == 3


def test_a_gap_splits_runs_and_the_longest_wins():
    days = days_back(0, 1, 3, 4, 5, 6)
    assert streak_of(days, TODAY).current == 2
    assert streak_of(days, TODAY).longest == 4


def test_several_attempts_on_one_day_are_one_day():
    assert longest_streak([TODAY, TODAY, TODAY]) == 1


def test_naive_instants_are_rejected():
    with pytest.raises(ValueError):
        local_day(datetime(2026, 1, 1, 12), ZoneInfo("UTC"))


@pytest.mark.parametrize(
    ("instant", "zone", "expected"),
    [
        # The date line: the same instant is two different days.
        (datetime(2026, 1, 1, 10, 30, tzinfo=UTC), "Pacific/Kiritimati", date(2026, 1, 2)),
        (datetime(2026, 1, 1, 10, 30, tzinfo=UTC), "Pacific/Pago_Pago", date(2025, 12, 31)),
        (datetime(2026, 1, 1, 10, 30, tzinfo=UTC), "UTC", date(2026, 1, 1)),
        # Spring forward in London: 01:00 UTC becomes 02:00 BST, still the same day.
        (datetime(2026, 3, 29, 0, 59, tzinfo=UTC), "Europe/London", date(2026, 3, 29)),
        (datetime(2026, 3, 29, 1, 0, tzinfo=UTC), "Europe/London", date(2026, 3, 29)),
        # Summer time makes 23:30 UTC the next morning in London.
        (datetime(2026, 7, 1, 23, 30, tzinfo=UTC), "Europe/London", date(2026, 7, 2)),
        # Fall back in New York: 01:30 happens twice, both on 1 November.
        (datetime(2026, 11, 1, 5, 30, tzinfo=UTC), "America/New_York", date(2026, 11, 1)),
        (datetime(2026, 11, 1, 6, 30, tzinfo=UTC), "America/New_York", date(2026, 11, 1)),
        (datetime(2026, 11, 2, 4, 59, tzinfo=UTC), "America/New_York", date(2026, 11, 1)),
        (datetime(2026, 11, 2, 5, 0, tzinfo=UTC), "America/New_York", date(2026, 11, 2)),
    ],
)
def test_local_day_in_a_zone(instant, zone, expected):
    assert local_day(instant, ZoneInfo(zone)) == expected


@given(st.sets(st.integers(0, 120)), st.integers(0, 120))
def test_current_streak_never_exceeds_longest(offsets, extra):
    days = {TODAY - timedelta(days=n) for n in offsets | {extra}}
    assert 0 <= current_streak(days, TODAY) <= longest_streak(days) <= len(days)


@given(st.sets(st.integers(0, 60)))
def test_longest_streak_matches_a_day_by_day_count(offsets):
    days = {TODAY - timedelta(days=n) for n in offsets}
    best = run = 0
    for n in range(60, -1, -1):
        run = run + 1 if TODAY - timedelta(days=n) in days else 0
        best = max(best, run)
    assert longest_streak(days) == best


@given(st.integers(1, 60), st.integers(0, 1))
def test_a_run_ending_today_or_yesterday_counts_in_full(length, ends_ago):
    days = {TODAY - timedelta(days=ends_ago + i) for i in range(length)}
    assert current_streak(days, TODAY) == length


@given(st.integers(1, 60), st.integers(2, 30))
def test_a_run_that_ended_before_yesterday_is_not_current(length, ends_ago):
    days = {TODAY - timedelta(days=ends_ago + i) for i in range(length)}
    assert current_streak(days, TODAY) == 0
    assert longest_streak(days) == length


@given(st.sets(st.integers(0, 120), min_size=1), st.integers(0, 120))
def test_learning_more_never_shortens_the_longest_streak(offsets, extra):
    days = {TODAY - timedelta(days=n) for n in offsets}
    assert longest_streak(days | {TODAY - timedelta(days=extra)}) >= longest_streak(days)


@given(instants, zones)
def test_local_day_is_within_a_day_of_the_utc_date(instant, zone):
    assert abs((local_day(instant, zone) - instant.date()).days) <= 1


@given(instants, zones, st.integers(0, 22))
def test_local_day_never_runs_backwards(instant, zone, hours):
    """Even across a DST change, 22 hours later is the same day or the next, never earlier."""
    later = instant + timedelta(hours=hours)
    step = (local_day(later, zone) - local_day(instant, zone)).days
    assert step in (0, 1)


@given(
    zones,
    st.dates(min_value=date(2020, 1, 3), max_value=date(2030, 1, 1)),
    st.lists(st.integers(0, 23), min_size=1, max_size=14),
)
def test_working_at_any_hour_each_day_is_one_streak(zone, start, hours):
    """Learning at any wall-clock hour on consecutive local days gives an unbroken streak,
    including across DST changes and in the zones furthest east and west."""
    days = []
    for offset, hour in enumerate(hours):
        wall = datetime.combine(start + timedelta(days=offset), datetime.min.time(), zone)
        instant = (wall + timedelta(hours=hour)).astimezone(UTC)
        days.append(local_day(instant, zone))
    assert days == [start + timedelta(days=i) for i in range(len(hours))]
    assert longest_streak(days) == len(hours)
