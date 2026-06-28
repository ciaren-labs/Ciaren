"""The process-wide registry build/reset is thread-safe and reload-consistent.

Runs execute on worker threads while the API can trigger ``reload_plugins`` on the
event loop, so building/resetting the registry must not race into a double-built
or half-reset state, and repeated reloads must not leak bridged plugin nodes into
the engine registry.
"""

from __future__ import annotations

import threading

from app.engine.registry import get_transformation, list_transformation_types
from app.plugins import runtime
from app.plugins.runtime import get_registry, reload_plugins, reset_registry


def test_concurrent_get_registry_returns_one_instance():
    reset_registry()
    results: list[object] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait()  # maximize the chance of a real race on first build
        results.append(get_registry())

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(results) == 8
    # Every thread observed the same cached registry — no double build.
    assert all(r is results[0] for r in results)
    # A known built-in transform resolves through the engine registry intact.
    assert get_transformation("filterRows") is not None


def test_reload_does_not_leak_bridged_types():
    reset_registry()
    get_registry()
    baseline = set(list_transformation_types())
    baseline_bridged = list(runtime._bridged_types)

    # Several reloads in a row must converge to the same engine registry contents
    # (bridged plugin nodes are unregistered before each rebuild, not stacked).
    for _ in range(3):
        reload_plugins()

    assert set(list_transformation_types()) == baseline
    assert runtime._bridged_types == baseline_bridged
