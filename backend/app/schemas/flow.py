# SPDX-License-Identifier: AGPL-3.0-only
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class FlowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    project_id: str | None = None
    graph_json: dict[str, Any] = Field(default_factory=dict)


class FlowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    project_id: str | None = None
    graph_json: dict[str, Any] | None = None
    is_disabled: bool | None = None


# Versioned tag on the portable flow document so importers can sanity-check it.
FLOW_DOCUMENT_FORMAT = "ciaren.flow/v1"


class FlowDocument(BaseModel):
    """A portable, environment-independent description of a flow — its name and
    node graph — suitable for committing to git and importing elsewhere."""

    format: str = FLOW_DOCUMENT_FORMAT
    name: str
    description: str | None = None
    graph_json: dict[str, Any]


class FlowImport(BaseModel):
    """Payload for importing a flow document. Environment-specific bindings
    (dataset/connection ids) in the graph are stripped on import.

    Accepts either envelope: the legacy ``graph_json`` shape (today's real
    export format) or the versioned ``graph``/``schemaVersion`` shape from
    ``app.flow_schema`` — whichever is present is routed through the
    ``flow_schema`` migrate/validate pipeline before import."""

    model_config = ConfigDict(populate_by_name=True)

    format: str | None = None
    name: str | None = Field(None, max_length=255)
    description: str | None = None
    project_id: str | None = None
    graph_json: dict[str, Any] | None = None
    graph: dict[str, Any] | None = None
    schema_version: str | None = Field(None, alias="schemaVersion")

    @model_validator(mode="after")
    def _require_a_graph(self) -> "FlowImport":
        if self.graph_json is None and self.graph is None:
            raise ValueError("either 'graph_json' or 'graph' is required")
        return self


class FlowMigrateDocumentRequest(BaseModel):
    """Raw .flow document (legacy or versioned) to migrate. Not persisted."""

    document: dict[str, Any]


class FlowMigrateDocumentResponse(BaseModel):
    document: dict[str, Any]
    migrated: bool
    from_version: str
    to_version: str


class CodeExportResponse(BaseModel):
    # `code` is the pandas export (kept for back-compat); `polars` is the
    # equivalent eager polars script; `polars_lazy` is the optimized lazy
    # (`scan_*` → `collect()`) polars script. `flow_document` is the importable
    # JSON description of the flow (name + node graph).
    #
    # The `notebook*` fields are Jupyter notebook JSON (nbformat v4) wrapping
    # the same generated code as the corresponding `.py` exports — one cell per
    # blank-line-separated paragraph so the notebook runs top-to-bottom.
    code: str
    polars: str
    polars_lazy: str
    notebook: str  # pandas notebook JSON
    notebook_polars: str  # eager polars notebook JSON
    notebook_polars_lazy: str  # lazy polars notebook JSON
    flow_document: FlowDocument


class FlowRead(BaseModel):
    id: str
    name: str
    description: str | None
    project_id: str | None
    graph_json: dict[str, Any]
    is_disabled: bool = False
    created_at: datetime
    updated_at: datetime
    # When this flow last ran (any trigger), or None if it never has. Populated by
    # the list/get endpoints; not a column on the flow itself.
    last_run_at: datetime | None = None

    model_config = {"from_attributes": True}
