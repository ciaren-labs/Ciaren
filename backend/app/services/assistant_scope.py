# SPDX-License-Identifier: AGPL-3.0-only
"""Decide whether and how a turn can be served before any provider call is made."""

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.db.models.flow import Flow
from app.db.models.run import FlowRun
from app.ml.availability import ml_extension_ready
from app.schemas.assistant import Reason, Reply, Suggestion, Turn
from app.services import assistant_join
from app.services.assistant_graph import INPUTS, SAFE, STEPS, Graph, inspect

STALE = "The flow or one of its inputs changed or became unavailable. Reopen the editor and review a fresh proposal."


class Refusal(ConflictError):
    """A conflict the client resolves itself; ``reason`` is a stable code for the editor."""

    def __init__(self, reason: str, detail: str) -> None:
        self.reason = reason
        super().__init__(detail)


def utc(value: datetime) -> datetime:
    """SQLite returns naive UTC revisions while clients may send any offset."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def projection(graph: Graph) -> str:
    """The semantic canvas: node identity, type, settings and label, plus wiring. Positions are ignored."""

    def node(n: object) -> object:
        if not isinstance(n, dict):
            return n
        data = n.get("data")
        data = data if isinstance(data, dict) else {}
        return [n.get("id"), n.get("type"), data.get("config"), data.get("label")]

    def edge(e: object) -> object:
        if not isinstance(e, dict):
            return e
        handles = [e.get("sourceHandle") or "out", e.get("targetHandle") or "in"]
        return [e.get("id"), e.get("source"), e.get("target"), *handles]

    nodes, edges = graph.get("nodes") or [], graph.get("edges") or []
    if not isinstance(nodes, list) or not isinstance(edges, list):
        return json.dumps([nodes, edges], sort_keys=True)
    return json.dumps(
        [
            sorted(json.dumps(node(n), sort_keys=True) for n in nodes),
            sorted(json.dumps(edge(e), sort_keys=True) for e in edges),
        ]
    )


@dataclass
class Route:
    kind: Literal["docs", "training", "join", "structure", "plan"]
    base: Graph = field(default_factory=dict)
    nodes: list[Graph] = field(default_factory=list)
    edges: list[Graph] = field(default_factory=list)
    failure: str = ""


def failure_category(raw: str | None) -> str:
    if not raw:
        return "No failed run recorded."
    for terms, category in (
        (("column", "keyerror"), "A column reference failed. Check transformation columns against the input schema."),
        (("connect", "cycle", "handle"), "A connection failed validation. Inspect the input and output handles."),
        (("dataset", "file"), "An input was unavailable. Check the selected dataset and version."),
        (("type", "cast", "numeric"), "A type conversion failed. Check column types and transformation settings."),
    ):
        if any(t in raw.lower() for t in terms):
            return category
    return "The last failed run reported an unclassified error. Review its details locally."


def unsupported(reason: Reason, message: str, *suggestions: Suggestion, supported: list[str] | None = None) -> Reply:
    return Reply(message=message, reason=reason, suggestions=list(suggestions), supported=supported)


EDIT = Suggestion(label="Edit the canvas manually", action="manual_edit")


async def preflight(db: AsyncSession, flow: Flow, body: Turn) -> Route | Reply:
    """Return the planner route, or a reply explaining why the turn is unsupported.

    Raises for conflicts the editor must resolve (stale or disabled flow, unsaved canvas)
    and for canvases beyond the assistant limits.
    """
    if body.training is not None and body.mode != "build":
        raise ValidationError("Regression proposals are available in Build only.")
    if body.mode == "docs":
        return Route("docs")
    if flow.is_disabled:
        raise Refusal("disabled_flow", "This flow is disabled. Enable it before asking the assistant to change it.")
    if utc(flow.updated_at) != utc(body.revision):
        raise ConflictError(STALE)
    # The saved flow is the only base a proposal is derived from and written over.
    base: Graph = flow.graph_json or {}
    if body.graph is not None and projection(body.graph) != projection(base):
        raise Refusal("unsaved_changes", "Save the canvas before asking the assistant to change it.")
    if len(json.dumps(base)) > 96000:
        raise ValidationError("Canvas exceeds the assistant size limit.")
    nodes, edges = inspect(base)
    failure = ""
    if body.mode == "diagnose":
        error = await db.scalar(
            select(FlowRun.error_message)
            .where(FlowRun.flow_id == flow.id, FlowRun.status == "failed")
            .order_by(FlowRun.created_at.desc())
            .limit(1)
        )
        if error is None:
            return unsupported(
                "no_failed_run",
                "Diagnose explains the latest failed run, and this flow has none.",
                Suggestion(label="Switch to Build", action="switch_mode", target="build"),
            )
        failure = failure_category(error)
    route = Route("plan", base, nodes, edges, failure)
    if body.training is not None:
        if not ml_extension_ready():
            return unsupported(
                "ml_disabled",
                "Regression proposals require the ML extension.",
                Suggestion(label="Enable ML in Settings", action="enable_ml"),
            )
        route.kind = "training"
        return route
    has_join = any(n["type"] == "join" for n in nodes)
    if body.second_dataset_id or (has_join and all(n["type"] in assistant_join.JOIN_NODES for n in nodes)):
        route.kind = "join"
        return route
    inputs = [n for n in nodes if n["type"] in INPUTS]
    if body.mode == "diagnose" and (any(n["type"] not in SAFE for n in nodes) or len(inputs) != 1):
        route.kind = "structure"
        return route
    if any(n["type"] not in SAFE for n in nodes):
        return unsupported(
            "unsupported_node",
            "Automatic edits are limited to file flows with supported cleaning steps.",
            EDIT,
            supported=sorted(STEPS),
        )
    if len(inputs) > 1:
        return unsupported("multiple_inputs", "Use a single file input to generate a proposal.", EDIT)
    if not inputs and (nodes or body.dataset_id is None):
        return unsupported("no_dataset", "Select a project dataset or add a file input first.", EDIT)
    return route
