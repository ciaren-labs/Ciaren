"""The assistant edit language: all-or-nothing ops, ordered gates, redaction, layout and delta."""

import json
from unittest.mock import AsyncMock

import pytest

from app.core.config import get_settings
from app.services import assistant_provider, assistant_service
from app.services.assistant_tools.context import ToolContext
from app.services.assistant_tools.edit import ProposeEdit, propose_edit, start
from app.services.assistant_tools.ops import diff

PRIVATE = "private_amount"
LABEL = "Secret label 9921"


@pytest.fixture
async def canvas(client, db_session):
    dataset = (
        await client.post("/api/datasets/upload", files={"file": ("edit.csv", f"city,{PRIVATE}\nLyon,3\n")})
    ).json()
    base = {
        "engine": "pandas",
        "nodes": [
            {
                "id": "a" * 32,
                "type": "fileInput",
                "position": {"x": 5, "y": 5},
                "data": {"label": LABEL, "config": {"dataset_id": dataset["id"], "format": "csv"}},
            },
            {
                "id": "b" * 32,
                "type": "pythonTransform",
                "position": {"x": 9, "y": 9},
                "data": {"label": "Script", "config": {"script": "return df"}},
            },
            {
                "id": "c" * 32,
                "type": "fileOutput",
                "position": {"x": 12, "y": 12},
                "data": {"label": "Out", "config": {"format": "csv", "dataset_name": "Scripted"}},
            },
        ],
        "edges": [
            {"id": "e1", "source": "a" * 32, "target": "b" * 32, "sourceHandle": "out", "targetHandle": "in"},
            {"id": "e2", "source": "b" * 32, "target": "c" * 32, "sourceHandle": "out", "targetHandle": "in"},
        ],
    }
    ctx = ToolContext(db_session, dataset["project_id"], base, datasets={"d0": dataset["id"]})
    return ctx, start(base)


def edit(*ops, reset=False):
    return ProposeEdit.model_validate({"ops": list(ops), "reset": reset})


ADD_LIMIT = {"op": "add_node", "as": "lim", "type": "limitRows", "config": {"n": 2, "offset": 0}}
ADD_OUT = {"op": "add_node", "as": "out", "type": "fileOutput", "config": {"dataset_name": "Edited"}}
WIRE = [{"op": "connect", "from": "n0", "to": "lim"}, {"op": "connect", "from": "lim", "to": "out"}]


async def test_valid_batch_maps_refs_lays_out_and_diffs(canvas):
    ctx, work = canvas
    add_filter = {"op": "add_node", "as": "keep", "type": "filterRows"}
    add_filter["config"] = {"column": "c1", "operator": ">", "value": 1}
    ops = [ADD_LIMIT, ADD_OUT, add_filter, *WIRE, {"op": "connect", "from": "n0", "to": "keep"}]
    work, result = await propose_edit(ctx, edit(*ops), work)
    assert result == {
        "ok": True,
        "nodes": {
            "n0": "fileInput",
            "n1": "pythonTransform",
            "n2": "fileOutput",
            "lim": "limitRows",
            "out": "fileOutput",
            "keep": "filterRows",
        },
        "issues": [],
    }
    nodes = {n["type"]: n for n in work.graph["nodes"] if n["id"] != "c" * 32}
    assert nodes["filterRows"]["data"]["config"]["column"] == PRIVATE
    assert nodes["fileInput"]["position"] == {"x": 5, "y": 5}
    # Layers: depth x 230 across, then branch x 150 down below the nodes already in that layer.
    assert nodes["limitRows"]["position"] == {"x": 310, "y": 270}
    assert nodes["filterRows"]["position"] == {"x": 310, "y": 420}
    assert nodes["fileOutput"]["position"] == {"x": 540, "y": 270}
    delta = diff(work)
    assert {n["type"] for n in delta["added"]} == {"limitRows", "fileOutput", "filterRows"}
    assert len(delta["connected"]) == 3 and delta["changed"] == delta["disconnected"] == [] and "removed" not in delta
    # A later call can disconnect, update and remove what this turn created.
    later = [
        {"op": "disconnect", "from": "n0", "to": "keep"},
        {"op": "remove_node", "node": "keep"},
        {"op": "update_config", "node": "lim", "set": {"n": 7}},
    ]
    work, result = await propose_edit(ctx, edit(*later), work)
    assert result["ok"], result
    assert "filterRows" not in {n["type"] for n in work.graph["nodes"]} and len(work.graph["edges"]) == 4
    work, result = await propose_edit(ctx, edit(ADD_LIMIT, ADD_OUT, *WIRE, reset=True), work)
    assert result["ok"] and len(work.graph["nodes"]) == 5


@pytest.mark.parametrize(
    ("op", "code"),
    [
        ({"op": "update_config", "node": "n1", "set": {"script": "import os"}}, "locked_node"),
        ({"op": "connect", "from": "n0", "to": "n1"}, "locked_node"),
        ({"op": "remove_node", "node": "n1"}, "locked_node"),
        ({"op": "remove_node", "node": "n0"}, "policy"),
        ({"op": "connect", "from": "n0", "to": "ghost"}, "bad_ref"),
        ({"op": "add_node", "as": "py", "type": "pythonTransform", "config": {"script": "return df"}}, "policy"),
        ({"op": "add_node", "as": "sql", "type": "sqlOutput", "config": {}}, "policy"),
        ({"op": "add_node", "as": "f", "type": "filterRows", "config": {"column": "{{ p }}", "value": 1}}, "policy"),
        ({"op": "add_node", "as": "f", "type": "filterRows", "config": {"operator": ">"}}, "config"),
        ({"op": "add_node", "as": "f", "type": "limitRows", "config": {"n": "many"}}, "bad_type"),
        ({"op": "add_node", "as": "f", "type": "filterRows", "config": {"column": "c9", "value": 1}}, "missing_column"),
        (
            {"op": "add_node", "as": "e", "type": "filterExpression", "config": {"expression": "os.system('x')"}},
            "policy",
        ),
        ({"op": "add_node", "as": "e", "type": "mlPredict", "config": {"model_uri": "runs:/x"}}, "policy"),
        ({"op": "connect", "from": "n0", "to": "n0"}, "cycle"),
    ],
)
async def test_rejected_batch_leaves_working_graph_unchanged(ml, canvas, op, code):
    ctx, work = canvas
    before = json.dumps(work.graph, sort_keys=True)
    ops = [ADD_LIMIT, op] if op.get("op") != "add_node" or op["as"] == "lim" else [op, ADD_LIMIT]
    if op.get("type") in {"filterRows", "filterExpression", "limitRows", "mlPredict"}:
        ops.append({"op": "connect", "from": "n0", "to": op["as"]})
    after, result = await propose_edit(ctx, edit(*ops), work)
    assert after is work and json.dumps(work.graph, sort_keys=True) == before
    assert not result["ok"] and code in {i["code"] for i in result["issues"]}, result
    text = json.dumps(result)
    assert PRIVATE not in text and LABEL not in text and "a" * 32 not in text
    assert all(len(i["message"]) <= 200 for i in result["issues"])


@pytest.fixture
def ml(monkeypatch):
    monkeypatch.setattr(get_settings(), "ML_ENABLED", True)


RF = {"model_type": "random_forest_regressor", "target_column": "c1"}


@pytest.mark.parametrize(
    ("node_type", "config", "code"),
    [
        ("mlCrossValidate", {"n_splits": "x"}, "config"),
        ("mlCrossValidate", {"n_repeats": None}, "config"),
        ("mlCrossValidate", {"cv_strategy": ["leave_one_out"]}, "config"),
        ("mlTrainRegressor", {**RF, "hyperparameters": [{}]}, "config"),
        ("mlTrainRegressor", {**RF, "hyperparameters": ["alpha"]}, "config"),
        ("mlTrainRegressor", {**RF, "hyperparameters": "n_jobs"}, "config"),
        ("mlTrainRegressor", {**RF, "model_type": ["ridge"]}, "config"),
        ("mlTrainRegressor", {**RF, "hyperparameters": {"n_estimators": 1e9}}, "config"),
        ("mlTrainRegressor", {**RF, "hyperparameters": {"max_depth": 64.5}}, "config"),
        ("mlTrainRegressor", {**RF, "hyperparameters": {"n_estimators": True}}, "config"),
        (
            "mlTrainClassifier",
            {**RF, "model_type": "lightgbm_classifier", "hyperparameters": {"num_leaves": 5000}},
            "limit",
        ),
        (
            "mlTrainClassifier",
            {**RF, "model_type": "logistic_regression", "hyperparameters": {"max_iter": 10**6}},
            "limit",
        ),
        ("mlPredict", {"model_uri": ["x"]}, "config"),
        # Column fields are bound to names before the model gate; unhashable values must not crash it.
        ("filterRows", {"column": {"x": 1}, "value": 1}, "bad_type"),
        ("sortRows", {"columns": [["c0"]]}, "bad_type"),
        ("renameColumns", {"mapping": ["c0"]}, "bad_type"),
    ],
)
async def test_malformed_values_are_issues_not_errors(ml, canvas, node_type, config, code):
    ctx, work = canvas
    op = {"op": "add_node", "as": "m", "type": node_type, "config": config}
    after, result = await propose_edit(ctx, edit(op, {"op": "connect", "from": "n0", "to": "m"}), work)
    assert after is work and not result["ok"]
    assert result["issues"][0]["code"] == code, result


def test_graph_limit_is_reported():
    from app.services.assistant_tools import gates
    from app.services.assistant_tools.ops import EditRejected

    nodes = [{"id": f"x{i}", "type": "limitRows", "data": {"label": "L", "config": {"n": 1}}} for i in range(81)]
    with pytest.raises(EditRejected) as rejected:
        gates.check(start({"nodes": nodes, "edges": []}), set())
    assert rejected.value.issues[0].code == "limit"


async def test_apply_rechecks_policy_on_the_reviewed_graph(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "ASSISTANT_PROVIDER", "openai")
    monkeypatch.setattr(
        assistant_provider, "complete", AsyncMock(return_value={"steps": [{"kind": "limitRows", "count": 1}]})
    )
    flow = (await client.post("/api/flows", json={"name": "Recheck"})).json()
    dataset = (await client.post("/api/datasets/upload", files={"file": ("r.csv", "a\n1\n")})).json()
    url = f"/api/assistant/flows/{flow['id']}"
    body = {"mode": "build", "provider": "openai", "question": "Limit", "revision": flow["updated_at"]}
    proposal = (await client.post(url + "/turn", json={**body, "dataset_id": dataset["id"]})).json()["proposal"]
    # A reviewed graph that no longer passes the policy is never written.
    pending = assistant_service._pending[proposal]
    limit = next(n for n in pending.graph["nodes"] if n["type"] == "limitRows")
    limit.update(type="pythonTransform")
    limit["data"]["config"] = {"script": "return df"}
    assert (await client.post(url + "/apply", json={"proposal": proposal})).status_code == 409
    assert not (await client.get(f"/api/flows/{flow['id']}")).json()["graph_json"]
