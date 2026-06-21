"""
Flow CRUD endpoint tests.

Happy path and edge cases for:
  GET    /api/flows
  POST   /api/flows
  GET    /api/flows/{id}
  PUT    /api/flows/{id}
  DELETE /api/flows/{id}
"""

from httpx import AsyncClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_PAYLOAD = {"name": "My Flow", "description": "A test flow"}
GRAPH = {
    "nodes": [{"id": "n1", "type": "csvInput", "position": {"x": 0, "y": 0}, "data": {}}],
    "edges": [],
}


async def _create_flow(client: AsyncClient, **overrides) -> dict:
    payload = {**VALID_PAYLOAD, **overrides}
    r = await client.post("/api/flows", json=payload)
    assert r.status_code == 201
    return r.json()


# ---------------------------------------------------------------------------
# GET /api/flows — list
# ---------------------------------------------------------------------------


async def test_list_flows_empty(client: AsyncClient) -> None:
    r = await client.get("/api/flows")
    assert r.status_code == 200
    assert r.json() == []


async def test_list_flows_returns_all(client: AsyncClient) -> None:
    await _create_flow(client, name="Flow A")
    await _create_flow(client, name="Flow B")

    r = await client.get("/api/flows")
    assert r.status_code == 200
    names = [f["name"] for f in r.json()]
    assert set(names) == {"Flow A", "Flow B"}


async def test_list_flows_ordered_by_updated_at_desc(client: AsyncClient) -> None:
    first = await _create_flow(client, name="First")
    # Update the first flow so its updated_at is newer than the second
    second = await _create_flow(client, name="Second")
    await client.put(f"/api/flows/{first['id']}", json={"name": "First updated"})

    r = await client.get("/api/flows")
    assert r.status_code == 200
    ids = [f["id"] for f in r.json()]
    # "First updated" was touched last, so it should appear first
    assert ids[0] == first["id"]
    assert ids[1] == second["id"]


# ---------------------------------------------------------------------------
# POST /api/flows — create
# ---------------------------------------------------------------------------


async def test_create_flow_minimal(client: AsyncClient) -> None:
    r = await client.post("/api/flows", json={"name": "Minimal"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Minimal"
    assert body["description"] is None
    assert body["graph_json"] == {}
    assert "id" in body
    assert "created_at" in body
    assert "updated_at" in body


async def test_create_flow_with_description(client: AsyncClient) -> None:
    r = await client.post("/api/flows", json=VALID_PAYLOAD)
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == VALID_PAYLOAD["name"]
    assert body["description"] == VALID_PAYLOAD["description"]


async def test_create_flow_with_graph_json(client: AsyncClient) -> None:
    r = await client.post("/api/flows", json={"name": "With graph", "graph_json": GRAPH})
    assert r.status_code == 201
    body = r.json()
    assert body["graph_json"] == GRAPH


async def test_create_flow_with_nested_graph_json(client: AsyncClient) -> None:
    complex_graph = {
        "nodes": [
            {
                "id": "n1",
                "type": "csvInput",
                "position": {"x": 100, "y": 200},
                "data": {"label": "Input", "config": {"dataset_id": "ds_abc"}},
            }
        ],
        "edges": [{"id": "e1", "source": "n1", "target": "n2", "metadata": {"weight": 1.5}}],
    }
    r = await client.post("/api/flows", json={"name": "Complex", "graph_json": complex_graph})
    assert r.status_code == 201
    assert r.json()["graph_json"] == complex_graph


async def test_create_flow_assigns_unique_ids(client: AsyncClient) -> None:
    r1 = await client.post("/api/flows", json={"name": "A"})
    r2 = await client.post("/api/flows", json={"name": "B"})
    assert r1.json()["id"] != r2.json()["id"]


# ---------------------------------------------------------------------------
# POST /api/flows — validation errors
# ---------------------------------------------------------------------------


async def test_create_flow_missing_name_returns_422(client: AsyncClient) -> None:
    r = await client.post("/api/flows", json={"description": "no name"})
    assert r.status_code == 422


async def test_create_flow_empty_name_returns_422(client: AsyncClient) -> None:
    r = await client.post("/api/flows", json={"name": ""})
    assert r.status_code == 422


async def test_create_flow_name_too_long_returns_422(client: AsyncClient) -> None:
    r = await client.post("/api/flows", json={"name": "x" * 256})
    assert r.status_code == 422


async def test_create_flow_name_exactly_255_chars(client: AsyncClient) -> None:
    r = await client.post("/api/flows", json={"name": "x" * 255})
    assert r.status_code == 201


# ---------------------------------------------------------------------------
# GET /api/flows/{id} — retrieve
# ---------------------------------------------------------------------------


async def test_get_flow(client: AsyncClient) -> None:
    created = await _create_flow(client)
    r = await client.get(f"/api/flows/{created['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == created["id"]
    assert r.json()["name"] == created["name"]


async def test_get_flow_not_found(client: AsyncClient) -> None:
    r = await client.get("/api/flows/nonexistent-id")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


async def test_get_flow_preserves_graph_json(client: AsyncClient) -> None:
    created = await _create_flow(client, graph_json=GRAPH)
    r = await client.get(f"/api/flows/{created['id']}")
    assert r.json()["graph_json"] == GRAPH


# ---------------------------------------------------------------------------
# PUT /api/flows/{id} — update
# ---------------------------------------------------------------------------


async def test_update_flow_name(client: AsyncClient) -> None:
    created = await _create_flow(client)
    r = await client.put(f"/api/flows/{created['id']}", json={"name": "Renamed"})
    assert r.status_code == 200
    assert r.json()["name"] == "Renamed"
    # Other fields unchanged
    assert r.json()["description"] == created["description"]


async def test_update_flow_description_only(client: AsyncClient) -> None:
    created = await _create_flow(client)
    r = await client.put(f"/api/flows/{created['id']}", json={"description": "New desc"})
    assert r.status_code == 200
    assert r.json()["description"] == "New desc"
    assert r.json()["name"] == created["name"]  # name untouched


async def test_update_flow_graph_json(client: AsyncClient) -> None:
    created = await _create_flow(client)
    r = await client.put(f"/api/flows/{created['id']}", json={"graph_json": GRAPH})
    assert r.status_code == 200
    assert r.json()["graph_json"] == GRAPH


async def test_update_flow_all_fields(client: AsyncClient) -> None:
    created = await _create_flow(client)
    payload = {"name": "New name", "description": "New desc", "graph_json": GRAPH}
    r = await client.put(f"/api/flows/{created['id']}", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "New name"
    assert body["description"] == "New desc"
    assert body["graph_json"] == GRAPH


async def test_update_flow_updates_updated_at(client: AsyncClient) -> None:
    created = await _create_flow(client)
    r = await client.put(f"/api/flows/{created['id']}", json={"name": "Changed"})
    assert r.json()["updated_at"] >= created["updated_at"]


async def test_update_flow_not_found(client: AsyncClient) -> None:
    r = await client.put("/api/flows/nonexistent-id", json={"name": "Nope"})
    assert r.status_code == 404


async def test_update_flow_empty_name_returns_422(client: AsyncClient) -> None:
    created = await _create_flow(client)
    r = await client.put(f"/api/flows/{created['id']}", json={"name": ""})
    assert r.status_code == 422


async def test_update_flow_name_too_long_returns_422(client: AsyncClient) -> None:
    created = await _create_flow(client)
    r = await client.put(f"/api/flows/{created['id']}", json={"name": "x" * 256})
    assert r.status_code == 422


async def test_update_flow_empty_body_is_noop(client: AsyncClient) -> None:
    """PUT with an empty body should not change anything (all fields optional)."""
    created = await _create_flow(client)
    r = await client.put(f"/api/flows/{created['id']}", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == created["name"]
    assert body["description"] == created["description"]
    assert body["graph_json"] == created["graph_json"]


async def test_update_flow_can_clear_description(client: AsyncClient) -> None:
    created = await _create_flow(client, description="Has desc")
    r = await client.put(f"/api/flows/{created['id']}", json={"description": None})
    assert r.status_code == 200
    assert r.json()["description"] is None


# ---------------------------------------------------------------------------
# DELETE /api/flows/{id}
# ---------------------------------------------------------------------------


async def test_delete_flow(client: AsyncClient) -> None:
    created = await _create_flow(client)
    r = await client.delete(f"/api/flows/{created['id']}")
    assert r.status_code == 204


async def test_delete_flow_removes_it_from_list(client: AsyncClient) -> None:
    created = await _create_flow(client)
    await client.delete(f"/api/flows/{created['id']}")
    r = await client.get("/api/flows")
    assert r.json() == []


async def test_delete_flow_makes_get_return_404(client: AsyncClient) -> None:
    created = await _create_flow(client)
    await client.delete(f"/api/flows/{created['id']}")
    r = await client.get(f"/api/flows/{created['id']}")
    assert r.status_code == 404


async def test_delete_flow_not_found(client: AsyncClient) -> None:
    r = await client.delete("/api/flows/nonexistent-id")
    assert r.status_code == 404


async def test_delete_flow_twice_second_is_404(client: AsyncClient) -> None:
    created = await _create_flow(client)
    await client.delete(f"/api/flows/{created['id']}")
    r = await client.delete(f"/api/flows/{created['id']}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


async def test_flow_response_shape(client: AsyncClient) -> None:
    """All expected fields are present in the response."""
    r = await client.post("/api/flows", json={"name": "Shape test"})
    body = r.json()
    expected_keys = {"id", "name", "description", "graph_json", "created_at", "updated_at"}
    assert expected_keys.issubset(body.keys())


async def test_flow_id_is_uuid_format(client: AsyncClient) -> None:
    import re

    r = await client.post("/api/flows", json={"name": "UUID check"})
    uuid_pattern = re.compile(
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
    )
    assert uuid_pattern.match(r.json()["id"])
