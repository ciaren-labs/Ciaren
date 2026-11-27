"""Persistent edits, privacy, conservative inverses and transactional failure."""

import json
from copy import deepcopy
from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.exceptions import ConflictError
from app.db.models.flow import AssistantActivity, Flow
from app.schemas.flow import FlowUpdate
from app.services import assistant_activity as audit
from app.services import assistant_provider
from app.services.assistant_service import AssistantService
from app.services.flow_service import FlowService

PRIVATE = "activity-private-user-value"


@pytest.fixture
async def proposal(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "ASSISTANT_PROVIDER", "openai")
    monkeypatch.setattr(
        assistant_provider, "complete", AsyncMock(return_value={"steps": [{"kind": "limitRows", "count": 3}]})
    )
    flow = (await client.post("/api/flows", json={"name": PRIVATE})).json()
    data = (
        await client.post("/api/datasets/upload", files={"file": (PRIVATE + ".csv", PRIVATE + "\n" + PRIVATE + "\n")})
    ).json()
    url = f"/api/assistant/flows/{flow['id']}"
    body = dict(
        mode="build",
        provider="openai",
        question=PRIVATE,
        revision=flow["updated_at"],
        graph={"nodes": [], "edges": [], "engine": "pandas"},
        dataset_id=data["id"],
    )
    res = await client.post(url + "/turn", json=body)
    assert res.status_code == 200, res.text
    return flow, url, {"proposal": res.json()["proposal"]}


async def test_durable_scoped_reversal(client, db_session, proposal, monkeypatch, caplog):
    flow, url, token = proposal
    path = f"/api/flows/{flow['id']}"
    assert (await client.get(url + "/activity")).json()["entries"] == []
    saved = (await client.post(url + "/apply", json=token)).json()
    assert (await client.post(url + "/apply", json=token)).status_code == 409
    hist = await client.get(url + "/activity")
    assert hist.headers["cache-control"] == "no-store"
    (entry,) = hist.json()["entries"]
    target = url + "/activity/" + entry["id"]
    assert entry["source"] == "build" and entry["state"] == "available"
    assert PRIVATE not in hist.text
    raw = await db_session.get(AssistantActivity, entry["id"])
    assert PRIVATE not in json.dumps([raw.details, raw.inverse])
    other = (await client.post("/api/flows", json={"name": "Other"})).json()
    foreign = f"/api/assistant/flows/{other['id']}/activity"
    body = {"revision": saved["revision"]}
    assert (await client.get(foreign, params={"cursor": entry["id"]})).status_code == 404
    assert (await client.post(foreign + "/" + entry["id"] + "/preview", json=body)).status_code == 404
    assert (await client.post(target + "/revert", json=token)).status_code == 409
    monkeypatch.setattr(get_settings(), "ASSISTANT_PROVIDER", "off")
    preview = await client.post(target + "/preview", json=body)
    assert preview.status_code == 200 and PRIVATE not in preview.text
    assert len((await client.get(path)).json()["graph_json"]["nodes"]) == 3
    confirm = {"proposal": preview.json()["confirmation"]}
    assert (await client.post(foreign + "/" + entry["id"] + "/revert", json=confirm)).status_code == 409
    await client.put(path, json={"name": "Later name"})
    assert (await client.post(target + "/revert", json=confirm)).status_code == 409
    body["revision"] = (await client.get(path)).json()["updated_at"]
    confirm["proposal"] = (await client.post(target + "/preview", json=body)).json()["confirmation"]
    cfg = get_settings()
    monkeypatch.setattr(cfg, "API_TOKEN", "activity-test-token")
    for method, route, payload in [
        ("GET", url + "/activity", None),
        ("POST", target + "/preview", body),
        ("POST", target + "/revert", confirm),
    ]:
        assert (await client.request(method, route, json=payload)).status_code == 401
    monkeypatch.setattr(cfg, "API_TOKEN", None)
    res = await client.post(target + "/revert", json=confirm)
    assert res.status_code == 200, res.text
    assert (await client.post(target + "/revert", json=confirm)).status_code == 409
    current = (await client.get(path)).json()
    assert current["name"] == "Later name" and current["graph_json"]["nodes"] == []
    latest, original = (await client.get(url + "/activity")).json()["entries"]
    assert latest["reverses"] == entry["id"] and latest["source"] == "revert" and original["state"] == "reverted"
    assert PRIVATE not in caplog.text
    # Moving an existing flow must not expose the prior project's history.
    project = (await client.post("/api/projects", json={"name": "Different project"})).json()
    moved = await db_session.get(Flow, flow["id"])
    moved.project_id = project["id"]
    await db_session.commit()
    assert (await client.get(url + "/activity")).json()["entries"] == []
    assert (await client.post(target + "/preview", json={"revision": current["updated_at"]})).status_code == 404


async def test_activity_write_failure_rolls_back_flow(db_session, proposal):
    flow, _, token = proposal

    def fail(*args):
        raise RuntimeError("synthetic write failure")

    event.listen(AssistantActivity, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="synthetic write failure"):
            await AssistantService(db_session).apply(flow["id"], token["proposal"])
        await db_session.rollback()
    finally:
        event.remove(AssistantActivity, "before_insert", fail)
    assert not (await db_session.get(Flow, flow["id"])).graph_json
    assert not list(await db_session.scalars(select(AssistantActivity)))
    await AssistantService(db_session).apply(flow["id"], token["proposal"])
    assert len(list(await db_session.scalars(select(AssistantActivity)))) == 1


def node(key, kind, **cfg):
    return {"id": key, "type": kind, "data": {"config": cfg, "label": PRIVATE}}


def edge(a, b):
    return {"id": f"e_{a}_out_{b}_in", "source": a, "target": b, "sourceHandle": "out", "targetHandle": "in"}


async def test_manual_wiring_private_identifiers_and_independent_edits(db_session):
    a, b, c = node(PRIVATE, "fileInput"), node("b", "fileOutput"), node("c", "limitRows", n=1)
    original = {"nodes": [a, b], "edges": [edge(a["id"], "b")]}
    graph = {"nodes": [a, b, c], "edges": [edge(a["id"], "c"), edge("c", "b")]}
    delta = {"added": [c], "changed": [], "connected": graph["edges"], "disconnected": [original["edges"][0]["id"]]}
    receipt = audit.receipt("flow", "project", original, graph, delta, [], "build")
    assert receipt.inverse["usable"] and PRIVATE not in json.dumps([receipt.inverse, receipt.details])
    later = deepcopy(graph)
    later["nodes"].append(node("independent", "fileInput"))
    reverted = await audit.inverse_graph(db_session, receipt, later)
    assert reverted["edges"] == original["edges"] and reverted["nodes"] == [a, b, later["nodes"][-1]]
    later["edges"].append(edge("c", "independent"))
    with pytest.raises(ConflictError):
        await audit.inverse_graph(db_session, receipt, later)


async def test_join_reversal_keeps_downstream_edits_and_checks_both_sources(db_session):
    sources = [node("left", "fileInput"), node("right", "fileInput")]
    join = node("j", "join", how="inner", on=PRIVATE)
    output = node("sort", "sortRows", ascending=True)
    original = {"nodes": [*sources, join, output], "edges": [edge("left", "j"), edge("right", "j"), edge("j", "sort")]}
    graph = deepcopy(original)
    changed = graph["nodes"][2]
    changed["data"]["config"]["how"] = "left"
    delta = {"added": [], "changed": [changed], "connected": [], "disconnected": []}
    receipt = audit.receipt("flow", "project", original, graph, delta, [], "diagnose")
    assert PRIVATE not in json.dumps([receipt.inverse, receipt.details])
    later = deepcopy(graph)
    later["nodes"][-1]["data"]["config"]["ascending"] = False
    later["parameters"] = [{"name": "unrelated", "default": PRIVATE}]
    result = await audit.inverse_graph(db_session, receipt, later)
    expected = deepcopy(later)
    expected["nodes"][2]["data"]["config"]["how"] = "inner"
    assert result == expected
    for index in (0, 1, 2):
        conflict = deepcopy(later)
        conflict["nodes"][index]["data"]["config"]["how"] = "modified"
        with pytest.raises(ConflictError):
            await audit.inverse_graph(db_session, receipt, conflict)


async def test_history_cursor_ties(client, db_session):
    flow = (await client.post("/api/flows", json={"name": "Paged"})).json()
    ids = sorted(uuid4().hex for _ in range(22))
    for key in ids:
        db_session.add(
            AssistantActivity(
                id=key,
                flow_id=flow["id"],
                project_id=flow["project_id"],
                created_at=datetime(2026, 1, 1),
                source="build",
                details=[],
                inverse={},
            )
        )
    await db_session.commit()
    url = f"/api/assistant/flows/{flow['id']}/activity"
    page = (await client.get(url)).json()
    tail = (await client.get(url, params={"cursor": page["next"]})).json()
    assert [e["id"] for e in page["entries"] + tail["entries"]] == list(reversed(ids))
    assert not tail["next"]


async def test_narrow_inverse_preserves_offset_and_marks_missing_column(db_session):
    prior = node(PRIVATE, "limitRows", n=5, offset=0)
    before = {"nodes": [prior], "edges": []}
    after = deepcopy(before)
    current = after["nodes"][0]
    current["data"]["config"]["n"] = 10
    delta = {"added": [], "changed": [current], "connected": [], "disconnected": []}
    change = audit.receipt("flow", "project", before, after, delta, [], "build")
    current["data"]["config"]["offset"] = 4
    assert (await audit.inverse_graph(db_session, change, after))["nodes"][0]["data"]["config"] == {"n": 5, "offset": 4}
    prior.update(type="sortRows", data={"config": {"columns": [PRIVATE]}})
    current.update(type="sortRows", data={"config": {"columns": ["new"]}})
    change = audit.receipt("flow", "project", before, after, delta, [], "diagnose", {"new"})
    assert not change.inverse["usable"] and PRIVATE not in json.dumps(change.inverse)


async def test_conditional_editor_save_and_run_creation(client, proposal):
    flow, url, token = proposal
    path = "/api/flows/" + flow["id"]
    original = flow["updated_at"]
    applied = (await client.post(url + "/apply", json=token)).json()["revision"]
    graph = (await client.get(path)).json()["graph_json"]
    for endpoint, method, body in [(path, "PUT", {"graph_json": {}}), (path + "/runs", "POST", {})]:
        rejected = await client.request(method, endpoint, json={**body, "expected_revision": original})
        assert rejected.status_code == 409
    assert (await client.get(path)).json()["graph_json"] == graph
    assert (await client.get("/api/runs", params={"flow_id": flow["id"]})).json() == []
    # Another writer wins after pre-run save but before POST /runs.
    saved = await client.put(path, json={"expected_revision": applied, "graph_json": graph})
    assert saved.status_code == 200
    rev = saved.json()["updated_at"]
    assert (await client.put(path, json={"name": "Another edit", "expected_revision": rev})).status_code == 200
    assert (await client.post(path + "/runs", json={"expected_revision": rev})).status_code == 409
    assert (await client.get("/api/runs", params={"flow_id": flow["id"]})).json() == []
    # Explicit legacy compatibility: callers omitting expected_revision keep prior behavior.
    assert (await client.put(path, json={"name": "Legacy write"})).status_code == 200


async def test_save_response_pins_own_revision_after_another_writer_commits(
    client, engine, db_session, proposal, monkeypatch
):
    flow, _, _ = proposal
    commit = db_session.commit
    versions = []

    async def interleaved_commit():
        await commit()
        async with async_sessionmaker(engine, expire_on_commit=False)() as other:
            versions.append(await FlowService(other).update(flow["id"], FlowUpdate(name="Later writer")))

    monkeypatch.setattr(db_session, "commit", interleaved_commit)
    first = await FlowService(db_session).update(
        flow["id"], FlowUpdate(name="First writer", expected_revision=flow["updated_at"])
    )
    assert versions and versions[0].name == "Later writer"
    assert first.name == "First writer" and first.updated_at != versions[0].updated_at
    rejected = await client.post(
        f"/api/flows/{flow['id']}/runs", json={"expected_revision": first.updated_at.isoformat()}
    )
    assert rejected.status_code == 409


def test_revision_precision_across_metadata_dialects():
    from sqlalchemy import update
    from sqlalchemy.dialects import mysql, postgresql, sqlite
    from sqlalchemy.schema import CreateTable

    from app.services.flow_revision import next_revision

    for dialect in [mysql.dialect(), postgresql.dialect(), sqlite.dialect()]:
        ddl = str(CreateTable(Flow.__table__).compile(dialect=dialect))
        stamp = str(
            update(Flow)
            .where(Flow.id == "x", Flow.updated_at == datetime(2026, 1, 1))
            .values(updated_at=Flow.updated_at)
            .compile(dialect=dialect)
        )
        assert "RETURNING" not in stamp.upper()
        if dialect.name == "mysql":
            assert "updated_at DATETIME(6)" in ddl
            assert "created_at DATETIME(6)" in str(CreateTable(AssistantActivity.__table__).compile(dialect=dialect))
    future = datetime(2099, 1, 1)
    assert next_revision(future) > future


@pytest.mark.parametrize(
    ("edit", "conflict"),
    [({"position": {"x": 999, "y": 1}}, False), ({"data": {"config": {"n": 1}, "label": "Renamed"}}, True)],
    ids=["moved", "relabelled"],
)
async def test_added_node_guard_ignores_position_only(db_session, edit, conflict):
    a, b = node("a", "fileInput"), node("b", "fileOutput")
    added = {**node("c", "limitRows", n=1), "position": {"x": 0, "y": 0}}
    before = {"nodes": [a, b], "edges": [edge("a", "b")]}
    after = {"nodes": [a, b, added], "edges": [edge("a", "c"), edge("c", "b")]}
    delta = {"added": [added], "changed": [], "connected": after["edges"], "disconnected": [before["edges"][0]["id"]]}
    receipt = audit.receipt("flow", "project", before, after, delta, [], "build")
    later = deepcopy(after)
    later["nodes"][2].update(deepcopy(edit))
    if conflict:
        with pytest.raises(ConflictError):
            await audit.inverse_graph(db_session, receipt, later)
    else:
        assert (await audit.inverse_graph(db_session, receipt, later))["nodes"] == [a, b]


def test_removed_nodes_are_recorded_and_not_reversible():
    a, gone, b = node("a", "fileInput"), node("gone", "dropNulls"), node("b", "fileOutput")
    before = {"nodes": [a, gone, b], "edges": [edge("a", "gone"), edge("gone", "b")]}
    after = {"nodes": [a, b], "edges": [edge("a", "b")]}
    delta = {
        "added": [],
        "changed": [],
        "connected": after["edges"],
        "disconnected": [e["id"] for e in before["edges"]],
        "removed": ["gone"],
    }
    receipt = audit.receipt("flow", "project", before, after, delta, [], "build")
    assert {"action": "remove_node", "kind": "dropNulls"} in receipt.details
    assert {"action": "disconnect", "from": "dropNulls", "to": "fileOutput", "port": "in"} in receipt.details
    assert receipt.inverse["usable"] is False


async def test_reversal_survives_a_new_version_of_a_pinned_input(client, proposal):
    flow, url, token = proposal
    saved = (await client.post(url + "/apply", json=token)).json()["revision"]
    (entry,) = (await client.get(url + "/activity")).json()["entries"]
    graph = (await client.get(f"/api/flows/{flow['id']}")).json()["graph_json"]
    assert graph["nodes"][0]["data"]["config"]["dataset_version"] == 1
    upload = await client.post("/api/datasets/upload", files={"file": (PRIVATE + ".csv", "other\n1\n")})
    assert upload.json()["latest_version"] == 2
    target = url + "/activity/" + entry["id"]
    preview = await client.post(target + "/preview", json={"revision": saved})
    assert preview.status_code == 200, preview.text


@pytest.mark.parametrize(("pinned", "follows"), [(None, True), (1, False)], ids=["unpinned", "pinned"])
def test_receipt_inputs_follow_latest_only_through_unpinned_nodes(pinned, follows):
    from app.services.assistant_inputs import InputVersion

    source = node("in", "fileInput", dataset_id="d", **({"dataset_version": pinned} if pinned else {}))
    after = {"nodes": [source, node("c", "limitRows", n=1)], "edges": [edge("in", "c")]}
    delta = {"added": [after["nodes"][1]], "changed": [], "connected": after["edges"], "disconnected": []}
    version = InputVersion("d", "v1", 1, "csv", True)
    change = audit.receipt("flow", "project", {"nodes": [source], "edges": []}, after, delta, [version], "build")
    assert change.inverse["inputs"][0]["follows_latest"] is follows


@pytest.mark.parametrize("suffix", ["Z", "+00:00", "+02:00"])
async def test_reversal_accepts_timezone_aware_revisions(client, proposal, suffix):
    flow, url, token = proposal
    saved = (await client.post(url + "/apply", json=token)).json()["revision"]
    (entry,) = (await client.get(url + "/activity")).json()["entries"]
    target = url + "/activity/" + entry["id"]
    stamp = datetime.fromisoformat(saved.removesuffix("Z"))
    if suffix == "+02:00":
        from datetime import UTC, timedelta, timezone

        revision = stamp.replace(tzinfo=UTC).astimezone(timezone(timedelta(hours=2))).isoformat()
    else:
        revision = stamp.isoformat() + suffix
    preview = await client.post(target + "/preview", json={"revision": revision})
    assert preview.status_code == 200, preview.text
    res = await client.post(target + "/revert", json={"proposal": preview.json()["confirmation"]})
    assert res.status_code == 200, res.text
