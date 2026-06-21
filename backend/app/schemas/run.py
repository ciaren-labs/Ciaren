from datetime import datetime
from typing import Any

from pydantic import BaseModel


class FlowRunCreate(BaseModel):
    input_dataset_id: str | None = None


class FlowRunRead(BaseModel):
    id: str
    flow_id: str
    input_dataset_id: str | None
    status: str
    output_location: str | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    logs_json: list[dict[str, Any]] | None
    created_at: datetime

    model_config = {"from_attributes": True}
