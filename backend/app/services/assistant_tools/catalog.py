# SPDX-License-Identifier: AGPL-3.0-only
"""Read-only tools: the allowed node catalog, node schemas and dataset shape. No row values."""

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from app.core.exceptions import MLNotEnabledError, ValidationError
from app.db.models.dataset_version import DatasetVersion
from app.plugin_api.specs import NodeSpec
from app.plugins import get_registry
from app.services.assistant_nodes import MODELS, column_fields
from app.services.assistant_policy import LEGACY_INPUTS, TERMINAL, tier
from app.services.assistant_tools import sample
from app.services.assistant_tools.context import ToolContext, ToolError

NUMERIC = {"integer", "float", "int64", "float64", "number"}
SHARED_TYPES = NUMERIC | {"string", "boolean", "datetime"}
Ref = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,23}$")]


class Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ListNodeTypes(Args):
    category: Annotated[str, Field(max_length=32)] | None = None


class GetNodeSchema(Args):
    types: Annotated[list[Annotated[str, Field(max_length=64)]], Field(min_length=1, max_length=6)]


class GetDatasetSchema(Args):
    dataset: Ref


class ProfileColumns(Args):
    source: Ref
    columns: Annotated[list[Ref], Field(min_length=1, max_length=16)]


def allowed_specs() -> dict[str, NodeSpec]:
    """Installed nodes the assistant may add: allowed by the policy, from their expected
    provider, and not a legacy input type."""
    return {
        s.id: s
        for s in get_registry().node_specs()
        if tier(s.id, s.provider) and s.id in MODELS and s.id not in LEGACY_INPUTS
    }


def compact_catalog() -> list[list[Any]]:
    """[type, category, input ports, output ports, first sentence] for every allowed type."""
    return [
        [
            s.id,
            s.category,
            [p.id for p in s.inputs],
            [p.id for p in s.outputs],
            (s.description or "").split(". ")[0].rstrip(".")[:70],
        ]
        for s in allowed_specs().values()
    ]


async def list_node_types(ctx: ToolContext, args: ListNodeTypes) -> dict[str, Any]:
    return {
        "nodes": [
            {
                "type": s.id,
                "label": s.label,
                "category": s.category,
                "description": s.description,
                "inputs": [{"id": p.id, "kind": p.type, "required": p.required, "multi": p.multi} for p in s.inputs],
                "outputs": [p.id for p in s.outputs],
                "tier": tier(s.id, s.provider),
                "terminal": s.id in TERMINAL or s.is_flow_terminal,
            }
            for s in allowed_specs().values()
            if args.category in (None, s.category)
        ]
    }


async def get_node_schema(ctx: ToolContext, args: GetNodeSchema) -> dict[str, Any]:
    specs = allowed_specs()
    result: dict[str, Any] = {}
    for node_type in dict.fromkeys(args.types):
        spec = specs.get(node_type)
        if spec is None:
            result[node_type] = {"error": "policy"}
            continue
        notes = []
        if column_fields(node_type):
            notes.append("Column fields take column refs such as c0 from the input's schema.")
        if tier(node_type, spec.provider) == "review":
            notes.append("Expressions may only reference known columns and basic math functions.")
        result[node_type] = {
            "schema": MODELS[node_type].model_json_schema(),
            "defaults": spec.default_config,
            "notes": notes,
        }
    return result


async def _stats(ctx: ToolContext, ref: str) -> tuple[int | None, list[dict[str, Any]]]:
    schema = await ctx.dataset(ref)
    row = (
        await ctx.db.execute(
            select(DatasetVersion.row_count, DatasetVersion.profile_json).where(
                DatasetVersion.id == schema.version.version_id
            )
        )
    ).one()
    return row.row_count, row.profile_json or []


async def get_dataset_schema(ctx: ToolContext, args: GetDatasetSchema) -> dict[str, Any]:
    rows, profile = await _stats(ctx, args.dataset)
    schema = ctx.schemas[args.dataset]
    names, refs = list(schema.columns), ctx.names
    columns = [c for c in schema.shared_columns(ctx.share_names) if names[c["index"]] in refs]
    return {
        "columns": [{"ref": refs[names[c.pop("index")]], **c} for c in columns],
        "row_count": rows,
        "profiled": bool(profile),
    }


def column_profile(ref: str, dtype: str, p: dict[str, Any], counts: bool, share_values: bool) -> dict[str, Any]:
    """Shape facts for one column from a profile entry.

    Without ``counts`` only flags are given: counts of a filtered node would let the model
    test data values one query at a time. Ranges need ``share_values``.
    """
    scanned = p.get("scanned") or 0
    kind = dtype if dtype in SHARED_TYPES else "other"
    entry: dict[str, Any] = {"ref": ref, "type": kind, "numeric": dtype in NUMERIC}
    if not (counts or share_values):
        return entry  # A filtered node's flags would answer guesses about its values.
    entry["unique"] = bool(scanned) and p.get("distinct") == scanned == p.get("total") and p.get("null_count") == 0
    if counts:
        entry["null_frac"] = round(p["null_count"] / scanned, 4) if scanned and "null_count" in p else None
        entry["distinct"] = p.get("distinct")
    else:
        entry["has_nulls"] = bool(p.get("null_count"))
    # Ranges are data values; they leave the process only with the explicit opt-in.
    if share_values and "min" in p:
        entry.update(min=p["min"], max=p["max"])
    return entry


async def _node_profile(ctx: ToolContext, args: ProfileColumns) -> dict[str, Any]:
    """Profile a working-graph node's output on the preview sample."""
    node_id = ctx.refs.get(args.source)
    if node_id is None:
        raise ToolError("bad_ref", "Unknown dataset or node reference.")
    try:
        preview = await sample.scoped_preview(ctx.db, ctx.project, ctx.graph, node_id, profile=True)
    except ValidationError:
        raise ToolError("missing_dataset", "The input dataset is unavailable.") from None
    except MLNotEnabledError:
        raise ToolError("ml_disabled", "ML nodes need the ML extension.") from None
    if preview.preview is None or node_id not in preview.schemas:
        issue = preview.issues[0].code if preview.issues else "config"
        raise ToolError(issue, "This node could not be previewed. Run validate for details.")
    types = {name: sample.kind(dtype) for name, dtype in preview.schemas[node_id]}
    ctx.register(args.source, list(types))
    names = ctx.column_names(args.source, args.columns)
    by_name = {p.get("name"): p for p in preview.preview.profile or []}
    columns = [
        column_profile(ref, types[name], by_name.get(name, {}), ctx.share_values, ctx.share_values)
        for ref, name in zip(args.columns, names, strict=True)
    ]
    return {"columns": columns, "sampled": preview.sampled, **counts(preview.preview.row_count, ctx.share_values)}


def counts(rows: int, share_values: bool) -> dict[str, Any]:
    """A node's row count, only with share_values.

    Any count or flag of a filtered node tells whether a guessed value occurs in the data.
    """
    return {"row_count": rows} if share_values else {}


async def profile_columns(ctx: ToolContext, args: ProfileColumns) -> dict[str, Any]:
    """Profile dataset columns from the stored profile, or node columns from a sample preview."""
    if args.source not in ctx.datasets:
        return await _node_profile(ctx, args)
    rows, profile = await _stats(ctx, args.source)
    names = ctx.column_names(args.source, args.columns)
    by_name = {p.get("name"): p for p in profile}
    types = ctx.schemas[args.source].columns
    # A dataset's stored profile describes the whole dataset, which the model cannot filter.
    columns = [
        column_profile(ref, types[name], by_name.get(name, {}), True, ctx.share_values)
        for ref, name in zip(args.columns, names, strict=True)
    ]
    return {"columns": columns, "row_count": rows}


TOOLS: dict[str, tuple[type[Args], Any]] = {
    "list_node_types": (ListNodeTypes, list_node_types),
    "get_node_schema": (GetNodeSchema, get_node_schema),
    "get_dataset_schema": (GetDatasetSchema, get_dataset_schema),
    "profile_columns": (ProfileColumns, profile_columns),
}
