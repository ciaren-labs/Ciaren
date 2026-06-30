# SPDX-License-Identifier: AGPL-3.0-only
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.db.models.dataset import Dataset


class DatasetVersion(Base):
    """An immutable snapshot of a dataset's data. Created on every upload; never
    mutated afterwards so a flow pinned to a version always reads the same data."""

    __tablename__ = "dataset_versions"
    __table_args__ = (UniqueConstraint("dataset_id", "version_number", name="uq_dataset_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dataset_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3, …
    location: Mapped[str] = mapped_column(Text, nullable=False)
    schema_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    sample_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    # Per-column statistics computed at creation time (see app/engine/profile.py).
    profile_json: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # set for flow-generated versions
    source_run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    dataset: Mapped["Dataset"] = relationship(back_populates="versions")
