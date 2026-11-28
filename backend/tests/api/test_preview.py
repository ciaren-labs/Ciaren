"""
Preview endpoint tests.

  GET  /api/transformations
  POST /api/transformations/preview
  POST /api/flows/{flow_id}/preview
"""

import io
from typing import Any

import pandas as pd
import pytest
from httpx import AsyncClient

from app.core.exceptions import ValidationError
from app.engine.transformations.base import BaseTransformation
from app.services import preview_service
from app.services.preview_service import ISSUE_TEMPLATES, preview_graph, redact_issue

ROWS: list[dict[str, Any]] = [
    {"name": "Alice", "age": 30, "city": "NYC"},
    {"name": "Bob", "age": None, "city": "LA"},
    {"name": "Charlie", "age": 35, "city": "NYC"},
]


def _csv(rows: list[dict] = ROWS) -> bytes:
    buf = io.BytesIO()
    pd.DataFrame(rows).to_csv(buf, index=False)
    return buf.getvalue()


async def _upload(client: AsyncClient, content: bytes | None = None, filename: str = "test.csv") -> dict:
    r = await client.post(
        "/api/datasets/upload",
        files={"file": (filename, content or _csv(), "text/csv")},
    )
    assert r.status_code == 201, r.text
    return r.json()


# -- GET /api/transformations ------------------------------------------


async def test_list_transformations(client: AsyncClient) -> None:
    r = await client.get("/api/transformations")
    assert r.status_code == 200
    types = r.json()
    assert "dropNulls" in types
    assert "castDtypes" in types


# -- POST /api/transformations/preview ---------------------------------


async def test_preview_transformation_drop_nulls(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": ds["id"], "config": {}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["row_count"] == 2  # one null age row dropped
    assert body["columns"] == ["name", "age", "city"]
    assert body["truncated"] is False


async def test_preview_transformation_with_config(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={
            "type": "renameColumns",
            "dataset_id": ds["id"],
            "config": {"mapping": {"name": "full_name"}},
        },
    )
    assert r.status_code == 200, r.text
    assert "full_name" in r.json()["columns"]


async def test_preview_transformation_limit(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": ds["id"], "config": {}, "limit": 1},
    )
    body = r.json()
    assert len(body["rows"]) == 1
    assert body["row_count"] == 2
    assert body["truncated"] is True


async def test_preview_transformation_profile_flag(client: AsyncClient) -> None:
    ds = await _upload(client)
    # Without the flag, no profile is computed.
    plain = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": ds["id"], "config": {}},
    )
    assert plain.json()["profile"] is None

    r = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": ds["id"], "config": {}, "profile": True},
    )
    assert r.status_code == 200, r.text
    profile = r.json()["profile"]
    assert profile is not None
    by_name = {p["name"]: p for p in profile}
    assert set(by_name) == {"name", "age", "city"}
    assert by_name["age"]["dtype"] in {"integer", "float"}


async def test_preview_transformation_unknown_type(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "nope", "dataset_id": ds["id"], "config": {}},
    )
    assert r.status_code == 404


async def test_preview_transformation_bad_config(client: AsyncClient) -> None:
    ds = await _upload(client)
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "renameColumns", "dataset_id": ds["id"], "config": {}},
    )
    assert r.status_code == 400


async def test_preview_transformation_missing_dataset(client: AsyncClient) -> None:
    r = await client.post(
        "/api/transformations/preview",
        json={"type": "dropNulls", "dataset_id": "does-not-exist", "config": {}},
    )
    assert r.status_code == 404


# -- POST /api/flows/{flow_id}/preview ---------------------------------


async def _create_flow(client: AsyncClient, dataset_id: str) -> dict:
    graph = {
        "nodes": [
            {
                "id": "in1",
                "type": "csvInput",
                "data": {"config": {"dataset_id": dataset_id}},
            },
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in1", "target": "drop"}],
    }
    r = await client.post("/api/flows", json={"name": "f", "graph_json": graph})
    assert r.status_code == 201, r.text
    return r.json()


async def test_preview_flow_default_node(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, ds["id"])
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={})
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 2  # deepest node = dropNulls


async def test_preview_flow_specific_node(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, ds["id"])
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={"node_id": "in1"})
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 3  # input node, nothing dropped yet


async def test_preview_flow_unknown_node(client: AsyncClient) -> None:
    ds = await _upload(client)
    flow = await _create_flow(client, ds["id"])
    r = await client.post(f"/api/flows/{flow['id']}/preview", json={"node_id": "ghost"})
    assert r.status_code == 404


async def test_preview_flow_missing_flow(client: AsyncClient) -> None:
    r = await client.post("/api/flows/nope/preview", json={})
    assert r.status_code == 404


async def test_preview_blocked_when_flow_disabled(client: AsyncClient) -> None:
    # Mirrors ExecutionService.run()'s "disabled flow can't run" guard — preview
    # executes real transformation logic too, so it must refuse the same way.
    ds = await _upload(client)
    flow = await _create_flow(client, ds["id"])
    r = await client.put(f"/api/flows/{flow['id']}", json={"is_disabled": True})
    assert r.status_code == 200, r.text

    r = await client.post(f"/api/flows/{flow['id']}/preview", json={})
    assert r.status_code == 400, r.text
    assert "disabled" in r.json()["detail"].lower()


async def test_preview_blocked_for_branch_fed_only_by_still_enabled_dataset(client: AsyncClient) -> None:
    """Regression: a flow disabled via one input dataset's cascade must block
    preview of *every* node — including one fed only by a different, still-
    enabled dataset. Previously only ExecutionService.run() enforced this, so a
    disabled flow's data could still be read and transformed through preview."""
    # Distinct filenames: _upload() with the same name would create a second
    # *version* of the same dataset instead of a genuinely separate one.
    ds_a = await _upload(client, filename="a.csv")
    ds_b = await _upload(client, filename="b.csv")
    graph = {
        "nodes": [
            {"id": "in_a", "type": "csvInput", "data": {"config": {"dataset_id": ds_a["id"]}}},
            {"id": "in_b", "type": "csvInput", "data": {"config": {"dataset_id": ds_b["id"]}}},
            {"id": "drop_b", "type": "dropNulls", "data": {"config": {}}},
        ],
        "edges": [{"id": "e1", "source": "in_b", "target": "drop_b"}],
    }
    r = await client.post("/api/flows", json={"name": "multi-input", "graph_json": graph})
    assert r.status_code == 201, r.text
    flow_id = r.json()["id"]

    # Disabling dataset A cascades to disable the whole flow, even though the
    # "drop_b" branch is fed only by dataset B, which stays enabled.
    r = await client.patch(f"/api/datasets/{ds_a['id']}", json={"is_disabled": True})
    assert r.status_code == 200, r.text
    assert (await client.get(f"/api/flows/{flow_id}")).json()["is_disabled"] is True

    r = await client.post(f"/api/flows/{flow_id}/preview", json={"node_id": "drop_b"})
    assert r.status_code == 400, r.text
    assert "disabled" in r.json()["detail"].lower()


async def test_preview_only_computes_the_upstream_slice(client: AsyncClient) -> None:
    """A failing node elsewhere in the flow (violated assertion) must not break
    previews of nodes that don't depend on it — preview computes only the
    requested node's ancestors."""
    ds = await _upload(client)
    graph = {
        "nodes": [
            {"id": "in1", "type": "csvInput", "data": {"config": {"dataset_id": ds["id"]}}},
            {"id": "drop", "type": "dropNulls", "data": {"config": {}}},
            # A sibling branch whose assertion always fails (needs >= 99 rows).
            {"id": "boom", "type": "assertRowCount", "data": {"config": {"min_rows": 99}}},
        ],
        "edges": [
            {"id": "e1", "source": "in1", "target": "drop"},
            {"id": "e2", "source": "in1", "target": "boom"},
        ],
    }
    r = await client.post("/api/flows", json={"name": "f2", "graph_json": graph})
    assert r.status_code == 201, r.text
    flow_id = r.json()["id"]

    # The clean branch previews fine…
    r = await client.post(f"/api/flows/{flow_id}/preview", json={"node_id": "drop"})
    assert r.status_code == 200, r.text
    assert r.json()["row_count"] == 2

    # …while previewing the failing node itself surfaces a clear 400 naming
    # the node (previously an unhandled 500).
    r = await client.post(f"/api/flows/{flow_id}/preview", json={"node_id": "boom"})
    assert r.status_code == 400, r.text
    detail = r.json()["detail"]
    assert "boom" in detail and "assertRowCount" in detail


# -- preview_graph (unsaved assistant graphs) ----------------------------

WIDE = [{"name": f"p{i}", "age": i, "city": "NYC" if i % 2 else "LA"} for i in range(12)]


def _encoded(fmt: str) -> tuple[str, bytes]:
    frame = pd.DataFrame(WIDE)
    buf = io.BytesIO()
    if fmt == "parquet":
        frame.to_parquet(buf, index=False)
    elif fmt == "jsonl":
        frame.to_json(buf, orient="records", lines=True)
    else:
        frame.to_csv(buf, index=False)
    return f"wide.{fmt}", buf.getvalue()


def _graph(dataset: dict, *steps: dict) -> dict:
    nodes = [
        {
            "id": "in1",
            "type": "fileInput",
            "data": {"config": {"dataset_id": dataset["id"], "format": dataset["source_type"]}},
        },
        *steps,
    ]
    chain = [n["id"] for n in nodes]
    edges = [{"id": f"e{i}", "source": a, "target": b} for i, (a, b) in enumerate(zip(chain, chain[1:], strict=False))]
    return {"nodes": nodes, "edges": edges}


@pytest.mark.parametrize("fmt", ["csv", "parquet", "jsonl"])
async def test_preview_graph_samples_inputs_and_types_every_node(client: AsyncClient, db_session, fmt) -> None:
    ds = await _upload(client, *reversed(_encoded(fmt)))
    graph = _graph(ds, {"id": "pick", "type": "selectColumns", "data": {"config": {"columns": ["age", "city"]}}})

    result = await preview_graph(db_session, ds["project_id"], graph, None, limit=2, profile=True, sample_rows=5)

    assert result.issues == [] and result.node == "pick" and result.sampled
    assert result.preview is not None
    assert result.preview.row_count == 5 and len(result.preview.rows) == 2 and result.preview.profile
    assert [c for c, _ in result.schemas["in1"]] == ["name", "age", "city"]
    assert dict(result.schemas["pick"]) == {"age": "int64", "city": "object"}


async def test_preview_graph_rejects_inputs_outside_the_project(client: AsyncClient, db_session) -> None:
    project = (await client.post("/api/projects", json={"name": "Elsewhere"})).json()
    ds = await _upload(client)
    with pytest.raises(ValidationError):
        await preview_graph(db_session, project["id"], _graph(ds), "in1", limit=5, profile=False)


async def test_preview_graph_reports_failures_as_issues(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    graph = _graph(ds, {"id": "pick", "type": "selectColumns", "data": {"config": {"columns": ["ghost"]}}})

    result = await preview_graph(db_session, ds["project_id"], graph, "pick", limit=5, profile=False)

    assert result.preview is None and [(i.node, i.code) for i in result.issues] == [("pick", "missing_column")]


@pytest.mark.parametrize(
    ("node", "code", "computed"),
    [
        # Preview never fits, so a train node's column checks come from validate_with_schema.
        (
            {
                "type": "mlTrainRegressor",
                "config": {
                    "seed": 1,
                    "model_type": "linear_regression",
                    "target_column": "age",
                    "feature_columns": ["ghost"],
                },
            },
            "missing_column",
            True,
        ),
        ({"type": "trainTestSplit", "config": {"seed": 1, "test_size": 0.5}}, "limit", False),
    ],
)
async def test_preview_graph_reports_ml_schema_issues(
    client: AsyncClient, db_session, monkeypatch, node, code, computed
) -> None:
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "ML_ENABLED", True)
    ds = await _upload(client, *reversed(_encoded("csv")))
    step = {"id": "ml", "type": node["type"], "data": {"config": node["config"]}}

    result = await preview_graph(db_session, ds["project_id"], _graph(ds, step), None, limit=5, profile=False)

    assert [(i.node, i.code) for i in result.issues] == [("ml", code)]
    assert ("ml" in result.schemas) is computed


@pytest.mark.parametrize(
    ("message", "refs"),
    [
        ("Column 'salary' not found", " Refs: c0."),
        ("unable to parse: alice@example.com, at position 0", ""),
        ("Values [alice, bob] are not in salary or 'Order Total'", " Refs: c0, c1."),
        ("Join (node-7) failed: salary", " Refs: c0, n0."),
        ("x" * 300 + " salary", " Refs: c0."),
    ],
)
def test_redact_emits_only_templates_and_refs(message: str, refs: str) -> None:
    known = {"salary": "c0", "Order Total": "c1", "node-7": "n0", "alice": "Not A Ref"}
    assert redact_issue(message, "config", known) == {"code": "config", "message": ISSUE_TEMPLATES["config"] + refs}


def test_redact_rejects_unknown_codes() -> None:
    with pytest.raises(ValueError):
        redact_issue("boom", "surprise", {})


class _PluginEcho(BaseTransformation):
    type = "pluginEchoForPreviewTest"

    def validate_config(self, config: dict[str, Any]) -> None:
        return None

    def execute(self, engine: Any, inputs: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
        raise AssertionError("a plugin node must not run in an assistant preview")

    def to_python_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        return ""

    def to_polars_code(self, input_vars: dict[str, str], output_vars: dict[str, str], config: dict[str, Any]) -> str:
        return ""


@pytest.mark.parametrize(
    "step",
    [
        {"type": "pythonTransform", "config": {"script": "raise SystemExit('ran')"}},
        {"type": "filterExpression", "config": {"expression": "age > 1"}},
        {"type": "calculatedColumn", "config": {"column_name": "x", "expression": "age * 2"}},
        {"type": "assertExpression", "config": {"expression": "age > 0"}},
        {"type": "pluginEchoForPreviewTest", "config": {}},
        {"type": "neverRegisteredNode", "config": {}},
        {"type": "sqlOutput", "config": {}},
        {"type": "csvOutput", "config": {"path": "x.csv"}},
        {"type": "mlPredict", "config": {"model_uri": "file:///tmp/model.pkl"}},
    ],
    ids=lambda s: s["type"],
)
async def test_preview_graph_refuses_unsafe_nodes_before_running(client: AsyncClient, db_session, step) -> None:
    from app.engine.registry import register_transformations, unregister_transformations

    register_transformations(_PluginEcho())
    try:
        ds = await _upload(client)
        graph = _graph(ds, {"id": "risky", "type": step["type"], "data": {"config": step["config"]}})
        result = await preview_graph(db_session, ds["project_id"], graph, None, limit=5, profile=False)
    finally:
        unregister_transformations(_PluginEcho.type)
    assert result.preview is None and [(i.node, i.code) for i in result.issues] == [("risky", "policy")]


async def test_preview_graph_estimates_joins_before_running_them(client: AsyncClient, db_session, monkeypatch) -> None:
    monkeypatch.setattr(preview_service, "PREVIEW_MAX_NODE_ROWS", 50)
    ds = await _upload(client, *reversed(_encoded("csv")))
    graph = _graph(ds)
    graph["nodes"].append({"id": "j", "type": "join", "data": {"config": {"on": ["city"], "how": "inner"}}})
    graph["edges"] += [
        {"id": "l", "source": "in1", "target": "j", "targetHandle": "left"},
        {"id": "r", "source": "in1", "target": "j", "targetHandle": "right"},
    ]
    merged = []
    monkeypatch.setattr(pd.DataFrame, "merge", lambda *a, **k: merged.append(1))

    result = await preview_graph(db_session, ds["project_id"], graph, "j", limit=5, profile=False)

    assert [(i.node, i.code) for i in result.issues] == [("j", "limit")] and not merged


@pytest.mark.parametrize("cap", ["rows", "deadline", "json_bytes"])
async def test_preview_graph_stops_at_resource_limits(client: AsyncClient, db_session, monkeypatch, cap) -> None:
    fmt = "json" if cap == "json_bytes" else "csv"
    frame = pd.DataFrame(WIDE)
    content = frame.to_json(orient="records").encode() if fmt == "json" else frame.to_csv(index=False).encode()
    ds = await _upload(client, content, f"capped.{fmt}")
    if cap == "rows":
        monkeypatch.setattr(preview_service, "PREVIEW_MAX_NODE_ROWS", 5)
    elif cap == "deadline":
        monkeypatch.setattr(preview_service, "PREVIEW_DEADLINE_SECONDS", 0)
    else:
        monkeypatch.setattr(preview_service, "PREVIEW_MAX_JSON_BYTES", 64)
    graph = _graph(ds, {"id": "keep", "type": "dropNulls", "data": {"config": {}}})

    result = await preview_graph(db_session, ds["project_id"], graph, None, limit=5, profile=False, sample_rows=10)

    assert result.preview is None and [(i.node, i.code) for i in result.issues] == [("in1", "limit")]


def test_every_registered_type_is_classified_for_preview() -> None:
    from app.engine.registry import list_transformation_types

    registered = set(list_transformation_types())
    safe, excluded = preview_service.PREVIEW_SAFE_TYPES, preview_service.PREVIEW_EXCLUDED
    assert safe <= registered and set(excluded) <= registered
    assert not safe & set(excluded) and all(reason.strip() for reason in excluded.values())
    # A new node type fails here until someone decides whether a preview may run it.
    assert registered == safe | set(excluded)


@pytest.mark.parametrize("guard", ["none", "rejects"])
@pytest.mark.parametrize("kind", ["calculatedColumn", "filterExpression", "assertExpression"])
async def test_expression_payloads_never_run_without_an_accepting_guard(
    client: AsyncClient, db_session, tmp_path, kind, guard
) -> None:
    sentinel = tmp_path / "written.csv"
    payload = f"age.to_csv({str(sentinel)!r}) == age"
    ds = await _upload(client)
    step = {"id": "expr", "type": kind, "data": {"config": {"column_name": "x", "expression": payload}}}
    seen: list[str] = []

    def rejecting(expression: str) -> None:
        seen.append(expression)
        raise ValueError("attribute calls are not allowed")

    result = await preview_graph(
        db_session,
        ds["project_id"],
        _graph(ds, step),
        None,
        limit=5,
        profile=False,
        expression_guard=rejecting if guard == "rejects" else None,
    )

    assert [(i.node, i.code) for i in result.issues] == [("expr", "policy")] and not sentinel.exists()
    assert seen == ([payload] if guard == "rejects" else [])


async def test_expression_nodes_run_once_the_guard_accepts(client: AsyncClient, db_session) -> None:
    ds = await _upload(client)
    step = {"id": "expr", "type": "calculatedColumn", "data": {"config": {"column_name": "x", "expression": "age * 2"}}}
    seen: list[str] = []

    result = await preview_graph(
        db_session, ds["project_id"], _graph(ds, step), None, limit=5, profile=False, expression_guard=seen.append
    )

    assert result.issues == [] and seen == ["age * 2"] and "x" in dict(result.schemas["expr"])


@pytest.mark.parametrize("shape", ["nodes", "edges", "fan_in"])
async def test_preview_graph_enforces_graph_shape_limits(client: AsyncClient, db_session, shape) -> None:
    ds = await _upload(client)
    graph = _graph(ds)
    if shape == "nodes":
        graph["nodes"] += [{"id": f"s{i}", "type": "dropNulls", "data": {"config": {}}} for i in range(80)]
    elif shape == "edges":
        graph["nodes"] += [{"id": f"s{i}", "type": "concatRows", "data": {"config": {}}} for i in range(21)]
        graph["edges"] += [
            {"id": f"x{i}_{j}", "source": "in1", "target": f"s{i}", "targetHandle": "in"}
            for i in range(21)
            for j in range(8)
        ]
    else:
        graph["nodes"].append({"id": "many", "type": "concatRows", "data": {"config": {}}})
        graph["edges"] += [{"id": f"f{j}", "source": "in1", "target": "many", "targetHandle": "in"} for j in range(9)]

    result = await preview_graph(db_session, ds["project_id"], graph, None, limit=5, profile=False)

    assert result.preview is None and [i.code for i in result.issues] == ["limit"]
    assert result.issues[0].node == ("many" if shape == "fan_in" else None)


@pytest.mark.parametrize(
    ("step", "edges", "method"),
    [
        ({"type": "concatRows", "config": {}}, 3, "concat"),
        ({"type": "unpivot", "config": {"id_vars": ["name"]}}, 1, "melt"),
        ({"type": "explodeRows", "config": {"column": "tags", "delimiter": ","}}, 1, "explode"),
    ],
    ids=lambda v: v if isinstance(v, str) else None,
)
async def test_preview_graph_estimates_fan_out_before_running(
    client: AsyncClient, db_session, monkeypatch, step, edges, method
) -> None:
    rows = [{"name": f"p{i}", "age": i, "tags": "a,b,c"} for i in range(12)]
    ds = await _upload(client, _csv(rows), "fanout.csv")
    monkeypatch.setattr(preview_service, "PREVIEW_MAX_NODE_ROWS", 20)
    graph = _graph(ds)
    graph["nodes"].append({"id": "big", "type": step["type"], "data": {"config": step["config"]}})
    graph["edges"] += [{"id": f"b{j}", "source": "in1", "target": "big", "targetHandle": "in"} for j in range(edges)]
    calls: list[str] = []
    target = pd if method == "concat" else pd.DataFrame
    monkeypatch.setattr(target, method, lambda *a, **k: calls.append(method))

    result = await preview_graph(db_session, ds["project_id"], graph, "big", limit=5, profile=False)

    assert [(i.node, i.code) for i in result.issues] == [("big", "limit")] and not calls


async def test_preview_deadline_is_checked_before_a_node_runs(client: AsyncClient, db_session, monkeypatch) -> None:
    ds = await _upload(client)
    monkeypatch.setattr(preview_service, "PREVIEW_DEADLINE_SECONDS", 0)
    reads: list[str] = []
    monkeypatch.setattr(pd, "read_csv", lambda *a, **k: reads.append("read"))

    result = await preview_graph(db_session, ds["project_id"], _graph(ds), None, limit=5, profile=False)

    assert [(i.node, i.code) for i in result.issues] == [("in1", "limit")] and not reads


async def test_safe_type_names_must_still_resolve_to_built_in_code(
    client: AsyncClient, db_session, monkeypatch
) -> None:
    from app.engine import registry

    # A safe name served by non-built-in code (e.g. a registry swap) is refused.
    monkeypatch.setitem(registry._REGISTRY, "sortRows", _PluginEcho())
    ds = await _upload(client)
    step = {"id": "swapped", "type": "sortRows", "data": {"config": {"columns": ["age"]}}}

    result = await preview_graph(db_session, ds["project_id"], _graph(ds, step), None, limit=5, profile=False)

    assert [(i.node, i.code) for i in result.issues] == [("swapped", "policy")]
