# SPDX-License-Identifier: AGPL-3.0-only
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.db.models.run import FlowRun
    from app.db.models.schedule import Schedule


# Why a flow is disabled, so re-enabling a *project* only restores the flows the
# project cascade itself disabled — not ones disabled by the user or by a broken
# dependency (dataset/connection). ``None`` while enabled.
DISABLED_BY_PROJECT = "project"
DISABLED_BY_DATASET = "dataset"
DISABLED_MANUAL = "manual"


class Flow(Base):
    __tablename__ = "flows"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Every flow belongs to exactly one project. Deleting a project reassigns its
    # flows to the default project first (ProjectService.delete), so a flow is
    # never left without one.
    project_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("projects.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    graph_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # One of DISABLED_BY_* above while disabled, else None. Drives whether a
    # project re-enable restores this flow (only DISABLED_BY_PROJECT flows).
    disabled_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # Which project's cascade set disabled_reason=DISABLED_BY_PROJECT — set only
    # alongside that reason, cleared whenever the reason changes to anything else.
    # No FK (a project can be deleted while this still points at it, same as
    # disabled_reason surviving a project delete): re-enabling a project must only
    # restore what *that* project's own cascade disabled, not a same-named-reason
    # row that was moved in from elsewhere or a since-deleted project's leftovers.
    disabled_by_project_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Deleting a flow deletes its run history and schedules with it — there is no
    # meaningful "flow_run without a flow" or "schedule without a flow" state.
    runs: Mapped[list["FlowRun"]] = relationship(cascade="all, delete-orphan")
    schedules: Mapped[list["Schedule"]] = relationship(cascade="all, delete-orphan")
