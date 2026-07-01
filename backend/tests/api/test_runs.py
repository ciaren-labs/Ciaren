"""
Flow run endpoint tests.

  POST /api/flows/{flow_id}/runs
  GET  /api/runs/{run_id}
"""

import io
import time
from pathlib import Path
from typing import Any

import pandas as pd
import pytest
from httpx import AsyncClient

from app.engine.executor import FlowExecutor, RunResult

ROWS: list[dict[str, Any]] = [
    {"name": "Alice", "age": 30},
    {"name": "Bob", "age": None},
    {"name": "Charlie", "age": 35},
]


async def _upload(client: AsyncClient) -> dict:
    buf = io.BytesIO()
    pd.DataFrame(ROWS).to_csv(buf, index=False)
    r = await client.post(
        "/api/datasets/upload",
        files={"file": ("people.csv", buf.getvalue(), "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _create_flow(client: AsyncClient, graph: dict) -> dict:
    r = await client.post("/api/flows", json={"name": "f", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


def _full_graph(dataset_id: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }


async def test_run_flow_success(client: AsyncClient, tmp_path: Path) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "success"
    assert run["output_location"] is not None
    assert run["started_at"] is not None
    assert run["finished_at"] is not None
    # output_location must be relative, never an absolute server path
    assert not Path(run["output_location"]).is_absolute()

    # The written output should contain only the 2 non-null rows.
    out_file = tmp_path / "outputs" / run["output_location"]
    assert out_file.exists()
    assert len(pd.read_csv(out_file)) == 2


async def test_run_records_node_results_and_dataset(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))

    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    # input_dataset_id is defaulted from the resolved input even though we didn't pass one.
    assert run["input_dataset_id"] == ds["id"]

    results = {r["node_id"]: r for r in run["node_results"]}
    assert results["in1"]["status"] == "success"
    assert results["in1"]["rows"] == 3
    assert results["drop"]["rows"] == 2  # null row dropped
    assert results["in1"]["columns"] == ["name", "age"]
    assert results["in1"]["sample"]  # preview rows recorded


async def test_run_flow_records_failure(client: AsyncClient) -> None:
    ds = await _upload(client)
    # Reference a column that doesn't exist -> execution error captured on the run.
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "drop", "type": "dropColumns", "data": {"config": {"columns": ["ghost"]}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }
    flow = await _create_flow(client, graph)
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "failed"
    assert run["error_message"]


async def test_run_on_polars_engine_records_engine(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"engine": "polars"})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["engine"] == "polars"
    assert run["status"] == "success"


async def test_retry_creates_a_new_run_with_same_config(client: AsyncClient) -> None:
    ds = await _upload(client)
    graph = {**_full_graph(ds["id"]), "engine": "pandas"}
    flow = await _create_flow(client, graph)
    first = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert first["engine"] == "pandas"

    r = await client.post(f"/api/runs/{first['id']}/retry")
    assert r.status_code == 201, r.text
    retried = r.json()
    assert retried["id"] != first["id"]  # brand-new run id
    assert retried["engine"] == "pandas"  # same config
    assert retried["input_dataset_id"] == first["input_dataset_id"]
    assert retried["trigger"] == "retry"
    assert retried["status"] == "success"


async def test_retry_unknown_run_is_404(client: AsyncClient) -> None:
    r = await client.post("/api/runs/nope/retry")
    assert r.status_code == 404


async def test_flow_last_run_at_populated_after_run(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    # No runs yet → last_run_at is null in the flow list.
    listed = {f["id"]: f for f in (await client.get("/api/flows")).json()}
    assert listed[flow["id"]]["last_run_at"] is None
    await client.post(f"/api/flows/{flow['id']}/runs", json={})
    listed2 = {f["id"]: f for f in (await client.get("/api/flows")).json()}
    assert listed2[flow["id"]]["last_run_at"] is not None


async def test_run_honors_flow_saved_engine(client: AsyncClient) -> None:
    # The flow saves a pandas preference in graph_json; a run with no explicit
    # engine should honor it instead of falling back to the polars default.
    ds = await _upload(client)
    graph = {**_full_graph(ds["id"]), "engine": "pandas"}
    flow = await _create_flow(client, graph)
    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert run["engine"] == "pandas"


async def test_explicit_engine_overrides_saved_engine(client: AsyncClient) -> None:
    ds = await _upload(client)
    graph = {**_full_graph(ds["id"]), "engine": "pandas"}
    flow = await _create_flow(client, graph)
    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={"engine": "polars"})).json()
    assert run["engine"] == "polars"


async def test_run_with_unknown_engine_is_400(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"engine": "spark"})
    assert r.status_code == 400


async def test_run_defaults_to_polars_engine(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert run["engine"] == "polars"


async def test_run_times_out(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))

    def slow(self: FlowExecutor, *args: Any, **kwargs: Any) -> RunResult:
        time.sleep(2)  # longer than the 1s limit below
        return RunResult({}, [], None)

    monkeypatch.setattr(FlowExecutor, "run_with_results", slow)
    monkeypatch.setenv("CIAREN_RUN_TIMEOUT_SECONDS", "1")
    from app.core.config import get_settings

    get_settings.cache_clear()

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "failed"
    assert "time limit" in run["error_message"]


async def test_run_flow_missing_flow_is_404(client: AsyncClient) -> None:
    r = await client.post("/api/flows/nope/runs", json={})
    assert r.status_code == 404


async def test_get_run(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    created = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()

    r = await client.get(f"/api/runs/{created['id']}")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == created["id"]
    assert r.json()["status"] == "success"


async def test_get_run_missing_is_404(client: AsyncClient) -> None:
    r = await client.get("/api/runs/nope")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/runs — history list + filters
# ---------------------------------------------------------------------------


async def test_list_runs_returns_summaries_with_flow_name(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    await client.post(f"/api/flows/{flow['id']}/runs", json={})

    r = await client.get("/api/runs")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["flow_name"] == flow["name"]
    assert rows[0]["status"] == "success"
    # The summary must not carry the heavy per-node payload.
    assert "node_results" not in rows[0]


async def test_list_runs_rejects_invalid_sort_params(client: AsyncClient) -> None:
    """sort_by and sort_order must be validated — unknown values return 422."""
    r = await client.get("/api/runs?sort_by=injected_column")
    assert r.status_code == 422

    r = await client.get("/api/runs?sort_order=INVALID")
    assert r.status_code == 422


async def test_list_runs_rejects_out_of_bounds_limit(client: AsyncClient) -> None:
    """limit must be 1–10000; values outside that range return 422."""
    r = await client.get("/api/runs?limit=0")
    assert r.status_code == 422

    r = await client.get("/api/runs?limit=99999")
    assert r.status_code == 422

    r = await client.get("/api/runs?limit=100")
    assert r.status_code == 200


async def test_download_output_rejects_malicious_node_id(client: AsyncClient, tmp_path: Path) -> None:
    """node_id with path-traversal characters must be rejected before touching the filesystem."""
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    run_id = run["id"]

    for evil in ["../etc/passwd", "../../secret", "foo/bar", "node id"]:
        r = await client.get(f"/api/runs/{run_id}/output?node_id={evil}")
        assert r.status_code == 400, f"Expected 400 for node_id={evil!r}, got {r.status_code}"


async def test_list_runs_filters_by_flow_status_and_dataset(client: AsyncClient) -> None:
    ds = await _upload(client)
    ok_flow = await _create_flow(client, _full_graph(ds["id"]))
    bad_graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "drop", "type": "dropColumns", "data": {"config": {"columns": ["ghost"]}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }
    bad_flow = await _create_flow(client, bad_graph)
    await client.post(f"/api/flows/{ok_flow['id']}/runs", json={})
    await client.post(f"/api/flows/{bad_flow['id']}/runs", json={})

    assert len(((await client.get("/api/runs")).json())) == 2
    assert len((await client.get("/api/runs?status=success")).json()) == 1
    assert len((await client.get("/api/runs?status=failed")).json()) == 1
    by_flow = (await client.get(f"/api/runs?flow_id={ok_flow['id']}")).json()
    assert [row["flow_id"] for row in by_flow] == [ok_flow["id"]]
    by_ds = (await client.get(f"/api/runs?dataset_id={ds['id']}")).json()
    assert len(by_ds) == 2  # both flows read the same dataset
