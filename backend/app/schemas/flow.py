from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FlowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    graph_json: dict[str, Any] = Field(default_factory=dict)


class FlowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    graph_json: dict[str, Any] | None = None


class FlowRead(BaseModel):
    id: str
    name: str
    description: str | None
    graph_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
