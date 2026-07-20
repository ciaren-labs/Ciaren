# SPDX-License-Identifier: AGPL-3.0-only
"""Cron parsing helpers, isolated so both the service (validation, scheduling)
and the runner (advancing schedules) share one implementation.

All datetimes crossing this module's boundary are **naive UTC**, matching the
rest of the app (``datetime.utcnow``). The schedule's ``timezone`` is only used
internally to interpret the cron expression in the user's wall-clock time.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, croniter


def is_valid_cron(expression: str) -> bool:
    return croniter.is_valid(expression)


def _fires_at_most_once_per_day(expression: str, reference: datetime) -> bool:
    """True when the cron fires at most once per calendar day ("daily-or-coarser":
    a pinned daily/weekly/monthly time), as opposed to a sub-daily interval such
    as ``*/30 * * * *`` or ``0 * * * *``.

    Probed in tz-naive time so DST can't distort the measured cadence; cadence is
    a property of the expression, not of any wall clock. On any error we return
    ``False`` (skip the DST de-dup below), which preserves the plain behaviour.
    """
    try:
        probe = croniter(expression, reference.replace(tzinfo=None))
        first: datetime = probe.get_next(datetime)
        second: datetime = probe.get_next(datetime)
    except (CroniterBadCronError, ValueError):
        return False
    return (second - first) >= timedelta(days=1)


def _is_stale_dst_repeat(candidate_local: datetime, after_utc: datetime, tz: ZoneInfo) -> bool:
    """True when ``candidate_local`` is the *second* (later) fold of a DST fall-back
    hour whose *first* fold already elapsed at or before ``after_utc``.

    On the fall-back night, clocks are set back an hour, so a pinned wall-clock
    time (e.g. 01:30) maps to two real instants. Once the earlier one has fired
    we must not fire again for the same wall-clock time — croniter, given an
    aware base inside the repeated hour, otherwise yields the later fold next.
    """
    wall = candidate_local.replace(tzinfo=None)
    earliest_utc = wall.replace(tzinfo=tz, fold=0).astimezone(timezone.utc)
    candidate_utc = candidate_local.astimezone(timezone.utc)
    # earliest_utc < candidate_utc  → candidate is the later fold of a repeated hour.
    # earliest_utc <= after_utc     → the earlier fold already elapsed (was fired).
    return earliest_utc < candidate_utc and earliest_utc <= after_utc


def is_valid_timezone(name: str) -> bool:
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True


def compute_next_run(expression: str, after: datetime, tz_name: str = "UTC") -> datetime:
    """Return the next fire time strictly after ``after`` as a naive UTC datetime.

    ``after`` is treated as naive UTC; the cron is evaluated in ``tz_name`` so a
    "0 9 * * *" schedule fires at 09:00 local time (honouring DST), then the
    result is converted back to naive UTC for storage and comparison.
    """
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown timezone: {tz_name!r}") from exc

    after_utc = after.replace(tzinfo=timezone.utc)
    base_local = after_utc.astimezone(tz)
    try:
        cron_iter = croniter(expression, base_local)
        nxt_local: datetime = cron_iter.get_next(datetime)

        # DST fall-back de-duplication. When the clocks go back an hour, a pinned
        # wall-clock time occurs at two real instants. A schedule that fires at
        # most once per day must run only ONCE for that wall-clock time; without
        # this, the recompute after the first fire lands on the second (later)
        # fold and the job fires twice. Sub-daily schedules (hourly, ``*/30``…)
        # run once per *elapsed* interval, so their repeated-hour occurrences are
        # genuine and are left untouched (the guard below only applies to
        # daily-or-coarser crons).
        if _fires_at_most_once_per_day(expression, after):
            while _is_stale_dst_repeat(nxt_local, after_utc, tz):
                nxt_local = cron_iter.get_next(datetime)
    except (CroniterBadCronError, ValueError) as exc:
        # Also fires for a valid-syntax cron that never resolves to a real date
        # (e.g. "0 0 30 2 *"): croniter raises CroniterBadDateError (a ValueError).
        raise ValueError(f"Invalid cron expression: {expression!r}") from exc
    return nxt_local.astimezone(timezone.utc).replace(tzinfo=None)
