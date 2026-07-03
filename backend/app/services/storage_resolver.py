# SPDX-License-Identifier: AGPL-3.0-only
"""Resolve ``storageInput`` / ``storageOutput`` nodes against storage connections.

Mirrors the sql_resolver pattern exactly:

- ``storageInput`` nodes are resolved in the **parent (async) layer**, which
  holds the Connection row and the resolved secret. The file is downloaded and
  materialized to a parquet snapshot so the executor only ever touches plain
  files — no credentials cross the process boundary.
- ``storageOutput`` results are pushed to the target storage location after a
  successful run. A write failure marks the run as failed (output never left).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import ConnectorError, get_connector, get_provider, is_storage_provider
from app.core.exceptions import ValidationError
from app.db.models.connection import Connection
from app.engine.node_kinds import STORAGE_INPUT_TYPE, STORAGE_OUTPUT_TYPE
from app.plugins.connectors import connection_config, guard_plugin_connection, plugin_connector
from app.services.connection_service import build_storage_spec


def _storage_plugin(conn: Connection):  # type: ignore[no-untyped-def]
    """The (spec, runtime) pair when ``conn`` uses a storage-kind plugin
    connector; raises for a plugin connector of any other kind."""
    plugin = plugin_connector(conn.provider)
    if plugin is None:
        return None
    if plugin[0].kind != "storage":
        raise ValidationError(f"Connection '{conn.name}' (provider '{conn.provider}') is not a storage connection.")
    return plugin


async def _load_connection(db: AsyncSession, connection_id: str | None) -> Connection:
    if not connection_id:
        raise ValidationError("Storage node has no connection selected.")
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    conn = result.scalar_one_or_none()
    if conn is None:
        raise ValidationError(f"Connection '{connection_id}' not found.")
    return conn


def _nodes(graph: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    return [n for n in graph.get("nodes", []) if n.get("type") == node_type]


def has_storage_inputs(graph: dict[str, Any]) -> bool:
    return bool(_nodes(graph, STORAGE_INPUT_TYPE))


async def materialize_storage_inputs(
    db: AsyncSession, graph: dict[str, Any], work_dir: Path, limit: int | None = None
) -> dict[str, Path]:
    """Download every ``storageInput`` file and write each to a parquet snapshot.

    Returns ``{node_id: parquet_path}`` for the executor. ``limit`` bounds the
    rows read (used by preview); ``None`` reads the whole file for a run.
    """
    paths: dict[str, Path] = {}
    for node in _nodes(graph, STORAGE_INPUT_TYPE):
        config = node.get("data", {}).get("config", {})
        conn = await _load_connection(db, config.get("connection_id"))
        file_path = config.get("path", "")
        fmt = config.get("format", "csv")
        if not file_path:
            raise ValidationError(f"Storage input node {node['id']!r} has no file path configured.")

        plugin = _storage_plugin(conn)
        if plugin is not None:
            runtime = plugin[1]
            guard_plugin_connection(conn.host, conn.options_json)
            runtime_config = connection_config(conn)

            def _read_plugin(runtime=runtime, runtime_config=runtime_config, path=file_path, fmt=fmt, limit=limit):  # type: ignore[no-untyped-def]
                try:
                    df = runtime.read(runtime_config, {"path": path, "format": fmt, "limit": limit})
                except NotImplementedError:
                    raise ValidationError(f"Connector '{conn.provider}' does not support reading.") from None
                except Exception as exc:
                    raise ValidationError(str(exc)) from None
                return df.head(limit) if limit is not None else df

            df = await asyncio.to_thread(_read_plugin)
        else:
            provider = get_provider(conn.provider)
            if not is_storage_provider(provider):
                raise ValidationError(
                    f"Connection '{conn.name}' (provider '{conn.provider}') is not a storage connection."
                )
            connector = get_connector(provider)
            spec = build_storage_spec(conn)

            def _read(connector=connector, spec=spec, path=file_path, fmt=fmt, limit=limit):  # type: ignore[no-untyped-def]
                try:
                    df = connector.read_file(spec, path, fmt)
                except Exception as exc:
                    raise ValidationError(str(exc)) from None
                return df.head(limit) if limit is not None else df

            df = await asyncio.to_thread(_read)
        snap_path = Path(work_dir) / f"{node['id']}__storageinput.parquet"
        df.to_parquet(snap_path, index=False)
        paths[node["id"]] = snap_path
    return paths


async def push_storage_outputs(db: AsyncSession, graph: dict[str, Any], output_paths: dict[str, Path]) -> int:
    """Upload each ``storageOutput`` node's parquet to its target location.

    Returns the number of files written. A connector failure propagates so the
    run is recorded as failed (the output was never delivered).
    """
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    written = 0
    for node_id, path in output_paths.items():
        node = nodes_by_id.get(node_id)
        if not node or node.get("type") != STORAGE_OUTPUT_TYPE:
            continue
        config = node.get("data", {}).get("config", {})
        conn = await _load_connection(db, config.get("connection_id"))
        df = pd.read_parquet(path)
        dest_path = config.get("path") or f"{node_id}.parquet"
        fmt = config.get("format", "parquet")
        if_exists = config.get("if_exists", "overwrite")

        plugin = _storage_plugin(conn)
        if plugin is not None:
            runtime = plugin[1]
            guard_plugin_connection(conn.host, conn.options_json)
            runtime_config = connection_config(conn)

            def _write_plugin(
                runtime: Any = runtime,
                runtime_config: dict[str, Any] = runtime_config,
                df: pd.DataFrame = df,
                dest: str = dest_path,
                fmt: str = fmt,
                mode: str = if_exists,
            ) -> None:
                try:
                    runtime.write(df, runtime_config, {"path": dest, "format": fmt, "if_exists": mode})
                except NotImplementedError:
                    raise ValidationError(f"Connector '{conn.provider}' does not support writing.") from None
                except Exception as exc:
                    raise ValidationError(str(exc)) from None

            await asyncio.to_thread(_write_plugin)
        else:
            provider = get_provider(conn.provider)
            if not is_storage_provider(provider):
                raise ValidationError(f"Connection '{conn.name}' is not a storage connection.")
            connector = get_connector(provider)
            spec = build_storage_spec(conn)

            def _write(connector=connector, spec=spec, df=df, dest=dest_path, fmt=fmt, mode=if_exists):  # type: ignore[no-untyped-def]
                try:
                    connector.write_file(spec, df, dest, fmt, mode)
                except ConnectorError as exc:
                    raise ValidationError(str(exc)) from None

            await asyncio.to_thread(_write)
        written += 1
    return written
