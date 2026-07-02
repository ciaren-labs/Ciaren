# SPDX-License-Identifier: AGPL-3.0-only
"""Registry of supported providers, their driver requirements, and availability
detection. The frontend uses this to disable providers whose driver isn't
installed (with a clear install hint).
"""

from __future__ import annotations

import importlib.util
from collections.abc import Callable
from dataclasses import dataclass

from app.connectors.base import DataConnector
from app.connectors.local_storage import LocalStorageConnector
from app.connectors.mongo import MongoConnector
from app.connectors.rest_api import RestApiConnector
from app.connectors.sql import SqlConnector
from app.connectors.storage_base import StorageConnector
from app.core.exceptions import ValidationError


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    # High-level kind: "sql" | "mongo" | "storage"
    kind: str
    # Python module to import-check for driver availability (None = always available).
    driver_module: str | None
    # pip extra that installs the driver (for the install hint shown in the UI).
    extra: str | None
    default_port: int | None
    needs_host: bool
    needs_auth: bool  # username + password env var
    supports_query: bool  # custom SQL / query mode
    # Storage-specific flags (all False for SQL/Mongo providers)
    needs_bucket: bool = False  # bucket / container / folder path
    needs_region: bool = False  # cloud region selector
    needs_endpoint: bool = False  # custom endpoint URL (S3-compatible stores)


PROVIDERS: dict[str, Provider] = {
    # ── SQL ────────────────────────────────────────────────────────────────
    "postgresql": Provider("postgresql", "PostgreSQL", "sql", "psycopg", "postgres", 5432, True, True, True),
    "mysql": Provider("mysql", "MySQL / MariaDB", "sql", "pymysql", "mysql", 3306, True, True, True),
    "sqlite": Provider("sqlite", "SQLite", "sql", None, None, None, False, False, True),
    "duckdb": Provider("duckdb", "DuckDB", "sql", "duckdb", "duckdb", None, False, False, True),
    "mssql": Provider("mssql", "SQL Server", "sql", "pyodbc", "mssql", 1433, True, True, True),
    "snowflake": Provider("snowflake", "Snowflake", "sql", "snowflake.sqlalchemy", "snowflake", None, True, True, True),
    # ── Document stores ────────────────────────────────────────────────────
    "mongodb": Provider("mongodb", "MongoDB", "mongo", "pymongo", "mongo", 27017, True, True, False),
    # ── Object / file storage ──────────────────────────────────────────────
    "local": Provider(
        "local",
        "Local Folder",
        "storage",
        None,
        None,
        None,
        needs_host=False,
        needs_auth=False,
        supports_query=False,
        needs_bucket=True,
        needs_region=False,
        needs_endpoint=False,
    ),
    "s3": Provider(
        "s3",
        "AWS S3",
        "storage",
        "boto3",
        "s3",
        None,
        needs_host=False,
        needs_auth=True,
        supports_query=False,
        needs_bucket=True,
        needs_region=True,
        needs_endpoint=True,
    ),
    "azure_blob": Provider(
        "azure_blob",
        "Azure Blob Storage",
        "storage",
        "azure.storage.blob",
        "azure",
        None,
        needs_host=False,
        needs_auth=True,
        supports_query=False,
        # Optional custom endpoint: sovereign clouds / Azurite emulator.
        needs_bucket=True,
        needs_region=False,
        needs_endpoint=True,
    ),
    "gcs": Provider(
        "gcs",
        "Google Cloud Storage",
        "storage",
        "google.cloud.storage",
        "gcs",
        None,
        needs_host=False,
        needs_auth=False,
        supports_query=False,
        needs_bucket=True,
        needs_region=False,
        needs_endpoint=False,
    ),
    # ── Web APIs ───────────────────────────────────────────────────────────
    # Read-only HTTP JSON/CSV APIs. `host` carries the base URL; auth, headers,
    # endpoints, parsing, and pagination live in options (see
    # app/connectors/rest_api.py). Endpoints list as tables for SQL Input, and
    # "custom SQL" mode doubles as a custom request path.
    "rest_api": Provider(
        "rest_api",
        "REST API",
        "api",
        None,  # stdlib urllib — always available
        None,
        None,
        needs_host=True,  # the base URL
        needs_auth=True,
        supports_query=True,
    ),
    # ── Experiment tracking ────────────────────────────────────────────────
    # MLflow is not a data source: it stores its tracking URI in `database`
    # (a local folder for the file store, or sqlite:/// / http://host:5000 /
    # databricks). It's tested and resolved through app/ml/tracking.py, not a
    # DataConnector/StorageConnector.
    "mlflow": Provider(
        "mlflow",
        "MLflow Tracking",
        "mlflow",
        "mlflow",
        "ml",
        None,
        needs_host=False,
        needs_auth=False,
        supports_query=False,
    ),
}

_SQL_CONNECTOR = SqlConnector()
_MONGO_CONNECTOR = MongoConnector()
_LOCAL_CONNECTOR = LocalStorageConnector()
_REST_API_CONNECTOR = RestApiConnector()


# Lazy imports for optional cloud storage connectors.
def _get_s3_connector() -> StorageConnector:
    from app.connectors.s3 import S3Connector

    return S3Connector()


def _get_azure_connector() -> StorageConnector:
    from app.connectors.azure_blob import AzureBlobConnector

    return AzureBlobConnector()


def _get_gcs_connector() -> StorageConnector:
    from app.connectors.gcs import GCSConnector

    return GCSConnector()


_STORAGE_CONNECTOR_FACTORIES: dict[str, Callable[[], StorageConnector]] = {
    "local": lambda: _LOCAL_CONNECTOR,
    "s3": _get_s3_connector,
    "azure_blob": _get_azure_connector,
    "gcs": _get_gcs_connector,
}


def get_provider(name: str) -> Provider:
    provider = PROVIDERS.get(name)
    if provider is None:
        allowed = ", ".join(PROVIDERS)
        raise ValidationError(f"Unknown provider '{name}'. Supported: {allowed}.")
    return provider


def driver_available(provider: Provider) -> bool:
    if provider.driver_module is None:
        return True
    try:
        return importlib.util.find_spec(provider.driver_module) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def get_connector(provider: Provider) -> DataConnector | StorageConnector:
    """Return the connector for a provider. Storage providers return a StorageConnector.

    MLflow has no DataConnector/StorageConnector — it is handled separately by the
    connection service (see app/ml/tracking.py); callers must guard with
    :func:`is_mlflow_provider` before reaching here.
    """
    if provider.kind == "storage":
        return _STORAGE_CONNECTOR_FACTORIES[provider.name]()
    if provider.kind == "mongo":
        return _MONGO_CONNECTOR
    if provider.kind == "api":
        return _REST_API_CONNECTOR
    if provider.kind == "mlflow":
        raise ValidationError("MLflow connections have no data connector.")
    return _SQL_CONNECTOR


def is_storage_provider(provider: Provider) -> bool:
    return provider.kind == "storage"


def is_mlflow_provider(provider: Provider) -> bool:
    return provider.kind == "mlflow"


def list_providers() -> list[dict[str, object]]:
    """Provider catalog for the UI, including driver availability."""
    return [
        {
            "name": p.name,
            "label": p.label,
            "kind": p.kind,
            "available": driver_available(p),
            "driver_module": p.driver_module,
            "extra": p.extra,
            "default_port": p.default_port,
            "needs_host": p.needs_host,
            "needs_auth": p.needs_auth,
            "supports_query": p.supports_query,
            "needs_bucket": p.needs_bucket,
            "needs_region": p.needs_region,
            "needs_endpoint": p.needs_endpoint,
        }
        for p in PROVIDERS.values()
    ]
