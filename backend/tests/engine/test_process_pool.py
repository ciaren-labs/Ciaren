"""Tests for the optional ProcessPoolExecutor execution mode.

The end-to-end flow is exercised by calling ``run_graph_in_process`` directly
(synchronously) — that already crosses the picklable-boundary contract that the
real pool relies on, without the flakiness of driving a spawned pool from
within pytest on Windows. The singleton lifecycle and the EXECUTION_MODE
validation are covered separately.
"""

from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

from app.engine.executor import dataset_ref_key
from app.engine.process_pool import (
    get_process_pool,
    recycle_process_pool,
    run_graph_in_process,
    shutdown_process_pool,
)


def _paths(**by_id: Path) -> dict[str, Path]:
    """Key dataset paths the way the engine resolves them (id -> 'id:latest')."""
    return {dataset_ref_key(ds_id, None): path for ds_id, path in by_id.items()}


def _pipeline_graph() -> dict:
    """csvInput -> dropNulls -> csvOutput."""
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": "ds1"}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }


def test_run_graph_in_process_runs_full_pipeline(tmp_path: Path) -> None:
    input_csv = tmp_path / "in.csv"
    pd.DataFrame({"a": [1, 2, None], "b": [4, 5, 6]}).to_csv(input_csv, index=False)
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    result = run_graph_in_process(_pipeline_graph(), _paths(ds1=input_csv), out_dir, "pandas")

    assert result.error is None
    assert "out1" in result.output_paths
    out_file = result.output_paths["out1"]
    assert out_file.exists()
    assert len(pd.read_csv(out_file)) == 2  # one null row dropped


def test_get_process_pool_is_singleton_and_resettable() -> None:
    try:
        first = get_process_pool()
        second = get_process_pool()
        assert first is second
        assert isinstance(first, ProcessPoolExecutor)
    finally:
        shutdown_process_pool()

    third = get_process_pool()
    try:
        assert third is not first  # a fresh pool after shutdown
    finally:
        shutdown_process_pool()


def test_recycle_process_pool_replaces_instance() -> None:
    first = get_process_pool()
    try:
        recycle_process_pool()  # drop without waiting
        second = get_process_pool()
        assert second is not first  # a fresh pool is created lazily
    finally:
        shutdown_process_pool()


async def test_run_with_unknown_execution_mode_is_400(client, monkeypatch) -> None:
    import io

    from app.core.config import get_settings

    monkeypatch.setenv("FLOWFRAME_EXECUTION_MODE", "bogus")
    get_settings.cache_clear()

    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2]}).to_csv(buf, index=False)
    ds = (
        await client.post(
            "/api/datasets/upload",
            files={"file": ("d.csv", buf.getvalue(), "text/csv")},
        )
    ).json()
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": graph})).json()

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 400, r.text
