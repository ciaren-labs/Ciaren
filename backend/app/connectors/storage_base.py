"""Base types and protocol for file / object-storage connectors.

Storage connectors are intentionally separate from DataConnector (SQL/Mongo):
they work with *files* inside a bucket or folder, not with tables and rows.
The security model is identical: secrets are resolved from environment variables
at call time and never stored.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import pandas as pd

log = logging.getLogger("app.connectors.storage")

FILE_FORMATS = ("csv", "excel", "parquet", "json", "text")
STORAGE_WRITE_MODES = ("overwrite", "error")


@dataclass
class StorageSpec:
    """Everything a storage connector needs at call time.

    Secrets live only in memory for the call's duration — the same guarantee
    as :class:`~app.connectors.base.ConnectionSpec`.
    """

    provider: str
    # The root scope: bucket for S3/GCS, container for Azure, folder for local.
    bucket: str
    # AWS Access Key ID or Azure storage account name (public identifiers).
    access_key: str | None = None
    # The actual secret, resolved from an env var — NEVER persisted.
    secret: str | None = None
    region: str | None = None
    # Custom endpoint for S3-compatible stores (MinIO, Cloudflare R2, …).
    endpoint_url: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class StorageConnector(Protocol):
    provider_kind: str  # always "storage"

    def test_connection(self, spec: StorageSpec) -> None: ...
    def list_objects(self, spec: StorageSpec, prefix: str = "") -> list[str]: ...
    def read_file(self, spec: StorageSpec, path: str, fmt: str) -> pd.DataFrame: ...
    def write_file(
        self, spec: StorageSpec, df: pd.DataFrame, path: str, fmt: str, if_exists: str
    ) -> None: ...
