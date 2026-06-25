"""End-to-end tests for flow parameters: per-run overrides, defaults, validation,
and per-schedule overrides feeding a manual ("run now") fire.
"""

import io
from typing import Any

import pandas as pd
from httpx import AsyncClient

ROWS: list[dict[str, Any]] = [{"v": 1}, {"v": 2}, {"v": 3}, {"v": 4}, {"v": 5}]


async def _upload(client: AsyncClient) -> dict:
    buf = io.BytesIO()
    pd.DataFrame(ROWS).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": ("nums.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


def _parametrized_graph(dataset_id: str) -> dict:
    """csvInput -> limitRows(n={{ keep }}) -> csvOutput, with `keep` defaulting to 2."""
    return {
        "parameters": [{"name": "keep", "type": "integer", "default": 2}],
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "lim", "type": "limitRows", "data": {"config": {"n": "{{ keep }}"}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "lim"},
            {"id": "e2", "source": "lim", "target": "out1"},
        ],
    }


async def _create_flow(client: AsyncClient, graph: dict) -> dict:
    r = await client.post("/api/flows", json={"name": "p", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


async def test_run_uses_parameter_default(client: AsyncClient, tmp_path) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _parametrized_graph(ds["id"]))

    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert run["status"] == "success", run
    assert run["parameters"] == {"keep": 2}
    out = pd.read_csv(tmp_path / "outputs" / run["output_location"])
    assert len(out) == 2  # default keep=2


async def test_run_override_changes_output(client: AsyncClient, tmp_path) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _parametrized_graph(ds["id"]))

    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={"parameters": {"keep": 4}})).json()
    assert run["status"] == "success", run
    assert run["parameters"] == {"keep": 4}
    out = pd.read_csv(tmp_path / "outputs" / run["output_location"])
    assert len(out) == 4

    # The stored snapshot is the *resolved* graph (typed int substituted in).
    assert run["graph_snapshot"]["nodes"][1]["data"]["config"]["n"] == 4


async def test_unknown_override_is_400(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _parametrized_graph(ds["id"]))
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"parameters": {"nope": 1}})
    assert r.status_code == 400, r.text


async def test_bad_type_override_is_400(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _parametrized_graph(ds["id"]))
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"parameters": {"keep": "abc"}})
    assert r.status_code == 400, r.text


async def test_preview_honors_parameters(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _parametrized_graph(ds["id"]))
    r = await client.post(
        f"/api/flows/{flow['id']}/preview",
        json={"node_id": "lim", "parameters": {"keep": 3}},
    )
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 3


async def test_schedule_parameter_override_on_run_now(client: AsyncClient, tmp_path) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _parametrized_graph(ds["id"]))

    sched = (
        await client.post(
            f"/api/flows/{flow['id']}/schedules",
            json={"cron": "0 0 * * *", "parameters": {"keep": 1}},
        )
    ).json()
    assert sched["parameters"] == {"keep": 1}

    run = (await client.post(f"/api/schedules/{sched['id']}/run-now")).json()
    assert run["status"] == "success", run
    assert run["parameters"] == {"keep": 1}
    out = pd.read_csv(tmp_path / "outputs" / run["output_location"])
    assert len(out) == 1
