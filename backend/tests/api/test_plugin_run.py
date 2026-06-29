"""End-to-end over HTTP: a flow that uses a plugin node uploads, runs, and writes
output with the plugin node applied."""

import io
from pathlib import Path

import pandas as pd
import pytest
from httpx import AsyncClient

from app.plugins import get_registry, reset_registry

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES_DIR = REPO_ROOT / "examples" / "plugins"


@pytest.fixture(autouse=True)
def _example_plugin(monkeypatch):
    from app.plugins.state import PluginStateStore

    # ASGITransport doesn't run lifespan, so bridge the example plugin explicitly.
    monkeypatch.setenv("FLOWFRAME_PLUGINS_DIR", str(EXAMPLES_DIR))
    # Plugins require explicit approval before their code loads; pre-approve the
    # example so the catalog/run flow has its node available.
    state = PluginStateStore()
    state.set_approved("community.hello", True)
    state.save()
    reset_registry()
    get_registry()
    yield
    reset_registry()


def _graph(dataset_id: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {
                "id": "greet",
                "type": "hello.greeting",
                "data": {"config": {"column": "msg", "name": "FlowFrame"}},
            },
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "greet"},
            {"id": "e2", "source": "greet", "target": "out1"},
        ],
    }


async def test_plugin_node_appears_in_catalog_and_runs(client: AsyncClient, tmp_path: Path) -> None:
    # The plugin node shows up in the dynamic catalog…
    catalog = await client.get("/api/catalog/nodes")
    assert "hello.greeting" in {n["id"] for n in catalog.json()}

    # …upload data, build a flow that uses it, and run it.
    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2, 3]}).to_csv(buf, index=False)
    ds = (
        await client.post(
            "/api/datasets/upload",
            files={"file": ("d.csv", buf.getvalue(), "text/csv")},
        )
    ).json()

    flow = (await client.post("/api/flows", json={"name": "plugin-flow", "graph_json": _graph(ds["id"])})).json()
    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    run = r.json()
    assert run["status"] == "success", run

    out = pd.read_csv(tmp_path / "outputs" / run["output_location"])
    assert list(out["msg"]) == ["Hello, FlowFrame!"] * 3
    assert list(out["a"]) == [1, 2, 3]


async def test_export_python_endpoint_with_plugin_node(client: AsyncClient) -> None:
    buf = io.BytesIO()
    pd.DataFrame({"a": [1]}).to_csv(buf, index=False)
    ds = (
        await client.post(
            "/api/datasets/upload",
            files={"file": ("d.csv", buf.getvalue(), "text/csv")},
        )
    ).json()
    flow = (await client.post("/api/flows", json={"name": "plugin-flow", "graph_json": _graph(ds["id"])})).json()

    r = await client.post(f"/api/flows/{flow['id']}/export/python")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "'msg': 'Hello, FlowFrame!'" in body["code"]  # pandas export
    assert "'msg': 'Hello, FlowFrame!'" in body["polars"]  # bridged polars export
