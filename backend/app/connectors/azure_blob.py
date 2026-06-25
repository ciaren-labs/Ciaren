"""Azure Blob Storage connector via azure-storage-blob.

Security:
- The storage account name (semi-public identifier) is stored in ``username``.
- The account key is resolved from ``password_env`` at call time — NEVER stored.
- Connection strings are explicitly rejected: they embed the key in a single
  string and are trivially leaked in logs or stack traces. Use account name +
  key env var instead.
- All errors are scrubbed of the secret before propagation.
- azure-sdk debug logging is silenced to prevent credential material in logs.
"""

from __future__ import annotations

import io
import logging
from typing import Any

import pandas as pd

from app.connectors.base import ConnectorError
from app.connectors.storage_base import StorageSpec
from app.core.secrets import scrub

logging.getLogger("azure").setLevel(logging.CRITICAL)


def _service_client(spec: StorageSpec) -> Any:
    try:
        from azure.storage.blob import BlobServiceClient
    except ImportError as exc:
        raise ConnectorError("azure-storage-blob is not installed. Run: pip install flowframe[azure]") from exc

    account_name = spec.access_key
    account_key = spec.secret
    if not account_name:
        raise ConnectorError("Azure connection requires a storage account name (set in the 'Username' field).")
    if not account_key:
        raise ConnectorError(
            "Azure connection requires an account key env var"
            " (set 'Password env var' to the name of the variable holding the key)."
        )
    # A custom endpoint targets Azure-compatible stores: sovereign/government
    # clouds (e.g. *.blob.core.usgovcloudapi.net) and the Azurite emulator. When
    # absent, default to the public-cloud URL derived from the account name.
    account_url = spec.endpoint_url or f"https://{account_name}.blob.core.windows.net"
    return BlobServiceClient(account_url=account_url, credential=account_key)


def _guard(exc: Exception, secret: str | None) -> ConnectorError:
    return ConnectorError(scrub(str(exc), secret))


class AzureBlobConnector:
    provider_kind = "storage"

    def test_connection(self, spec: StorageSpec) -> None:
        try:
            _service_client(spec).get_container_client(spec.bucket).get_container_properties()
        except ConnectorError:
            raise
        except Exception as exc:
            raise _guard(exc, spec.secret) from None

    def list_objects(self, spec: StorageSpec, prefix: str = "") -> list[str]:
        try:
            container = _service_client(spec).get_container_client(spec.bucket)
            return [b.name for b in container.list_blobs(name_starts_with=prefix or None)]
        except ConnectorError:
            raise
        except Exception as exc:
            raise _guard(exc, spec.secret) from None

    def read_file(self, spec: StorageSpec, path: str, fmt: str) -> pd.DataFrame:
        try:
            client = _service_client(spec)
            body = client.get_blob_client(container=spec.bucket, blob=path).download_blob().readall()
        except ConnectorError:
            raise
        except Exception as exc:
            raise _guard(exc, spec.secret) from None

        buf = io.BytesIO(body)
        try:
            if fmt == "csv":
                return pd.read_csv(buf)
            elif fmt == "excel":
                return pd.read_excel(buf)
            elif fmt == "parquet":
                return pd.read_parquet(buf)
            else:
                raise ConnectorError(f"Unsupported format {fmt!r}. Supported: csv, excel, parquet.")
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(f"Failed to parse {spec.bucket}/{path} as {fmt}: {exc}") from None

    def write_file(self, spec: StorageSpec, df: pd.DataFrame, path: str, fmt: str, if_exists: str) -> None:
        client = _service_client(spec)
        if if_exists == "error":
            try:
                client.get_blob_client(container=spec.bucket, blob=path).get_blob_properties()
                raise ConnectorError(
                    f"Blob {spec.bucket}/{path} already exists. Set 'if_exists' to 'overwrite' to replace it."
                )
            except ConnectorError:
                raise
            except Exception:
                pass

        buf = io.BytesIO()
        try:
            if fmt == "csv":
                df.to_csv(buf, index=False)
            elif fmt == "excel":
                df.to_excel(buf, index=False)
            elif fmt == "parquet":
                df.to_parquet(buf, index=False)
            else:
                raise ConnectorError(f"Unsupported format {fmt!r}.")
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(f"Failed to serialize as {fmt}: {exc}") from None

        buf.seek(0)
        try:
            blob = client.get_blob_client(container=spec.bucket, blob=path)
            blob.upload_blob(buf, overwrite=(if_exists == "overwrite"))
        except ConnectorError:
            raise
        except Exception as exc:
            raise _guard(exc, spec.secret) from None
