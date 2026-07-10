"""Process-pool recycling on run timeout must never abort concurrent runs.

Recycling shuts the shared pool down with ``cancel_futures=True``, so a timeout
may only recycle immediately when the timed-out run is the last one active;
otherwise the recycle is deferred to the finalizer of the last run to drain.
The pool itself is replaced by a ThreadPoolExecutor here (driving a spawned
process pool from pytest on Windows is flaky); what's under test is the
recycle-decision logic, not the pool.
"""

import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.run import FlowRun
from app.engine.cancellation import register_run, unregister_run
from app.engine.executor import RunResult
from app.engine.process_pool import (
    defer_pool_recycle,
    pool_recycle_pending,
    recycle_pool_if_pending,
)
from app.schemas.run import FlowRunCreate
from app.services.execution_service import ExecutionService


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


async def test_process_run_carries_plugin_generation(client: AsyncClient, monkeypatch) -> None:
    """Process-mode submissions must carry the parent's plugin-state generation,
    the wire that lets a reused worker apply permission revocations."""
    from app.plugins import plugin_state_generation

    recycles: list[str] = []
    pool = await _setup_process_mode(client, monkeypatch, recycles)
    seen: list[object] = []

    def _capture(graph, *args, **kwargs) -> RunResult:
        seen.append(args[7])  # ... ctx_data, settings_overrides, plugin_generation
        return RunResult(output_paths={}, node_results=[], error=None)

    monkeypatch.setattr("app.services.execution_service.run_graph_in_process", _capture)
    try:
        flow_id = await _create_flow(client, _graph())
        r = await client.post(f"/api/flows/{flow_id}/runs", json={})
        assert r.json()["status"] == "success"
        assert seen == [plugin_state_generation()]
    finally:
        pool.shutdown(wait=False)


async def _setup_single_slot_pool(client: AsyncClient, monkeypatch, recycles: list[str]) -> tuple:
    """Process mode with a 1-worker fake pool, so a second run genuinely queues,
    and a release event controlling how long the 'slow' compute occupies it."""
    from app.core.config import get_settings

    monkeypatch.setenv("CIAREN_EXECUTION_MODE", "process")
    get_settings.cache_clear()

    release = threading.Event()

    def _blocking_run(graph, *args, **kwargs) -> RunResult:
        if any(str(n["id"]).startswith("slow") for n in graph["nodes"]):
            release.wait(10)
        return RunResult(output_paths={}, node_results=[], error=None)

    pool = ThreadPoolExecutor(max_workers=1)
    monkeypatch.setattr("app.services.execution_service.get_process_pool", lambda: pool)
    monkeypatch.setattr("app.services.execution_service.run_graph_in_process", _blocking_run)

    async def _no_datasets(db, graph):
        return {}, []

    monkeypatch.setattr("app.services.execution_service.build_dataset_paths", _no_datasets)
    monkeypatch.setattr("app.services.execution_service.recycle_process_pool", lambda: recycles.append("immediate"))
    monkeypatch.setattr("app.engine.process_pool.recycle_process_pool", lambda: recycles.append("deferred"))
    return pool, release


async def test_queued_run_cancel_frees_slot_without_recycle(client: AsyncClient, db_session, monkeypatch) -> None:
    """A run still queued behind a busy worker is cancellable directly (its
    pool future never started) — no pool recycle, no harm to the running run.
    This was the audit's starvation finding: before, cancelling was refused
    while another run was active."""
    recycles: list[str] = []
    pool, release = await _setup_single_slot_pool(client, monkeypatch, recycles)
    try:
        flow_a = await _create_flow(client, _graph("slow-a"))
        flow_b = await _create_flow(client, _graph("fast-b"))
        task_a = asyncio.create_task(ExecutionService(db_session).run(flow_a, FlowRunCreate()))
        await asyncio.sleep(0.3)  # A occupies the pool's only worker
        task_b = asyncio.create_task(ExecutionService(db_session).run(flow_b, FlowRunCreate()))
        await asyncio.sleep(0.3)  # B is flushed and queued behind A

        run_b_id = (await db_session.execute(select(FlowRun.id).where(FlowRun.flow_id == flow_b))).scalar_one()
        resp = await ExecutionService(db_session).cancel(run_b_id)
        assert resp["status"] == "cancelling"

        result_b = await task_b  # finalizes normally — the task itself was never cancelled
        assert result_b.status == "cancelled"
        assert recycles == []  # the shared pool was never touched

        release.set()
        result_a = await task_a
        assert result_a.status == "success"  # the running run was unharmed
        assert recycles == []
        assert pool_recycle_pending() is False
    finally:
        release.set()
        pool.shutdown(wait=False)


async def test_timeout_of_queued_run_needs_no_recycle(client: AsyncClient, db_session, monkeypatch) -> None:
    """A queued run hitting its time limit cancels its never-started future:
    no worker is hung, so neither an immediate nor a deferred recycle fires."""
    recycles: list[str] = []
    pool, release = await _setup_single_slot_pool(client, monkeypatch, recycles)
    try:
        flow_a = await _create_flow(client, _graph("slow-a"))
        flow_b = await _create_flow(client, _graph("fast-b"))
        task_a = asyncio.create_task(ExecutionService(db_session).run(flow_a, FlowRunCreate()))
        await asyncio.sleep(0.3)
        task_b = asyncio.create_task(ExecutionService(db_session).run(flow_b, FlowRunCreate(timeout_seconds=1)))

        result_b = await task_b
        assert result_b.status == "failed"
        assert "time limit" in (result_b.error_message or "")
        assert recycles == []  # queued task cancelled — nothing to recycle
        assert pool_recycle_pending() is False

        release.set()
        result_a = await task_a
        assert result_a.status == "success"
    finally:
        release.set()
        pool.shutdown(wait=False)


async def _setup_process_mode_slow_materialize(
    client: AsyncClient, monkeypatch, recycles: list[str], gate: asyncio.Event
) -> tuple[ThreadPoolExecutor, list[str]]:
    """Process mode where dataset resolution blocks on ``gate`` — opens a real
    window between a run being registered (cancellable) and its compute ever
    reaching the pool, so a cancel arriving in that window can be tested."""
    from app.core.config import get_settings

    monkeypatch.setenv("CIAREN_EXECUTION_MODE", "process")
    get_settings.cache_clear()

    pool = ThreadPoolExecutor(max_workers=2)
    submitted: list[str] = []

    def _record_submission(graph, *args, **kwargs) -> RunResult:
        submitted.append(graph["nodes"][0]["id"])
        return RunResult(output_paths={}, node_results=[], error=None)

    monkeypatch.setattr("app.services.execution_service.get_process_pool", lambda: pool)
    monkeypatch.setattr("app.services.execution_service.run_graph_in_process", _record_submission)

    async def _slow_datasets(db, graph):
        await gate.wait()
        return {}, []

    monkeypatch.setattr("app.services.execution_service.build_dataset_paths", _slow_datasets)
    monkeypatch.setattr("app.services.execution_service.recycle_process_pool", lambda: recycles.append("immediate"))
    monkeypatch.setattr("app.engine.process_pool.recycle_process_pool", lambda: recycles.append("deferred"))
    return pool, submitted


async def test_cancel_during_materialization_skips_submission(client: AsyncClient, db_session, monkeypatch) -> None:
    """A cancel arriving while inputs are still materializing (before the
    compute is ever submitted to the pool) has no future to cancel and no
    worker to abandon. It must not be refused just because another run shares
    the pool, must not recycle the pool, and the run must finish 'cancelled'
    instead of proceeding to execute anyway."""
    recycles: list[str] = []
    gate = asyncio.Event()
    pool, submitted = await _setup_process_mode_slow_materialize(client, monkeypatch, recycles, gate)
    register_run("other-run")  # a second active run, so active_run_count() > 1
    try:
        flow_id = await _create_flow(client, _graph())
        run_task = asyncio.create_task(ExecutionService(db_session).run(flow_id, FlowRunCreate()))
        await asyncio.sleep(0.1)  # the row is flushed and materialization is blocked on `gate`

        run_id = (await db_session.execute(select(FlowRun.id).where(FlowRun.flow_id == flow_id))).scalar_one()
        resp = await ExecutionService(db_session).cancel(run_id)
        assert resp["status"] == "cancelling"

        gate.set()  # let materialization finish now that the cancel is recorded
        result = await run_task
        assert result.status == "cancelled"
        assert submitted == []  # the graph was never submitted to the pool
        assert recycles == []  # nothing was ever touched, so nothing needed recycling
    finally:
        unregister_run("other-run")
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
