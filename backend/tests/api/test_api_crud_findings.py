"""Regression tests for four API-CRUD findings:

F1  PUT /api/flows/{id} with an explicit ``project_id: null`` moves to the default
    project instead of 500'ing (also covered in test_flows.py at the API layer).
F2  Moving a flow into a disabled project tags it DISABLED_BY_PROJECT; re-enabling
    the project restores it.
F3  Dataset/flow list services accept limit/offset and derive latest-version +
    count via an aggregate instead of loading every version.
F4  Creating a run with a non-existent (or cross-project) input_dataset_id is
    rejected (4xx) and never stored; a valid one works.
"""

import io

import pandas as pd
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.dataset import Dataset
from app.db.models.dataset_version import DatasetVersion
from app.db.models.flow import DISABLED_BY_PROJECT, Flow
from app.schemas.flow import FlowCreate, FlowUpdate
from app.schemas.project import ProjectCreate, ProjectUpdate
from app.services.dataset_service import DatasetService
from app.services.flow_service import FlowService
from app.services.project_service import ProjectService

# ---------------------------------------------------------------------------
# F2 — move into a disabled project
# ---------------------------------------------------------------------------


async def test_move_flow_into_disabled_project_tags_it_and_reenable_restores(
    db_session: AsyncSession,
) -> None:
    projects = ProjectService(db_session)
    flows = FlowService(db_session)

    default = await projects.ensure_default()
    dest = await projects.create(ProjectCreate(name="Archived"))
    # Disable the destination project (no members yet, so nothing cascades now).
    await projects.update(dest.id, ProjectUpdate(is_disabled=True))

    flow = await flows.create(FlowCreate(name="Mover", project_id=default.id))
    assert flow.is_disabled is False

    # Move the enabled flow into the disabled project.
    moved = await flows.update(flow.id, FlowUpdate(project_id=dest.id))
    assert moved.is_disabled is True

    row = (await db_session.execute(select(Flow).where(Flow.id == flow.id))).scalar_one()
    assert row.disabled_reason == DISABLED_BY_PROJECT
    assert row.disabled_by_project_id == dest.id

    # Re-enabling the project restores exactly what its cascade disabled.
    await projects.update(dest.id, ProjectUpdate(is_disabled=False))
    restored = (await db_session.execute(select(Flow).where(Flow.id == flow.id))).scalar_one()
    assert restored.is_disabled is False
    assert restored.disabled_reason is None
    assert restored.disabled_by_project_id is None


async def test_move_into_enabled_project_does_not_disable(db_session: AsyncSession) -> None:
    projects = ProjectService(db_session)
    flows = FlowService(db_session)

    default = await projects.ensure_default()
    dest = await projects.create(ProjectCreate(name="Active"))
    flow = await flows.create(FlowCreate(name="Mover", project_id=default.id))

    moved = await flows.update(flow.id, FlowUpdate(project_id=dest.id))
    assert moved.is_disabled is False
    row = (await db_session.execute(select(Flow).where(Flow.id == flow.id))).scalar_one()
    assert row.disabled_reason is None


async def test_move_into_disabled_project_preserves_manual_disable_reason(
    db_session: AsyncSession,
) -> None:
    """A flow the user disabled manually keeps its own reason when moved into a
    disabled project — so re-enabling that project must NOT revive it."""
    projects = ProjectService(db_session)
    flows = FlowService(db_session)

    default = await projects.ensure_default()
    dest = await projects.create(ProjectCreate(name="Archived"))
    await projects.update(dest.id, ProjectUpdate(is_disabled=True))

    flow = await flows.create(FlowCreate(name="Off", project_id=default.id))
    await flows.update(flow.id, FlowUpdate(is_disabled=True))  # manual disable

    await flows.update(flow.id, FlowUpdate(project_id=dest.id))
    row = (await db_session.execute(select(Flow).where(Flow.id == flow.id))).scalar_one()
    assert row.is_disabled is True
    assert row.disabled_reason == "manual"

    # Re-enabling the project leaves the manually-disabled flow disabled.
    await projects.update(dest.id, ProjectUpdate(is_disabled=False))
    still = (await db_session.execute(select(Flow).where(Flow.id == flow.id))).scalar_one()
    assert still.is_disabled is True


# ---------------------------------------------------------------------------
# F3 — pagination + latest-version/count without eager-loading all versions
# ---------------------------------------------------------------------------


async def _make_dataset_with_versions(db_session: AsyncSession, project_id: str, name: str, n_versions: int) -> str:
    ds = Dataset(name=name, source_type="csv", project_id=project_id, dataset_kind="input")
    db_session.add(ds)
    await db_session.flush()
    for i in range(1, n_versions + 1):
        db_session.add(
            DatasetVersion(
                dataset_id=ds.id,
                version_number=i,
                location=f"/tmp/{name}_v{i}.csv",
                schema_json=[{"name": "c", "type": f"string_v{i}"}],
                sample_json=[{"c": i}],
                row_count=i,
            )
        )
    await db_session.commit()
    return ds.id


async def test_dataset_list_reports_latest_version_and_count(db_session: AsyncSession) -> None:
    projects = ProjectService(db_session)
    default = await projects.ensure_default()
    await _make_dataset_with_versions(db_session, default.id, "many.csv", 25)

    reads = await DatasetService(db_session).list_all()
    assert len(reads) == 1
    read = reads[0]
    assert read.version_count == 25
    assert read.latest_version == 25
    # Latest version's schema is surfaced (derived via the aggregate, not the
    # first/loaded version).
    assert read.column_schema == [{"name": "c", "type": "string_v25"}]


async def test_dataset_list_limit_and_offset(db_session: AsyncSession) -> None:
    projects = ProjectService(db_session)
    default = await projects.ensure_default()
    for idx in range(5):
        await _make_dataset_with_versions(db_session, default.id, f"d{idx}.csv", 2)

    svc = DatasetService(db_session)
    page1 = await svc.list_all(limit=2, offset=0)
    page2 = await svc.list_all(limit=2, offset=2)
    all_rows = await svc.list_all(limit=None)

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(all_rows) == 5
    # Non-overlapping pages.
    assert {r.id for r in page1}.isdisjoint({r.id for r in page2})


async def test_flow_list_limit_and_offset(db_session: AsyncSession) -> None:
    projects = ProjectService(db_session)
    flows = FlowService(db_session)
    default = await projects.ensure_default()
    for idx in range(4):
        await flows.create(FlowCreate(name=f"f{idx}", project_id=default.id))

    page1 = await flows.list_all(limit=2, offset=0)
    page2 = await flows.list_all(limit=2, offset=2)
    everything = await flows.list_all(limit=None)

    assert len(page1) == 2
    assert len(page2) == 2
    assert len(everything) == 4
    assert {f.id for f in page1}.isdisjoint({f.id for f in page2})


async def test_dataset_list_empty_returns_empty(db_session: AsyncSession) -> None:
    await ProjectService(db_session).ensure_default()
    assert await DatasetService(db_session).list_all() == []


# ---------------------------------------------------------------------------
# F4 — input_dataset_id existence/scope validation on run creation
# ---------------------------------------------------------------------------


async def _upload_csv(client: AsyncClient, project_id: str | None = None) -> dict:
    buf = io.BytesIO()
    pd.DataFrame([{"v": 1}, {"v": 2}]).to_csv(buf, index=False)
    url = "/api/datasets/upload"
    if project_id is not None:
        url += f"?project_id={project_id}"
    r = await client.post(url, files={"file": ("nums.csv", buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


def _passthrough_graph(dataset_id: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }


async def test_run_with_unknown_input_dataset_id_is_rejected(client: AsyncClient) -> None:
    ds = await _upload_csv(client)
    flow = (await client.post("/api/flows", json={"name": "r", "graph_json": _passthrough_graph(ds["id"])})).json()

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"input_dataset_id": "does-not-exist"})
    assert r.status_code in (400, 404), r.text

    # No run row was created for the rejected request.
    runs = (await client.get("/api/runs", params={"flow_id": flow["id"]})).json()
    assert runs == []


async def test_run_with_valid_input_dataset_id_succeeds(client: AsyncClient) -> None:
    ds = await _upload_csv(client)
    flow = (await client.post("/api/flows", json={"name": "r", "graph_json": _passthrough_graph(ds["id"])})).json()

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"input_dataset_id": ds["id"]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "success", body
    assert body["input_dataset_id"] == ds["id"]


async def test_run_with_cross_project_input_dataset_id_is_rejected(client: AsyncClient) -> None:
    # Dataset lives in a different project than the flow (flow is in default).
    proj = (await client.post("/api/projects", json={"name": "Other"})).json()
    ds = await _upload_csv(client, project_id=proj["id"])
    # Flow's own input references a default-project dataset so the graph is valid.
    default_ds = await _upload_csv(client)
    flow = (
        await client.post("/api/flows", json={"name": "r", "graph_json": _passthrough_graph(default_ds["id"])})
    ).json()

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={"input_dataset_id": ds["id"]})
    assert r.status_code == 400, r.text
    assert "project" in r.json()["detail"].lower()


async def test_run_without_input_dataset_id_still_works(client: AsyncClient) -> None:
    ds = await _upload_csv(client)
    flow = (await client.post("/api/flows", json={"name": "r", "graph_json": _passthrough_graph(ds["id"])})).json()

    r = await client.post(f"/api/flows/{flow['id']}/runs", json={})
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "success"
