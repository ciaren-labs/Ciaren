# SPDX-License-Identifier: AGPL-3.0-only
"""POST /flows/{id}/duplicate: an independent copy of the definition (graph,
parameters, engine) with none of the operational state (schedules, runs)."""

from httpx import AsyncClient

_GRAPH = {
    "engine": "polars",
    "parameters": [{"name": "keep", "type": "integer", "default": 3}],
    "nodes": [
        {"id": "in", "type": "csvInput", "data": {"config": {"dataset_id": "d1"}}},
        {"id": "lim", "type": "limitRows", "data": {"config": {"n": "{{ keep }}"}}},
        {"id": "out", "type": "csvOutput", "data": {"config": {"path": "out.csv"}}},
    ],
    "edges": [
        {"id": "e1", "source": "in", "target": "lim"},
        {"id": "e2", "source": "lim", "target": "out"},
    ],
}


async def _create(client: AsyncClient, name: str = "original") -> dict:
    r = await client.post("/api/flows", json={"name": name, "graph_json": _GRAPH, "description": "desc"})
    assert r.status_code == 201, r.text
    return r.json()


async def test_duplicate_copies_definition(client: AsyncClient) -> None:
    original = await _create(client)
    r = await client.post(f"/api/flows/{original['id']}/duplicate")
    assert r.status_code == 201, r.text
    copy = r.json()
    assert copy["id"] != original["id"]
    assert copy["name"] == "original (copy)"
    assert copy["description"] == "desc"
    assert copy["project_id"] == original["project_id"]
    assert copy["graph_json"] == original["graph_json"]  # engine + parameters ride along


async def test_duplicate_is_independent(client: AsyncClient) -> None:
    """Editing the copy must not touch the original's graph (deep copy)."""
    original = await _create(client, "indep")
    copy = (await client.post(f"/api/flows/{original['id']}/duplicate")).json()
    mutated = dict(_GRAPH, nodes=[{"id": "solo", "type": "csvInput", "data": {"config": {}}}], edges=[])
    r = await client.put(f"/api/flows/{copy['id']}", json={"graph_json": mutated})
    assert r.status_code == 200, r.text
    fresh_original = (await client.get(f"/api/flows/{original['id']}")).json()
    assert fresh_original["graph_json"] == _GRAPH


async def test_duplicate_custom_name(client: AsyncClient) -> None:
    original = await _create(client, "named")
    r = await client.post(f"/api/flows/{original['id']}/duplicate", params={"name": "mi copia"})
    assert r.status_code == 201
    assert r.json()["name"] == "mi copia"


async def test_duplicate_does_not_copy_schedules(client: AsyncClient) -> None:
    original = await _create(client, "scheduled")
    r = await client.post(
        f"/api/flows/{original['id']}/schedules",
        json={"cron": "0 9 * * *", "timezone": "UTC"},
    )
    assert r.status_code == 201, r.text

    copy = (await client.post(f"/api/flows/{original['id']}/duplicate")).json()
    listing = await client.get("/api/schedules")
    flows_with_schedules = {s["flow_id"] for s in listing.json()}
    assert original["id"] in flows_with_schedules
    assert copy["id"] not in flows_with_schedules


async def test_duplicate_unknown_flow_is_404(client: AsyncClient) -> None:
    r = await client.post("/api/flows/nope/duplicate")
    assert r.status_code == 404
