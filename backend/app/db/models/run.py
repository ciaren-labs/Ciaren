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
    input_dataset_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("datasets.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )  # pending, running, success, failed
    output_location: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # Per-node execution outcomes (rows, columns, sample) for the read-only run DAG.
    node_results_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # Python-side default keeps microsecond precision (SQLite CURRENT_TIMESTAMP
    # only has second resolution, which breaks ORDER BY created_at tests).
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
