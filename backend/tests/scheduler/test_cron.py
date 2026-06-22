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
