# SPDX-License-Identifier: AGPL-3.0-only
"""Per-turn state shared by the assistant tools."""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.assistant_inputs import InputSchema, resolve_input

Graph = dict[str, Any]
MAX_COLUMNS = 64


class ToolError(ValueError):
    """A recoverable tool failure, returned to the model as an issue with a stable ``code``."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


@dataclass
class ToolContext:
    db: AsyncSession
    project: str
    #: The working graph and its node refs (``n0``, model-named refs) -> node ids.
    graph: Graph
    refs: dict[str, str] = field(default_factory=dict)
    #: Dataset ref (``d0``) -> project dataset id, fixed by the caller before the turn.
    datasets: dict[str, str] = field(default_factory=dict)
    share_names: bool = False
    share_values: bool = False
    #: Source ref (dataset or node) -> column ref (``c0``) -> real column name.
    columns: dict[str, dict[str, str]] = field(default_factory=dict)
    schemas: dict[str, InputSchema] = field(default_factory=dict)

    async def dataset(self, ref: str) -> InputSchema:
        """Resolve a dataset ref inside the flow's project and register its column refs."""
        if ref not in self.datasets:
            raise ToolError("missing_dataset", "Unknown dataset reference.")
        if ref not in self.schemas:
            schema = await resolve_input(self.db, self.project, self.datasets[ref], None)
            self.schemas[ref] = schema
            self.register(ref, list(schema.columns))
        return self.schemas[ref]

    def register(self, source: str, names: list[str]) -> dict[str, str]:
        """Column refs of one dataset or node output, by position."""
        self.columns[source] = {f"c{i}": name for i, name in enumerate(names[:MAX_COLUMNS])}
        return self.columns[source]

    def hidden(self) -> dict[str, str]:
        """Real column name -> ref for every registered column; empty when names are shared."""
        if self.share_names:
            return {}
        return {name: ref for cols in self.columns.values() for ref, name in cols.items()}

    def column_names(self, source: str, refs: list[str]) -> list[str]:
        known = self.columns.get(source, {})
        if any(ref not in known for ref in refs):
            raise ToolError("missing_column", "Unknown column reference.")
        return [known[ref] for ref in refs]
