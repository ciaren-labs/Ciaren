"""Aggressive end-to-end coverage of the flow export → import lifecycle.

Exercises the portable flow-document round trip and a wide range of edge cases:
malformed payloads, unknown node types, environment-binding stripping across node
kinds, unicode, large graphs, dangling edges, project targeting, and stability of
a re-exported imported flow.
"""
import io

import pandas as pd
from httpx import AsyncClient


async def _upload(client: AsyncClient, name: str = "people.csv") -> dict:
    buf = io.BytesIO()
    pd.DataFrame([{"a": 1, "b": 2}, {"a": 3, "b": None}]).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": (name, buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


async def _create_flow(client: AsyncClient, graph: dict, name: str = "f") -> dict:
    r = await client.post("/api/flows", json={"name": name, "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


async def _export_doc(client: AsyncClient, flow_id: str) -> dict:
    r = await client.post(f"/api/flows/{flow_id}/export/python")
    assert r.status_code == 200, r.text
    return r.json()["flow_document"]


def _basic_graph(dataset_id: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput",
             "data": {"config": {"dataset_id": dataset_id, "dataset_version": 3}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {"path": "clean.csv"}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "drop", "target": "out1"},
        ],
    }


# -- round trip --------------------------------------------------------------


async def test_full_roundtrip_export_import_reexport_is_stable(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, _basic_graph(ds["id"]))
    doc = await _export_doc(client, flow["id"])

    imported = (await client.post("/api/flows/import", json=doc)).json()
    assert imported["id"] != flow["id"]
    # bindings stripped on import
    in_node = next(n for n in imported["graph_json"]["nodes"] if n["id"] == "in1")
    assert "dataset_id" not in in_node["data"]["config"]
    assert "dataset_version" not in in_node["data"]["config"]
    # structure preserved
    assert [n["id"] for n in imported["graph_json"]["nodes"]] == [
        n["id"] for n in doc["graph_json"]["nodes"]
    ]
    # importing the same document again is idempotent in shape (new flow each time)
    again = await client.post("/api/flows/import", json=doc)
    assert again.status_code == 201, again.text
    assert again.json()["id"] != imported["id"]


# -- malformed payloads ------------------------------------------------------


async def test_import_missing_graph_json_is_422(client: AsyncClient) -> None:
    r = await client.post("/api/flows/import", json={"name": "x"})
    assert r.status_code == 422, r.text


async def test_import_empty_nodes_is_400(client: AsyncClient) -> None:
    r = await client.post("/api/flows/import", json={"graph_json": {"nodes": [], "edges": []}})
    assert r.status_code == 400, r.text


async def test_import_graph_json_not_object_is_400_or_422(client: AsyncClient) -> None:
    r = await client.post("/api/flows/import", json={"graph_json": "nope"})
    assert r.status_code in (400, 422), r.text


async def test_import_node_without_type_is_400(client: AsyncClient) -> None:
    r = await client.post(
        "/api/flows/import",
        json={"graph_json": {"nodes": [{"id": "x"}], "edges": []}},
    )
    assert r.status_code == 400, r.text


async def test_import_unknown_node_type_is_400_and_names_it(client: AsyncClient) -> None:
    r = await client.post(
        "/api/flows/import",
        json={"graph_json": {"nodes": [{"id": "x", "type": "wat", "data": {}}], "edges": []}},
    )
    assert r.status_code == 400
    assert "wat" in r.json()["detail"]


# -- sanitization ------------------------------------------------------------


async def test_import_strips_bindings_across_node_kinds_but_keeps_other_config(client: AsyncClient) -> None:
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput",
             "data": {"config": {"dataset_id": "ds-x", "dataset_version": 2}}},
            {"id": "sqlin", "type": "sqlInput",
             "data": {"config": {"connection_id": "c1", "table": "users", "mode": "table"}}},
            {"id": "t1", "type": "dropNulls",
             "data": {"config": {"model_uri": "models:/m@production", "keep_me": 42}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {"path": "o.csv"}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "t1"}],
    }
    imported = (await client.post("/api/flows/import", json={"graph_json": graph})).json()
    by_id = {n["id"]: n for n in imported["graph_json"]["nodes"]}
    assert "dataset_id" not in by_id["in1"]["data"]["config"]
    assert "dataset_version" not in by_id["in1"]["data"]["config"]
    assert "connection_id" not in by_id["sqlin"]["data"]["config"]
    # non-binding config survives
    assert by_id["sqlin"]["data"]["config"]["table"] == "users"
    assert by_id["t1"]["data"]["config"]["model_uri"] == "models:/m@production"
    assert by_id["t1"]["data"]["config"]["keep_me"] == 42


async def test_import_drops_edges_referencing_missing_nodes(client: AsyncClient) -> None:
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [
            {"id": "ok", "source": "in1", "target": "out1"},
            {"id": "ghost", "source": "in1", "target": "does-not-exist"},
        ],
    }
    imported = (await client.post("/api/flows/import", json={"graph_json": graph})).json()
    edge_ids = [e["id"] for e in imported["graph_json"]["edges"]]
    assert edge_ids == ["ok"]


# -- metadata / unicode / sizing ---------------------------------------------


async def test_import_preserves_unicode_name_and_config(client: AsyncClient) -> None:
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {}}},
            {"id": "ren", "type": "renameColumns",
             "data": {"config": {"mapping": {"café": "naïve_Ω"}}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "ren"}],
    }
    doc = {"format": "flowframe.flow/v1", "name": "café ☕ flow", "graph_json": graph}
    imported = (await client.post("/api/flows/import", json=doc)).json()
    assert imported["name"] == "café ☕ flow"
    ren = next(n for n in imported["graph_json"]["nodes"] if n["id"] == "ren")
    assert ren["data"]["config"]["mapping"] == {"café": "naïve_Ω"}


async def test_import_defaults_name_when_blank(client: AsyncClient) -> None:
    graph = {"nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}], "edges": []}
    imported = (await client.post("/api/flows/import", json={"name": "   ", "graph_json": graph})).json()
    assert imported["name"] == "Imported flow"


async def test_import_large_graph_roundtrips(client: AsyncClient) -> None:
    nodes = [{"id": "in1", "type": "csvInput", "data": {"config": {}}}]
    edges = []
    prev = "in1"
    for i in range(60):
        nid = f"n{i}"
        nodes.append({"id": nid, "type": "dropNulls", "data": {"config": {}}})
        edges.append({"id": f"e{i}", "source": prev, "target": nid})
        prev = nid
    nodes.append({"id": "out1", "type": "csvOutput", "data": {"config": {}}})
    edges.append({"id": "eo", "source": prev, "target": "out1"})
    r = await client.post("/api/flows/import", json={"graph_json": {"nodes": nodes, "edges": edges}})
    assert r.status_code == 201, r.text
    assert len(r.json()["graph_json"]["nodes"]) == 62


# -- project targeting -------------------------------------------------------


async def test_import_assigns_default_project_without_target(client: AsyncClient) -> None:
    graph = {"nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}], "edges": []}
    imported = (await client.post("/api/flows/import", json={"graph_json": graph})).json()
    assert imported["project_id"]  # never null


async def test_import_into_explicit_project(client: AsyncClient) -> None:
    proj = (await client.post("/api/projects", json={"name": "Target"})).json()
    graph = {"nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}], "edges": []}
    imported = (
        await client.post("/api/flows/import", json={"graph_json": graph, "project_id": proj["id"]})
    ).json()
    assert imported["project_id"] == proj["id"]


async def test_import_into_nonexistent_project_is_404(client: AsyncClient) -> None:
    graph = {"nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {}}}], "edges": []}
    r = await client.post("/api/flows/import", json={"graph_json": graph, "project_id": "nope"})
    assert r.status_code == 404, r.text


# -- the export side stays usable --------------------------------------------


async def test_exported_document_graph_matches_flow(client: AsyncClient) -> None:
    ds = await _upload(client)
    graph = _basic_graph(ds["id"])
    flow = await _create_flow(client, graph, name="exact")
    doc = await _export_doc(client, flow["id"])
    assert doc["name"] == "exact"
    assert doc["format"] == "flowframe.flow/v1"
    assert doc["graph_json"] == flow["graph_json"]


async def test_unconfigured_import_export_fails_gracefully_then_works_after_rewire(
    client: AsyncClient,
) -> None:
    """An imported flow has its inputs stripped, so exporting code first returns a
    clean 400 (not a 500/KeyError); after the dataset is re-selected it exports."""
    ds = await _upload(client)
    flow = await _create_flow(client, _basic_graph(ds["id"]))
    doc = await _export_doc(client, flow["id"])
    imported = (await client.post("/api/flows/import", json=doc)).json()

    # Inputs not yet wired -> graceful validation error, never a server crash.
    r = await client.post(f"/api/flows/{imported['id']}/export/python")
    assert r.status_code == 400, r.text
    assert "dataset" in r.json()["detail"].lower()

    # Re-select the dataset (what a user does after importing) and export succeeds.
    graph = imported["graph_json"]
    for node in graph["nodes"]:
        if node["id"] == "in1":
            node["data"]["config"]["dataset_id"] = ds["id"]
    await client.put(f"/api/flows/{imported['id']}", json={"graph_json": graph})
    r2 = await client.post(f"/api/flows/{imported['id']}/export/python")
    assert r2.status_code == 200, r2.text
    assert "import pandas as pd" in r2.json()["code"]
