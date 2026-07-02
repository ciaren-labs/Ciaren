# SPDX-License-Identifier: Apache-2.0
"""Executable behavior for a plugin-contributed connector.

A :class:`~app.plugin_api.providers.ConnectorProvider` can hand Ciaren a
:class:`ConnectorRuntime` for a connector id (via ``connector_implementations``);
Ciaren then routes the connections API (test, list tables/objects) and the
SQL/storage flow nodes (read, write) through it, exactly like a built-in
connector.

Like :class:`~app.plugin_api.node_runtime.NodeRuntime`, the contract is
**pandas-based and engine-agnostic**: ``read`` returns a pandas DataFrame and
``write`` receives one; Ciaren converts to/from the active engine and
materializes reads to parquet snapshots in its async layer. Frames are typed
``Any`` so the contract carries no hard pandas dependency.

Security model: a runtime only becomes reachable once the user approved the
plugin (its code is never imported before that), and the manifest's declared
permissions (``network``, ``credentials``, ``database_access``, …) are surfaced
in the approval UI. Connection secrets follow Ciaren's env-var-only rule — the
``config`` passed here carries the *resolved* secret for the one call, and the
runtime must never persist it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ConnectorTestResult(BaseModel):
    """Outcome of a connection test."""

    ok: bool
    message: str = ""


class ConnectorRuntime(ABC):
    """The runnable side of a plugin connector.

    ``config`` is the saved connection flattened to a plain mapping::

        {
          "host": str | None, "port": int | None, "database": str | None,
          "username": str | None,
          "password": str | None,   # resolved from the connection's env var
          "options": dict,          # extra fields, incl. config_schema values
        }

    ``options`` on :meth:`read` / :meth:`write` carries the flow node's config
    (e.g. ``mode``/``table``/``query`` from ``sqlInput``, ``path``/``format``
    from ``storageInput``) plus ``limit`` for bounded preview reads.

    Only :meth:`read` is required. The optional methods raise
    ``NotImplementedError`` by default; Ciaren maps that to a clear
    "not supported by this connector" error in the API/UI.
    """

    def test(self, config: dict[str, Any]) -> ConnectorTestResult:
        """Cheaply verify the connection settings (reachability, auth)."""
        raise NotImplementedError

    def list_tables(self, config: dict[str, Any]) -> list[dict[str, Any]]:
        """Tables/collections for query-style connectors. Each entry is
        ``{"name": str, "schema": str | None, "row_count": int | None}``."""
        raise NotImplementedError

    def list_objects(self, config: dict[str, Any], prefix: str = "") -> list[str]:
        """Object/file names for storage-style connectors."""
        raise NotImplementedError

    @abstractmethod
    def read(self, config: dict[str, Any], options: dict[str, Any]) -> Any:
        """Read from the source and return a pandas DataFrame."""

    def write(self, frame: Any, config: dict[str, Any], options: dict[str, Any]) -> None:
        """Write a pandas DataFrame to the target."""
        raise NotImplementedError
