"""AWS S3 (and S3-compatible) storage connector via boto3.

Security:
- The Access Key ID (a public identifier) may be stored in ``username``.
- The Secret Access Key is resolved from ``password_env`` at call time — NEVER stored.
- When both access_key and secret are absent, boto3 uses its credential chain
  (IAM role, instance profile, env vars, ~/.aws/credentials) automatically.
- boto3 / botocore debug logging is silenced to prevent credential material
  reaching log files.
- All errors are scrubbed of the secret before propagation.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from app.connectors.base import ConnectorError
from app.connectors.storage_base import StorageSpec, deserialize_dataframe, serialize_dataframe
from app.core.secrets import scrub

# Silencing these prevents Access Key / token values leaking into log output.
for _logger in ("boto3", "botocore", "s3transfer"):
    logging.getLogger(_logger).setLevel(logging.CRITICAL)


def _client(spec: StorageSpec) -> Any:
    try:
        import boto3
    except ImportError as exc:
        raise ConnectorError("boto3 is not installed. Run: pip install flowframe[s3]") from exc

    kwargs: dict[str, Any] = {}
    if spec.region:
        kwargs["region_name"] = spec.region
    if spec.endpoint_url:
        kwargs["endpoint_url"] = spec.endpoint_url
    # Only pass explicit credentials when both are present; otherwise fall through
    # to boto3's own credential chain (IAM role, env vars, ~/.aws/credentials).
    if spec.access_key and spec.secret:
        kwargs["aws_access_key_id"] = spec.access_key
        kwargs["aws_secret_access_key"] = spec.secret
    return boto3.client("s3", **kwargs)


def _guard(exc: Exception, secret: str | None) -> ConnectorError:
    return ConnectorError(scrub(str(exc), secret))


class S3Connector:
    provider_kind = "storage"

    def test_connection(self, spec: StorageSpec) -> None:
        try:
            _client(spec).head_bucket(Bucket=spec.bucket)
        except Exception as exc:
            raise _guard(exc, spec.secret) from None

    def list_objects(self, spec: StorageSpec, prefix: str = "") -> list[str]:
        client = _client(spec)
        try:
            paginator = client.get_paginator("list_objects_v2")
            keys: list[str] = []
            for page in paginator.paginate(Bucket=spec.bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            return keys
        except Exception as exc:
            raise _guard(exc, spec.secret) from None

    def read_file(self, spec: StorageSpec, path: str, fmt: str) -> pd.DataFrame:
        client = _client(spec)
        try:
            body = client.get_object(Bucket=spec.bucket, Key=path)["Body"].read()
        except Exception as exc:
            raise _guard(exc, spec.secret) from None
        try:
            return deserialize_dataframe(body, fmt)
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(f"Failed to parse s3://{spec.bucket}/{path} as {fmt}: {exc}") from None

    def write_file(self, spec: StorageSpec, df: pd.DataFrame, path: str, fmt: str, if_exists: str) -> None:
        client = _client(spec)
        if if_exists == "error":
            try:
                client.head_object(Bucket=spec.bucket, Key=path)
                raise ConnectorError(
                    f"Object s3://{spec.bucket}/{path} already exists. Set 'if_exists' to 'overwrite' to replace it."
                )
            except ConnectorError:
                raise
            except Exception:
                pass  # Object doesn't exist — safe to write.

        try:
            data, content_type = serialize_dataframe(df, fmt)
        except ConnectorError:
            raise
        except Exception as exc:
            raise ConnectorError(f"Failed to serialize data as {fmt}: {exc}") from None

        try:
            client.put_object(Bucket=spec.bucket, Key=path, Body=data, ContentType=content_type)
        except Exception as exc:
            raise _guard(exc, spec.secret) from None
