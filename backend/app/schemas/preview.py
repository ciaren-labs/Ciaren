from typing import Any

from pydantic import BaseModel, Field


class TransformationPreviewRequest(BaseModel):
    """Preview a single transformation applied to a dataset's data."""

    type: str
    dataset_id: str
    config: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=50, ge=1, le=1000)


class FlowPreviewRequest(BaseModel):
    """Preview the data flowing out of one node of a saved flow."""

    node_id: str | None = None
    limit: int = Field(default=50, ge=1, le=1000)


class PreviewResponse(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    truncated: bool
