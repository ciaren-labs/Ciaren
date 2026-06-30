# SPDX-License-Identifier: AGPL-3.0-only
from typing import Any

from pydantic import BaseModel, Field


class TransformationPreviewRequest(BaseModel):
    """Preview a single transformation applied to a dataset's data."""

    type: str
    dataset_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=50, ge=1, le=1000)
    # When true, also compute per-column statistics for the result.
    profile: bool = False


class FlowPreviewRequest(BaseModel):
    """Preview the data flowing out of one node of a saved flow."""

    node_id: str | None = None
    limit: int = Field(default=50, ge=1, le=1000)
    profile: bool = False
    # Flow-parameter overrides applied before previewing (name -> value), so the
    # preview reflects the values a run would use. Defaults fill in the rest.
    parameters: dict[str, Any] | None = None


class PreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
    # Per-column profile (null/distinct counts, numeric/string summaries).
    # Only populated when the request sets ``profile=true``.
    profile: list[dict[str, Any]] | None = None
