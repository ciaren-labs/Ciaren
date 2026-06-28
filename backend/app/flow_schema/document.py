"""The versioned ``.flow`` document — a public, stable description of a flow.

Today a flow persists in the DB as React Flow ``graph_json`` and is exported as
the unversioned ``flowframe.flow/v1`` ``FlowDocument`` (``app/schemas/flow.py``).
This module formalizes that into a versioned, JSON-schema-able contract with an
explicit ``schemaVersion``, a place to declare required plugins/capabilities, and
a migration path — without changing how flows are stored or how the existing
export/import endpoints behave. The legacy document round-trips into this one via
:func:`from_legacy_document` / :func:`to_legacy_document`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

#: The schema version this build writes. Bump on a breaking change to the shape
#: and add a migration (see ``app.flow_schema.migrations``).
CURRENT_SCHEMA_VERSION = "1.0.0"

#: The unversioned export tag the current backend emits (kept for reconciliation).
LEGACY_FORMAT = "flowframe.flow/v1"


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


class FlowGraph(BaseModel):
    """The React Flow graph. ``extra`` is allowed so flow-level keys the engine
    already understands (``parameters``, ``engine``) survive a round-trip."""

    model_config = ConfigDict(extra="allow")

    nodes: list[dict[str, Any]] = Field(default_factory=list)
    edges: list[dict[str, Any]] = Field(default_factory=list)


class FlowSchemaDocument(BaseModel):
    """A portable, versioned flow document."""

    model_config = ConfigDict(populate_by_name=True)

    schema_version: str = Field(default=CURRENT_SCHEMA_VERSION, alias="schemaVersion")
    flowframe_version: str | None = Field(default=None, alias="flowframeVersion")
    project: FlowProject
    graph: FlowGraph
    metadata: dict[str, Any] = Field(default_factory=dict)
    requirements: FlowRequirements = Field(default_factory=FlowRequirements)

    def to_json_dict(self) -> dict[str, Any]:
        """Serialize with the public (camelCase) field names."""
        return self.model_dump(mode="json", by_alias=True)
