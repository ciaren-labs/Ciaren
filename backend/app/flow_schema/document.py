# SPDX-License-Identifier: AGPL-3.0-only
"""The versioned ``.flow`` document — a public, stable description of a flow.

Today a flow persists in the DB as React Flow ``graph_json`` and is exported as
the unversioned ``ciaren.flow/v1`` ``FlowDocument`` (``app/schemas/flow.py``).
This module formalizes that into a versioned, JSON-schema-able contract with an
explicit ``schemaVersion``, a place to declare required plugins/capabilities, and
a migration path — without changing how flows are stored or how the existing
export/import endpoints behave. The legacy document round-trips into this one via
:func:`from_legacy_document` / :func:`to_legacy_document`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

#: The schema version this build writes. Bump on a breaking change to the shape
#: and add a migration (see ``app.flow_schema.migrations``).
CURRENT_SCHEMA_VERSION = "1.0.0"

#: The unversioned export tag the current backend emits (kept for reconciliation).
LEGACY_FORMAT = "ciaren.flow/v1"


class FlowProject(BaseModel):
    id: str | None = None
    name: str = Field(..., min_length=1)
    description: str | None = None


class PluginRequirement(BaseModel):
    """A plugin a flow needs to open/run, with a PEP 440 version specifier."""

    id: str = Field(..., min_length=1)
    version: str = ">=0"
    required: bool = True


class FlowRequirements(BaseModel):
    """What a flow needs from the host to be openable/runnable. Lets the app give
    a clear "install plugin X" message instead of failing cryptically."""

    plugins: list[PluginRequirement] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)


class FlowNode(BaseModel):
    """A typed, canonical *view* of one React Flow node.

    Deliberately permissive (``extra="allow"``, every field optional): it is a
    lens over graph JSON that may come from an older schema, a plugin, or a
    hand-written ``.flow`` file, so parsing must never reject a node the
    structural validator should instead report on. Cosmetic React Flow keys
    (``width``, ``selected``, …) are preserved by ``extra`` so a
    parse → :meth:`model_dump` round-trip is lossless.
    """

    model_config = ConfigDict(extra="allow")

    id: str | None = None
    type: str | None = None
    position: dict[str, Any] = Field(default_factory=dict)
    data: dict[str, Any] = Field(default_factory=dict)

    # Honor the "parse never rejects" contract: coerce malformed-but-plausible
    # values (a hand-written or older-schema graph with ``data: null``, a numeric
    # ``id``) to safe defaults so the *structural validator* — not the parser —
    # is what reports them.
    @field_validator("id", "type", mode="before")
    @classmethod
    def _str_or_none(cls, value: Any) -> str | None:
        return value if isinstance(value, str) else None

    @field_validator("position", "data", mode="before")
    @classmethod
    def _dict_or_empty(cls, value: Any) -> dict[str, Any]:
        return value if isinstance(value, dict) else {}

    @property
    def config(self) -> dict[str, Any]:
        """The node's engine config (``data.config``), or ``{}`` if absent/malformed."""
        cfg = self.data.get("config")
        return cfg if isinstance(cfg, dict) else {}

    @property
    def label(self) -> str | None:
        lbl = self.data.get("label")
        return lbl if isinstance(lbl, str) else None


class FlowEdge(BaseModel):
    """A typed, canonical *view* of one React Flow edge (see :class:`FlowNode`)."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    id: str | None = None
    source: str | None = None
    target: str | None = None
    source_handle: str | None = Field(default=None, alias="sourceHandle")
    target_handle: str | None = Field(default=None, alias="targetHandle")

    @field_validator("id", "source", "target", "source_handle", "target_handle", mode="before")
    @classmethod
    def _str_or_none(cls, value: Any) -> str | None:
        return value if isinstance(value, str) else None


class FlowGraph(BaseModel):
    """The React Flow graph. ``extra`` is allowed so flow-level keys the engine
    already understands (``parameters``, ``engine``) survive a round-trip.

    ``nodes``/``edges`` stay raw ``dict``s so persistence and export are byte-for-byte
    faithful; :meth:`typed_nodes` / :meth:`typed_edges` provide the canonical typed
    view for domain logic that wants to reason about a graph without poking dicts.
    """

    model_config = ConfigDict(extra="allow")

    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)

    def typed_nodes(self) -> list[FlowNode]:
        """The nodes as canonical :class:`FlowNode` views."""
        return [FlowNode.model_validate(node) for node in self.nodes]

    def typed_edges(self) -> list[FlowEdge]:
        """The edges as canonical :class:`FlowEdge` views."""
        return [FlowEdge.model_validate(edge) for edge in self.edges]

    def node_ids(self) -> set[str]:
        """Ids of nodes that declare one (malformed/idless nodes are skipped)."""
        return {nid for node in self.nodes if isinstance(node, dict) and (nid := node.get("id"))}

    def node_types(self) -> list[str]:
        """Distinct node types in document order (idless/typeless nodes skipped)."""
        seen: list[str] = []
        for node in self.nodes:
            node_type = node.get("type") if isinstance(node, dict) else None
            if node_type and node_type not in seen:
                seen.append(node_type)
        return seen

    def structural_issues(self) -> list[str]:
        """Structure problems independent of node semantics: missing ids/types,
        duplicate node ids, and edges referencing unknown/absent endpoints. Empty
        when the graph is structurally sound."""
        issues: list[str] = []
        ids: set[str] = set()
        for i, node in enumerate(self.nodes):
            node_id = node.get("id") if isinstance(node, dict) else None
            if not node_id:
                issues.append(f"node[{i}] is missing an 'id'")
                continue
            if node_id in ids:
                issues.append(f"duplicate node id {node_id!r}")
            ids.add(node_id)
            if not node.get("type"):
                issues.append(f"node {node_id!r} is missing a 'type'")
        for i, edge in enumerate(self.edges):
            edge_dict = edge if isinstance(edge, dict) else {}
            for end in ("source", "target"):
                ref = edge_dict.get(end)
                if not ref:
                    issues.append(f"edge[{i}] is missing '{end}'")
                elif ref not in ids:
                    issues.append(f"edge[{i}] {end} {ref!r} references an unknown node")
        return issues


class FlowSchemaDocument(BaseModel):
    """A portable, versioned flow document."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default=CURRENT_SCHEMA_VERSION, alias="schemaVersion")
    ciaren_version: str | None = Field(default=None, alias="ciarenVersion")
    project: FlowProject
    graph: FlowGraph
    metadata: dict[str, Any] = Field(default_factory=dict)
    requirements: FlowRequirements = Field(default_factory=FlowRequirements)

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize with the public (camelCase) field names."""
        return self.model_dump(mode="json", by_alias=True)
