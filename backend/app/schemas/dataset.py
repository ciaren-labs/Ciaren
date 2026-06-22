from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DatasetRead(BaseModel):
    id: str
    name: str
    source_type: str
    # column_schema / data_sample use validation_alias to map from ORM attribute names
    # (schema_json / sample_json) without conflicting with Pydantic's own schema_json method.
    # location is intentionally omitted — internal filesystem path, not exposed to clients.
    column_schema: list[dict[str, Any]] | None = Field(None, validation_alias="schema_json")
    data_sample: list[dict[str, Any]] | None = Field(None, validation_alias="sample_json")
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
