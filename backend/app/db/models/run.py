import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FlowRun(Base):
    __tablename__ = "flow_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id: Mapped[str] = mapped_column(String(36), ForeignKey("flows.id"), nullable=False)
    input_dataset_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("datasets.id"), nullable=True)
    # Every input dataset the run resolved, with its concrete version. Lets the
    # run view list all inputs of a multi-input flow (join/concat), not just the
    # primary `input_dataset_id` (which stays the filterable one).
    input_datasets_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, running, success, failed
    engine: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pandas"
    )  # pandas | polars — the dataframe engine the run executed on
    # How the run was started, and (for scheduled runs) which schedule fired it.
    trigger: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")  # manual | schedule
    schedule_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    output_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # Per-node execution outcomes (rows, columns, sample) for the read-only run DAG.
    node_results_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # The flow graph captured at trigger time. Flow.graph_json can be edited after a
    # run, so this snapshot is what makes a run (especially an ML training run)
    # reproducible. Nullable for runs created before this column existed.
    graph_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Python-side default keeps microsecond precision (SQLite CURRENT_TIMESTAMP
    # only has second resolution, which breaks ORDER BY created_at tests).
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
