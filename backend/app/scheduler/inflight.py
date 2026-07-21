# SPDX-License-Identifier: AGPL-3.0-only
"""Process-wide overlap guard shared by the background scheduler and the
manual ``run_now`` path.

A scheduled fire and a manual "Run now" both execute the *same* flow to
completion and write to its (possibly external) SQL/storage sinks. Running two
at once would produce duplicate/interleaved writes, so at most one
scheduler-driven run per flow may be in flight at a time. Both entry points
acquire the same flow-keyed guard here; ad-hoc flow runs (``POST /runs``) are
intentionally *not* gated — this guard only serialises schedule-owned runs.

The whole app runs in a single event loop, but a ``threading.Lock`` keeps the
acquire/release atomic and future-proofs process/thread execution modes.
"""

import threading

_lock = threading.Lock()
_active_flows: set[str] = set()


def try_acquire(flow_id: str) -> bool:
    """Reserve the flow for a scheduler-owned run. Returns ``False`` (and changes
    nothing) if a scheduler-owned run of this flow is already in flight."""
    with _lock:
        if flow_id in _active_flows:
            return False
        _active_flows.add(flow_id)
        return True


def release(flow_id: str) -> None:
    """Release a reservation taken by :func:`try_acquire`. Idempotent."""
    with _lock:
        _active_flows.discard(flow_id)


def is_active(flow_id: str) -> bool:
    with _lock:
        return flow_id in _active_flows
