from collections import defaultdict, deque
from typing import Any

from app.engine.node_kinds import (
    FLOW_TERMINAL_NODES,
    MODEL_INPUT_HANDLES,
    MULTI_OUTPUT_NODES,
    SQL_INPUT_TYPE,
    SQL_OUTPUT_TYPE,
    STORAGE_INPUT_TYPE,
    edge_carries_model,
    is_model_input_handle,
)
from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
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
    has_ml_output = any(n["type"] in FLOW_TERMINAL_NODES for n in nodes)
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
        handles = MULTI_OUTPUT_NODES.get(types_by_id.get(edge["source"], ""))
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
            expected = ", ".join(sorted(MODEL_INPUT_HANDLES.get(target_type, frozenset())))
            raise GraphValidationError(
                f"{labels_by_id[edge['target']]}: the {expected!r} input needs a "
                f"model reference — connect a model-producing ML node's output."
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
