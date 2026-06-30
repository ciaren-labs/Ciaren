# SPDX-License-Identifier: AGPL-3.0-only
"""Cron parsing helpers, isolated so both the service (validation, scheduling)
and the runner (advancing schedules) share one implementation.

All datetimes crossing this module's boundary are **naive UTC**, matching the
rest of the app (``datetime.utcnow``). The schedule's ``timezone`` is only used
internally to interpret the cron expression in the user's wall-clock time.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from croniter import CroniterBadCronError, croniter


def is_valid_cron(expression: str) -> bool:
    return croniter.is_valid(expression)


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

    base_local = after.replace(tzinfo=timezone.utc).astimezone(tz)
    try:
        nxt_local: datetime = croniter(expression, base_local).get_next(datetime)
    except (CroniterBadCronError, ValueError) as exc:
        raise ValueError(f"Invalid cron expression: {expression!r}") from exc
    return nxt_local.astimezone(timezone.utc).replace(tzinfo=None)
