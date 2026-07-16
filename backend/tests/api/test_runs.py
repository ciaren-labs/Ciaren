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


async def test_run_input_datasets_snapshot_the_dataset_name(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()

    assert run["input_datasets"] == [{"dataset_id": ds["id"], "version_number": 1, "dataset_name": ds["name"]}]


async def test_run_input_dataset_name_survives_a_hard_delete(client: AsyncClient) -> None:
    """Regression: input_dataset_id has no FK (SQLite FK enforcement is off,
    and purge removes the row entirely), so resolving a purged dataset's name
    for a historical run's lineage display used to come up empty. The name is
    now snapshotted onto the run at run time."""
    ds = await _upload(client)
    flow = await _create_flow(client, _full_graph(ds["id"]))
    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()

    deleted = await client.delete(f"/api/datasets/{ds['id']}", params={"purge": True})
    assert deleted.status_code == 204, deleted.text

    fetched = (await client.get(f"/api/runs/{run['id']}")).json()
    assert fetched["input_datasets"][0]["dataset_name"] == ds["name"]


def _named_output_graph(dataset_id: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {"dataset_name": "reusable_out"}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }


async def test_output_registration_success_records_no_warning(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _named_output_graph(ds["id"]))

    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert run["status"] == "success", run.get("error_message")
    # The named output was registered as a reusable dataset...
    names = [d["name"] for d in (await client.get("/api/datasets")).json()]
    assert "reusable_out" in names
    # ...and there is no warning log entry.
    assert all(entry.get("level") != "warning" for entry in (run["logs_json"] or []))


async def test_output_registration_failure_is_observable_but_run_succeeds(client: AsyncClient, monkeypatch) -> None:
    """A failure registering the reusable output dataset must not fail the run, but
    must be surfaced: logged, and recorded as a warning on the run (not silently
    swallowed)."""
    from app.services.dataset_service import DatasetService

    async def _boom(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        raise RuntimeError("registry exploded")

    monkeypatch.setattr(DatasetService, "register_output", _boom)

    ds = await _upload(client)
    flow = await _create_flow(client, _named_output_graph(ds["id"]))

    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    # The run itself still succeeds — the output file was written.
    assert run["status"] == "success", run.get("error_message")
    assert run["output_location"] is not None
    # A warning entry naming the dataset is recorded on the run.
    warnings = [e for e in (run["logs_json"] or []) if e.get("level") == "warning"]
    assert warnings, run["logs_json"]
    assert "reusable_out" in warnings[0]["message"]
    assert warnings[0]["node_id"] == "out1"
    # And it never got registered as a dataset.
    names = [d["name"] for d in (await client.get("/api/datasets")).json()]
    assert "reusable_out" not in names


async def test_output_registration_db_failure_still_finalizes_run(client: AsyncClient, monkeypatch) -> None:
    """A registration failure that dirties the shared DB session (e.g. an
    IntegrityError at flush) must be contained by a savepoint so the run's own
    finalizing commit still succeeds — the run must not 500 or lose its status."""
    from app.db.models.connection import Connection
    from app.services.dataset_service import DatasetService

    async def _flush_conflict(self, *args, **kwargs):  # noqa: ANN001, ANN002, ANN003
        # Two connections with the same (unique) name → IntegrityError on flush,
        # which would deactivate the session's transaction without a savepoint.
        self.db.add(Connection(name="dupe-conn", provider="local"))
        await self.db.flush()
        self.db.add(Connection(name="dupe-conn", provider="local"))
        await self.db.flush()

    monkeypatch.setattr(DatasetService, "register_output", _flush_conflict)

    ds = await _upload(client)
    flow = await _create_flow(client, _named_output_graph(ds["id"]))

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "success", run.get("error_message")
    warnings = [e for e in (run["logs_json"] or []) if e.get("level") == "warning"]
    assert warnings, run["logs_json"]
    # The savepoint rolled back the conflicting insert — no stray connection leaked.
    conns = (await client.get("/api/connections")).json()
    assert "dupe-conn" not in [c["name"] for c in conns]


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


async def test_run_with_misconfigured_node_is_400_and_creates_no_run(client: AsyncClient) -> None:
    ds = await _upload(client)
    # selectColumns with no columns can never execute: the run must be refused
    # up front (no run row, no dataset materialization), naming the node.
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "sel", "type": "selectColumns", "data": {"config": {}, "label": "Pick columns"}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "sel"},
            {"id": "e2", "source": "sel", "target": "out1"},
        ],
    }
    flow = await _create_flow(client, graph)
    before = len((await client.get("/api/runs")).json())

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 400, r.text
    assert "Pick columns" in r.json()["detail"]
    assert len((await client.get("/api/runs")).json()) == before  # no run row


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


async def test_download_output_rejects_malicious_run_id(client: AsyncClient) -> None:
    """run_id with path-traversal characters must be rejected before it's ever used to
    build a filesystem path, even though a real run_id would also 404 via the DB lookup.

    Values containing "/" (or ASGI-normalized to one, like "..") never reach this route
    at all — Starlette 404s them before dispatch, since {run_id} is a single path
    segment — so only single-segment payloads are meaningful cases here.
    """
    for evil in ["run id", "run;id"]:
        r = await client.get(f"/api/runs/{evil}/output?node_id=out1")
        assert r.status_code == 400, f"Expected 400 for run_id={evil!r}, got {r.status_code}"


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
