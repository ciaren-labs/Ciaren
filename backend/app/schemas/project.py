# SPDX-License-Identifier: AGPL-3.0-only
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    color: str = Field("violet", max_length=32)


class ProjectUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    color: str | None = Field(None, max_length=32)
    is_disabled: bool | None = None


class ProjectRead(BaseModel):
    id: str
    name: str
    description: str | None
    color: str
    is_default: bool
    is_disabled: bool = False
    dataset_count: int
    flow_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
