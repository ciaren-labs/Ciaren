"""Process-pool workers must pick up plugin-state changes (permission
revocations, disables) without a pool recycle.

Workers bootstrap plugins once at spawn; before the fix a revoked grant stayed
baked into their bridged plugin nodes for the worker's whole life — a
permission bypass. The parent now bumps a generation on every plugin reload
and passes it per task; a stale worker re-reads the persisted state before
executing.
"""

from pathlib import Path

import pandas as pd

from app.engine import process_pool
from app.engine.executor import dataset_ref_key
from app.engine.process_pool import _sync_worker_plugins, run_graph_in_process
from app.plugins import plugin_state_generation, reload_plugins, reset_registry


def test_generation_bumps_on_reload_and_reset() -> None:
    g0 = plugin_state_generation()
    reload_plugins()
    g1 = plugin_state_generation()
    assert g1 > g0
    reset_registry()
    assert plugin_state_generation() > g1


def _record_reloads(monkeypatch) -> list[str]:
    calls: list[str] = []
    monkeypatch.setattr("app.plugins.reset_registry", lambda: calls.append("reset"))
    monkeypatch.setattr("app.plugins.ensure_plugins_loaded", lambda: calls.append("load"))
    return calls


def test_sync_reloads_only_when_generation_moved(monkeypatch) -> None:
    calls = _record_reloads(monkeypatch)
    monkeypatch.setattr(process_pool, "_worker_plugin_generation", 5)

    _sync_worker_plugins(5)  # up to date — no reload
    assert calls == []

    _sync_worker_plugins(None)  # direct/sync callers opt out — no reload
    assert calls == []

    _sync_worker_plugins(6)  # the parent reloaded — re-sync
    assert calls == ["reset", "load"]
    assert process_pool._worker_plugin_generation == 6

    calls.clear()
    _sync_worker_plugins(6)  # already synced — idempotent
    assert calls == []


def test_failed_sync_is_retried_on_the_next_task(monkeypatch) -> None:
    def _boom() -> None:
        raise RuntimeError("plugin dir unreadable")

    monkeypatch.setattr("app.plugins.reset_registry", _boom)
    monkeypatch.setattr(process_pool, "_worker_plugin_generation", 5)

    _sync_worker_plugins(6)  # must not raise (best-effort) ...
    assert process_pool._worker_plugin_generation == 5  # ... and not record success

    calls = _record_reloads(monkeypatch)
    _sync_worker_plugins(6)  # the next task retries the sync
    assert calls == ["reset", "load"]
    assert process_pool._worker_plugin_generation == 6


def test_run_graph_in_process_syncs_before_executing(tmp_path: Path, monkeypatch) -> None:
    """The per-task entry point performs the sync with the generation it was
    handed — the wire that carries a revocation into the worker."""
    synced: list[int | None] = []
    monkeypatch.setattr(process_pool, "_sync_worker_plugins", synced.append)

    input_csv = tmp_path / "in.csv"
    pd.DataFrame({"a": [1, None]}).to_csv(input_csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    paths = {dataset_ref_key("ds1", None): input_csv}

    result = run_graph_in_process(graph, paths, out_dir, "pandas", plugin_generation=42)

    assert result.error is None
    assert synced == [42]
