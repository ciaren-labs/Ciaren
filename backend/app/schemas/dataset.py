from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DatasetRead(BaseModel):
    id: str
    name: str
    source_type: str
    location: str
    column_schema: list[dict[str, Any]] | None = Field(None, validation_alias="schema_json")
    data_sample: list[dict[str, Any]] | None = Field(None, validation_alias="sample_json")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
