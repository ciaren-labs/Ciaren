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

import pytest
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
# Reserved default name ("Default" squatting)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["Default", "default", "DEFAULT", " Default "])
async def test_create_project_named_default_is_rejected(client: AsyncClient, name: str) -> None:
    # Squatting the reserved name on a fresh DB used to make ensure_default()'s
    # insert violate the unique name constraint, 500-ing every subsequent call.
    r = await client.post("/api/projects", json={"name": name})
    assert r.status_code == 400, r.text
    assert "reserved" in r.json()["detail"].lower()

    # The rejection must leave everything working: listing lazily creates the
    # real default project without tripping the unique constraint.
    r = await client.get("/api/projects")
    assert r.status_code == 200
    projects = r.json()
    assert len(projects) == 1
    assert projects[0]["is_default"] is True
    assert projects[0]["name"] == "Default"


async def test_rename_project_to_default_is_rejected(client: AsyncClient) -> None:
    pid = (await client.post("/api/projects", json={"name": "Sales"})).json()["id"]
    r = await client.put(f"/api/projects/{pid}", json={"name": "default"})
    assert r.status_code == 400, r.text
    assert "reserved" in r.json()["detail"].lower()
    # Everything still works and the project kept its name.
    assert (await client.get(f"/api/projects/{pid}")).json()["name"] == "Sales"
    assert (await client.get("/api/projects")).status_code == 200


@pytest.mark.parametrize("squatter_name", ["Default", "DEFAULT"])
async def test_ensure_default_adopts_preexisting_default_named_row(
    client: AsyncClient, db_session, squatter_name: str
) -> None:
    # A row squatting the reserved name (e.g. created before the name guard
    # existed) must be adopted as the default, not duplicated (which would
    # violate the unique name constraint and 500).
    from app.db.models.project import Project
    from app.services.project_service import ProjectService

    squatter = Project(name=squatter_name, is_default=False)
    db_session.add(squatter)
    await db_session.commit()

    service = ProjectService(db_session)
    default = await service.ensure_default()
    assert default.id == squatter.id
    assert default.is_default is True
    # Idempotent: a second call returns the same row.
    assert (await service.ensure_default()).id == squatter.id

    projects = (await client.get("/api/projects")).json()
    assert len(projects) == 1
    assert projects[0]["id"] == squatter.id
    assert projects[0]["is_default"] is True


# ---------------------------------------------------------------------------
# Delete with dataset name clashes against the default project
# ---------------------------------------------------------------------------


async def test_delete_project_renames_clashing_dataset(client: AsyncClient) -> None:
    # Datasets are unique per (project_id, name): reassigning a same-named
    # dataset into Default used to violate the constraint and 500 the delete.
    in_default = await _csv_upload(client, "sales.csv")  # lands in Default
    pid = (await client.post("/api/projects", json={"name": "Temp"})).json()["id"]
    clashing = await _csv_upload(client, "sales.csv", project_id=pid)
    keeps_name = await _csv_upload(client, "other.csv", project_id=pid)

    r = await client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204, r.text

    datasets = {d["id"]: d for d in (await client.get("/api/datasets")).json()}
    default = next(p for p in (await client.get("/api/projects")).json() if p["is_default"])
    # Both same-named datasets survive; the moved one was renamed.
    assert datasets[in_default["id"]]["name"] == "sales.csv"
    assert datasets[clashing["id"]]["name"] == "sales.csv (from Temp)"
    assert datasets[clashing["id"]]["project_id"] == default["id"]
    # A non-clashing dataset keeps its name.
    assert datasets[keeps_name["id"]]["name"] == "other.csv"
    assert datasets[keeps_name["id"]]["project_id"] == default["id"]


async def test_delete_project_dataset_rename_falls_back_to_numeric_suffix(client: AsyncClient, db_session) -> None:
    # If the "(from <project>)" name is itself taken in Default, a numeric
    # suffix keeps the rename collision-free.
    from app.db.models.dataset import Dataset

    await _csv_upload(client, "sales.csv")
    default = next(p for p in (await client.get("/api/projects")).json() if p["is_default"])
    # The upload gate rejects extension-less filenames, so plant the squatting
    # name directly.
    db_session.add(Dataset(name="sales.csv (from Temp)", source_type="csv", project_id=default["id"]))
    await db_session.commit()
    pid = (await client.post("/api/projects", json={"name": "Temp"})).json()["id"]
    moved = await _csv_upload(client, "sales.csv", project_id=pid)

    r = await client.delete(f"/api/projects/{pid}")
    assert r.status_code == 204, r.text

    datasets = {d["id"]: d for d in (await client.get("/api/datasets")).json()}
    assert datasets[moved["id"]]["name"] == "sales.csv (from Temp) (2)"
    assert len(datasets) == 3  # nothing was lost or merged


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


async def test_same_filename_in_two_projects_creates_separate_datasets(client: AsyncClient) -> None:
    # Regression: the create-vs-new-version lookup used to match by name alone
    # (no project filter), so uploading "customers.csv" to project B would find
    # project A's dataset of the same name and silently append a new version to
    # it there, instead of creating an isolated dataset in project B.
    pid_a = (await client.post("/api/projects", json={"name": "A"})).json()["id"]
    pid_b = (await client.post("/api/projects", json={"name": "B"})).json()["id"]

    in_a = await _csv_upload(client, "customers.csv", project_id=pid_a)
    in_b = await _csv_upload(client, "customers.csv", project_id=pid_b)

    assert in_a["id"] != in_b["id"]
    assert in_a["project_id"] == pid_a
    assert in_b["project_id"] == pid_b
    assert in_a["latest_version"] == 1
    assert in_b["latest_version"] == 1  # not version 2 of project A's dataset

    a_datasets = (await client.get(f"/api/datasets?project_id={pid_a}")).json()
    b_datasets = (await client.get(f"/api/datasets?project_id={pid_b}")).json()
    assert [d["id"] for d in a_datasets] == [in_a["id"]]
    assert [d["id"] for d in b_datasets] == [in_b["id"]]


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
