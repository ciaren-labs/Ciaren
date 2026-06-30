# SPDX-License-Identifier: AGPL-3.0-only
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.db.models.dataset_version import DatasetVersion


class Dataset(Base):
    """A named, logical dataset. The actual data lives in immutable
    ``DatasetVersion`` rows — re-uploading a file under the same name adds a new
    version rather than overwriting, so flows that pin a version stay stable."""

    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # csv | excel | parquet
    # input | output
    dataset_kind: Mapped[str | None] = mapped_column(String(20), nullable=True, default="input")
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Set when the dataset is soft-deleted; its version files are retained until the
    # retention window passes and it is purged. None = live.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # Every dataset belongs to exactly one project (reassigned to the default on
    # project deletion), so it is never orphaned.
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    versions: Mapped[list["DatasetVersion"]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        order_by="DatasetVersion.version_number",
    )
