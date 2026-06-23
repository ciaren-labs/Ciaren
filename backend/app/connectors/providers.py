"""Registry of supported database providers, their driver requirements, and
availability detection. The frontend uses this to disable providers whose driver
isn't installed (with a clear "install X" message)."""

from __future__ import annotations

import importlib.util
from dataclasses import dataclass

from app.connectors.base import DataConnector
from app.connectors.mongo import MongoConnector
from app.connectors.sql import SqlConnector
from app.core.exceptions import ValidationError


@dataclass(frozen=True)
class Provider:
    name: str
    label: str
    kind: str  # "sql" | "mongo"
    # Python module to import-check for driver availability (None = stdlib/always).
    driver_module: str | None
    # pip extra that installs the driver (for the "install X" hint).
    extra: str | None
    default_port: int | None
    needs_host: bool
    needs_auth: bool
    supports_query: bool  # custom SQL/query mode available?


PROVIDERS: dict[str, Provider] = {
    "postgresql": Provider("postgresql", "PostgreSQL", "sql", "psycopg", "postgres", 5432, True, True, True),
    "mysql": Provider("mysql", "MySQL / MariaDB", "sql", "pymysql", "mysql", 3306, True, True, True),
    "sqlite": Provider("sqlite", "SQLite", "sql", None, None, None, False, False, True),
    "mssql": Provider("mssql", "SQL Server", "sql", "pyodbc", "mssql", 1433, True, True, True),
    "mongodb": Provider("mongodb", "MongoDB", "mongo", "pymongo", "mongo", 27017, True, True, False),
}

_CONNECTORS: dict[str, DataConnector] = {"sql": SqlConnector(), "mongo": MongoConnector()}


def get_provider(name: str) -> Provider:
    provider = PROVIDERS.get(name)
    if provider is None:
        allowed = ", ".join(PROVIDERS)
        raise ValidationError(f"Unknown provider '{name}'. Supported: {allowed}.")
    return provider


def driver_available(provider: Provider) -> bool:
    if provider.driver_module is None:
        return True
    return importlib.util.find_spec(provider.driver_module) is not None


def get_connector(provider: Provider) -> DataConnector:
    return _CONNECTORS[provider.kind]


def list_providers() -> list[dict[str, object]]:
    """Provider catalog for the UI, including whether each driver is installed."""
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
        }
        for p in PROVIDERS.values()
    ]
