"""Process-pool recycling on run timeout must never abort concurrent runs.

Recycling shuts the shared pool down with ``cancel_futures=True``, so a timeout
may only recycle immediately when the timed-out run is the last one active;
otherwise the recycle is deferred to the finalizer of the last run to drain.
The pool itself is replaced by a ThreadPoolExecutor here (driving a spawned
process pool from pytest on Windows is flaky); what's under test is the
recycle-decision logic, not the pool.
"""

import time
from concurrent.futures import ThreadPoolExecutor

from httpx import AsyncClient

from app.engine.cancellation import register_run, unregister_run
from app.engine.executor import RunResult
from app.engine.process_pool import (
    defer_pool_recycle,
    pool_recycle_pending,
    recycle_pool_if_pending,
)


def _graph(input_id: str = "in1") -> dict:
    return {
        "nodes": [
            # dataset resolution is patched out, so the dataset_id is arbitrary
            {"id": input_id, "type": "csvInput", "data": {"config": {"dataset_id": "ds-x"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": input_id, "target": "out1"}],
    }


def _fake_run_graph(graph, *args, **kwargs) -> RunResult:
    """Stand-in for run_graph_in_process: sleeps when the graph is marked slow."""
    if any(str(n["id"]).startswith("slow") for n in graph["nodes"]):
        time.sleep(2)
    return RunResult(output_paths={}, node_results=[], error=None)


async def _setup_process_mode(client: AsyncClient, monkeypatch, recycles: list[str]) -> ThreadPoolExecutor:
    from app.core.config import get_settings

    monkeypatch.setenv("CIAREN_EXECUTION_MODE", "process")
    get_settings.cache_clear()

    pool = ThreadPoolExecutor(max_workers=2)
    monkeypatch.setattr("app.services.execution_service.get_process_pool", lambda: pool)
    monkeypatch.setattr("app.services.execution_service.run_graph_in_process", _fake_run_graph)

    async def _no_datasets(db, graph):
        return {}, []

    monkeypatch.setattr("app.services.execution_service.build_dataset_paths", _no_datasets)
    # Record recycles instead of touching the (fake) pool. The immediate path
    # calls execution_service's imported name; the deferred path resolves the
    # name inside app.engine.process_pool.
    monkeypatch.setattr("app.services.execution_service.recycle_process_pool", lambda: recycles.append("immediate"))
    monkeypatch.setattr("app.engine.process_pool.recycle_process_pool", lambda: recycles.append("deferred"))
    return pool


async def _create_flow(client: AsyncClient, graph: dict) -> str:
    r = await client.post("/api/flows", json={"name": "f", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_timeout_with_concurrent_run_defers_recycle(client: AsyncClient, monkeypatch) -> None:
    recycles: list[str] = []
    pool = await _setup_process_mode(client, monkeypatch, recycles)
    register_run("other-run")  # a concurrent run sharing the pool
    try:
        flow_id = await _create_flow(client, _graph("slow-in"))
        r = await client.post(f"/api/flows/{flow_id}/runs", json={"timeout_seconds": 1})
        assert r.status_code == 201, r.text
        run = r.json()
        assert run["status"] == "failed"
        assert "time limit" in run["error_message"]
        # The other run is still active: the pool must NOT have been recycled.
        assert recycles == []
        assert pool_recycle_pending() is True

        # The concurrent run finishing performs the deferred recycle.
        unregister_run("other-run")
        fast_flow = await _create_flow(client, _graph("fast-in"))
        r2 = await client.post(f"/api/flows/{fast_flow}/runs", json={})
        assert r2.json()["status"] == "success"
        assert recycles == ["deferred"]
        assert pool_recycle_pending() is False
    finally:
        unregister_run("other-run")
        recycle_pool_if_pending()  # leave no pending flag for other tests
        pool.shutdown(wait=False)


async def test_timeout_of_only_active_run_recycles_immediately(client: AsyncClient, monkeypatch) -> None:
    recycles: list[str] = []
    pool = await _setup_process_mode(client, monkeypatch, recycles)
    try:
        flow_id = await _create_flow(client, _graph("slow-in"))
        r = await client.post(f"/api/flows/{flow_id}/runs", json={"timeout_seconds": 1})
        run = r.json()
        assert run["status"] == "failed"
        assert recycles == ["immediate"]
        assert pool_recycle_pending() is False
    finally:
        pool.shutdown(wait=False)


def test_deferred_recycle_waits_for_active_runs() -> None:
    from app.engine import process_pool

    swaps: list[str] = []
    original = process_pool.recycle_process_pool
    process_pool.recycle_process_pool = lambda: swaps.append("recycled")  # type: ignore[assignment]
    register_run("busy")
    try:
        defer_pool_recycle()
        assert pool_recycle_pending() is True
        recycle_pool_if_pending()  # a run is still active: must not recycle
        assert swaps == []
        assert pool_recycle_pending() is True

        unregister_run("busy")
        recycle_pool_if_pending()
        assert swaps == ["recycled"]
        assert pool_recycle_pending() is False

        recycle_pool_if_pending()  # idempotent once cleared
        assert swaps == ["recycled"]
    finally:
        process_pool.recycle_process_pool = original  # type: ignore[assignment]
        unregister_run("busy")
        process_pool._clear_pending_recycle()


def test_recycle_and_shutdown_clear_a_pending_flag() -> None:
    from app.engine.process_pool import recycle_process_pool, shutdown_process_pool

    defer_pool_recycle()
    recycle_process_pool()
    assert pool_recycle_pending() is False

    defer_pool_recycle()
    shutdown_process_pool()
    assert pool_recycle_pending() is False
