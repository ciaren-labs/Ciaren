# SPDX-License-Identifier: AGPL-3.0-only
"""Base types and protocol for file / object-storage connectors.

Storage connectors are intentionally separate from DataConnector (SQL/Mongo):
they work with *files* inside a bucket or folder, not with tables and rows.
The security model is identical: secrets are resolved from environment variables
at call time and never stored.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

import pandas as pd

from app.connectors.base import ConnectorError

log = logging.getLogger("app.connectors.storage")

FILE_FORMATS = ("csv", "tsv", "excel", "parquet", "json", "jsonl", "text")
STORAGE_WRITE_MODES = ("overwrite", "error")

#: MIME type per file format (used when uploading to object stores).
_CONTENT_TYPES = {
    "csv": "text/csv",
    "tsv": "text/tab-separated-values",
    "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "parquet": "application/octet-stream",
    "json": "application/json",
    "jsonl": "application/x-ndjson",
    "text": "text/plain",
}


def serialize_dataframe(df: pd.DataFrame, fmt: str) -> tuple[bytes, str]:
    """Serialize a frame to ``(bytes, content_type)`` for any storage backend.

    Shared by every storage connector so all five formats are written
    identically. Text writes one row per line (tab-separated for wider frames),
    mirroring the text reader.
    """
    buf = io.BytesIO()
    if fmt == "csv":
        df.to_csv(buf, index=False)
    elif fmt == "tsv":
        df.to_csv(buf, index=False, sep="\t")
    elif fmt == "excel":
        df.to_excel(buf, index=False)
    elif fmt == "parquet":
        df.to_parquet(buf, index=False)
    elif fmt == "json":
        df.to_json(buf, orient="records", indent=2)
    elif fmt == "jsonl":
        df.to_json(buf, orient="records", lines=True)
    elif fmt == "text":
        df.to_csv(buf, index=False, header=False, sep="\t")
    else:
        raise ConnectorError(f"Unsupported format {fmt!r}. Supported: {', '.join(FILE_FORMATS)}.")
    return buf.getvalue(), _CONTENT_TYPES[fmt]


def deserialize_dataframe(data: bytes, fmt: str) -> pd.DataFrame:
    """Parse bytes read from a storage backend into a frame (all five formats)."""
    buf = io.BytesIO(data)
    if fmt == "csv":
        return pd.read_csv(buf)
    if fmt == "tsv":
        return pd.read_csv(buf, sep="\t")
    if fmt == "excel":
        return pd.read_excel(buf)
    if fmt == "parquet":
        return pd.read_parquet(buf)
    if fmt == "json":
        return pd.read_json(buf)
    if fmt == "jsonl":
        return pd.read_json(buf, lines=True)
    if fmt == "text":
        # One row per line. Robust across pandas versions (sep="\n" is rejected by
        # newer pandas) and mirrors the text input reader's single "text" column.
        return pd.DataFrame({"text": data.decode("utf-8").splitlines()})
    raise ConnectorError(f"Unsupported format {fmt!r}. Supported: {', '.join(FILE_FORMATS)}.")


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
    def write_file(self, spec: StorageSpec, df: pd.DataFrame, path: str, fmt: str, if_exists: str) -> None: ...
