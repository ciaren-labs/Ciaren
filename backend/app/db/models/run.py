# SPDX-License-Identifier: AGPL-3.0-only
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class FlowRun(Base):
    __tablename__ = "flow_runs"
    __table_args__ = (
        # NULL is never considered equal to NULL by a UNIQUE constraint (in both
        # SQLite and Postgres), so a run triggered without an idempotency key
        # never collides with anything — only two triggers of the SAME flow
        # reusing the SAME key do.
        UniqueConstraint("flow_id", "webhook_idempotency_key", name="uq_flow_run_webhook_idempotency_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    flow_id: Mapped[str] = mapped_column(String(36), ForeignKey("flows.id"), nullable=False)
    # SET NULL (not RESTRICT): purging a dataset past its retention window must
    # not be blocked by completed run history — the run row survives with its
    # input link cleared instead of dangling (FK enforcement is ON for SQLite
    # too, see app.core.database.enable_sqlite_foreign_keys).
    input_dataset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True
    )
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
    # Caller-supplied Idempotency-Key on a webhook trigger (see
    # routes/webhooks.py). NULL for every non-webhook trigger and for webhook
    # triggers that didn't send the header — see __table_args__ for why NULLs
    # never collide with each other.
    webhook_idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    output_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # Per-node execution outcomes (rows, columns, sample) for the read-only run DAG.
    node_results_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # The flow graph captured at trigger time. Flow.graph_json can be edited after a
    # run, so this snapshot is what makes a run (especially an ML training run)
    # reproducible. Nullable for runs created before this column existed. This holds
    # the *resolved* graph (flow parameters already substituted), i.e. exactly what
    # executed.
    graph_snapshot_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # The resolved flow-parameter values this run executed with (name -> value).
    # None for flows without parameters or runs created before this column existed.
    parameters_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Python-side default keeps microsecond precision (SQLite CURRENT_TIMESTAMP
    # only has second resolution, which breaks ORDER BY created_at tests).
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
