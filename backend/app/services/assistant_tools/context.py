# SPDX-License-Identifier: AGPL-3.0-only
"""Per-turn state shared by the assistant tools."""

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.assistant_inputs import InputSchema, resolve_input

Graph = dict[str, Any]
MAX_COLUMNS = 64
#: Column refs one turn may hand out: c0 .. c255.
MAX_REFS = 256
_REF = re.compile(r"\b[cdn]\d{1,3}\b")
_ECHO = re.compile(r"(\S+) \(\1\)")


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
    #: Source ref (dataset or node) -> column ref (``c0``) -> real column name.
    columns: dict[str, dict[str, str]] = field(default_factory=dict)
    #: Real column name -> ref, one map per turn: a column keeps its ref at every node.
    names: dict[str, str] = field(default_factory=dict)
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
        """Column refs of one dataset or node output. A name seen before keeps its ref; a new
        name gets the next one. Past ``MAX_REFS`` new names get no ref and stay unaddressable."""
        refs = {}
        for name in names[:MAX_COLUMNS]:
            if name not in self.names and len(self.names) < MAX_REFS:
                self.names[name] = f"c{len(self.names)}"
            if name in self.names:
                refs[self.names[name]] = name
        self.columns[source] = refs
        return refs

    def hidden(self) -> dict[str, str]:
        """Real column name -> ref for every registered column; empty when names are shared."""
        return {} if self.share_names else dict(self.names)

    def readable(self, text: str, datasets: dict[str, str]) -> str:
        """``text`` with each column, node and dataset ref replaced by its name. For the user
        only: the result can hold real names, so it never goes back to the model."""
        labels = {ref: name for name, ref in self.names.items()}
        nodes = {n["id"]: n["data"].get("label") or n["type"] for n in self.graph["nodes"]}
        labels |= {ref: nodes[i] for ref, i in self.refs.items() if i in nodes}
        labels |= datasets
        named = _REF.sub(lambda m: labels.get(m.group(0), m.group(0)), text)
        # "price (c3)" would read "price (price)".
        return _ECHO.sub(r"\1", named)

    def column_names(self, source: str, refs: list[str]) -> list[str]:
        known = self.columns.get(source, {})
        if any(ref not in known for ref in refs):
            raise ToolError("missing_column", "Unknown column reference.")
        return [known[ref] for ref in refs]
