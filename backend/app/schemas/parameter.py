from typing import Any

from pydantic import BaseModel, Field

from app.core.enums import ParameterType


class ParameterSpec(BaseModel):
    """A single parameter declared on a flow (stored in ``graph_json.parameters``).

    Defined as a schema for documentation and optional save-time validation; the
    engine reads/validates the raw dicts directly via ``app.engine.parameters`` so
    it stays free of Pydantic at execution time.
    """

    name: str = Field(..., min_length=1, max_length=64, pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    type: ParameterType = ParameterType.STRING
    default: Any | None = None
    description: str | None = Field(None, max_length=500)
