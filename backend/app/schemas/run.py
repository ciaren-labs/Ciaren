from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class FlowRunCreate(BaseModel):
    input_dataset_id: str | None = None
    engine: str = "pandas"


class InputDatasetRef(BaseModel):
    """One input dataset a run resolved, with the concrete version it read."""

    dataset_id: str
    version_number: int | None = None


class NodeResultRead(BaseModel):
    """A single node's outcome within a run (for the read-only run DAG)."""

    node_id: str
    type: str
    label: str
    status: str  # success | failed | skipped
    rows: int | None = None
    columns: list[str] = Field(default_factory=list)
    sample: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class FlowRunSummary(BaseModel):
    """A lightweight run row for the history list (no per-node samples)."""

    id: str
    flow_id: str
    flow_name: str | None
    project_id: str | None
    input_dataset_id: str | None
    input_datasets: list[InputDatasetRef] | None = None
    status: str
    engine: str
    output_location: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class FlowRunRead(BaseModel):
    id: str
    flow_id: str
    input_dataset_id: str | None
    input_datasets: list[InputDatasetRef] | None = Field(
        None, validation_alias="input_datasets_json"
    )
    status: str
    engine: str
    output_location: str | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    logs_json: list[dict[str, Any]] | None
    node_results: list[NodeResultRead] | None = Field(
        None, validation_alias="node_results_json"
    )
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
