"""Route inventory guardrail.

Snapshots the full set of registered ``METHOD /path`` pairs so an *accidental* route
change — a typo in a prefix, a dropped endpoint, a collision — fails CI, while an
*intentional* change shows up as a reviewable diff of ``tests/route_snapshot.txt``.

To update after an intentional route change, regenerate the snapshot:

    CIAREN_UPDATE_ROUTE_SNAPSHOT=1 pytest tests/test_route_snapshot.py

See app/README.md for the routing conventions the snapshot encodes.
"""

import os
from pathlib import Path

from app.main import app

_SNAPSHOT = Path(__file__).resolve().parent / "route_snapshot.txt"


def _current_routes() -> list[str]:
    paths = app.openapi()["paths"]
    return sorted(f"{method.upper()} {path}" for path, ops in paths.items() for method in ops)


def test_no_duplicate_method_path_registrations() -> None:
    routes = _current_routes()
    dupes = sorted({r for r in routes if routes.count(r) > 1})
    assert not dupes, f"the same METHOD+path is registered more than once (collision): {dupes}"


def test_route_snapshot_matches() -> None:
    current = _current_routes()
    if os.getenv("CIAREN_UPDATE_ROUTE_SNAPSHOT"):
        _SNAPSHOT.write_text("\n".join(current) + "\n", encoding="utf-8")
        return
    expected = _SNAPSHOT.read_text(encoding="utf-8").splitlines()
    added = sorted(set(current) - set(expected))
    removed = sorted(set(expected) - set(current))
    assert current == expected, (
        "Registered routes changed.\n"
        f"  added:   {added}\n"
        f"  removed: {removed}\n"
        "If intentional, regenerate: CIAREN_UPDATE_ROUTE_SNAPSHOT=1 pytest tests/test_route_snapshot.py"
    )


def test_critical_routes_present() -> None:
    # A few load-bearing endpoints that must never silently disappear/rename.
    current = set(_current_routes())
    for route in (
        "GET /health",
        "GET /ready",
        "POST /api/flows/{flow_id}/runs",
        "POST /api/datasets/upload",
        "GET /api/runs/{run_id}",
        "POST /api/connections/{connection_id}/test",
    ):
        assert route in current, f"critical route missing: {route}"
