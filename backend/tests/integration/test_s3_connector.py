"""Live round-trip tests for the S3 storage connector.

These exercise the real boto3 code path (``app/connectors/s3.py``) against an
S3-compatible endpoint — MinIO in CI (see ``.github/workflows/connectors-
integration.yml``), or any endpoint you point the env vars at locally.

The whole module self-skips unless ``FLOWFRAME_TEST_S3_ENDPOINT`` is set, so the
default infra-free suite is unaffected. To run locally against MinIO::

    docker run -d -p 9000:9000 -e MINIO_ROOT_USER=minioadmin \\
        -e MINIO_ROOT_PASSWORD=minioadmin minio/minio server /data
    FLOWFRAME_TEST_S3_ENDPOINT=http://127.0.0.1:9000 \\
    FLOWFRAME_TEST_S3_ACCESS_KEY=minioadmin \\
    FLOWFRAME_TEST_S3_SECRET_KEY=minioadmin \\
        pytest tests/integration/test_s3_connector.py -m connectors
"""

from __future__ import annotations

import os
import uuid

import pandas as pd
import pytest

from app.connectors.base import ConnectorError
from app.connectors.storage_base import StorageSpec

pytestmark = pytest.mark.connectors

_ENDPOINT = os.environ.get("FLOWFRAME_TEST_S3_ENDPOINT")
_ACCESS_KEY = os.environ.get("FLOWFRAME_TEST_S3_ACCESS_KEY", "minioadmin")
_SECRET_KEY = os.environ.get("FLOWFRAME_TEST_S3_SECRET_KEY", "minioadmin")
_REGION = os.environ.get("FLOWFRAME_TEST_S3_REGION", "us-east-1")

if not _ENDPOINT:
    pytest.skip(
        "FLOWFRAME_TEST_S3_ENDPOINT not set; skipping live S3 connector tests.",
        allow_module_level=True,
    )

boto3 = pytest.importorskip("boto3", reason="boto3 not installed (pip install flowframe[s3])")


def _spec(bucket: str) -> StorageSpec:
    return StorageSpec(
        provider="s3",
        bucket=bucket,
        access_key=_ACCESS_KEY,
        secret=_SECRET_KEY,
        region=_REGION,
        endpoint_url=_ENDPOINT,
    )


@pytest.fixture
def bucket():
    """Create a unique bucket for the test and tear it down afterwards."""
    name = f"flowframe-test-{uuid.uuid4().hex[:12]}"
    client = boto3.client(
        "s3",
        endpoint_url=_ENDPOINT,
        aws_access_key_id=_ACCESS_KEY,
        aws_secret_access_key=_SECRET_KEY,
        region_name=_REGION,
    )
    client.create_bucket(Bucket=name)
    try:
        yield name
    finally:
        # Empty the bucket before deleting it — S3 refuses to drop a non-empty one.
        try:
            objs = client.list_objects_v2(Bucket=name).get("Contents", [])
            for obj in objs:
                client.delete_object(Bucket=name, Key=obj["Key"])
            client.delete_bucket(Bucket=name)
        except Exception:  # pragma: no cover - best-effort cleanup
            pass


@pytest.fixture
def connector():
    from app.connectors.s3 import S3Connector

    return S3Connector()


def test_test_connection_succeeds_on_existing_bucket(connector, bucket):
    # Should not raise for a bucket that exists.
    connector.test_connection(_spec(bucket))


def test_test_connection_fails_on_missing_bucket(connector):
    with pytest.raises(ConnectorError):
        connector.test_connection(_spec(f"does-not-exist-{uuid.uuid4().hex[:8]}"))


@pytest.mark.parametrize("fmt", ["csv", "parquet"])
def test_write_then_read_round_trip(connector, bucket, fmt):
    spec = _spec(bucket)
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    key = f"data/sample.{fmt}"

    connector.write_file(spec, df, key, fmt, "overwrite")
    out = connector.read_file(spec, key, fmt)

    assert list(out.columns) == ["a", "b"]
    assert len(out) == 3
    assert out["a"].tolist() == [1, 2, 3]
    assert out["b"].tolist() == ["x", "y", "z"]


def test_list_objects_returns_written_keys(connector, bucket):
    spec = _spec(bucket)
    df = pd.DataFrame({"a": [1]})
    connector.write_file(spec, df, "prefix/one.csv", "csv", "overwrite")
    connector.write_file(spec, df, "prefix/two.csv", "csv", "overwrite")
    connector.write_file(spec, df, "other/three.csv", "csv", "overwrite")

    all_keys = connector.list_objects(spec)
    assert {"prefix/one.csv", "prefix/two.csv", "other/three.csv"} <= set(all_keys)

    scoped = connector.list_objects(spec, prefix="prefix/")
    assert set(scoped) == {"prefix/one.csv", "prefix/two.csv"}


def test_write_error_mode_rejects_existing_object(connector, bucket):
    spec = _spec(bucket)
    df = pd.DataFrame({"a": [1]})
    key = "guarded.csv"
    connector.write_file(spec, df, key, "csv", "overwrite")

    with pytest.raises(ConnectorError, match="already exists"):
        connector.write_file(spec, df, key, "csv", "error")


def test_overwrite_mode_replaces_existing_object(connector, bucket):
    spec = _spec(bucket)
    key = "replace.csv"
    connector.write_file(spec, pd.DataFrame({"a": [1]}), key, "csv", "overwrite")
    connector.write_file(spec, pd.DataFrame({"a": [1, 2, 3]}), key, "csv", "overwrite")

    out = connector.read_file(spec, key, "csv")
    assert len(out) == 3


def test_read_missing_object_raises(connector, bucket):
    with pytest.raises(ConnectorError):
        connector.read_file(_spec(bucket), "nope.csv", "csv")
