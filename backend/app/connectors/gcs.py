"""Google Cloud Storage connector via google-cloud-storage.

Security:
- ``password_env`` holds the NAME of an env var whose VALUE is the path to a
  service-account JSON key file.  The raw key content is never stored or
  transmitted — only the file path is resolved at connect time.
- If no key path is configured, Application Default Credentials (ADC) are used
  (``gcloud auth application-default login`` or Workload Identity).
- google-sdk debug logging is silenced.
- All errors are scrubbed of the key path before propagation.
"""
from __future__ import annotations

import io
import logging

import pandas as pd

from app.connectors.base import ConnectorError
from app.connectors.storage_base import StorageSpec
from app.core.secrets import scrub

for _logger in ("google", "urllib3.connectionpool"):
    logging.getLogger(_logger).setLevel(logging.CRITICAL)


def _client(spec: StorageSpec):
    try:
        from google.cloud import storage as gcs
    except ImportError as exc:
        raise ConnectorError(
            "google-cloud-storage is not installed. Run: pip install flowframe[gcs]"
        ) from exc

    project = spec.extra.get("project_id") or None
    credentials_path = spec.secret  # env var resolves to a local file path

    if credentials_path:
        try:
            from google.oauth2 import service_account

            creds = service_account.Credentials.from_service_account_file(
                credentials_path,
                scopes=["https://www.googleapis.com/auth/cloud-platform"],
            )
        except Exception as exc:
            raise ConnectorError(
                f"Failed to load GCS service-account key from {credentials_path!r}: {exc}"
            ) from None
        return gcs.Client(credentials=creds, project=project)

    # Fall back to Application Default Credentials (no explicit key file).
    return gcs.Client(project=project)


def _guard(exc: Exception, secret: str | None) -> ConnectorError:
    return ConnectorError(scrub(str(exc), secret or ""))


class GCSConnector:
    provider_kind = "storage"

    def test_connection(self, spec: StorageSpec) -> None:
        try:
            _client(spec).bucket(spec.bucket).reload()
        except ConnectorError:
            raise
        except Exception as exc:
            raise _guard(exc, spec.secret) from None

    def list_objects(self, spec: StorageSpec, prefix: str = "") -> list[str]:
        try:
            return [b.name for b in _client(spec).list_blobs(spec.bucket, prefix=prefix or None)]
        except ConnectorError:
            raise
        except Exception as exc:
            raise _guard(exc, spec.secret) from None

    def read_file(self, spec: StorageSpec, path: str, fmt: str) -> pd.DataFrame:
        try:
            body = _client(spec).bucket(spec.bucket).blob(path).download_as_bytes()
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
            raise ConnectorError(
                f"Failed to parse gs://{spec.bucket}/{path} as {fmt}: {exc}"
            ) from None

    def write_file(
        self, spec: StorageSpec, df: pd.DataFrame, path: str, fmt: str, if_exists: str
    ) -> None:
        client = _client(spec)
        blob = client.bucket(spec.bucket).blob(path)

        if if_exists == "error":
            try:
                if blob.exists():
                    raise ConnectorError(
                        f"Object gs://{spec.bucket}/{path} already exists."
                        " Set 'if_exists' to 'overwrite' to replace it."
                    )
            except ConnectorError:
                raise
            except Exception:
                pass

        buf = io.BytesIO()
        try:
            if fmt == "csv":
                df.to_csv(buf, index=False)
                content_type = "text/csv"
            elif fmt == "excel":
                df.to_excel(buf, index=False)
                content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            elif fmt == "parquet":
                df.to_parquet(buf, index=False)
                content_type = "application/octet-stream"
            else:
                raise ConnectorError(f"Unsupported format {fmt!r}.")
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(f"Failed to serialize as {fmt}: {exc}") from None

        buf.seek(0)
        try:
            blob.upload_from_file(buf, content_type=content_type)
        except ConnectorError:
            raise
        except Exception as exc:
            raise _guard(exc, spec.secret) from None
