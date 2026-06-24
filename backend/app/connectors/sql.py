"""SQLAlchemy-backed connector for relational databases (PostgreSQL, MySQL,
SQLite, SQL Server, …).

Security notes:
- The SQLAlchemy URL is *built* from structured fields with ``URL.create`` (no
  user-supplied DSN string), so a user can never inject extra driver parameters.
- Table reads/writes go through reflection / pandas, which quote identifiers; we
  additionally validate identifiers as defense-in-depth.
- All driver errors are scrubbed of the password before they leave this module.
"""

from __future__ import annotations

from typing import Any, cast

import pandas as pd
from sqlalchemy import MetaData, NullPool, Table, create_engine, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL

from app.connectors.base import (
    ConnectionSpec,
    ConnectorError,
    TableRef,
    validate_identifier,
)
from app.core.secrets import scrub

# Each SQL provider maps to a concrete **synchronous** SQLAlchemy driver. The
# executor runs off the event loop, so connectors are sync (the app's own async
# DATABASE_URL is unrelated).
_DRIVERNAMES = {
    "postgresql": "postgresql+psycopg",
    "mysql": "mysql+pymysql",
    "sqlite": "sqlite",
    "mssql": "mssql+pyodbc",
    "duckdb": "duckdb",
    "snowflake": "snowflake",
}

# Cap rows scanned when previewing/snapshotting a table without an explicit limit.
_READ_GUARD_LIMIT = 1_000_000


class SqlConnector:
    provider_kind = "sql"

    # -- URL / engine ---------------------------------------------------

    def _url(self, spec: ConnectionSpec) -> URL:
        drivername = _DRIVERNAMES.get(spec.provider)
        if drivername is None:
            raise ConnectorError(f"Unsupported SQL provider {spec.provider!r}.")
        if spec.provider in ("sqlite", "duckdb"):
            # File-based databases: no host or credentials.
            return URL.create(drivername, database=spec.database or "")
        if spec.provider == "snowflake":
            # Snowflake: host = account identifier, options carry warehouse/schema.
            opts = {str(k): str(v) for k, v in (spec.options or {}).items() if v}
            return URL.create(
                "snowflake",
                username=spec.username or None,
                password=spec.password or None,
                host=spec.host or None,
                database=spec.database or None,
                query=opts,
            )
        return URL.create(
            drivername,
            username=spec.username or None,
            password=spec.password or None,
            host=spec.host or None,
            port=spec.port or None,
            database=spec.database or None,
            query={str(k): str(v) for k, v in (spec.options or {}).items()},
        )

    def _engine(self, spec: ConnectionSpec) -> Engine:
        # NullPool: never hold connections open between calls.
        return create_engine(self._url(spec), poolclass=NullPool, pool_pre_ping=True)

    def _guard(self, spec: ConnectionSpec, exc: Exception) -> ConnectorError:
        return ConnectorError(scrub(str(exc), spec.password))

    # -- DataConnector interface ----------------------------------------

    def test_connection(self, spec: ConnectionSpec) -> None:
        engine = self._engine(spec)
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
        except Exception as exc:
            raise self._guard(spec, exc) from None
        finally:
            engine.dispose()

    def list_tables(self, spec: ConnectionSpec) -> list[TableRef]:
        engine = self._engine(spec)
        try:
            inspector = inspect(engine)
            refs: list[TableRef] = []
            schemas = inspector.get_schema_names() if spec.provider != "sqlite" else [None]
            for schema in schemas:
                # Skip internal system schemas to keep the picker focused on user data.
                if schema in ("information_schema", "pg_catalog", "sys"):
                    continue
                for name in inspector.get_table_names(schema=schema):
                    refs.append(TableRef(name=name, schema=schema))
                for name in inspector.get_view_names(schema=schema):
                    refs.append(TableRef(name=name, schema=schema))
            return refs
        except Exception as exc:
            raise self._guard(spec, exc) from None
        finally:
            engine.dispose()

    def read_table(self, spec: ConnectionSpec, table: str, schema: str | None, limit: int | None) -> pd.DataFrame:
        validate_identifier(table)
        if schema:
            validate_identifier(schema, "schema")
        engine = self._engine(spec)
        try:
            reflected = Table(table, MetaData(), schema=schema, autoload_with=engine)
            stmt = select(reflected).limit(limit if limit is not None else _READ_GUARD_LIMIT)
            with engine.connect() as conn:
                return pd.read_sql(stmt, conn)
        except Exception as exc:
            raise self._guard(spec, exc) from None
        finally:
            engine.dispose()

    def read_query(self, spec: ConnectionSpec, query: str) -> pd.DataFrame:
        if not query or not query.strip():
            raise ConnectorError("The SQL query is empty.")
        engine = self._engine(spec)
        try:
            with engine.connect() as conn:
                return pd.read_sql_query(text(query), conn)
        except Exception as exc:
            raise self._guard(spec, exc) from None
        finally:
            engine.dispose()

    def write_table(
        self, spec: ConnectionSpec, df: pd.DataFrame, table: str, schema: str | None, if_exists: str
    ) -> None:
        validate_identifier(table)
        if schema:
            validate_identifier(schema, "schema")
        engine = self._engine(spec)
        try:
            with engine.begin() as conn:
                df.to_sql(table, conn, schema=schema, if_exists=cast(Any, if_exists), index=False)
        except Exception as exc:
            raise self._guard(spec, exc) from None
        finally:
            engine.dispose()
