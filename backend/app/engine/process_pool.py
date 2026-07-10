# SPDX-License-Identifier: AGPL-3.0-only
"""Optional multi-process execution for flow runs.

Flow compute is CPU-bound (pandas/polars) and therefore serialised by the GIL
when offloaded to a thread. Running it in a :class:`ProcessPoolExecutor`
instead gives true multi-core parallelism. On Windows (spawn start method) the
function submitted to the pool must be a module-level callable and all of its
arguments must be picklable — both hold here (``run_with_results`` args and the
returned :class:`RunResult` are picklable).
"""

import logging
import threading
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.engine.executor import FlowExecutor, RunResult

logger = logging.getLogger("ciaren.process_pool")


def run_graph_in_process(
    graph: dict[str, Any],
    dataset_paths: dict[str, Path],
    output_dir: Path,
    engine_name: str,
    sql_input_paths: dict[str, Path] | None = None,
    storage_input_paths: dict[str, Path] | None = None,
    run_context_data: dict[str, Any] | None = None,
    settings_overrides: dict[str, Any] | None = None,
    plugin_generation: int | None = None,
) -> RunResult:
    """Run a flow graph and return its :class:`RunResult`.

    Constructed as a module-level function so it is importable in spawned
    worker processes. It builds a fresh :class:`FlowExecutor` in the worker and
    takes no DB session, so it is safe to run in another process. SQL and storage
    inputs are pre-materialized to parquet in the parent (picklable paths cross here).
    ``run_context_data`` re-establishes the run context (ContextVars don't cross
    process boundaries) so ML nodes can tag their MLflow runs.
    ``settings_overrides`` mirrors the parent's Settings-page overrides into this
    worker (its ``get_settings()`` is built from env only), so runtime-edited
    values like the ML guardrail limits hold in process mode too. Synced per
    task — with ``reset_missing`` — because workers are reused across runs.
    ``plugin_generation`` is the parent's plugin-state generation at submit
    time; when it is ahead of what this worker last synced to, the worker
    re-reads the persisted plugin state (see :func:`_sync_worker_plugins`) so a
    permission revocation or plugin disable is honored without a pool recycle.
    """
    from contextlib import nullcontext

    from app.core.runtime_settings import apply_overrides
    from app.engine.run_context import run_context

    apply_overrides(settings_overrides or {}, reset_missing=True)
    _sync_worker_plugins(plugin_generation)

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
        from app.plugins import plugin_state_generation

        max_workers = max(1, get_settings().SCHEDULER_MAX_CONCURRENT_RUNS)
        # Bootstrap plugins in each worker so plugin-contributed nodes resolve in
        # `process` mode too (the parent's in-memory registry isn't inherited).
        # The generation initarg records which plugin state that bootstrap read,
        # so per-task syncs only reload when the parent's state moved on.
        _pool = ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=_init_worker,
            initargs=(plugin_state_generation(),),
        )
    return _pool


#: Plugin-state generation this worker process last synced its registry to.
#: Lives in the worker's copy of this module; ``None`` until the initializer runs.
_worker_plugin_generation: int | None = None


def _init_worker(plugin_generation: int) -> None:
    """Process-pool worker initializer: load + bridge plugins. Best-effort."""
    global _worker_plugin_generation
    from app.plugins import ensure_plugins_loaded

    ensure_plugins_loaded()
    _worker_plugin_generation = plugin_generation


def _sync_worker_plugins(plugin_generation: int | None) -> None:
    """Re-read the persisted plugin state when the parent reloaded it.

    Workers are reused across runs, so the grants baked into their bridged
    plugin nodes at spawn time would otherwise outlive a permission revocation
    or a plugin disable until the whole pool was recycled — a permission
    bypass. The parent bumps its generation on every reload and passes it per
    task; a mismatch here rebuilds this worker's registry from the state file
    (which the API saves before reloading). Best-effort like the initializer:
    a plugin failure must not break core execution. ``None`` (direct/sync
    callers, tests) skips the check.
    """
    global _worker_plugin_generation
    if plugin_generation is None or plugin_generation == _worker_plugin_generation:
        return
    from app.plugins import ensure_plugins_loaded, reset_registry

    try:
        reset_registry()
        ensure_plugins_loaded()
        # Recorded only on success, so a failed sync is retried on the next task
        # rather than silently leaving revoked grants in force.
        _worker_plugin_generation = plugin_generation
    except Exception:  # noqa: BLE001 — plugin trouble must not fail the run
        logger.warning("Plugin re-sync in worker failed; continuing with the previous plugin state.", exc_info=True)


def shutdown_process_pool() -> None:
    """Shut down the process pool (if any) and reset the singleton."""
    global _pool
    _clear_pending_recycle()
    if _pool is not None:
        _pool.shutdown(wait=True)
        _pool = None


def recycle_process_pool() -> None:
    """Discard the current pool without waiting, so a fresh one is created lazily.

    Used after a run timeout/cancel in process mode when no other run shares the
    pool — ``shutdown(cancel_futures=True)`` aborts every queued future, so
    recycling under a concurrent run would kill that innocent run too (callers
    must use :func:`defer_pool_recycle` instead in that case). The stdlib pool
    cannot force-kill a worker mid-task, but dropping the pool stops new work
    queueing behind a hung worker and gives subsequent runs fresh capacity; the
    orphaned worker is reaped once its (abandoned) task returns.
    """
    global _pool
    _clear_pending_recycle()
    if _pool is not None:
        _pool.shutdown(wait=False, cancel_futures=True)
        _pool = None


# A timed-out run that shares the pool with other in-flight runs cannot recycle
# immediately (that would abort them); it marks the recycle pending and the last
# run to finish performs it.
_recycle_pending = False
_recycle_lock = threading.Lock()


def _clear_pending_recycle() -> None:
    global _recycle_pending
    with _recycle_lock:
        _recycle_pending = False


def defer_pool_recycle() -> None:
    """Mark the pool for recycling once the last active run drains.

    Used when a run times out in process mode while other runs share the pool:
    their futures must not be cancelled with it, so the abandoned worker keeps
    its slot until the pool goes idle and :func:`recycle_pool_if_pending` swaps
    it out."""
    global _recycle_pending
    with _recycle_lock:
        _recycle_pending = True


def recycle_pool_if_pending() -> None:
    """Perform a deferred recycle once no runs are active (no-op otherwise).

    Called after every run finishes; cheap when nothing is pending."""
    global _recycle_pending
    from app.engine.cancellation import active_run_count

    with _recycle_lock:
        if not _recycle_pending or active_run_count() > 0:
            return
        _recycle_pending = False
    recycle_process_pool()


def pool_recycle_pending() -> bool:
    """Whether a deferred recycle is waiting for the pool to go idle."""
    with _recycle_lock:
        return _recycle_pending
