# SPDX-License-Identifier: AGPL-3.0-only
"""Optional multi-process execution for flow runs.

Flow compute is CPU-bound (pandas/polars) and therefore serialised by the GIL
when offloaded to a thread. Running it in a :class:`ProcessPoolExecutor`
instead gives true multi-core parallelism. On Windows (spawn start method) the
function submitted to the pool must be a module-level callable and all of its
arguments must be picklable — both hold here (``run_with_results`` args and the
returned :class:`RunResult` are picklable).
"""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.engine.executor import FlowExecutor, RunResult


def run_graph_in_process(
    graph: dict[str, Any],
    dataset_paths: dict[str, Path],
    output_dir: Path,
    engine_name: str,
    sql_input_paths: dict[str, Path] | None = None,
    storage_input_paths: dict[str, Path] | None = None,
    run_context_data: dict[str, Any] | None = None,
) -> RunResult:
    """Run a flow graph and return its :class:`RunResult`.

    Constructed as a module-level function so it is importable in spawned
    worker processes. It builds a fresh :class:`FlowExecutor` in the worker and
    takes no DB session, so it is safe to run in another process. SQL and storage
    inputs are pre-materialized to parquet in the parent (picklable paths cross here).
    ``run_context_data`` re-establishes the run context (ContextVars don't cross
    process boundaries) so ML nodes can tag their MLflow runs.
    """
    from contextlib import nullcontext

    from app.engine.run_context import run_context

    ctx = (
        run_context(
            flow_id=run_context_data.get("flow_id"),
            run_id=run_context_data.get("run_id"),
            dataset_ids=run_context_data.get("dataset_ids", []),
            tracking_uri=run_context_data.get("tracking_uri"),
        )
        if run_context_data
        else nullcontext()
    )
    with ctx:
        return FlowExecutor().run_with_results(
            graph,
            dataset_paths,
            output_dir,
            engine_name=engine_name,
            sql_input_paths=sql_input_paths,
            storage_input_paths=storage_input_paths,
        )


_pool: ProcessPoolExecutor | None = None


def get_process_pool() -> ProcessPoolExecutor:
    """Return the lazily-created process pool singleton.

    Sized from ``SCHEDULER_MAX_CONCURRENT_RUNS`` (min 1). This single-process
    app creates the pool from the event loop thread, so a simple module global
    is sufficient.
    """
    global _pool
    if _pool is None:
        max_workers = max(1, get_settings().SCHEDULER_MAX_CONCURRENT_RUNS)
        # Bootstrap plugins in each worker so plugin-contributed nodes resolve in
        # `process` mode too (the parent's in-memory registry isn't inherited).
        _pool = ProcessPoolExecutor(max_workers=max_workers, initializer=_init_worker)
    return _pool


def _init_worker() -> None:
    """Process-pool worker initializer: load + bridge plugins. Best-effort."""
    from app.plugins import ensure_plugins_loaded

    ensure_plugins_loaded()


def shutdown_process_pool() -> None:
    """Shut down the process pool (if any) and reset the singleton."""
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=True)
        _pool = None


def recycle_process_pool() -> None:
    """Discard the current pool without waiting, so a fresh one is created lazily.

    Used after a run timeout in process mode. The stdlib pool cannot force-kill a
    worker mid-task, but dropping the pool stops new work queueing behind a hung
    worker and gives subsequent runs fresh capacity; the orphaned worker is
    reaped once its (abandoned) task returns.
    """
    global _pool
    if _pool is not None:
        _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None
