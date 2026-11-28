# SPDX-License-Identifier: AGPL-3.0-only
"""``propose_edit``: map refs to names, materialize the ops and run the static gates."""

from copy import deepcopy
from typing import Annotated, Any

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MLNotEnabledError, ValidationError
from app.plugins import get_registry
from app.services.assistant_nodes import MODELS, column_fields
from app.services.assistant_policy import INPUTS, tier
from app.services.assistant_tools import gates, sample
from app.services.assistant_tools.catalog import Args
from app.services.assistant_tools.context import Graph, ToolContext, ToolError
from app.services.assistant_tools.ops import (
    MAX_OPS,
    AddNode,
    AnyOp,
    EditRejected,
    Issue,
    Working,
    layout,
    materialize,
)


class ProposeEdit(Args):
    ops: Annotated[list[AnyOp], Field(min_length=1, max_length=MAX_OPS)]
    reset: bool = False


def start(graph: dict[str, Any]) -> Working:
    """Working state for a stored graph; nodes outside the policy are locked."""
    providers = {s.id: s.provider for s in get_registry().node_specs()}
    locked = {n["id"] for n in graph.get("nodes", []) if tier(n["type"], providers.get(n["type"])) is None}
    return Working.start(graph, locked)


def _unavailable() -> EditRejected:
    return EditRejected([Issue("missing_dataset", "The input dataset is unavailable.")])


def _ml_disabled() -> EditRejected:
    return EditRejected([Issue("ml_disabled", "ML nodes need the ML extension. Enable it in Settings.")])


async def expression_columns(db: AsyncSession, project: str, graph: Graph, node_ids: set[str]) -> dict[str, list[str]]:
    """Columns each review-tier node's expression may reference: its upstream node's preview schema.

    Propose and apply both use this, so the apply-time recheck sees the same columns.
    """
    providers = {s.id: s.provider for s in get_registry().node_specs()}
    wanted = {
        n["id"] for n in graph["nodes"] if n["id"] in node_ids and tier(n["type"], providers.get(n["type"])) == "review"
    }
    if not wanted:
        return {}
    try:
        scopes, failed = await sample.expression_scopes(db, project, graph, sample.ancestors(graph, wanted))
    except ValidationError:
        raise _unavailable() from None
    except MLNotEnabledError:
        raise _ml_disabled() from None
    if failed is not None:
        code = failed.issues[0].code if failed.issues else "config"
        raise EditRejected([Issue(code, "The input of an expression node could not be previewed.")])
    return {node: columns for node, columns in scopes.items() if node in wanted}


async def _bind(ctx: ToolContext, work: Working, touched: set[str], prior: Working) -> None:
    """Replace dataset and column refs by real values in touched nodes.

    Column refs are scoped per node: they index the output columns of the node's upstream
    node, computed by a sample preview. Values already bound by an earlier edit of the same
    node are kept as they are.
    """
    before = {n["id"]: n["data"]["config"] for n in prior.graph["nodes"]}
    by_id = {n["id"]: n for n in work.graph["nodes"]}
    schemas: dict[str, list[tuple[str, str]]] = {}
    # Dependency order: a node's upstream settings are bound before its source is previewed.
    for node_id in sample.order(work.graph):
        if node_id not in touched:
            continue
        node = by_id[node_id]
        cfg, ref = node["data"]["config"], work.ref_of(node_id)
        if node["type"] in INPUTS:
            dataset = cfg.get("dataset_id")
            if dataset == before.get(node_id, {}).get("dataset_id"):
                continue
            if dataset not in ctx.datasets:
                raise EditRejected([Issue("missing_dataset", "Use a dataset ref such as d0.", ref, "dataset_id")])
            await ctx.dataset(dataset)
            cfg["dataset_id"] = ctx.datasets[dataset]
            continue
        fields = column_fields(node["type"]) if node["type"] in MODELS else {}
        source = sample.data_source(work.graph, node_id)
        if not fields or source is None:
            continue
        if source not in schemas:
            try:
                preview = await sample.scoped_preview(ctx.db, ctx.project, work.graph, source)
            except ValidationError:
                raise _unavailable() from None
            except MLNotEnabledError:
                raise _ml_disabled() from None
            schemas.update(preview.schemas)
            if source not in schemas:
                refs = {i: r for r, i in work.refs.items()}
                found = sample.public_issues(preview, refs, ctx.hidden())
                # Unattributed graph errors point at the node whose input failed.
                source_ref = work.ref_of(source)
                raise EditRejected([Issue(i["code"], i["message"], i.get("node", source_ref)) for i in found])
        columns = ctx.register(work.ref_of(source), [c for c, _ in schemas[source]])

        def name(value: Any, field: str) -> Any:
            if not isinstance(value, str):
                return value  # The node model gate reports the wrong type.
            if value in columns:
                return columns[value]
            previous = before.get(node_id, {}).get(field)
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


async def propose_edit(ctx: ToolContext, args: ProposeEdit, work: Working) -> tuple[Working, dict[str, Any]]:
    """All-or-nothing: returns the new working state on success, the unchanged one otherwise."""
    current = start(work.base) if args.reset else work
    defaults = {s.id: s.default_config for s in get_registry().node_specs()}
    # New nodes start from their catalog defaults, as in the editor.
    ops = [
        op.model_copy(update={"config": {**deepcopy(defaults.get(op.type, {})), **op.config}})
        if isinstance(op, AddNode)
        else op
        for op in args.ops
    ]
    try:
        candidate, touched = materialize(current, ops)
        gates.policy(candidate, touched)
        await _bind(ctx, candidate, touched, current)
        columns = await expression_columns(ctx.db, ctx.project, candidate.graph, touched)
        gates.check(candidate, touched, columns, names=ctx.hidden())
    except EditRejected as exc:
        return work, {"ok": False, "issues": [i.public() for i in exc.issues]}
    except ToolError as exc:
        return work, {"ok": False, "issues": [{"code": exc.code, "message": str(exc)}]}
    layout(candidate)
    nodes = {r: n["type"] for r, i in candidate.refs.items() for n in candidate.graph["nodes"] if n["id"] == i}
    return candidate, {"ok": True, "nodes": nodes, "issues": []}
