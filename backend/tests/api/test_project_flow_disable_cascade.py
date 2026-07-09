"""Re-enabling a project restores only the flows the project cascade disabled.

A flow disabled by the user, or by a broken dataset dependency, must stay
disabled when the project is turned back on — the two reasons for "disabled"
(project inheritance vs the flow's own state) are tracked separately via
``flows.disabled_reason``.
"""

import io

from httpx import AsyncClient

GRAPH = {
    "nodes": [{"id": "n1", "type": "csvInput", "position": {"x": 0, "y": 0}, "data": {"config": {}}}],
    "edges": [],
}


async def _project(client: AsyncClient, name: str) -> dict:
    r = await client.post("/api/projects", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


async def _flow(client: AsyncClient, project_id: str, name: str, graph: dict | None = None) -> dict:
    r = await client.post("/api/flows", json={"name": name, "project_id": project_id, "graph_json": graph or GRAPH})
    assert r.status_code == 201, r.text
    return r.json()


async def _is_disabled(client: AsyncClient, flow_id: str) -> bool:
    return (await client.get(f"/api/flows/{flow_id}")).json()["is_disabled"]


async def _set_project_disabled(client: AsyncClient, project_id: str, disabled: bool) -> None:
    r = await client.put(f"/api/projects/{project_id}", json={"is_disabled": disabled})
    assert r.status_code == 200, r.text


# ---------------------------------------------------------------------------


async def test_project_disable_enable_roundtrips_plain_flow(client: AsyncClient) -> None:
    proj = await _project(client, "P1")
    flow = await _flow(client, proj["id"], "f1")
    assert await _is_disabled(client, flow["id"]) is False

    await _set_project_disabled(client, proj["id"], True)
    assert await _is_disabled(client, flow["id"]) is True

    await _set_project_disabled(client, proj["id"], False)
    assert await _is_disabled(client, flow["id"]) is False  # restored


async def test_reenable_keeps_manually_disabled_flow_off(client: AsyncClient) -> None:
    proj = await _project(client, "P2")
    manual = await _flow(client, proj["id"], "manual")
    cascaded = await _flow(client, proj["id"], "cascaded")

    # User disables one flow directly, before the project is touched.
    await client.put(f"/api/flows/{manual['id']}", json={"is_disabled": True})

    await _set_project_disabled(client, proj["id"], True)
    assert await _is_disabled(client, manual["id"]) is True
    assert await _is_disabled(client, cascaded["id"]) is True

    await _set_project_disabled(client, proj["id"], False)
    # The project cascade restores only the flow it disabled.
    assert await _is_disabled(client, cascaded["id"]) is False
    assert await _is_disabled(client, manual["id"]) is True  # stays off — user's choice


async def test_reenable_keeps_dataset_disabled_flow_off(client: AsyncClient) -> None:
    proj = await _project(client, "P3")
    # Upload into the project and build a flow that uses it as input.
    files = {"file": ("orders.csv", io.BytesIO(b"id,amt\n1,10\n"), "text/csv")}
    ds = (await client.post(f"/api/datasets/upload?project_id={proj['id']}", files=files)).json()
    graph = {
        "nodes": [{"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}}],
        "edges": [],
    }
    dep = await _flow(client, proj["id"], "dep", graph)
    plain = await _flow(client, proj["id"], "plain")

    # Disabling the dataset cascades to the dependent flow (reason=dataset).
    await client.patch(f"/api/datasets/{ds['id']}", json={"is_disabled": True})
    assert await _is_disabled(client, dep["id"]) is True

    await _set_project_disabled(client, proj["id"], True)
    await _set_project_disabled(client, proj["id"], False)

    assert await _is_disabled(client, plain["id"]) is False  # project-only → restored
    assert await _is_disabled(client, dep["id"]) is True  # dataset still disabled → stays off


async def test_reenable_restores_flow_user_left_project_disabled(client: AsyncClient) -> None:
    """Round-trip a plain project-disabled flow twice to prove the reason clears
    on restore (a second disable/enable still restores it)."""
    proj = await _project(client, "P5")
    flow = await _flow(client, proj["id"], "f")

    for _ in range(2):
        await _set_project_disabled(client, proj["id"], True)
        assert await _is_disabled(client, flow["id"]) is True
        await _set_project_disabled(client, proj["id"], False)
        assert await _is_disabled(client, flow["id"]) is False


async def test_echoing_unchanged_is_disabled_does_not_strand_flow(client: AsyncClient) -> None:
    """A save that echoes is_disabled unchanged (e.g. a rename) must NOT re-tag a
    project-cascaded flow as manual — otherwise a later project re-enable can't
    restore it."""
    proj = await _project(client, "P6")
    flow = await _flow(client, proj["id"], "f")
    await _set_project_disabled(client, proj["id"], True)

    # Rename while echoing the (unchanged) disabled state, as a full-object save would.
    r = await client.put(f"/api/flows/{flow['id']}", json={"name": "renamed", "is_disabled": True})
    assert r.status_code == 200, r.text

    await _set_project_disabled(client, proj["id"], False)
    assert await _is_disabled(client, flow["id"]) is False  # still restored


# -- dataset side (symmetric to flows) --------------------------------------


async def _dataset(client: AsyncClient, project_id: str, name: str) -> dict:
    files = {"file": (name, io.BytesIO(b"id,amt\n1,10\n"), "text/csv")}
    r = await client.post(f"/api/datasets/upload?project_id={project_id}", files=files)
    assert r.status_code == 201, r.text
    return r.json()


async def _ds_disabled(client: AsyncClient, dataset_id: str) -> bool:
    return (await client.get(f"/api/datasets/{dataset_id}")).json()["is_disabled"]


async def test_project_roundtrip_restores_project_disabled_dataset(client: AsyncClient) -> None:
    proj = await _project(client, "DP1")
    ds = await _dataset(client, proj["id"], "a.csv")

    await _set_project_disabled(client, proj["id"], True)
    assert await _ds_disabled(client, ds["id"]) is True
    await _set_project_disabled(client, proj["id"], False)
    assert await _ds_disabled(client, ds["id"]) is False  # restored


async def test_reenable_keeps_manually_disabled_dataset_off(client: AsyncClient) -> None:
    proj = await _project(client, "DP2")
    manual = await _dataset(client, proj["id"], "manual.csv")
    cascaded = await _dataset(client, proj["id"], "cascaded.csv")

    # User disables one dataset directly (not deleted) before touching the project.
    await client.patch(f"/api/datasets/{manual['id']}", json={"is_disabled": True})

    await _set_project_disabled(client, proj["id"], True)
    await _set_project_disabled(client, proj["id"], False)

    assert await _ds_disabled(client, cascaded["id"]) is False  # project-only → restored
    assert await _ds_disabled(client, manual["id"]) is True  # user's choice → stays off


async def test_reenable_keeps_soft_deleted_dataset_deleted(client: AsyncClient) -> None:
    proj = await _project(client, "DP3")
    ds = await _dataset(client, proj["id"], "d.csv")
    await client.delete(f"/api/datasets/{ds['id']}")  # soft delete (is_disabled + deleted_at)

    await _set_project_disabled(client, proj["id"], True)
    await _set_project_disabled(client, proj["id"], False)

    fetched = (await client.get(f"/api/datasets/{ds['id']}")).json()
    assert fetched["deleted_at"] is not None  # still deleted
    assert fetched["is_disabled"] is True  # not revived by the project re-enable
