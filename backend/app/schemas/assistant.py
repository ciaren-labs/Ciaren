# SPDX-License-Identifier: AGPL-3.0-only
from datetime import datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.core.assistant_profiles import Provider


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Credential(ClosedModel):
    key: SecretStr = Field(min_length=1, max_length=4096)


class Turn(ClosedModel):
    request_id: UUID = Field(default_factory=uuid4)
    mode: Literal["build", "docs", "diagnose"]
    provider: Provider
    question: str = Field(min_length=1, max_length=1500)
    revision: datetime
    graph: dict[str, Any] = Field(default_factory=dict)
    dataset_id: str | None = Field(None, max_length=64)
    share_names: bool = False


class Confirmation(ClosedModel):
    proposal: str = Field(pattern=r"^[0-9a-f]{32}$")


class Step(ClosedModel):
    kind: Literal[
        "limitRows", "sortRows", "dropNulls", "removeDuplicates", "selectColumns", "dropColumns", "filterRows"
    ]
    operator: Literal["==", "!=", ">", ">=", "<", "<=", "isnull", "notnull"] | None = None
    value: int | float | bool | str | None = None
    columns: list[int] = Field(default_factory=list, max_length=32)
    count: int | None = Field(None, ge=1, le=1000000)
    ascending: bool | None = None


class Plan(ClosedModel):
    # Replace only a single explicitly identified transformation, otherwise append.
    replace: int | None = Field(None, ge=0)
    steps: list[Step] = Field(min_length=1, max_length=6)
