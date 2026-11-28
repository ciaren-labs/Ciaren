# SPDX-License-Identifier: AGPL-3.0-only
"""Static gates every assistant edit passes, in a fixed order, with redacted issues."""

import re
from collections.abc import Iterable, Mapping

from pydantic import ValidationError as SchemaError

from app.core.exceptions import ValidationError
from app.engine.graph import GraphValidationError, validate_graph, validate_node_configs
from app.engine.parameters import ParameterError, apply_parameters, validate_parameter_specs
from app.engine.registry import get_transformation
from app.plugins import get_registry
from app.services.assistant_graph import inspect
from app.services.assistant_nodes import MODELS
from app.services.assistant_policy import INPUTS, PolicyError, check_fields, guard_expression, tier
from app.services.assistant_tools.ops import AnyOp, EditRejected, Graph, Issue, Working, diff, layout, materialize

MESSAGE_LIMIT = 200
_QUOTED = re.compile(r"'[^']*'|\"[^\"]*\"")


def redact(message: str, refs: Mapping[str, str]) -> str:
    """Replace known names by their refs, drop quoted literals and bound the length."""
    for name, ref in sorted(refs.items(), key=lambda item: -len(item[0])):
        # Whole names only: a column called "a" must not rewrite the words around it.
        message = re.sub(rf"(?<!\w){re.escape(name)}(?!\w)", ref, message)
    return _QUOTED.sub("'…'", message)[:MESSAGE_LIMIT]


def _graph_code(message: str) -> str:
    lowered = message.lower()
    if "cycle" in lowered:
        return "cycle"
    if "handle" in lowered or "port" in lowered or "input" in lowered and "connect" in lowered:
        return "bad_port"
    if "column" in lowered:
        return "missing_column"
    return "config"


def policy(work: Working, touched: Iterable[str], rows: int | None = None) -> None:
    """Gate 1 alone, for callers that must run it before binding refs to names."""
    providers = {s.id: s.provider for s in get_registry().node_specs()}
    issues = []
    wanted = set(touched)
    for node in work.graph["nodes"]:
        if node["id"] not in wanted:
            continue
        ref, kind = work.ref_of(node["id"]), node["type"]
        if tier(kind, providers.get(kind)) is None or kind not in MODELS:
            issues.append(Issue("policy", "This node type is not available to the assistant.", ref))
            continue
        try:
            check_fields(kind, node["data"]["config"], rows)
        except PolicyError as exc:
            issues.append(Issue(exc.code, str(exc), ref, exc.field))
    if issues:
        raise EditRejected(issues)


def upstream_input(graph: Graph, node_id: str) -> Graph | None:
    """The input node feeding a node through its first incoming path, if any."""
    by_id: dict[str, Graph] = {n["id"]: n for n in graph["nodes"]}
    seen: set[str] = set()
    current: str | None = node_id
    while current and current not in seen:
        seen.add(current)
        if by_id[current]["type"] in INPUTS:
            return by_id[current]
        current = next((e["source"] for e in graph["edges"] if e["target"] == current), None)
    return None


def check(
    work: Working,
    touched: Iterable[str],
    columns: Mapping[str, list[str]] | None = None,
    rows: int | None = None,
    names: Mapping[str, str] | None = None,
) -> None:
    """Run the gates on the working graph; ``touched`` nodes get the per-node gates.

    ``columns`` are the column names expressions may reference and ``names`` maps real
    names to the refs shown to the model (empty when names are shared).
    """
    by_id = {n["id"]: n for n in work.graph["nodes"]}
    labels = {by_id[i]["data"].get("label"): ref for ref, i in work.refs.items() if i in by_id}
    names = {
        **{label: ref for label, ref in labels.items() if isinstance(label, str) and label},
        **(names or {}),
        **{node_id: ref for ref, node_id in work.refs.items()},
    }
    providers = {s.id: s.provider for s in get_registry().node_specs()}
    issues: list[Issue] = []
    wanted = set(touched)
    for node in work.graph["nodes"]:
        if node["id"] not in wanted:
            continue
        ref, kind, cfg = work.ref_of(node["id"]), node["type"], node["data"]["config"]
        level = tier(kind, providers.get(kind))
        if level is None or kind not in MODELS:
            issues.append(Issue("policy", "This node type is not available to the assistant.", ref))
            continue
        try:
            check_fields(kind, cfg, rows)
        except PolicyError as exc:
            issues.append(Issue(exc.code, redact(str(exc), names), ref, exc.field))
            continue
        try:
            MODELS[kind].model_validate(cfg, strict=True)
        except SchemaError as exc:
            error = exc.errors()[0]
            field = ".".join(str(p) for p in error["loc"]) or None
            code = "bad_type" if error["type"].endswith(("_type", "_parsing")) else "config"
            issues.append(Issue(code, redact(error["msg"], names), ref, field))
            continue
        if level == "review":
            try:
                guard_expression(str(cfg.get("expression", "")), (columns or {}).get(node["id"], []))
            except PolicyError as exc:
                issues.append(Issue(exc.code, str(exc), ref, exc.field))
                continue
        if kind in INPUTS or kind == "fileOutput":
            continue
        try:
            get_transformation(kind).validate_config(cfg)
        except (ValueError, TypeError, KeyError) as exc:
            issues.append(Issue("config", redact(str(exc), names), ref))
    if issues:
        raise EditRejected(issues)
    try:
        inspect(work.graph)
    except ValidationError as exc:
        raise EditRejected([Issue("limit", str(exc))]) from None
    try:
        validate_parameter_specs(work.graph)
        resolved, _ = apply_parameters(work.graph)
        validate_graph(resolved)
        validate_node_configs(resolved)
    except (GraphValidationError, ParameterError, ValueError, TypeError, KeyError) as exc:
        message = redact(str(exc), names)
        raise EditRejected([Issue(_graph_code(message), message)]) from None


def build(base: Graph, ops: list[AnyOp]) -> tuple[Graph, Graph]:
    """Materialize planner ops over a stored base, gate them, lay them out and return graph and delta."""
    work, touched = materialize(Working.start(base), ops)
    check(work, touched)
    layout(work)
    return work.graph, diff(work)


def reviewed(base: Graph, graph: Graph) -> tuple[Working, set[str]]:
    """A reviewed proposal as working state, with the nodes it adds or changes."""
    work = Working(base, graph, {f"n{i}": n["id"] for i, n in enumerate(graph["nodes"])})
    delta = diff(work)
    return work, {n["id"] for n in delta["added"] + delta["changed"]}
