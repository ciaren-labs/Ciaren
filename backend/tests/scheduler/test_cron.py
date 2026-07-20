"""Unit tests for the cron helpers — pure functions, no DB."""

from datetime import datetime

import pytest

from app.scheduler.cron import compute_next_run, is_valid_cron, is_valid_timezone


def test_is_valid_cron() -> None:
    assert is_valid_cron("0 9 * * *")
    assert is_valid_cron("*/5 * * * *")
    assert not is_valid_cron("not a cron")
    assert not is_valid_cron("99 99 * * *")


def test_is_valid_timezone() -> None:
    assert is_valid_timezone("UTC")
    assert is_valid_timezone("America/New_York")
    assert not is_valid_timezone("Mars/Phobos")


def test_compute_next_run_utc() -> None:
    # 12:00 UTC -> next 09:00 UTC is the following day.
    nxt = compute_next_run("0 9 * * *", datetime(2026, 6, 22, 12, 0, 0), "UTC")
    assert nxt == datetime(2026, 6, 23, 9, 0, 0)


def test_compute_next_run_honours_timezone() -> None:
    # 09:00 in New York (EDT, UTC-4 in June) == 13:00 UTC, returned as naive UTC.
    nxt = compute_next_run("0 9 * * *", datetime(2026, 6, 22, 0, 0, 0), "America/New_York")
    assert nxt == datetime(2026, 6, 22, 13, 0, 0)


def test_compute_next_run_is_strictly_after() -> None:
    base = datetime(2026, 6, 22, 9, 0, 0)
    nxt = compute_next_run("0 9 * * *", base, "UTC")
    assert nxt > base
    assert nxt == datetime(2026, 6, 23, 9, 0, 0)


def test_compute_next_run_rejects_bad_timezone() -> None:
    with pytest.raises(ValueError):
        compute_next_run("0 9 * * *", datetime(2026, 6, 22, 12, 0, 0), "Mars/Phobos")


def test_compute_next_run_rejects_cron_that_never_resolves() -> None:
    # Syntactically valid (croniter.is_valid == True) but 30 February never exists,
    # so croniter raises CroniterBadDateError (a ValueError) — surfaced as ValueError.
    with pytest.raises(ValueError):
        compute_next_run("0 0 30 2 *", datetime(2026, 1, 1, 0, 0, 0), "UTC")


# -- DST fall-back: a repeated wall-clock hour must not double-fire ----------
#
# On 2026-11-01 the US Eastern clocks go back from 02:00 EDT to 01:00 EST, so the
# 01:00–01:59 wall-clock hour happens twice (01:30 EDT == 05:30 UTC, then
# 01:30 EST == 06:30 UTC). A once-a-day schedule must fire only once for it.


def test_daily_cron_fires_once_across_dst_fall_back() -> None:
    # After firing at 01:30 EDT (05:30 UTC), the next run must skip the repeated
    # 01:30 EST (06:30 UTC) and jump to the NEXT day, not fire twice.
    first = compute_next_run("30 1 * * *", datetime(2026, 11, 1, 5, 0, 0), "America/New_York")
    assert first == datetime(2026, 11, 1, 5, 30, 0)  # 01:30 EDT

    second = compute_next_run("30 1 * * *", first, "America/New_York")
    # NOT 2026-11-01 06:30 (the DST repeat) — the following day's 01:30 EST.
    assert second == datetime(2026, 11, 2, 6, 30, 0)
    assert second.date() == datetime(2026, 11, 2).date()


def test_daily_cron_first_fold_still_fires_before_it_elapses() -> None:
    # Computing before the first fold has passed must return that first fold,
    # not skip straight past the whole hour.
    nxt = compute_next_run("30 1 * * *", datetime(2026, 11, 1, 5, 0, 0), "America/New_York")
    assert nxt == datetime(2026, 11, 1, 5, 30, 0)  # 01:30 EDT, the earlier instant


def test_subdaily_cron_keeps_both_dst_repeated_occurrences() -> None:
    # A */30 schedule fires every elapsed 30 minutes, so it MUST run at both the
    # 01:00/01:30 EDT instants AND the repeated 01:00/01:30 EST instants — losing
    # one would drop a genuine run.
    fires = []
    t = datetime(2026, 11, 1, 4, 45, 0)  # 00:45 EDT
    for _ in range(6):
        t = compute_next_run("*/30 * * * *", t, "America/New_York")
        fires.append(t)
    assert fires == [
        datetime(2026, 11, 1, 5, 0, 0),  # 01:00 EDT
        datetime(2026, 11, 1, 5, 30, 0),  # 01:30 EDT
        datetime(2026, 11, 1, 6, 0, 0),  # 01:00 EST (repeat kept)
        datetime(2026, 11, 1, 6, 30, 0),  # 01:30 EST (repeat kept)
        datetime(2026, 11, 1, 7, 0, 0),  # 02:00 EST
        datetime(2026, 11, 1, 7, 30, 0),  # 02:30 EST
    ]


def test_hourly_cron_keeps_both_dst_repeated_hours() -> None:
    # An hourly schedule runs once per elapsed hour, so the 25-hour fall-back day
    # includes both 01:00 instants (01:00 EDT and 01:00 EST).
    fires = []
    t = datetime(2026, 11, 1, 4, 30, 0)  # 00:30 EDT
    for _ in range(4):
        t = compute_next_run("0 * * * *", t, "America/New_York")
        fires.append(t)
    assert fires == [
        datetime(2026, 11, 1, 5, 0, 0),  # 01:00 EDT
        datetime(2026, 11, 1, 6, 0, 0),  # 01:00 EST (repeat kept)
        datetime(2026, 11, 1, 7, 0, 0),  # 02:00 EST
        datetime(2026, 11, 1, 8, 0, 0),  # 03:00 EST
    ]
