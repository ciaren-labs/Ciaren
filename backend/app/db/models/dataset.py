# SPDX-License-Identifier: AGPL-3.0-only
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.db.models.dataset_version import DatasetVersion


class Dataset(Base):
    """A named, logical dataset. The actual data lives in immutable
    ``DatasetVersion`` rows — re-uploading a file under the same name adds a new
    version rather than overwriting, so flows that pin a version stay stable."""

    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_datasets_project_id_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Unique within a project (see __table_args__), not globally — two projects
    # may each have their own dataset named e.g. "customers.csv".
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)  # csv | excel | parquet
    # input | output
    dataset_kind: Mapped[str | None] = mapped_column(String(20), nullable=True, default="input")
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Why the dataset is disabled: "project" (disabled by a project cascade) or
    # "manual" (the user disabled it directly). None while enabled. Mirrors
    # Flow.disabled_reason so re-enabling a project restores only the datasets the
    # project cascade itself disabled, not ones the user turned off. (Soft-delete is
    # tracked separately by deleted_at, which also blocks project-re-enable revival.)
    disabled_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Which project's cascade set disabled_reason="project" — set only alongside
    # that reason, cleared whenever the reason changes to anything else. No FK,
    # same as Flow.disabled_by_project_id: re-enabling a project must only restore
    # what *that* project's own cascade disabled.
    disabled_by_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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
