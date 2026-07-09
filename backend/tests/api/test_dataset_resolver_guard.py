"""The dataset resolver refuses disabled / soft-deleted datasets as flow inputs.

"disabled" and "deleted" must mean "do not use in new executions or previews".
Soft-delete keeps the file on disk, so without this guard a run could still read a
dataset the user believes is out of use. Historical *downloads* are a separate,
still-allowed path (they don't go through the resolver).
"""

import io

import pandas as pd
import pytest
from httpx import AsyncClient

from app.core.exceptions import ValidationError
from app.services.dataset_resolver import resolve_version


async def _upload(client: AsyncClient, name: str = "src.csv") -> dict:
    buf = io.BytesIO()
    pd.DataFrame({"a": [1, 2], "b": [3, 4]}).to_csv(buf, index=False)
    r = await client.post("/api/datasets/upload", files={"file": (name, buf.getvalue(), "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()


def _flow_graph(dataset_id: str) -> dict:
    return {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": dataset_id}}},
            {"id": "out1", "type": "csvOutput", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "out1"}],
    }


# -- resolver unit ----------------------------------------------------------


async def test_resolve_version_ok_for_live_dataset(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    ver = await resolve_version(db_session, ds["id"], None)
    assert ver.dataset_id == ds["id"]


async def test_resolve_version_rejects_disabled(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    await client.patch(f"/api/datasets/{ds['id']}", json={"is_disabled": True})
    with pytest.raises(ValidationError, match="disabled"):
        await resolve_version(db_session, ds["id"], None)


async def test_resolve_version_rejects_soft_deleted(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    await client.delete(f"/api/datasets/{ds['id']}")  # soft delete
    with pytest.raises(ValidationError, match="deleted"):
        await resolve_version(db_session, ds["id"], None)


async def test_resolve_version_allow_unavailable_bypasses_guard(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    await client.delete(f"/api/datasets/{ds['id']}")
    ver = await resolve_version(db_session, ds["id"], None, allow_unavailable=True)
    assert ver.dataset_id == ds["id"]


async def test_resolve_version_deleted_takes_precedence_over_disabled(client: AsyncClient, db_session) -> None:
    # A soft-deleted dataset is also is_disabled=True; the message should name the
    # stronger, more actionable "deleted" state.
    ds = await _upload(client)
    await client.delete(f"/api/datasets/{ds['id']}")
    with pytest.raises(ValidationError, match="deleted"):
        await resolve_version(db_session, ds["id"], None)


# -- run / preview via the API ----------------------------------------------


async def test_run_blocked_when_dataset_disabled(client: AsyncClient) -> None:
    ds = await _upload(client)
    # Create the flow while the dataset is live, then disable the dataset. The
    # PATCH cascade disables the flow too, so re-enable the flow to prove the
    # resolver itself is the guard (not just the disabled-flow check).
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": _flow_graph(ds["id"])})).json()
    await client.patch(f"/api/datasets/{ds['id']}", json={"is_disabled": True})
    await client.put(f"/api/flows/{flow['id']}", json={"is_disabled": False})

    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert run["status"] == "failed"
    assert "disabled" in run["error_message"]


async def test_run_blocked_when_dataset_soft_deleted(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": _flow_graph(ds["id"])})).json()
    await client.delete(f"/api/datasets/{ds['id']}")
    await client.put(f"/api/flows/{flow['id']}", json={"is_disabled": False})

    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert run["status"] == "failed"
    assert "deleted" in run["error_message"]


async def test_run_ok_after_restore(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = (await client.post("/api/flows", json={"name": "f", "graph_json": _flow_graph(ds["id"])})).json()
    await client.delete(f"/api/datasets/{ds['id']}")
    await client.post(f"/api/datasets/{ds['id']}/restore")
    await client.put(f"/api/flows/{flow['id']}", json={"is_disabled": False})

    run = (await client.post(f"/api/flows/{flow['id']}/runs", json={})).json()
    assert run["status"] == "success", run.get("error_message")


async def test_register_output_revives_soft_deleted_output_dataset(client: AsyncClient, db_session, tmp_path) -> None:
    """A run writing to a soft-deleted output dataset name revives it, so the new
    version isn't born already-deleted (and is reusable as an input)."""
    from app.services.dataset_service import DatasetService

    # Seed an output dataset by registering once, then soft-delete it.
    out_file = tmp_path / "out.csv"
    pd.DataFrame({"a": [1]}).to_csv(out_file, index=False)
    svc = DatasetService(db_session)
    first = await svc.register_output(name="result.csv", source_type="csv", file_path=out_file, project_id=None)
    await svc.db.commit()
    await client.delete(f"/api/datasets/{first.id}")

    # A later run writes to the same name again → revived, new version, live.
    again = await svc.register_output(name="result.csv", source_type="csv", file_path=out_file, project_id=None)
    await svc.db.commit()
    assert again.id == first.id
    assert again.deleted_at is None
    assert again.is_disabled is False
    assert again.version_count == 2


async def test_transformation_preview_blocked_when_disabled(client: AsyncClient) -> None:
    ds = await _upload(client)
    await client.patch(f"/api/datasets/{ds['id']}", json={"is_disabled": True})
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "selectColumns", "dataset_id": ds["id"], "config": {"columns": ["a"]}},
    )
    assert r.status_code == 400
    assert "disabled" in r.json()["detail"]
