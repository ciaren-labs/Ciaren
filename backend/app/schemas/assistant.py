# SPDX-License-Identifier: AGPL-3.0-only
from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.core.assistant_profiles import Provider


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class Credential(ClosedModel):
    key: SecretStr = Field(min_length=1, max_length=4096)


class TrainingSelection(ClosedModel):
    dataset_id: str = Field(min_length=1, max_length=64)
    versions: list[Annotated[int, Field(ge=1, strict=True)]] = Field(min_length=3, max_length=3)
    target: str = Field(min_length=1, max_length=96)


class RegressionPlan(ClosedModel):
    joins: list[str] = Field(min_length=2, max_length=2)
    target: str
    features: list[str] = Field(min_length=2, max_length=2)
    model: Literal["linear_regression"]


class Turn(ClosedModel):
    request_id: UUID = Field(default_factory=uuid4)
    mode: Literal["build", "docs", "diagnose"]
    provider: Provider
    question: str = Field(min_length=1, max_length=1500)
    revision: datetime
    graph: dict[str, Any] = Field(default_factory=dict)
    dataset_id: str | None = Field(None, max_length=64)
    second_dataset_id: str | None = Field(None, min_length=1, max_length=64)
    training: TrainingSelection | None = None
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


class ColumnRef(ClosedModel):
    source: str = Field(pattern=r"^[0-9a-f]{12}$")
    column: int = Field(ge=0, lt=64)


class JoinSide(ColumnRef):
    port: str = Field(pattern=r"^[0-9a-f]{12}$")


class EqualityFlag(ColumnRef):
    equals: str = Field(min_length=1, max_length=96)
    name: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,63}$")


class BuildJoin(ClosedModel):
    left: JoinSide
    right: JoinSide
    how: Literal["left", "inner"]
    flag: EqualityFlag | None = None
    sort: ColumnRef | None = None


class RepairJoin(ClosedModel):
    join: str = Field(pattern=r"^[0-9a-f]{12}$")
    how: Literal["left"]


class RevertPreview(ClosedModel):
    revision: datetime
