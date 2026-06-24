from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import Engine, MLTask, NodeStatus, RunStatus, RunTrigger


class FlowRunCreate(BaseModel):
    input_dataset_id: str | None = None
    # Permissive str (not the Engine enum) so an unknown engine yields a friendly
    # 400 from ExecutionService (with the available engines) rather than a raw 422.
    engine: str | None = None
    # Per-run timeout override in seconds (0 = no limit). None falls back to the
    # schedule's run_timeout_seconds (for scheduled runs) then RUN_TIMEOUT_SECONDS.
    # ML training can far outlast typical ETL, so a caller can grant more time.
    timeout_seconds: int | None = Field(default=None, ge=0)


class MLRegisterRequest(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=255)
    # Optional alias to tag the new version with (MLflow 3 uses aliases, not stages).
    stage: str | None = Field(None, max_length=64)


class MLAliasRequest(BaseModel):
    alias: str = Field(..., min_length=1, max_length=64)
    version: str = Field(..., min_length=1, max_length=32)


class MLNodeMetrics(BaseModel):
    node_id: str
    type: str
    label: str | None = None
    ml_metrics: dict[str, float] | None = None
    model_uri: str | None = None
    task_type: MLTask | None = None
    cv_scores: list[float] | None = None
    mlflow_run_id: str | None = None


class InputDatasetRef(BaseModel):
    """One input dataset a run resolved, with the concrete version it read."""

    dataset_id: str
    version_number: int | None = None


class NodeResultRead(BaseModel):
    """A single node's outcome within a run (for the read-only run DAG)."""

    node_id: str
    type: str
    label: str
    status: NodeStatus
    rows: int | None = None
    columns: list[str] = Field(default_factory=list)
    sample: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    duration_ms: float | None = None
    # ML-specific — None for non-ML nodes (populated from NodeMetadata at run time).
    ml_metrics: dict[str, float] | None = None
    mlflow_run_id: str | None = None
    model_uri: str | None = None
    task_type: MLTask | None = None
    cv_scores: list[float] | None = None


class FlowRunSummary(BaseModel):
    """A lightweight run row for the history list (no per-node samples)."""

    id: str
    flow_id: str
    flow_name: str | None
    project_id: str | None
    input_dataset_id: str | None
    input_datasets: list[InputDatasetRef] | None = None
    status: RunStatus
    engine: Engine
    trigger: RunTrigger = RunTrigger.MANUAL
    schedule_id: str | None = None
    output_location: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class FlowRunRead(BaseModel):
    id: str
    flow_id: str
    input_dataset_id: str | None
    input_datasets: list[InputDatasetRef] | None = Field(None, validation_alias="input_datasets_json")
    status: RunStatus
    engine: Engine
    trigger: RunTrigger = RunTrigger.MANUAL
    schedule_id: str | None = None
    output_location: str | None
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    logs_json: list[dict[str, Any]] | None
    node_results: list[NodeResultRead] | None = Field(None, validation_alias="node_results_json")
    # The graph captured at trigger time (reproducibility); None for older runs.
    graph_snapshot: dict[str, Any] | None = Field(None, validation_alias="graph_snapshot_json")
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
