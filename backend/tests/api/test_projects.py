"""
Project (workspace) endpoint tests.

  GET    /api/projects
  POST   /api/projects
  GET    /api/projects/{id}
  PUT    /api/projects/{id}
  DELETE /api/projects/{id}

plus project assignment/filtering on flows and datasets.
"""

import io

from httpx import AsyncClient

GRAPH = {
    "nodes": [{"id": "n1", "type": "csvInput", "position": {"x": 0, "y": 0}, "data": {}}],
    "edges": [],
}


async def _csv_upload(client: AsyncClient, name: str, project_id: str | None = None) -> dict:
    content = b"id,amount\n1,10\n2,20\n"
    files = {"file": (name, io.BytesIO(content), "text/csv")}
    url = "/api/datasets/upload"
    if project_id:
        url += f"?project_id={project_id}"
    r = await client.post(url, files=files)
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------------------
# Default project
# ---------------------------------------------------------------------------


async def test_list_creates_default_project(client: AsyncClient) -> None:
    r = await client.get("/api/projects")
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) == 1
    assert projects[0]["is_default"] is True
    assert projects[0]["name"] == "Default"


async def test_new_flow_lands_in_default_project(client: AsyncClient) -> None:
    r = await client.post("/api/flows", json={"name": "F"})
    flow = r.json()
    projects = (await client.get("/api/projects")).json()
    default = next(p for p in projects if p["is_default"])
    assert flow["project_id"] == default["id"]


async def test_default_project_counts_datasets_and_flows(client: AsyncClient) -> None:
    await client.post("/api/flows", json={"name": "F"})
    await _csv_upload(client, "sales.csv")
    projects = (await client.get("/api/projects")).json()
    default = next(p for p in projects if p["is_default"])
    assert default["flow_count"] == 1
    assert default["dataset_count"] == 1


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


async def test_create_project(client: AsyncClient) -> None:
    r = await client.post("/api/projects", json={"name": "Sales", "color": "violet"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "Sales"
    assert body["is_default"] is False
    assert body["dataset_count"] == 0


async def test_duplicate_project_name_conflicts(client: AsyncClient) -> None:
    await client.post("/api/projects", json={"name": "Sales"})
    r = await client.post("/api/projects", json={"name": "sales"})  # case-insensitive
    assert r.status_code == 409


async def test_update_project(client: AsyncClient) -> None:
    pid = (await client.post("/api/projects", json={"name": "Sales"})).json()["id"]
    r = await client.put(f"/api/projects/{pid}", json={"description": "Q3 work"})
    assert r.status_code == 200
    assert r.json()["description"] == "Q3 work"


async def test_cannot_delete_default_project(client: AsyncClient) -> None:
    default = next(p for p in (await client.get("/api/projects")).json() if p["is_default"])
    r = await client.delete(f"/api/projects/{default['id']}")
    assert r.status_code == 400


async def test_delete_project_reassigns_children_to_default(client: AsyncClient) -> None:
    pid = (await client.post("/api/projects", json={"name": "Temp"})).json()["id"]
    flow = (await client.post("/api/flows", json={"name": "F", "project_id": pid})).json()
    assert flow["project_id"] == pid

    r = await client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204

    moved = (await client.get(f"/api/flows/{flow['id']}")).json()
    default = next(p for p in (await client.get("/api/projects")).json() if p["is_default"])
    assert moved["project_id"] == default["id"]


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


async def test_filter_flows_by_project(client: AsyncClient) -> None:
    pid = (await client.post("/api/projects", json={"name": "Sales"})).json()["id"]
    await client.post("/api/flows", json={"name": "In project", "project_id": pid})
    await client.post("/api/flows", json={"name": "In default"})

    r = await client.get(f"/api/flows?project_id={pid}")
    names = [f["name"] for f in r.json()]
    assert names == ["In project"]


async def test_filter_datasets_by_project(client: AsyncClient) -> None:
    pid = (await client.post("/api/projects", json={"name": "Sales"})).json()["id"]
    await _csv_upload(client, "in_project.csv", project_id=pid)
    await _csv_upload(client, "in_default.csv")

    r = await client.get(f"/api/datasets?project_id={pid}")
    names = [d["name"] for d in r.json()]
    assert names == ["in_project.csv"]


# ---------------------------------------------------------------------------
# Dataset → flows lineage
# ---------------------------------------------------------------------------


async def test_dataset_flows_lineage(client: AsyncClient) -> None:
    ds = await _csv_upload(client, "sales.csv")
    graph = {
        "nodes": [
            {
                "id": "in",
                "type": "csvInput",
                "position": {"x": 0, "y": 0},
                "data": {"config": {"dataset_id": ds["id"]}},
            }
        ],
        "edges": [],
    }
    used = (await client.post("/api/flows", json={"name": "Uses it", "graph_json": graph})).json()
    await client.post("/api/flows", json={"name": "Unrelated", "graph_json": GRAPH})

    r = await client.get(f"/api/datasets/{ds['id']}/flows")
    assert r.status_code == 200
    names = [f["name"] for f in r.json()]
    assert names == [used["name"]]


async def test_dataset_flows_lineage_unknown_dataset_404(client: AsyncClient) -> None:
    r = await client.get("/api/datasets/nope/flows")
    assert r.status_code == 404
