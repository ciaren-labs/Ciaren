# SPDX-License-Identifier: AGPL-3.0-only
"""``propose_edit``: map refs to names, materialize the ops and run the static gates."""

from typing import Annotated, Any

from pydantic import Field

from app.plugins import get_registry
from app.services.assistant_nodes import MODELS, column_fields
from app.services.assistant_policy import INPUTS, tier
from app.services.assistant_tools import gates
from app.services.assistant_tools.catalog import Args
from app.services.assistant_tools.context import ToolContext, ToolError
from app.services.assistant_tools.ops import MAX_OPS, AnyOp, EditRejected, Issue, Working, layout, materialize


class ProposeEdit(Args):
    ops: Annotated[list[AnyOp], Field(min_length=1, max_length=MAX_OPS)]
    reset: bool = False


def start(graph: dict[str, Any]) -> Working:
    """Working state for a stored graph; nodes outside the policy are locked."""
    providers = {s.id: s.provider for s in get_registry().node_specs()}
    locked = {n["id"] for n in graph.get("nodes", []) if tier(n["type"], providers.get(n["type"])) is None}
    return Working.start(graph, locked)


def _upstream_dataset(ctx: ToolContext, work: Working, node_id: str) -> str | None:
    """The dataset ref feeding a node through its first input path, if any."""
    by_id = {n["id"]: n for n in work.graph["nodes"]}
    refs = {dataset: ref for ref, dataset in ctx.datasets.items()}
    seen: set[str] = set()
    current: str | None = node_id
    while current and current not in seen:
        seen.add(current)
        node = by_id[current]
        if node["type"] in INPUTS:
            return refs.get(node["data"]["config"].get("dataset_id"))
        current = next((e["source"] for e in work.graph["edges"] if e["target"] == current), None)
    return None


async def _bind(ctx: ToolContext, work: Working, touched: set[str], prior: Working) -> list[str]:
    """Replace dataset and column refs by real values in touched nodes; returns known column names.

    Values already bound by an earlier edit of the same node are kept as they are.
    """
    known: list[str] = []
    before = {n["id"]: n["data"]["config"] for n in prior.graph["nodes"]}
    for node in work.graph["nodes"]:
        if node["id"] not in touched:
            continue
        cfg, ref = node["data"]["config"], work.ref_of(node["id"])
        if node["type"] in INPUTS:
            dataset = cfg.get("dataset_id")
            if dataset == before.get(node["id"], {}).get("dataset_id"):
                continue
            if dataset not in ctx.datasets:
                raise EditRejected([Issue("missing_dataset", "Use a dataset ref such as d0.", ref, "dataset_id")])
            await ctx.dataset(dataset)
            cfg["dataset_id"] = ctx.datasets[dataset]
            continue
        fields = column_fields(node["type"]) if node["type"] in MODELS else {}
        source = _upstream_dataset(ctx, work, node["id"])
        if source is None:
            continue
        await ctx.dataset(source)
        columns = ctx.columns[source]
        known.extend(columns.values())

        def name(value: Any, field: str) -> Any:
            if value in columns:
                return columns[value]
            previous = before.get(node["id"], {}).get(field)
            bound = value == previous or isinstance(previous, list | dict) and value in previous
            if value in columns.values() and (ctx.share_names or bound):
                return value
            raise EditRejected([Issue("missing_column", "Use a column ref from the input schema.", ref, field)])

        for field, kind in fields.items():
            value = cfg.get(field)
            if value in (None, "", [], {}):
                continue
            if kind == "column_keys" and isinstance(value, dict):
                cfg[field] = {name(k, field): v for k, v in value.items()}
            elif isinstance(value, list):
                cfg[field] = [name(v, field) for v in value]
            else:
                cfg[field] = name(value, field)
    return known


async def propose_edit(ctx: ToolContext, args: ProposeEdit, work: Working) -> tuple[Working, dict[str, Any]]:
    """All-or-nothing: returns the new working state on success, the unchanged one otherwise."""
    current = start(work.base) if args.reset else work
    try:
        candidate, touched = materialize(current, args.ops)
        gates.policy(candidate, touched)
        known = await _bind(ctx, candidate, touched, current)
        hidden = {} if ctx.share_names else {n: r for cols in ctx.columns.values() for r, n in cols.items()}
        gates.check(candidate, touched, known, names=hidden)
    except EditRejected as exc:
        return work, {"ok": False, "issues": [i.public() for i in exc.issues]}
    except ToolError as exc:
        return work, {"ok": False, "issues": [{"code": exc.code, "message": str(exc)}]}
    layout(candidate)
    nodes = {r: n["type"] for r, i in candidate.refs.items() for n in candidate.graph["nodes"] if n["id"] == i}
    return candidate, {"ok": True, "nodes": nodes, "issues": []}
