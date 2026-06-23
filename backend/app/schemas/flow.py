from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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


class CodeExportResponse(BaseModel):
    # `code` is the pandas export (kept for back-compat); `polars` is the
    # equivalent eager polars script; `polars_lazy` is the optimized lazy
    # (`scan_*` → `collect()`) polars script.
    code: str
    polars: str
    polars_lazy: str


class FlowRead(BaseModel):
    id: str
    name: str
    description: str | None
    project_id: str | None
    graph_json: dict[str, Any]
    is_disabled: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
