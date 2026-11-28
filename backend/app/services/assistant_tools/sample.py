# SPDX-License-Identifier: AGPL-3.0-only
"""Sample previews of a working graph, with expression guards scoped per node.

An expression node may only reference the columns its own upstream node produces. Those
columns come from the preview schemas, so derived columns (a calculated column feeding a
filter expression) are known while names that exist nowhere upstream are refused.
"""

from collections.abc import Callable, Iterable, Mapping
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.graph import GraphValidationError, ancestor_subgraph, topological_sort
from app.services.assistant_policy import guard_expression
from app.services.preview_service import PREVIEW_EXPRESSION_TYPES, GraphPreview, preview_graph, redact_issue

Graph = dict[str, Any]
Schema = list[tuple[str, str]]
#: Input ports whose frame defines the columns a node's settings refer to, in priority order.
DATA_PORTS = ("in", "left")


def data_source(graph: Graph, node_id: str) -> str | None:
    """The node whose output frame feeds ``node_id``'s primary data input."""
    edges = [e for e in graph["edges"] if e["target"] == node_id]
    for port in DATA_PORTS:
        for edge in edges:
            if (edge.get("targetHandle") or "in") == port:
                return str(edge["source"])
    return None


def order(graph: Graph) -> list[str]:
    try:
        return topological_sort(graph)
    except GraphValidationError:
        # A cycle: keep graph order; the preview reports the cycle itself.
        return [n["id"] for n in graph["nodes"]]


def ancestors(graph: Graph, node_ids: Iterable[str]) -> set[str]:
    """The nodes and every node upstream of them."""
    known = {n["id"] for n in graph["nodes"]}
    return {n["id"] for i in node_ids if i in known for n in ancestor_subgraph(graph, i)["nodes"]}


def _guard(graph: Graph, scopes: Mapping[str, list[str]]) -> Callable[[str], None]:
    """Expression guard for one preview. The preview passes only the expression text, so
    each text maps to the columns of every node that carries it (their intersection)."""
    allowed: dict[str, set[str]] = {}
    for node in graph["nodes"]:
        text = node["data"]["config"].get("expression")
        if node["id"] in scopes and isinstance(text, str):
            columns = set(scopes[node["id"]])
            allowed[text] = allowed[text] & columns if text in allowed else columns

    def guard(expression: str) -> None:
        guard_expression(expression, sorted(allowed.get(expression, ())))

    return guard


async def expression_scopes(
    db: AsyncSession, project: str, graph: Graph, wanted: set[str] | None = None
) -> tuple[dict[str, list[str]], GraphPreview | None]:
    """Upstream columns of each expression node in ``wanted`` (all when None).

    Nodes are scoped in dependency order so a scope's own preview can run earlier
    expressions. Returns the failed preview instead when an upstream slice cannot be computed.
    Raises ``ValidationError`` for an unavailable input and ``MLNotEnabledError`` for ML nodes
    while ML is off.
    """
    by_id = {n["id"]: n for n in graph["nodes"]}
    scopes: dict[str, list[str]] = {}
    known: dict[str, Schema] = {}
    for node_id in order(graph):
        if by_id[node_id]["type"] not in PREVIEW_EXPRESSION_TYPES or (wanted is not None and node_id not in wanted):
            continue
        source = data_source(graph, node_id)
        if source is None:
            scopes[node_id] = []
            continue
        if source not in known:
            result = await preview_graph(db, project, graph, source, 0, False, expression_guard=_guard(graph, scopes))
            known.update(result.schemas)
            if source not in known:
                return scopes, result
        scopes[node_id] = [c for c, _ in known[source]]
    return scopes, None


async def scoped_preview(
    db: AsyncSession, project: str, graph: Graph, node_id: str | None = None, *, profile: bool = False
) -> GraphPreview:
    """``preview_graph`` with per-node expression scopes. Same errors as ``expression_scopes``."""
    wanted = ancestors(graph, [node_id]) if node_id else None
    scopes, failed = await expression_scopes(db, project, graph, wanted)
    if failed is not None:
        return failed
    return await preview_graph(db, project, graph, node_id, 0, profile, expression_guard=_guard(graph, scopes))


def kind(dtype: str) -> str:
    """The coarse type shown to the model for a pandas dtype."""
    lowered = dtype.lower()
    for prefix, label in (
        ("int", "integer"),
        ("uint", "integer"),
        ("float", "float"),
        ("bool", "boolean"),
        ("datetime", "datetime"),
        ("object", "string"),
        ("string", "string"),
        ("str", "string"),
        ("category", "string"),
    ):
        if lowered.startswith(prefix):
            return label
    return "other"


def public_issues(preview: GraphPreview, node_refs: Mapping[str, str], names: Mapping[str, str]) -> list[Graph]:
    """Model-facing preview issues: fixed templates with refs, never raw engine text.

    ``node_refs`` maps node ids to refs and ``names`` maps hidden column names to refs.
    """
    refs = {**names, **node_refs}
    issues = []
    for issue in preview.issues:
        entry: Graph = redact_issue(issue.message, issue.code, refs)
        if issue.node is not None and issue.node in node_refs:
            entry["node"] = node_refs[issue.node]
        issues.append(entry)
    return issues
