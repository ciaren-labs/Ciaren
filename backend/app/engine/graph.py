from collections import defaultdict, deque
from typing import Any

_INPUT_TYPES = {"csvInput", "excelInput", "parquetInput"}
_OUTPUT_TYPES = {"csvOutput", "excelOutput", "parquetOutput"}


class GraphValidationError(Exception):
    pass


def validate_graph(graph: dict[str, Any]) -> None:
    nodes: list[dict] = graph.get("nodes", [])
    edges: list[dict] = graph.get("edges", [])

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
    if not output_nodes:
        raise GraphValidationError("Graph must have at least one output node")

    if _has_cycle(node_ids, edges):
        raise GraphValidationError("Graph contains a cycle")


def topological_sort(graph: dict[str, Any]) -> list[str]:
    nodes: list[dict] = graph.get("nodes", [])
    edges: list[dict] = graph.get("edges", [])

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


def _has_cycle(node_ids: set[str], edges: list[dict]) -> bool:
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
