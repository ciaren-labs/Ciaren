# SPDX-License-Identifier: AGPL-3.0-only
"""MongoDB connector (document store). ``pymongo`` is imported lazily so this
module loads even when the optional driver isn't installed — availability is
reported to the UI, which disables the provider with a warning.

A Mongo "table" is a collection. Custom SQL has no equivalent, so MongoDB inputs
use collection-pick mode only.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.connectors.base import (
    ConnectionSpec,
    ConnectorError,
    TableRef,
    validate_identifier,
)
from app.connectors.ssrf import guard_host
from app.core.secrets import scrub

_READ_GUARD_LIMIT = 1_000_000


class MongoConnector:
    provider_kind = "mongo"

    def _client(self, spec: ConnectionSpec) -> Any:
        try:
            from pymongo import MongoClient
        except ImportError as exc:  # pragma: no cover - exercised only without pymongo
            raise ConnectorError("MongoDB support requires the 'pymongo' package (pip install ciaren[mongo]).") from exc
        # Refuse internal hosts when the SSRF guard is enabled (no-op otherwise).
        guard_host(spec.host)
        # Credentials are passed as keyword args, never interpolated into a URI
        # string, so the password can't leak into a connection-string log.
        return MongoClient(
            host=spec.host or "localhost",
            port=spec.port or 27017,
            username=spec.username or None,
            password=spec.password or None,
            authSource=spec.database or "admin",
            serverSelectionTimeoutMS=5000,
        )

    def _db(self, client: Any, spec: ConnectionSpec) -> Any:
        if not spec.database:
            raise ConnectorError("MongoDB connections require a database name.")
        return client[spec.database]

    def _guard(self, spec: ConnectionSpec, exc: Exception) -> ConnectorError:
        return ConnectorError(scrub(str(exc), spec.password))

    def test_connection(self, spec: ConnectionSpec) -> None:
        client = self._client(spec)
        try:
            client.admin.command("ping")
        except Exception as exc:
            raise self._guard(spec, exc) from None
        finally:
            client.close()

    def list_tables(self, spec: ConnectionSpec) -> list[TableRef]:
        client = self._client(spec)
        try:
            return [TableRef(name=c) for c in self._db(client, spec).list_collection_names()]
        except Exception as exc:
            raise self._guard(spec, exc) from None
        finally:
            client.close()

    def read_table(self, spec: ConnectionSpec, table: str, schema: str | None, limit: int | None) -> pd.DataFrame:
        validate_identifier(table, "collection")
        client = self._client(spec)
        try:
            cursor = self._db(client, spec)[table].find({}, limit=limit if limit is not None else _READ_GUARD_LIMIT)
            records = list(cursor)
            for doc in records:
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])  # ObjectId -> str (JSON-safe)
            return pd.DataFrame(records)
        except Exception as exc:
            raise self._guard(spec, exc) from None
        finally:
            client.close()

    def read_query(self, spec: ConnectionSpec, query: str) -> pd.DataFrame:
        raise ConnectorError("MongoDB inputs use collection selection, not custom SQL. Pick a collection.")

    def write_table(
        self, spec: ConnectionSpec, df: pd.DataFrame, table: str, schema: str | None, if_exists: str
    ) -> None:
        validate_identifier(table, "collection")
        client = self._client(spec)
        try:
            collection = self._db(client, spec)[table]
            if if_exists == "fail" and collection.estimated_document_count() > 0:
                raise ConnectorError(f"Collection {table!r} already has documents.")
            if if_exists == "replace":
                collection.drop()
            records = df.to_dict(orient="records")
            if records:
                collection.insert_many(records)
        except ConnectorError:
            raise
        except Exception as exc:
            raise self._guard(spec, exc) from None
        finally:
            client.close()
