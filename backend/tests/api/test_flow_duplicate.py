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


async def test_duplicate_blank_name_falls_back_to_default(client: AsyncClient) -> None:
    """A whitespace-only ?name= must not create a flow named "" — the same
    invariant FlowCreate enforces with min_length=1."""
    original = await _create(client, "blanked")
    r = await client.post(f"/api/flows/{original['id']}/duplicate", params={"name": "   "})
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "blanked (copy)"


async def test_duplicate_over_long_name_is_rejected(client: AsyncClient) -> None:
    """Same contract as FlowCreate (max_length=255): reject, don't silently
    truncate an explicitly chosen name."""
    original = await _create(client, "longname")
    r = await client.post(f"/api/flows/{original['id']}/duplicate", params={"name": "y" * 300})
    assert r.status_code == 400, r.text
    assert "255" in r.json()["detail"]

    # Exactly 255 is fine.
    r = await client.post(f"/api/flows/{original['id']}/duplicate", params={"name": "y" * 255})
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "y" * 255


async def test_duplicate_max_length_name_keeps_copy_suffix(client: AsyncClient) -> None:
    """The default name must never be byte-identical to the original's — a
    255-char original truncates so " (copy)" still fits."""
    original = await _create(client, "z" * 255)
    r = await client.post(f"/api/flows/{original['id']}/duplicate")
    assert r.status_code == 201, r.text
    name = r.json()["name"]
    assert name != original["name"]
    assert name.endswith(" (copy)")
    assert len(name) <= 255


async def test_duplicate_preserves_disabled_state(client: AsyncClient) -> None:
    """A disabled flow (e.g. auto-disabled because its dataset was deleted)
    must not duplicate into an enabled, schedulable copy of the same graph."""
    original = await _create(client, "off")
    r = await client.put(f"/api/flows/{original['id']}", json={"is_disabled": True})
    assert r.status_code == 200, r.text
    copy = (await client.post(f"/api/flows/{original['id']}/duplicate")).json()
    assert copy["is_disabled"] is True

    # And an enabled original still duplicates enabled.
    other = await _create(client, "on")
    copy2 = (await client.post(f"/api/flows/{other['id']}/duplicate")).json()
    assert copy2["is_disabled"] is False


async def test_duplicate_tolerates_legacy_invalid_parameters(client: AsyncClient, db_session) -> None:
    """A legacy row whose parameter specs predate the create/update gate must
    stay duplicatable (copied verbatim), not 400."""
    original = await _create(client, "legacy")
    # Corrupt the stored row directly — the API itself refuses such specs.
    from sqlalchemy import update

    from app.db.models.flow import Flow

    bad_graph = dict(_GRAPH, parameters=[{"name": "1 not an identifier!!", "type": "bogus"}])
    await db_session.execute(update(Flow).where(Flow.id == original["id"]).values(graph_json=bad_graph))
    await db_session.commit()

    r = await client.post(f"/api/flows/{original['id']}/duplicate")
    assert r.status_code == 201, r.text
    assert r.json()["graph_json"]["parameters"] == bad_graph["parameters"]
