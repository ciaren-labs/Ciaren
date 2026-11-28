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


class Clarification(ClosedModel):
    """The user's pick from an earlier ``needs_choice`` reply, sent back as the model wrote it."""

    question: str = Field(min_length=1, max_length=1000)
    answer: str = Field(min_length=1, max_length=1000)


class Turn(ClosedModel):
    request_id: UUID = Field(default_factory=uuid4)
    mode: Literal["build", "docs", "diagnose"]
    provider: Provider
    question: str = Field(min_length=1, max_length=1500)
    revision: datetime
    # Optional draft check only: proposals are always derived from the saved flow graph.
    graph: dict[str, Any] | None = None
    dataset_id: str | None = Field(None, max_length=64)
    second_dataset_id: str | None = Field(None, min_length=1, max_length=64)
    training: TrainingSelection | None = None
    share_names: bool = False
    # assistant_agent.MAX_ANSWERS: a turn with three answers cannot ask a fourth question.
    clarifications: list[Clarification] = Field(default_factory=list, max_length=3)


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


Reason = Literal[
    "unsupported_node",
    "locked_node",
    "unsaved_changes",
    "multiple_inputs",
    "no_dataset",
    "ml_disabled",
    "no_failed_run",
    "budget_exhausted",
    "provider_no_tools",
    "abstained",
    "no_change",
    "needs_choice",
    "validation_failed",
    "step_limit",
    "timeout",
    "provider_error",
    "disabled_flow",
    "canvas_limit",
]


class Refused(ClosedModel):
    """409 body. ``reason`` is absent when the saved flow simply changed since it was loaded."""

    detail: str
    reason: Reason | None = None


class Suggestion(ClosedModel):
    label: str
    action: Literal["save", "switch_mode", "open_docs", "enable_ml", "manual_edit", "share_names", "retry"]
    target: str | None = None


class Choice(ClosedModel):
    #: Shown to the user, with names in place of refs.
    label: str
    #: Sent back as the answer, as the model wrote it.
    reply: str


class Usage(ClosedModel):
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class ToolStep(ClosedModel):
    tool: str
    ok: bool


class Delta(ClosedModel):
    added: list[dict[str, Any]]
    changed: list[dict[str, Any]]
    connected: list[dict[str, Any]]
    disconnected: list[str]
    removed: list[str] | None = None


class Citation(ClosedModel):
    title: str
    url: str


class Reply(ClosedModel):
    """Every turn answer. Absent fields are omitted from the response body."""

    message: str
    proposal: str | None = None
    delta: Delta | None = None
    citation: Citation | None = None
    usage: Usage | None = None
    steps: list[ToolStep] | None = None
    expires_in: int | None = None
    reason: Reason | None = None
    supported: list[str] | None = None
    suggestions: list[Suggestion] | None = None
    #: Short details under a proposal's one-sentence summary.
    notes: list[str] | None = None
    #: For ``needs_choice``: the question as the model wrote it, and the options to pick from.
    ask: str | None = None
    choices: list[Choice] | None = None
