# SPDX-License-Identifier: AGPL-3.0-only
"""Compile a narrow proposal language into ordinary editor nodes and edges."""

from copy import deepcopy
from typing import Any
from uuid import uuid4

from app.core.exceptions import ValidationError
from app.engine.graph import GraphValidationError, topological_sort, validate_graph, validate_node_configs
from app.engine.parameters import ParameterError, apply_parameters, validate_parameter_specs
from app.plugins import get_registry
from app.schemas.assistant import Plan, Step

Graph = dict[str, Any]
INPUTS = {"fileInput", "csvInput", "excelInput", "parquetInput", "textInput", "jsonInput"}
OUTPUTS = {"fileOutput", "csvOutput", "excelOutput", "parquetOutput"}
STEPS = {"limitRows", "sortRows", "dropNulls", "removeDuplicates", "selectColumns", "dropColumns", "filterRows"}
SAFE = INPUTS | OUTPUTS | STEPS


def inspect(graph: Graph) -> tuple[list[Graph], list[Graph]]:
    nodes, edges = graph.get("nodes", []), graph.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list) or len(nodes) > 80 or len(edges) > 160:
        raise ValidationError("Canvas exceeds the assistant graph limit.")
    ids = set()
    for n in nodes:
        if not (
            isinstance(n, dict)
            and isinstance(n.get("id"), str)
            and isinstance(n.get("type"), str)
            and isinstance(n.get("data"), dict)
            and isinstance(n["data"].get("config"), dict)
        ):
            raise ValidationError("Invalid canvas node.")
        ids.add(n["id"])
    if len(ids) != len(nodes) or any(
        not isinstance(e, dict)
        or not isinstance(e.get("id"), str)
        or not isinstance(e.get("source"), str)
        or not isinstance(e.get("target"), str)
        or e.get("source") not in ids
        or e.get("target") not in ids
        for e in edges
    ):
        raise ValidationError("Invalid canvas wiring.")
    if len({e["id"] for e in edges}) != len(edges):
        raise ValidationError("Duplicate canvas connections.")
    return nodes, edges


def config(step: Step, names: list[str]) -> dict[str, Any]:
    if any(i < 0 or i >= len(names) for i in step.columns):
        raise ValidationError("The proposal references an unavailable column.")
    cols = [names[i] for i in step.columns]
    if len(cols) != len(set(cols)):
        raise ValidationError("Choose distinct columns.")
    if step.kind == "filterRows":
        unary = step.operator in {"isnull", "notnull"}
        if (
            len(cols) != 1
            or step.operator is None
            or (step.value is None) != unary
            or step.count is not None
            or step.ascending is not None
            or isinstance(step.value, str)
            and (len(step.value) > 160 or "{{" in step.value)
        ):
            raise ValidationError("A filter needs one column and a supported comparison.")
        return {"column": cols[0], "operator": step.operator, "value": step.value}
    if step.operator is not None or step.value is not None:
        raise ValidationError("Only filters accept a comparison.")
    if step.kind == "limitRows":
        if step.count is None or cols or step.ascending is not None:
            raise ValidationError("A row limit needs only a positive count.")
        return {"n": step.count, "offset": 0}
    if step.count is not None or (step.kind != "sortRows" and step.ascending is not None):
        raise ValidationError("Unexpected transformation setting.")
    if step.kind in {"selectColumns", "dropColumns"}:
        if not cols:
            raise ValidationError("Choose at least one column.")
        return {"columns": cols}
    if step.kind == "sortRows":
        if not cols:
            raise ValidationError("Sorting needs at least one column.")
        return {"columns": cols, "ascending": step.ascending is not False}
    if step.kind == "removeDuplicates":
        return {"subset": cols, "keep": "first"}
    return {"subset": cols, "how": "any"}


def _validate_comparison(cfg: Graph, dtype: str) -> None:
    if cfg.get("operator") not in {"==", "!=", ">", ">=", "<", "<="}:
        return
    value = cfg.get("value")
    if dtype in {"integer", "float", "int64", "float64", "number"}:
        compatible = type(value) in (int, float)
    elif dtype in {"bool", "boolean"}:
        compatible = type(value) is bool and cfg["operator"] in {"==", "!="}
    elif dtype in {"string", "text"}:
        compatible = isinstance(value, str)
    else:
        compatible = False
    if not compatible:
        raise GraphValidationError("The comparison is incompatible with the column type.")


def _validate_schemas(graph: Graph, column_types: dict[str, str]) -> None:
    """Propagate the file schema along the supported single-input built-ins."""
    nodes = {node["id"]: node for node in graph["nodes"]}
    parent = {e["target"]: e["source"] for e in graph["edges"]}
    outputs: dict[str, set[str]] = {}
    for node_id in topological_sort(graph):
        node = nodes[node_id]
        kind, cfg = node["type"], node["data"]["config"]
        schema = outputs[parent[node_id]] if node_id in parent else set(column_types)
        cols = cfg.get("columns") or cfg.get("subset") or []
        if kind == "filterRows":
            cols = [cfg.get("column")]
        cols = [cols] if isinstance(cols, str) else cols
        if not isinstance(cols, list) or any(not isinstance(c, str) or c not in schema for c in cols):
            raise GraphValidationError("Unavailable input column")
        if kind == "filterRows":
            _validate_comparison(cfg, column_types[cols[0]])
        if kind == "selectColumns":
            schema = set(cols)
        elif kind == "dropColumns":
            schema = schema.difference(cols)
            if not schema:
                raise GraphValidationError("Empty output schema")
        if kind in OUTPUTS and not cfg.get("dataset_name"):
            raise GraphValidationError("Output dataset needs a name")
        outputs[node_id] = schema


def compile_plan(
    graph: Graph, plan: Plan, column_types: dict[str, str], binding: Graph, fmt: str
) -> tuple[Graph, Graph]:
    nodes, edges = inspect(graph)
    specs = {s.id: s for s in get_registry().node_specs() if s.id in SAFE}
    if any(n["type"] not in specs for n in nodes):
        raise ValidationError("Automatic edits support file inputs, cleaning steps and file outputs only.")
    added: list[Graph] = []
    changed: list[Graph] = []
    links: list[Graph] = []
    removed: list[str] = []

    def add(kind: str, cfg: Graph) -> Graph:
        if kind not in specs:
            raise ValidationError("The requested node is unavailable on this installation.")
        n = {
            "id": uuid4().hex,
            "type": kind,
            "position": {"x": 80 + (len(nodes) + len(added)) * 230, "y": 120},
            "data": {"label": specs[kind].label, "config": cfg},
        }
        added.append(n)
        return n

    def connect(a: Graph, b: Graph) -> None:
        links.append(
            {"id": uuid4().hex, "source": a["id"], "target": b["id"], "sourceHandle": "out", "targetHandle": "in"}
        )

    shared_names = list(column_types)[:64]
    configs = [config(step, shared_names) for step in plan.steps]
    if plan.replace is not None:
        if len(configs) != 1 or plan.replace >= len(nodes) or nodes[plan.replace]["type"] != plan.steps[0].kind:
            raise ValidationError("Repair must update one existing transformation of the same type.")
        n = deepcopy(nodes[plan.replace])
        n["data"]["config"] = configs[0]
        changed.append(n)
    else:
        outputs = [n for n in nodes if n["type"] in OUTPUTS]
        if not nodes:
            upstream = add("fileInput", {**binding, "format": fmt})
        elif outputs:
            incoming = [e for e in edges if e["target"] == outputs[0]["id"]]
            if len(outputs) != 1 or len(incoming) != 1:
                raise ValidationError("Select a canvas with one connected file output.")
            removed.append(incoming[0]["id"])
            upstream = next(n for n in nodes if n["id"] == incoming[0]["source"])
        else:
            leaves = [n for n in nodes if not any(e["source"] == n["id"] for e in edges)]
            if len(leaves) != 1:
                raise ValidationError("Connect the canvas to a single last step first.")
            upstream = leaves[0]
        for step, cfg in zip(plan.steps, configs, strict=True):
            n = add(step.kind, cfg)
            connect(upstream, n)
            upstream = n
        output = (
            outputs[0]
            if outputs
            else add("fileOutput", {"format": "csv", "dataset_name": f"Flow result {uuid4().hex[:12]}"})
        )
        connect(upstream, output)

    replacements = {n["id"]: n for n in changed}
    result = {
        **graph,
        "nodes": [replacements.get(n["id"], n) for n in nodes] + added,
        "edges": [e for e in edges if e["id"] not in removed] + links,
    }
    inspect(result)
    try:
        validate_parameter_specs(result)
        resolved, _ = apply_parameters(result)
        validate_graph(resolved)
        validate_node_configs(resolved)
        _validate_schemas(resolved, column_types)
    except (GraphValidationError, ParameterError, ValueError, TypeError, KeyError):
        raise ValidationError(
            "The proposed graph failed Ciaren validation. Review its inputs, parameters and connections."
        ) from None
    return result, {"added": added, "changed": changed, "connected": links, "disconnected": removed}
