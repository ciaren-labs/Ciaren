"""Resolve ``sqlInput`` / ``sqlOutput`` nodes against database connections.

The DB read/write runs in the **parent** (async) layer — it needs the Connection
row, the resolved secret, and a connector — so the executor only ever sees plain
parquet files. ``sqlInput`` nodes are read live and materialized to a parquet
snapshot (reproducing that run's input); ``sqlOutput`` results are pushed to the
target database after a successful run.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.connectors import get_connector, get_provider
from app.core.exceptions import ValidationError
from app.db.models.connection import Connection
from app.engine.node_kinds import SQL_INPUT_TYPE, SQL_OUTPUT_TYPE
from app.services.connection_service import build_connection_spec


async def _load_connection(db: AsyncSession, connection_id: str | None) -> Connection:
    if not connection_id:
        raise ValidationError("SQL node has no connection selected.")
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    conn = result.scalar_one_or_none()
    if conn is None:
        raise ValidationError(f"Connection '{connection_id}' not found.")
    return conn


def _nodes(graph: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    return [n for n in graph.get("nodes", []) if n.get("type") == node_type]


def has_sql_inputs(graph: dict[str, Any]) -> bool:
    return bool(_nodes(graph, SQL_INPUT_TYPE))


async def materialize_sql_inputs(
    db: AsyncSession, graph: dict[str, Any], work_dir: Path, limit: int | None = None
) -> dict[str, Path]:
    """Read every ``sqlInput`` node live and write each to a parquet snapshot.

    Returns ``{node_id: parquet_path}`` for the executor. ``limit`` bounds the
    rows read (used by preview); ``None`` reads the whole source for a run.
    """
    paths: dict[str, Path] = {}
    for node in _nodes(graph, SQL_INPUT_TYPE):
        config = node.get("data", {}).get("config", {})
        conn = await _load_connection(db, config.get("connection_id"))
        connector = get_connector(get_provider(conn.provider))
        spec = build_connection_spec(conn)
        mode = config.get("mode", "table")

        def _read(connector=connector, spec=spec, config=config, mode=mode):  # type: ignore[no-untyped-def]
            if mode == "query":
                return connector.read_query(spec, config.get("query", ""))
            return connector.read_table(spec, config.get("table", ""), config.get("schema"), limit)

        df = await asyncio.to_thread(_read)
        path = Path(work_dir) / f"{node['id']}__sqlinput.parquet"
        df.to_parquet(path, index=False)
        paths[node["id"]] = path
    return paths


async def push_sql_outputs(db: AsyncSession, graph: dict[str, Any], output_paths: dict[str, Path]) -> int:
    """Write each ``sqlOutput`` node's materialized parquet to its target table.

    Returns the number of tables written. A connector failure propagates so the
    run is recorded as failed (the output wasn't delivered).
    """
    nodes_by_id = {n["id"]: n for n in graph.get("nodes", [])}
    written = 0
    for node_id, path in output_paths.items():
        node = nodes_by_id.get(node_id)
        if not node or node.get("type") != SQL_OUTPUT_TYPE:
            continue
        config = node.get("data", {}).get("config", {})
        conn = await _load_connection(db, config.get("connection_id"))
        connector = get_connector(get_provider(conn.provider))
        spec = build_connection_spec(conn)
        df = pd.read_parquet(path)

        def _write(connector=connector, spec=spec, config=config, df=df):  # type: ignore[no-untyped-def]
            connector.write_table(
                spec,
                df,
                config.get("table", ""),
                config.get("schema"),
                config.get("if_exists", "replace"),
            )

        await asyncio.to_thread(_write)
        written += 1
    return written
