# SPDX-License-Identifier: AGPL-3.0-only
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import DatasetKind


class DatasetUpdate(BaseModel):
    is_disabled: bool | None = None


class DatasetVersionRead(BaseModel):
    """One immutable snapshot of a dataset."""

    id: str
    version_number: int
    row_count: int
    # Aliased from the ORM's schema_json; never exposes the filesystem location.
    column_schema: list[dict[str, Any]] | None = Field(None, validation_alias="schema_json")
    column_profile: list[dict[str, Any]] | None = Field(None, validation_alias="profile_json")
    source_run_id: str | None = None  # set when the version was created by a flow run
    created_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}


class DatasetRead(BaseModel):
    """A logical dataset. ``column_schema`` / ``data_sample`` reflect the latest
    version; flows pin a specific ``version_number`` for reproducibility."""

    id: str
    name: str
    source_type: str
    dataset_kind: DatasetKind = DatasetKind.INPUT
    is_disabled: bool = False
    deleted_at: datetime | None = None
    project_id: str | None = None
    latest_version: int
    version_count: int
    column_schema: list[dict[str, Any]] | None = None
    data_sample: list[dict[str, Any]] | None = None
    column_profile: list[dict[str, Any]] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True, "populate_by_name": True}
