# SPDX-License-Identifier: AGPL-3.0-only
"""``validate`` and ``preview``: static gates and sample previews of the working graph.

Both report column refs and types per node, never row values.
"""

import json
from typing import Any

from app.core.exceptions import MLNotEnabledError, ValidationError
from app.services.assistant_tools import gates, sample
from app.services.assistant_tools.catalog import Args, Ref, column_profile
from app.services.assistant_tools.context import Graph, ToolContext, ToolError
from app.services.assistant_tools.edit import expression_columns
from app.services.assistant_tools.ops import EditRejected, Working, diff
from app.services.preview_service import GraphPreview


class Validate(Args):
    pass


class Preview(Args):
    node: Ref
    profile: bool = False


def touched(work: Working) -> set[str]:
    """Nodes this turn added or reconfigured."""
    delta = diff(work)
    return {n["id"] for n in delta["added"] + delta["changed"]}


def affected(graph: Graph, nodes: set[str]) -> Graph:
    """The part of the graph an edit can change: the nodes, everything downstream of them
    and everything those depend on. Unrelated branches are left out of the preview."""
    down, frontier = set(nodes), set(nodes)
    while frontier:
        frontier = {e["target"] for e in graph["edges"] if e["source"] in frontier} - down
        down |= frontier
    keep = sample.ancestors(graph, down)
    return {
        **graph,
        "nodes": [n for n in graph["nodes"] if n["id"] in keep],
        "edges": [e for e in graph["edges"] if e["source"] in keep and e["target"] in keep],
    }


def _columns(ctx: ToolContext, ref: str, schema: list[tuple[str, str]]) -> dict[str, str]:
    """Column ref (or name when names are shared) -> coarse type, registering the refs."""
    refs = ctx.register(ref, [c for c, _ in schema])
    types = dict(schema)
    return {name if ctx.share_names else key: sample.kind(types[name]) for key, name in refs.items()}


async def _preview(ctx: ToolContext, graph: Graph, node: str | None, profile: bool = False) -> GraphPreview:
    try:
        return await sample.scoped_preview(ctx.db, ctx.project, graph, node, profile=profile)
    except ValidationError:
        raise ToolError("missing_dataset", "An input dataset is unavailable.") from None
    except MLNotEnabledError:
        raise ToolError("ml_disabled", "ML nodes need the ML extension. Enable it in Settings.") from None


def fingerprint(work: Working) -> str:
    """Identity of a working graph, so ``finish`` can require that it was validated as is."""
    return json.dumps(work.graph, sort_keys=True, default=str)


async def validate(ctx: ToolContext, args: Validate, work: Working) -> dict[str, Any]:
    """Static gates on the changed nodes, then a sample preview of every affected node."""
    changed = touched(work)
    try:
        columns = await expression_columns(ctx.db, ctx.project, work.graph, changed)
        gates.check(work, changed, columns, names=ctx.hidden())
    except EditRejected as exc:
        return {"ok": False, "nodes": {}, "issues": [i.public() for i in exc.issues]}
    if not changed:
        return {"ok": True, "nodes": {}, "issues": []}
    preview = await _preview(ctx, affected(work.graph, changed), None)
    refs = {i: r for r, i in work.refs.items()}
    nodes = {
        refs[node_id]: {"columns": _columns(ctx, refs[node_id], schema)}
        for node_id, schema in preview.schemas.items()
        if node_id in refs
    }
    issues = sample.public_issues(preview, refs, ctx.hidden())
    return {"ok": not issues, "nodes": nodes, "sampled": preview.sampled, "issues": issues}


async def preview(ctx: ToolContext, args: Preview, work: Working) -> dict[str, Any]:
    """Row count, column types and an optional shape profile of one node. No rows."""
    node_id = work.refs.get(args.node)
    if node_id is None or not any(n["id"] == node_id for n in work.graph["nodes"]):
        raise ToolError("bad_ref", "Unknown node reference.")
    result = await _preview(ctx, work.graph, node_id, args.profile)
    refs = {i: r for r, i in work.refs.items()}
    if result.preview is None or node_id not in result.schemas:
        return {"ok": False, "issues": sample.public_issues(result, refs, ctx.hidden())}
    columns = _columns(ctx, args.node, result.schemas[node_id])
    reply: dict[str, Any] = {
        "ok": True,
        "row_count": result.preview.row_count,
        "sampled": result.sampled,
        "columns": columns,
    }
    if args.profile:
        types = dict(result.schemas[node_id])
        by_name = {p.get("name"): p for p in result.preview.profile or []}
        reply["profile"] = [
            column_profile(ref, sample.kind(types[name]), by_name.get(name, {}), ctx.share_values)
            for ref, name in ctx.columns[args.node].items()
        ]
    return reply
