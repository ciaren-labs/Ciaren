"""Public lightweight type annotations for ciaren-client responses."""

from __future__ import annotations

from typing import Any, Literal, TypedDict

JsonDict = dict[str, Any]


class Project(TypedDict, total=False):
    id: str
    name: str
    description: str | None
    color: str
    is_default: bool
    is_disabled: bool
    dataset_count: int
    flow_count: int
    created_at: str
    updated_at: str


class Dataset(TypedDict, total=False):
    id: str
    name: str
    source_type: str
    dataset_kind: str
    is_disabled: bool
    deleted_at: str | None
    project_id: str | None
    latest_version: int
    version_count: int
    column_schema: list[JsonDict] | None
    data_sample: list[JsonDict] | None
    column_profile: list[JsonDict] | None
    created_at: str
    updated_at: str


class DatasetVersion(TypedDict, total=False):
    id: str
    version_number: int
    row_count: int
    column_schema: list[JsonDict] | None
    column_profile: list[JsonDict] | None
    source_run_id: str | None
    created_at: str


class Flow(TypedDict, total=False):
    id: str
    name: str
    description: str | None
    project_id: str | None
    graph_json: JsonDict
    is_disabled: bool
    created_at: str
    updated_at: str
    last_run_at: str | None


class FlowDocument(TypedDict, total=False):
    format: str
    name: str
    description: str | None
    graph_json: JsonDict


class CodeExport(TypedDict, total=False):
    code: str
    polars: str
    polars_lazy: str
    flow_document: FlowDocument


class Run(TypedDict, total=False):
    id: str
    flow_id: str
    flow_name: str | None
    project_id: str | None
    input_dataset_id: str | None
    input_datasets: list[JsonDict] | None
    status: str
    engine: str
    trigger: str
    schedule_id: str | None
    output_location: str | None
    started_at: str | None
    finished_at: str | None
    error_message: str | None
    logs_json: list[JsonDict] | None
    node_results: list[JsonDict] | None
    graph_snapshot: JsonDict | None
    parameters: JsonDict | None
    created_at: str


class Schedule(TypedDict, total=False):
    id: str
    flow_id: str
    name: str | None
    description: str | None
    cron: str
    timezone: str
    engine: str | None
    enabled: bool
    catch_up: bool
    max_retries: int
    retry_delay_seconds: int
    run_timeout_seconds: int | None
    parameters: JsonDict | None
    next_run_at: str | None
    last_fired_at: str | None
    last_run_id: str | None
    last_status: str | None
    consecutive_failures: int
    retry_count: int
    disabled_reason: str | None
    created_at: str
    updated_at: str


class Connection(TypedDict, total=False):
    id: str
    name: str
    provider: str
    kind: str
    config: JsonDict
    created_at: str
    updated_at: str


class ConnectionTestResult(TypedDict, total=False):
    ok: bool
    message: str
    details: JsonDict | None


class WebhookStatus(TypedDict, total=False):
    configured: bool


RunStatus = Literal["pending", "running", "success", "failed"]
