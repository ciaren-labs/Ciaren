from collections import defaultdict, deque
from typing import Any

from app.engine.node_kinds import INPUT_TYPES as _INPUT_TYPES
from app.engine.node_kinds import OUTPUT_TYPES as _OUTPUT_TYPES
from app.engine.node_kinds import (
    SQL_INPUT_TYPE,
    SQL_OUTPUT_TYPE,
)


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
    if require_output and not output_nodes:
        raise GraphValidationError("Graph must have at least one output node")

    if _has_cycle(node_ids, edges):
        raise GraphValidationError("Graph contains a cycle")

    _validate_connections(nodes, edges)


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
        by_handle: dict[str, int] = defaultdict(int)
        for edge in edges_in:
            handle = edge.get("targetHandle") or "in"
            if handle not in handles:
                raise GraphValidationError(f"{label}: connection to unknown input {handle!r}.")
            by_handle[handle] += 1
        for handle in handles:
            count = by_handle[handle]
            which = f" {handle!r}" if len(handles) > 1 else ""
            if count == 0:
                raise GraphValidationError(f"{label}: the{which} input is not connected.")
            if count > 1:
                raise GraphValidationError(f"{label}: the{which} input accepts only one connection (got {count}).")


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
    adj: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        adj[edge["source"]].append(edge["target"])

    visited: set[str] = set()
    in_stack: set[str] = set()

    def dfs(node: str) -> bool:
        visited.add(node)
        in_stack.add(node)
        for neighbor in adj[node]:
            if neighbor not in visited:
                if dfs(neighbor):
                    return True
            elif neighbor in in_stack:
                return True
        in_stack.discard(node)
        return False

    return any(dfs(n) for n in node_ids if n not in visited)
