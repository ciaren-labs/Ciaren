# SPDX-License-Identifier: AGPL-3.0-only
"""In-memory cancellation registry for in-flight runs.

The API request that cancels a run is not the task executing it, so they need
a shared signal. The app is single-process (the scheduler and all API workers
share this interpreter; process-mode workers only ever run the picklable
compute), so a plain module-level dict of ``threading.Event``s keyed by run id
is sufficient — and survives nothing, deliberately: a run left ``running``
after a crash is already swept to ``failed`` by the scheduler's startup
recovery, never left waiting for a cancel that can't arrive.

Semantics by execution mode:

- **thread** (default): the executor checks the event *between nodes* and
  stops cooperatively — remaining nodes are recorded ``skipped`` and the run
  ends ``cancelled``. A single long node cannot be interrupted mid-computation
  (Python threads are not killable); the run stops at the next node boundary.
- **process**: the worker process cannot see this event, so cancel abandons
  the task the same way the timeout path does (the pool is recycled); the run
  is marked ``cancelled`` immediately.
"""

from __future__ import annotations

import threading

_lock = threading.Lock()
_active: dict[str, threading.Event] = {}


def register_run(run_id: str) -> threading.Event:
    """Create and track the cancel event for a run about to execute."""
    event = threading.Event()
    with _lock:
        _active[run_id] = event
    return event


def unregister_run(run_id: str) -> None:
    with _lock:
        _active.pop(run_id, None)


def request_cancel(run_id: str) -> bool:
    """Signal a running run to stop. False when the run isn't executing in
    this process (already finished, or a stale row from before a restart)."""
    with _lock:
        event = _active.get(run_id)
    if event is None:
        return False
    event.set()
    return True


def request_cancel_all() -> int:
    """Signal every currently-executing run to stop. Returns how many were signalled.

    Used at shutdown to ask in-flight runs to stop cooperatively (thread mode stops
    at the next node boundary and finalizes as ``cancelled``) before the scheduler
    resorts to abandoning them."""
    with _lock:
        events = list(_active.values())
    for event in events:
        event.set()
    return len(events)


def is_run_active(run_id: str) -> bool:
    """Whether ``run_id`` is executing in this process — without touching its
    cancel event. Lets the cancel endpoint refuse (guards, stale rows) before
    setting the event; a refused cancel must leave no trace, or a later
    timeout/real failure would be mislabeled "cancelled"."""
    with _lock:
        return run_id in _active


def active_run_count() -> int:
    """How many runs are currently executing in this process."""
    with _lock:
        return len(_active)


def is_cancel_requested(run_id: str) -> bool:
    with _lock:
        event = _active.get(run_id)
    return event.is_set() if event is not None else False
