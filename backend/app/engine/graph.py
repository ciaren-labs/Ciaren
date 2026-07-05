# SPDX-License-Identifier: AGPL-3.0-only
from collections import defaultdict, deque
from typing import Any

from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
from app.engine.node_kinds import (
    MODEL_DEFINITION_NODE_TYPES,
    SQL_INPUT_TYPE,
    SQL_OUTPUT_TYPE,
    STORAGE_INPUT_TYPE,
    edge_carries_model,
    is_flow_terminal,
    is_model_input_handle,
    model_input_handles,
    multi_output_handles,
)
from app.engine.node_kinds import OUTPUT_TYPES as _OUTPUT_TYPES


class GraphValidationError(Exception):
    pass


def validate_graph(graph: dict[str, Any], require_output: bool = True) -> None:
    nodes: list[dict[str, Any]] = graph.get("nodes", [])
    edges: list[dict[str, Any]] = graph.get("edges", [])

    if not nodes:
        raise GraphValidationError("Graph has no nodes")

    node_ids = {n["id"] for n in nodes}

    for edge in edges:
        if edge["source"] not in node_ids:
            raise GraphValidationError(f"Edge source {edge['source']!r} not in nodes")
        if edge["target"] not in node_ids:
            raise GraphValidationError(f"Edge target {edge['target']!r} not in nodes")

    input_nodes = [n for n in nodes if n["type"] in _INPUT_TYPES]
    output_nodes = [n for n in nodes if n["type"] in _OUTPUT_TYPES]

    if not input_nodes:
        raise GraphValidationError("Graph must have at least one input node")
    # An mlTrain node (persists a model) or a report node like cross-validation
    # (emits a scores frame) is a valid terminal, so such a flow needs no
    # file-output node.
    has_ml_output = any(is_flow_terminal(n["type"]) for n in nodes)
    if require_output and not output_nodes and not has_ml_output:
        raise GraphValidationError("Graph must have at least one output node")

    if _has_cycle(node_ids, edges):
        raise GraphValidationError("Graph contains a cycle")

    _validate_source_handles(nodes, edges)
    _validate_connections(nodes, edges)
    _validate_model_handles(nodes, edges)


def _validate_source_handles(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    """Check that edges leaving a multi-output node name a real output handle.

    Single-output nodes are unrestricted (their sole output is implied). For a
    multi-output node (e.g. ``trainTestSplit``), every outgoing edge must carry a
    ``sourceHandle`` that is one of the node's declared handles — otherwise the
    executor cannot tell which frame the edge should carry.
    """
    types_by_id = {n["id"]: n["type"] for n in nodes}
    labels_by_id = {n["id"]: (n.get("data", {}).get("label") or n["type"]) for n in nodes}
    for edge in edges:
        handles = multi_output_handles(types_by_id.get(edge["source"], ""))
        if handles is None:
            continue
        label = labels_by_id[edge["source"]]
        source_handle = edge.get("sourceHandle")
        if source_handle is None:
            raise GraphValidationError(
                f"{label}: this node has multiple outputs {list(handles)}; each outgoing connection must choose one."
            )
        if source_handle not in handles:
            raise GraphValidationError(f"{label}: unknown output {source_handle!r} (expected one of {list(handles)}).")


def _validate_connections(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    """Check that every node's incoming edges respect its handle topology.

    Catches the wiring mistakes the frontend prevents but the API could still
    accept: two edges feeding a single-input handle (which would silently drop
    one input), a join missing a side, an output with the wrong number of
    inputs, or an input node fed by an upstream edge.
    """
    # Imported lazily so this pure module isn't loaded with the whole engine.
    from app.engine.registry import get_transformation

    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in edges:
        incoming[edge["target"]].append(edge)

    for node in nodes:
        node_id = node["id"]
        node_type = node["type"]
        edges_in = incoming.get(node_id, [])
        label = node.get("data", {}).get("label") or node_type

        if node_type in _INPUT_TYPES:
            if edges_in:
                raise GraphValidationError(f"{label}: input nodes cannot have an incoming connection.")
            config = node.get("data", {}).get("config", {})
            if node_type == SQL_INPUT_TYPE:
                _validate_sql_input(label, config)
            elif node_type == STORAGE_INPUT_TYPE:
                _validate_storage_input(label, config)
            elif not isinstance(config.get("dataset_id"), str) or not config.get("dataset_id"):
                raise GraphValidationError(f"{label}: no dataset selected.")
            continue

        if node_type in _OUTPUT_TYPES:
            if len(edges_in) != 1:
                raise GraphValidationError(f"{label}: output nodes need exactly one input (got {len(edges_in)}).")
            if node_type == SQL_OUTPUT_TYPE:
                _validate_sql_output(label, node.get("data", {}).get("config", {}))
            continue

        try:
            transformation = get_transformation(node_type)
        except KeyError as exc:
            raise GraphValidationError(f"Unknown node type: {node_type!r}") from exc

        if transformation.multi_input:
            if not edges_in:
                raise GraphValidationError(f"{label}: connect at least one input.")
            continue

        handles = transformation.input_handles
        optional = transformation.optional_input_handles
        known = set(handles) | set(optional)
        by_handle: dict[str, int] = defaultdict(int)
        for edge in edges_in:
            handle = edge.get("targetHandle") or "in"
            if handle not in known:
                raise GraphValidationError(f"{label}: connection to unknown input {handle!r}.")
            by_handle[handle] += 1
        for handle in handles:
            count = by_handle[handle]
            which = f" {handle!r}" if len(known) > 1 else ""
            if count == 0:
                raise GraphValidationError(f"{label}: the{which} input is not connected.")
            if count > 1:
                raise GraphValidationError(f"{label}: the{which} input accepts only one connection (got {count}).")
        for handle in optional:
            if by_handle[handle] > 1:
                raise GraphValidationError(f"{label}: the {handle!r} input accepts only one connection.")


def validate_node_configs(graph: dict[str, Any]) -> None:
    """Fail fast when a transformation node's saved config cannot execute.

    Every transformation ships a cheap, data-independent ``validate_config``
    (the same check the single-node preview runs), but nothing called it on
    the run path — a filter saved without a column would materialize every
    input and run all upstream nodes before failing mid-flow. Calling this
    alongside :func:`validate_graph` turns that into an immediate,
    node-labelled error before any data is touched.

    Kept separate from ``validate_graph`` on purpose: the code generators
    validate structure on graphs whose configs hold ``CodeRef`` placeholders
    (parameterized export), which these concrete-value checks would falsely
    reject. Execution-path callers pass the *resolved* graph, where every
    config value is concrete.
    """
    # Imported lazily so this pure module isn't loaded with the whole engine.
    from app.engine.registry import get_transformation

    for node in graph.get("nodes", []):
        node_type = node.get("type", "")
        # Input/output/SQL/storage config checks live in validate_graph.
        if node_type in _INPUT_TYPES or node_type in _OUTPUT_TYPES:
            continue
        try:
            transformation = get_transformation(node_type)
        except KeyError as exc:
            raise GraphValidationError(f"Unknown node type: {node_type!r}") from exc
        label = node.get("data", {}).get("label") or node_type
        try:
            transformation.validate_config(node.get("data", {}).get("config") or {})
        except GraphValidationError:
            raise
        except Exception as exc:  # noqa: BLE001 — name the node even if a (plugin) validator misbehaves
            raise GraphValidationError(f"{label}: {exc}") from exc


def _validate_model_handles(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> None:
    """Enforce that a model wire only ever connects a model output to a model input.

    A "model" connection (mlTrain's output) carries a trained model, not a frame.
    Catching the two miswirings here gives a clear error instead of a confusing
    runtime failure:
    - a model fed into a *data* input (e.g. mlTrain -> a cleaning node or a file
      output, which would try to treat the model as a dataframe), and
    - a *data* frame fed into a node's ``model`` input (e.g. raw rows into
      mlPredict's model handle instead of a trained model).
    """
    types_by_id = {n["id"]: n["type"] for n in nodes}
    labels_by_id = {n["id"]: (n.get("data", {}).get("label") or n["type"]) for n in nodes}
    for edge in edges:
        source_type = types_by_id.get(edge["source"], "")
        target_type = types_by_id.get(edge["target"], "")
        target_handle = edge.get("targetHandle") or "in"
        carries_model = edge_carries_model(source_type, edge.get("sourceHandle"))
        wants_model = is_model_input_handle(target_type, target_handle)
        if carries_model and not wants_model:
            raise GraphValidationError(
                f"{labels_by_id[edge['target']]}: a trained model can only connect to a "
                f"model input, not {target_handle!r}."
            )
        if wants_model and not carries_model:
            expected = ", ".join(sorted(model_input_handles(target_type)))
            raise GraphValidationError(
                f"{labels_by_id[edge['target']]}: the {expected!r} input needs a "
                f"model reference — connect a model-producing ML node's output."
            )
        if (
            target_type == "mlCrossValidate"
            and target_handle == "model"
            and source_type not in MODEL_DEFINITION_NODE_TYPES
        ):
            raise GraphValidationError(
                f"{labels_by_id[edge['target']]}: connect Classifier Model or Regressor Model to cross-validate. "
                "Train nodes fit a final model and would make cross-validation do extra work."
            )


def _validate_storage_input(label: str, config: dict[str, Any]) -> None:
    if not config.get("connection_id"):
        raise GraphValidationError(f"{label}: no storage connection selected.")
    if not config.get("path"):
        raise GraphValidationError(f"{label}: no file path specified.")


def _validate_sql_input(label: str, config: dict[str, Any]) -> None:
    if not config.get("connection_id"):
        raise GraphValidationError(f"{label}: no connection selected.")
    mode = config.get("mode", "table")
    if mode == "query":
        if not (config.get("query") or "").strip():
            raise GraphValidationError(f"{label}: the SQL query is empty.")
    elif not config.get("table"):
        raise GraphValidationError(f"{label}: no table selected.")


def _validate_sql_output(label: str, config: dict[str, Any]) -> None:
    if not config.get("connection_id"):
        raise GraphValidationError(f"{label}: no connection selected.")
    if not config.get("table"):
        raise GraphValidationError(f"{label}: no target table specified.")


def ancestor_subgraph(graph: dict[str, Any], node_id: str) -> dict[str, Any]:
    """The subgraph one node's output depends on: the node, its transitive
    ancestors, and the edges among them.

    Previewing a node only needs its upstream slice — computing unrelated
    branches wastes time, and a *failing* node elsewhere in the flow (a
    violated assertion, a typo'd column) would break previews of nodes that
    don't depend on it. Flow-level keys (``engine``, ``parameters``) are kept;
    node/edge dicts are shared with the input graph, not copied.
    """
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    if node_id not in nodes_by_id:
        raise GraphValidationError(f"Unknown node: {node_id!r}")
    incoming: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in graph.get("edges", []):
        incoming[edge["target"]].append(edge)
    keep: set[str] = set()
    stack = [node_id]
    while stack:
        nid = stack.pop()
        if nid in keep:
            continue
        keep.add(nid)
        stack.extend(e["source"] for e in incoming[nid] if e["source"] in nodes_by_id)
    # Keep every edge whose *target* is in the slice: a kept target's source is
    # either kept too (it was traversed) or dangling — and a dangling edge must
    # stay visible so downstream validation rejects the corrupt graph instead
    # of silently computing the node with one input missing.
    return {
        **{k: v for k, v in graph.items() if k not in ("nodes", "edges")},
        "nodes": [n for n in graph.get("nodes", []) if n["id"] in keep],
        "edges": [e for e in graph.get("edges", []) if e["target"] in keep],
    }


def topological_sort(graph: dict[str, Any]) -> list[str]:
    nodes: list[dict[str, Any]] = graph.get("nodes", [])
    edges: list[dict[str, Any]] = graph.get("edges", [])

    in_degree: dict[str, int] = defaultdict(int)
    adj: dict[str, list[str]] = defaultdict(list)

    for n in nodes:
        in_degree.setdefault(n["id"], 0)

    for edge in edges:
        adj[edge["source"]].append(edge["target"])
        in_degree[edge["target"]] += 1

    queue: deque[str] = deque(nid for nid, deg in in_degree.items() if deg == 0)
    order: list[str] = []

    while queue:
        nid = queue.popleft()
        order.append(nid)
        for neighbor in adj[nid]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(order) != len(nodes):
        raise GraphValidationError("Cycle detected during topological sort")

    return order


def _has_cycle(node_ids: set[str], edges: list[dict[str, Any]]) -> bool:
    """Iterative DFS-based cycle detection (avoids recursion-limit issues on deep graphs)."""
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adj[edge["source"]].append(edge["target"])

    # Stack entries: (node, iterator-over-neighbors, in-recursion-stack flag)
    # We use a colour scheme: WHITE=unvisited, GRAY=in-stack, BLACK=done.
    WHITE, GRAY, BLACK = 0, 1, 2
    colour: dict[str, int] = {n: WHITE for n in node_ids}

    for start in node_ids:
        if colour[start] != WHITE:
            continue
        # Each stack frame: (node, neighbour_index)
        stack: list[tuple[str, int]] = [(start, 0)]
        colour[start] = GRAY
        while stack:
            node, idx = stack[-1]
            neighbours = adj[node]
            if idx < len(neighbours):
                stack[-1] = (node, idx + 1)
                nbr = neighbours[idx]
                if colour[nbr] == GRAY:
                    return True
                if colour[nbr] == WHITE:
                    colour[nbr] = GRAY
                    stack.append((nbr, 0))
            else:
                colour[node] = BLACK
                stack.pop()

    return False
