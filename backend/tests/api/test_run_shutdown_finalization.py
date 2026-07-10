"""A hard-cancelled run task (scheduler shutdown grace expired, server stopping)
must never leave its FlowRun committed as status="running".

`except Exception` doesn't catch asyncio.CancelledError, so before the fix the
finalizer committed the row still "running" — stuck until the next boot's
orphan recovery, or forever if the scheduler was restarted without a process
restart.
"""

import asyncio
import threading

from httpx import AsyncClient
from sqlalchemy import select

from app.db.models.run import FlowRun
from app.engine.cancellation import request_cancel_all
from app.engine.executor import RunResult
from app.schemas.run import FlowRunCreate
from app.services.execution_service import ExecutionService

_GRAPH = {
    "nodes": [
        # dataset resolution is patched out, so the dataset_id is arbitrary
        {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds-x"}}},
        {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
    ],
    "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
}


async def _create_flow(client: AsyncClient) -> str:
    r = await client.post("/api/flows", json={"name": "f", "graph_json": _GRAPH})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _patch_slow_compute(monkeypatch, release: threading.Event) -> None:
    """Replace the executor with one that blocks until `release` is set, and
    dataset resolution with a no-op."""

    class _SlowExecutor:
        def __init__(self, events=None) -> None:
            pass

        def run_with_results(self, *args, **kwargs) -> RunResult:
            release.wait(10)
            return RunResult(output_paths={}, node_results=[], error=None)

    monkeypatch.setattr("app.services.execution_service.FlowExecutor", _SlowExecutor)

    async def _no_datasets(db, graph):
        return {}, []

    monkeypatch.setattr("app.services.execution_service.build_dataset_paths", _no_datasets)


async def _run_rows(db_session) -> list[FlowRun]:
    return list((await db_session.execute(select(FlowRun))).scalars().all())


async def test_hard_cancel_finalizes_run_as_failed(client: AsyncClient, db_session, monkeypatch) -> None:
    release = threading.Event()
    _patch_slow_compute(monkeypatch, release)
    try:
        flow_id = await _create_flow(client)
        task = asyncio.create_task(ExecutionService(db_session).run(flow_id, FlowRunCreate()))
        await asyncio.sleep(0.3)  # let the run register and submit its compute
        task.cancel()
        (outcome,) = await asyncio.gather(task, return_exceptions=True)
        assert isinstance(outcome, asyncio.CancelledError)  # cancellation still propagates

        runs = await _run_rows(db_session)
        assert len(runs) == 1
        run = runs[0]
        assert run.status == "failed"  # never "running"
        assert "interrupted" in (run.error_message or "")
        assert run.finished_at is not None
    finally:
        release.set()


async def test_hard_cancel_after_cooperative_signal_finalizes_as_cancelled(
    client: AsyncClient, db_session, monkeypatch
) -> None:
    """Shutdown first asks runs to stop (request_cancel_all), then hard-cancels:
    the run must finalize as a deliberate 'cancelled', not a failure."""
    release = threading.Event()
    _patch_slow_compute(monkeypatch, release)
    try:
        flow_id = await _create_flow(client)
        task = asyncio.create_task(ExecutionService(db_session).run(flow_id, FlowRunCreate()))
        await asyncio.sleep(0.3)
        assert request_cancel_all() == 1  # the graceful phase of shutdown
        task.cancel()  # the grace period "expired"
        await asyncio.gather(task, return_exceptions=True)

        (run,) = await _run_rows(db_session)
        assert run.status == "cancelled"
        assert run.finished_at is not None
    finally:
        release.set()


async def test_early_failure_with_cancel_requested_finalizes_cleanly(
    client: AsyncClient, db_session, monkeypatch
) -> None:
    """A failure during input materialization with a cancel already requested
    used to hit a NameError (compute_finished unbound) inside the exception
    handler — which skipped finalization entirely and committed the row as
    "running". It must finalize as 'cancelled' (the cancel is honored)."""

    async def _cancel_then_fail(db, graph):
        request_cancel_all()  # the user cancels while inputs materialize
        raise RuntimeError("input materialization blew up")

    monkeypatch.setattr("app.services.execution_service.build_dataset_paths", _cancel_then_fail)
    flow_id = await _create_flow(client)

    run = await ExecutionService(db_session).run(flow_id, FlowRunCreate())
    assert run.status == "cancelled"
    (row,) = await _run_rows(db_session)
    assert row.status == "cancelled"
    assert row.finished_at is not None
