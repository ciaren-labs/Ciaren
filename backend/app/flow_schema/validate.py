"""Validation and conversion for ``.flow`` documents.

Schema validation here is *contract-level* (shape + structural integrity of the
graph), distinct from the engine's execution-time graph validation in
``app/engine/graph.py``. It is deliberately importable without the engine so
external tooling can validate a ``.flow`` file without the full app.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.flow_schema.document import (
    LEGACY_FORMAT,
    FlowGraph,
    FlowSchemaDocument,
)
from app.version import flowframe_version


class FlowSchemaError(ValueError):
    """Raised when a ``.flow`` document fails schema or structural validation."""


def validate_document(data: dict[str, Any]) -> FlowSchemaDocument:
    """Validate the document shape. Raises :class:`FlowSchemaError` on failure."""
    try:
        return FlowSchemaDocument.model_validate(data)
    except ValidationError as exc:
        raise FlowSchemaError(str(exc)) from exc


def graph_structure_issues(graph: FlowGraph) -> list[str]:
    """Structural problems with the graph (independent of node semantics): missing
    ids/types, duplicate node ids, and edges referencing unknown nodes. Returns a
    list of human-readable issues (empty when the graph is structurally sound)."""
    issues: list[str] = []
    ids: set[str] = set()
    for i, node in enumerate(graph.nodes):
        node_id = node.get("id")
        if not node_id:
            issues.append(f"node[{i}] is missing an 'id'")
            continue
        if node_id in ids:
            issues.append(f"duplicate node id {node_id!r}")
        ids.add(node_id)
        if not node.get("type"):
            issues.append(f"node {node_id!r} is missing a 'type'")
    for i, edge in enumerate(graph.edges):
        for end in ("source", "target"):
            ref = edge.get(end)
            if not ref:
                issues.append(f"edge[{i}] is missing '{end}'")
            elif ref not in ids:
                issues.append(f"edge[{i}] {end} {ref!r} references an unknown node")
    return issues


def validate(data: dict[str, Any]) -> FlowSchemaDocument:
    """Full validation: schema shape **and** graph structure."""
    document = validate_document(data)
    issues = graph_structure_issues(document.graph)
    if issues:
        raise FlowSchemaError("graph structure errors: " + "; ".join(issues))
    return document


def missing_node_types(document: FlowSchemaDocument, available_types: set[str]) -> list[str]:
    """Node types used by the graph that the host does not provide — the basis for
    a "this project requires plugin X" message. Order-stable, de-duplicated."""
    seen: list[str] = []
    for node in document.graph.nodes:
        node_type = node.get("type")
        if node_type and node_type not in available_types and node_type not in seen:
            seen.append(node_type)
    return seen


def from_legacy_document(doc: dict[str, Any]) -> FlowSchemaDocument:
    """Upgrade a legacy ``flowframe.flow/v1`` export (``name`` / ``description`` /
    ``graph_json``) into the versioned document."""
    graph_json = doc.get("graph_json") or {}
    return FlowSchemaDocument.model_validate(
        {
            "project": {"name": doc.get("name", "Untitled"), "description": doc.get("description")},
            "graph": graph_json,
            "flowframeVersion": flowframe_version(),
        }
    )


def to_legacy_document(document: FlowSchemaDocument) -> dict[str, Any]:
    """Downgrade to the legacy export shape consumed by ``POST /api/flows/import``."""
    return {
        "format": LEGACY_FORMAT,
        "name": document.project.name,
        "description": document.project.description,
        "graph_json": document.graph.model_dump(mode="json"),
    }
