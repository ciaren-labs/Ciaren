"""Shared types and the connector interface for external data sources.

A connector turns a :class:`ConnectionSpec` (structured connection fields + an
in-memory, never-persisted password) into table listings and DataFrames. SQL
databases share one connector (:class:`~app.connectors.sql.SqlConnector`);
document stores like MongoDB get their own.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import pandas as pd

# A table/collection identifier must be a simple name (optionally schema-qualified
# upstream). This is defense-in-depth on top of the driver's own quoting.
_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")

WRITE_MODES = ("replace", "append", "fail")


class ConnectorError(Exception):
    """A connection/read/write failure, with any secret already scrubbed."""


@dataclass(frozen=True)
class TableRef:
    name: str
    schema: str | None = None

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name


@dataclass
class ConnectionSpec:
    """Everything a connector needs, assembled from a Connection row plus the
    resolved password. The password lives only in memory for the call's duration."""

    provider: str
    host: str | None = None
    port: int | None = None
    database: str | None = None
    username: str | None = None
    password: str | None = None
    options: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class DataConnector(Protocol):
    provider_kind: str

    def test_connection(self, spec: ConnectionSpec) -> None: ...
    def list_tables(self, spec: ConnectionSpec) -> list[TableRef]: ...
    def read_table(
        self, spec: ConnectionSpec, table: str, schema: str | None, limit: int | None
    ) -> pd.DataFrame: ...
    def read_query(self, spec: ConnectionSpec, query: str) -> pd.DataFrame: ...
    def write_table(
        self, spec: ConnectionSpec, df: pd.DataFrame, table: str, schema: str | None, if_exists: str
    ) -> None: ...


def validate_identifier(name: str, kind: str = "table") -> str:
    """Reject identifiers that aren't simple names (injection defense-in-depth)."""
    if not name or not _IDENTIFIER_RE.match(name):
        raise ConnectorError(
            f"Invalid {kind} name {name!r}: use letters, digits and underscores only."
        )
    return name
